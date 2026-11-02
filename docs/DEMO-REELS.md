# The demo reels

A screenshot proves a site was up. A few seconds of it *moving* proves it runs.
That is why `assets/reels/` exists.

## What GitHub will and will not do

| Format | In a profile README |
|---|---|
| `<iframe>` | stripped by the sanitiser |
| `<video>` / `<embed>` / `<object>` | stripped |
| **animated GIF in `<img>`** | **plays, loops, no click needed** |
| animated WebP | works in browsers, but not reliably everywhere a README is viewed |

So the reel is a GIF: the one moving format a profile README is guaranteed to
play. It is captioned `recorded <date> · not live` because that is the truth —
it is a recording of a real page, not a live feed.

## The pipeline

```
reels.yml  ──►  scripts/build_reel.py  ──►  assets/reels/<repo>.gif
                    │                          assets/reels/manifest.json
                    ├── playwright drives Chromium over the real URL
                    │     load → settle 900ms → scroll down in eased steps
                    │     → 22 screenshots → scroll back → 2 screenshots
                    └── ffmpeg crops, scales, overlays the chrome, encodes
```

`scripts/build_profile.py` then renders the README section from
`assets/reels/manifest.json`, and **only lists a reel whose GIF is actually on
disk** — a failed recording leaves the section shorter instead of leaving a
broken image in the README.

## The rules the tests enforce

`tests/reels.test.mjs` fails if:

- the builder stops taking real `page.screenshot()` frames, or starts drawing
  viewport frames itself — a synthesised "demo" is a fabrication
- a caption stops carrying the recording date, or starts saying `live`
- a GIF exceeds **4.9 MB**: GitHub's Camo proxy refuses README images over ~5 MB,
  and over that line the demo is simply a broken icon
- the README references a reel file that is not there
- a generated GIF has one frame, i.e. a still pretending to be a reel

## Why only three reels

A GIF costs roughly thirty times the bytes of a still. Three reels is about the
budget a README can spend before it loads badly on a phone, so the list in
`REELS` is short on purpose: the newest build and the two projects that are
genuinely interactive. Everything else keeps its still in the screenshot wall.

## Recording locally

```bash
python3 -m pip install playwright pillow
python3 -m playwright install --with-deps chromium
python3 scripts/build_reel.py --force        # or: python3 scripts/build_reel.py toolscour
```

A container without a browser cannot record. It can still encode: `ffmpeg` comes
from PATH, or from `pip install imageio-ffmpeg` when the image has no system
media tooling.
