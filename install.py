#!/usr/bin/env python3
"""One-time setup on your own computer (Windows, Mac or Linux).

    python install.py

1. checks ffmpeg and git are installed
2. creates .venv/ and installs faster-whisper, numpy, opencv, pillow, mediapipe
3. clones claude-video-effects into vendor/ at a pinned commit (updates never arrive silently)
4. with --music: also creates .venv-music/ with MusicGen (torch CPU + transformers, about 1 GB) for
   background music made on your computer (scripts/music_bed.py)
5. with --global: also copies the /reel skill into ~/.claude/skills/reel/ so it works from any folder.
   Without it, /reel works whenever Claude Code is opened in this folder
   (the skill ships in .claude/skills/reel/SKILL.md).

Safe to run again.
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
EFFECTS_REPO = "https://github.com/Vibha-Ramprakash/claude-video-effects"
EFFECTS_COMMIT = "93140a9"     # reviewed 9 Nov 2026. Change only after reading what changed.
PACKAGES = ["faster-whisper", "numpy", "opencv-python", "pillow", "mediapipe"]
WIN = os.name == "nt"


def step(msg):
    print(f"\n== {msg}", flush=True)


def run(cmd, **kw):
    r = subprocess.run(cmd, **kw)
    if r.returncode:
        sys.exit(f"failed: {' '.join(cmd)}")


def main():
    if sys.version_info < (3, 10):
        sys.exit("Python 3.10 or newer is needed (python.org/downloads)")
    step("checking tools")
    for tool, hint in (("ffmpeg", "Windows: winget install ffmpeg   Mac: brew install ffmpeg"),
                       ("ffprobe", "comes with ffmpeg"),
                       ("git", "Windows: winget install Git.Git   Mac: xcode-select --install")):
        if not shutil.which(tool):
            sys.exit(f"{tool} is missing. {hint}. Then open a NEW terminal and run this again.")
        print(f"  {tool} ok")

    step("python environment (.venv)")
    venv = os.path.join(ROOT, ".venv")
    py = os.path.join(venv, "Scripts", "python.exe") if WIN else os.path.join(venv, "bin", "python")
    if not os.path.exists(py):
        run([sys.executable, "-m", "venv", venv])
    run([py, "-m", "pip", "install", "-q", "--upgrade", "pip"])
    run([py, "-m", "pip", "install", "-q"] + PACKAGES)
    with open(os.path.join(ROOT, "requirements.lock.txt"), "w") as f:
        f.write(subprocess.run([py, "-m", "pip", "freeze"], capture_output=True, text=True).stdout)
    print("  packages ok (exact versions saved to requirements.lock.txt)")

    step(f"effects renderer, pinned to {EFFECTS_COMMIT}")
    dst = os.path.join(ROOT, "vendor", "claude-video-effects")
    if not os.path.isdir(os.path.join(dst, ".git")):
        run(["git", "clone", "-q", EFFECTS_REPO, dst])
    run(["git", "-C", dst, "fetch", "-q", "origin"])
    run(["git", "-C", dst, "checkout", "-q", EFFECTS_COMMIT])
    # fx.py executes a file called fx_private.py if one sits next to it. Nothing should.
    priv = os.path.join(dst, "scripts", "fx_private.py")
    if os.path.exists(priv):
        os.remove(priv)
        print("  removed an unexpected scripts/fx_private.py")
    print("  ok")

    if "--music" in sys.argv:
        step("music environment (.venv-music, MusicGen on CPU, about 1 GB)")
        mvenv = os.path.join(ROOT, ".venv-music")
        mpy = os.path.join(mvenv, "Scripts", "python.exe") if WIN else os.path.join(mvenv, "bin", "python")
        if not os.path.exists(mpy):
            run([sys.executable, "-m", "venv", mvenv])
        run([mpy, "-m", "pip", "install", "-q", "--upgrade", "pip"])
        run([mpy, "-m", "pip", "install", "-q", "torch", "--index-url", "https://download.pytorch.org/whl/cpu"])
        run([mpy, "-m", "pip", "install", "-q", "transformers<5", "soundfile", "numpy", "scipy"])
        print(f"  ok. Run music with: {mpy} scripts/music_bed.py <out.wav> --prompt \"...\"")

    if "--global" in sys.argv:
        step("installing /reel for every folder (--global)")
        skill_dir = os.path.join(os.path.expanduser("~"), ".claude", "skills", "reel")
        os.makedirs(skill_dir, exist_ok=True)
        with open(os.path.join(ROOT, ".claude", "skills", "reel", "SKILL.md"), encoding="utf-8") as f:
            text = f.read()
        end = text.index("\n---", 3) + 4                     # after the frontmatter
        pin = (f"\n\n> Installed globally. Pipeline folder: `{ROOT.replace(chr(92), '/')}`. "
               f"PY: `{py.replace(chr(92), '/')}`. These replace the relative paths below; "
               f"cd to the pipeline folder before running anything.")
        with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(text[:end] + pin + text[end:])
        print(f"  {skill_dir}")
        print("  re-run install.py --global after updating, or this copy goes stale")

    print("\nREADY. Open this folder in Claude Code and type /reel with your video idea.")
    print("The first transcription downloads the Whisper model once (a few hundred MB for small, about 3 GB for large-v3).")


if __name__ == "__main__":
    main()
