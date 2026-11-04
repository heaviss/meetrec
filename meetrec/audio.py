import array
import struct
import wave
from pathlib import Path

RATE = 16000
SAMPLE_BYTES = 2
FULL_SCALE = 32768
FORMAT = (RATE, 1, SAMPLE_BYTES)
WAV_HEADER = 44
RIFF_SIZE_OFFSET = 4
RIFF_SIZE_EXCLUDES = 8
DATA_TAG_OFFSET = 36
DATA_SIZE_OFFSET = 40
UINT32 = "<I"


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


def recorded_s(path: Path) -> float:
    return (path.stat().st_size - WAV_HEADER) / SAMPLE_BYTES / RATE


def repair_wav(path: Path) -> bool:
    """Fix RIFF and data sizes that pw-record leaves at zero when killed."""
    size = path.stat().st_size
    if size <= WAV_HEADER:
        return False
    with open(path, "r+b") as wav_file:
        wav_file.seek(DATA_TAG_OFFSET)
        if wav_file.read(4) != b"data":
            return False
        if struct.unpack(UINT32, wav_file.read(4))[0] == size - WAV_HEADER:
            return False
        wav_file.seek(RIFF_SIZE_OFFSET)
        wav_file.write(struct.pack(UINT32, size - RIFF_SIZE_EXCLUDES))
        wav_file.seek(DATA_SIZE_OFFSET)
        wav_file.write(struct.pack(UINT32, size - WAV_HEADER))
    return True
