---
name: reel
description: >-
  Script-to-finished-Reel pipeline with two human gates. Writes the script with effect cues, then
  after the user shoots: picks the best takes, cuts dead air and filler, adds effects, captions and
  on-screen text, renders a preview, takes notes, renders the final and writes the post caption.
  Use when the user types /reel, has a video idea, drops raw footage, says "edit video ini",
  "bikin reel", gives notes on a preview, or shares a reference edit to copy the style of.
---

# reel

## Where things are, and first-time setup

- **Pipeline folder** = the `video-pipeline` folder this skill lives in (three levels above this
  file: `video-pipeline/.claude/skills/reel/SKILL.md`). Run every command from there.
  Projects live in `projects/<date>-<slug>/` inside it.
- **PY** = the pipeline's own Python. Use it for every command below, never the system one:
  `.venv/Scripts/python.exe` on Windows, `.venv/bin/python` on Mac or Linux.
- **If PY does not exist yet**, set up first, without asking the user to type anything:
  run `python install.py` (or `py install.py` on Windows, `python3 install.py` on Mac). If it
  stops with "ffmpeg is missing" or "git is missing", install that tool for them (Windows:
  `winget install ffmpeg` / `winget install Git.Git`; Mac: `brew install ffmpeg`), tell them to
  restart Claude Code if the new command is not found, then run install again.
  When install prints READY, run `PY scripts/selftest.py` and confirm `9/9 passed`.

```
STYLE (once per reference) -> 1 BRIEF -> [gate: user approves script] -> 2 SHOOT (user)
-> 3 ALIGN -> 4 CUT -> 5 EFFECTS -> 6 PREVIEW -> [gate: user notes, loop] -> 7 FINAL
```

You write, cut and render. The user shoots, approves and posts. Nothing is ever posted from here.

## 0. Style from a reference (when the user sends reference edits)

1. `PY scripts/style_ref.py <ref.mp4> [more refs] --name <style-name>`
2. Open every image it writes in `styles/refs/<style-name>/` and read the report.json numbers.
3. Write `styles/<style-name>.json` with ONLY the keys that differ from `styles/default.json`:
   caption font/size/colours/position/words per group/uppercase, on-screen text look, cut
   tightness (`cut.max_gap`: tighter for fast edits), effect spacing (`effects.min_gap`, from the
   reference's pace), loudness.
4. Write `styles/<style-name>.md`: what the edit does, in plain words. Which of the 51 effects
   match moves you saw, how often something happens on screen, how the hook opens, what it never
   does. Add the measured numbers (cuts per minute, shot length).
5. Show the user the .md and ask what you got wrong. You see sampled frames, not motion or sound:
   say so, and ask them to name timestamps they love (`--at 7.2,12` grabs those frames).

Fonts: captions can use any font in `vendor/claude-video-effects/fonts/` (Montserrat, Anton,
Archivo Black, Inter, Instrument Serif, Playfair Display, Space Mono, Permanent Marker) or any
.ttf/.otf the user drops into `fonts/`.

## 1. Brief

1. `PY scripts/new_project.py "<slug>" --lang id --style <style>` (lang: id, en or auto).
2. Read `~/.claude/youtube/voice.md` or `~/.claude/instagram/voice.md` if one exists. Write in the
   user's language and voice. Never invent a number, result or client; ask, or leave `{{angka}}`.
3. Fill `script.json`: one line per sentence they will say, roles `hook` / `body` / `cta`.
   - Hook: write 3 options, recommend one, keep it under ~3 seconds spoken.
   - `onscreen`: short text for the hook (and any line that needs a title card).
   - `effects`: cue effects ON A WORD: `{"fx": "backdrop-word", "on": "GRATIS", "text": "GRATIS"}`.
     Pick from the style's .md. At most one effect every `effects.min_gap` seconds. Not every
     line gets one. Effects that use the user's own reels (`orbit`, `phone-fan`, `place-in-grid`,
     `fan-build`, `noise`, `profile-wall`, `carousel-spin`) need `"images": "<folder>"`.
   - Charts and counters (`liquid-glass-graph`, `over-the-shoulder-zoom`) only with real numbers.
4. Write `brief.md` next to it: the hook options, the script as they will read it, a shot note per
   effect ("line 4: leave headroom above your head"), and the shooting rules from
   `templates/shooting.md`.
