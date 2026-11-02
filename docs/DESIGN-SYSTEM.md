# The design system

Every card in the profile is generated, and every generator now draws from one
file: `scripts/tokens.py`. That file is the only place a colour, a font stack, a
font size, a margin or a canvas size is allowed to be invented.

```bash
python3 scripts/tokens.py          # print the palette, type scale and geometry
python3 scripts/tokens.py --emit   # refresh data/tokens.json for the web pages
```

`data/tokens.json` is committed, so `web/` gets the same values without a build
step, and the tests can assert against the exact numbers.

## What was wrong before

Seven generators had grown seven palettes. The two worst were invisible until
you put the cards side by side:

| Role | Hero (dark) | Dashboard (dark) |
|---|---|---|
| decorative grid | `#1f2937` | `#30363d` |
| body text (light mode) | `#1f2328` | `#0d1117` |

Plus four different mono font stacks and six near-identical font sizes
(9, 9.5, 10, 10.5, 11.5, 12). Nothing was *broken*; nothing quite matched.

## The rules

1. **Roles, not colours.** Generators ask for `bg`, `panel`, `grid`, `text`,
   `muted`, `accent`, `accent2`, `accent3`, `warn`, `live`. Those are aliases
   resolved by `tokens.theme()`.
2. **Both modes define every role.** `tests/tokens.test.mjs` fails if dark and
   light disagree about which keys exist — a missing key silently keeps the
   other mode's colour.
3. **Brand hues are tokens too.** GitHub's star gold, LinkedIn's blue and the
   language colours live in `BRANDS`, because they are not ours to invent.
4. **Full-width cards share a grid.** 900 wide, 44pt gutters, content from
   44 to 856. The live-window tile is the one documented exception at 423 wide,
   because two of them sit side by side in a table cell.
5. **The browser pages read the same file.** `web/core.js` exposes
   `applyTokens()`; `web/index.html` and `web/snake.html` apply it at boot. The
   literal palettes they still carry are `file://` fallbacks, nothing more.

## What the guard test catches

`node --test tests/tokens.test.mjs` fails when:

- `data/tokens.json` drifts from `scripts/tokens.py` (i.e. someone hand-edited it)
- a role exists in one mode but not the other
- any colour is not a valid 6-digit hex
- a generator re-grows a private `THEMES = {` literal
- a generator hardcodes a hex that is not in the tokens
- a generator uses a font family outside the two token stacks
- a browser page stops reading `data/tokens.json`
- the grid stops adding up (`right - gutter != contentWidth`)

That is the whole point: consistency that is asserted, not remembered.
