#!/usr/bin/env python3
"""Record how old each live-site capture is, so a tile can stop claiming LIVE.

Reads assets/shots/<repo>.json (written by build_mosaic.py, which knows when each
page was actually fetched) and writes assets/tiles/state.json. Pure stdlib and no
network, so it can run inside the nightly profile job.

A tile is only allowed to pulse LIVE while its capture is recent; past the
threshold the pill goes flat and reads "captured". The animation should never be
a claim the data cannot back.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(ROOT, "assets", "shots")
OUT = os.path.join(ROOT, "assets", "tiles", "state.json")
FRESH_DAYS = 21


def main() -> int:
    sites: dict[str, dict] = {}
    now = datetime.now(timezone.utc)
    for name in sorted(os.listdir(SHOTS)) if os.path.isdir(SHOTS) else []:
        if not name.endswith(".json"):
            continue
        repo = name[:-5]
        try:
            with open(os.path.join(SHOTS, name), encoding="utf-8") as handle:
                meta = json.load(handle)
        except (OSError, ValueError):
            continue
        stamp = meta.get("captured")
        if not stamp or not os.path.exists(os.path.join(SHOTS, repo + ".png")):
            continue
        try:
            when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            continue
        age = (now - when).days
        sites[repo] = {"captured": stamp, "age_days": age, "confirmed_live": age <= FRESH_DAYS}

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    payload = {"checked": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "fresh_days": FRESH_DAYS, "sites": sites}
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")

    fresh = sum(1 for v in sites.values() if v["confirmed_live"])
    print(f"{fresh}/{len(sites)} captures confirmed live (<= {FRESH_DAYS} days)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