5. **Gate:** show the script and stop. Do not continue until the user approves it.

## 2. Shoot (user)

They put the files in `<project>/raw/`. Several files are fine; they are used in name order.

## 3. Align

1. `PY scripts/transcribe.py <project>` (first run downloads the Whisper model).
   Many restarts in the recording, or the cut still repeats words? Use
   `PY scripts/burst_transcribe.py <project>` instead: it transcribes every burst of speech on its own
   (large-v3-turbo), so a restart after a pause is never merged into the next take. If words still
   swallow pauses, run `PY scripts/snap_words.py <project>` before align.
2. `PY scripts/align.py <project>`. Read the report to the user in short form:
   lines that are MISSING or have NO COMPLETE TAKE, and any ad-lib that sounds worth keeping.
   Do not stop for them unless a line is missing; mention them with the preview.

## 4. Cut

`PY scripts/cut.py <project>`

**Voice-only reels** (the user records only their voice, the picture is all motion graphics):
`PY scripts/cut_voice.py <project>` instead -> `work/voice.wav` (clean, -16 LUFS) and
`work/prog_words.json` (every kept word with its time in the cut track). Build the visuals on that
(HyperFrames, if the user has it, or their own editor). The effects step needs a face, so skip it.

**Background music without a licence:** if `.venv-music/` exists (`python install.py --music`), make a
bed with `.venv-music/<Scripts|bin>/python scripts/music_bed.py work/bed.wav --seconds 30 --seed 1 --prompt "<mood>, no vocals"`,
listen for gaps (try another seed if uneven), and set `"music": {"file": "<abs path>/work/bed.wav", "db": -22}`.

## 5. Effects

1. `PY scripts/effects.py <project> plan`. Fix any warning by editing `script.json` cues.
2. `PY scripts/effects.py <project> check`, then LOOK at every `work/check/fx_*.png`.
   Text over the face, cut off at the edge, unreadable: fix options (`x`, `y`, shorter `text`)
   and check again.
3. `PY scripts/effects.py <project> render`. This is the slow step (every frame goes through
   face tracking). Tell the user it is running.

## 6. Preview

1. `PY scripts/finish.py <project>` -> `preview/preview_vN.mp4`.
2. `PY scripts/finish.py <project> --check <t1,t2,...>` at the middle of each effect and two
   or three other moments. LOOK at the PNGs: captions colliding with an effect, the hook text
   unreadable, anything over the face. Fix before showing.
3. **Gate:** give the user the preview path and a short edit list: takes used, what was cut,
   effects and where. Ask for notes.

### Turning notes into changes

| note | change | re-run from |
|---|---|---|
| "use the other take of line 3" | `choices.json` `{"take": {"3": 1}}` | align |
| "keep what I said at 0:14" | `choices.json` `{"keep_unmatched": ["u3"]}` | align |
| "drop line 5" | `choices.json` `{"drop_lines": [5]}` | align |
| "cut is too tight / too loose" | style `cut.max_gap`, `cut.post_pad` | align |
| "no effect there" / "bigger word" | `script.json` effects | effects plan |
| caption look, on-screen text | style `captions` / `onscreen`, or script `onscreen` | finish |
| music | `script.json` `"music": {"file": "...", "db": -22}` | finish |

Re-running from a stage means every stage after it too. Re-running align or cut means effects
render again (slow), so batch the notes first.

## 7. Final

1. `PY scripts/finish.py <project> --final` -> `final/final.mp4` and `final/cover.jpg`.
2. Write `final/caption.md`:
   - First ~125 characters carry the hook; that is all the feed shows before "more".
   - One call to action. If it is "comment KEYWORD", it matches the video.
   - Max 5 hashtags, specific to the topic, at the end. In the user's language and voice.
   - No invented numbers. No "stop scrolling", no hashtag walls.
3. Remind them in one line: trending audio is added inside Instagram, and they post it themselves.

## Rules

- The style .md is the taste. When unsure whether to add something, leave it out.
- Never cover the face. Never zoom past 2x.
- Be straight about limits: the editor picks takes and timings well; it does not judge their
  delivery. If a take sounds flat, say "check line 3's energy", do not pretend you heard it.
- Keep `projects/` out of git: raw footage is large and personal.
