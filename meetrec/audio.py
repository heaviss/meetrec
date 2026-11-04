import array
import wave
from pathlib import Path

RATE = 16000
SAMPLE_BYTES = 2
FULL_SCALE = 32768
FORMAT = (RATE, 1, SAMPLE_BYTES)


def read_s16(path: Path) -> array.array[int]:
    with wave.open(str(path)) as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != FORMAT:
            raise ValueError(f"{path} is not 16 kHz mono s16")
        return array.array("h", wav.readframes(wav.getnframes()))


def write_s16(path: Path, samples: array.array[int]) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(SAMPLE_BYTES)
        wav.setframerate(RATE)
        wav.writeframes(samples.tobytes())


def as_float_pcm(samples: array.array[int]) -> array.array[float]:
    return array.array("f", (sample / FULL_SCALE for sample in samples))
