/* Shared simulation + projection logic for the interactive profile.
 *
 * Plain ES module, no dependencies, no bundler: it has to run in a browser from
 * a static host (kiranreddy.nl) and under `node --test` in CI. Everything that
 * can be wrong is a pure function here, so the tests can hold it to account
 * without a DOM.
 */

export const THEMES = {
  cyberpunk: {
    name: "Cyberpunk",
    bg: "#07070f", grid: "#12122a", text: "#e8e8ff", muted: "#8b8bb0",
    snake: "#00ff66", snakeDark: "#00331a", head: "#eaffef",
    food: ["#ff007f", "#00f2fe"], accent: "#00f2fe", glow: "#ff007f",
  },
  matrix: {
    name: "Matrix",
    bg: "#050a05", grid: "#0d1f0d", text: "#d4ffd4", muted: "#63a363",
    snake: "#39d353", snakeDark: "#0b2a12", head: "#f0fff0",
    food: ["#7ee787", "#26a641"], accent: "#39d353", glow: "#26a641",
  },
  amber: {
    name: "Amber terminal",
    bg: "#0d0904", grid: "#241705", text: "#ffe9c7", muted: "#a8814a",
    snake: "#ffb000", snakeDark: "#3a2600", head: "#fff5e0",
    food: ["#fcee0a", "#ff7b00"], accent: "#ffb000", glow: "#ff7b00",
  },
  cyan: {
    name: "Neon cyan",
    bg: "#04090f", grid: "#0c1f2e", text: "#dff5ff", muted: "#5a8ba3",
    snake: "#00f2fe", snakeDark: "#002b33", head: "#effeff",
    food: ["#4facfe", "#a371f7"], accent: "#00f2fe", glow: "#4facfe",
  },
  light: {
    name: "Light",
    bg: "#ffffff", grid: "#e6ebf1", text: "#0d1117", muted: "#57606a",
    snake: "#1a7f37", snakeDark: "#d7f0dd", head: "#0b3d1c",
    food: ["#0969da", "#8250df"], accent: "#0969da", glow: "#8250df",
  },
};

/* ------------------------------------------------------------------ grid --- */

/** Seven rows, one column per week. `count` is that day's contributions. */
export function buildGrid(calendar) {
  const days = [...calendar].sort((a, b) => (a.date < b.date ? -1 : 1));
  if (!days.length) return { cols: 0, rows: 7, cells: [], weeks: [], total: 0, peak: 0 };
  const peak = Math.max(1, ...days.map((d) => d.count));
  const cells = [];
  // pad the first week so row 0 is always Monday, like the contributions graph
  const firstDow = (new Date(days[0].date + "T00:00:00Z").getUTCDay() + 6) % 7;
  let index = 0;
  const weeks = [];
  for (let col = 0; col < 60; col += 1) {
    const week = [];
    for (let row = 0; row < 7; row += 1) {
      let day = null;
      if (col === 0 && row < firstDow) {
        day = null;
      } else if (index < days.length) {
        day = days[index];
        index += 1;
      }
      const cell = {
        col,
        row,
        date: day ? day.date : null,
        count: day ? day.count : 0,
        alpha: day ? level(day.count, peak) : 0,
      };
      cells.push(cell);
      week.push(cell);
    }
    weeks.push(week);
    if (index >= days.length) break;
  }
  return {
    cols: weeks.length,
    rows: 7,
    cells,
    weeks,
    total: days.reduce((sum, d) => sum + d.count, 0),
    peak,
  };
}

export function level(count, peak) {
  if (count <= 0) return 0;
  const ratio = count / Math.max(peak, 1);
  if (ratio >= 0.66) return 4;
  if (ratio >= 0.36) return 3;
  if (ratio >= 0.16) return 2;
  return 1;
}

/* ----------------------------------------------------------------- snake --- */

/** Cells the snake may occupy: every real day, and only those with a commit. */
export function foodCells(grid) {
  return grid.cells.filter((c) => c.count > 0).map((c) => ({ col: c.col, row: c.row, count: c.count }));
}

export function makeSnake(start) {
  const head = start ?? { col: 0, row: 3 };
  return {
    body: [head, { col: head.col, row: head.row }, { col: head.col, row: head.row }],
    dir: { col: 1, row: 0 },
    growth: 0,
    alive: true,
    eaten: 0,
    score: 0,
  };
}

export const DIRS = {
  up: { col: 0, row: -1 },
  down: { col: 0, row: 1 },
  left: { col: -1, row: 0 },
  right: { col: 1, row: 0 },
};

export function isReverse(dir, next) {
  return dir.col + next.col === 0 && dir.row + next.row === 0;
}

export function turn(snake, next) {
  if (!snake.alive) return snake;
  if (isReverse(snake.dir, next)) return { ...snake, dir: snake.dir };
  return { ...snake, dir: next };
}

/**
 * One logic tick. Toroidal wrap, self-collision kills, growth on food.
 * Returns a NEW snake plus what happened, so callers stay pure and testable.
 */
