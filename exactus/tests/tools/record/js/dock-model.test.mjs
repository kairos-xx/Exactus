/** Exercise the pure dock grid model: alignment, docking, gaps and collapse. */
import assert from "node:assert/strict";
import test from "node:test";
/** Shared panel identifiers used to access the dynamic dock model. */
const panelKeys = Object.freeze({
  workspace: "workspace",
  actions: "actions",
  composition: "composition",
  steps: "steps",
  target: "target",
  properties: "properties",
  timeline: "timeline",
  runs: "runs",
});
/** Require a model entry to exist before checking its geometry.
 * @template T
 * @param {T|null|undefined} value Selected model entry.
 * @returns {T} Present value.
 */
const requiredValue = value => {
  assert.ok(value !== undefined && value !== null);
  return value;
};
import {
  HEADER_SIZE,
  adoptShared,
  boundaries,
  canCollapse,
  collapseAxis,
  collapseDirection,
  coverage,
  defaultLayout,
  defaultGraphLayout,
  describeShared,
  dockBeside,
  dockOuter,
  effectiveTracks,
  float,
  layoutForMode,
  resizeBoundary,
  sameShared,
  setCollapsed,
  stateOwner,
  swap,
  undock,
  validate,
} from "../../../../tools/record/studio/web/dock-model.js";
const known = new Set([
  "workspace",
  "actions",
  "composition",
  "steps",
  "target",
  "properties",
  "timeline",
  "runs",
]);
/** Return the small panel limits used by model-only geometry tests.
 * @returns {{width:number,height:number}} Test panel minimum.
 */
const minimum = () => ({ width: 120, height: 80 });
/** Resolve the model's preferred track sizes for docking calculations.
 * @param {import('../../../../tools/record/studio/web/dock-model.js').Layout} layout Test layout.
 * @returns {{cols:number[],rows:number[]}} Column and row pixel sizes.
 */
const metrics = layout => ({
  cols: layout.cols.map(item => item.size),
  rows: layout.rows.map(item => item.size),
});
/** Every cell is covered once, so no gap and no overlap exists.
 * @param {import('../../../../tools/record/studio/web/dock-model.js').Layout} layout Layout under test.
 */
