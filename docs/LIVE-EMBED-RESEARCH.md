# Can a github.io site render *live* inside the profile README?

Short answer: **no — not inside github.com.** Everything below is a test result, not
an opinion. The rest of this note is what does work, ranked by how close it gets to
"live", because the answer changes depending on which surface you mean.

Ask the question again on a page you control and the answer becomes yes, today,
with no restrictions — see option 3.

---

## 1. What GitHub's renderer actually does

Tested by POSTing each snippet to GitHub's own markdown API
(`POST /markdown`, `mode: gfm`), which is the same pipeline that renders a README.

| Snippet | Result |
|---|---|
| `<iframe src="https://knarayanareddy.github.io/toolscour/" width="800">` | **escaped** to `&lt;iframe …&gt;` — shown as text |
| `<object data="…">` | dropped entirely |
| `<embed src="…">` | dropped entirely |
| `<video src="…">` | **kept** — the only real embed GitHub allows |
| `<script>`, `onclick=`, inline JS | stripped |
| `<style>` in a `.md` file | ignored (only allowed inside an image's SVG) |
| SVG auto-fetched from a URL (`![](https://mine/svg)` → `<svg><foreignObject>` with `<iframe>`) | the `foreignObject` is stripped before it reaches the page |

And the reason an `iframe` could never work even if the tag survived — the
`Content-Security-Policy` header GitHub serves on `github.com/knarayanareddy`:

```
frame-src viewscreen.githubusercontent.com notebooks.githubusercontent.com
img-src   … camo.githubusercontent.com …
media-src github.com user-images.githubusercontent.com …
default-src 'none'
```

`frame-src` names GitHub's own hosts only, so even a smuggled-through iframe would
be refused by the browser. This is not a bug, an accident, or something a clever
trick routes around: it is a deliberate, correct decision about running third-party
code on a page that carries your session.

**Consequence:** any claim that a README "shows the live site" is either (a) an
animated image, or (b) a video. There is no third option on github.com.

---

## 2. What people are actually doing (and what they are really doing)

| Approach | Reality |
|---|---|
| Animated SVG tiles (this repo's `assets/tiles`, Leonxlnx's tiles) | Not live. Animation that *reads* as a running window; the pixels are a capture. |
| Screenshot walls / "auto-refreshed previews" | Not live. The capture is recent, the site is not running. |
| GIF / APNG recordings | Not live, and heavy: a 5-second 900px GIF is 2–8 MB. |
| `mp4` in a README | The only genuine video path (the `<video>` tag survives), and it still is not the site. |
| Browser-in-browser services (Webfuse, co-browsing SaaS) | Can be framed *on your own site*, but GitHub's `frame-src` blocks them in a README. |
| Markdown viewer Chrome extensions that do render iframes | Prove the file is fine, not that github.com renders it. Never test with these. |

---

## 3. The routes that actually deliver "live", ranked

### 3a. Frame your own site from your own site — works today

`knarayanareddy.github.io` does not send `X-Frame-Options`, so it can frame anything
that permits framing. A page on `kiranreddy.nl` can host real iframes of all 35
deployments, with real scroll, hover and clicks — and the README can link to it and
show an animated tile. This is the only arrangement where a visitor genuinely
touches the running site from your profile.

Cost: one page, ~40 lines of HTML, no dependencies. The blocked part is GitHub
pointing at it; the destination is entirely yours.

### 3b. Video — the only allowed motion *inside* the README

`<video src="…mp4" autoplay muted loop playsinline>` survives the sanitizer. A 3–4
second loop of the real app, cropped to a tile, is 200–600 KB at H.264. That is
closer to "live" than any SVG, because the pixels are a recording of a real input
sequence — but it is still a recording.

Honest limitation: `<video>` is allowed but not guaranteed to autoplay in every
viewer, and a broken `<video>` renders as nothing rather than a fallback image. Use
it *alongside* a poster image, never instead of one.

### 3c. Freshness, not liveness (what this repo does)

The tiles are captures, so the honest move is to keep them recent and say so:
`screenshots.yml` recaptures daily, `build_tiles.py` redraws from the newest
capture, and `refresh-ctimes.yml` downgrades the pulsing LIVE pill to a flat
"captured" once a capture is more than three weeks old. The animation never makes a
claim the data cannot back.

### 3d. Accept the profile cannot carry it, and make the first click pay

The profile's job is to earn a click. `kiranreddy.nl`, the 35 Pages builds and the
five case studies are all one click away; a tile that looks like a window is enough
to earn that click, and pretending harder starts costing credibility.

---

## 4. Reusable diagnostic

`scripts/camo_probe.py` asks Camo (GitHub's image proxy) to render any URL and
prints the text nodes it got back, so you can see how a page's *markup* renders
inside the profile before wiring it in:

```
python3 scripts/camo_probe.py https://knarayanareddy.github.io/toolscour/
python3 scripts/camo_probe.py --all          # every site in data/sites.json
```

Camo's TLS is blocked from some sandboxes; it fails with a clear error rather than
silently, and works from a normal network or CI runner.

---

## 5. Summary

| Surface | Live site possible? |
|---|---|
| github.com profile README | **No.** iframe/object/embed stripped; CSP `frame-src` blocks the rest. Video only. |
| github.com README as a *link* to a framed page | Yes — one click away. |
| kiranreddy.nl / any page you own | **Yes.** Real iframes, no restrictions. |
| A copied screenshot of a real iframe | Indistinguishable from a screenshot, and honest about it. |
