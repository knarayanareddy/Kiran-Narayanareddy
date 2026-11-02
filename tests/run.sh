#!/bin/sh
# Everything that can be asserted without a browser.
set -e
cd "$(dirname "$0")/.."
python3 scripts/tokens.py --emit >/dev/null 2>&1 || true
node --test tests/core.test.mjs tests/tokens.test.mjs tests/reels.test.mjs
