"""
Capturing the audio of one application.

Windows has an API for this - process loopback, added in build 20348 - but
nothing in the Python audio stack exposes it, so the COM plumbing is done
here by hand.

The shape of it: ActivateAudioInterfaceAsync is asked for an IAudioClient
against the pseudo-device "VAD\\Process_Loopback", with a blob naming the
target process. Activation is asynchronous and demands a completion
handler, which means implementing a COM interface in Python. From there it
behaves like any other WASAPI capture client.

Note the process ID is the top of a tree: Chrome, Discord and Steam all
run their audio in child processes, so asking for the parent and including
its tree is what actually gets the sound.
"""

import ctypes
import ctypes.wintypes as wt
import threading
import time
import wave

import numpy as np
from comtypes import COMObject, GUID, IUnknown, COMMETHOD, HRESULT

MIN_BUILD = 20348

# Activation types and modes from audioclientactivationparams.h
AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK = 1
INCLUDE_TARGET_PROCESS_TREE = 0
EXCLUDE_TARGET_PROCESS_TREE = 1

VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK = "VAD\\Process_Loopback"

AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
AUDCLNT_STREAMFLAGS_EVENTCALLBACK = 0x00040000
AUDCLNT_BUFFERFLAGS_SILENT = 0x2

WAVE_FORMAT_PCM = 1
VT_BLOB = 65

# 100-nanosecond units, which is how WASAPI measures durations.
REFTIMES_PER_SEC = 10_000_000


class PROCESS_LOOPBACK_PARAMS(ctypes.Structure):
    _fields_ = [("TargetProcessId", wt.DWORD),
                ("ProcessLoopbackMode", ctypes.c_int)]


class ACTIVATION_PARAMS(ctypes.Structure):
    _fields_ = [("ActivationType", ctypes.c_int),
                ("ProcessLoopbackParams", PROCESS_LOOPBACK_PARAMS)]


class BLOB(ctypes.Structure):
    _fields_ = [("cbSize", wt.ULONG), ("pBlobData", ctypes.c_void_p)]


class PROPVARIANT(ctypes.Structure):
    # Only the blob member is used, but the padding has to be right or the
    # struct is the wrong size and the call fails in confusing ways.
    _fields_ = [("vt", ctypes.c_ushort), ("wReserved1", ctypes.c_ushort),
                ("wReserved2", ctypes.c_ushort),
                ("wReserved3", ctypes.c_ushort),
                ("blob", BLOB), ("padding", ctypes.c_byte * 8)]


class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [("wFormatTag", wt.WORD), ("nChannels", wt.WORD),
                ("nSamplesPerSec", wt.DWORD), ("nAvgBytesPerSec", wt.DWORD),
                ("nBlockAlign", wt.WORD), ("wBitsPerSample", wt.WORD),
                ("cbSize", wt.WORD)]


# --- the COM interfaces involved ---------------------------------------

class IActivateAudioInterfaceAsyncOperation(IUnknown):
    _iid_ = GUID("{72A22D78-CDE4-431D-B8CC-843A71199B6D}")
    _methods_ = [
        # activateResult is declared as a plain long rather than HRESULT.
        # comtypes treats an HRESULT as the call's own status and would
        # raise on a failure code, losing the value we actually want to
        # read and report.
        COMMETHOD([], HRESULT, "GetActivateResult",
                  (["out"], ctypes.POINTER(ctypes.c_long), "activateResult"),
                  (["out"], ctypes.POINTER(ctypes.POINTER(IUnknown)),
                   "activatedInterface")),
    ]


class IActivateAudioInterfaceCompletionHandler(IUnknown):
    _iid_ = GUID("{41D949AB-9862-444A-80F6-C261334DA5EB}")
    _methods_ = [
        COMMETHOD([], HRESULT, "ActivateCompleted",
                  (["in"], ctypes.POINTER(IActivateAudioInterfaceAsyncOperation),
                   "activateOperation")),
    ]


