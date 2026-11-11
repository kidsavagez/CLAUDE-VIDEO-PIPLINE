#!/usr/bin/env python3
"""Trim Whisper word spans that swallowed a silence (Whisper sometimes stretches a word over the
pause before or after it, so the cut keeps dead air). Uses ffmpeg silencedetect on the raw audio.

    python snap_words.py <project>

Backs up work/words.json to work/words.orig.json once, then rewrites work/words.json.
Run it after transcribe.py and before align.py.
"""
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Project, load, save  # noqa: E402

PAD = 0.04


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pr = Project(sys.argv[1])
    wp, orig = pr.p("work", "words.json"), pr.p("work", "words.orig.json")
    if not os.path.exists(orig):
        shutil.copy2(wp, orig)
    words = load(orig)
    sil = {}
    for src in sorted({w["src"] for w in words}):
        out = subprocess.run(["ffmpeg", "-hide_banner", "-i", pr.p(src), "-map", "0:a:0",
                              "-af", "silencedetect=noise=-35dB:d=0.25", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
        st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
        en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
        sil[src] = list(zip(st, en))
    n = 0
    for w in words:
        for a, b in sil[w["src"]]:
            lo, hi = max(a, w["s"]), min(b, w["e"])
            if hi - lo < 0.25:
                continue
            if (lo - w["s"]) <= (w["e"] - hi):      # silence sits at the front of the word
                new = (round(hi - PAD, 2), w["e"])
            else:                                    # silence sits at the back
                new = (w["s"], round(lo + PAD, 2))
            if new[1] - new[0] >= 0.08:
                print(f'{w["w"]:>14}  {w["s"]:.2f}-{w["e"]:.2f}  ->  {new[0]:.2f}-{new[1]:.2f}')
                w["s"], w["e"] = new
                n += 1
    save(wp, words)
    print(f"{n} words trimmed -> work/words.json")


if __name__ == "__main__":
    main()
