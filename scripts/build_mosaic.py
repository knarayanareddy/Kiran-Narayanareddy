#!/usr/bin/env python3
"""Screenshot every live deployment and render them as one mosaic.

The profile's most unusual asset is that dozens of projects are actually running
in public. A table of text links does not communicate that; a wall of screenshots
does. This script captures each site at a fixed viewport, crops and scales the
results to a uniform tile, and composes a single PNG mosaic plus a per-theme SVG
index that links each tile to its live URL.

Screenshots are expensive, so they are cached: a site is only re-captured when it
has been pushed since the last capture, when the cached PNG is missing, or when
--force is passed. The daily workflow therefore costs almost nothing.

Usage:
    python3 scripts/build_mosaic.py                # incremental
    python3 scripts/build_mosaic.py --force        # recapture everything
    python3 scripts/build_mosaic.py --limit 6      # quick local test

Requires playwright (installed in CI via `playwright install chromium`).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITES = os.path.join(ROOT, "data", "sites.json")
SHOTS = os.path.join(ROOT, "assets", "shots")
OUT_DIR = os.path.join(ROOT, "assets")

USER = os.environ.get("PROFILE_USER", "knarayanareddy")
VIEWPORT = {"width": 1280, "height": 800}
TILE = 360            # display width of one tile in the mosaic
COLS = 4
ROWS = 4              # per page: 16 tiles
PAD = 14
GAP = 14
CAPTION = 26          # strip under each tile for the repo name

THEMES = {
    "dark": {"bg": "#0d1117", "tile": "#161b22", "grid": "#30363d",
             "text": "#e6edf3", "muted": "#8b949e", "accent": "#58a6ff"},
    "light": {"bg": "#ffffff", "tile": "#f6f8fa", "grid": "#d0d7de",
              "text": "#0d1117", "muted": "#57606a", "accent": "#0969da"},
}


def fetch_sites_live() -> list[dict] | None:
    """Ask the Pages API directly so we never capture from a stale snapshot.

    The daily refresh normally updates data/sites.json, but a capture run that
    races it (or runs on a branch) should still see sites deployed today.
    """
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token or os.environ.get("MOSAIC_OFFLINE"):
        return None
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "mosaic-builder",
        "Authorization": f"Bearer {token}",
    }

    def get(path: str):
        request = urllib.request.Request(f"https://api.github.com{path}", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError:
            return None

    repos = []
    for page in (1, 2):
        batch = get(f"/users/{USER}/repos?per_page=100&page={page}&sort=pushed&type=owner")
        if not batch:
            break
        repos.extend(batch)

    sites = []
    for repo in repos:
        if repo.get("fork") or repo["name"] in EXCLUDE:
            continue
        home = (repo.get("homepage") or "").strip()
        info = get(f"/repos/{USER}/{repo['name']}/pages")
        on_pages = isinstance(info, dict) and bool(info.get("html_url"))
        url = None
        external = False
        if home and "github.io" not in home:
            if on_pages or repo.get("has_pages"):
                url, external = home, True
        elif on_pages:
            url = info["html_url"]
        elif home:
            url = home
        if not url:
            continue
        sites.append({
            "repo": repo["name"],
            "url": url.rstrip("/") + "/",
            "lang": repo.get("language") or "",
            "stars": repo.get("stargazers_count", 0),
            "pushed": (repo.get("pushed_at") or "")[:10],
            "pages": not external,
        })
    return sites or None


def load_sites() -> list[dict]:
    live = fetch_sites_live()
    if live:
        print(f"using {len(live)} live sites from the GitHub API", file=sys.stderr)
        sites = live
    else:
        with open(SITES, encoding="utf-8") as handle:
            sites = json.load(handle).get("sites", [])
    # Pages first, then most recently pushed: the top of the wall should be the
    # things that are actually alive.
    sites.sort(key=lambda s: (not s.get("pages", False), s.get("pushed", "")), reverse=True)
    return sites


def needs_capture(site: dict) -> bool:
    path = os.path.join(SHOTS, f"{site['repo']}.png")
    if not os.path.exists(path):
        return True
    meta_path = os.path.join(SHOTS, f"{site['repo']}.json")
    if not os.path.exists(meta_path):
        return True
    try:
        with open(meta_path, encoding="utf-8") as handle:
            meta = json.load(handle)
    except json.JSONDecodeError:
        return True
    return meta.get("pushed") != site.get("pushed")


def capture(sites: list[dict], force: bool, workers: int = 4) -> None:
    from playwright.sync_api import sync_playwright  # imported lazily

    os.makedirs(SHOTS, exist_ok=True)
    todo = [s for s in sites if force or needs_capture(s)]
    print(f"capturing {len(todo)} of {len(sites)} sites "
          f"({len(sites) - len(todo)} cached)", file=sys.stderr)
    if not todo:
        return

    def shoot(site: dict) -> tuple[str, str]:
        name = site["repo"]
        png = os.path.join(SHOTS, f"{name}.png")
        try:
            with sync_playwright() as play:
                browser = play.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
                page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
                page.goto(site["url"], wait_until="networkidle", timeout=45_000)
                # let entrance animations settle, then freeze them for a clean still
                page.add_style_tag(content="*,*::before,*::after{animation-play-state:paused!important}")
                page.wait_for_timeout(600)
                page.screenshot(path=png, type="png")
                browser.close()
            meta_path = os.path.join(SHOTS, f"{name}.json")
            meta = {"url": site["url"], "pushed": site.get("pushed"),
                    "captured": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
            previous = None
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, encoding="utf-8") as handle:
                        previous = json.load(handle)
                except json.JSONDecodeError:
                    previous = None
            if previous != meta:
                with open(meta_path, "w", encoding="utf-8") as handle:
                    json.dump(meta, handle, indent=1, sort_keys=True)
                    handle.write("\n")
            return name, "ok"
        except Exception as exc:  # noqa: BLE001 - a dead site must not kill the run
            return name, f"fail: {type(exc).__name__}"

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for name, status in pool.map(shoot, todo):
            print(f"  {status:28} {name}", file=sys.stderr)


def _font(size: int, bold: bool = False):
    """A real TTF if the runner has one; PIL's bitmap default is unreadable."""
    from PIL import ImageFont

    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono%s.ttf" % ("-Bold" if bold else ""),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else ""),
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/System/Library/Fonts/Menlo.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def compose(sites: list[dict]) -> None:
    from PIL import Image, ImageDraw

    available = []
    for site in sites:
        path = os.path.join(SHOTS, f"{site['repo']}.png")
        if os.path.exists(path):
            available.append((site, path))

    if not available:
        raise SystemExit("no screenshots available; run without --cached first")

    per_page = COLS * ROWS
    pages = [available[i: i + per_page] for i in range(0, len(available), per_page)]
    for index, page in enumerate(pages, start=1):
        suffix = "" if index == 1 else f"-{index}"
        compose_page(page, suffix)
    print(f"composed {len(pages)} page(s) covering {len(available)} sites", file=sys.stderr)


