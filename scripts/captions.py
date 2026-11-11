#!/usr/bin/env python3
"""Word-by-word captions and on-screen text, as an .ass subtitle file burned in by finish.py.

    python captions.py <project>      # writes work/captions.ass (finish.py also calls this)

Captions come from work/cut.words.json, so they are timed to the cut and need no second pass of
Whisper. On-screen text comes from each script line's "onscreen" field and shows while that line is
spoken (the hook's stays up for at least onscreen.hook_min seconds).

While an effect listed in captions.avoid_fx is on screen, captions move to captions.alt_y
(conflict "shift") or disappear (conflict "hide"), so the two do not sit on top of each other.
"""
import glob
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, Project, load  # noqa: E402


def ass_color(hexstr):
    h = hexstr.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    alpha = 255 - int(h[6:8], 16) if len(h) == 8 else 0      # CSS opacity -> ASS transparency
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ts(t):
    t = max(0.0, t)
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def esc(text):
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def groups(words, max_words, max_chars):
    out, cur = [], []
    for w in words:
        if cur:
            text = " ".join(x["w"] for x in cur + [w])
            if (len(cur) >= max_words or len(text) > max_chars or w["s"] - cur[-1]["e"] > 0.45
                    or w["line"] != cur[-1]["line"] or cur[-1]["w"][-1:] in ".?!"):
                out.append(cur)
                cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return out


def copy_fonts(pr):
    dst = pr.p("work", "fonts")
    os.makedirs(dst, exist_ok=True)
    for d in (os.path.join(pr.cfg["effects_dir"], "fonts"), os.path.join(ROOT, "fonts")):
        for f in glob.glob(os.path.join(d, "*.[ot]tf")):
            shutil.copy2(f, dst)
    return dst


def build(pr):
    W, H = pr.cfg["width"], pr.cfg["height"]
    cs, os_ = pr.style["captions"], pr.style["onscreen"]
    words = load(pr.p("work", "cut.words.json"))
    dur = load(pr.p("work", "cut_map.json"))["duration"]
    fx_path = pr.p("work", "fx_plan.json")
    effects = load(fx_path)["effects"] if os.path.exists(fx_path) else []
    avoid = [(f["start"], f["end"]) for f in effects if f["fx"] in set(cs.get("avoid_fx", []))]
    copy_fonts(pr)

    bold = -1 if cs.get("bold", True) else 0
    head = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2",
        "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{cs['font']},{cs['size']},{ass_color(cs['color'])},&H000000FF,{ass_color(cs['outline_color'])},"
        f"&H80000000,{bold},0,0,0,100,100,0,0,1,{cs['outline']},{cs['shadow']},5,60,60,0,1",
        f"Style: Onscreen,{os_['font']},{os_['size']},{ass_color(os_['color'])},&H000000FF,{ass_color(os_['box'])},"
        f"{ass_color(os_['box'])},0,0,0,0,100,100,0,0,3,16,0,5,80,80,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    ev = []

    if cs.get("enabled", True):
        hi = ass_color(cs["highlight"])[2:]
        base = ass_color(cs["color"])[2:]
        gs = groups(words, cs["max_words"], cs["max_chars"])
        for gi, g in enumerate(gs):
            g_end = g[-1]["e"] + 0.12
            if gi + 1 < len(gs) and gs[gi + 1][0]["s"] - g_end < 0.3:
                g_end = gs[gi + 1][0]["s"]          # hold until the next group: no flicker between groups
            for k, w in enumerate(g):
                a = w["s"]
                b = g[k + 1]["s"] if k + 1 < len(g) else g_end
                mid = (a + b) / 2
                clash = any(s0 <= mid <= s1 for s0, s1 in avoid)
                if clash and cs.get("conflict") == "hide":
                    continue
                y = int(H * (cs["alt_y"] if clash else cs["y"]))
                parts = []
                for j, x in enumerate(g):
                    t = esc(x["w"].upper() if cs.get("uppercase") else x["w"])
                    if j == k:
                        pop = r"\fscx112\fscy112" if cs.get("pop") else ""
                        parts.append(f"{{\\1c&H{hi}&{pop}}}{t}{{\\1c&H{base}&\\fscx100\\fscy100}}")
                    else:
                        parts.append(t)
                ev.append(f"Dialogue: 1,{ts(a)},{ts(b)},Cap,,0,0,0,,{{\\pos({W // 2},{y})}}{' '.join(parts)}")

    if os_.get("enabled", True):
        for line in pr.script["lines"]:
            text = (line.get("onscreen") or "").strip()
            mine = [w for w in words if str(w["line"]) == str(line["id"])]
            if not text or not mine:
                continue
            a, b = mine[0]["s"], mine[-1]["e"]
            if line.get("role") == "hook":
                a, b = 0.0, max(b, os_["hook_min"])
            text = text.upper() if os_.get("uppercase") else text
            ev.append(f"Dialogue: 2,{ts(a)},{ts(min(b, dur))},Onscreen,,0,0,0,,"
                      f"{{\\pos({W // 2},{int(H * os_['y'])})}}{esc(text)}")

    path = pr.p("work", "captions.ass")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(head + ev) + "\n")
    return path, len(ev)


if __name__ == "__main__":
    p, n = build(Project(sys.argv[1] if len(sys.argv) > 1 else "."))
    print(f"-> {p}  ({n} events)")
