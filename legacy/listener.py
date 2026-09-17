r"""
Listens to whatever your PC is playing, transcribes ~10s of it every minute,
turns that into an image prompt, generates an image, and shows the newest one
on a local page you can capture in OBS.

Run:  .\.venv\Scripts\python.exe listener.py
Then open http://localhost:8420 and window-capture it in OBS.
"""

import os
import re
import socket
import threading
import time
import urllib.parse
import wave
from datetime import datetime
from pathlib import Path

import numpy as np
import pyaudiowpatch as pyaudio
import requests
from faster_whisper import WhisperModel
from flask import Flask, jsonify, send_from_directory

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RECORD_SECONDS = 10          # length of each listening window
CYCLE_SECONDS = 22           # 10s record + ~1.5s transcribe + ~8s render
PORT = 8420

WHISPER_MODEL = "small.en"   # base.en is faster but noticeably less accurate
CPU_THREADS = 4              # keep Whisper from grabbing every core

BACKEND = "comfyui"     # "comfyui" or "pollinations"

# Local ComfyUI settings. Start ComfyUI first (run-comfyui.bat in its folder).
COMFY_URL = "http://127.0.0.1:8188"
COMFY_CHECKPOINT = ""        # blank = auto-detect the first checkpoint found
COMFY_STEPS = 8             # Turbo/Lightning models want 4-8 instead
COMFY_CFG = 1.5              # Turbo/Lightning models want 1.0-2.0
COMFY_SAMPLER = "dpmpp_2m"
COMFY_SCHEDULER = "karras"
COMFY_TIMEOUT = 180          # seconds to wait for one image
IMAGE_SIZE = (1344, 768)     # native SDXL 16:9 - don't go far below ~1MP
STYLE_SUFFIX = (
    "High Detail, deplorable, legs spread bent over, bright lighting"
)

NEGATIVE_PROMPT = (
    " "
    " "
)

SILENCE_RMS = 250            # below this, treat the clip as silence and skip
MIN_WORDS = 3                # shorter than this and the clip is skipped
MAX_PROMPT_CHARS = 400       # keeps the request URL a sane length
KEEP_IMAGES = 40             # delete older files beyond this count

BASE = Path(__file__).parent
OUT_DIR = BASE / "output"
OUT_DIR.mkdir(exist_ok=True)

# Whisper reliably invents these when fed silence or music.
HALLUCINATIONS = {
    "you", "thank you", "thanks for watching", "thank you for watching",
    "bye", "bye bye", "subscribe", "please subscribe", "okay", "so",
    "thanks", "the end", "music", "applause", "outro", "intro",
}

# ---------------------------------------------------------------------------
# Shared state between the worker thread and the web server
# ---------------------------------------------------------------------------

state = {
    "prompt": None,
    "heard": None,
    "image": None,
    "updated": 0,
    "status": "starting up",
}
state_lock = threading.Lock()


def set_state(**kwargs):
    with state_lock:
        state.update(kwargs)


# ---------------------------------------------------------------------------
# Audio capture
# ---------------------------------------------------------------------------

def find_loopback(pa):
    """Get the loopback device for the current default speakers."""
    wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
    default_out = pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
    for dev in pa.get_loopback_device_info_generator():
        if default_out["name"] in dev["name"]:
            return dev
    raise RuntimeError(
        "No loopback device matched your default speakers. "
        "Make sure PyAudioWPatch is installed, not plain PyAudio."
    )


def record_clip(pa, device, path):
    """Record RECORD_SECONDS of system audio. Returns the clip's RMS level."""
    rate = int(device["defaultSampleRate"])
    channels = device["maxInputChannels"]
    chunk = 1024

    stream = pa.open(
        format=pyaudio.paInt16,
        channels=channels,
        rate=rate,
        input=True,
        input_device_index=device["index"],
        frames_per_buffer=chunk,
    )
    frames = []
    try:
        for _ in range(int(rate / chunk * RECORD_SECONDS)):
            frames.append(stream.read(chunk, exception_on_overflow=False))
    finally:
        stream.stop_stream()
        stream.close()

    data = b"".join(frames)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
        wf.setframerate(rate)
        wf.writeframes(data)

    # audioop was removed in Python 3.13, so compute RMS with numpy.
    samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples * samples)))


# ---------------------------------------------------------------------------
# Transcription and prompt building
# ---------------------------------------------------------------------------

