import struct
import wave
from pathlib import Path

from meetrec.meeting import DATA_SIZE_OFFSET, RIFF_SIZE_OFFSET, UINT32, repair_wav

FRAMES = 16000


def test_repair_wav_restores_zeroed_sizes(tmp_path: Path) -> None:
    path = tmp_path / "me.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(FRAMES)
        wav.writeframes(b"\x01\x00" * FRAMES)
    killed = bytearray(path.read_bytes())
    struct.pack_into(UINT32, killed, RIFF_SIZE_OFFSET, 0)
    struct.pack_into(UINT32, killed, DATA_SIZE_OFFSET, 0)
    path.write_bytes(killed)

    assert repair_wav(path)
    assert not repair_wav(path)
    with wave.open(str(path)) as wav:
        assert wav.getnframes() == FRAMES