def compose_page(selected: list[dict], suffix: str) -> None:
    from PIL import Image, ImageDraw

    rows = (len(selected) + COLS - 1) // COLS
    width = PAD * 2 + COLS * TILE + (COLS - 1) * GAP
    height = PAD * 2 + rows * (TILE * 9 // 16 + CAPTION) + (rows - 1) * GAP

    for theme_name, theme in THEMES.items():
        canvas = Image.new("RGB", (width, height), theme["bg"])
        draw = ImageDraw.Draw(canvas)
        caption_font = _font(12)
        for index, (site, path) in enumerate(selected):
            col, row = index % COLS, index // COLS
            x = PAD + col * (TILE + GAP)
            y = PAD + row * (TILE * 9 // 16 + CAPTION + GAP)
            tile_h = TILE * 9 // 16

            shot = Image.open(path).convert("RGB")
            # top-crop to the tile aspect, then downscale with a good filter
            scale = max(TILE / shot.width, tile_h / shot.height)
            resized = shot.resize((max(TILE, int(shot.width * scale)),
                                   max(tile_h, int(shot.height * scale))), Image.LANCZOS)
            left = (resized.width - TILE) // 2
            tile = resized.crop((left, 0, left + TILE, tile_h))

            # rounded corners via a mask
            mask = Image.new("L", (TILE, tile_h), 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, TILE, tile_h), radius=8, fill=255)
            canvas.paste(tile, (x, y), mask)

            draw.rounded_rectangle((x, y, x + TILE, y + tile_h), radius=8,
                                   outline=theme["grid"], width=1)
            label = site["repo"]
            if len(label) > 36:
                label = label[:35] + "…"
            draw.text((x + 2, y + tile_h + 6), label, fill=theme["muted"], font=caption_font)
            if not site.get("pages", False):
                draw.text((x + TILE - 18, y + tile_h + 6), "↗", fill=theme["accent"], font=caption_font)

        out = os.path.join(OUT_DIR, f"mosaic-{theme_name}{suffix}.png")
        canvas.save(out, optimize=True)
        print(f"wrote {os.path.relpath(out, ROOT)} "
              f"({os.path.getsize(out):,} bytes, {len(selected)} tiles)", file=sys.stderr)


def index_svg(sites: list[dict]) -> None:
    """A clickable version of the same wall: each tile links to its live site."""
    with_shots = [s for s in sites if os.path.exists(os.path.join(SHOTS, f"{s['repo']}.png"))]
    per_page = COLS * ROWS * 2  # the SVG index is denser than the PNG wall
    tiles = with_shots[:per_page]
    rows = (len(tiles) + COLS - 1) // COLS
    tile_w, tile_h = 210, 118
    width = PAD * 2 + COLS * tile_w + (COLS - 1) * GAP
    height = PAD * 2 + rows * tile_h + (rows - 1) * GAP

    for theme_name, theme in THEMES.items():
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="Live deployments">',
            f'<rect width="{width}" height="{height}" fill="{theme["bg"]}"/>',
        ]
        for index, site in enumerate(tiles):
            col, row = index % COLS, index // COLS
            x = PAD + col * (tile_w + GAP)
            y = PAD + row * (tile_h + GAP)
            href = f'https://github.com/knarayanareddy/{site["repo"]}'
            parts.append(
                f'<a href="{href}">'
                f'<image href="shots/{site["repo"]}.png" x="{x}" y="{y}" '
                f'width="{tile_w}" height="{tile_h}" preserveAspectRatio="xMidYMin slice" '
                f'clip-path="inset(0 round 8px)"/>'
                f'<rect x="{x}" y="{y}" width="{tile_w}" height="{tile_h}" rx="8" '
                f'fill="none" stroke="{theme["grid"]}"/>'
                f"</a>"
            )
        parts.append("</svg>")
        path = os.path.join(OUT_DIR, f"mosaic-{theme_name}.svg")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(parts))
        print(f"wrote {os.path.relpath(path, ROOT)}", file=sys.stderr)


