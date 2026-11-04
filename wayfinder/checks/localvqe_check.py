"""Throwaway check: does LocalVQE damage clean headphone speech?

uv run --with transcribe-cpp==0.4.1 python -I localvqe_check.py <dir with me.wav, them.wav>
"""
import array, ctypes, glob, math, os, sys, wave

import transcribe_cpp as tc

d = sys.argv[1]
home = os.path.expanduser("~/.cache/meetrec")


def read(name):
    with wave.open(f"{d}/{name}") as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2), name
        return array.array("h", w.readframes(w.getnframes()))


me, them = read("me.wav"), read("them.wav")
n = min(len(me), len(them))
me, them = me[:n], them[:n]

lib = ctypes.CDLL(glob.glob(f"{home}/src/LocalVQE/ggml/build/**/liblocalvqe.so", recursive=True)[0])
lib.localvqe_new.restype = ctypes.c_void_p
lib.localvqe_last_error.restype = ctypes.c_char_p
ctx = lib.localvqe_new(f"{home}/models/localvqe-v1.4-aec-200K-f32.gguf".encode())
assert ctx, "localvqe_new failed"
out = array.array("h", bytes(2 * n))
buf = lambda a: (ctypes.c_int16 * n).from_buffer(a)
rc = lib.localvqe_process_s16(ctypes.c_void_p(ctx), buf(me), buf(them), n, buf(out))
assert rc == 0, lib.localvqe_last_error(ctypes.c_void_p(ctx))
with wave.open(f"{d}/me.clean.wav", "wb") as w:
    w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000), w.writeframes(out.tobytes())

rms = lambda a: round(20 * math.log10(math.sqrt(sum(x * x for x in a) / len(a)) / 32768 + 1e-9), 1)
print(f"{n / 16000:.1f} s; RMS dBFS: me {rms(me)}, them {rms(them)}, me.clean {rms(out)}")

model = tc.Model(f"{home}/models/gigaam-v3-e2e-ctc-Q8_0.gguf", backend="cpu").session(n_threads=4)
for name, pcm in (("me", me), ("me.clean", out), ("them", them)):
    text = model.run(array.array("f", (x / 32768 for x in pcm)), language="ru").text
    print(f"\n== {name} ==\n{text}")
    open(f"{d}/{name}.txt", "w").write(text + "\n")
