#!/usr/bin/env python3
"""Render one self-hosted "signal dashboard" SVG from real GitHub data.

Replaces a stack of third-party stat images (stats card, streak card, summary
cards, language cards, activity graph) with a single designed artefact that we
own: no external fonts, no external requests, and it costs nothing per view.

Data sources:
  * GraphQL contributionsCollection -> exact daily calendar, streaks, weekday
    rhythm (one request, authenticated)
  * REST commits on the most active repos -> hour-of-day rhythm. A commit's
    timestamp carries the author's UTC offset, so the local hour is the hour
    they actually worked. This is a 90-day sample and the card says so.
  * data/sites.json -> deployment counters

Usage:
    GITHUB_TOKEN=... python3 scripts/build_dashboard.py
    python3 scripts/build_dashboard.py --offline   # reuse data/stats.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

from tokens import THEMES as TOKENS  # shared design system

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATS = os.path.join(ROOT, "data", "stats.json")
SITES = os.path.join(ROOT, "data", "sites.json")
OUT_DIR = os.path.join(ROOT, "assets")

USER = os.environ.get("PROFILE_USER", "knarayanareddy")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

# Repos sampled for the hour-of-day histogram. Enough to characterise the rhythm
# without costing dozens of API calls.
HOUR_SAMPLE_REPOS = 14
HOUR_SAMPLE_DAYS = 120

THEMES = TOKENS  # from scripts/tokens.py — one palette for every card


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def graphql(query: str, variables: dict | None = None) -> dict:
    """Query by explicit login, never `viewer`.

    In GitHub Actions the token belongs to an App installation, so `viewer`
    resolves to the bot and would report the bot's (empty) contributions.
    Public contribution data for a named user works with any token.
    """
    if not TOKEN:
        raise SystemExit("GITHUB_TOKEN is required to fetch contribution data")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": f"{USER}-dashboard",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.loads(response.read().decode())
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]


def rest(path: str):
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{USER}-dashboard",
            **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as code:
        print(f"  rest {path} -> HTTP {code.code}", file=sys.stderr)
        return None


def collect() -> dict:
    print("fetching contribution calendar...", file=sys.stderr)
    payload = graphql(
        """
        query($login: String!) {
          user(login: $login) { contributionsCollection {
            totalCommitContributions totalPullRequestContributions
            totalIssueContributions totalRepositoriesWithContributedCommits
            contributionCalendar {
              totalContributions
              weeks { contributionDays { date contributionCount } }
            }
          } }
        }
        """,
        {"login": USER},
    )
    if not payload.get("user"):
        raise SystemExit(f"no public user data for {USER}")
    data = payload["user"]["contributionsCollection"]

    days = [
        (day["date"], day["contributionCount"])
        for week in data["contributionCalendar"]["weeks"]
        for day in week["contributionDays"]
    ]
    days.sort()
    calendar = [{"date": iso, "count": count} for iso, count in days]

    weekday = [0] * 7
    for iso, count in days:
        weekday[datetime.strptime(iso, "%Y-%m-%d").weekday()] += count

    best_day = max(days, key=lambda pair: pair[1]) if days else ("", 0)

    # streaks. The calendar includes today, which is usually still in progress,
    # so a zero today must not be read as "streak broken".
    longest = 0
    running = 0
    for _, count in days:
        if count > 0:
            running += 1
            longest = max(longest, running)
        else:
            running = 0
    trailing = list(reversed(days))
    if trailing and trailing[0][1] == 0:
        trailing = trailing[1:]
    current = 0
    for _, count in trailing:
        if count > 0:
            current += 1
        else:
            break

    weeks = [
        sum(count for _, count in week_days)
        for week_days in (
            days[index: index + 7] for index in range(0, len(days), 7)
        )
    ]

    print(f"  {data['contributionCalendar']['totalContributions']:,} contributions, "
          f"{len(days)} days", file=sys.stderr)

    # hour rhythm: commits on the busiest repos over the recent window
    hours = [0] * 24
    sampled = 0
    since = (datetime.now(timezone.utc) - timedelta(days=HOUR_SAMPLE_DAYS)).isoformat()
    repos = rest(f"/users/{USER}/repos?per_page=100&sort=pushed&type=owner") or []
    repos = [r for r in repos if not r.get("fork")][:HOUR_SAMPLE_REPOS]
    print(f"sampling commit hours across {len(repos)} repos...", file=sys.stderr)
    for repo in repos:
        commits = rest(
            f"/repos/{USER}/{repo['name']}/commits"
            f"?author={USER}&since={since}&per_page=100"
        ) or []
        for item in commits:
            stamp = (item.get("commit", {}).get("author") or {}).get("date")
            if not stamp:
                continue
            # the offset in the stamp is the author's local time: keep its hour
            try:
                local = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                continue
            hours[local.hour] += 1
            sampled += 1
    print(f"  sampled {sampled} commits", file=sys.stderr)

    languages: list[list] = []
    if os.path.exists(SITES):
        with open(SITES, encoding="utf-8") as handle:
            sites = json.load(handle)
        languages = sites.get("languages", [])

    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "window_days": len(days),
        "total_contributions": data["contributionCalendar"]["totalContributions"],
        "commits": data["totalCommitContributions"],
        "pull_requests": data["totalPullRequestContributions"],
        "issues": data["totalIssueContributions"],
        "repos_contributed": data["totalRepositoriesWithContributedCommits"],
        "current_streak": current,
        "longest_streak": longest,
        "best_day": {"date": best_day[0], "count": best_day[1]},
        "weekday": weekday,
        "hours": hours,
        "hour_sample": {"commits": sampled, "days": HOUR_SAMPLE_DAYS, "repos": len(repos)},
        "weeks": weeks,
        # Every day of the window, so a downstream artefact (the interactive
        # terrain) can be rebuilt from data instead of an opaque image.
        "calendar": calendar,
        "languages": languages,
    }


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #
W, H = 900, 430


def spark_path(weeks: list[int], x0: float, y0: float, width: float, height: float) -> str:
    if not weeks:
        return ""
    peak = max(weeks) or 1
    step = width / max(len(weeks) - 1, 1)
    points = []
    for index, value in enumerate(weeks):
        x = x0 + index * step
        y = y0 + height - (value / peak) * height
        points.append((round(x, 1), round(y, 1)))
    # smooth with a simple Catmull-Rom-ish polyline (SVG keeps it crisp)
    path = f"M{points[0][0]},{points[0][1]}"
    for index in range(1, len(points)):
        px, py = points[index - 1]
        cx, cy = points[index]
        mx = (px + cx) / 2
        path += f" C{mx},{py} {mx},{cy} {cx},{cy}"
    return path


def bars_hours(hours: list[int], theme: dict) -> str:
    peak = max(hours) or 1
    peak_hour = hours.index(peak)
    parts = []
    base_y = 196
    max_h = 86
    total = sum(hours) or 1
    for index, value in enumerate(hours):
        hour = index
        height = max(2.5, (value / peak) * max_h)
        x = 44 + index * 15.4
        highlighted = index == peak_hour
        fill = theme["accent"] if highlighted else theme["accent2"]
        opacity = 0.95 if highlighted else 0.42 + 0.4 * (value / peak)
        parts.append(
            f'    <g class="hcol">'
            f'<rect class="bar" style="animation-delay:{index * 0.028:.2f}s" '
            f'x="{x:.1f}" y="{base_y - height:.1f}" width="9.4" height="{height:.1f}" '
            f'rx="2" fill="{fill}" opacity="{opacity:.2f}"/>'
            f'<title>{hour:02d}:00 — {value} commits ({value * 100 // total}%)</title>'
            f'<rect class="hit" x="{x - 3:.1f}" y="{base_y - max_h - 6}" width="15.4" height="{max_h + 24}" '
            f'fill="transparent" tabindex="0" role="img" aria-label="{hour:02d}:00, {value} commits"/>'
            f'</g>'
        )
    labels = []
    for hour in (0, 6, 12, 18):
        labels.append(
            f'    <text class="mono" x="{44 + hour * 15.4 + 4.7:.1f}" y="{base_y + 15}" '
            f'font-size="9.5" fill="{theme["muted"]}" text-anchor="middle">{hour:02d}</text>'
        )
    return (
        "\n".join(parts)
        + "\n"
        + "\n".join(labels)
        + f'\n    <line x1="40" y1="{base_y + 3}" x2="410" y2="{base_y + 3}" '
        f'stroke="{theme["grid"]}" stroke-width="1"/>'
        + f'\n    <text class="mono" x="410" y="76" font-size="11" fill="{theme["accent"]}" '
        f'text-anchor="end">peak {peak_hour:02d}:00</text>'
    )


def bars_weekday(weekday: list[int], theme: dict) -> str:
    peak = max(weekday) or 1
    names = ["M", "T", "W", "T", "F", "S", "S"]
    parts = []
    base_y = 278
    for index, value in enumerate(weekday):
        height = max(2.5, (value / peak) * 28)
        x = 44 + index * 52
        day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][index]
        parts.append(
            f'    <g class="hcol">'
            f'<rect class="bar" style="animation-delay:{0.5 + index * 0.05:.2f}s" '
            f'x="{x}" y="{base_y - height:.1f}" width="34" height="{height:.1f}" rx="2" '
            f'fill="{theme["accent3"]}" opacity="{0.35 + 0.55 * (value / peak):.2f}"/>'
            f'<title>{day_name} — {value} contributions</title>'
            f'<rect class="hit" x="{x - 9}" y="{base_y - 40}" width="52" height="62" '
            f'fill="transparent" tabindex="0" role="img" aria-label="{day_name}, {value} contributions"/>'
            f'</g>'
        )
        parts.append(
            f'    <text class="mono" x="{x + 17}" y="{base_y + 15}" font-size="9.5" '
            f'fill="{theme["muted"]}" text-anchor="middle">{names[index]}</text>'
        )
    return "\n".join(parts)


def chips(stats: dict, theme: dict) -> str:
    items = [
        (f"{stats['total_contributions']:,}", "contributions"),
        (f"{stats['commits']:,}", "commits"),
        (f"{stats['pull_requests']:,}", "pull requests"),
        (f"{stats['repos_contributed']}", "repos touched"),
    ]
    parts = []
    x = 452
    for index, (value, label) in enumerate(items):
        width = 96
        parts.append(
            f'    <g class="bar" style="animation-delay:{0.8 + index * 0.09:.2f}s">\n'
            f'      <rect x="{x}" y="92" width="{width}" height="52" rx="8" '
            f'fill="{theme["panel"]}" stroke="{theme["grid"]}" stroke-width="1"/>\n'
            f'      <text class="mono" x="{x + 11}" y="118" font-size="17" font-weight="700" '
            f'fill="{theme["accent"]}">{value}</text>\n'
            f'      <text class="mono" x="{x + 11}" y="133" font-size="9" letter-spacing="0.3" '
            f'fill="{theme["muted"]}">{label}</text>\n'
            f"    </g>"
        )
        x += 102
    return "\n".join(parts)


def languages_bar(stats: dict, theme: dict) -> str:
    languages = stats.get("languages") or []
    if not languages:
        return ""
    total = sum(count for _, count in languages) or 1
    palette = [theme["accent"], theme["accent2"], theme["accent3"], theme["warn"],
               theme["muted"], theme["grid"]]
    parts = []
    x = 44.0
    width_total = 812.0
    legend = []
    for index, (name, count) in enumerate(languages[:6]):
        share = count / total
        width = max(6, share * width_total)
        color = palette[index % len(palette)]
        parts.append(
            f'    <g class="hcol"><rect class="bar" style="animation-delay:{1.1 + index * 0.06:.2f}s" '
            f'x="{x:.1f}" y="356" width="{width - 3:.1f}" height="9" rx="3" fill="{color}" '
            f'opacity="{0.9 - index * 0.09:.2f}"/>'
            f'<title>{name} — {count} repos ({share * 100:.0f}%)</title></g>'
        )
        legend.append(
            f'<tspan fill="{color}">■</tspan> {name} {share * 100:.0f}%'
        )
        x += width
    legend_line = '   '.join(legend)
    return "\n".join(parts) + (
        f'\n    <text class="mono" x="44" y="386" font-size="9.5" fill="{theme["muted"]}">'
        f"{legend_line}</text>"
    )


TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="900" height="430" viewBox="0 0 900 430" role="img" aria-label="__ARIA__">
  <title>__ARIA__</title>
  <defs>
    <linearGradient id="line" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="__ACCENT__"/>
      <stop offset="100%" stop-color="__ACCENT2__"/>
    </linearGradient>
    <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="__ACCENT__" stop-opacity="0.28"/>
      <stop offset="100%" stop-color="__ACCENT__" stop-opacity="0"/>
    </linearGradient>
    <style>
      .mono { font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace; }
      .sans { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Helvetica, Arial, sans-serif; }
      /* base state is the finished state, so static renderers show everything */
      .bar { transform-box: fill-box; transform-origin: center bottom; animation: rise .9s cubic-bezier(.22,1,.36,1) both; }
      .fade { animation: fade .9s ease-out both; }
      .draw { stroke-dasharray: 4000; stroke-dashoffset: 0; animation: draw 2.2s ease-out both; }
      @keyframes rise { from { transform: scaleY(0); } to { transform: scaleY(1); } }
      @keyframes fade { from { opacity: 0; } to { opacity: 1; } }
      @keyframes draw { from { stroke-dashoffset: 4000; } to { stroke-dashoffset: 0; } }
      .static { display: none; }
      .hcol { transform-box: fill-box; transform-origin: center bottom; transition: transform .18s cubic-bezier(.22,1,.36,1); }
      .hcol:hover, .hcol:focus-within { transform: scaleY(1.06) translateY(-2px); }
      .hit { cursor: pointer; outline: none; }
      .hit:focus { stroke: __ACCENT__; stroke-width: 1.5; rx: 3; }
      @media (prefers-reduced-motion: reduce) {
        .bar, .fade, .draw { animation: none; }
        .draw { stroke-dashoffset: 0; }
        .hcol { transition: none; }
        .hcol:hover, .hcol:focus-within { transform: none; }
      }
    </style>
  </defs>

  <rect x="0" y="0" width="900" height="430" fill="__BG__"/>
  <rect x="0.5" y="0.5" width="899" height="429" fill="none" stroke="__GRID__" stroke-width="1"/>

  <!-- header -->
  <text class="mono" x="44" y="38" font-size="11.5" letter-spacing="3.2" fill="__ACCENT__">SIGNAL DASHBOARD</text>
  <text class="mono" x="856" y="38" font-size="10" letter-spacing="0.6" fill="__MUTED__" text-anchor="end">last __WINDOW__ days · generated __GENERATED__</text>
  <line x1="44" y1="50" x2="856" y2="50" stroke="__GRID__" stroke-width="1" opacity="0.7"/>

  <!-- zone A: rhythm -->
  <text class="mono" x="44" y="76" font-size="10.5" letter-spacing="2" fill="__TEXT__">WHEN I SHIP</text>
__HOUR_BARS__

  <text class="mono" x="44" y="248" font-size="10" letter-spacing="1.4" fill="__MUTED__">BY WEEKDAY</text>
__WEEKDAY_BARS__

  <!-- zone B: volume -->
  <text class="mono" x="452" y="76" font-size="10.5" letter-spacing="2" fill="__TEXT__">THE YEAR</text>
__CHIPS__

  <!-- sparkline -->
  <g class="fade" style="animation-delay:1s">
    <path d="__SPARK_AREA__" fill="url(#area)"/>
    <path class="draw" d="__SPARK_LINE__" fill="none" stroke="url(#line)" stroke-width="2" stroke-linecap="round"/>
  </g>
  <text class="mono" x="452" y="246" font-size="9.5" letter-spacing="0.4" fill="__MUTED__">53-week contribution trend</text>

  <!-- streaks -->
  <g class="fade" style="animation-delay:1.2s">
    <rect x="452" y="264" width="193" height="44" rx="8" fill="__PANEL__" stroke="__GRID__" stroke-width="1"/>
    <text class="mono" x="464" y="284" font-size="15" font-weight="700" fill="__ACCENT3__">__CURRENT_STREAK__ days</text>
    <text class="mono" x="464" y="298" font-size="9" letter-spacing="0.3" fill="__MUTED__">current streak</text>

    <rect x="655" y="264" width="201" height="44" rx="8" fill="__PANEL__" stroke="__GRID__" stroke-width="1"/>
    <text class="mono" x="667" y="284" font-size="15" font-weight="700" fill="__ACCENT2__">__LONGEST_STREAK__ days</text>
    <text class="mono" x="667" y="298" font-size="9" letter-spacing="0.3" fill="__MUTED__">longest in 12 months</text>
  </g>

  <text class="mono" x="856" y="332" font-size="9" letter-spacing="0.3" fill="__MUTED__" text-anchor="end">hour rhythm sampled from __HOUR_SAMPLE__ commits · __HOUR_REPOS__ repos</text>

  <!-- languages -->
  <text class="mono" x="44" y="344" font-size="10" letter-spacing="1.4" fill="__MUTED__">LANGUAGE MIX</text>
__LANGUAGES__

  <text class="mono" x="44" y="410" font-size="8.5" letter-spacing="0.3" fill="__MUTED__">__BEST_DAY__</text>
</svg>
"""