class IAudioClient(IUnknown):
    _iid_ = GUID("{1CB9AD4C-DBFA-4c32-B178-C2F568A703B2}")
    _methods_ = [
        COMMETHOD([], HRESULT, "Initialize",
                  (["in"], ctypes.c_int, "ShareMode"),
                  (["in"], wt.DWORD, "StreamFlags"),
                  (["in"], ctypes.c_longlong, "hnsBufferDuration"),
                  (["in"], ctypes.c_longlong, "hnsPeriodicity"),
                  (["in"], ctypes.POINTER(WAVEFORMATEX), "pFormat"),
                  (["in"], ctypes.POINTER(GUID), "AudioSessionGuid")),
        COMMETHOD([], HRESULT, "GetBufferSize",
                  (["out"], ctypes.POINTER(wt.UINT), "pNumBufferFrames")),
        COMMETHOD([], HRESULT, "GetStreamLatency",
                  (["out"], ctypes.POINTER(ctypes.c_longlong), "phnsLatency")),
        COMMETHOD([], HRESULT, "GetCurrentPadding",
                  (["out"], ctypes.POINTER(wt.UINT), "pNumPaddingFrames")),
        COMMETHOD([], HRESULT, "IsFormatSupported",
                  (["in"], ctypes.c_int, "ShareMode"),
                  (["in"], ctypes.POINTER(WAVEFORMATEX), "pFormat"),
                  (["out"], ctypes.POINTER(ctypes.POINTER(WAVEFORMATEX)),
                   "ppClosestMatch")),
        COMMETHOD([], HRESULT, "GetMixFormat",
                  (["out"], ctypes.POINTER(ctypes.POINTER(WAVEFORMATEX)),
                   "ppDeviceFormat")),
        COMMETHOD([], HRESULT, "GetDevicePeriod",
                  (["out"], ctypes.POINTER(ctypes.c_longlong), "default"),
                  (["out"], ctypes.POINTER(ctypes.c_longlong), "minimum")),
        COMMETHOD([], HRESULT, "Start"),
        COMMETHOD([], HRESULT, "Stop"),
        COMMETHOD([], HRESULT, "Reset"),
        COMMETHOD([], HRESULT, "SetEventHandle",
                  (["in"], wt.HANDLE, "eventHandle")),
        COMMETHOD([], HRESULT, "GetService",
                  (["in"], ctypes.POINTER(GUID), "riid"),
                  (["out"], ctypes.POINTER(ctypes.POINTER(IUnknown)), "ppv")),
    ]


class IAudioCaptureClient(IUnknown):
    _iid_ = GUID("{C8ADBD64-E71E-48a0-A4DE-185C395CD317}")
    _methods_ = [
        COMMETHOD([], HRESULT, "GetBuffer",
                  (["out"], ctypes.POINTER(ctypes.POINTER(ctypes.c_byte)),
                   "ppData"),
                  (["out"], ctypes.POINTER(wt.UINT), "pNumFramesToRead"),
                  (["out"], ctypes.POINTER(wt.DWORD), "pdwFlags"),
                  (["out"], ctypes.POINTER(ctypes.c_ulonglong), "pu64Position"),
                  (["out"], ctypes.POINTER(ctypes.c_ulonglong), "pu64QPC")),
        COMMETHOD([], HRESULT, "ReleaseBuffer",
                  (["in"], wt.UINT, "NumFramesRead")),
        COMMETHOD([], HRESULT, "GetNextPacketSize",
                  (["out"], ctypes.POINTER(wt.UINT), "pNumFramesInNextPacket")),
    ]


class IAgileObject(IUnknown):
    """
    Marker interface, no methods of its own.

    Windows delivers the activation callback from a different apartment,
    so the handler has to be agile or it is rejected before activation
    even starts - with E_ILLEGAL_METHOD_CALL, which says nothing about
    threading and sends you looking in the wrong place entirely. The C++
    sample gets this for free by deriving from FtmBase.
    """

    _iid_ = GUID("{94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90}")
    _methods_ = []


class CompletionHandler(COMObject):
    """
    Activation is asynchronous and the handler is not optional, so this
    exists purely to signal an event the calling thread waits on.

    Declaring IAgileObject is what makes Windows accept it.
    """

    _com_interfaces_ = [IActivateAudioInterfaceCompletionHandler,
                        IAgileObject]

    def __init__(self):
        super().__init__()
        self.done = threading.Event()

    def ActivateCompleted(self, operation):
        self.done.set()
        return 0


# --- capture ------------------------------------------------------------

