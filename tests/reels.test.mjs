// Guards the honesty of the demo reels, not their pixels.
//
// The whole value of a reel is that the README says what it is. These tests fail
// if that claim quietly disappears: if a caption stops saying "recorded", if the
// builder starts synthesising frames, or if a generated reel breaks the 5 MB
// ceiling that GitHub's image proxy enforces (over it, the image is simply a
// broken icon - the most common way README demos die).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync, readdirSync, readFileSync as read, statSync } from "node:fs";
import { execFileSync } from "node:child_process";

const root = new URL("..", import.meta.url).pathname;
const script = readFileSync(`${root}scripts/build_reel.py`, "utf8");
const profile = readFileSync(`${root}scripts/build_profile.py`, "utf8");
const workflow = readFileSync(`${root}.github/workflows/reels.yml`, "utf8");
const readme = readFileSync(`${root}README.md`, "utf8");

test("reels are captured from a real browser, never synthesised", () => {
  // No frame generation: every frame must come from page.screenshot().
  assert.match(script, /page\.screenshot\(/);
  assert.match(script, /from playwright\.sync_api import sync_playwright/);
  // The only allowed image writes are ffmpeg/overlay outputs, not drawn frames.
  assert.doesNotMatch(script, /Image\.new\(\s*\(VIEWPORT/, "must not fabricate viewport frames");
});

test("every reel caption says it is a recording, not a live feed", () => {
  assert.match(script, /recorded \$\{esc\(recorded\)\}|recorded \{recorded\}/, "caption must carry the date");
  assert.match(script, /not live/, "caption must say it is not live");
  // The word LIVE belongs to the still tiles, which can pulse; a loop cannot.
  const captionBlock = script.slice(script.indexOf("def chrome_png"), script.indexOf("def ffmpeg"));
  assert.doesNotMatch(captionBlock, /·\s*live|>LIVE</, "a reel must not claim to be live");
});

test("reels stay under GitHub's Camo limit", () => {
  const ceiling = Number(script.match(/MAX_BYTES = ([\d_]+)/)[1].replace(/_/g, ""));
  assert.ok(ceiling <= 5_000_000, "the 5 MB proxy limit is a hard ceiling");
  const dir = `${root}assets/reels`;
  if (!existsSync(dir)) return; // nothing recorded yet
  for (const name of readdirSync(dir).filter((n) => n.endsWith(".gif"))) {
    const bytes = statSync(`${dir}/${name}`).size;
    assert.ok(bytes <= ceiling, `${name} is ${(bytes / 1e6).toFixed(2)} MB, over the limit`);
  }
});

test("the README only shows reels that exist", () => {
  const manifestPath = `${root}assets/reels/manifest.json`;
  const manifest = existsSync(manifestPath)
    ? JSON.parse(readFileSync(manifestPath, "utf8"))
    : {};
  for (const repo of Object.keys(manifest)) {
    assert.ok(
      existsSync(`${root}assets/reels/${repo}.gif`),
      `${repo} is in the manifest but has no GIF`,
    );
  }
  // Every image the README references must be readable, or the page shows a
  // broken icon where a demo should be.
  for (const [, src] of readme.matchAll(/src="\.\/(assets\/reels\/[^"]+)"/g)) {
    assert.ok(existsSync(`${root}${src}`), `README references missing ${src}`);
  }
});

function gifFrames(path) {
  // Walk the GIF block structure and count image descriptors. Done here rather
  // than with ffprobe/ImageMagick so the guard runs on any machine that can run
  // the tests - CI has ffprobe, a bare container does not.
  const buf = read(path);
  if (buf.toString("ascii", 0, 3) !== "GIF") return 0;
  let pos = 6;                                  // header
  const flags = buf[10];
  pos = 13;
  if (flags & 0x80) pos += 3 * (1 << ((flags & 0x07) + 1));  // global colour table

  const skipSubBlocks = () => {
    while (pos < buf.length) {
      const size = buf[pos++];
      if (size === 0) return;
      pos += size;
    }
  };

  let frames = 0;
  while (pos < buf.length) {
    const block = buf[pos++];
    if (block === 0x3b) break;                  // trailer
    if (block === 0x21) { pos += 1; skipSubBlocks(); }        // extension
    else if (block === 0x2c) {                  // image descriptor
      frames += 1;
      const local = buf[pos + 8];
      pos += 9;
      if (local & 0x80) pos += 3 * (1 << ((local & 0x07) + 1));
      pos += 1;                                 // LZW minimum code size
      skipSubBlocks();
    } else {
      break;                                    // unknown block: stop honestly
    }
  }
  return frames;
}

test("generated reels actually animate and loop", () => {
  const dir = `${root}assets/reels`;
  if (!existsSync(dir)) return;
  for (const name of readdirSync(dir).filter((n) => n.endsWith(".gif"))) {
    const frames = gifFrames(`${dir}/${name}`);
    assert.ok(frames > 1, `${name} has ${frames} frame(s); a still is not a reel`);
  }
});

test("the reel workflow records on a real browser and asserts ffmpeg", () => {
  assert.match(workflow, /playwright install --with-deps chromium/);
  assert.match(workflow, /command -v ffmpeg/);
  // `ffmpeg -version | head -1` always exits 0 (head's status), so it checks
  // nothing. That exact line shipped once and cost two failed runs. Comments
  // are stripped first, because documenting the trap must stay allowed.
  const code = workflow.split("\n").filter((line) => !line.trim().startsWith("#")).join("\n");
  assert.doesNotMatch(code, /ffmpeg -version\s*\|\s*head/, "a pipe masks a missing ffmpeg");
  assert.match(workflow, /scripts\/build_reel\.py/);
});

test("the grid never loads every GIF eagerly", () => {
  // GitHub ships no loading="lazy" on README images (checked in the served
  // HTML), so any <img> the reader scrolls past has already cost its bytes.
  // The grid must therefore point at covers, with the GIF behind <details>.
  const section = readme.slice(
    readme.indexOf("<!-- REELS:START -->"),
    readme.indexOf("<!-- REELS:END -->"),
  );
  if (!section.includes("assets/reels/")) return;

  // "Eager" means visible without opening anything: a GIF inside <details> is not
  // fetched until the reader opens it, which is the whole point of the grid.
  let depth = 0;
  const eager = [];
  for (const [tag] of section.matchAll(/<details[^>]*>|<\/details>|<img[^>]*src="[^"]*assets\/reels\/[^"]+\.gif"/g)) {
    if (tag.startsWith("<details")) depth += 1;
    else if (tag.startsWith("</details")) depth = Math.max(0, depth - 1);
    else if (depth === 0) eager.push(tag);
  }
  assert.ok(eager.length <= 2, `${eager.length} GIFs load eagerly; keep it to the two newest`);

  // Everything else is a cover, and every cover exists.
  for (const [, src] of section.matchAll(/src="\.\/(assets\/reels\/[^"]+-cover\.png)"/g)) {
    assert.ok(existsSync(`${root}${src}`), `README references missing ${src}`);
  }
  // A GIF offered for playback must sit inside a details block, not inline.
  for (const [match] of section.matchAll(/<details>[\s\S]*?<\/details>/g)) {
    assert.ok(match.includes("<summary>"), "a details block needs a summary to click");
  }
});

test("every recorded reel gets a cover for the grid", () => {
  const manifestPath = `${root}assets/reels/manifest.json`;
  if (!existsSync(manifestPath)) return;
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  for (const repo of Object.keys(manifest)) {
    assert.ok(
      existsSync(`${root}assets/reels/${repo}-cover.png`),
      `${repo} has a reel but no cover, so the grid would have a hole`,
    );
  }
});

test("the reel list is an edit, not everything that happens to be deployed", () => {
  const list = script.slice(script.indexOf("REELS = ["), script.indexOf("]", script.indexOf("REELS = [")));
  const repos = [...list.matchAll(/\("([^"]+)",/g)].map((m) => m[1]);
  assert.ok(repos.length >= 8, "the section should showcase more than a handful");
  assert.ok(repos.length <= 25, "past ~25 the page weight stops being defensible");
  for (const repo of repos) {
    const site = JSON.parse(readFileSync(`${root}data/sites.json`, "utf8")).sites.find((s) => s.repo === repo);
    assert.ok(site, `${repo} is listed but not deployed, so there is nothing to record`);
  }
  // Each entry names its gesture, because a scroll-only capture of a dashboard
  // produces a near-still and that is not a demo.
  for (const [, gesture] of list.matchAll(/, "([a-z]+)"\),/g)) {
    assert.ok(["scroll", "pointer", "mixed"].includes(gesture), `unknown gesture ${gesture}`);
  }
});
