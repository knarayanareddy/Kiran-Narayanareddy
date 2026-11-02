#!/usr/bin/env python3
"""Regenerate the auto-updating blocks of the profile README.

Pulls every public repository for the user, works out which ones have a live
GitHub Pages site, and rewrites the regions of README.md that sit between
HTML comment markers:

    <!-- LIVE_SITES:START -->   ... <!-- LIVE_SITES:END -->
    <!-- SHIPPED:START -->      ... <!-- SHIPPED:END -->
    <!-- COUNTERS:START -->     ... <!-- COUNTERS:END -->

Usage:
    GITHUB_TOKEN=... python3 scripts/build_profile.py            # rewrite README.md
    GITHUB_TOKEN=... python3 scripts/build_profile.py --dry-run   # print, don't write

The script is deliberately dependency free (stdlib only) so the GitHub Action
that runs it needs no install step.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

USER = os.environ.get("PROFILE_USER", "knarayanareddy")
# The profile repository is named after the user. Read it from the environment so
# renaming the repo needs no code change.
PROFILE_REPO = os.environ.get("PROFILE_REPO") or USER
API = "https://api.github.com"
README = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md")
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sites.json")

TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

# ---------------------------------------------------------------------------
# Editorial layer. GitHub descriptions are often empty, so a short, honest
# one-liner per project lives here and wins over the API description.
# ---------------------------------------------------------------------------
BLURBS: dict[str, str] = {
    "sallie-returns-ai-agent": "Omnichannel shoe-retail returns pipeline: a 6-node deterministic state machine with 48h stock holds, defect assessment and human supervisor triage",
    "Aeroscribe": "Nine gated stages from literature archaeology to a submission-ready manuscript, every claim traceable to a recorded computation",
    "toolscour": "3D knowledge galaxy and stack architect over 11,000+ open-source AI tools, models, runtimes and skill packs",
    "AI-Arsenal": "Schema-first, Markdown-native encyclopedia of AI engineering — readable by humans, LLMs and agents",
    "AI-Daily": "A calm, curated daily briefing for the AI ecosystem, built on a Scout → Challenge → Agree editorial model",
    "gitscour": "Queryable knowledge base of 50,000+ high-star GitHub repositories, sharded and served free from Pages",
    "Aerorepos": "Curated directory of open-source aerospace engineering projects — aero, propulsion, structures, GNC, space",
    "WebsitedesignandPrompts": "Democratising the paywalled web: reusable landing-page templates with the full build prompts",
    "3dexperimentation": "Pure-code, 60 FPS Canvas animated film studio with generated soundtracks and speech",
    "curiolab": "Two-screen family science episodes where measured experiments, not canned values, branch the story",
    "roomsmith": "Physical-digital escape room whose deterministic engine — not the model — owns puzzle completion",
    "accesshold": "Post-booking accessibility evidence monitoring with explicitly approved disruption recovery",
    "nexttime": "Consented conversation capture, 90-second rehearsal, and functional-language progress tracking",
    "harvestgrid": "Privacy-preserving backyard harvest forecasting and volunteer glean logistics for food pantries",
    "Bunqsy": "Always-on financial guardian: 7-agent risk oracle, proactive interventions, nightly Dream Mode",
    "Autoorg": "Autonomous mission orchestration and hardened agentic infrastructure",
    "Agentcrash": "SAAF policy circuit breaker for support agents — propose, gate, quarantine, restore",
    "SAAF-circuit-breaker": "Policy circuit breaker that quarantines drifting agents and restores a healthy checkpoint",
    "so101-domain-operator": "Domain-scoped SO-101 robot operator: script → voice → perception → verification → ledger",
    "dreamswarm": "Multi-agent orchestration engine for software engineering, written in Rust",
    "LEGACYVAULTV1.0": "Solana-native digital estate executor with a time-delayed, multi-party unlock",
    "keepsake": "A 16×16 on-chain arena where the world — never you — is the attester",
    "ghosthandshake": "Strangers pick the same secret word without saying it, then reveal on Monad",
    "sylva": "Three.js landscape study: a procedural moss-covered root that reacts to the pointer",
    "proofpress-evidence-portal": "Continuous, Scout-led Three.js evidence journey with a constraint-first editorial stage",
    "jointcheck-solder-inspection": "Solder-joint workmanship inspection with proof: OpenCV, Nemotron reasoning, sandbox branching",
    "gridqueue-grid-connection": "Energy grid interconnection navigator and flexibility planner",
    "redflag-eu-compliance": "Pre-flight EU product-safety compliance gate for GPSR Art. 19 and Safety Gate recalls",
    "reflex-physical-ai": "Edge deterministic safety envelope with cloud counterfactual replay for physical AI",
    "Courserefresh": "A course that watches the thing it teaches and rewrites its own lessons when it changes",
    "twitch-codex": "Four independent live-audience, accessibility and broadcaster-control builds for TwitchCon",
    "Magpie": "Autonomous classifieds scout that finds underpriced listings, haggles, and closes the deal",
    "Nimbus": "Solana-native parametric climate cover with deterministic, oracle-driven settlement",
    "idea-dump": "High-volume idea ingestion feeding a daily autonomous project factory",
    "Handy": "Handy is my name and robot is my form",
    "vouwfiets": "Folding-bike explorer built on the open Dutch cycling network",
    "F1Elastichopsworkshack": "Explorable 2023–2024 F1 race workspace on Elasticsearch and Hopsworks",
}

# Not mine to showcase: a study/replica of someone else's project, and a
# hackathon challenge page that is not a deployed app of mine.
EXCLUDE = {"sylva", "onegov2-spatial-assistant"}

# Featured live sites get a hand-written card row in the README, in this order.
FEATURED = [
    "sallie-returns-ai-agent",
    "Aeroscribe",
    "toolscour",
    "AI-Arsenal",
    "AI-Daily",
    "gitscour",
    "Aerorepos",
    "WebsitedesignandPrompts",
    "Bunqsy",
]

LANG_BADGE = {
    "TypeScript": "3178C6",
    "Python": "3776AB",
    "JavaScript": "F7DF1E",
    "Rust": "000000",
    "Go": "00ADD8",
    "Kotlin": "7F52FF",
    "HTML": "E34F26",
    "Shell": "4EAA25",
    "CSS": "1572B6",
    "Java": "007396",
    "C++": "00599C",
}

USER_AGENT = f"{USER}-profile-readme-builder"


def api(path: str):
    """GET a GitHub API path, following pagination when a list comes back."""
    url = path if path.startswith("http") else f"{API}{path}"
    while url:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
        if TOKEN:
            req.add_header("Authorization", f"Bearer {TOKEN}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode())
                link = resp.headers.get("Link", "")
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):
                return None
            raise
        yield payload
        match = re.search(r'<([^>]+)>;\s*rel="next"', link)
        url = match.group(1) if match else None


def api_one(path: str):
    for page in api(path):
        return page
    return None


def fetch_repos() -> list[dict]:
    repos: list[dict] = []
    for page in api(f"/users/{USER}/repos?per_page=100&type=owner&sort=pushed"):
        repos.extend(page)
    return repos


def pages_url(repo: dict) -> tuple[str, bool] | None:
    """Resolve a live-site URL for a repo, or None if nothing is deployed.

    Returns (url, is_github_pages). Many repos repeat their Pages URL in the
    `homepage` field; a non-github.io homepage (Vercel, a custom domain, a VM)
    is treated as the canonical build and labelled as externally hosted.
    """
    if repo.get("fork") or repo["name"] in EXCLUDE:
        return None

    home = (repo.get("homepage") or "").strip()
    # A repo with no Pages flag and no homepage cannot have anything deployed,
    # so skip the extra request (keeps a full refresh to ~40 API calls).
    if not repo.get("has_pages") and not home:
        return None

    on_pages = False
    if repo.get("has_pages"):
        info = api_one(f"/repos/{USER}/{repo['name']}/pages")
        on_pages = isinstance(info, dict) and bool(info.get("html_url"))
        if on_pages and not home:
            home = info["html_url"]

    if home and "github.io" not in home:
        # Custom domain / other host. Only trust it if the repo is deployed at all.
        if on_pages or repo.get("has_pages"):
            return home.rstrip("/") + "/", False
        return None

    if home:
        return home.rstrip("/") + "/", True
    return None


def badge(label: str, color: str, logo: str | None = None) -> str:
    logo_q = f"&logo={logo}&logoColor=white" if logo else ""
    label_q = label.replace(" ", "%20")
    return f"https://img.shields.io/badge/{label_q}-{color}?style=flat-square&labelColor=1a1b27{logo_q}"


def stars_badge(name: str) -> str:
    return f"https://img.shields.io/github/stars/{USER}/{name}?style=flat-square&labelColor=1a1b27&color=58a6ff"


def collect() -> dict:
    repos = fetch_repos()
    own = [r for r in repos if not r["fork"] and r["name"].lower() != PROFILE_REPO.lower()]

    sites = []
    for repo in own:
        resolved = pages_url(repo)
        if not resolved:
            continue
        url, on_pages = resolved
        sites.append(
            {
                "repo": repo["name"],
                "url": url,
                "pages": on_pages,
                "lang": repo.get("language") or "",
                "stars": repo.get("stargazers_count", 0),
                "pushed": (repo.get("pushed_at") or "")[:10],
                "blurb": BLURBS.get(repo["name"]) or (repo.get("description") or "").strip(),
            }
        )

    sites.sort(key=lambda s: (s["pages"], s["pushed"], s["stars"]), reverse=True)

    languages: dict[str, int] = {}
    for repo in own:
        lang = repo.get("language")
        if lang:
            languages[lang] = languages.get(lang, 0) + 1

    profile = api_one(f"/users/{USER}") or {}

    return {
        "followers": profile.get("followers", 0),
        # Total public repos *including* forks and this profile repo. Stored so
        # the hourly gate in update-profile.yml can tell "nothing new was
        # published" from "a repo appeared" with one API call, instead of
        # rebuilding all seven artefacts to find out.
        "public_repos": profile.get("public_repos", 0),
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "repos": len(own),
        "stars": sum(r.get("stargazers_count", 0) for r in own),
        "forks": sum(r.get("forks_count", 0) for r in own),
        "site_count": len(sites),
        "pages_count": sum(1 for site in sites if site["pages"]),
        "languages": sorted(languages.items(), key=lambda kv: kv[1], reverse=True),
        "sites": sites,
    }


def render_featured(data: dict) -> str:
    by_name = {s["repo"]: s for s in data["sites"]}
    rows = []
    for name in FEATURED:
        site = by_name.get(name)
        if not site:
            continue
        stack = f"`{site['lang']}`" if site["lang"] else "—"
        stars = f"★ {site['stars']}" if site["stars"] else "—"
        rows.append(
            f"| 🌐 | [**{site['repo']}**]({site['url']}) · [source](https://github.com/{USER}/{site['repo']}) "
            f"| {stack} | {stars} | {site['blurb']} |"
        )
    return (
        "| | Live site | Stack | Stars | What it does |\n"
        "|:--:|-----------|-------|:-----:|--------------|\n" + "\n".join(rows)
    )


def render_catalogue(data: dict) -> str:
    """Every other live site, grouped into two compact columns."""
    featured = set(FEATURED)
    rest = [s for s in data["sites"] if s["repo"] not in featured]
    if not rest:
        return "_Nothing else deployed yet._"
    half = (len(rest) + 1) // 2
    columns = [rest[:half], rest[half:]]

    tables = []
    for column in columns:
        lines = ["| Live site | Stack |", "|-----------|-------|"]
        for site in column:
            lang = f"`{site['lang']}`" if site["lang"] else "—"
            mark = "" if site["pages"] else " ↗"
            lines.append(f"| [**{site['repo']}**]({site['url']}){mark} | {lang} |")
        tables.append("\n".join(lines))

    while len(tables) < 2:
        tables.append("")
    return (
        "<table>\n<tr>\n"
        f'<td width="50%" valign="top">\n\n{tables[0]}\n\n</td>\n'
        f'<td width="50%" valign="top">\n\n{tables[1]}\n\n</td>\n'
        "</tr>\n</table>"
    )


def render_shipped(data: dict) -> str:
    recent = data["sites"][:8]
    if not recent:
        return "_Nothing shipped yet._"
    icons = ["🚀", "🛰️", "🧠", "🧪", "🔭", "⚙️", "🛡️", "🎛️"]
    lines = []
    for icon, site in zip(icons, recent):
        lines.append(
            f"- {icon} **[`{site['repo']}`](https://github.com/{USER}/{site['repo']})** — "
            f"[live]({site['url']}) · pushed {site['pushed']}"
        )
    return "\n".join(lines)


def render_counters(data: dict) -> str:
    """One block, one set of numbers.

    Every figure the README states is emitted here from data/sites.json, so the
    header badges, the counters and the prose cannot drift apart: a number that
    is not derived from this file does not belong in the README.
    """
    langs = " · ".join(f"**{lang}** {count}" for lang, count in data["languages"][:6])
    followers = data["followers"]
    follower_word = "follower" if followers == 1 else "followers"
    return (
        f"**{data['pages_count']} live GitHub Pages sites** · "
        f"**{data['site_count']} live deployments** · "
        f"**{data['repos']} original repositories** · "
        f"**{data['stars']} stars** · **{data['forks']} forks** · "
        f"**{followers} {follower_word}**\n\n"
        f"<sub>{langs}</sub>"
    )


VOLATILE = re.compile(r"<!-- Last updated: .*?-->")


def substantive(text: str) -> str:
    """Text with the bits that change on every run removed."""
    return VOLATILE.sub("", text)


def replace_block(text: str, name: str, body: str) -> str:
    pattern = re.compile(
        rf"(<!-- {name}:START -->)(.*?)(<!-- {name}:END -->)",
        re.DOTALL,
    )
    if not pattern.search(text):
        print(f"warning: markers for {name} not found in README.md", file=sys.stderr)
        return text
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(3)}", text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data = collect()
    print(f"collected {data['repos']} repos, {data['site_count']} live sites, {data['stars']} stars", file=sys.stderr)

    with open(README, encoding="utf-8") as handle:
        readme = handle.read()

    readme = replace_block(readme, "COUNTERS", render_counters(data))
    readme = replace_block(readme, "LIVE_SITES", render_featured(data))
    readme = replace_block(readme, "SITE_CATALOGUE", render_catalogue(data))
    readme = replace_block(readme, "SHIPPED", render_shipped(data))
    # Only move the stamp when something else actually changed. A timestamp that
    # ticks while the numbers do not makes the page look refreshed when it is
    # merely rebuilt; the footer says "daily" explicitly instead.
    existing = re.search(r"<!-- Last updated: (.*?) -->", readme)
    if existing and substantive(readme.replace(existing.group(0), "")) == substantive(readme):
        # nothing but the stamp differs from what is already committed: keep it
        data["generated"] = existing.group(1)
    readme = re.sub(r"<!-- Last updated: .*?-->", f"<!-- Last updated: {data['generated']} -->", readme)
    # Rewrite the profile-repo segment of any snake image URL to the current name.
    # The README was committed with a literal name, so a placeholder-only swap
    # would silently do nothing after a rename.
    readme = re.sub(
        rf"(raw\.githubusercontent\.com/[^/]+/)[^/]+(/output/)",
        rf"\g<1>{PROFILE_REPO}\g<2>",
        readme,
    )

    if args.dry_run:
        print(readme)
        return 0

    old_readme = ""
    if os.path.exists(README):
        with open(README, encoding="utf-8") as handle:
            old_readme = handle.read()
    old_data = None
    if os.path.exists(DATA):
        try:
            with open(DATA, encoding="utf-8") as handle:
                old_data = json.load(handle)
        except json.JSONDecodeError:
            old_data = None

    new_data = dict(data)
    if old_data is not None:
        old_data = {k: v for k, v in old_data.items() if k != "generated"}
        new_data_cmp = {k: v for k, v in new_data.items() if k != "generated"}
        # Round-trip through JSON so tuples compare equal to the lists on disk.
        same_data = old_data == json.loads(json.dumps(new_data_cmp))
        unchanged = substantive(old_readme) == substantive(readme) and same_data
        if unchanged:
            print("nothing changed; leaving README.md and data/sites.json alone", file=sys.stderr)
            return 0

    with open(README, "w", encoding="utf-8") as handle:
        handle.write(readme)

    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    with open(DATA, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    print(f"wrote README.md and {os.path.relpath(DATA)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
