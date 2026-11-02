/**
 * Guards the links between the profile README and the interactive pages.
 *
 * The dashboard and the terrain are only static <img> cards inside the README —
 * GitHub strips scripts, styles and pointer events, so the interactive build has
 * to live on Pages and be linked by hand. Twice now the README has pointed that
 * link at a host that does not serve the pages. These tests read the README and
 * the Pages workflow as text and fail if the link drifts again. No browser.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";

const ROOT = new URL("..", import.meta.url).pathname;
const readme = readFileSync(ROOT + "README.md", "utf8");
const pages = readFileSync(ROOT + ".github/workflows/pages.yml", "utf8");

/** The Pages site the workflow publishes to, without a trailing slash. */
const SITE = "https://knarayanareddy.github.io/knarayanareddy";
/** Hosts that have never served the interactive pages. */
const DEAD_HOSTS = ["kiranreddy.nl/dashboards", "kiranreddy.nl/snake"];

function block(text, name) {
  const start = text.indexOf(`<!-- ${name}:START -->`);
  const end = text.indexOf(`<!-- ${name}:END -->`);
  assert.ok(start !== -1 && end !== -1, `missing ${name} marker block`);
  return text.slice(start, end);
}

test("README never links the pages at a host that does not serve them", () => {
  for (const host of DEAD_HOSTS) {
    assert.ok(
      !readme.includes(host),
      `README still links ${host}; the interactive pages are served from ${SITE}`,
    );
  }
});

test("the interactive block exists and links the dashboard, snake and reel", () => {
  const text = block(readme, "INTERACTIVE");
  assert.ok(text.includes(`href="${SITE}/"`), "dashboard link missing or wrong host");
  assert.ok(text.includes(`href="${SITE}/snake.html"`), "snake link missing or wrong host");
  assert.ok(text.includes(`href="${SITE}/reel.html"`), "reel link missing or wrong host");
});

test("every page the interactive block links is actually published", () => {
  const text = block(readme, "INTERACTIVE");
  const linked = [...text.matchAll(new RegExp(`href="${SITE}/([^"]*)"`, "g"))];
  assert.ok(linked.length >= 3, "expected dashboard, snake and reel links");
  for (const [, path] of linked) {
    const file = path === "" || path.endsWith("/") ? "index.html" : path;
    assert.ok(existsSync(ROOT + "web/" + file), `README links ${file}, but web/${file} does not exist`);
  }
});

test("the snake caption points at the published page", () => {
  assert.ok(
    readme.includes(`](${SITE}/snake.html)`),
    `the "Play it yourself" link must point at ${SITE}/snake.html`,
  );
});

test("Pages publishes the pages and the data they fetch", () => {
  assert.match(pages, /cp -r web\/\*\s+_site\//, "web/* must land at the site root");
  assert.match(pages, /_site\/data/, "the JSON the pages fetch must be published under /data/");
  assert.match(pages, /tokens\.json/, "tokens.json drives the palette; it must be published");
});

test("Pages fails loudly when a required artefact is missing", () => {
  assert.match(pages, /::error::/, "a missing file should surface as an error annotation");
  for (const needed of ["index.html", "snake.html", "reel.html", "data/stats.json", "data/tokens.json"]) {
    assert.ok(pages.includes(needed), `the publish guard does not check _site/${needed}`);
  }
});