export function step(snake, grid, food, opts = {}) {
  const wrap = opts.wrap !== false;
  if (!snake.alive) return { snake, ate: null, died: false };

  let col = snake.body[0].col + snake.dir.col;
  let row = snake.body[0].row + snake.dir.row;

  if (wrap) {
    col = (col + grid.cols) % grid.cols;
    row = (row + grid.rows) % grid.rows;
  } else if (col < 0 || row < 0 || col >= grid.cols || row >= grid.rows) {
    return { snake: { ...snake, alive: false }, ate: null, died: true };
  }

  const hitsSelf = snake.body.some(
    (seg, i) => i < snake.body.length - (snake.growth > 0 ? 0 : 1) && seg.col === col && seg.row === row,
  );
  if (hitsSelf) return { snake: { ...snake, alive: false }, ate: null, died: true };

  const head = { col, row };
  const body = [head, ...snake.body];
  if (snake.growth > 0) {
    snake = { ...snake, growth: snake.growth - 1 };
  } else {
    body.pop();
  }

  const eaten = food ? food.find((f) => f.col === col && f.row === row) : null;
  const next = {
    ...snake,
    body,
    eaten: snake.eaten + (eaten ? 1 : 0),
    score: snake.score + (eaten ? eaten.count : 0),
    growth: snake.growth + (eaten ? 2 : 0),
    alive: true,
  };
  return { snake: next, ate: eaten, died: false };
}

/**
 * Deterministic autopilot: greedy BFS toward the nearest food, with a flood-fill
 * guard so it refuses a move that would seal it into a pocket. Deterministic on
 * purpose — a seeded RNG and no Math.random means the tests can assert on it.
 */
export function autoMove(snake, grid, food, rng = mulberry32(7)) {
  if (!snake.alive || !food.length) return snake.dir;
  const occupied = new Set(snake.body.map((s) => `${s.col},${s.row}`));
  const start = snake.body[0];
  const goals = new Set(food.map((f) => `${f.col},${f.row}`));

  // BFS over free cells, wrapped
  const queue = [start];
  const prev = new Map([[`${start.col},${start.row}`, null]]);
  let found = null;
  while (queue.length) {
    const cur = queue.shift();
    const key = `${cur.col},${cur.row}`;
    if (goals.has(key) && (cur.col !== start.col || cur.row !== start.row)) {
      found = key;
      break;
    }
    for (const d of Object.values(DIRS)) {
      const col = (cur.col + d.col + grid.cols) % grid.cols;
      const row = (cur.row + d.row + grid.rows) % grid.rows;
      const k = `${col},${row}`;
      if (prev.has(k) || occupied.has(k)) continue;
      prev.set(k, key);
      queue.push({ col, row });
    }
  }

  const candidates = Object.values(DIRS).filter((d) => {
    const col = (start.col + d.col + grid.cols) % grid.cols;
    const row = (start.row + d.row + grid.rows) % grid.rows;
    return !occupied.has(`${col},${row}`);
  });
  if (!candidates.length) return snake.dir;

  if (found) {
    // walk back to the first step of the path
    let node = found;
    while (prev.get(node) && prev.get(prev.get(node)) !== null) node = prev.get(node);
    const [col, row] = node.split(",").map(Number);
    const dir = { col: col - start.col, row: row - start.row };
    // normalise across the wrap
    if (dir.col > 1) dir.col -= grid.cols;
    if (dir.col < -1) dir.col += grid.cols;
    if (dir.row > 1) dir.row -= grid.rows;
    if (dir.row < -1) dir.row += grid.rows;
    const safe = candidates.some((d) => d.col === dir.col && d.row === dir.row);
    if (safe && openArea(snake, grid, start, dir) >= snake.body.length) return dir;
  }
  // fall back: the roomiest legal neighbour
  let best = candidates[0];
  let bestArea = -1;
  for (const d of candidates) {
    const area = openArea(snake, grid, start, d);
    if (area > bestArea) {
      bestArea = area;
      best = d;
    }
  }
  return best;
}

/** Flood fill: how much room is reachable if we step one cell in `dir`? */
export function openArea(snake, grid, start, dir) {
  const occupied = new Set(snake.body.map((s) => `${s.col},${s.row}`));
  const seen = new Set();
  const head = {
    col: (start.col + dir.col + grid.cols) % grid.cols,
    row: (start.row + dir.row + grid.rows) % grid.rows,
  };
  const stack = [head];
  while (stack.length) {
    const cur = stack.pop();
    const key = `${cur.col},${cur.row}`;
    if (seen.has(key) || occupied.has(key)) continue;
    seen.add(key);
    for (const d of Object.values(DIRS)) {
      stack.push({
        col: (cur.col + d.col + grid.cols) % grid.cols,
        row: (cur.row + d.row + grid.rows) % grid.rows,
      });
    }
  }
  return seen.size;
}

/** Tiny seeded PRNG so nothing in the simulation depends on Math.random. */
export function mulberry32(seed) {
  let a = seed >>> 0;
  return function next() {
    a += 0x6d2b79f5;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* ------------------------------------------------------------- projection --- */

/**
 * Isometric projection for the terrain. Returns screen coordinates for a day
 * block. Kept here (not in the page) so the same numbers can be checked in CI.
 */
export function project(col, row, opts = {}) {
  const { weekDx = 14.2, dayDx = 8.4, dayDy = 8.6, weekRise = 0.3, left = 54, top = 214 } = opts;
  return {
    x: left + col * weekDx + row * dayDx,
    y: top + row * dayDy - col * weekRise,
  };
}

/** Half-open hover test, used by both the page and the tests. */
export function blockAt(px, py, grid, opts = {}) {
  const { blockW = 9.4, maxStack = 34 } = opts;
  let best = null;
  for (const cell of grid.cells) {
    if (cell.date === null) continue;
    const { x, y } = project(cell.col, cell.row, opts);
    const height = cell.count ? Math.max(2.2, Math.min(maxStack, cell.count * 3.1)) : 2.2;
    // a generous box: the visible column plus its top face
    if (px >= x && px <= x + blockW + 5 && py >= y - height - 6 && py <= y + 4) {
      best = cell; // later cells are drawn in front, so keep the last match
    }
  }
  return best;
}
