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

# Every project that gets a reel. A GIF costs ~30x the bytes of a still, so this
# is a deliberate edit, not "all 37": the ones with something to show. Each entry
# is (repo, one-line label, the gesture that best suits the page).
#
#   scroll  - a landing page or document: scrolling reveals it
#   pointer - an app or dashboard: hover states and pointer-reactive canvases
#   mixed   - a bit of both
REELS = [
    ("sallie-returns-ai-agent", "returns pipeline", "pointer"),
    ("toolscour", "3D knowledge galaxy", "mixed"),
    ("3dexperimentation", "canvas film studio", "pointer"),
    ("AI-Arsenal", "schema-first encyclopedia", "scroll"),
    ("gitscour", "50,000+ repo knowledge base", "scroll"),
    ("Aeroscribe", "manuscript pipeline", "scroll"),
    ("WebsitedesignandPrompts", "landing-page templates", "scroll"),
    ("Bunqsy", "7-agent financial guardian", "pointer"),
    ("AI-Daily", "daily AI briefing", "scroll"),
    ("curiolab", "family science episodes", "mixed"),
    ("roomsmith", "escape-room engine", "pointer"),
    ("dreamswarm", "multi-agent orchestrator", "mixed"),
    ("gridqueue-grid-connection", "grid interconnection navigator", "pointer"),
    ("twitch-codex", "live-audience builds", "mixed"),
    ("proofpress-evidence-portal", "Three.js evidence journey", "mixed"),
    ("jointcheck-solder-inspection", "solder-joint inspection", "mixed"),
    ("redflag-eu-compliance", "EU product-safety gate", "scroll"),
    ("harvestgrid", "harvest forecasting + gleaning", "mixed"),
    ("Magpie", "autonomous classifieds scout", "scroll"),
    ("Nimbus", "parametric climate cover", "mixed"),
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
    # Opaque, not translucent: at 86% the page's own text showed through the
    # caption and collided with it, which read as a rendering bug.
    draw.rectangle([0, top, WIDTH, BAR + HEIGHT], fill=rgba("canvas"))
    draw.rectangle([0, top, WIDTH, top + 1], fill=rgba("border"))
    draw.ellipse([12, top + 11, 20, top + 19], fill=rgba("live"))
    draw.text((30, top + 9), repo, font=_font(11), fill=rgba("text"))
    stamp = f"recorded {recorded} \u00b7 not live"
    text_w = draw.textlength(stamp, font=_font(10))
    draw.text((WIDTH - 14 - text_w, top + 10), stamp, font=_font(10), fill=rgba("muted"))

    image.save(path)


def make_posters() -> dict:
    """A still cover per reel, for the grid on the README.

    The grid shows a cover per project; the GIF is only fetched when someone opens
    that project. That is not decoration: GitHub emits no loading="lazy" on README
    images (checked in the served HTML), so twenty eager GIFs would be ~40 MB
    downloaded before anyone clicked anything. Twenty covers are ~1.5 MB.

    The cover is the reel's first frame plus the same chrome, so the grid and the
    playing reel look like the same thing.
    """
    from PIL import Image

    covers = {}
    manifest = {}
    if os.path.exists(MANIFEST):
        try:
            with open(MANIFEST, encoding="utf-8") as handle:
                manifest = json.load(handle)
        except ValueError:
            manifest = {}

    for repo, info in manifest.items():
        frames = sorted(
            n for n in os.listdir(os.path.join(FRAMES, repo)) if n.endswith(".png")
        ) if os.path.isdir(os.path.join(FRAMES, repo)) else []
        if not frames:
            continue
        # mid-reel, not frame zero: frame zero is a page that has not started
        # moving yet, and the cover of a demo should look like something happening
        chrome = os.path.join(work_dir(repo), "chrome.png")
        if not os.path.exists(chrome):
            # A normal run deletes its scratch directory when it finishes, so the
            # separate --posters step has to be able to draw the chrome itself.
            chrome_png(chrome, info["url"], repo, info.get("recorded", ""))

        source = os.path.join(FRAMES, repo, frames[len(frames) // 3])
        cover = os.path.join(OUT, f"{repo}-cover.png")
        img = Image.open(source).convert("RGB")
        if img.size == (WIDTH, HEIGHT + BAR):
            # Already composed (a frame recovered from a finished reel). Take the
            # page area only, so the chrome is not pasted on twice.
            img = img.crop((0, BAR, WIDTH, BAR + HEIGHT))
        else:
            img = img.crop((0, 0, VIEWPORT["width"], int(VIEWPORT["width"] * HEIGHT / WIDTH)))
            img = img.resize((WIDTH, HEIGHT), Image.LANCZOS)
        canvas = Image.new("RGB", (WIDTH, HEIGHT + BAR), "#0d1117")
        canvas.paste(img, (0, BAR))
        chrome = Image.open(chrome).convert("RGBA")
        canvas.paste(chrome, (0, 0), chrome)
        canvas = canvas.convert("P", palette=Image.ADAPTIVE, colors=160)
        canvas.save(cover, optimize=True)
        info["cover_bytes"] = os.path.getsize(cover)
        covers[repo] = cover
        print(f"{repo:30} cover {info['cover_bytes'] / 1e3:6.0f} kB")

    with open(MANIFEST, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return covers


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


def record(repo: str, url: str, force: bool, gesture: str = "mixed") -> dict:
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

        # App-like pages (a dashboard, a canvas studio) have nothing to scroll,
        # so a scroll-only reel would be a still image of a running app. Sweep
        # the pointer across them instead: hover states fire, and the
        # pointer-reactive canvases actually react. Still a recording of the
        # real page, just a gesture that suits the page.
        if gesture == "pointer" or (gesture == "mixed" and travel < 200):
            page.evaluate("window.scrollTo({top:0, behavior:'instant'})")
            cols, rows = 5, 2
            for r in range(rows):
                for c in range(cols):
                    x = VIEWPORT["width"] * (0.15 + 0.7 * c / (cols - 1))
                    y = VIEWPORT["height"] * (0.3 + 0.4 * r / max(1, rows - 1))
                    page.mouse.move(x, y, steps=6)
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


def work_dir(repo: str) -> str:
    """Per-reel scratch space.

    Shared scratch broke as soon as reels were recorded in parallel: two workers
    wrote s000.png into the same directory and the encoder stitched a flipbook
    of two different sites. Each repo gets its own.
    """
    path = os.path.join(WORK, repo)
    os.makedirs(path, exist_ok=True)
    return path


def scale_frames(repo: str) -> int:
    """Crop the 1280x720 viewport to the reel aspect and downscale once."""
    exe = ffmpeg()
    if not exe:
        raise RuntimeError("no ffmpeg on PATH and no imageio-ffmpeg installed")
    scaled = os.path.join(work_dir(repo), "scaled")
    shutil.rmtree(scaled, ignore_errors=True)
    os.makedirs(scaled, exist_ok=True)
    crop_h = int(VIEWPORT["width"] * HEIGHT / WIDTH)      # exactly the viewport
    subprocess.run(
        [exe, "-y", "-loglevel", "error", "-framerate", str(FPS),
         "-i", os.path.join(FRAMES, repo, "f%03d.png"),
         # The bottom caption lives *inside* the frame, so the canvas has to be
         # the full height; padding the viewport down by the bar keeps the
         # chrome overlay from being clipped at the bottom.
         "-vf", f"crop={VIEWPORT['width']}:{crop_h}:0:0,scale={WIDTH}:{HEIGHT}:flags=lanczos,"
                f"pad={WIDTH}:{HEIGHT + BAR}:0:{BAR}:color=0x0d1117",
         os.path.join(scaled, "s%03d.png")],
        check=True,
    )
    return len([n for n in os.listdir(scaled) if n.endswith(".png")])


def compose_gif(repo: str, url: str, recorded: str) -> tuple[str, int]:
    """Overlay the chrome, then encode a looping GIF under the Camo limit."""
    exe = ffmpeg()
    if not exe:
        raise SystemExit("no ffmpeg available: install it, or pip install imageio-ffmpeg")

    overlay = os.path.join(work_dir(repo), "chrome.png")
    chrome_png(overlay, url, repo, recorded)

    gif = os.path.join(OUT, f"{repo}.gif")
    width = WIDTH
    colors = 160
    for attempt in range(4):
        palette = os.path.join(work_dir(repo), "palette.png")
        subprocess.run(
            [exe, "-y", "-loglevel", "error", "-framerate", str(FPS),
             "-i", os.path.join(work_dir(repo), "scaled", "s%03d.png"),
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
    parser.add_argument("--posters", action="store_true",
                        help="only rebuild the grid covers from frames already on disk")
    args = parser.parse_args()

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(FRAMES, exist_ok=True)

    if args.posters:
        # Separate CI step, run with Pillow but without a browser: it only needs
        # the frames the recording step already left behind.
        make_posters()
        shutil.rmtree(WORK, ignore_errors=True)
        return 0

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

    wanted = [r for r in REELS if not args.repos or r[0] in args.repos]
    failures = 0
    for repo, label, gesture in wanted:
        site = by_name.get(repo)
        if not site:
            print(f"{repo}: not in data/sites.json (nothing deployed?)", file=sys.stderr)
            failures += 1
            continue

        folder = os.path.join(FRAMES, repo)
        cached = os.path.isdir(folder) and any(n.endswith(".png") for n in os.listdir(folder))
        try:
            if args.force or not cached:
                info = record(repo, site["url"], args.force, gesture)
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
            # A cover is made here too when a browser is available; the CI step
            # also re-runs this from frames alone, which is what covers a
            # re-record on a runner without Pillow.
            try:
                make_posters()
            except Exception:                     # noqa: BLE001
                pass
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