def is_supported():
    """Process loopback needs Windows 10 build 20348 or newer."""
    try:
        ver = ctypes.windll.ntdll.RtlGetVersion
    except Exception:
        return False, "Windows version could not be read"

    class OSVERSIONINFOEXW(ctypes.Structure):
        _fields_ = [("dwOSVersionInfoSize", wt.DWORD),
                    ("dwMajorVersion", wt.DWORD),
                    ("dwMinorVersion", wt.DWORD),
                    ("dwBuildNumber", wt.DWORD),
                    ("dwPlatformId", wt.DWORD),
                    ("szCSDVersion", ctypes.c_wchar * 128),
                    ("wServicePackMajor", wt.WORD),
                    ("wServicePackMinor", wt.WORD),
                    ("wSuiteMask", wt.WORD),
                    ("wProductType", ctypes.c_byte),
                    ("wReserved", ctypes.c_byte)]

    info = OSVERSIONINFOEXW()
    info.dwOSVersionInfoSize = ctypes.sizeof(info)
    ver(ctypes.byref(info))
    build = info.dwBuildNumber
    if build >= MIN_BUILD:
        return True, f"build {build}"
    return False, (f"Windows build {build} is too old for per-application "
                   f"capture; {MIN_BUILD} or newer is needed")


class ProcessRecorder:
    """
    Records what one process (and its children) is playing.

    Presents the same surface as the ordinary Recorder - name, label,
    record(), close() - so the engine does not need to care which it has.
    """

    def __init__(self, pid, name="", rate=48000, channels=2,
                 include_tree=True):
        ok, why = is_supported()
        if not ok:
            raise RuntimeError(why)
        self.pid = int(pid)
        self.process_name = name or str(pid)
        self.rate = rate
        self.channels = channels
        self.include_tree = include_tree
        self.kind = "process"

    @property
    def name(self):
        return self.process_name

    @property
    def label(self):
        return f"{self.process_name}  (application)"

    def _activate(self):
        """Ask Windows for an IAudioClient bound to the target process."""
        params = ACTIVATION_PARAMS()
        params.ActivationType = AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK
        params.ProcessLoopbackParams.TargetProcessId = self.pid
        params.ProcessLoopbackParams.ProcessLoopbackMode = (
            INCLUDE_TARGET_PROCESS_TREE if self.include_tree
            else EXCLUDE_TARGET_PROCESS_TREE)

        prop = PROPVARIANT()
        prop.vt = VT_BLOB
        prop.blob.cbSize = ctypes.sizeof(params)
        prop.blob.pBlobData = ctypes.cast(ctypes.byref(params),
                                          ctypes.c_void_p)

        handler = CompletionHandler()
        operation = ctypes.POINTER(IActivateAudioInterfaceAsyncOperation)()

        mmdevapi = ctypes.WinDLL("mmdevapi.dll")
        fn = mmdevapi.ActivateAudioInterfaceAsync
        fn.restype = HRESULT
        fn.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(GUID),
                       ctypes.POINTER(PROPVARIANT), ctypes.c_void_p,
                       ctypes.POINTER(
                           ctypes.POINTER(
                               IActivateAudioInterfaceAsyncOperation))]

        hr = fn(VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK,
                ctypes.byref(IAudioClient._iid_), ctypes.byref(prop),
                ctypes.cast(handler._com_pointers_[
                    IActivateAudioInterfaceCompletionHandler._iid_],
                    ctypes.c_void_p),
                ctypes.byref(operation))
        if hr != 0:
            raise RuntimeError(f"ActivateAudioInterfaceAsync failed: 0x{hr:08X}")

        if not handler.done.wait(timeout=5):
            raise RuntimeError("Windows never finished activating the "
                               "capture stream for that application.")

        # comtypes hands back [out] parameters as return values rather
        # than filling in pointers passed as arguments.
        activate_hr, unknown = operation.GetActivateResult()
        if activate_hr != 0:
            raise RuntimeError(
                f"That application could not be captured (0x"
                f"{activate_hr & 0xFFFFFFFF:08X}). It may not be playing "
                f"any audio.")
        return unknown.QueryInterface(IAudioClient)

    def _open(self):
        """
        Set up a capture stream for the target process.

        Shared by both the fixed-length and sound-triggered paths, which
        differ only in when they decide to stop.
        """
        fmt = WAVEFORMATEX()
        fmt.wFormatTag = WAVE_FORMAT_PCM
        fmt.nChannels = self.channels
        fmt.nSamplesPerSec = self.rate
        fmt.wBitsPerSample = 16
        fmt.nBlockAlign = fmt.nChannels * fmt.wBitsPerSample // 8
        fmt.nAvgBytesPerSec = fmt.nSamplesPerSec * fmt.nBlockAlign
        fmt.cbSize = 0

        client = self._activate()
        client.Initialize(
            AUDCLNT_SHAREMODE_SHARED,
            AUDCLNT_STREAMFLAGS_LOOPBACK | AUDCLNT_STREAMFLAGS_EVENTCALLBACK,
            2 * REFTIMES_PER_SEC // 10,     # 200ms of buffer
            0, ctypes.byref(fmt), None)

        event = ctypes.windll.kernel32.CreateEventW(None, False, False, None)
        client.SetEventHandle(event)
        unknown = client.GetService(ctypes.byref(IAudioCaptureClient._iid_))
        capture = unknown.QueryInterface(IAudioCaptureClient)
        return fmt, client, capture, event

    def record(self, path, seconds, cancel=None, on_level=None):
        """
        Record `seconds` of that application's audio to `path`.

        Same contract as the ordinary Recorder: returns the RMS, honours
        cancel, and reports levels as it goes.
        """
        fmt, client, capture, event = self._open()

        frames = []
        every = max(1, int(self.rate / 2048 / 20))
        block_count = 0
        client.Start()
        try:
            end = time.time() + seconds
            while time.time() < end:
                if cancel and cancel():
                    break
                # A 200ms wait keeps this responsive to cancellation while
                # still blocking rather than spinning.
                ctypes.windll.kernel32.WaitForSingleObject(event, 200)
                while True:
                    try:
                        count = capture.GetNextPacketSize()
                    except Exception:
                        break
                    if not count:
                        break
                    data, got, flags, _pos, _qpc = capture.GetBuffer()
                    n = got * fmt.nBlockAlign
                    if flags & AUDCLNT_BUFFERFLAGS_SILENT:
                        # Windows hands back a silent packet rather than
                        # nothing when the app is idle; it must still be
                        # written or the clip ends up shorter than asked.
                        chunk = b"\x00" * n
                    else:
                        chunk = ctypes.string_at(data, n)
                    frames.append(chunk)
                    capture.ReleaseBuffer(got)

                    block_count += 1
                    if on_level and block_count % every == 0:
                        block = np.frombuffer(chunk, dtype=np.int16)
                        if block.size:
                            block = block.astype(np.float32)
                            on_level(float(np.sqrt(np.mean(block * block))))
        finally:
            try:
                client.Stop()
            except Exception:
                pass
            ctypes.windll.kernel32.CloseHandle(event)

        data = b"".join(frames)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(fmt.nChannels)
            wf.setsampwidth(2)
            wf.setframerate(fmt.nSamplesPerSec)
            wf.writeframes(data)

        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        if samples.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples * samples)))

    def record_activated(self, path, gate, cancel=None, on_level=None,
                         on_state=None):
        """
        Sound-triggered capture from one application.

        Same contract as the ordinary recorder's version, so the engine
        does not care which kind of source it is driving.
        """
        from collections import deque

        from .audio import DONE, WAITING

        fmt, client, capture, event = self._open()
        block_align = fmt.nBlockAlign
        rate = fmt.nSamplesPerSec
        lead = deque(maxlen=24)          # roughly a third of a second
        frames = []
        last_state = None

        client.Start()
        try:
            while True:
                if cancel and cancel():
                    break
                ctypes.windll.kernel32.WaitForSingleObject(event, 200)
                while True:
                    try:
                        if not capture.GetNextPacketSize():
                            break
                    except Exception:
                        break
                    data, got, flags, _p, _q = capture.GetBuffer()
                    n = got * block_align
                    if flags & AUDCLNT_BUFFERFLAGS_SILENT:
                        buf = b"\x00" * n
                    else:
                        buf = ctypes.string_at(data, n)
                    capture.ReleaseBuffer(got)

                    block = np.frombuffer(buf, dtype=np.int16)
                    rms = 0.0
                    if block.size:
                        b = block.astype(np.float32)
                        rms = float(np.sqrt(np.mean(b * b)))
                    if on_level:
                        on_level(rms)

                    dt = (got / rate) if rate else 0.0
                    state = gate.feed(rms, dt)
                    if state != last_state:
                        last_state = state
                        if on_state:
                            on_state(state, gate)

                    if state == WAITING:
                        lead.append(buf)
                        continue
                    if not frames:
                        frames.extend(lead)
                    frames.append(buf)
                if last_state == DONE:
                    break
        finally:
            try:
                client.Stop()
            except Exception:
                pass
            ctypes.windll.kernel32.CloseHandle(event)

        data = b"".join(frames)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(fmt.nChannels)
            wf.setsampwidth(2)
            wf.setframerate(fmt.nSamplesPerSec)
            wf.writeframes(data)

        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        rms = (float(np.sqrt(np.mean(samples * samples)))
               if samples.size else 0.0)
        return rms, gate

    def close(self):
        pass


