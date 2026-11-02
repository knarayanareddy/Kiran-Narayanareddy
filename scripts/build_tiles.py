#!/usr/bin/env python3
"""Turn each live site's screenshot into a self-contained "live window" tile.

GitHub strips <iframe>, <object> and <embed> from profile READMEs, so a real
embed is impossible. What is possible is the next best thing: an SVG that looks
and behaves like a running window instead of a screenshot --

  * a URL bar carrying the site's real address
  * a pulsing LIVE pill, so the row reads as "running", not "captured"
  * a scanline sweeping across the viewport at a different phase per tile
  * the actual latest capture, inlined as a data URI, so the tile is one file
    with no request of its own and can never show a broken image

Animation lives in CSS inside the SVG. GitHub serves README images through
Camo, and both Camo and the browser keep an SVG's internal CSS when it is
loaded through <img>, which is how the hero already animates. A
prefers-reduced-motion guard leaves a still window for anyone who asks for one.

    python3 scripts/build_tiles.py            # every tile in TILES
    python3 scripts/build_tiles.py toolscour  # just one

Screenshots come from assets/shots/<repo>.png, refreshed by screenshots.yml, so
re-running this after a capture is all it takes to keep the tiles current.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from PIL import Image

from tokens import THEMES as TOKENS  # shared design system

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(ROOT, "assets", "shots")
OUT = os.path.join(ROOT, "assets", "tiles")
SITES = os.path.join(ROOT, "data", "sites.json")
STATE = os.path.join(ROOT, "assets", "tiles", "state.json")

USER = os.environ.get("PROFILE_USER", "knarayanareddy")

W, H = 423, 258
BAR = 26              # URL bar height
VIEW = 196            # screenshot height
FOOT = H - BAR - VIEW  # caption strip

# name, metric line, scanline phase (seconds, staggered on purpose)
TILES = [
    ("Aeroscribe", "manuscript pipeline", 0.0),
    ("toolscour", "12,771 tools", 1.7),
    ("gitscour", "50,000+ repos", 3.1),
    ("AI-Arsenal", "1,598 entries", 4.6),
    ("WebsitedesignandPrompts", "38 templates", 2.4),
    ("Bunqsy", "7-agent oracle", 5.8),
]

THEMES = TOKENS  # from scripts/tokens.py — one palette for every card


def load_state() -> dict:
    """Capture ages, written by refresh-ctimes.yml.

    A tile may only say LIVE while the newest capture is recent. Past that it
    drops to a neutral "captured" label instead of pulsing a claim we cannot
    back — the same rule the rest of this profile follows.
    """
    try:
        with open(STATE, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def crop(path: str) -> Image.Image:
    """Top-crop to the viewport aspect, then downscale once with a good filter."""
    shot = Image.open(path).convert("RGB")
    scale = max(W / shot.width, VIEW / shot.height)
    resized = shot.resize((max(W, int(shot.width * scale)), max(VIEW, int(shot.height * scale))), Image.LANCZOS)
    left = (resized.width - W) // 2
    return resized.crop((left, 0, left + W, VIEW))


def data_uri(image: Image.Image) -> str:
    import io

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=72, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def render(name: str, metric: str, phase: float, theme_name: str, confirmed_live: bool = True) -> str:
    theme = THEMES[theme_name]
    shot_path = os.path.join(SHOTS, f"{name}.png")
    if not os.path.exists(shot_path):
        raise FileNotFoundError(shot_path)

    uri = data_uri(crop(shot_path))
    live_color = theme["live"] if confirmed_live else theme["muted"]
    live_label = "LIVE" if confirmed_live else "captured"
    live_cls = ' class="live-dot"' if confirmed_live else ""
    live_cls_b = ' class="live-dot-b"' if confirmed_live else ""
    # Right-align the pill to the bar edge; mono 7.5px bold advances ~4.7px.
    live_w = len(live_label) * 4.7 + 0.6 * (len(live_label) - 1)
    live_x = W - 12 - live_w
    live_dot_x = live_x - 8
    host = f"{USER}.github.io"
    slug = name if name.islower() else name
    url_line = f"{host}/{slug}"

    # Widths measured by eye against DejaVu-class metrics; the caption is short
    # by construction so it cannot collide with the metric on the right.
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(name)} live window: {esc(metric)}">
  <defs>
    <clipPath id="view-clip"><rect x="1" y="{BAR}" width="{W - 2}" height="{VIEW}"/></clipPath>
    <linearGradient id="scan-grad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{theme['scan']}" stop-opacity="0"/>
      <stop offset="0.5" stop-color="{theme['scan']}" stop-opacity="0.16"/>
      <stop offset="1" stop-color="{theme['scan']}" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="fade-grad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{theme['bg']}" stop-opacity="0"/>
      <stop offset="1" stop-color="{theme['bg']}" stop-opacity="0.92"/>
    </linearGradient>
    <linearGradient id="bar-grad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{theme['accent']}" stop-opacity="0.55"/>
      <stop offset="1" stop-color="{theme['accent']}" stop-opacity="0.10"/>
    </linearGradient>
    <style>
      @keyframes livePulse {{
        0%, 100% {{ opacity: 1; }}
        50%      {{ opacity: 0.25; }}
      }}
      .live-dot {{ animation: livePulse 1.8s ease-in-out infinite; }}
      .live-dot-b {{ animation: livePulse 1.8s ease-in-out infinite; animation-delay: 0.9s; }}
      @media (prefers-reduced-motion: reduce) {{
        .live-dot, .live-dot-b {{ animation: none; }}
        .scan {{ display: none; }}
      }}
    </style>
  </defs>

  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" fill="{theme['bg']}" stroke="{theme['stroke']}"/>

  <!-- url bar -->
  <path d="M0.5 {BAR} V10.5 a10 10 0 0 1 10-10 H{W - 10.5} a10 10 0 0 1 10 10 V{BAR} Z" fill="{theme['panel']}"/>
  <line x1="0.5" y1="{BAR}" x2="{W - 0.5}" y2="{BAR}" stroke="{theme['stroke']}"/>
  <rect x="10" y="8" width="4" height="9" rx="2" fill="{live_color}"{live_cls}/>
  <rect x="18" y="8" width="4" height="9" rx="2" fill="{theme['muted']}" opacity="0.55"/>
  <rect x="26" y="8" width="4" height="9" rx="2" fill="{theme['muted']}" opacity="0.35"/>
  <rect x="40" y="6.5" width="{W - 96}" height="13" rx="6.5" fill="{theme['bg']}" stroke="{theme['stroke']}"/>
  <rect x="46" y="11" width="3" height="4" rx="1" fill="{theme['accent']}" opacity="0.8"/>
  <text x="54" y="16.5" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="8.5" fill="{theme['muted']}">{esc(url_line)}</text>
  <circle cx="{live_dot_x:.1f}" cy="13" r="2.4" fill="{live_color}"{live_cls_b}/>
  <text x="{W - 12}" y="16.5" text-anchor="end" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="7.5" letter-spacing="0.6" fill="{live_color}" font-weight="bold">{live_label}</text>

  <!-- viewport -->
  <g clip-path="url(#view-clip)">
    <image x="1" y="{BAR}" width="{W - 2}" height="{VIEW}" href="{uri}" preserveAspectRatio="xMidYMin slice"/>
    <g class="scan">
      <rect x="-90" y="{BAR}" width="90" height="{VIEW}" fill="url(#scan-grad)">
        <animate attributeName="x" values="-90;{W}" dur="6.5s" begin="{phase}s" repeatCount="indefinite"/>
      </rect>
    </g>
    <rect x="1" y="{BAR + VIEW - 34}" width="{W - 2}" height="34" fill="url(#fade-grad)"/>
  </g>

  <!-- caption -->
  <line x1="0.5" y1="{BAR + VIEW}" x2="{W - 0.5}" y2="{BAR + VIEW}" stroke="{theme['stroke']}"/>
  <rect x="10" y="{BAR + VIEW + 9}" width="3" height="16" rx="1.5" fill="url(#bar-grad)"/>
  <text x="20" y="{BAR + VIEW + 21}" font-family="ui-sans-serif,-apple-system,Segoe UI,Helvetica,Arial,sans-serif" font-size="12" font-weight="600" fill="{theme['text']}">{esc(name)}</text>
  <text x="{W - 12}" y="{BAR + VIEW + 21}" text-anchor="end" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="9.5" fill="{theme['muted']}">{esc(metric)}</text>
</svg>
"""


def main() -> int:
    wanted = set(sys.argv[1:])
    os.makedirs(OUT, exist_ok=True)
    state = load_state()
    manifest = {"tiles": []}
    for name, metric, phase in TILES:
        if wanted and name not in wanted and name.lower() not in {w.lower() for w in wanted}:
            continue
        info = state.get("sites", {}).get(name, {})
        confirmed = bool(info.get("confirmed_live", True))
        for theme_name in THEMES:
            svg = render(name, metric, phase, theme_name, confirmed)
            path = os.path.join(OUT, f"{name}-{theme_name}.svg")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(svg)
            print(f"{os.path.relpath(path, ROOT):52s} {len(svg):>8} B", file=sys.stderr)
        manifest["tiles"].append(
            {
                "repo": name,
                "metric": metric,
                "phase": phase,
                "captured": info.get("captured"),
                "age_days": info.get("age_days"),
                "confirmed_live": confirmed,
            }
        )

    if not wanted:
        with open(os.path.join(OUT, "tiles.json"), "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
