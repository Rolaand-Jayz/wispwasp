"""
Stands in for PyAV, which is not shipped.

faster-whisper imports av at module load, but only uses it inside
decode_audio - and we never call that, because avcore.speech reads its own
WAV files with the standard library. Shipping the full ffmpeg stack for an
import that is never exercised costs about 62 MB, so it is left out and
satisfied here instead.

Every attribute access raises. If some future version of faster-whisper
starts genuinely needing av, this fails immediately with an explanation
rather than misbehaving quietly.
"""

import sys
import types

_MESSAGE = (
    "This build of WispWasp does not include the media decoding stack "
    "(PyAV). It reads its own WAV recordings directly, so nothing should "
    "need it. If you are seeing this error, something is trying to decode "
    "a media file and the build needs PyAV added back."
)


class _AvStub(types.ModuleType):
    def __getattr__(self, name):
        # Python's import machinery and decorator helpers probe for dunder
        # and private attributes (__wrapped__, __path__, __all__) and
        # expect AttributeError when they are absent. Raising the loud
        # error for those would fire during import, before anything has
        # actually tried to decode audio.
        if name.startswith("_"):
            raise AttributeError(name)
        raise RuntimeError(f"{_MESSAGE} (tried to use av.{name})")


for _name in ("av", "av.audio", "av.error", "av.audio.resampler",
              "av.audio.fifo"):
    if _name not in sys.modules:
        sys.modules[_name] = _AvStub(_name)