# --- finding something to capture --------------------------------------

# Background noise that nobody wants to point the app at.
_IGNORE = {"explorer.exe", "rainmeter.exe", "wallpaper64.exe",
           "textinputhost.exe", "shellexperiencehost.exe",
           "searchhost.exe", "voicemod.exe", "audiodg.exe",
           "wispwasp.exe", "python.exe", "pythonw.exe"}

_FRIENDLY = {
    "discord.exe": "Discord",
    "chrome.exe": "Chrome",
    "msedge.exe": "Edge",
    "firefox.exe": "Firefox",
    "opera.exe": "Opera",
    "opera_gx.exe": "Opera GX",
    "brave.exe": "Brave",
    "steam.exe": "Steam",
    "steamwebhelper.exe": "Steam",
    "spotify.exe": "Spotify",
    "vlc.exe": "VLC",
    "obs64.exe": "OBS",
    "slack.exe": "Slack",
    "teams.exe": "Teams",
}


def _root_of(proc):
    """
    Walk up to the top process of an application.

    Browsers, Discord and Steam all play audio from a child process, so
    capturing the child alone would miss anything a sibling plays. Taking
    the highest ancestor sharing the executable name and including its
    tree captures the application as a whole.
    """
    import psutil

    best = proc
    try:
        current = proc
        for _ in range(6):
            parent = current.parent()
            if parent is None:
                break
            if parent.name().lower() == proc.name().lower():
                best = parent
            current = parent
    except Exception:
        pass
    return best


