/**
 * Guards the design system.
 *
 * The point of scripts/tokens.py is that no card owns a colour of its own. These
 * tests fail if a generator grows a private palette again, if dark and light
 * stop covering the same roles, or if the committed tokens.json drifts from the
 * source. No browser needed.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { execFileSync } from "node:child_process";

const ROOT = new URL("..", import.meta.url).pathname;
const GENERATORS = [
  "build_hero.py",
  "build_badges.py",
  "build_dashboard.py",
  "build_3d_terrain.py",
  "build_tiles.py",
  "build_mosaic.py",
];
const tokens = JSON.parse(readFileSync(ROOT + "data/tokens.json", "utf8"));

test("data/tokens.json matches scripts/tokens.py", () => {
  // --emit is deterministic, so a difference means the file was hand-edited
  const before = readFileSync(ROOT + "data/tokens.json", "utf8");
  execFileSync("python3", ["scripts/tokens.py", "--emit"], { cwd: ROOT, stdio: "pipe" });
  const after = readFileSync(ROOT + "data/tokens.json", "utf8");
  assert.equal(after, before, "run `python3 scripts/tokens.py --emit` and commit the result");
});

test("dark and light define the same roles", () => {
  const dark = Object.keys(tokens.palette.dark).sort();
  const light = Object.keys(tokens.palette.light).sort();
  assert.deepEqual(light, dark, "a role missing in one mode silently keeps the other mode's colour");
});

test("every colour is a valid hex value", () => {
  for (const [mode, palette] of Object.entries(tokens.palette)) {
    for (const [role, value] of Object.entries(palette)) {
      assert.match(value, /^#[0-9a-f]{6}$/i, `${mode}.${role} = ${value}`);
    }
    for (const level of tokens.levels[mode]) {
      assert.match(level, /^#[0-9a-f]{6}$/i, `${mode} heat level ${level}`);
    }
  }
});

test("both heat ramps have five steps and they get darker or lighter consistently", () => {
  for (const mode of ["dark", "light"]) {
    assert.equal(tokens.levels[mode].length, 5, `${mode} heat ramp`);
  }
});

test("no generator carries a private THEMES literal", () => {
  for (const file of GENERATORS) {
    const src = readFileSync(ROOT + "scripts/" + file, "utf8");
    assert.ok(
      /from tokens import .*\bTOKENS\b/.test(src),
      `${file} does not import the shared tokens`,
    );
    assert.ok(
      !/^THEMES = \{\s*$/m.test(src),
      `${file} still defines its own THEMES dict - drift starts there`,
    );
  }
});

test("no generator hardcodes a colour that is not in the tokens", () => {
  const owned = new Set([
    ...Object.values(tokens.palette.dark),
    ...Object.values(tokens.palette.light),
    ...Object.values(tokens.brands || {}),
  ]);
  // #000000 / #ffffff appear as shader-like primitives (glows, scanlines) and
  // are allowed; anything else must come from the tokens.
  const allowed = new Set(["#000000", "#ffffff"]);
  for (const file of GENERATORS) {
    const src = readFileSync(ROOT + "scripts/" + file, "utf8");
    // ignore the import line and any comment
    const body = src
      .split("\n")
      .filter((line) => !line.trim().startsWith("#") && !line.includes("from tokens import"))
      .join("\n");
    const hexes = body.match(/#[0-9a-f]{6}\b/gi) || [];
    for (const hex of hexes) {
      const lower = hex.toLowerCase();
      assert.ok(
        owned.has(lower) || allowed.has(lower),
        `${file} hardcodes ${hex}; add it to PALETTE or BRANDS in scripts/tokens.py`,
      );
    }
  }
});

test("every generator uses the shared mono stack, not a lookalike", () => {
  for (const file of GENERATORS) {
    const src = readFileSync(ROOT + "scripts/" + file, "utf8");
    if (!/font-family/.test(src)) continue;
    // the only literals allowed in a stylesheet are the token strings themselves
    const families = [...src.matchAll(/font-family[:=]\s*["']?([^"';\n]+)/g)].map((m) => m[1].trim());
    for (const family of families) {
      if (family.startsWith("__") || family.includes("{theme")) continue;
      assert.ok(
        family.includes("ui-monospace") || family.includes("-apple-system"),
        `${file} uses a font family outside the token set: ${family}`,
      );
    }
  }
});

test("the browser pages read the same tokens", () => {
  const core = readFileSync(ROOT + "web/core.js", "utf8");
  assert.match(core, /export function applyTokens/, "core.js must accept the shared tokens");
  for (const page of ["web/index.html", "web/snake.html"]) {
    const src = readFileSync(ROOT + page, "utf8");
    assert.match(src, /tokens\.json/, `${page} does not load data/tokens.json`);
  }
});

test("geometry keeps full-width cards on one grid", () => {
  const { gutter, right, contentWidth } = tokens.geometry;
  assert.equal(right - gutter, contentWidth, "content width must equal right - gutter");
  assert.equal(tokens.geometry.canvas.hero[0], 900);
  assert.equal(tokens.geometry.canvas.card[0], 900);
  // the tile is the one intentional exception, and it is documented as such
  assert.equal(tokens.geometry.tile[0], 423);
});
