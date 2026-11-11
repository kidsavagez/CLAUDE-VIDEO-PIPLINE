#!/usr/bin/env python3
"""Measure a reference edit so a style can be written from evidence instead of vibes.

    python style_ref.py ref1.mp4 [ref2.mp4 ...] --name my-style

For each reference, writes to styles/refs/<name>/:
  <ref>_report.json   duration, cuts, average shot length, cuts per minute, loudness
  <ref>_sheet.jpg     20 frames across the whole video (what it looks like over time)
  <ref>_cuts_N.jpg    the first frame after each detected cut (what changes at a cut)
  <ref>_hook.jpg      the first 3 seconds, 6 frames per second (how it opens)

Then Claude looks at the images, writes styles/<name>.json (only the keys that differ from
default.json) and styles/<name>.md (the taste notes: which effects, how often, what to avoid).

What this cannot see: motion between sampled frames, sound design, how transitions feel. Point at
timestamps you like ("the zoom at 0:07") and those get extracted and studied directly.
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, duration, ffmpeg, need, save  # noqa: E402


def scene_cuts(path, thr):
    need("ffmpeg")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-an", "-vf",
                        f"scale=320:-2,select='gt(scene,{thr})',showinfo", "-f", "null", "-"],
                       capture_output=True, text=True)
    return [round(float(m), 2) for m in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def loudness(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-vn", "-af", "loudnorm=print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr)
    if not m:
        return None
    d = json.loads(m.group(0))
    return {"lufs": float(d["input_i"]), "true_peak": float(d["input_tp"]), "lra": float(d["input_lra"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("refs", nargs="+")
    ap.add_argument("--name", required=True)
    ap.add_argument("--threshold", type=float, default=0.3, help="scene change sensitivity, lower = more cuts")
    ap.add_argument("--at", help="extra timestamps to grab at full size, comma separated (e.g. 7.2,12)")
    a = ap.parse_args()
    out = os.path.join(ROOT, "styles", "refs", a.name)
    os.makedirs(out, exist_ok=True)
    for ref in a.refs:
        base = os.path.splitext(os.path.basename(ref))[0]
        d = duration(ref)
        cuts = scene_cuts(ref, a.threshold)
        edges = [0.0] + cuts + [d]
        shots = [b - x for x, b in zip(edges, edges[1:]) if b - x > 0.04]
        rep = {"file": ref, "duration": round(d, 2), "cuts": cuts, "cut_count": len(cuts),
               "cuts_per_minute": round(len(cuts) / d * 60, 1) if d else 0,
               "shot_avg": round(statistics.mean(shots), 2) if shots else d,
               "shot_median": round(statistics.median(shots), 2) if shots else d,
               "shot_shortest": round(min(shots), 2) if shots else d,
               "loudness": loudness(ref)}
        save(os.path.join(out, f"{base}_report.json"), rep)
        step = max(d / 20, 0.25)
        ffmpeg(["-i", ref, "-vf", f"fps=1/{step:.3f},scale=216:-2,tile=5x4:padding=4", "-frames:v", "1",
                "-q:v", "3", os.path.join(out, f"{base}_sheet.jpg")])
        if cuts:
            ffmpeg(["-i", ref, "-vf", f"select='gt(scene,{a.threshold})',scale=216:-2,tile=5x4:padding=4",
                    "-fps_mode", "vfr", "-q:v", "3", os.path.join(out, f"{base}_cuts_%d.jpg")])
        ffmpeg(["-t", "3", "-i", ref, "-vf", "fps=6,scale=216:-2,tile=6x3:padding=4", "-frames:v", "1",
                "-q:v", "3", os.path.join(out, f"{base}_hook.jpg")])
        for t in (a.at.split(",") if a.at else []):
            ffmpeg(["-ss", t, "-i", ref, "-frames:v", "1", "-q:v", "2", os.path.join(out, f"{base}_at_{t}.jpg")])
        lu = rep["loudness"]
        print(f"\n  {base}: {d:.1f}s, {len(cuts)} cuts ({rep['cuts_per_minute']}/min), "
              f"shot avg {rep['shot_avg']}s, median {rep['shot_median']}s"
              + (f", {lu['lufs']} LUFS" if lu else ""))
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
