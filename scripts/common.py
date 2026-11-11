"""Shared helpers for the video pipeline. Standard library only, plus numpy where noted."""
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".mkv", ".webm")
AUDIO_EXT = (".m4a", ".wav", ".mp3", ".aac", ".ogg", ".opus")   # voice-only takes (motion-graphic reels)


# ---------- files ----------
def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)


def deep_merge(base, over):
    out = dict(base)
    for k, v in over.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def config():
    c = {"effects_dir": os.path.join(ROOT, "vendor", "claude-video-effects"),
         "whisper_model": "small", "whisper_device": "auto",
         "width": 1080, "height": 1920, "fps": 30}
    p = os.path.join(ROOT, "config.json")
    if os.path.exists(p):
        c.update(load(p))
    return c


def style(name):
    s = load(os.path.join(ROOT, "styles", "default.json"))
    if name and name != "default":
        p = os.path.join(ROOT, "styles", name + ".json")
        if not os.path.exists(p):
            sys.exit(f"style '{name}' not found at {p}")
        s = deep_merge(s, load(p))
    return s


class Project:
    def __init__(self, path):
        self.dir = os.path.abspath(path)
        if not os.path.exists(self.p("script.json")):
            sys.exit(f"no script.json in {self.dir} - is this a project folder?")
        self.script = load(self.p("script.json"))
        self.lang = self.script.get("lang", "id")
        self.style = style(self.script.get("style", "default"))
        self.cfg = config()
        os.makedirs(self.p("work"), exist_ok=True)

    def p(self, *parts):
        return os.path.join(self.dir, *parts)

    def raw_files(self):
        d = self.p("raw")
        if not os.path.isdir(d):
            return []
        return sorted(os.path.join("raw", f) for f in os.listdir(d) if f.lower().endswith(VIDEO_EXT + AUDIO_EXT))

    def choices(self):
        p = self.p("choices.json")
        return load(p) if os.path.exists(p) else {}


# ---------- tools ----------
def need(tool):
    if not shutil.which(tool):
        sys.exit(f"{tool} not found. Install ffmpeg (Windows: winget install ffmpeg, "
                 f"Mac: brew install ffmpeg), then open a new terminal.")


def ffmpeg(args, cwd=None):
    need("ffmpeg")
    cmd = ["ffmpeg", "-hide_banner", "-v", "error", "-y"] + args
    r = subprocess.run(cmd, cwd=cwd)
    if r.returncode != 0:
        sys.exit("ffmpeg failed:\n  " + " ".join(cmd))


def duration(path):
    need("ffprobe")
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
                       capture_output=True, text=True)
    try:
        return float(json.loads(r.stdout)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError):
        sys.exit(f"could not read the duration of {path}")


def clock(t):
    t = max(0.0, t)
    return f"{int(t // 60)}:{t % 60:04.1f}"


# ---------- text ----------
# Spelling variants Whisper and people swap freely. Both sides of the match go through this.
SYN = {"nggak": "gak", "enggak": "gak", "ngga": "gak", "engga": "gak", "ga": "gak", "gk": "gak", "nggk": "gak",
       "saja": "aja", "sudah": "udah", "kalo": "kalau", "yg": "yang", "dgn": "dengan", "tdk": "tidak",
       "bgt": "banget", "gimana": "bagaimana", "gonna": "going", "wanna": "want", "ok": "oke", "okay": "oke"}
FILLER_RE = re.compile(r"^(u+m+|u+h+|u+h+m+|e+r+m*|a+h+|a+|e+|e+h+|e+h*m+|h+m+|m+|anu)$")


def tokens(text):
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\s]", " ", t).replace("_", " ")
    return [SYN.get(w, w) for w in t.split()]


def is_filler(word_text):
    toks = tokens(word_text)
    return bool(toks) and all(FILLER_RE.match(t) for t in toks)


# ---------- audio ----------
def envelope(path, hop=0.01):
    """RMS per `hop` seconds of the file's audio, or None if numpy or audio is unavailable."""
    try:
        import numpy as np
    except ImportError:
        return None
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                       capture_output=True)
    if r.returncode or not r.stdout:
        return None
    a = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    n = int(16000 * hop)
    k = len(a) // n
    if k < 10:
        return None
    rms = np.sqrt((a[:k * n].reshape(k, n) ** 2).mean(axis=1) + 1e-12)
    lo, hi = float(np.percentile(rms, 10)), float(np.percentile(rms, 90))
    return {"rms": rms, "hop": hop, "thr": lo + 0.15 * (hi - lo)}


def speech_end(env, e, limit):
    """First quiet moment after a word's reported end (Whisper ends tend to be early)."""
    if not env:
        return None
    rms, hop, thr = env["rms"], env["hop"], env["thr"]
    i = max(0, int((e - 0.05) / hop))
    stop = min(len(rms) - 2, int(min(limit, e + 0.35) / hop))
    while i < stop:
        if rms[i] < thr and rms[i + 1] < thr:
            return i * hop + 0.04
        i += 1
    return None


def speech_start(env, s, limit):
    """Last quiet moment before a word's reported start."""
    if not env:
        return None
    rms, hop, thr = env["rms"], env["hop"], env["thr"]
    i = min(len(rms) - 1, int((s + 0.05) / hop))
    stop = max(1, int(max(limit, s - 0.3) / hop))
    while i > stop:
        if rms[i] < thr and rms[i - 1] < thr:
            return max(0.0, i * hop - 0.03)
        i -= 1
    return None
