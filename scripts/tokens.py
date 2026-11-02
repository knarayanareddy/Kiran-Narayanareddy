#!/usr/bin/env python3
"""One design system for every generated artefact.

The profile is drawn by seven separate generators (hero, footer, badges,
dashboard, terrain, tiles, mosaic). Each one grew its own palette, its own font
stack and its own idea of a margin, so the parts never quite looked like one
design:

    hero grid on dark      #1f2937
    dashboard grid on dark #30363d     <- same role, different colour
    terrain body text      #1f2328
    dashboard body text    #0d1117     <- same role, different colour
    four different mono font stacks, six near-identical font sizes

This module is the single source of truth for colour, type, spacing and canvas
geometry. Generators import it instead of carrying a THEMES dict, so a change
here moves every card at once and they cannot drift apart again.

It is also emitted as data/tokens.json, which web/ reads. That gives the browser
pages the same tokens without a build step, and gives tests something to assert
against.

    python3 scripts/tokens.py            # explain the palette
    python3 scripts/tokens.py --emit     # refresh data/tokens.json
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMIT = os.path.join(ROOT, "data", "tokens.json")

# ---------------------------------------------------------------- palette ---
#
# One hue per job, two values (dark surface, light surface). Anything that is a
# *role* - surface, border, body text - gets its own entry rather than being
# reused from a neighbour, so a card can never quietly borrow the wrong colour.

PALETTE = {
    "dark": {
        "canvas": "#0d1117",     # page background behind a card
        "surface": "#161b22",    # raised panel (chips, cards, tiles)
        "surfaceAlt": "#1a1b27",  # badge pill, one step away from surface
        "border": "#30363d",     # card edges, axis lines
        "borderSoft": "#1f2937",  # decorative grid lines only
        "text": "#e6edf3",
        "muted": "#8b949e",
        "accent": "#58a6ff",
        "accent2": "#a371f7",
        "accent3": "#3fb950",
        "warn": "#f0883e",
        "live": "#f85149",
        "scan": "#ffffff",
        "shadow": "#000000",
    },
    "light": {
        "canvas": "#ffffff",
        "surface": "#f6f8fa",
        "surfaceAlt": "#eef1f4",
        "border": "#d0d7de",
        "borderSoft": "#e2e8f0",
        "text": "#0d1117",
        "muted": "#57606a",
        "accent": "#0969da",
        "accent2": "#8250df",
        "accent3": "#1a7f37",
        "warn": "#bc4c00",
        "live": "#cf222e",
        "scan": "#0b1220",
        "shadow": "#8c959f",
    },
}

# Contribution heat, 0..4. Same five steps everywhere a year is drawn (terrain,
# mosaic, tiles) so "dark green" means the same thing in every card.
LEVELS = {
    "dark": ["#1d2634", "#0e4429", "#006d32", "#26a641", "#39d353"],
    "light": ["#eaeef2", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
}

# ---------------------------------------------------------------- brands ---
#
# Third-party brand hues and language colours. These are not ours to invent, so
# they are recorded here rather than scattered through the generators: one place
# to check when a brand refreshes its logo.

BRANDS = {
    "github": "#e3b341",       # star gold
    "linkedin": "#0a66c2",
    "rss": "#f26522",
    "typescript": "#3178c6",
    "python": "#3776ab",
    "javascript": "#f7df1e",
    "rust": "#ce422b",
    "go": "#00add8",
    "kotlin": "#7f52ff",
    "html": "#e34f26",
    "claude": "#d97757",
    "openai": "#412991",
    "langchain": "#1c3c3c",
    "mcp": "#2b3137",
    "pytorch": "#ee4c2c",
    "react": "#61dafb",
    "threejs": "#4b5563",
    "vite": "#646cff",
    "fastapi": "#009688",
    "docker": "#2496ed",
    "actions": "#2088ff",
    "su2": "#1f6feb",
    "solana": "#9945ff",
    "opencv": "#5c3ee8",
}

# ------------------------------------------------------------- typography ---
#
# Two families, four sizes, five roles. Sizes are the ones already in use, so
# adopting the tokens does not silently resize the existing cards.

FONTS = {
    # Rendered inside a browser. Both stacks are the same order everywhere.
    "mono": 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace',
    "sans": '-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Helvetica, Arial, sans-serif',
}

TYPE = {
    "eyebrow": {"size": 11.5, "tracking": 3.0, "weight": 700, "family": "mono"},
    "meta": {"size": 10.0, "tracking": 0.5, "weight": 400, "family": "mono"},
    "caption": {"size": 9.5, "tracking": 0.3, "weight": 400, "family": "mono"},
    "micro": {"size": 8.5, "tracking": 1.1, "weight": 400, "family": "mono"},
    "heading": {"size": 16.0, "tracking": 0.0, "weight": 700, "family": "mono"},
    "stat": {"size": 17.0, "tracking": 0.0, "weight": 700, "family": "mono"},
    "body": {"size": 12.0, "tracking": 0.0, "weight": 600, "family": "sans"},
}

# ---------------------------------------------------------------- geometry ---
#
# Every full-width card is 900 wide. Heights differ because content differs, but
# the *margins* are shared, and that is what makes a stack of cards line up.

SPACE = {"0": 0, "1": 4, "2": 8, "3": 12, "4": 16, "5": 24, "6": 32, "7": 44}

GEOMETRY = {
    # horizontal rhythm
    "gutter": 44,        # left edge of content
    "right": 856,        # right edge of content (900 - 44)
    "contentWidth": 812,  # right - gutter
    "gap": 12,           # between sibling chips
    # vertical rhythm
    "headerEyebrowY": 38,   # the small uppercase title
    "headerRuleY": 50,      # rule under the header
    "footerBaseline": 18,   # from the bottom edge
    # radii
    "radius": {"chip": 6.5, "card": 8, "panel": 10, "pill": 15},
    # stroke
    "stroke": {"hair": 1, "rule": 1, "emphasis": 2},
    # canvases
    "canvas": {"hero": [900, 300], "footer": [900, 110], "card": [900, 430]},
    # the live-window tile is the one deliberately non-900 artefact: two of them
    # sit side by side in a 50% table cell
    "tile": [423, 258],
}

# ----------------------------------------------------------------- themes ---
#
# Generators want {"bg", "panel", "grid", "text", ...}. Those are role aliases,
# not new colours: mapping them here means every generator can keep its own
# vocabulary while drawing from one palette.

ALIASES = {
    "bg": "canvas",
    "panel": "surface",
    "chip": "surfaceAlt",
    "grid": "border",
    "gridSoft": "borderSoft",
    "edge": "border",
    "stroke": "border",
}


def theme(mode: str) -> dict:
    """A flat, renderer-friendly dict for one mode, with aliases resolved."""
    if mode not in PALETTE:
        raise KeyError(f"unknown theme mode {mode!r}; expected one of {list(PALETTE)}")
    out = dict(PALETTE[mode])
    for alias, source in ALIASES.items():
        out.setdefault(alias, out[source])
    out["levels"] = list(LEVELS[mode])
    out["floor"] = LEVELS[mode][0]
    out["mono"] = FONTS["mono"]
    out["sans"] = FONTS["sans"]
    return out


THEMES = {mode: theme(mode) for mode in PALETTE}


def typ(role: str) -> str:
    """Inline attributes for a type role, for generators that build raw SVG."""
    spec = TYPE[role]
    family = FONTS[spec["family"]]
    tracking = f' letter-spacing="{spec["tracking"]}"' if spec["tracking"] else ""
    return (
        f'font-family="{family}" font-size="{spec["size"]}" '
        f'font-weight="{spec["weight"]}"{tracking}'
    )


def emit() -> dict:
    """The same tokens as data, for the browser pages and the tests."""
    return {
        "palette": PALETTE,
        "brands": BRANDS,
        "levels": LEVELS,
        "fonts": FONTS,
        "type": TYPE,
        "space": SPACE,
        "geometry": GEOMETRY,
    }


def main() -> int:
    if "--emit" in sys.argv:
        payload = emit()
        os.makedirs(os.path.dirname(EMIT), exist_ok=True)
        with open(EMIT, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(f"wrote {os.path.relpath(EMIT, ROOT)}", file=sys.stderr)
        return 0

    for mode in PALETTE:
        print(f"\n{mode}")
        for key, value in PALETTE[mode].items():
            print(f"  {key:12s} {value}")
        print(f"  {'levels':12s} {' '.join(LEVELS[mode])}")
    sizes = ", ".join(f"{name} {spec['size']}px" for name, spec in TYPE.items())
    print(f"\ntype: {sizes}")
    print(f"geometry: gutter {GEOMETRY['gutter']} -> {GEOMETRY['right']} ({GEOMETRY['contentWidth']} wide)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
