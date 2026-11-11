#!/usr/bin/env python3
"""Transcribe each burst of speech on its own (split on real silence), so a restart after a pause
can never be merged with the take that follows it. Use it instead of transcribe.py when the
recording has many restarts, or when the cut still contains repeated words.

    python burst_transcribe.py <project> [--model large-v3-turbo] [--lang id|en] [--noise -38] [--gap 0.3]

Writes work/words.json (+ a backup work/words.orig.json) and work/transcript.txt, one line per burst.
Then run align.py as usual.
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Project, save  # noqa: E402
from transcribe import load_model, vocab_prompt  # noqa: E402


def silences(wav, noise, gap):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", wav, "-af", f"silencedetect=noise={noise}dB:d={gap}",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err).groups()
    dur = int(h) * 3600 + int(m) * 60 + float(s)
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    edges = [0.0] + [x for pair in zip(st, en) for x in pair] + [dur]
    return [(edges[i], edges[i + 1]) for i in range(0, len(edges) - 1, 2) if edges[i + 1] - edges[i] > 0.12]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--model", default="large-v3-turbo")
    ap.add_argument("--lang")
    ap.add_argument("--noise", type=float, default=-38, help="silence threshold in dB")
    ap.add_argument("--gap", type=float, default=0.3, help="shortest pause that splits two bursts, seconds")
    a = ap.parse_args()
    pr = Project(a.project)
    files = pr.raw_files()
    if not files:
        sys.exit(f"no video or audio files in {pr.p('raw')}")
    lang = a.lang or pr.lang
    lang = None if lang == "auto" else lang
    model = load_model(a.model, pr.cfg["whisper_device"])
    prompt = vocab_prompt(pr.script)
    tmp = tempfile.mkdtemp()
    words, lines = [], []
    for rel in files:
        print(f"transcribing {rel} burst by burst ...", flush=True)
        wav = os.path.join(tmp, "a.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", pr.p(rel), "-map", "0:a:0", "-ac", "1", "-ar", "16000", wav],
                       check=True)
        for a0, b0 in silences(wav, a.noise, a.gap):
            lo, hi = max(0, a0 - 0.1), b0 + 0.1
            clip = os.path.join(tmp, "b.wav")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{lo:.3f}", "-to", f"{hi:.3f}", "-i", wav, clip], check=True)
            segs, _ = model.transcribe(clip, language=lang, word_timestamps=True, condition_on_previous_text=False,
                                       vad_filter=False, initial_prompt=prompt)
            ws = [w for s in segs for w in (s.words or []) if w.word.strip()]
            for w in ws:
                s_, e_ = max(a0, w.start + lo), min(b0, w.end + lo)
                words.append({"w": w.word.strip(), "s": round(s_, 3), "e": round(max(e_, s_ + 0.05), 3),
                              "p": round(w.probability, 2), "src": rel})
            lines.append(f"{rel}  {a0:7.2f}-{b0:7.2f}  " + (" ".join(w.word.strip() for w in ws) or "(no words)"))
    save(pr.p("work", "words.orig.json"), words)
    save(pr.p("work", "words.json"), words)
    with open(pr.p("work", "transcript.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"{len(words)} words -> work/words.json, work/transcript.txt")


if __name__ == "__main__":
    main()