def render(stats: dict, theme_name: str) -> str:
    theme = THEMES[theme_name]
    aria = (
        f"Signal dashboard for {USER}: {stats['total_contributions']:,} contributions, "
        f"{stats['commits']:,} commits, {stats['pull_requests']:,} pull requests, "
        f"{stats['current_streak']}-day current streak."
    )
    spark_line = spark_path(stats["weeks"], 452, 190, 404, 40)
    spark_area = (spark_line + " L856,230 L452,230 Z") if spark_line else ""

    svg = TEMPLATE
    for key, value in theme.items():
        if isinstance(value, str):
            svg = svg.replace(f"__{key.upper()}__", value)
    replacements = {
        "__ARIA__": aria,
        "__WINDOW__": str(stats["window_days"]),
        "__GENERATED__": stats["generated"],
        "__HOUR_BARS__": bars_hours(stats["hours"], theme),
        "__WEEKDAY_BARS__": bars_weekday(stats["weekday"], theme),
        "__CHIPS__": chips(stats, theme),
        "__SPARK_LINE__": spark_line,
        "__SPARK_AREA__": spark_area,
        "__CURRENT_STREAK__": str(stats["current_streak"]),
        "__LONGEST_STREAK__": str(stats["longest_streak"]),
        "__LANGUAGES__": languages_bar(stats, theme),
        "__HOUR_SAMPLE__": f"{stats['hour_sample']['commits']:,}",
        "__HOUR_REPOS__": str(stats["hour_sample"]["repos"]),
        "__BEST_DAY__": (
            f"best day {stats['best_day']['date']} · {stats['best_day']['count']} contributions"
            if stats.get("best_day", {}).get("date") else "no contribution data available"
        ),
    }
    for key, value in replacements.items():
        svg = svg.replace(key, value)
    return svg


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="reuse data/stats.json")
    args = parser.parse_args()

    if args.offline:
        with open(STATS, encoding="utf-8") as handle:
            stats = json.load(handle)
    else:
        stats = collect()
        os.makedirs(os.path.dirname(STATS), exist_ok=True)
        with open(STATS, "w", encoding="utf-8") as handle:
            json.dump(stats, handle, indent=2)
            handle.write("\n")

    os.makedirs(OUT_DIR, exist_ok=True)
    for theme_name in THEMES:
        path = os.path.join(OUT_DIR, f"dashboard-{theme_name}.svg")
        svg = render(stats, theme_name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(svg)
        print(f"wrote {os.path.relpath(path, ROOT)} ({len(svg):,} bytes)", file=sys.stderr)

    unresolved = [
        token for token in ("__BG__", "__CHIPS__", "__HOUR_BARS__", "__LANGUAGES__")
        if token in open(os.path.join(OUT_DIR, "dashboard-dark.svg"), encoding="utf-8").read()
    ]
    if unresolved:
        print(f"error: unresolved tokens {unresolved}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