EXCLUDE = {"sylva", "onegov2-spatial-assistant"}


def write_manifest(sites: list[dict]) -> None:
    """Record which sites we have, which we missed, and why."""
    rows = []
    for site in sites:
        png = os.path.join(SHOTS, f"{site['repo']}.png")
        rows.append({
            "repo": site["repo"],
            "url": site["url"],
            "ok": os.path.exists(png),
            "bytes": os.path.getsize(png) if os.path.exists(png) else 0,
            "pushed": site.get("pushed"),
        })
    ok = sum(1 for r in rows if r["ok"])
    payload = {
        "total": len(rows),
        "captured": ok,
        "missing": [r["repo"] for r in rows if not r["ok"]],
        "sites": rows,
    }
    path = os.path.join(ROOT, "data", "shots-manifest.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    print(f"manifest: {ok}/{len(rows)} captured"
          f"{', missing ' + ', '.join(payload['missing']) if payload['missing'] else ''}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="recapture every site")
    parser.add_argument("--cached", action="store_true", help="skip capture, recompose only")
    parser.add_argument("--limit", type=int, default=0, help="capture only the first N sites")
    args = parser.parse_args()

    sites = load_sites()
    if args.limit:
        sites = sites[: args.limit]

    if not args.cached:
        try:
            capture(sites, args.force)
        except ImportError:
            print("playwright is not installed; composing from cache only", file=sys.stderr)

    compose(sites)
    index_svg(sites)
    write_manifest(sites)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
