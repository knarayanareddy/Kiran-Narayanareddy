import { test } from "node:test";
import assert from "node:assert/strict";
import {
  THEMES, buildGrid, level, makeSnake, step, turn, DIRS, autoMove,
  openArea, foodCells, mulberry32, project, blockAt, isReverse,
} from "../web/core.js";

/** A year-shaped calendar with deterministic gaps, so tests never depend on live data. */
function calendar(days = 371) {
  const out = [];
  const start = Date.UTC(2025, 10, 6);
  const rng = mulberry32(42);
  for (let i = 0; i < days; i += 1) {
    const d = new Date(start + i * 86400000);
    const count = rng() < 0.35 ? 0 : Math.floor(rng() * 12);
    out.push({ date: d.toISOString().slice(0, 10), count });
  }
  return out;
}

const grid = buildGrid(calendar());

test("grid is seven rows and one column per week", () => {
  assert.equal(grid.rows, 7);
  assert.ok(grid.cols >= 53 && grid.cols <= 54, `cols=${grid.cols}`);
  assert.equal(grid.cells.length, grid.cols * 7);
});

test("first row is Monday and no day is invented", () => {
  const first = grid.weeks[0].find((c) => c.date);
  assert.ok(first, "the first week must contain at least one real day");
  const dow = (new Date(first.date + "T00:00:00Z").getUTCDay() + 6) % 7;
  assert.equal(dow, first.row, "a day must sit on its real weekday row");
  const real = grid.cells.filter((c) => c.date !== null);
  assert.equal(real.length, calendar().length);
});

test("totals and peak match the source calendar", () => {
  const src = calendar();
  assert.equal(grid.total, src.reduce((s, d) => s + d.count, 0));
  assert.equal(grid.peak, Math.max(...src.map((d) => d.count)));
});

test("levels are monotone and bounded", () => {
  // thresholds are 0.16 / 0.36 / 0.66 of the peak, so these are the real buckets
  assert.deepEqual([0, 1, 9, 20, 34].map((c) => level(c, 50)), [0, 1, 2, 3, 4]);
  for (const cell of grid.cells) assert.ok(cell.alpha >= 0 && cell.alpha <= 4);
});

test("snake grows when it eats and scores by the day's count", () => {
  const g = buildGrid([{ date: "2026-01-05", count: 9 }]);
  let snake = makeSnake({ col: 0, row: 0 });
  snake.dir = DIRS.right;
  const food = [{ col: 1, row: 0, count: 9 }];
  const before = snake.body.length;
  const { snake: after, ate } = step(snake, { ...g, cols: 5, rows: 7 }, food);
  assert.equal(ate.count, 9);
  assert.equal(after.score, 9);
  assert.equal(after.growth, 2);
  // next tick should not shrink the tail, because growth is pending
  const { snake: after2 } = step(after, { ...g, cols: 5, rows: 7 }, []);
  assert.equal(after2.body.length, before + 1);
});

test("walls are toroidal and the snake comes out the other side", () => {
  const g = { cols: 4, rows: 7 };
  let snake = makeSnake({ col: 3, row: 0 });
  snake.dir = DIRS.right;
  const { snake: after, died } = step(snake, g, []);
  assert.equal(died, false);
  // col 3 + 1 wraps to 0
  assert.equal(after.body[0].col, 0);
});

test("running into itself kills the snake", () => {
  const g = { cols: 10, rows: 10 };
  let snake = {
    body: [
      { col: 5, row: 5 }, { col: 5, row: 6 }, { col: 6, row: 6 }, { col: 6, row: 5 }, { col: 6, row: 4 },
    ],
    dir: DIRS.right,
    growth: 0,
    alive: true,
    eaten: 0,
    score: 0,
  };
  // step right from (5,5) lands on (6,5), which the body occupies
  const { died } = step(snake, g, []);
  assert.equal(died, true);
});

test("a 180-degree turn is ignored", () => {
  const snake = makeSnake({ col: 2, row: 2 });
  const turned = turn(snake, DIRS.left);
  assert.deepEqual(turned.dir, snake.dir);
  assert.ok(isReverse(DIRS.right, DIRS.left));
  assert.ok(!isReverse(DIRS.right, DIRS.up));
});

test("autopilot finds food without dying for 300 ticks", () => {
  const g = grid;
  let food = foodCells(g).slice(0, 40);
  let snake = makeSnake({ col: 0, row: 3 });
  const rng = mulberry32(11);
  let eaten = 0;
  for (let t = 0; t < 300; t += 1) {
    snake = turn(snake, autoMove(snake, g, food, rng));
    const res = step(snake, g, food);
    snake = res.snake;
    assert.ok(snake.alive, `autopilot died at tick ${t}`);
    if (res.ate) {
      eaten += 1;
      food = food.filter((f) => !(f.col === res.ate.col && f.row === res.ate.row));
      if (!food.length) food = foodCells(g).slice(0, 40);
    }
  }
  assert.ok(eaten > 0, "autopilot should eat something");
  assert.ok(snake.body.length > 3, "and it should have grown");
});

test("openArea shrinks as the body fills the board", () => {
  const g = { cols: 6, rows: 6 };
  const small = { body: [{ col: 0, row: 0 }] };
  const big = { body: Array.from({ length: 18 }, (_, i) => ({ col: i % 6, row: Math.floor(i / 6) })) };
  assert.ok(openArea(small, g, { col: 0, row: 0 }, DIRS.right) > openArea(big, g, { col: 0, row: 2 }, DIRS.right));
});

test("projection stays inside a 900x430 canvas for a full year", () => {
  for (const cell of grid.cells) {
    const { x, y } = project(cell.col, cell.row);
    assert.ok(x > 0 && x < 890, `x=${x} at ${cell.date}`);
    assert.ok(y > 60 && y < 330, `y=${y} at ${cell.date}`);
  }
});

test("blockAt picks the day under the pointer, and nothing in empty space", () => {
  const cell = grid.cells.find((c) => c.count > 0 && c.col === 10);
  const { x, y } = project(cell.col, cell.row);
  const hit = blockAt(x + 2, y - 2, grid);
  assert.ok(hit, "a click on a column must hit a day");
  assert.equal(typeof hit.date, "string");
  assert.equal(blockAt(2, 2, grid), null, "empty sky is not a day");
});

test("every theme has the keys the renderer needs", () => {
  const required = ["bg", "grid", "text", "muted", "snake", "snakeDark", "head", "food", "accent"];
  for (const [key, theme] of Object.entries(THEMES)) {
    for (const prop of required) assert.ok(theme[prop], `${key} is missing ${prop}`);
    assert.equal(theme.food.length, 2, `${key} needs two food colours`);
  }
});
