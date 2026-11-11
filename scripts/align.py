#!/usr/bin/env python3
"""Match the raw transcript to the script and choose the take for every line.

    python align.py <project>

Reads script.json, work/words.json and (optional) choices.json. Writes work/edl.json and prints a
report: every take of every line, which one was used, lines that are missing, and anything said
that is not in the script (ad-libs), which is left out unless you keep it.

Rules, in order:
  - A take is a run of speech that matches a script line. A restart inside one breath
    ("most freelancers write - most freelancers write the price...") resolves to the restart.
  - The LAST complete take wins (complete = 85% of the line's words, style cut.complete).
    No complete take -> the best partial one, flagged.
  - Pure filler words (um, eh, emm...) inside a take are cut out. Gaps longer than cut.max_gap
    are tightened. Cut points are moved into real silence using the audio, not Whisper's
    timestamps alone, so word endings do not get clipped.

choices.json, written while reviewing a preview:
  {"take": {"3": 1}, "drop_lines": [5], "keep_unmatched": ["u2"]}
"""
import os
import sys
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Project, clock, envelope, is_filler, load, save, speech_end, speech_start, tokens  # noqa: E402


def flatten(words):
    """Token stream over all words, with a sentinel between source files so no take crosses one."""
    T, TW = [], []
    last_src = None
    for wi, w in enumerate(words):
        if last_src is not None and w["src"] != last_src:
            T.append("\x00")
            TW.append(-1)
        last_src = w["src"]
        for t in tokens(w["w"]):
            T.append(t)
            TW.append(wi)
    return T, TW


def blocks_for(line_toks, window):
    bl = [b for b in SequenceMatcher(None, line_toks, window, autojunk=False).get_matching_blocks() if b.size]
    # Drop stray single-word matches hanging off either end ("yang" from the next sentence).
    while len(bl) > 1 and bl[-1].size == 1 and bl[-1].b - (bl[-2].b + bl[-2].size) > 1:
        bl.pop()
    while len(bl) > 1 and bl[0].size == 1 and bl[1].b - (bl[0].b + bl[0].size) > 1:
        bl.pop(0)
    return bl


def find_takes(line_toks, T):
    n = len(line_toks)
    if n == 0:
        return []
    head = line_toks[:2]
    span = int(n * 1.4) + 4
    found = {}
    for p, tok in enumerate(T):
        if tok not in head:
            continue
        window = T[p:p + span]
        if "\x00" in window:
            window = window[:window.index("\x00")]
        bl = blocks_for(line_toks, window)
        if not bl or bl[0].a > 1:          # a take starts at the start of the line
            continue
        matched = sum(b.size for b in bl)
        cov = matched / n
        if cov < 0.34 or (n >= 3 and matched < 2):
            continue
        t0, t1 = p + bl[0].b, p + bl[-1].b + bl[-1].size - 1
        key = (t0, t1)
        if key not in found or found[key] < cov:
            found[key] = cov
    # Overlapping candidates are one attempt seen from two start points: keep the best, later on ties.
    takes = []
    for (t0, t1), cov in sorted(found.items()):
        if takes and t0 <= takes[-1]["t1"]:
            if cov > takes[-1]["cov"] or (cov == takes[-1]["cov"] and t0 > takes[-1]["t0"]):
                takes[-1] = {"t0": t0, "t1": t1, "cov": cov}
            continue
        takes.append({"t0": t0, "t1": t1, "cov": cov})
    return takes


def neighbours(words, i, j):
    """Hard limits for cut points: the previous and next word in the same file."""
    lo = words[i - 1]["e"] if i > 0 and words[i - 1]["src"] == words[i]["src"] else 0.0
    hi = words[j + 1]["s"] if j + 1 < len(words) and words[j + 1]["src"] == words[j]["src"] else 1e9
    return lo, hi


def segments_for(words, w0, w1, line_toks, cut, envs, line_id):
    keep_fill = set(line_toks)
    kept = [i for i in range(w0, w1 + 1)
            if not (cut["cut_fillers"] and is_filler(words[i]["w"]) and not set(tokens(words[i]["w"])) & keep_fill)]
    runs, cur = [], []
    for i in kept:
        if cur and (i != cur[-1] + 1 or words[i]["s"] - words[cur[-1]]["e"] > cut["max_gap"]):
            runs.append(cur)
            cur = []
        cur.append(i)
    if cur:
        runs.append(cur)
    segs = []
    for r in runs:
        i, j = r[0], r[-1]
        src = words[i]["src"]
        lo, hi = neighbours(words, i, j)
        s, e = words[i]["s"], words[j]["e"]
        env = envs.get(src)
        start = speech_start(env, s, lo)
        end = speech_end(env, e, hi)
        start = max(lo, s - cut["pre_pad"]) if start is None else max(lo, start)
        end = min(hi, e + cut["post_pad"]) if end is None else min(hi, end)
        if end - start > 0.05:
            segs.append({"src": src, "start": round(start, 3), "end": round(end, 3), "line": line_id,
                         "w0": i, "w1": j})
    return segs


def say(words, i, j):
    return " ".join(w["w"] for w in words[i:j + 1])


