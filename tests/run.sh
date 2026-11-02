#!/bin/sh
# Logic tests for the interactive pages. No browser needed.
set -e
cd "$(dirname "$0")/.."
node --test tests/core.test.mjs
