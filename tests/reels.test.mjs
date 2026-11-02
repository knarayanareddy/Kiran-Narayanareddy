// Guards the honesty of the demo reels, not their pixels.
//
// The whole value of a reel is that the README says what it is. These tests fail
// if that claim quietly disappears: if a caption stops saying "recorded", if the
// builder starts synthesising frames, or if a generated reel breaks the 5 MB
// ceiling that GitHub's image proxy enforces (over it, the image is simply a
// broken icon - the most common way README demos die).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync, readdirSync, statSync } from "node:fs";
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

test("generated reels actually animate and loop", () => {
  const dir = `${root}assets/reels`;
  if (!existsSync(dir)) return;
  const gifs = readdirSync(dir).filter((n) => n.endsWith(".gif"));
  if (!gifs.length) return;
  for (const name of gifs) {
    const probe = execFileSync("ffprobe", [
      "-v", "error", "-select_streams", "v:0",
      "-count_frames", "-show_entries", "stream=nb_read_frames",
      "-of", "csv=p=0", `${dir}/${name}`,
    ], { encoding: "utf8" }).trim();
    assert.ok(Number(probe) > 1, `${name} has ${probe} frame(s); a still is not a reel`);
  }
});

test("the reel workflow records on a real browser and asserts ffmpeg", () => {
  assert.match(workflow, /playwright install --with-deps chromium/);
  assert.match(workflow, /ffmpeg -version/);
  assert.match(workflow, /scripts\/build_reel\.py/);
});
