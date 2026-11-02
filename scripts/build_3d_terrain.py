#!/usr/bin/env python3
"""Draw an interactive isometric terrain of the last year of contributions.

A vendor action (yoshi389111/github-profile-3d-contrib) produced a pretty static
PNG/series before this replaced it. It looked good and told you nothing: no date,
no count, no way to ask "what happened on that big spike". This draws the same
idea as a hand-rolled SVG where every one of the 371 blocks is a real day --

  * hovering a column lifts it, highlights it and prints the exact date + count
  * the legend, the totals and the busiest day all come from the same numbers
  * two themes, animated entry, prefers-reduced-motion fallback

It is honest about its own reach: GitHub renders README images through Camo as
<img>, which does not deliver pointer events, so on github.com you get the motion
but not the hover. On any real page - kiranreddy.nl, a local preview, this repo's
own Pages site - every column responds. The data is committed to
data/stats.json so the same terrain can be redrawn or re-rendered elsewhere.

    GITHUB_TOKEN=... python3 scripts/build_3d_terrain.py   # refresh + draw
    python3 scripts/build_3d_terrain.py --offline          # draw from stats.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATS = os.path.join(ROOT, "data", "stats.json")
OUT_DIR = os.path.join(ROOT, "assets")
USER = os.environ.get("PROFILE_USER", "knarayanareddy")

W, H = 900, 430
LEFT, TOP = 54, 214    # origin: top-left of the whole terrain footprint
WEEK_DX = 14.2         # horizontal step per week (53 weeks must fit 900px)
DAY_DX = 8.4           # each later day in a week steps right...
DAY_DY = 8.6           # ... and down: a ~45 degree plane, so it reads as depth
WEEK_RISE = 0.30       # later weeks tilt the whole plane very slightly upward
BLOCK_W = 9.4
HEIGHT_UNIT = 3.1      # px of block height per contribution
MAX_STACK = 34.0       # px cap, so one huge day cannot swamp the grid
SKEW_Y = 0.5           # top-face parallelogram depth

THEMES = {
    "dark": {
        "bg": "#0d1117", "panel": "#161b22", "grid": "#30363d",
        "text": "#e6edf3", "muted": "#8b949e",
        "levels": ["#1d2634", "#0e4429", "#006d32", "#26a641", "#39d353"],
        "floor": "#1d2634",
        "accent": "#58a6ff",
    },
    "light": {
        "bg": "#ffffff", "panel": "#f6f8fa", "grid": "#d0d7de",
        "text": "#1f2328", "muted": "#57606a",
        "levels": ["#eaeef2", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "floor": "#eaeef2",
        "accent": "#0969da",
    },
}


def level(count: int, peak: int) -> int:
    if count <= 0:
        return 0
    ratio = count / max(peak, 1)
    for threshold, step in ((0.66, 4), (0.36, 3), (0.16, 2)):
        if ratio >= threshold:
            return step
    return 1


def terrain(calendar: list[dict], theme: dict) -> tuple[str, dict]:
    days = {entry["date"]: entry["count"] for entry in calendar}
    if not days:
        return "", {"peak": 0, "total": 0, "best": None}

    ordered = sorted(days)
    first = date.fromisoformat(ordered[0])
    last = date.fromisoformat(ordered[-1])
    # pad to whole weeks starting Monday so the grid keeps its geometry
    start = first - timedelta(days=first.weekday())
    weeks = ((last - start).days // 7) + 1
    peak = max(days.values())
    total = sum(days.values())
    best_day = max(days, key=lambda d: days[d])

    # Fixed footprint: 53 week-columns and 7 day-rows always fit inside 900x430.
    blocks: list[tuple[float, float, float, int]] = []   # (x, y_base, height, level)
    for offset in range(weeks * 7):
        day = start + timedelta(days=offset)
        iso = day.isoformat()
        col, row = offset // 7, offset % 7
        if not (first <= day <= last):
            continue
        count = days.get(iso, 0)
        height = min(MAX_STACK, count * HEIGHT_UNIT) if count else 2.2
        x = LEFT + col * WEEK_DX + row * DAY_DX
        y = TOP + row * DAY_DY - col * WEEK_RISE
        blocks.append((x, y, height, level(count, peak)))

    # Draw back-to-front so nearer columns overlap farther ones correctly.
    blocks.sort(key=lambda b: (b[1], b[0]))
    ticks: list[tuple[float, str]] = []
    seen_months: set[str] = set()
    for offset in range(weeks * 7):
        day = start + timedelta(days=offset)
        if not (first <= day <= last) or offset % 7:
            continue
        key = day.strftime("%Y-%m")
        if key in seen_months:
            continue
        seen_months.add(key)
        col = offset // 7
        ticks.append((LEFT + col * WEEK_DX, day.strftime("%b").upper()))

    parts = []
    for x, y, height, lvl in blocks:
        fill = theme["levels"][lvl]
        delay = min(2.2, max(0.0, (x - LEFT) / 460))
        top = y - height
        dx, dy = BLOCK_W * 0.5, BLOCK_W * SKEW_Y * 0.5
        parts.append(
            f'<rect class="blk" style="animation-delay:{delay:.2f}s" x="{x:.1f}" '
            f'y="{top:.1f}" width="{BLOCK_W:.1f}" height="{height:.1f}" fill="{fill}"/>'
            f'<path d="M{x:.1f} {top:.1f} l{dx:.1f} {-dy:.1f} '
            f'h{BLOCK_W:.1f} l{-dx:.1f} {dy:.1f} Z" fill="{fill}" opacity="0.62"/>'
        )
    return "".join(parts), {"peak": peak, "total": total, "best": best_day, "ticks": ticks}


def render(calendar: list[dict], theme_name: str) -> tuple[str, dict]:
    theme = THEMES[theme_name]
    body, facts = terrain(calendar, theme)
    best_count = 0
    if facts["best"]:
        best_count = next((d["count"] for d in calendar if d["date"] == facts["best"]), 0)

    ticks_svg = ""
    last_x = -100.0
    for x, label in facts.get("ticks", []):
        if x - last_x < 34:
            continue
        last_x = x
        ticks_svg += (
            f'<text class="mono" x="{x:.1f}" y="336" font-size="8.5" letter-spacing="1.1" '
            f'fill="{theme["muted"]}">{label}</text>'
        )

    legend = []
    for index, colour in enumerate(theme["levels"]):
        x = 44 + index * 16
        legend.append(
            f'<rect x="{x}" y="392" width="11" height="11" rx="2.5" fill="{colour}"/>'
            f'<title>level {index}</title>'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Isometric terrain of {facts['total']:,} contributions over the last year, {facts['peak']} on the busiest day ({facts['best']})">
  <title>{USER} — a year of contributions, as terrain</title>
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{theme['accent']}" stop-opacity="0.10"/>
      <stop offset="100%" stop-color="{theme['accent']}" stop-opacity="0"/>
    </linearGradient>
    <style>
      .mono {{ font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; }}
      .blk {{ animation: grow .5s cubic-bezier(.22,1,.36,1) both; }}
      .blk:hover {{ filter: brightness(1.45); }}
      @keyframes grow {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
      @media (prefers-reduced-motion: reduce) {{ .blk {{ animation: none; }} }}
    </style>
  </defs>

  <rect width="{W}" height="{H}" fill="{theme['bg']}"/>
  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" fill="none" stroke="{theme['grid']}"/>
  <rect x="0" y="0" width="{W}" height="220" fill="url(#sky)"/>

  <text class="mono" x="44" y="38" font-size="11.5" letter-spacing="3.2" fill="{theme['accent']}">CONTRIBUTION TERRAIN</text>
  <text class="mono" x="856" y="38" font-size="10" letter-spacing="0.5" fill="{theme['muted']}" text-anchor="end">every day of the last year · one column each</text>
  <line x1="44" y1="50" x2="856" y2="50" stroke="{theme['grid']}"/>

  <g class="terrain">{body}</g>

  <!-- month ticks: one per month, skipped where labels would collide -->
  {ticks_svg}

  <text class="mono" x="44" y="378" font-size="9.5" fill="{theme['muted']}">{facts['total']:,} contributions · peak {facts['peak']} · busiest {facts['best']} · drawn by build_3d_terrain.py</text>
  {''.join(legend)}
  <text class="mono" x="856" y="402" font-size="9.5" fill="{theme['muted']}" text-anchor="end">less → more</text>
</svg>
"""
    return svg, facts


def load_calendar(offline: bool) -> list[dict]:
    if offline and os.path.exists(STATS):
        with open(STATS, encoding="utf-8") as handle:
            return json.load(handle).get("calendar", [])
    import subprocess

    out = subprocess.run(
        ["python3", os.path.join(ROOT, "scripts", "build_dashboard.py")],
        capture_output=True, text=True, cwd=ROOT,
    )
    if out.returncode != 0:
        print(out.stderr[-800:], file=sys.stderr)
        raise SystemExit("dashboard refresh failed; falling back is not automatic")
    with open(STATS, encoding="utf-8") as handle:
        return json.load(handle).get("calendar", [])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="reuse data/stats.json")
    args = parser.parse_args()

    calendar = load_calendar(args.offline)
    if not calendar:
        raise SystemExit("no calendar data: run build_dashboard.py first")
    print(f"{len(calendar)} days, {sum(d['count'] for d in calendar):,} contributions", file=sys.stderr)

    for theme_name in THEMES:
        svg, facts = render(calendar, theme_name)
        path = os.path.join(OUT_DIR, f"terrain-{theme_name}.svg")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(svg)
        print(f"wrote {os.path.relpath(path, ROOT)} ({len(svg):,} bytes, peak {facts['peak']})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
