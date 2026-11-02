#!/usr/bin/env python3
"""Generate a self-hosted, animated profile hero as SVG.

Why this exists: every visual in the profile used to come from someone else's
server (capsule-render, readme-typing-svg, github-readme-stats, komarev...).
Those break, rate-limit, and make the profile look like a template. This script
renders our own hero from real data, so the profile costs zero requests per view
and looks like nobody else's.

GitHub strips <script>, <style>, <iframe> and <video> from README markdown, but an
SVG loaded through <img src="..."> keeps its internal CSS @keyframes and SMIL
animations and runs under a strict CSP (default-src 'none'). So:
  - no external fonts, images or fetches: system font stacks only
  - animation is pure SMIL + inline CSS keyframes
  - a static fallback is shown when prefers-reduced-motion: reduce is set

Usage:
    python3 scripts/build_hero.py            # writes assets/hero-{dark,light}.svg
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "sites.json")
OUT_DIR = os.path.join(ROOT, "assets")

NAME = "KIRAN NARAYANAREDDY"

TAGLINES = [
    "autonomous agents that can prove their work",
    "aerospace research pipelines with evidence chains",
    "compliance-as-code for EU regulated products",
]

THEMES = {
    "dark": {
        "bg": "#0d1117",
        "panel": "#161b22",
        "grid": "#1f2937",
        "text": "#e6edf3",
        "muted": "#8b949e",
        "accent": "#58a6ff",
        "accent2": "#a371f7",
        "accent3": "#3fb950",
        "glow": "#58a6ff",
    },
    "light": {
        "bg": "#ffffff",
        "panel": "#f6f8fa",
        "grid": "#e2e8f0",
        "text": "#0d1117",
        "muted": "#57606a",
        "accent": "#0969da",
        "accent2": "#8250df",
        "accent3": "#1a7f37",
        "glow": "#0969da",
    },
}

TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="900" height="300" viewBox="0 0 900 300" role="img" aria-label="__ARIA__">
  <title>__ARIA__</title>
  <defs>
    <linearGradient id="nameGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="__ACCENT__"/>
      <stop offset="52%" stop-color="__ACCENT2__"/>
      <stop offset="100%" stop-color="__ACCENT3__"/>
      <animate attributeName="x1" values="-0.3;1.1;-0.3" dur="14s" repeatCount="indefinite"/>
      <animate attributeName="x2" values="0.4;1.6;0.4" dur="14s" repeatCount="indefinite"/>
    </linearGradient>
    <radialGradient id="auroraA" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="__ACCENT__" stop-opacity="0.42"/>
      <stop offset="100%" stop-color="__ACCENT__" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="auroraB" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="__ACCENT2__" stop-opacity="0.38"/>
      <stop offset="100%" stop-color="__ACCENT2__" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="auroraC" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="__ACCENT3__" stop-opacity="0.26"/>
      <stop offset="100%" stop-color="__ACCENT3__" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="__ACCENT__" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="__ACCENT2__" stop-opacity="0.15"/>
    </linearGradient>
    <linearGradient id="fadeRight" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="__BG__" stop-opacity="0"/>
      <stop offset="100%" stop-color="__BG__" stop-opacity="1"/>
    </linearGradient>
    <clipPath id="clipA"><rect x="48" y="118" width="0" height="26"><animate attributeName="width" values="0;340;340;0" keyTimes="0;0.14;0.30;0.34" dur="12s" begin="0s" repeatCount="indefinite" calcMode="spline" keySplines="0.4 0 0.2 1;0.4 0 0.2 1;0.4 0 0.2 1"/></rect></clipPath>
    <clipPath id="clipB"><rect x="48" y="118" width="0" height="26"><animate attributeName="width" values="0;360;360;0" keyTimes="0;0.14;0.30;0.34" dur="12s" begin="4s" repeatCount="indefinite"/></rect></clipPath>
    <clipPath id="clipC"><rect x="48" y="118" width="0" height="26"><animate attributeName="width" values="0;350;350;0" keyTimes="0;0.14;0.30;0.34" dur="12s" begin="8s" repeatCount="indefinite"/></rect></clipPath>
    <style>
      .mono { font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace; }
      .sans { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Helvetica, Arial, sans-serif; }
      /* Base styles are the FINISHED state on purpose: a renderer that ignores
         CSS animation (static previewers, crawlers) must still show the name. */
      .letter { opacity: 1; animation: rise 0.9s cubic-bezier(.22,1,.36,1) both; }
      .bar { transform-origin: left center; animation: grow 1.6s cubic-bezier(.22,1,.36,1) both; }
      @keyframes rise { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: translateY(0); } }
      @keyframes grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
      @keyframes drift { 0% { transform: translate(0,0) scale(1); } 50% { transform: translate(18px,-12px) scale(1.06); } 100% { transform: translate(0,0) scale(1); } }
      .aurora { animation: drift 18s ease-in-out infinite; }
      .aurora-slow { animation: drift 26s ease-in-out infinite reverse; }
      @keyframes gridpan { from { transform: translateX(0); } to { transform: translateX(-40px); } }
      .gridpan { animation: gridpan 9s linear infinite; }
      .static { display: none; }
      @media (prefers-reduced-motion: reduce) {
        .anim { display: none; }
        .static { display: inline; }
        .letter { opacity: 1 !important; animation: none; }
        .bar { transform: scaleX(1) !important; animation: none; }
        .aurora, .aurora-slow, .gridpan { animation: none; }
      }
    </style>
  </defs>

  <!-- card: full bleed, so no page-coloured slivers at the corners -->
  <rect x="0" y="0" width="900" height="300" fill="__BG__"/>
  <rect x="0.5" y="0.5" width="899" height="299" fill="none" stroke="__GRID__" stroke-width="1"/>

  <!-- aurora -->
  <g class="anim">
    <ellipse class="aurora" cx="150" cy="70" rx="230" ry="150" fill="url(#auroraA)"/>
    <ellipse class="aurora-slow" cx="640" cy="250" rx="260" ry="160" fill="url(#auroraB)"/>
    <ellipse class="aurora" cx="820" cy="60" rx="180" ry="120" fill="url(#auroraC)"/>
  </g>

  <!-- perspective grid floor -->
  <g class="anim" opacity="0.55">
    <line x1="0" y1="237" x2="900" y2="237" stroke="__ACCENT__" stroke-width="1" opacity="0.35"/>
    <g class="gridpan">
__GRID_LINES__
    </g>
    <rect x="0" y="296" width="900" height="4" fill="__BG__"/>
  </g>

  <!-- name: staggered per-letter reveal -->
  <g class="sans" font-size="__NAME_SIZE__" font-weight="700" fill="url(#nameGrad)">
__NAME_LETTERS__
  </g>

  <!-- rotating tagline: each line is visible by default (opacity 1) and the SMIL
       animation cycles them; a static render therefore still shows a full line -->
  <g class="mono" font-size="14.5" fill="__MUTED__" letter-spacing="0.3">
    <text x="63" y="137" class="anim">__LINE_A__
      <animate attributeName="opacity" values="1;1;0;0;0;0" keyTimes="0;0.30;0.34;0.63;0.67;1" dur="24s" repeatCount="indefinite"/>
    </text>
    <text x="63" y="137" class="anim" opacity="0">__LINE_B__
      <animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="0;0.32;0.36;0.63;0.67;1" dur="24s" repeatCount="indefinite"/>
    </text>
    <text x="63" y="137" class="anim" opacity="0">__LINE_C__
      <animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="0;0.65;0.69;0.96;1;1" dur="24s" repeatCount="indefinite"/>
    </text>
    <text x="63" y="137" class="static">__LINE_A__</text>
    <rect x="48" y="125" width="8" height="15" fill="__ACCENT__" opacity="0.85" class="anim">
      <animate attributeName="opacity" values="1;1;0;0;1" keyTimes="0;0.45;0.5;0.95;1" dur="1.1s" repeatCount="indefinite"/>
    </rect>
  </g>

  <!-- stat chips -->
__STAT_CHIPS__

  <!-- the harness glyph: rings, orbiting nodes, signal pulses -->
  <g transform="translate(748,152)" class="anim">
    <circle r="112" fill="none" stroke="__GRID__" stroke-width="1" opacity="0.5"/>
    <g>
      <animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="60s" repeatCount="indefinite"/>
      <circle r="96" fill="none" stroke="__GRID__" stroke-width="1" stroke-dasharray="2 10" opacity="0.9"/>
    </g>
    <!-- two counter-rotating gradient arcs, drawn as circles with a dash offset -->
    <g>
      <animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="16s" repeatCount="indefinite"/>
      <circle r="78" fill="none" stroke="__ACCENT__" stroke-width="1.6" stroke-linecap="round"
              stroke-dasharray="150 340" opacity="0.85"/>
      <circle cx="78" cy="0" r="3.4" fill="__ACCENT__"/>
    </g>
    <g>
      <animateTransform attributeName="transform" type="rotate" from="360" to="0" dur="10s" repeatCount="indefinite"/>
      <circle r="56" fill="none" stroke="__ACCENT2__" stroke-width="1.5" stroke-linecap="round"
              stroke-dasharray="90 262" opacity="0.85"/>
      <circle cx="56" cy="0" r="2.8" fill="__ACCENT2__"/>
    </g>
    <g>
      <animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="22s" repeatCount="indefinite"/>
      <circle r="34" fill="none" stroke="__ACCENT3__" stroke-width="1.2" stroke-dasharray="40 174"
              stroke-linecap="round" opacity="0.8"/>
      <circle cx="0" cy="-34" r="2.2" fill="__ACCENT3__"/>
    </g>
    <!-- core -->
    <circle r="12" fill="__ACCENT__" opacity="0.95"/>
    <circle r="12" fill="none" stroke="__ACCENT__" stroke-width="1.4" opacity="0.5">
      <animate attributeName="r" values="12;30" dur="2.8s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0.5;0" dur="2.8s" repeatCount="indefinite"/>
    </circle>
    <circle r="3" fill="__BG__" opacity="0.85"/>
    <!-- signal pulses -->
    <circle r="2" fill="__ACCENT__" opacity="0">
      <animate attributeName="r" values="14;96" dur="4.2s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0.75;0" dur="4.2s" repeatCount="indefinite"/>
    </circle>
    <circle r="2" fill="__ACCENT2__" opacity="0">
      <animate attributeName="r" values="14;96" dur="4.2s" begin="1.4s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0.75;0" dur="4.2s" begin="1.4s" repeatCount="indefinite"/>
    </circle>
    <circle r="2" fill="__ACCENT3__" opacity="0">
      <animate attributeName="r" values="14;96" dur="4.2s" begin="2.8s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0.75;0" dur="4.2s" begin="2.8s" repeatCount="indefinite"/>
    </circle>
  </g>
</svg>
"""


