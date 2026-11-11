#!/usr/bin/env python3
"""Check the pipeline works on this computer, without a camera, Whisper or the effects renderer.

    python scripts/selftest.py

Builds a fake 26-second recording (test pattern + tone "speech") with a false start, a mid-line
restart, an "emm" and an ad-lib, then runs align -> cut -> effects plan -> preview -> final and
checks every decision. Leaves the result in projects/_selftest/ so you can watch it.
"""
import math
import os
import random
import shutil
import struct
import subprocess
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import ROOT, envelope, ffmpeg, load, save  # noqa: E402

P = os.path.join(ROOT, "projects", "_selftest")
SCRIPT = {"title": "selftest", "lang": "id", "style": "default", "music": None, "lines": [
    {"id": 1, "role": "hook", "text": "Kamu kehilangan klien karena satu kalimat ini.", "onscreen": "1 kalimat ini",
     "effects": [{"fx": "lean-in", "on": "kalimat"}]},
    {"id": 2, "role": "body", "text": "Kebanyakan freelancer menulis harga di awal pesan.",
     "effects": [{"fx": "backdrop-word", "on": "harga", "text": "HARGA"}]},
    {"id": 3, "role": "body", "text": "Coba ganti dengan pertanyaan tentang hasil yang mereka mau.", "effects": []},
    {"id": 4, "role": "cta", "text": "Komen KALIMAT dan aku kirim templatenya.", "effects": []}]}
SPOKEN = [("Kamu kehilangan klien eh", 1.0), ("Kamu kehilangan klien karena satu kalimat ini.", 1.2),
          ("Kebanyakan freelancer nulis", 0.1), ("kebanyakan freelancer menulis harga emm di awal pesan.", 1.0),
          ("oke terus", 1.0), ("Coba ganti dengan pertanyaan", 0.8), ("tentang hasil yang mereka mau.", 1.0),
          ("Komen kalimat dan aku kirim templatenya.", 1.0)]


def step(*args):
    r = subprocess.run([sys.executable, os.path.join(HERE, args[0]), P] + list(args[1:]),
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"FAIL {args[0]}:\n{r.stdout}\n{r.stderr}")
    return r.stdout


def main():
    shutil.rmtree(P, ignore_errors=True)
    for d in ("raw", "work", "preview", "final"):
        os.makedirs(os.path.join(P, d))
    save(os.path.join(P, "script.json"), SCRIPT)
    t, words = 0.5, []
    for text, pause in SPOKEN:
        for w in text.split():
            d = 0.18 + 0.035 * len(w)
            # Whisper's word ends run early; the fake audio runs 80 ms past them on purpose.
            words.append({"w": w, "s": round(t, 3), "e": round(t + d - 0.08, 3), "p": 0.9, "src": "raw/take.mp4"})
            t += d + 0.07
        t += pause
    dur = t + 0.5
    save(os.path.join(P, "work", "words.json"), words)
    sr = 48000
    random.seed(1)
    spans, buf, j = [(w["s"], w["e"] + 0.08) for w in words], bytearray(), 0
    for i in range(int(dur * sr)):
        x = i / sr
        a = 0.002 * random.uniform(-1, 1)
        while j < len(spans) and spans[j][1] < x:
            j += 1
        if j < len(spans) and spans[j][0] <= x <= spans[j][1]:
            a += 0.4 * math.sin(2 * math.pi * (180 + 40 * (j % 5)) * x)
        buf += struct.pack("<h", int(max(-1, min(1, a)) * 32767))
    wav = os.path.join(P, "raw", "take.wav")
    with wave.open(wav, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr); wf.writeframes(bytes(buf))
    ffmpeg(["-f", "lavfi", "-i", f"testsrc2=size=1080x1920:rate=30:duration={dur:.2f}", "-i", wav,
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", os.path.join(P, "raw", "take.mp4")])
    os.remove(wav)

    print(step("align.py"))
    edl = load(os.path.join(P, "work", "edl.json"))
    said = {r["line"]: next(t["said"] for t in r["takes"] if t["n"] == r["used"]) for r in edl["lines"]}
    checks = [
        ("line 1 uses the complete take, not the false start", said[1].endswith("kalimat ini.")),
        ("line 2 uses the restart", said[2].startswith("kebanyakan freelancer menulis")),
        ("'emm' is cut out of line 2", sum(1 for s in edl["segments"] if s["line"] == 2) == 2),
        ("the ad-lib is reported, not used", any(u["said"] == "oke terus" for u in edl["unmatched"])),
        ("false starts are labelled", sum(1 for u in edl["unmatched"] if u.get("note")) == 2),
    ]
    step("cut.py")
    env = envelope(os.path.join(P, "work", "cut.mp4"))
    cmap = load(os.path.join(P, "work", "cut_map.json"))
    if env:
        loud = [b for s in cmap["segments"] for b in (s["out_start"], s["out_end"])
                if env["rms"][max(0, int(b / 0.01) - 2):int(b / 0.01) + 2].max() >= env["thr"]]
        checks.append(("every cut point lands in silence", not loud))
    checks.append(("cut length is right", abs(cmap["duration"] - edl["duration"]) < 0.2))
    step("effects.py", "plan")
    fx = load(os.path.join(P, "work", "fx_plan.json"))["effects"]
    checks.append(("effects land on their words", [f["fx"] for f in fx] == ["lean-in", "backdrop-word"]))
    step("finish.py")
    step("finish.py", "--final")
    checks.append(("preview and final rendered", os.path.exists(os.path.join(P, "preview", "preview_v1.mp4"))
                   and os.path.exists(os.path.join(P, "final", "final.mp4"))))
    bad = 0
    for name, ok in checks:
        print(("  PASS  " if ok else "  FAIL  ") + name)
        bad += not ok
    print(f"\n{len(checks) - bad}/{len(checks)} passed. Watch it: {os.path.join(P, 'final', 'final.mp4')}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
