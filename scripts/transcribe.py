#!/usr/bin/env python3
"""Word-level transcript of every file in <project>/raw/.

    python transcribe.py <project> [--model small] [--lang id|en|auto]

Writes work/words.json  ([{w, s, e, p, src}])  and work/transcript.txt (readable, with timestamps).

Model size: "small" is the floor for Bahasa. "medium" or "large-v3" are more accurate and much slower
on a CPU; with an NVIDIA GPU, large-v3 is the right choice.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Project, clock, save  # noqa: E402


def vocab_prompt(script):
    """Names, numbers and long words from the script, so Whisper spells them the way the script does."""
    seen, out = set(), []
    for line in script.get("lines", []):
        for w in re.findall(r"[\w$%'-]+", line.get("text", "")):
            k = w.lower()
            if k not in seen and (w[:1].isupper() or any(c.isdigit() for c in w) or len(w) >= 9):
                seen.add(k)
                out.append(w)
    return ", ".join(out[:40]) or None


def load_model(name, device):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("faster-whisper is not installed. Run: python install.py")
    if device in ("auto", "cuda"):
        try:
            m = WhisperModel(name, device="cuda", compute_type="float16")
            # A GPU can be found while its CUDA libraries (cuBLAS, cuDNN) are missing; that only fails
            # on the first real encode, so try one second of silence now and fall back to the CPU.
            import numpy as np
            list(m.transcribe(np.zeros(16000, dtype=np.float32), vad_filter=False)[0])
            return m
        except Exception as e:
            if device == "cuda":
                raise
            print(f"  GPU not usable ({str(e).splitlines()[0][:90]}), using the CPU")
    return WhisperModel(name, device="cpu", compute_type="int8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--model")
    ap.add_argument("--lang")
    a = ap.parse_args()
    pr = Project(a.project)
    files = pr.raw_files()
    if not files:
        sys.exit(f"no video files in {pr.p('raw')}")
    lang = a.lang or pr.lang
    lang = None if lang == "auto" else lang
    model = load_model(a.model or pr.cfg["whisper_model"], pr.cfg["whisper_device"])
    prompt = vocab_prompt(pr.script)
    words, lines = [], []
    for rel in files:
        print(f"transcribing {rel} ...", flush=True)
        segs, info = model.transcribe(
            pr.p(rel), language=lang, word_timestamps=True, initial_prompt=prompt,
            # Off on purpose: with it on, Whisper "tidies" retakes and repeated phrases out of the
            # transcript, and the retakes are exactly what the cutter needs to see.
            condition_on_previous_text=False,
            vad_filter=True, vad_parameters={"min_silence_duration_ms": 400})
        print(f"  language: {info.language} ({info.language_probability:.0%})")
        for seg in segs:
            seg_words = [w for w in (seg.words or []) if w.word.strip()]
            for w in seg_words:
                words.append({"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3),
                              "p": round(w.probability, 2), "src": rel})
            if seg_words:
                lines.append(f"{rel}  {clock(seg_words[0].start)}  {seg.text.strip()}")
    save(pr.p("work", "words.json"), words)
    with open(pr.p("work", "transcript.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{len(words)} words -> work/words.json, work/transcript.txt")


if __name__ == "__main__":
    main()
