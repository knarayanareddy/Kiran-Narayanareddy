#!/usr/bin/env python3
"""Render the social badges and tech-stack strip as self-hosted SVG.

shields.io was the last third-party host in the profile, across ~70 image
references. If it is slow or down, the Live Sites table collapses into broken
image icons and the tech-stack section turns into a wall of missing glyphs.

This script draws those same chips ourselves, from the same data the rest of the
profile uses, so:
  - no external requests per profile view
  - star counts are never stale behind GitHub's image proxy (Camo) cache
  - one artefact, light and dark variants, works when shields.io does not

Text is laid out with approximate per-character advances (the same approach as
build_hero.py) because SVG has no text measurement. Chips are right-padded
generously so long labels never overflow.

Usage:
    python3 scripts/build_badges.py
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "sites.json")
OUT_DIR = os.path.join(ROOT, "assets")

THEMES = {
    "dark": {
        "bg": "#0d1117", "chip": "#1a1b27", "text": "#e6edf3", "muted": "#8b949e",
        "edge": "#30363d", "accent": "#58a6ff",
    },
    "light": {
        "bg": "#ffffff", "chip": "#eef1f4", "text": "#0d1117", "muted": "#57606a",
        "edge": "#d0d7de", "accent": "#0969da",
    },
}

# --------------------------------------------------------------------------- #
# content
# --------------------------------------------------------------------------- #
# Social row: (label, icon glyph, accent colour, href)
# No glyphs: exotic icon characters depend on the viewer's font and render as
# tofu or stray dots. A clean typographic chip is more reliable.
SOCIAL = [
    ("Followers", None, "#58a6ff", "https://github.com/knarayanareddy?tab=followers"),
    ("Total Stars", None, "#e3b341", "https://github.com/knarayanareddy?tab=repositories"),
    ("Repositories", None, "#8b949e", "https://github.com/knarayanareddy?tab=repositories"),
    ("Forks", None, "#a371f7", "https://github.com/knarayanareddy?tab=repositories"),
    ("Live Sites", None, "#3fb950", "https://github.com/knarayanareddy?tab=repositories&q=&type=source"),
    ("LinkedIn", None, "#0a66c2", "https://www.linkedin.com/in/knarayanareddy/"),
    ("Follow", None, "#f0883e", "https://github.com/knarayanareddy.atom"),
]

TECH = [
    ("Languages", [
        ("TypeScript", "#3178c6"), ("Python", "#3776ab"), ("JavaScript", "#f7df1e"),
        ("Rust", "#ce422b"), ("Go", "#00add8"), ("Kotlin", "#7f52ff"),
    ]),
    ("AI & Agents", [
        ("Claude", "#d97757"), ("Codex / OpenAI", "#412991"), ("LangChain", "#1c3c3c"),
        ("MCP Servers", "#2b3137"), ("PyTorch", "#ee4c2c"),
    ]),
    ("Web, Data & Infra", [
        ("React", "#61dafb"), ("Three.js", "#4b5563"), ("Vite", "#646cff"),
        ("FastAPI", "#009688"), ("Docker", "#2496ed"), ("Actions", "#2088ff"),
    ]),
    ("Domain", [
        ("Su2 / CFD", "#1f6feb"), ("Solana", "#9945ff"), ("OpenCV", "#5c3ee8"),
    ]),
]

# Approximate advance widths in em, scaled by font size.
NARROW = set("iljtfrI.,:;'|!()[]")
WIDE = set("mwMW@")


def text_width(text: str, size: float, weight: str = "normal") -> float:
    total = 0.0
    for char in text:
        if char in NARROW:
            advance = 0.34
        elif char in WIDE:
            advance = 0.86
        elif char.isupper():
            advance = 0.66
        elif char == " ":
            advance = 0.30
        else:
            advance = 0.54
        total += advance
    if weight == "bold":
        # SVG has no text measurement; err generous so labels never touch the edge
        total *= 1.11
    return total * size


def esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #
def chip(x: float, y: float, label: str, value: str | None, color: str,
         theme: dict, height: float = 30, glyph: str | None = None) -> tuple[str, float]:
    """A shields-style chip: coloured label block, then an optional value block."""
    size = 12.0
    pad = 11.0
    gap = 5.0

    glyph_w = (text_width(glyph, size, "bold") + gap) if glyph else 0.0
    label_w = text_width(label, size, "bold")
    left = pad + glyph_w + label_w + pad
    value_w = (pad + text_width(value, size, "bold") + pad) if value else 0.0
    total = left + value_w
    radius = height / 2
    mid = y + height / 2 + 4.1

    parts = [
        f'<g><title>{esc(label)}{" " + esc(value) if value else ""}</title>',
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{total:.1f}" height="{height}" '
        f'rx="{radius}" fill="{theme["chip"]}" stroke="{theme["edge"]}" stroke-width="1"/>',
        # accent block, rounded only on the left; squared where the value begins
        f'<path d="M{x + radius:.1f} {y:.1f} h{left - radius:.1f} v{height} '
        f'h{-(left - radius):.1f} a{radius} {radius} 0 0 1 0 {-height} z" fill="{color}"/>',
    ]
    if glyph:
        parts.append(
            f'<text x="{x + pad:.1f}" y="{mid:.1f}" font-size="{size}" '
            f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-weight="700" '
            f'fill="{theme["bg"]}" opacity="0.95">{esc(glyph)}</text>'
        )
    parts.append(
        f'<text x="{x + pad + glyph_w:.1f}" y="{mid:.1f}" font-size="{size}" font-weight="700" '
        f'font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Inter, Helvetica, Arial, sans-serif" '
        f'fill="{theme["bg"]}">{esc(label)}</text>'
    )
    if value:
        parts.append(
            f'<text x="{x + left + value_w / 2:.1f}" y="{mid:.1f}" text-anchor="middle" '
            f'font-size="{size}" font-weight="700" '
            f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
            f'fill="{theme["text"]}">{esc(value)}</text>'
        )
    parts.append("</g>")
    return "".join(parts), total


def tech_chip(x: float, y: float, label: str, color: str, theme: dict) -> tuple[str, float]:
    """A small dot + label pill, one per technology."""
    size = 11.5
    pad = 10.0
    dot = 11.0
    width = pad * 2 + dot + 6 + text_width(label, size, "bold")
    height = 24.0
    return (
        f'<g><title>{esc(label)}</title>'
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height}" rx="{height / 2}" '
        f'fill="{theme["chip"]}" stroke="{theme["edge"]}" stroke-width="1"/>'
        f'<circle cx="{x + pad + dot / 2:.1f}" cy="{y + height / 2:.1f}" r="4.2" fill="{color}"/>'
        f'<text x="{x + pad + dot + 6:.1f}" y="{y + height / 2 + 4:.1f}" font-size="{size}" '
        f'font-weight="600" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Inter, Helvetica, Arial, sans-serif" '
        f'fill="{theme["text"]}">{esc(label)}</text></g>'
    ), width


def render(social_values: dict, theme_name: str) -> str:
    theme = THEMES[theme_name]
    GAP = 8.0
    PAD = 2.0

    # --- social row ---
    social_svg = []
    x = PAD
    max_x = 0.0
    for label, glyph, colour, href in SOCIAL:
        value = social_values.get(label)
        piece, width = chip(x, PAD, label, value, colour, theme, height=32, glyph=glyph)
        social_svg.append(f'<a href="{esc(href)}">{piece}</a>')
        x += width + GAP
        max_x = max(max_x, x)
    social_h = 32 + PAD

    # --- tech stack grid ---
    tech_svg = []
    y = social_h + 22
    rows: list[tuple[str, list[tuple[str, str]]]] = TECH
    for group_name, items in rows:
        tech_svg.append(
            f'<text x="{PAD}" y="{y:.1f}" font-size="10" letter-spacing="1.6" '
            f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
            f'fill="{theme["muted"]}">{esc(group_name.upper())}</text>'
        )
        y += 12
        cx = PAD
        for label, colour in items:
            piece, width = tech_chip(cx, y, label, colour, theme)
            tech_svg.append(piece)
            cx += width + 7
            max_x = max(max_x, cx)
        y += 24 + 13

    width = max(max_x + PAD, 320)
    height = y - 6

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" role="img" '
        f'aria-label="Kiran Narayanareddy — badges and technology stack">\n'
        f'  <title>Kiran Narayanareddy — badges and technology stack</title>\n'
        f'  <defs><style>\n'
        f'    .fade {{ animation: fade .7s ease-out both; }}\n'
        f'    @keyframes fade {{ from {{ opacity: 0; transform: translateY(4px); }} '
        f'to {{ opacity: 1; transform: translateY(0); }} }}\n'
        f'    @media (prefers-reduced-motion: reduce) {{ .fade {{ animation: none; }} }}\n'
        f'  </style></defs>\n'

        f'  <g class="fade">\n    ' + "\n    ".join(social_svg) + "\n  </g>\n"
        f'  <g class="fade" style="animation-delay:.25s">\n    '
        + "\n    ".join(tech_svg) + "\n  </g>\n"
        "</svg>\n"
    )


def main() -> int:
    if not os.path.exists(DATA):
        print(f"error: {DATA} is missing; run build_profile.py first", file=sys.stderr)
        return 1
    with open(DATA, encoding="utf-8") as handle:
        data = json.load(handle)

    social_values = {
        "Followers": str(data.get("followers", 0)) if data.get("followers") else None,
        "Total Stars": str(data.get("stars", 0)),
        "Repositories": str(data.get("repos", 0)),
        "Forks": str(data.get("forks", 0)),
        "Live Sites": str(data.get("site_count", 0)),
        "LinkedIn": None,
        "Follow": "RSS",
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    for theme_name in THEMES:
        svg = render(social_values, theme_name)
        path = os.path.join(OUT_DIR, f"badges-{theme_name}.svg")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(svg)
        print(f"wrote {os.path.relpath(path, ROOT)} ({len(svg):,} bytes)", file=sys.stderr)

    # Validate: <a href> links are fine (they are navigation, not fetches). What
    # must not appear is anything the renderer would fetch: <image href>, <use>,
    # url(...) or a src attribute.
    import re

    forbidden = re.compile(r'(<image\b|<use\b|\bsrc\s*=|url\((?!"?#))', re.IGNORECASE)
    for theme_name in THEMES:
        body = open(os.path.join(OUT_DIR, f"badges-{theme_name}.svg"), encoding="utf-8").read()
        if forbidden.search(body):
            print(f"error: fetchable external reference in badges-{theme_name}.svg",
                  file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
