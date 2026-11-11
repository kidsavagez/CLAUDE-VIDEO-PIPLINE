#!/usr/bin/env python3
"""Create a project folder for one video.

    python new_project.py "klien-kabur" --lang id --style default

Makes projects/<date>-<slug>/ with raw/, work/, preview/, final/ and a script.json to fill in.
"""
import argparse
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, save  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("slug")
ap.add_argument("--lang", default="id", help="id, en, or auto")
ap.add_argument("--style", default="default")
ap.add_argument("--title", default="")
a = ap.parse_args()

slug = re.sub(r"[^a-z0-9]+", "-", a.slug.lower()).strip("-") or "video"
d = os.path.join(ROOT, "projects", f"{datetime.date.today():%Y-%m-%d}-{slug}")
if os.path.exists(os.path.join(d, "script.json")):
    sys.exit(f"already exists: {d}")
for sub in ("raw", "work", "preview", "final"):
    os.makedirs(os.path.join(d, sub), exist_ok=True)
save(os.path.join(d, "script.json"), {
    "title": a.title or a.slug,
    "lang": a.lang,
    "style": a.style,
    "music": None,
    "lines": [
        {"id": 1, "role": "hook", "text": "", "onscreen": "", "effects": []},
        {"id": 2, "role": "body", "text": "", "effects": []},
        {"id": 3, "role": "cta", "text": "", "effects": []}
    ]
})
print(d)