FOOTER_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="900" height="110" viewBox="0 0 900 110" role="img" aria-label="Kiran Narayanareddy, Amsterdam">
  <title>Kiran Narayanareddy, Amsterdam</title>
  <defs>
    <linearGradient id="wave" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="__ACCENT__" stop-opacity="0.55"/>
      <stop offset="50%" stop-color="__ACCENT2__" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="__ACCENT3__" stop-opacity="0.55"/>
      <animate attributeName="x1" values="-0.2;1;-0.2" dur="18s" repeatCount="indefinite"/>
    </linearGradient>
    <style>
      .sans { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Helvetica, Arial, sans-serif; }
      .mono { font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; }
      @keyframes drift { from { transform: translateX(0); } to { transform: translateX(-60px); } }
      .drift { animation: drift 14s linear infinite; }
      @media (prefers-reduced-motion: reduce) { .drift { animation: none; } }
    </style>
  </defs>
  <rect width="900" height="110" fill="none"/>
  <g class="drift" opacity="0.85">
    <path d="M-60 78 C 60 52, 180 98, 300 78 S 540 52, 660 78 S 840 98, 960 78 L 960 110 L -60 110 Z" fill="url(#wave)"/>
    <path d="M-60 88 C 80 66, 200 104, 320 88 S 560 66, 680 88 S 860 104, 960 88 L 960 110 L -60 110 Z" fill="url(#wave)" opacity="0.6"/>
  </g>
  <text class="sans" x="450" y="42" text-anchor="middle" font-size="14" font-weight="700" fill="__TEXT__">Kiran Narayanareddy</text>
  <text class="mono" x="450" y="60" text-anchor="middle" font-size="9.5" letter-spacing="2.4" fill="__MUTED__">AMSTERDAM · AUTONOMOUS AGENTS · AEROSPACE · COMPLIANCE-AS-CODE</text>
