#!/usr/bin/env python3
"""Effects stage. Turns the effect cues in script.json into timings on the cut, then drives the
claude-video-effects renderer (vendor/claude-video-effects, pinned by install.py).

    python effects.py <project> plan      # work/fx_plan.json from script.json cues
    python effects.py <project> check     # PNG check frames at the middle of every effect -> work/check/
    python effects.py <project> render    # work/fx.mp4

A cue lives on a script line:
    {"id": 4, "text": "...", "effects": [{"fx": "backdrop-word", "on": "GRATIS", "text": "GRATIS", "dur": 2.5}]}
"on" is the word (or phrase) the effect lands on; without it the effect starts with the line.
Every other key is passed to the effect as an option (text, color, zoom, images, look...).
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Project, clock, load, save, tokens  # noqa: E402

RESERVED = {"fx", "on", "dur", "start", "end", "offset"}


def cue_time(words, line_id, on):
    mine = [w for w in words if str(w["line"]) == str(line_id)]
    if not mine:
        return None, None
    if not on:
        return mine[0]["s"], mine[-1]["e"]
    want = tokens(on)
    for pool in (mine, words):                     # the line first, then anywhere
        toks = [tokens(w["w"]) for w in pool]
        for i in range(len(pool)):
            got = [t for tt in toks[i:i + len(want) + 2] for t in tt][:len(want)]
            if got == want:
                return pool[i]["s"], mine[-1]["e"]
    return None, None


def plan(pr):
    words = load(pr.p("work", "cut.words.json"))
    dur = load(pr.p("work", "cut_map.json"))["duration"]
    st = pr.style["effects"]
    out, warn = [], []
    for line in pr.script["lines"]:
        for cue in line.get("effects") or []:
            t, line_end = cue_time(words, line["id"], cue.get("on"))
            if t is None:
                warn.append(f"line {line['id']}: '{cue.get('on') or 'line start'}' not found in the cut - {cue['fx']} skipped")
                continue
            start = max(0.0, t - st["lead"] + float(cue.get("offset", 0)))
            end = min(dur, start + float(cue.get("dur", st["default_dur"])))
            fx = {"fx": cue["fx"], "start": round(start, 2), "end": round(end, 2), "line": line["id"]}
            fx.update({k: v for k, v in cue.items() if k not in RESERVED})
            out.append(fx)
    out.sort(key=lambda f: f["start"])
    for a, b in zip(out, out[1:]):
        if b["start"] - a["end"] < st["min_gap"]:
            warn.append(f"{a['fx']} at {clock(a['start'])} and {b['fx']} at {clock(b['start'])} are closer than "
                        f"{st['min_gap']}s - the style says space them out")
    save(pr.p("work", "fx_plan.json"), {"effects": out})
    print(f"\nEFFECTS PLAN  ·  {len(out)} effects on a {dur:.1f}s cut\n")
    for f in out:
        extra = {k: v for k, v in f.items() if k not in ("fx", "start", "end", "line")}
        print(f"  {clock(f['start'])}-{clock(f['end'])}  line {f['line']}  {f['fx']}  {extra if extra else ''}")
    for w in warn:
        print(f"  ! {w}")
    print("\n-> work/fx_plan.json")
    return out


def renderer(pr):
    fx = os.path.join(pr.cfg["effects_dir"], "scripts", "fx.py")
    if not os.path.exists(fx):
        sys.exit(f"effects renderer not found at {fx} - run install.py")
    return fx


def main():
    if len(sys.argv) < 3 or sys.argv[2] not in ("plan", "check", "render"):
        sys.exit(__doc__)
    pr = Project(sys.argv[1])
    step = sys.argv[2]
    if step == "plan":
        plan(pr)
        return
    plan_path = pr.p("work", "fx_plan.json")
    if not os.path.exists(plan_path):
        plan(pr)
    effects = load(plan_path)["effects"]
    fx_out = pr.p("work", "fx.mp4")
    if not effects:
        if os.path.exists(fx_out):
            os.remove(fx_out)
        print("no effects planned - the finish step will use work/cut.mp4")
        return
    # The renderer only needs fx/start/end and options; "line" is ours.
    clean = pr.p("work", "fx_plan.render.json")
    save(clean, {"effects": [{k: v for k, v in f.items() if k != "line"} for f in effects]})
    cmd = [sys.executable, renderer(pr), "--plan", clean, pr.p("work", "cut.mp4")]
    if step == "check":
        os.makedirs(pr.p("work", "check"), exist_ok=True)
        mids = ",".join(f"{(f['start'] + f['end']) / 2:.2f}" for f in effects)
        cmd += [pr.p("work", "check", "fx.png"), "--still", mids]
    else:
        cmd += [fx_out]
    r = subprocess.run(cmd)
    if r.returncode:
        sys.exit("the effects renderer failed (see above)")
    print("-> " + ("work/check/fx_*.png" if step == "check" else "work/fx.mp4"))


if __name__ == "__main__":
    main()
