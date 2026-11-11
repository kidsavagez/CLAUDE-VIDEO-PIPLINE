#!/usr/bin/env python3
"""Voice-only reels: cut the clean voice track from work/edl.json (after align.py), without any video.
Every segment end is pushed out to where the audio really goes quiet (Whisper ends words early),
the pieces are joined with tiny fades and levelled to -16 LUFS.

    python cut_voice.py <project> [out.wav]

Writes work/voice.wav (or out.wav) and work/prog_words.json: every kept word with its time in the
cut voice track, for building captions or motion graphics on top of it.
Use the voice track in your own edit (CapCut, Premiere) or ask Claude to build motion graphics on it.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Project, load, save  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pr = Project(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else pr.p("work", "voice.wav")
    e = load(pr.p("work", "edl.json"))
    words = load(pr.p("work", "words.json"))
    srcs = {s["src"].replace("\\", "/") for s in e["segments"]}
    if len(srcs) != 1:
        sys.exit("cut_voice.py handles one raw recording; join the files first or record in one take")
    src = pr.p(srcs.pop())

    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", src, "-af", "silencedetect=noise=-40dB:d=0.12", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    sil = list(zip([float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)],
                   [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]))

    segs = []
    for i, s in enumerate(e["segments"]):
        a, b = s["start"], s["end"]
        nxt = e["segments"][i + 1]["start"] if i + 1 < len(e["segments"]) and e["segments"][i + 1]["start"] > b else 1e9
        cand = [ss for ss, _ in sil if ss >= b - 0.02 and ss - b < 0.7 and ss < nxt]
        if cand:
            b = cand[0] + 0.06
        segs.append({"start": round(a, 3), "end": round(b, 3), "line": s.get("line")})

    parts = []
    for i, s in enumerate(segs):
        d = s["end"] - s["start"]
        parts.append(f"[0:a]atrim={s['start']:.3f}:{s['end']:.3f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d=0.012,afade=t=out:st={d - 0.015:.3f}:d=0.015[a{i}]")
    fc = ";".join(parts) + ";" + "".join(f"[a{i}]" for i in range(len(segs))) + \
        f"concat=n={len(segs)}:v=0:a=1,aresample=48000,pan=stereo|c0=0.5*c0+0.5*c1|c1=0.5*c0+0.5*c1," \
        "loudnorm=I=-16:TP=-1.5:LRA=11[o]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex", fc, "-map", "[o]", "-ar", "48000", out],
                   check=True)

    prog, t, used = [], 0.0, set()
    for s in segs:
        for i, w in enumerate(words):
            if i not in used and s["start"] - 0.08 <= w["s"] < s["end"] - 0.05:
                used.add(i)
                prog.append({"w": w["w"], "s": round(max(w["s"], s["start"]) - s["start"] + t, 3),
                             "e": round(min(w["e"], s["end"]) - s["start"] + t, 3), "line": s["line"]})
        t += s["end"] - s["start"]
    save(pr.p("work", "prog_words.json"), {"duration": round(t, 3), "segments": segs, "words": prog})
    print(f"voice {t:.2f}s, {len(prog)} words -> {out}, work/prog_words.json")


if __name__ == "__main__":
    main()
