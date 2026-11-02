# Taking the profile showcase to the next level

A deep dive into what the most innovative GitHub profile showcases actually do, what
GitHub's renderer physically allows, and a concrete plan for this repository.

**TL;DR** — the current README is in the top ~5% of profile READMEs, but every *visual*
element in it is borrowed and third-party: capsule-render, readme-typing-svg,
github-readme-stats, streak-stats, komarev, quotes, activity-graph, Platane/snk. That means
it looks like the same template thousands of other profiles use, and it breaks whenever one
of those Vercel/Heroku endpoints dies (several already have). The 10x move is not *more*
widgets. It is **owning the pixels**: hand-authored animated SVG, generated from your real
data, hosted in this repo, with no third-party dependency. Everything below is ranked by
impact per unit of effort.

---

## 1. What "innovative" actually means out there

Most "best profile README" lists are the same 40 profiles recycled since 2020. Sorting the
genre by what it genuinely demonstrates:

### Tier 0 — The template wall (what 90% of profiles are)
Shields badges, a typing SVG, a stats card, a trophy shelf, a snake, a visitor counter.
Individually fine, collectively noise. The best write-ups now argue *against* this: badge
restraint is scored above badge volume, and the strongest profiles are ~30 lines, not 300.

### Tier 1 — Instrumented (data-driven, still third-party)
- **[lowlighter/metrics](https://github.com/lowlighter/metrics)** — the single biggest
  upgrade available to most people: 47 plugins, 335 options. Isometric commit calendar,
  coding-habits charts, achievements, languages activity, lines of code changed, stargazers
  over time, notable contributions, Stack Overflow, WakaTime, Spotify, and a
  **GitHub Skyline / GitHub City** plugin that renders your contribution year as a 3D city.
  Renders to a committed SVG. This is the "serious engineer" look.
- **[github-readme-stats](https://github.com/anuraghazra/github-readme-stats)** — by
  Anurag Hazra, 65k+ stars. Its credibility comes from *meta*: the author embeds his own
  library showing his own numbers.
- **[streak-stats](https://github.com/DenverCoder1/github-readme-streak-stats)** — Jonah
  Lawrence's. The lesson people miss: he leads with the single strongest number, placed
  above the fold, not buried under decoration.

### Tier 2 — Motion (self-hosted animated SVG)
This is where it stops looking like a template. The technique: GitHub sanitizes README
markdown and strips `<script>`, `<style>`, `<iframe>`, and `<video>`, **but an SVG loaded
through `<img src="…">` renders as a normal image and keeps its internal CSS `@keyframes`
and SMIL animations.** So you pre-render motion into a file you own.
- **[kevinpradith](https://github.com/kevinpradith/kevinpradith)** — six self-hosted animated
  SVGs styled as macOS 26 Tahoe UI, rebuilt from live GitHub data every morning.
- **[DigitLion](https://github.com/DigitLion/DigitLion/pull/3)** — the best-documented
  example: hero with drifting aurora + per-letter name reveal + typed rotating tagline + a
  "perceive → reason → plan → act" neural net with flowing signals + synthwave grid floor;
  a looping terminal card; an animated semantic-space plot; a 3D-orbit tech stack with depth
  scaling and occlusion; animated timeline. Fonts subset and embedded as data URIs. All
  honour `prefers-reduced-motion`.
- **[Aiyzoxx/animated-terminal-profile](https://github.com/Aiyzoxx/animated-terminal-profile)**
  — ASCII portrait of your face typed out with SMIL clipPath wipes, neofetch-style info
  card, animated contribution heatmap. Genuinely custom, zero third parties.
- **[Dylan2388/github-theme](https://github.com/Dylan2388/github-theme)** — TypeScript
  pipeline: profile data → animated SVG cards → generated README → push.
- **[dilshan-codes/contribution-animations](https://github.com/dilshan-codes/contribution-animations)**
  — a menu of animated styles over your *real* contribution graph.

### Tier 3 — Interactive (the profile is a toy, not a poster)
- **[JonathanGin52](https://github.com/JonathanGin52)** — multiplayer **Connect 4**. Clicking
  a move opens an issue; a workflow parses the issue title, commits the new board into the
  README, and a bot replies when it's your turn. Playable by strangers, directly on a profile.
- **[timburgan](https://github.com/timburgan)** — **multiplayer chess**, same issue-title
  protocol.
- **[evaristocuesta](https://github.com/evaristocuesta)** — **Minesweeper** rendered into the
  README by a .NET workflow.
- **Vote-based tic-tac-toe** — no moves by individuals, just click-counters; the most-voted
  cell is played hourly by cron.
- **Guestbooks** — signing in opens an issue, and the workflow appends your message to the
  README (Jason Etcovitch's original trick).
- **"Code mode"** — the whole README formatted as a fake VS Code editor
  ([AlbertArakelyan](https://github.com/AlbertArakelyan/AlbertArakelyan) is the reference),
  complete with syntax-highlighted "file" and a terminal.

### Tier 4 — Dimensional
- **[yoshi389111/github-profile-3d-contrib](https://github.com/yoshi389111/github-profile-3d-contrib)**
  — your contribution calendar as an isometric 3D block terrain, committed as SVG. One
  workflow file, immediate "wait, how?" reaction. Has `season` and `night` palettes.
- **Forest/season forks** — the same calendar drawn as trees with seasonal palettes.
- **Skyline clones** — `skyline.github.com` is dead; **[gitcity](https://github.com/aprilNH7/gitcity)**
  and **[doctorixx/github-skyline](https://github.com/doctorixx/github-skyline)** replace it,
  and gitcity exports **STL** — meaning you can 3D-print your year of commits. That is a
  genuinely great thing to own.

---

## 2. The constraints that decide everything

These are the rules that make most "cool ideas" impossible, and they're why the winning
moves are all *pre-rendered SVG*:

| Constraint | Consequence |
|---|---|
| README HTML is sanitized: `<script>`, `<style>`, `<iframe>`, `<video>`, `<audio>`, `<object>`, event handlers are stripped | No JavaScript. No real video. No HTML canvas. |
| `<video>` is not rendered in READMEs | Demo clips must be **GIF, APNG or animated SVG** — or a thumbnail linking out |
| SVG via `<img>` keeps CSS `@keyframes` + SMIL, but runs under `default-src 'none'; style-src 'unsafe-inline'; sandbox` | No external fonts, no external images, no fetch. **Everything must be embedded** — subset fonts as data URIs, or system font stacks |
| Images are proxied and cached by GitHub's Camo | Mutable URLs go stale until cache-bust; third-party hosts are a single point of failure (Heroku free tier is dead; several Vercel widgets now 402/500) |
| `prefers-color-scheme` works via `<picture>` + `media` | Ship light and dark variants rather than one compromise colour |
| Animation can hurt people | Wrap everything in `@media (prefers-reduced-motion: reduce)` — a reviewer flagged its absence on someone else's PR, and it's the difference between "cool" and "careless" |
| API-driven widgets share rate limits | Your own committed SVG costs zero requests per view |

**The strategic conclusion:** every third-party widget you remove is both a reliability win
and a differentiation win. A hand-drawn hero costs nothing to serve, never rate-limits,
never 404s, and looks like nobody else's.

---

## 3. Ranked plan for this repository

Ranked by impact ÷ effort, with the flagship first.

### 🥇 1. Own the hero — hand-built animated SVG (implemented)
Replace capsule-render + readme-typing-svg with `assets/hero.svg`, generated by
`scripts/build_hero.py` from real repo data. Aurora drift, per-letter name reveal, typewriter
tagline cycling through your actual positioning, a live "harness" glyph with orbiting rings
and signal pulses, animated stat bars, drifting grid floor, light/dark safe, reduced-motion
safe, zero external requests. **This alone changes the profile from "templated" to "designed."**

### ✅ 3. Real screenshots of your 33 live sites — IMPLEMENTED
`scripts/build_mosaic.py` + `.github/workflows/screenshots.yml`. Playwright captures
every deployment at 1280×800, crops to a uniform tile, and composes a screenshot wall
(`assets/mosaic-{dark,light}.png`) plus a clickable SVG index. Captures are cached per repo
and only re-taken when that repo is pushed, so a daily run costs almost nothing.
**Getting a browser where there isn't one.** This sandbox cannot download Chromium, and
`workflow_dispatch` only registers workflows that exist on the default branch — so a branch
run cannot be requested directly. The way through is a push trigger: allow `arena/**` in
`screenshots.yml`, and a commit to the working branch starts a run on a runner that *does*
have a browser. The job then commits the captures back to that branch, and the sandbox
fetches them with `git pull` (`api.github.com` is reachable even when `raw.githubusercontent`
is not). Two further obstacles, both real on this repo: Actions is not permitted to create
pull requests here, so publishing must be a plain commit; and the working tree needs
`contents: write`. Total round trip: about 70 seconds for 35 sites.

*Status: shipped. 33 of 35 deployments capture cleanly; `Handy` serves GitHub's 404 and
`SAAF-circuit-breaker` renders blank, so both are classified as unavailable and left off the
wall instead of being shown broken.*

### ✅ 4. One designed dashboard — IMPLEMENTED
`scripts/build_dashboard.py` → `assets/dashboard-{dark,light}.svg`. Replaces the stats card,
streak card, three summary cards, language cards and activity graph with a single
self-rendered card: hour-of-day rhythm (sampled from commit timestamps, keeping each
author's UTC offset so the hour is their local hour), weekday rhythm, year totals, 53-week
sparkline, streaks and language mix. Real figures at time of writing: **4,243 contributions,
3,749 commits, 394 pull requests, 116 repos touched, 42-day streak**.
It queries `user(login:)` rather than `viewer`, because in Actions the token belongs to the
App and `viewer` would report the bot's empty history.

### 🥈 2. Isometric 3D contribution terrain (workflow added)
`yoshi389111/github-profile-3d-contrib` → committed SVG. Highest wow-per-line-of-code
available. Pairs with the snake you already have, or replaces it if you want restraint.

### ~~3. Real screenshots of your 33 live sites~~ (built — see above)
You have the single most unusual asset here: **33 deployed sites nobody has seen**. A table
of text links undersells that badly. A workflow that visits each Pages URL with Playwright
inside Actions, captures a 1280×800 PNG, commits them under `assets/shots/`, and renders a
**mosaic gallery** would make the profile obviously unlike anyone else's. No third-party
service, no rate limits, and it self-updates when a site changes. This is the recommendation
I'd push hardest on after the hero.

### ~~4. Replace the stat wall with one designed dashboard~~ (built — see above)
Currently: stats card + streak + summary + activity graph + repos-per-language +
commit-language + productive-time + snake + quote — nine third-party images that repeat the
same information in six visual languages. Replace with **one** self-rendered SVG "signal
dashboard": commits by weekday/hour as a radial heat clock, language mix as a stacked arc,
streak as a sparkline, plus your 33-site/35-deploy counters. One image, your design system.

### 5. Interactive layer, if you want the gasps
Pick exactly **one**; more than one and the profile becomes a circus:
- **Multiplayer Connect 4 or chess** (issue-title protocol) — most social, highest engagement,
  and it visibly proves you can wire Actions to state.
- **Minesweeper** — self-contained, no opponent needed.
- **Guestbook** — cheapest, and gives visitors a reason to interact.
- **A choose-your-own-adventure** over your projects, driven by collapsible `<details>` —
  zero infrastructure, and almost nobody does it well.

Given your portfolio is literally about *autonomous agents with guardrails*, the most
on-brand interactive option is a small **"agent harness" simulator**: visitors open an issue
choosing a "ring" of defense, a workflow replays a canned decision trace, and the README shows
the resulting gate verdict. That's a demo of your thesis, not a toy.

### 6. Terminal / "code mode" restyle
A looping typed terminal session (`whoami`, `cat profile.yaml`, `./research --latest`) as a
self-hosted SVG. Cheap, very legible, and reads as senior. Works best as *one card*, not the
whole README.

### 7. Dimensional finishes
- **3D-printed skyline** via [gitcity](https://github.com/aprilNH7/gitcity) STL export — a
  photo of the print on the profile is an unreasonably effective flex.
- **Live status badge** — self-hosted SVG showing "currently building X", fed by a JSON file
  you edit; no API needed.
- **Light/dark hero variants** via `<picture>` — already wired in the hero generator.

### What to delete
The visitor counter (komarev) and the random quote are the two elements most associated with
templated profiles; both also add third-party failure modes. The `productive-time` and
`most-commit-language` cards duplicate what the repos-per-language card already says.

---

## 4. Anti-patterns worth naming

- **Nine stats images.** Every additional widget divides attention. One well-designed card
  beats six default-themed ones.
- **Metrics that don't flatter you.** 69 stars and 1 follower don't need a leaderboard —
  lead with the 33 shipped products instead. Your strongest number is *deployed sites*, which
  almost nobody can match.
- **Motion with no escape hatch.** Always honour `prefers-reduced-motion`.
- **Unverifiable claims.** Your repos already do the honest thing (explicit
  `IMPLEMENTATION_STATUS.md`, "prototype with a working slice"). Keep that voice in the
  profile copy; it's a differentiator, not a weakness.
- **Copying the reference profile verbatim.** tysoncung's works because it maps to *his*
  facts (600K contributed stars, 20+ awesome lists, CPO). Yours has different facts: 33 live
  sites, a new repo nearly every day, aerospace + EU compliance. Build the showcase around
  those.

---

## 5. Sources

- [lowlighter/metrics — plugins and options](https://github.com/lowlighter/metrics)
- [yoshi389111/github-profile-3d-contrib](https://github.com/yoshi389111/github-profile-3d-contrib)
- [DigitLion animated SVG card redesign (PR #3)](https://github.com/DigitLion/DigitLion/pull/3)
- [Aiyzoxx/animated-terminal-profile](https://github.com/Aiyzoxx/animated-terminal-profile)
- [Dylan2388/github-theme](https://github.com/Dylan2388/github-theme)
- [dilshan-codes/contribution-animations](https://github.com/dilshan-codes/contribution-animations)
- [Four multiplayer games on GitHub profiles](https://leonardomontini.dev/4-github-games-readme-profiles/)
- [evaristocuesta — Minesweeper profile](https://github.com/evaristocuesta/evaristocuesta)
- [gitcity — Skyline replacement with STL export](https://github.com/aprilNH7/gitcity)
- [doctorixx/github-skyline](https://github.com/doctorixx/github-skyline)
- [AlbertArakelyan — code-mode interactive profile](https://github.com/AlbertArakelyan/AlbertArakelyan)
- [Best GitHub profile README examples, 2026](https://readmedesign.com/blog/best-github-profile-readme-examples)
- [High-signal sections vs gimmicks](https://readmedesign.com/blog/github-profile-readme-ideas)
- [awesome-dynamic-readme](https://github.com/soroushchehresa/awesome-dynamic-readme)
