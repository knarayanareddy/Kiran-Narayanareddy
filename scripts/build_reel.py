#!/usr/bin/env python3
"""Record each live project as a short animated reel instead of a still.

A screenshot proves a site was up. A few seconds of it *moving* proves it runs:
the counter ticking, the skeleton filling in, the canvas drawing, the page
scrolling. GitHub renders animated images inline -- it strips <iframe>, <video>
and <object> from READMEs, but a GIF in an <img> just plays. That is the closest
thing to a live demo a profile README can honestly have.

Two rules, because the alternative is dishonest:

  1. **It is a recording, not a simulation.** Every frame comes from a real
     browser rendering the real URL. Nothing here fakes a "live" state.
  2. **It never claims to be live.** Each reel is captioned with its capture
     date and the word "recorded". A loop that looks interactive but is a week
     old is a lie of omission; a loop that says "recorded 2026-11-02" is an
     honest advertisement. The pulsing LIVE pill the still tiles use is
     deliberately absent here -- an animation cannot pulse, so claiming it would
     be a promise the format cannot keep.

The gesture is deliberately simple and repeatable: load the page, let it settle,
scroll down in eased steps so scroll-linked and lazy-loaded animation actually
fires, then return to the top so the loop restarts where it began.

Usage:
    python3 scripts/build_reel.py                 # every reel in REELS
    python3 scripts/build_reel.py toolscour
    python3 scripts/build_reel.py --force         # re-record even if cached

Requires playwright (CI installs it via `playwright install chromium`) and
ffmpeg (present on GitHub's ubuntu runners; `pip install imageio-ffmpeg` covers
a container that has neither).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from tokens import THEMES as TOKENS  # shared design system

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITES = os.path.join(ROOT, "data", "sites.json")
OUT = os.path.join(ROOT, "assets", "reels")
FRAMES = os.path.join(OUT, "frames")
MANIFEST = os.path.join(OUT, "manifest.json")

# The reels that earn their bandwidth. A GIF costs ~30x the bytes of a still, so
# this list is short on purpose: the newest build and the two projects that are
# actually interactive. Everything else keeps its still capture in the mosaic.
REELS = [
    ("sallie-returns-ai-agent", "returns pipeline"),
    ("toolscour", "3D knowledge galaxy"),
    ("3dexperimentation", "canvas film studio"),
]

# GitHub serves README images through Camo, which refuses anything over ~5 MB.
# Landing under it is not a nicety: over it the image is a broken icon.
MAX_BYTES = 4_900_000

WIDTH = 900
HEIGHT = 506          # 16:9 viewport, under a 34px address bar
BAR = 34
VIEWPORT = {"width": 1280, "height": 720}
FPS = 12              # the documentation sweet spot: smooth, not enormous
STEPS = 22
STEP_MS = 110
THEMES = TOKENS

WORK = os.path.join(OUT, "_work")
SCALED = os.path.join(WORK, "scaled")


def esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# Overlay: the chrome that makes a recording read as a browser window rather
# than a floating slab of pixels. Drawn once as a transparent PNG and composited
# by ffmpeg, so the frame count does not multiply the file size.
#
# Drawn with Pillow rather than an SVG because ffmpeg on the runners has no SVG
# rasteriser, and adding one dependency to draw four rectangles is not worth it.
# The colours come from the shared tokens, so the chrome matches the SVG cards.
# ---------------------------------------------------------------------------
def _font(size: int) -> "object":
    from PIL import ImageFont

    for name in ("DejaVuSansMono.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def chrome_png(path: str, url: str, repo: str, recorded: str) -> None:
    from PIL import Image, ImageDraw

    theme = {k: v.lstrip("#") for k, v in THEMES["dark"].items() if isinstance(v, str) and v.startswith("#")}

    def rgba(role: str, alpha: int = 255) -> tuple[int, int, int, int]:
        h = theme.get(role, "0d1117")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha

    image = Image.new("RGBA", (WIDTH, HEIGHT + BAR), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # address bar
    draw.rectangle([0, 0, WIDTH, BAR - 1], fill=rgba("surface"))
    draw.rectangle([0, BAR - 1, WIDTH, BAR], fill=rgba("border"))
    for i in range(3):
        cx = 16 + i * 15
        draw.ellipse([cx - 4, BAR // 2 - 4, cx + 4, BAR // 2 + 4], fill=rgba("borderSoft"))
    draw.rounded_rectangle([62, 7, WIDTH - 14, BAR - 7], 6, fill=rgba("canvas"), outline=rgba("border"))
    shown = url.replace("https://", "").rstrip("/")
    if len(shown) > 70:
        shown = shown[:67] + "..."
    draw.text((74, BAR // 2 - 6), shown, font=_font(11), fill=rgba("muted"))

    # caption strip, translucent so the page shows through: this is where the
    # honesty lives -- "recorded <date> · not live", never the word live.
    top = BAR + HEIGHT - 30
    draw.rectangle([0, top, WIDTH, BAR + HEIGHT], fill=rgba("canvas", 220))
    draw.rectangle([0, top, WIDTH, top + 1], fill=rgba("border"))
    draw.ellipse([12, top + 11, 20, top + 19], fill=rgba("live"))
    draw.text((30, top + 9), repo, font=_font(11), fill=rgba("text"))
    stamp = f"recorded {recorded} \u00b7 not live"
    text_w = draw.textlength(stamp, font=_font(10))
    draw.text((WIDTH - 14 - text_w, top + 10), stamp, font=_font(10), fill=rgba("muted"))

    image.save(path)


def ffmpeg() -> str | None:
    """ffmpeg from PATH, or from the pip wheel that ships a static build.

    GitHub runners have ffmpeg; a sandbox without system media tooling can still
    fetch imageio-ffmpeg from PyPI, which is why the fallback exists.
    """
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:                             # noqa: BLE001
        return None


def record(repo: str, url: str, force: bool) -> dict:
    """Drive a real browser over the real URL and screenshot as it moves."""
    from playwright.sync_api import sync_playwright  # imported lazily

    folder = os.path.join(FRAMES, repo)
    os.makedirs(folder, exist_ok=True)
    if force:
        for name in os.listdir(folder):
            if name.endswith(".png"):
                os.remove(os.path.join(folder, name))

    with sync_playwright() as play:
        browser = play.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
        try:
            page.goto(url, wait_until="networkidle", timeout=45_000)
        except Exception:                         # noqa: BLE001
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(900)                # let fonts and first paint land

        height = page.evaluate("document.body.scrollHeight") or VIEWPORT["height"]
        travel = max(0, min(height - VIEWPORT["height"], 2000))

        index = 0
        for step in range(STEPS):
            # Ease in and out, so the motion reads as a person scrolling rather
            # than a machine teleporting: slow at both ends, faster in the middle.
            t = step / (STEPS - 1)
            y = int(travel * (0.5 - 0.5 * math.cos(math.pi * t)))
            page.evaluate(f"window.scrollTo({{top:{y}, behavior:'instant'}})")
            page.wait_for_timeout(STEP_MS)
            page.screenshot(path=os.path.join(folder, f"f{index:03d}.png"))
            index += 1

        # Return to the top, so the loop restarts where it began instead of
        # snapping back every few seconds.
        for _ in range(2):
            page.evaluate("window.scrollTo({top:0, behavior:'instant'})")
            page.wait_for_timeout(STEP_MS * 2)
            page.screenshot(path=os.path.join(folder, f"f{index:03d}.png"))
            index += 1

        browser.close()

    return {"frames": index, "recorded": datetime.now(timezone.utc).strftime("%Y-%m-%d")}


def scale_frames(repo: str) -> int:
    """Crop the 1280x720 viewport to the reel aspect and downscale once."""
    exe = ffmpeg()
    if not exe:
        raise RuntimeError("no ffmpeg on PATH and no imageio-ffmpeg installed")
    shutil.rmtree(SCALED, ignore_errors=True)
    os.makedirs(SCALED, exist_ok=True)
    crop_h = int(VIEWPORT["width"] * HEIGHT / WIDTH)      # exactly the viewport
    subprocess.run(
        [exe, "-y", "-loglevel", "error", "-framerate", str(FPS),
         "-i", os.path.join(FRAMES, repo, "f%03d.png"),
         # The bottom caption lives *inside* the frame, so the canvas has to be
         # the full height; padding the viewport down by the bar keeps the
         # chrome overlay from being clipped at the bottom.
         "-vf", f"crop={VIEWPORT['width']}:{crop_h}:0:0,scale={WIDTH}:{HEIGHT}:flags=lanczos,"
                f"pad={WIDTH}:{HEIGHT + BAR}:0:{BAR}:color=0x0d1117",
         os.path.join(SCALED, "s%03d.png")],
        check=True,
    )
    return len([n for n in os.listdir(SCALED) if n.endswith(".png")])


def compose_gif(repo: str, url: str, recorded: str) -> tuple[str, int]:
    """Overlay the chrome, then encode a looping GIF under the Camo limit."""
    exe = ffmpeg()
    if not exe:
        raise SystemExit("no ffmpeg available: install it, or pip install imageio-ffmpeg")

    os.makedirs(WORK, exist_ok=True)
    overlay = os.path.join(WORK, "chrome.png")
    chrome_png(overlay, url, repo, recorded)

    gif = os.path.join(OUT, f"{repo}.gif")
    width = WIDTH
    colors = 160
    for attempt in range(4):
        palette = os.path.join(WORK, "palette.png")
        subprocess.run(
            [exe, "-y", "-loglevel", "error", "-framerate", str(FPS),
             "-i", os.path.join(SCALED, "s%03d.png"),
             "-i", overlay,
             "-filter_complex",
             f"[0:v]scale={width}:-1:flags=lanczos,fps={FPS}[base];"
             f"[base][1:v]overlay=0:0:format=auto,split[a][b];"
             f"[a]palettegen=max_colors={colors}:stats_mode=diff[p];"
             f"[b][p]paletteuse=dither=bayer:bayer_scale=2:diff_mode=rectangle",
             "-loop", "0", gif],
            check=True,
        )
        size = os.path.getsize(gif)
        if size <= MAX_BYTES:
            break
        # Fewer colours and a narrower canvas before fewer frames: motion is the
        # whole point, so a smooth loop at 720px beats a stuttering one at 900px.
        if attempt == 1:
            colors = 96
        elif attempt == 2:
            width = 720
        else:
            colors = 64
    return gif, size


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repos", nargs="*", help="only these repos")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(FRAMES, exist_ok=True)

    try:
        with open(SITES, encoding="utf-8") as handle:
            by_name = {s["repo"]: s for s in json.load(handle)["sites"]}
    except (OSError, ValueError, KeyError) as exc:
        print(f"cannot read {SITES}: {exc}", file=sys.stderr)
        return 1

    manifest = {}
    if os.path.exists(MANIFEST):
        try:
            with open(MANIFEST, encoding="utf-8") as handle:
                manifest = json.load(handle)
        except ValueError:
            manifest = {}

    wanted = [(n, lbl) for n, lbl in REELS if not args.repos or n in args.repos]
    failures = 0
    for repo, label in wanted:
        site = by_name.get(repo)
        if not site:
            print(f"{repo}: not in data/sites.json (nothing deployed?)", file=sys.stderr)
            failures += 1
            continue

        folder = os.path.join(FRAMES, repo)
        cached = os.path.isdir(folder) and any(n.endswith(".png") for n in os.listdir(folder))
        try:
            if args.force or not cached:
                info = record(repo, site["url"], args.force)
            else:
                info = {
                    "frames": len([n for n in os.listdir(folder) if n.endswith(".png")]),
                    "recorded": manifest.get(repo, {}).get("recorded")
                    or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                }
            kept = scale_frames(repo)
            if not kept:
                raise RuntimeError("no frames to encode")
            gif, size = compose_gif(repo, site["url"], info["recorded"])
        except Exception as exc:                  # noqa: BLE001
            print(f"{repo}: could not build a reel ({type(exc).__name__}: {exc})", file=sys.stderr)
            failures += 1
            continue

        manifest[repo] = {
            "label": label,
            "url": site["url"],
            "recorded": info["recorded"],
            "frames": info["frames"],
            "gif_bytes": size,
            "under_camo_limit": size <= MAX_BYTES,
        }
        flag = "" if size <= MAX_BYTES else "  ** OVER the 5 MB Camo limit **"
        print(f"{repo:28} {info['frames']:3} frames  {size / 1e6:5.2f} MB  {label}{flag}")

    with open(MANIFEST, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")

    shutil.rmtree(WORK, ignore_errors=True)
    return 1 if failures and failures == len(wanted) else 0


if __name__ == "__main__":
    raise SystemExit(main())
