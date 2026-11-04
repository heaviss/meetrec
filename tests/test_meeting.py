import wave

from meetrec.meeting import repair_wav


def test_repair_wav_restores_sizes_left_at_zero(tmp_path):
    path = tmp_path / "me.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x01\x00" * 16000)
    data = bytearray(path.read_bytes())
    data[4:8] = data[40:44] = b"\0\0\0\0"
    path.write_bytes(data)

    assert repair_wav(path)
    assert not repair_wav(path)
    with wave.open(str(path)) as w:
        assert w.getnframes() == 16000
