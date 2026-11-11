#!/usr/bin/env python3
"""Captions, on-screen text, loudness, music, export.

    python finish.py <project>                    # preview/preview_vN.mp4 (540x960, fast)
    python finish.py <project> --final            # final/final.mp4 (1080x1920) + final/cover.jpg
    python finish.py <project> --check 1.5,7.2    # PNG frames from the latest render -> work/check/

Input is work/fx.mp4 when the effects render is current, otherwise work/cut.mp4.
Music: set "music": {"file": "C:/music/track.mp3", "db": -22} in script.json. It loops, sits at
audio.music_db, and ducks under your voice. Trending Instagram audio cannot be added here: that
is licensed inside the app, so add it there when you post.
"""
import argparse
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captions  # noqa: E402
from common import Project, ffmpeg  # noqa: E402


def latest(pr):
    cands = glob.glob(pr.p("preview", "preview_v*.mp4")) + glob.glob(pr.p("final", "final.mp4"))
    return max(cands, key=os.path.getmtime) if cands else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--check")
    ap.add_argument("--input")
    a = ap.parse_args()
    pr = Project(a.project)

    if a.check:
        src = latest(pr)
        if not src:
            sys.exit("nothing rendered yet")
        os.makedirs(pr.p("work", "check"), exist_ok=True)
        for t in a.check.split(","):
            out = pr.p("work", "check", f"out_{float(t):06.2f}.png")
            ffmpeg(["-ss", t, "-i", src, "-frames:v", "1", out])
            print(out)
        return

    cut, fx = pr.p("work", "cut.mp4"), pr.p("work", "fx.mp4")
    src = a.input or (fx if os.path.exists(fx) and os.path.getmtime(fx) >= os.path.getmtime(cut) else cut)
    if not os.path.exists(src):
        sys.exit("no work/cut.mp4 - run cut.py first")
    captions.build(pr)

    ex, au = pr.style["export"], pr.style["audio"]
    vf = "ass=captions.ass:fontsdir=fonts"       # relative, run from work/: avoids Windows path escaping
    if not a.final:
        w = ex["preview_width"]
        vf += f",scale={w}:{w * 16 // 9}"
    music = pr.script.get("music") or None
    inputs = ["-i", src]
    voice = "[0:a]aresample=48000,aformat=channel_layouts=stereo"
    norm = f"loudnorm=I={au['lufs']}:TP=-1.5:LRA=11,aresample=48000"
    if music and music.get("file"):
        if not os.path.exists(music["file"]):
            sys.exit(f"music file not found: {music['file']}")
        inputs += ["-stream_loop", "-1", "-i", music["file"]]
        db = music.get("db", au["music_db"])
        m = f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={db}dB"
        if au.get("duck", True):
            af = (f"{voice},asplit=2[vo][sc];{m}[m];[m][sc]sidechaincompress=threshold=0.03:ratio=10:"
                  f"attack=15:release=350[md];[vo][md]amix=inputs=2:duration=first:normalize=0,{norm}[a]")
        else:
            af = f"{voice}[vo];{m}[m];[vo][m]amix=inputs=2:duration=first:normalize=0,{norm}[a]"
    else:
        af = f"{voice},{norm}[a]"

    if a.final:
        os.makedirs(pr.p("final"), exist_ok=True)
        out = pr.p("final", "final.mp4")
        venc = ["-c:v", "libx264", "-preset", "medium", "-crf", str(ex["crf_final"])]
    else:
        os.makedirs(pr.p("preview"), exist_ok=True)
        nums = [int(m.group(1)) for f in glob.glob(pr.p("preview", "preview_v*.mp4"))
                if (m := re.search(r"preview_v(\d+)\.mp4$", f))]
        out = pr.p("preview", f"preview_v{max(nums, default=0) + 1}.mp4")
        venc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(ex["crf_preview"])]
    ffmpeg(inputs + ["-filter_complex", f"[0:v]{vf}[v];{af}", "-map", "[v]", "-map", "[a]"] + venc +
           ["-pix_fmt", "yuv420p", "-r", str(pr.cfg["fps"]), "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", out], cwd=pr.p("work"))
    if a.final:
        ffmpeg(["-ss", str(ex["cover_at"]), "-i", out, "-frames:v", "1", "-q:v", "2", pr.p("final", "cover.jpg")])
    print(f"-> {out}")


if __name__ == "__main__":
    main()
