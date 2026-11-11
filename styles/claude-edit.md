# Style: claude-edit

Taken from 3 reference reels: a Claude Code effects demo, an AI-tool versus real-designer
comparison, and an AI explainer built from kinetic type. All three are about AI and Claude.

## What the edit does

- **Captions are small and quiet.** One or two words at a time, sentence case, plain white,
  no karaoke colour and no big box. They sit around chest height and never shout.
- **The hook is type behind the head.** One reel opens on a desaturated frame with an italic serif
  word up top and a big red serif word sliding in behind the speaker's head. Red is the only
  accent colour across all three reels.
- **Something new every 3 to 6 seconds.** It might be a cutaway, a graphic, a widget or a word
  behind the head. The speaker is rarely on screen for more than 6 seconds without something
  changing.
- **Logos and UI as proof.** App logos (ChatGPT, Claude, Gemini, After Effects), Claude chat
  screens and editing timelines show up as evidence for what's being said.
- **Ends on a follow or comment prompt**, shown in UI form (a Follow button, a profile chip).

## Effects that match these moves

| Move in the references | Effect here |
|---|---|
| desaturated frame + big red word behind the head (hook) | `red-collage` |
| serif word dropping in behind the head | `backdrop-word` with `font: serif` |
| logos and app tiles floating around the speaker | `orbit` with your own logo images |
| Claude UI, timeline, "Edited by Claude" proof | `wave-trim`, `timeline`, `glass-widgets`, `checklist` |
| glowing word in a dark room | `spotlight` |
| Follow button prompt | `tap` |

## Never

- Big yellow karaoke captions or thick outlines
- More than one accent colour (red only)
- Covering the face

## Measured

| reel | length | cuts/min | median shot |
|---|---|---|---|
| Claude effects demo | 25.8 s | 16.3 | 3.1 s |
| AI vs designer | 56.9 s | 9.5 | 4.8 s |
| AI kinetic explainer | 79.4 s | 10.6 | 5.5 s |

All three are mixed to about -14 LUFS.

## What I can't copy

I only saw still frames. I couldn't see the motion (how words slide or slam in), hear the sound
design, or see the full-screen motion-graphic cutaways. Those cutaways are designed animation
the pipeline can't make; effects stand in for them.