def transcribe(model, path):
    segments, _ = model.transcribe(
        str(path),
        beam_size=5,              # was 1; searches harder for the best wording
        language="en",
        temperature=0.0,          # no random fallback decoding
        vad_filter=True,          # cut non-speech before decoding
        vad_parameters=dict(min_silence_duration_ms=300),
        condition_on_previous_text=False,  # stops repetition loops
    )
    return " ".join(s.text.strip() for s in segments).strip()


def looks_repetitive(text):
    """Catch Whisper's stuck-loop output, e.g. 'we are, we are, we are...'."""
    words = text.lower().split()
    if len(words) < 8:
        return False
    return len(set(words)) / len(words) < 0.35


def build_prompt(text):
    """Pass the speech through as-is. Only rejects junk; never rewrites."""
    prompt = " ".join(text.split())
    if not prompt:
        return None

    # Normalised copy, used only for the junk checks below.
    bare = re.sub(r"[^\w\s']", "", prompt.lower()).strip()
    if not bare or bare in HALLUCINATIONS:
        return None
    if len(bare.split()) < MIN_WORDS:
        return None
    if looks_repetitive(bare):
        return None

    if len(prompt) > MAX_PROMPT_CHARS:
        prompt = prompt[:MAX_PROMPT_CHARS].rsplit(" ", 1)[0]

    if STYLE_SUFFIX:
        prompt = f"{prompt}, {STYLE_SUFFIX}"
    return prompt


# ---------------------------------------------------------------------------
# Image backends
# ---------------------------------------------------------------------------

def generate_pollinations(prompt, dest):
    w, h = IMAGE_SIZE
    url = (
        "https://image.pollinations.ai/prompt/"
        + urllib.parse.quote(prompt)
        + f"?width={w}&height={h}&nologo=true&seed={int(time.time())}"
    )
    if NEGATIVE_PROMPT:
        url += "&negative_prompt=" + urllib.parse.quote(NEGATIVE_PROMPT)
    r = None
    for attempt, wait in enumerate((0, 6, 14)):
        if wait:
            set_state(status=f"retrying in {wait}s")
            time.sleep(wait)
        r = requests.get(url, timeout=180)
        if r.status_code == 429 or r.status_code >= 500:
            continue
        r.raise_for_status()
        dest.write_bytes(r.content)
        return dest

    raise RuntimeError(
        f"Pollinations returned {r.status_code} three times - skipped this "
        "cycle. If 429s keep happening, raise CYCLE_SECONDS."
    )


_comfy_ckpt = None


