#!/usr/bin/env python3
"""Background music made on your own computer with MusicGen (facebook/musicgen-small, CPU, free,
no account). Needs the music environment: python install.py --music  (about 1 GB, once).
Run it with the music environment's python, not .venv:

    .venv-music/Scripts/python.exe scripts/music_bed.py <out.wav> --seconds 30 --seed 47 \
        --prompt "warm lo-fi hip hop groove, soft drums, mellow keys, steady, no vocals"

MusicGen makes at most ~30 s per run; for longer videos ask for 30 s and let finish.py loop it.
Generation takes a few minutes on a CPU. Try another --seed if the result is uneven.
Then put it in script.json: "music": {"file": "<out.wav>", "db": -22}  (finish.py ducks it under the voice).
"""
import argparse
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--prompt", default="warm lo-fi hip hop groove, soft drums, mellow keys, steady, no vocals")
    a = ap.parse_args()
    try:
        import numpy as np
        import soundfile as sf
        import torch
        from transformers import AutoProcessor, MusicgenForConditionalGeneration
    except ImportError:
        raise SystemExit("music environment missing. Run: python install.py --music, then use .venv-music's python")
    torch.manual_seed(a.seed)
    t0 = time.time()
    proc = AutoProcessor.from_pretrained("facebook/musicgen-small")
    model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small")
    inputs = proc(text=[a.prompt], padding=True, return_tensors="pt")
    tokens = int(min(a.seconds, 30) * model.config.audio_encoder.frame_rate)
    with torch.no_grad():
        audio = model.generate(**inputs, do_sample=True, guidance_scale=3.0, max_new_tokens=tokens)
    sr = model.config.audio_encoder.sampling_rate
    wav = audio[0, 0].cpu().numpy().astype(np.float32)
    wav = wav / max(1e-6, float(np.abs(wav).max())) * 0.9
    sf.write(a.out, wav, sr)
    print(f"wrote {a.out}  {len(wav) / sr:.1f}s  in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
