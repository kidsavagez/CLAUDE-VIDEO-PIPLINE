# Credits

This pipeline stands on other people's open-source work. Thank you.

## Repos and tools the pipeline uses

| What | Used for | By | Licence |
|---|---|---|---|
| [claude-video-effects](https://github.com/Vibha-Ramprakash/claude-video-effects) | the 51 face-tracking effects, fonts and models. `install.py` clones it into `vendor/` at a pinned, reviewed commit; it is not copied into this repo | Vibha Ramprakash ([@vibha.in.progress](https://instagram.com/vibha.in.progress)) | MIT |
| [YuNet face detector](https://github.com/opencv/opencv_zoo) | face tracking (ships inside claude-video-effects) | OpenCV Zoo | MIT |
| [MediaPipe Selfie Segmenter](https://ai.google.dev/edge/mediapipe/solutions/vision/image_segmenter) | cutting the speaker out from the background (inside claude-video-effects) | Google | Apache 2.0 |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | word-level transcription | SYSTRAN | MIT |
| [Whisper](https://github.com/openai/whisper) models (small, large-v3-turbo) | the speech-recognition models faster-whisper runs | OpenAI | MIT |
| [MusicGen](https://github.com/facebookresearch/audiocraft) (`facebook/musicgen-small`) | background music made on your computer (`scripts/music_bed.py`) | Meta AI | code MIT, **model weights CC-BY-NC 4.0** |
| [Transformers](https://github.com/huggingface/transformers) | runs MusicGen | Hugging Face | Apache 2.0 |
| [PyTorch](https://github.com/pytorch/pytorch) | runs MusicGen | PyTorch Foundation | BSD-3 |
| [FFmpeg](https://ffmpeg.org) | cutting, captions, loudness, export | FFmpeg team | LGPL / GPL |
| [OpenCV](https://github.com/opencv/opencv), [MediaPipe](https://github.com/google-ai-edge/mediapipe), [Pillow](https://github.com/python-pillow/Pillow), [NumPy](https://github.com/numpy/numpy) | image and video processing | their communities | Apache 2.0 / Apache 2.0 / MIT-CMU / BSD |
| [Claude Code](https://claude.com/claude-code) | runs the `/reel` skill: writes the script, edits, renders | Anthropic | Anthropic terms |

## Companion skills (recommended, installed separately)

The `/reel` skill reads your voice profile from these when it writes a script
(`~/.claude/instagram/voice.md` or `~/.claude/youtube/voice.md`). They also cover what this pipeline
doesn't: hook scoring, viral research, caption linting, carousels, titles and thumbnails, retention
analysis. They are not copied into this repo; install them from their own pages.

| What | Used for | By | Licence |
|---|---|---|---|
| [instagram-agent-skill](https://github.com/Jakeschincariol/instagram-agent-skill) | the Instagram voice profile (`~/.claude/instagram/voice.md`), plus 13 Instagram skills: Reel hooks, captions, carousels, stories, planning, DMs | Jake Schincariol ([opusjake.ai](https://opusjake.ai)) | MIT |
| [youtube-agent-skill](https://github.com/Jakeschincariol/youtube-agent-skill) | the YouTube voice profile (`~/.claude/youtube/voice.md`), plus 11 YouTube skills: scripts, titles and thumbnails, Shorts, chapters, SEO | Jake Schincariol | MIT |

**About the MusicGen licence:** the model weights are CC-BY-NC 4.0 (non-commercial). Music you make
with it is fine for personal and creator content, but check the licence yourself before using it in
paid ads or client work. For commercial jobs, use music you have a licence for.

## Used only for the example reels in `examples/`

These made the motion-graphics look of the three example reels. They are not part of the pipeline
and are not in this repo.

| What | Used for | By |
|---|---|---|
| [HyperFrames](https://hyperframes.heygen.com) | HTML-to-video motion graphics, film texture, rendering | HeyGen |
| [GSAP](https://gsap.com) | the animation timelines inside HyperFrames | GreenSock / Webflow |
| [Inter](https://github.com/rsms/inter), [Playfair Display](https://github.com/clauseggers/Playfair), [Space Mono](https://github.com/googlefonts/spacemono), [Archivo Black](https://github.com/Omnibus-Type/Archivo), [Anton](https://github.com/googlefonts/AntonFont) | typography | their designers, SIL Open Font License |
| Sound effects | "scribble" by [indigosierra](https://freesound.org/people/indigosierra/sounds/82610), "Thump" by [mpuffenbarger](https://freesound.org/people/mpuffenbarger/sounds/683031), "Page Slides - 1" by [SpaceJoe](https://freesound.org/people/SpaceJoe/sounds/484920) (CC0, via Freesound / Openverse); the rest from the HyperFrames bundled library | |
| Music | generated locally with MusicGen (see above) | |

Made something you think is missing here? Open an issue and it gets added.