def main():
    pr = Project(sys.argv[1] if len(sys.argv) > 1 else ".")
    words_path = pr.p("work", "words.json")
    if not os.path.exists(words_path):
        sys.exit("no work/words.json - run transcribe.py first")
    words = load(words_path)
    cut = pr.style["cut"]
    ch = pr.choices()
    take_over = {str(k): int(v) for k, v in ch.get("take", {}).items()}
    drop = {str(x) for x in ch.get("drop_lines", [])}
    keep_un = set(ch.get("keep_unmatched", []))
    T, TW = flatten(words)
    envs = {src: envelope(pr.p(src)) for src in sorted({w["src"] for w in words})}
    if not any(envs.values()):
        print("note: numpy or audio unavailable - cut points use Whisper timestamps only")

    used = set()
    report, chosen = [], []
    for line in pr.script["lines"]:
        lid = str(line["id"])
        lt = tokens(line.get("text", ""))
        if not lt:
            continue
        takes = find_takes(lt, T)
        for k, tk in enumerate(takes):
            tk["n"] = k + 1
            tk["w0"], tk["w1"] = TW[tk["t0"]], TW[tk["t1"]]
            used.update(range(tk["w0"], tk["w1"] + 1))
        pick, why = None, ""
        if lid in drop:
            why = "dropped (choices.json)"
        elif lid in take_over:
            pick = next((t for t in takes if t["n"] == take_over[lid]), None)
            why = f"take {take_over[lid]} (choices.json)" if pick else f"take {take_over[lid]} does not exist"
        elif takes:
            complete = [t for t in takes if t["cov"] >= cut["complete"]]
            best = max(takes, key=lambda t: t["cov"])
            if complete:
                pick, why = complete[-1], "last complete take"
            elif best["cov"] >= 0.5:
                pick, why = best, "NO COMPLETE TAKE - best partial used"
            else:
                why = "MISSING - only fragments found"
        else:
            why = "MISSING - not found in the footage"
        entry = {"line": line["id"], "role": line.get("role", ""), "text": line["text"], "why": why,
                 "takes": [{"n": t["n"], "cov": round(t["cov"], 2), "src": words[t["w0"]]["src"],
                            "at": words[t["w0"]]["s"], "said": say(words, t["w0"], t["w1"])} for t in takes],
                 "used": pick["n"] if pick else None}
        report.append(entry)
        if pick:
            chosen.append((line["id"], segments_for(words, pick["w0"], pick["w1"], lt, cut, envs, line["id"])))

    # Speech that matched no line: ad-libs, false starts too short to match, chatter between takes.
    unmatched, cur = [], []
    for i, w in enumerate(words):
        if i in used or is_filler(w["w"]):
            if cur:
                unmatched.append(cur)
                cur = []
            continue
        if cur and (w["src"] != words[cur[-1]]["src"] or w["s"] - words[cur[-1]]["e"] > cut["pause_split"]):
            unmatched.append(cur)
            cur = []
        cur.append(i)
    if cur:
        unmatched.append(cur)
    un = [{"id": f"u{k + 1}", "src": words[g[0]]["src"], "at": words[g[0]]["s"], "w0": g[0], "w1": g[-1],
           "said": say(words, g[0], g[-1])} for k, g in enumerate(unmatched)]
    for u in un:                     # name the false starts, so they are not mistaken for ad-libs
        ut = tokens(u["said"])
        for line in pr.script["lines"]:
            lt = tokens(line.get("text", ""))
            bl = blocks_for(lt, ut) if lt and ut else []
            if bl and bl[0].a == 0 and bl[0].b == 0 and sum(b.size for b in bl) >= min(2, len(ut)) \
                    and sum(b.size for b in bl) / len(ut) >= 0.6:
                u["note"] = f"false start of line {line['id']}"
                break

    # Assemble in script order. Kept ad-libs go after whichever chosen segment precedes them in the footage.
    segs = [s for _, ss in chosen for s in ss]
    src_order = {src: k for k, src in enumerate(sorted({w["src"] for w in words}))}
    for u in un:
        if u["id"] not in keep_un:
            continue
        extra = segments_for(words, u["w0"], u["w1"], [], cut, envs, u["id"])
        before = [k for k, s in enumerate(segs)
                  if (src_order[s["src"]], s["end"]) <= (src_order[u["src"]], u["at"])]
        pos = (max(before, key=lambda k: (src_order[segs[k]["src"]], segs[k]["end"])) + 1) if before else 0
        segs[pos:pos] = extra

    total = sum(s["end"] - s["start"] for s in segs)
    save(pr.p("work", "edl.json"), {"segments": segs, "lines": report, "unmatched": un,
                                    "duration": round(total, 2)})

    print(f"\nEDIT LIST  ·  {len(segs)} segments  ·  {total:.1f}s\n")
    for r in report:
        print(f"  line {r['line']} [{r['role']}]  {r['why']}")
        print(f"         script: {r['text'][:70]}")
        for t in r["takes"]:
            mark = "->" if t["n"] == r["used"] else "  "
            print(f"      {mark} take {t['n']}  {clock(t['at'])}  {t['cov']:.0%}  \"{t['said'][:60]}\"")
    if un:
        print("\n  NOT IN THE SCRIPT (left out unless added to keep_unmatched in choices.json)")
        for u in un:
            flag = " [KEPT]" if u["id"] in keep_un else ""
            note = f"  ({u['note']})" if u.get("note") else ""
            print(f"    {u['id']}  {u['src']} {clock(u['at'])}  \"{u['said'][:70]}\"{note}{flag}")
    print("\n-> work/edl.json")


if __name__ == "__main__":
    main()
