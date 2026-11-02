#!/usr/bin/env python3
"""Ask GitHub's Camo proxy how it treats a page, without guessing.

Camo is the image proxy behind every remote image in a README. When it fetches
something that is not an image it answers with a generated SVG that embeds the
upstream HTML structure as <text> children. That means the proxy will happily
tell us how a page renders *before* we wire it into the profile: which lines come
from the page's own markup, which come from linked stylesheets, and whether an
external sheet survives the parser at all.

GitHub's own HTML rendering drops <iframe>/<object>/<embed>, so this is the only
way to answer "does my live site look right inside the profile" before shipping.

    python3 scripts/camo_probe.py https://knarayanareddy.github.io/toolscour/
    python3 scripts/camo_probe.py --all          # every site in data/sites.json

Needs Pillow to decode the response into words (`pip install pillow`).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "sites.json")

CAMO_HOST = "https://camo.githubusercontent.com"
USER_AGENT = "knarayanareddy-profile-camo-probe"
# Any 64-hex digest is accepted: the signature is not checked on read, Camo just
# needs the path shape. The real path is taken from the rendered README when we
# want the exact one the viewer will use.
DUMMY_DIGEST = "0" * 64


def encode(blob: bytes) -> str:
    """GitHub's legacy encoder.

    Camo paths are *not* URL-safe base64: values are grouped into threes and
    padded in the middle of the quartet, which happens to be exactly what
    RFC 4648 base64 does for byte-aligned input. Kept explicit so a future
    editorial change to the URL format shows up here instead of silently 404ing.
    """
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    out: list[str] = []
    for i in range(0, len(blob), 3):
        chunk = blob[i:i + 3]
        pad = 3 - len(chunk)
        chunk = chunk + b"\0" * pad
        n = (chunk[0] << 16) | (chunk[1] << 8) | chunk[2]
        out.append(alphabet[n >> 18 & 63])
        out.append(alphabet[n >> 12 & 63])
        out.append("=" if pad > 1 else alphabet[n >> 6 & 63])
        out.append("=" if pad > 0 else alphabet[n & 63])
    return "".join(out)


def camo_url(url: str, digest: str = DUMMY_DIGEST) -> str:
    return f"{CAMO_HOST}/{digest}?{encode(url.encode())}"


def fetch(url: str, timeout: int = 30) -> tuple[int, str, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.headers.get("Content-Type", ""), response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers.get("Content-Type", ""), error.read()
    except Exception as error:  # noqa: BLE001 - network shapes vary wildly
        return 0, "error", str(error).encode()


def parse_svg(svg: bytes) -> list[tuple[float, float, str]]:
    """(x, y, text) for every <text> node, in document order."""
    seen: list[tuple[float, float, str]] = []
    root = ET.fromstring(svg)
    for node in root.iter():
        if node.tag.endswith("text"):
            label = (node.text or "").strip()
            if not label:
                continue
            seen.append((float(node.get("x", 0) or 0), float(node.get("y", 0) or 0), unescape(label)))
    return seen


def summarise(texts: list[tuple[float, float, str]]) -> dict:
    words = [t for _, _, t in texts]
    joined = "\n".join(words)
    return {
        "lines": len(words),
        "chars": len(joined),
        "has_iframe": bool(re.search(r"<iframe", joined, re.I)),
        "has_script": "<script" in joined.lower(),
        "has_link": "<link" in joined.lower(),
        "head_lines": sum(1 for _, y, _ in texts if y < 120),
        "stylesheet_words": sum(1 for w in words if re.search(r"[{};]", w)),
    }


def probe(url: str, keep: str | None = None) -> dict:
    status, ctype, body = fetch(camo_url(url))
    result = {"url": url, "camo_status": status, "content_type": ctype, "bytes": len(body)}
    if status != 200:
        result["note"] = body[:200].decode("utf-8", "replace")
        return result

    if "svg" in ctype.lower():
        result.update(summarise(parse_svg(body)))
        if keep:
            with open(keep, "wb") as handle:
                handle.write(body)
            result["svg"] = keep
            # Left as text so the words are readable without a browser.
            try:
                from PIL import Image, ImageDraw, ImageFont
            except ImportError:
                return result

            texts = parse_svg(body)
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
            if not os.path.exists(font_path):
                return result
            font = ImageFont.truetype(font_path, 13)
            width = 1400
            height = 40 + 16 * len(texts)
            canvas = Image.new("RGB", (width, height), (16, 18, 24))
            draw = ImageDraw.Draw(canvas)
            for i, (x, y, label) in enumerate(texts):
                draw.text((20 + min(x, 200) * 0.5, 20 + i * 16), label[:150], font=font, fill=(215, 218, 224))
            png = keep.replace(".svg", ".png")
            canvas.save(png)
            result["png"] = png
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?")
    parser.add_argument("--all", action="store_true", help="probe every live site in data/sites.json")
    parser.add_argument("--keep", help="write the Camo SVG here (and a PNG of its words next to it)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    urls: list[str] = []
    if args.url:
        urls = [args.url]
    elif args.all:
        with open(DATA, encoding="utf-8") as handle:
            urls = [s["url"] for s in json.load(handle)["sites"]]
    else:
        parser.error("pass a URL or --all")

    for url in urls:
        keep = args.keep if len(urls) == 1 else None
        result = probe(url, keep=keep)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            verdict = "OK" if result.get("lines") else (result.get("note") or "empty")
            print(
                f"{url:58s} {result['camo_status']:>3} "
                f"{result.get('bytes', 0):>8} B "
                f"lines={result.get('lines', 0):>3} "
                f"head={result.get('head_lines', 0):>3} "
                f"css={result.get('stylesheet_words', 0):>3} "
                f"{verdict}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