</svg>
"""


def render_footer(theme_name: str) -> str:
    theme = THEMES[theme_name]
    svg = FOOTER_TEMPLATE
    for key, value in theme.items():
        svg = svg.replace(f"__{key.upper()}__", value)
    return svg


def load_stats() -> dict:
    """Prefer the committed snapshot so a build is fast and deterministic."""
    if os.path.exists(DATA):
        with open(DATA, encoding="utf-8") as handle:
            return json.load(handle)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from build_profile import collect  # type: ignore

    return collect()


def grid_lines(theme: dict) -> str:
    """A perspective-ish grid: tighter spacing and lower opacity as it recedes."""
    parts = []
    for index, y in enumerate(range(238, 306, 10)):
        opacity = 0.22 + index * 0.11
        parts.append(
            f'    <line x1="-40" y1="{y}" x2="940" y2="{y}" stroke="{theme["grid"]}" '
            f'stroke-width="1" opacity="{opacity:.2f}"/>'
        )
    for x in range(-40, 960, 40):
        parts.append(
            f'    <line x1="{x}" y1="238" x2="{x + (x - 450) * 0.16:.0f}" y2="306" '
            f'stroke="{theme["accent"]}" stroke-width="1" opacity="0.28"/>'
        )
    return "\n".join(parts)


# Helvetica/Arial Bold advance widths in em, so per-letter placement is accurate.
GLYPH_EM = {
    "A": 0.722, "B": 0.722, "C": 0.722, "D": 0.722, "E": 0.667, "F": 0.611,
    "G": 0.778, "H": 0.722, "I": 0.278, "J": 0.556, "K": 0.722, "L": 0.611,
    "M": 0.889, "N": 0.722, "O": 0.778, "P": 0.667, "Q": 0.778, "R": 0.722,
    "S": 0.667, "T": 0.611, "U": 0.722, "V": 0.722, "W": 0.944, "X": 0.667,
    "Y": 0.667, "Z": 0.611, " ": 0.3,
}

NAME_SIZE = 34
NAME_TRACKING = 1.4  # extra px between glyphs


def name_letters() -> str:
    """Per-letter reveal with real advances, so the wordmark keeps its rhythm."""
    parts = []
    x = 48.0
    for index, char in enumerate(NAME):
        advance = GLYPH_EM.get(char, 0.62) * NAME_SIZE
        if char != " ":
            delay = 0.05 * index + 0.1
            parts.append(
                f'    <text x="{x:.1f}" y="94" class="letter" '
                f'style="animation-delay:{delay:.2f}s">{char}</text>'
            )
        x += advance + NAME_TRACKING
    return "\n".join(parts)


def stat_chips(stats: dict, theme: dict) -> str:
    chips = [
        (str(stats.get("site_count", 0)), "live deployments"),
        (str(stats.get("pages_count", 0)), "pages sites"),
        (str(stats.get("repos", 0)), "repositories"),
        (str(stats.get("stars", 0)), "stars"),
    ]
    parts = []
    x = 48.0
    for index, (value, label) in enumerate(chips):
        width = 30 + len(label) * 6.4
        parts.append(
            f'  <g class="bar" style="animation-delay:{0.9 + index * 0.14:.2f}s">\n'
            f'    <rect x="{x:.0f}" y="176" width="{width:.0f}" height="46" rx="9" '
            f'fill="{theme["panel"]}" stroke="{theme["grid"]}" stroke-width="1"/>\n'
            f'    <text class="mono" x="{x + 12:.0f}" y="197" font-size="16" font-weight="700" '
            f'fill="{theme["accent"]}">{value}</text>\n'
            f'    <text class="mono" x="{x + 12:.0f}" y="213" font-size="10.5" '
            f'fill="{theme["muted"]}" letter-spacing="0.4">{label}</text>\n'
            f"  </g>"
        )
        x += width + 12
    return "\n".join(parts)


def render(theme_name: str, stats: dict) -> str:
    theme = THEMES[theme_name]
    aria = (
        f"{NAME.title()} — autonomous agents, aerospace research and compliance-as-code. "
        f"{stats.get('site_count', 0)} live deployments across {stats.get('repos', 0)} repositories."
    )
    svg = TEMPLATE
    for key, value in theme.items():
        svg = svg.replace(f"__{key.upper()}__", value)
    replacements = {
        "__ARIA__": aria,
        "__GRID_LINES__": grid_lines(theme),
        "__NAME_LETTERS__": name_letters(),
        "__STAT_CHIPS__": stat_chips(stats, theme),
        "__NAME_SIZE__": str(NAME_SIZE),
        "__LINE_A__": TAGLINES[0],
        "__LINE_B__": TAGLINES[1],
        "__LINE_C__": TAGLINES[2],
    }
    for key, value in replacements.items():
        svg = svg.replace(key, value)
    return svg


def main() -> int:
    stats = load_stats()
    os.makedirs(OUT_DIR, exist_ok=True)
    for theme_name in THEMES:
        path = os.path.join(OUT_DIR, f"hero-{theme_name}.svg")
        svg = render(theme_name, stats)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(svg)
        print(f"wrote {os.path.relpath(path, ROOT)} ({len(svg):,} bytes)", file=sys.stderr)

        footer = render_footer(theme_name)
        fpath = os.path.join(OUT_DIR, f"footer-{theme_name}.svg")
        with open(fpath, "w", encoding="utf-8") as handle:
            handle.write(footer)
        print(f"wrote {os.path.relpath(fpath, ROOT)} ({len(footer):,} bytes)", file=sys.stderr)

    leftover = [
        token
        for token in ("__BG__", "__ACCENT__", "__GRID_LINES__", "__NAME_LETTERS__", "__LINE_A__")
        if token in open(os.path.join(OUT_DIR, "hero-dark.svg"), encoding="utf-8").read()
    ]
    if leftover:
        print(f"error: unresolved template tokens: {leftover}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
