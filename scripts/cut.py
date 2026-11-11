#!/usr/bin/env python3
"""Render the edit list into one vertical video.

    python cut.py <project>

Each segment is cut frame-accurately from the raw file, reframed to 1080x1920 at 30 fps, given a
tiny audio fade so joins do not click, then joined. Writes:
  work/cut.mp4         the assembled cut
  work/cut.words.json  every kept word, retimed onto the cut's timeline (no second transcription)
  work/cut_map.json    where each segment sits in the cut
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Project, ffmpeg, is_filler, load, save  # noqa: E402


def main():
    pr = Project(sys.argv[1] if len(sys.argv) > 1 else ".")
    edl = load(pr.p("work", "edl.json"))
    words = load(pr.p("work", "words.json"))
    segs = edl["segments"]
    if not segs:
        sys.exit("the edit list is empty - check the align report")
    W, H, fps = pr.cfg["width"], pr.cfg["height"], pr.cfg["fps"]
    tmp = pr.p("work", "segs")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    vf = f"fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"
    out_t, cmap, cut_words, listing = 0.0, [], [], []
    for k, s in enumerate(segs):
        # Round every segment to whole frames so the word timings below stay exact.
        d = max(1, round((s["end"] - s["start"]) * fps)) / fps
        f = 0.008
        name = f"seg_{k:03d}.mkv"
        ffmpeg(["-ss", f"{s['start']:.3f}", "-i", pr.p(s["src"]), "-t", f"{d:.4f}",
                "-vf", vf,
                "-af", f"aresample=48000,afade=t=in:d={f},afade=t=out:st={max(0, d - f):.4f}:d={f}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
                "-c:a", "pcm_s16le", "-ac", "2", "-ar", "48000", os.path.join(tmp, name)])
        listing.append(f"file '{name}'")
        for w in words:
            if w["src"] == s["src"] and w["s"] >= s["start"] - 0.05 and w["e"] <= s["end"] + 0.08 \
                    and not is_filler(w["w"]):
                ns = out_t + max(0.0, w["s"] - s["start"])
                ne = out_t + min(d, w["e"] - s["start"])
                cut_words.append({"w": w["w"], "s": round(ns, 3), "e": round(max(ns + 0.05, ne), 3),
                                  "line": s["line"]})
        cmap.append({"k": k, "line": s["line"], "src": s["src"], "src_start": s["start"],
                     "out_start": round(out_t, 3), "out_end": round(out_t + d, 3)})
        out_t += d
        print(f"  segment {k + 1}/{len(segs)}", flush=True)
    with open(os.path.join(tmp, "list.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(listing) + "\n")
    ffmpeg(["-f", "concat", "-safe", "0", "-i", "list.txt", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", os.path.join("..", "cut.mp4")], cwd=tmp)
    # Remove the per-segment files (they are large); keep the cut.
    shutil.rmtree(tmp, ignore_errors=True)
    # Any older effects render no longer matches this cut.
    stale = pr.p("work", "fx.mp4")
    if os.path.exists(stale):
        os.remove(stale)
    save(pr.p("work", "cut.words.json"), cut_words)
    save(pr.p("work", "cut_map.json"), {"duration": round(out_t, 3), "segments": cmap})
    print(f"-> work/cut.mp4  ({out_t:.1f}s, {len(segs)} segments)")


if __name__ == "__main__":
    main()