def comfy_checkpoint():
    """Find a checkpoint to use, caching the answer."""
    global _comfy_ckpt
    if _comfy_ckpt:
        return _comfy_ckpt
    if COMFY_CHECKPOINT:
        _comfy_ckpt = COMFY_CHECKPOINT
        return _comfy_ckpt

    r = requests.get(f"{COMFY_URL}/object_info/CheckpointLoaderSimple",
                     timeout=30)
    r.raise_for_status()
    names = r.json()["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
    if not names:
        raise RuntimeError(
            "No checkpoint found. Put a .safetensors model in "
            "ComfyUI\\models\\checkpoints and restart ComfyUI."
        )
    _comfy_ckpt = names[0]
    print(f"  using checkpoint: {_comfy_ckpt}")
    return _comfy_ckpt


def generate_comfyui(prompt, dest):
    """Render locally through the ComfyUI HTTP API."""
    w, h = IMAGE_SIZE
    ckpt = comfy_checkpoint()

    workflow = {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode",
              "inputs": {"text": NEGATIVE_PROMPT, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": w, "height": h, "batch_size": 1}},
        "5": {"class_type": "KSampler",
              "inputs": {"seed": int(time.time() * 1000) % 2**31,
                         "steps": COMFY_STEPS, "cfg": COMFY_CFG,
                         "sampler_name": COMFY_SAMPLER,
                         "scheduler": COMFY_SCHEDULER, "denoise": 1.0,
                         "model": ["1", 0], "positive": ["2", 0],
                         "negative": ["3", 0], "latent_image": ["4", 0]}},
        "6": {"class_type": "VAEDecode",
              "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage",
              "inputs": {"images": ["6", 0], "filename_prefix": "listener"}},
    }

    r = requests.post(f"{COMFY_URL}/prompt", json={"prompt": workflow},
                      timeout=30)
    if r.status_code == 400:
        raise RuntimeError(f"ComfyUI rejected the workflow: {r.text[:300]}")
    r.raise_for_status()
    pid = r.json()["prompt_id"]

    deadline = time.time() + COMFY_TIMEOUT
    while time.time() < deadline:
        time.sleep(0.4)
        h_r = requests.get(f"{COMFY_URL}/history/{pid}", timeout=30)
        h_r.raise_for_status()
        hist = h_r.json().get(pid)
        if not hist:
            continue

        status = hist.get("status", {})
        if status.get("status_str") == "error":
            raise RuntimeError(f"ComfyUI failed to render: {status}")

        for node in hist.get("outputs", {}).values():
            for img in node.get("images", []):
                v = requests.get(
                    f"{COMFY_URL}/view",
                    params={"filename": img["filename"],
                            "subfolder": img.get("subfolder", ""),
                            "type": img.get("type", "output")},
                    timeout=60)
                v.raise_for_status()
                dest.write_bytes(v.content)
                return dest

    raise RuntimeError(f"ComfyUI did not return an image in {COMFY_TIMEOUT}s")


def generate(prompt, dest):
    if BACKEND == "comfyui":
        return generate_comfyui(prompt, dest)
    return generate_pollinations(prompt, dest)


def prune_images():
    files = sorted(OUT_DIR.glob("img_*.*"), key=lambda p: p.stat().st_mtime)
    for old in files[:-KEEP_IMAGES]:
        old.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Worker loop
# ---------------------------------------------------------------------------

def worker():
    set_state(status="loading speech model")
    print("Loading speech model (first run downloads ~75 MB)...")
    model = WhisperModel(
        WHISPER_MODEL, device="cpu", compute_type="int8", cpu_threads=CPU_THREADS
    )

    pa = pyaudio.PyAudio()
    device = find_loopback(pa)
    print(f"Listening to: {device['name']}\n")
    set_state(status="listening")

    clip = BASE / "clip.wav"

    while True:
        started = time.time()
        try:
            set_state(status="listening")
            level = record_clip(pa, device, clip)

            if level < SILENCE_RMS:
                set_state(status="nothing to hear")
                raise StopIteration

            set_state(status="transcribing")
            t0 = time.time()
            heard = transcribe(model, clip)
            t_stt = time.time() - t0
            prompt = build_prompt(heard)

            if not prompt:
                set_state(status="no usable speech", heard=heard or "")
                raise StopIteration

            print(f"heard:  {heard}")
            print(f"prompt: {prompt}")
            set_state(status="generating image", heard=heard, prompt=prompt)

            ext = "png" if BACKEND == "comfyui" else "jpg"
            name = f"img_{datetime.now():%H%M%S}.{ext}"
            t1 = time.time()
            generate(prompt, OUT_DIR / name)
            prune_images()
            print(f"  [stt {t_stt:.1f}s | image {time.time() - t1:.1f}s | "
                  f"cycle {time.time() - started:.1f}s]")

            set_state(image=name, updated=time.time(), status="listening")

        except StopIteration:
            pass
        except Exception as exc:
            print(f"[error] {exc}")
            set_state(status=f"error: {exc}")

        remaining = CYCLE_SECONDS - (time.time() - started)
        if remaining > 0:
            time.sleep(remaining)


# ---------------------------------------------------------------------------
# Web server
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder=None)


@app.route("/")
def index():
    return send_from_directory(BASE, "overlay.html")


@app.route("/state.json")
def get_state():
    with state_lock:
        return jsonify(dict(state))


@app.route("/img/<name>")
def get_image(name):
    return send_from_directory(OUT_DIR, name, max_age=0)


if __name__ == "__main__":
    # Refuse to start if another copy already holds the port. Two instances
    # fight over the audio device and double the API request rate.
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", PORT))
    except OSError:
        print(f"listener.py is already running on port {PORT}.")
        print("Close that console window first, then run this again.")
        raise SystemExit(1)
    finally:
        probe.close()

    if BACKEND == "comfyui":
        try:
            requests.get(f"{COMFY_URL}/system_stats", timeout=5).raise_for_status()
            print(f"ComfyUI reachable at {COMFY_URL}")
            try:
                print(f"Checkpoint: {comfy_checkpoint()}")
            except Exception as exc:
                print(f"WARNING: {exc}")
        except requests.RequestException:
            print(f"WARNING: ComfyUI is not responding at {COMFY_URL}.")
            print("Start run-comfyui.bat first, or set BACKEND to 'pollinations'.")

    threading.Thread(target=worker, daemon=True).start()
    print(f"\nOverlay:  http://localhost:{PORT}")
    print(f"For OBS:  http://localhost:{PORT}/?bare=1\n")
    app.run(host="127.0.0.1", port=PORT, threaded=True)