const assertTiled = layout => {
  const grid = coverage(layout);
  for (const row of grid)
    for (const id of row) assert.ok(id, JSON.stringify(layout.cells));
  const cells = Object.entries(layout.cells);
  const area = cells.reduce((sum, [, cell]) => sum + cell.cs * cell.rs, 0);
  assert.equal(area, layout.cols.length * layout.rows.length);
  assert.equal(layout.cols.filter(item => item.flex).length, 1);
  assert.equal(layout.rows.filter(item => item.flex).length, 1);
};
test("the default layout is a valid tiled grid", () => {
  const layout = defaultLayout();
  assertTiled(layout);
  assert.ok(validate(layout, known));
  assert.equal(validate({ version: 99 }, known), null);
  assert.equal(validate(null, known), null);
});
test("panels in different rows share one column line", () => {
  const layout = defaultLayout();
  const lines = boundaries(layout, "c");
  // Workspace|steps and steps|right column separate the same two track edges.
  assert.deepEqual(
    [...new Set(lines.map(item => item.index))].sort(),
    [0, 1],
  );
  const dockedRight = dockBeside(
    layout,
    "properties",
    "steps",
    "right",
    metrics(layout),
  );
  assertTiled(dockedRight);
  for (const line of boundaries(dockedRight, "c"))
    assert.ok(line.index < dockedRight.cols.length - 1);
});
test("docking beside a panel adds a track and tiles the grid", () => {
  const layout = defaultLayout();
  for (const edge of /** @type {const} */ (["left", "right", "top", "bottom"]))
    for (const target of [
      "workspace",
      "steps",
      "target",
      "properties",
      "timeline",
    ]) {
      const next = dockBeside(
        layout,
        "properties",
        target,
        edge,
        metrics(layout),
      );
      assertTiled(next);
      assert.ok(next.cells[panelKeys.properties], `${target}:${edge}`);
    }
});
test("moving a panel away lets a neighbour fill the gap", () => {
  const layout = defaultLayout();
  const withoutTimeline = undock(layout, "timeline");
  assertTiled(withoutTimeline);
  assert.equal(withoutTimeline.rows.length, 2);
  const withoutProperties = undock(layout, "properties");
  assertTiled(withoutProperties);
  assert.equal(
    requiredValue(withoutProperties.cells[panelKeys.target]).rs >= 1,
    true,
  );
  for (const id of ["workspace", "steps", "target", "properties", "timeline"])
    assertTiled(undock(layout, id));
});
test("outer docks span the whole window", () => {
  const layout = defaultLayout();
  const left = dockOuter(layout, "target", "left", 260);
  assertTiled(left);
  assert.equal(requiredValue(left.cells[panelKeys.target]).c, 0);
  assert.equal(
    requiredValue(left.cells[panelKeys.target]).rs,
    left.rows.length,
  );
  const top = dockOuter(layout, "timeline", "top", 200);
  assertTiled(top);
  assert.equal(
    requiredValue(top.cells[panelKeys.timeline]).cs,
    top.cols.length,
  );
});
test("swap exchanges places and keeps the grid tiled", () => {
  const layout = defaultLayout();
  const next = swap(layout, "workspace", "steps");
  assertTiled(next);
  assert.deepEqual(
    next.cells[panelKeys.workspace],
    layout.cells[panelKeys.steps],
  );
  assert.deepEqual(
    next.cells[panelKeys.steps],
    layout.cells[panelKeys.workspace],
  );
});
test("floating a panel frees its cells", () => {
  const layout = defaultLayout();
  const next = float(layout, "target", { x: 10, y: 10, w: 300, h: 200 });
  assertTiled(next);
  assert.ok(next.floating[panelKeys.target]);
  assert.equal(next.cells[panelKeys.target], undefined);
});
test("collapse direction follows the panel's position", () => {
  const layout = defaultLayout();
  assert.equal(collapseAxis(layout, "workspace"), "h");
  assert.equal(collapseDirection(layout, "workspace"), "left");
  assert.equal(collapseAxis(layout, "timeline"), "v");
  assert.equal(collapseDirection(layout, "timeline"), "down");
  assert.equal(collapseAxis(layout, "target"), "v");
  assert.equal(collapseDirection(layout, "target"), "up");
  assert.equal(collapseAxis(layout, "properties"), "v");
  assert.equal(collapseDirection(layout, "properties"), "down");
  assert.equal(collapseAxis(layout, "steps"), "h");
});
test("collapsing shrinks only its own track and a neighbour takes the space", () => {
  const layout = defaultLayout();
  const timeline = setCollapsed(layout, "timeline", true);
  const rows = effectiveTracks(timeline, "r");
  assert.equal(requiredValue(rows[2]).size, HEADER_SIZE);
  assert.equal(requiredValue(rows[2]).collapsed, true);
  assert.equal(rows.filter(item => item.flex).length, 1);
  assert.notEqual(requiredValue(rows[2]).flex, true);
  const workspace = setCollapsed(layout, "workspace", true);
  const columns = effectiveTracks(workspace, "c");
  assert.equal(requiredValue(columns[0]).size, HEADER_SIZE);
  assert.equal(requiredValue(columns[1]).flex, true);
  // Collapsing the flexible panel hands the flex role to the neighbour that
  // sits opposite its collapse direction.
  const properties = setCollapsed(layout, "properties", true);
  const propertyRows = effectiveTracks(properties, "r");
  assert.equal(requiredValue(propertyRows[1]).collapsed, true);
  assert.equal(requiredValue(propertyRows[0]).flex, true);
  const restored = setCollapsed(timeline, "timeline", false);
  assert.deepEqual(
    effectiveTracks(restored, "r").map(item => item.size),
    [340, 300, 200],
  );
});
test("the last open track on an axis cannot be collapsed away", () => {
  let layout = defaultLayout();
  layout = setCollapsed(layout, "workspace", true);
  layout = setCollapsed(layout, "target", true);
  assert.equal(canCollapse(layout, "steps"), true);
  const single = layoutForMode("timeline", layout);
  assert.equal(canCollapse(requiredValue(single), "timeline"), false);
});
test("resizing a shared boundary honours minimum sizes", () => {
  const layout = defaultLayout();
  const sizes = metrics(layout);
  sizes.cols = [232, 1000, 352];
  const wider = resizeBoundary(layout, "c", 0, 5000, minimum, sizes);
  assert.ok(requiredValue(wider.cols[0]).size > 232);
  assert.ok(requiredValue(wider.cols[0]).size <= 232 + 1000 - 120);
  const narrower = resizeBoundary(layout, "c", 0, -5000, minimum, sizes);
  assert.ok(requiredValue(narrower.cols[0]).size >= 120);
});
test("a boundary next to a collapsed panel still resizes the open side", () => {
  const layout = defaultLayout();
  const sizes = metrics(layout);
  sizes.cols = [232, 1000, 352];
  sizes.rows = [196, 300, 240];
  // Collapse the left panel: dragging the right column's edge still works.
  const collapsed = setCollapsed(layout, "workspace", true);
  const widened = resizeBoundary(collapsed, "c", 1, -80, minimum, sizes);
  assert.equal(requiredValue(widened.cols[2]).size, 352 + 80);
  // The line beside the collapsed bar itself moves nothing on the collapsed side.
  const beside = resizeBoundary(collapsed, "c", 0, 50, minimum, sizes);
  assert.equal(requiredValue(beside.cols[0]).size, 232);
  // A collapsed bottom panel leaves the row above resizable from its own edge.
  const bar = setCollapsed(layout, "timeline", true);
  const taller = resizeBoundary(bar, "r", 0, 40, minimum, sizes);
  assert.equal(requiredValue(taller.rows[0]).size, 196 + 40);
  // A line beside a collapsed bar resizes the nearest open panel on each side and
  // the bar travels with it, instead of leaving the line dead.
  const middle = setCollapsed(layout, "steps", true);
  const beyond = resizeBoundary(middle, "c", 0, 50, minimum, sizes);
  assert.equal(requiredValue(beyond.cols[2]).size, 352 - 50);
  const stack = setCollapsed(layout, "properties", true);
  const below = resizeBoundary(stack, "r", 0, 30, minimum, sizes);
  assert.equal(requiredValue(below.rows[2]).size, 240 - 30);
  // Collapsing the flexible column hands its role on and keeps both sides usable.
  const centre = setCollapsed(layout, "steps", true);
  const handed = resizeBoundary(centre, "c", 1, -60, minimum, sizes);
  assert.equal(requiredValue(handed.cols[2]).size, 352 + 60);
});
test("graph derives its own flow-only layout, never Edit's actions", () => {
  const layout = defaultGraphLayout();
  const graph = layoutForMode("graph", layout);
  assert.deepEqual(Object.keys(requiredValue(graph).cells).sort(), [
    "composition",
    "properties",
    "workspace",
  ]);
  assert.deepEqual(
    requiredValue(graph).cells[panelKeys.steps],
    layout.cells[panelKeys.steps],
  );
  assert.deepEqual(requiredValue(graph).cols, layout.cols);
  assert.deepEqual(requiredValue(graph).rows, layout.rows);
  assert.equal(graph, layout);
  assert.equal(stateOwner("graph", "steps"), "steps");
  assert.equal(stateOwner("edit", "composition"), "composition");
  assert.equal(stateOwner("graph", "target"), "target");
});
test("mode layouts show only the panels that belong to them", () => {
  const layout = defaultLayout();
  const record = layoutForMode("record", layout);
  assert.deepEqual(
    requiredValue(record).cells[panelKeys.target],
    layout.cells[panelKeys.steps],
  );
  assert.deepEqual(
    requiredValue(record).cells[panelKeys.steps],
    layout.cells[panelKeys.target],
  );
  assert.equal(stateOwner("record", "target"), "steps");
  assert.equal(stateOwner("record", "steps"), "target");
  assert.deepEqual(
    Object.keys(requiredValue(layoutForMode("timeline", layout)).cells),
    ["timeline"],
  );
  assert.equal(layoutForMode("edit", layout), layout);
});
test("random docking sequences always leave a tiled grid", () => {
  const ids = [
    "workspace",
    "steps",
    "target",
    "properties",
    "timeline",
    "composition",
    "runs",
  ];
  const edges = ["left", "right", "top", "bottom"];
  let seed = 7;
  /** Advance the deterministic pseudo-random generator.
   * @returns {number} Fraction in the range zero to one.
   */
  const random = () => {
    seed = (seed * 1664525 + 1013904223) % 4294967296;
    return seed / 4294967296;
  };
  /** Choose a deterministic member for randomized layout operations.
   * @param {any[]} list Nonempty candidate list.
   * @returns {any} Selected candidate.
   */
  const pick = list => list[Math.floor(random() * list.length)];
  for (let run = 0; run < 60; run += 1) {
    let layout = defaultLayout();
    for (let step = 0; step < 25; step += 1) {
      const id = pick(ids);
      const docked = Object.keys(layout.cells);
      const action = random();
      if (action < 0.45 && docked.length > 1) {
        const target = pick(docked.filter(item => item !== id));
        layout = dockBeside(layout, id, target, pick(edges), metrics(layout));
      } else if (action < 0.6) layout = dockOuter(layout, id, pick(edges));
      else if (action < 0.75 && layout.cells[id]) layout = undock(layout, id);
      else if (action < 0.85 && docked.length > 1 && layout.cells[id])
        layout = swap(layout, id, pick(docked.filter(item => item !== id)));
      else if (action < 0.92 && docked.length > 1 && layout.cells[id])
        layout = float(layout, id, { x: 0, y: 0, w: 300, h: 200 });
      else if (layout.cells[id])
        layout = setCollapsed(layout, id, random() < 0.5);
      if (Object.keys(layout.cells).length === 0) {
        layout = defaultLayout();
        continue;
      }
      try {
        assertTiled(layout);
      } catch (error) {
        throw new Error(`run ${run} step ${step}: ${String(error)}`, {
          cause: error,
        });
      }
    }
  }
});
test("the Flows panel sits in the same place in Edit and Graph by default", () => {
  const edit = describeShared(defaultLayout());
  const graph = describeShared(defaultGraphLayout());
  assert.ok(sameShared(edit, graph), JSON.stringify({ edit, graph }));
  const cell = requiredValue(defaultLayout().cells[panelKeys.workspace]);
  assert.equal(cell.rs, defaultLayout().rows.length);
});
test("moving, resizing or collapsing Flows in one workspace carries over to the other", () => {
  const moved = dockOuter(defaultLayout(), panelKeys.workspace, "right", 300);
  const shared = describeShared(moved);
  assert.equal(shared.edge, "right");
  assert.equal(shared.size, 300);
  const graph = adoptShared(defaultGraphLayout(), shared);
  assert.ok(sameShared(describeShared(graph), shared));
  assert.ok(coverage(graph).every(row => row.every(Boolean)));
  const closed = setCollapsed(defaultLayout(), panelKeys.workspace, true);
  const adopted = adoptShared(defaultGraphLayout(), describeShared(closed));
  assert.equal(describeShared(adopted).collapsed, true);
  const detached = float(defaultLayout(), panelKeys.workspace, {
    x: 40,
    y: 80,
    w: 260,
    h: 400,
  });
  const floating = adoptShared(defaultGraphLayout(), describeShared(detached));
  assert.ok(panelKeys.workspace in floating.floating);
  assert.ok(!(panelKeys.workspace in floating.cells));
});
test("an older saved Edit layout is moved to the full-height column without a gap", () => {
  // The shipped layout before Flows became shared: Flows stopped above the timeline.
  const legacy = defaultLayout();
  legacy.cells[panelKeys.workspace] = { c: 0, r: 0, cs: 1, rs: 2 };
  legacy.cells[panelKeys.timeline] = { c: 0, r: 2, cs: 3, rs: 1 };
  const migrated = adoptShared(legacy, describeShared(legacy));
  const flows = requiredValue(migrated.cells[panelKeys.workspace]);
  assert.equal(flows.r, 0);
  assert.equal(flows.rs, migrated.rows.length);
  assert.ok(
    coverage(migrated).every(row => row.every(Boolean)),
    "the grid must stay fully tiled",
  );
  for (const id of [
    panelKeys.steps,
    panelKeys.target,
    panelKeys.properties,
    panelKeys.timeline,
  ])
    assert.ok(id in migrated.cells, `${id} must still be docked`);
});