def audible_processes(include_silent=True):
    """
    Applications that can be captured, the ones making noise first.

    A list of every window on the desktop would be useless; the audio
    session list is exactly the set of programs that have opened an audio
    stream, and the peak meter says which are actually playing.
    """
    try:
        import psutil
        from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
    except ImportError:
        return []

    grouped = {}
    try:
        sessions = AudioUtilities.GetAllSessions()
    except Exception:
        return []

    for session in sessions:
        proc = getattr(session, "Process", None)
        if proc is None:
            continue
        try:
            exe = proc.name()
        except Exception:
            continue
        if exe.lower() in _IGNORE:
            continue

        try:
            peak = session._ctl.QueryInterface(
                IAudioMeterInformation).GetPeakValue()
        except Exception:
            peak = 0.0

        try:
            root = _root_of(proc)
            pid, root_exe = root.pid, root.name()
        except Exception:
            pid, root_exe = proc.pid, exe

        label = _FRIENDLY.get(root_exe.lower(),
                              root_exe.rsplit(".", 1)[0].title())
        entry = grouped.setdefault(pid, {
            "pid": pid, "exe": root_exe, "name": label, "peak": 0.0,
        })
        entry["peak"] = max(entry["peak"], peak)

    out = [e for e in grouped.values()
           if include_silent or e["peak"] > 0.0001]
    for e in out:
        e["playing"] = e["peak"] > 0.0001
    # Loudest first, then alphabetical, so whatever is actually making
    # noise is at the top of the list.
    out.sort(key=lambda e: (-e["peak"], e["name"].lower()))
    return out

# --- a self-check, so failures are explicable ---------------------------

def describe_failure(exc):
    """Turn a COM error into something a person can act on."""
    text = str(exc)
    if "0x88890001" in text or "AUDCLNT_E_NOT_INITIALIZED" in text:
        return ("Windows refused the capture stream. The application may "
                "have closed, or it may not have played any audio yet.")
    if "0x80070057" in text:
        return ("Windows rejected the capture settings for that "
                "application.")
    if "too old" in text:
        return text
    return text


def find_by_name(exe):
    """
    Find a running process by executable name.

    Process IDs do not survive a restart, so a saved target is stored by
    name as well and re-found here. Otherwise picking "Discord" would work
    until you next closed it, then silently capture nothing.
    """
    if not exe:
        return None
    wanted = exe.lower()
    for entry in audible_processes():
        if entry["exe"].lower() == wanted:
            return entry
    # Not currently holding an audio session, so fall back to any running
    # process with that name; it may simply not have played anything yet.
    try:
        import psutil
        for proc in psutil.process_iter(["name", "pid"]):
            if (proc.info["name"] or "").lower() == wanted:
                root = _root_of(proc)
                return {"pid": root.pid, "exe": exe,
                        "name": _FRIENDLY.get(wanted,
                                              exe.rsplit(".", 1)[0].title()),
                        "peak": 0.0, "playing": False}
    except Exception:
        pass
    return None
