/** Pure layout model for the Studio dock grid.  Every panel occupies a rectangle of cells in one shared grid. Rows and columns are tracks common to all panels, so panels in different rows can never end up with misaligned columns. The model has no DOM access: the view in `dock-grid.js` renders it and feeds back measured pixel sizes.
 */
/** Size of a collapsed track: just enough for a panel header.
 */
export const HEADER_SIZE = 36;
/** Smallest new column or row a drop may create.
 */
export const MIN_NEW_TRACK = 120;
/** Preferred size of a column created by a drop.
 */
export const DEFAULT_COLUMN = 280;
/** Preferred size of a row created by a drop.
 */
export const DEFAULT_ROW = 176;
/** Layout schema version stored with the persisted layout.
 */
export const LAYOUT_VERSION = 1;
/** @typedef {{size:number,flex:boolean}} Track */
/** @typedef {{c:number,r:number,cs:number,rs:number}} Cell */
/** @typedef {{x:number,y:number,w:number,h:number}} FloatRect */
/** @typedef {"left"|"right"|"top"|"bottom"} Edge */
/** @typedef {"c"|"r"} Axis */
/** @typedef {object} Layout @property {number} version Schema version. @property {Track[]} cols Column tracks, left to right. @property {Track[]} rows Row tracks, top to bottom. @property {Record<string, Cell>} cells Docked panels by id. @property {Record<string, "h"|"v">} collapsed Collapse axis by panel id. @property {Record<string, FloatRect>} floating Detached panels by id.
 */
/** @typedef {{width:number,height:number}} Minimum */
/** Create a track with its preferred pixel size and flexible flag.
 * @param {number} size
 * @param {boolean} [flex]
 * @returns {Track}
 */
const track = (size, flex = false) => ({ size, flex });
/** Return the shipped editor grid with flows, steps, target, properties and timeline.
 * @returns {Layout} The Edit workspace as shipped.
 */
export const defaultLayout = () => ({
  version: LAYOUT_VERSION,
  cols: [track(232), track(480, true), track(352)],
  rows: [track(340), track(300, true), track(200)],
  cells: {
    workspace: { c: 0, r: 0, cs: 1, rs: 3 },
    steps: { c: 1, r: 0, cs: 1, rs: 2 },
    target: { c: 2, r: 0, cs: 1, rs: 1 },
    properties: { c: 2, r: 1, cs: 1, rs: 1 },
    timeline: { c: 1, r: 2, cs: 2, rs: 1 },
  },
  collapsed: {},
  floating: {},
});
/** Return a deep copy of the supplied layout.
 * @param {Layout} layout
 * @returns {Layout} A deep copy.
 */
export const clone = layout => structuredClone(layout);
/** Graph arranges whole flows and connections, never actions or a timeline.
 * @returns {Layout} Independent graph workspace.
 */
export const defaultGraphLayout = () => ({
  version: LAYOUT_VERSION,
  cols: [track(232), track(480, true), track(352)],
  rows: [track(480, true)],
  cells: {
    workspace: { c: 0, r: 0, cs: 1, rs: 1 },
    composition: { c: 1, r: 0, cs: 1, rs: 1 },
    properties: { c: 2, r: 0, cs: 1, rs: 1 },
  },
  collapsed: {},
  floating: {},
});
/** Move one entry of a record to another key.
 * @template T
 * @param {Record<string,T>} record Mutated in place.
 * @param {string} from
 * @param {string} to
 * @returns {void}
 */
const rename = (record, from, to) => {
  const value = record[from];
  if (value === undefined) return;
  record[to] = value;
  delete record[from];
};
/** Derive the visible layout. The caller supplies the independent Edit or Graph base. Timeline shows only its timeline; task workspaces show no panels.
 * @param {string} mode Workspace mode.
 * @param {Layout} base The current workspace's saved layout.
 * @returns {Layout|null} Layout to render, or null when no panel is shown.
 */
export const layoutForMode = (mode, base) => {
  if (mode === "edit" || mode === "graph") return base;
  if (mode === "record") {
    const view = clone(base);
    rename(view.cells, "steps", "record-swap");
    rename(view.cells, "target", "steps");
    rename(view.cells, "record-swap", "target");
    rename(view.collapsed, "steps", "record-swap");
    rename(view.collapsed, "target", "steps");
    rename(view.collapsed, "record-swap", "target");
    rename(view.floating, "steps", "record-swap");
    rename(view.floating, "target", "steps");
    rename(view.floating, "record-swap", "target");
    return view;
  }
  if (mode === "timeline") {
    /** @type {Layout} */
    const frame = {
      version: LAYOUT_VERSION,
      cols: [track(480, true)],
      rows: [track(480, true)],
      cells: { timeline: { c: 0, r: 0, cs: 1, rs: 1 } },
      collapsed: {},
      floating: {},
    };
    return frame;
  }
  return null;
};
/** The panel whose saved state a panel shows in a mode; Record swaps Edit's steps and target.
 * @param {string} mode Workspace mode.
 * @param {string} id Panel id.
 * @returns {string}
 */
export const stateOwner = (mode, id) => {
  if (mode === "record" && id === "target") return "steps";
  if (mode === "record" && id === "steps") return "target";
  return id;
};
/** Return the first track occupied by a cell on the given axis.
 * @param {Cell} cell
 * @param {Axis} axis
 * @returns {number} First track.
 */
const start = (cell, axis) => axis === "c" ? cell.c : cell.r;
/** Return the number of tracks occupied by a cell on the given axis.
 * @param {Cell} cell
 * @param {Axis} axis
 * @returns {number} Track count.
 */
const span = (cell, axis) => axis === "c" ? cell.cs : cell.rs;
/** Return the exclusive last track occupied by a cell.
 * @param {Cell} cell
 * @param {Axis} axis
 * @returns {number} One past the last track.
 */
const end = (cell, axis) => start(cell, axis) + span(cell, axis);
/** Return the perpendicular grid axis.
 * @param {Axis} axis
 * @returns {Axis} The other axis.
 */
const across = axis => axis === "c" ? "r" : "c";
/** Return the layout tracks belonging to the selected axis.
 * @param {Layout} layout
 * @param {Axis} axis
 * @returns {Track[]}
 */
const tracksOf = (layout, axis) => axis === "c" ? layout.cols : layout.rows;
/** Grid of panel ids; overlaps keep the first panel.
 * @param {Layout} layout
 * @returns {(string|null)[][]} Rows of columns.
 */
export const coverage = layout => {
  /** @type {(string|null)[][]} */
  const grid = layout.rows.map(() => layout.cols.map(() => null));
  for (const [id, cell] of Object.entries(layout.cells))
    for (let r = cell.r; r < cell.r + cell.rs; r += 1)
      for (let c = cell.c; c < cell.c + cell.cs; c += 1) {
        const line = grid[r];
        if (line && line[c] === null) line[c] = id;
      }
  return grid;
};
/** Check whether a panel currently occupies grid cells.
 * @param {Layout} layout
 * @param {string} id
 * @returns {boolean}
 */
export const isDocked = (layout, id) => id in layout.cells;
/** Check a persisted layout before trusting it.
 * @param {unknown} value Parsed JSON.
 * @param {ReadonlySet<string>} known Panel ids that exist.
 * @returns {Layout|null} The layout when it is internally consistent.
 */
export const validate = (value, known) => {
  if (!value || typeof value !== "object") return null;
  const layout = /** @type {Layout} */ (value);
  if (layout.version !== LAYOUT_VERSION) return null;
  for (const axis of /** @type {Axis[]} */ (["c", "r"])) {
    const tracks = tracksOf(layout, axis);
    if (!Array.isArray(tracks) || tracks.length === 0) return null;
    if (tracks.filter(item => item?.flex).length !== 1) return null;
    if (tracks.some(item => !Number.isFinite(item?.size) || item.size < 0))
      return null;
  }
  if (!layout.cells || !layout.collapsed || !layout.floating) return null;
  const seen = new Set();
  for (const [id, cell] of Object.entries(layout.cells)) {
    if (!known.has(id) || id in layout.floating) return null;
    const values = [cell.c, cell.r, cell.cs, cell.rs];
    if (values.some(item => !Number.isInteger(item))) return null;
    if (cell.c < 0 || cell.r < 0 || cell.cs < 1 || cell.rs < 1) return null;
    if (cell.c + cell.cs > layout.cols.length) return null;
    if (cell.r + cell.rs > layout.rows.length) return null;
    for (let r = cell.r; r < cell.r + cell.rs; r += 1)
      for (let c = cell.c; c < cell.c + cell.cs; c += 1) {
        const key = `${r}:${c}`;
        if (seen.has(key)) return null;
        seen.add(key);
      }
  }
  for (const id of Object.keys(layout.floating))
    if (!known.has(id)) return null;
  return layout;
};
/** Which axis a panel collapses along, or null when it shares both its row and its column with siblings and has no free direction.  - "h": the panel's width collapses to a vertical bar. - "v": the panel's height collapses to a horizontal bar.
 * @param {Layout} layout
 * @param {string} id
 * @returns {"h"|"v"|null}
 */
export const collapseAxis = (layout, id) => {
  if (id in layout.floating) return "v";
  const cell = layout.cells[id];
  if (!cell) return null;
  const others = Object.entries(layout.cells).filter(([key]) => key !== id);
  /** Check whether a panel owns a complete track without siblings.
   * @param {Axis} axis
   * @returns {boolean}
   */
  const alone = axis =>
    span(cell, axis) === 1 &&
    others.every(
      ([, other]) =>
        !(
          start(other, axis) <= start(cell, axis) &&
          end(other, axis) > start(cell, axis)
        ) || span(other, axis) > 1,
    );
  const column = alone("c");
  const row = alone("r");
  if (column && row) {
    const touchesSide = cell.c === 0 || cell.c + cell.cs === layout.cols.length;
    return touchesSide ? "h" : "v";
  }
  if (column) return "h";
  if (row) return "v";
  return null;
};
/** Where a collapsing panel points, used for its chevron and for choosing which neighbour receives the freed space.
 * @param {Layout} layout
 * @param {string} id
 * @returns {"left"|"right"|"up"|"down"|null}
 */
export const collapseDirection = (layout, id) => {
  const axis = collapseAxis(layout, id);
  const cell = layout.cells[id];
  if (!axis) return null;
  if (!cell) return "down";
  if (axis === "h")
    return cell.c + cell.cs / 2 < layout.cols.length / 2 ? "left" : "right";
  return cell.r + cell.rs / 2 < layout.rows.length / 2 ? "up" : "down";
};
/** Find the collapsed panel responsible for a header-only track.
 * @param {Layout} layout
 * @param {Axis} axis
 * @param {number} index
 * @returns {string|null}
 */
const collapsedPanelOf = (layout, axis, index) => {
  const wanted = axis === "c" ? "h" : "v";
  for (const [id, cell] of Object.entries(layout.cells))
    if (
      layout.collapsed[id] === wanted &&
      span(cell, axis) === 1 &&
      start(cell, axis) === index &&
      collapseAxis(layout, id) === wanted
    )
      return id;
  return null;
};
/** Track sizes after collapses: collapsed tracks shrink to a header, and the flexible track hands over to a neighbour when it is the one collapsing.
 * @param {Layout} layout
 * @param {Axis} axis
 * @returns {{size:number,flex:boolean,collapsed:boolean}[]}
 */
export const effectiveTracks = (layout, axis) => {
  const tracks = tracksOf(layout, axis);
  const collapsed = tracks.map((_, index) =>
    Boolean(collapsedPanelOf(layout, axis, index)),
  );
  let flex = tracks.findIndex((item, index) => item.flex && !collapsed[index]);
  if (flex < 0) {
    const origin = tracks.findIndex(item => item.flex);
    const id = collapsedPanelOf(layout, axis, origin);
    const direction = id ? collapseDirection(layout, id) : null;
    const step = direction === "left" || direction === "up" ? 1 : -1;
    for (const candidate of [origin + step, origin - step])
      if (tracks[candidate] && !collapsed[candidate]) {
        flex = candidate;
        break;
      }
    if (flex < 0) flex = tracks.findIndex((_, index) => !collapsed[index]);
    if (flex < 0) flex = origin;
  }
  return tracks.map((item, index) => ({
    size: collapsed[index] ? HEADER_SIZE : item.size,
    flex: index === flex,
    collapsed: collapsed[index] ?? false,
  }));
};
/** Whether collapsing would leave the axis with an expandable track.
 * @param {Layout} layout
 * @param {string} id
 * @returns {boolean}
 */
export const canCollapse = (layout, id) => {
  const axis = collapseAxis(layout, id);
  if (!axis) return false;
  if (id in layout.floating) return true;
  const trackAxis = axis === "h" ? "c" : "r";
  const tracks = effectiveTracks(layout, trackAxis);
  const cell = layout.cells[id];
  if (!cell) return false;
  const index = start(cell, trackAxis);
  if (tracks[index]?.collapsed) return true;
  return tracks.some((item, other) => other !== index && !item.collapsed);
};
/** Collapse or expand a panel.
 * @param {Layout} layout
 * @param {string} id
 * @param {boolean} on
 * @returns {Layout}
 */
export const setCollapsed = (layout, id, on) => {
  const next = clone(layout);
  if (!on) {
    delete next.collapsed[id];
    return next;
  }
  const axis = collapseAxis(next, id);
  if (!axis || !canCollapse(next, id)) return next;
  next.collapsed[id] = axis;
  return next;
};
/** Check whether a cell covers the requested track interval.
 * @param {Layout} layout
 * @param {Axis} axis
 * @param {number} index
 * @returns {boolean} A panel covers the track.
 */
const covered = (layout, axis, index) =>
  Object.values(layout.cells).some(
    cell => start(cell, axis) <= index && end(cell, axis) > index,
  );
/** Check whether panel cells are separated along the given axis.
 * @param {Layout} layout
 * @param {Axis} axis
 * @param {number} index
 * @returns {boolean} A panel edge lies between two tracks.
 */
const separated = (layout, axis, index) =>
  Object.values(layout.cells).some(
    cell => end(cell, axis) === index + 1 || start(cell, axis) === index + 1,
  );
/** Calculate the available space after fixed tracks and minimum sizes.
 * @param {(string|null)[][]} grid
 * @param {number} row
 * @param {number} column
 * @param {number} width
 * @returns {boolean} The row slice is free.
 */
const free = (grid, row, column, width) => {
  const line = grid[row];
  return (
    line !== undefined &&
    Array.from({ length: width }, (_, offset) => line[column + offset]).every(
      item => item === null,
    )
  );
};
/** Remove tracks nothing covers and merge tracks no panel edge separates.
 * @param {Layout} layout Mutated in place.
 * @returns {void}
 */
const prune = layout => {
  for (const axis of /** @type {Axis[]} */ (["c", "r"])) {
    const tracks = tracksOf(layout, axis);
    let index = 0;
    while (index < tracks.length && tracks.length > 1) {
      if (covered(layout, axis, index)) {
        index += 1;
        continue;
      }
      const removed = tracks.splice(index, 1)[0];
      const heir = tracks[Math.max(0, index - 1)];
      if (removed?.flex && heir) heir.flex = true;
      for (const cell of Object.values(layout.cells))
        if (start(cell, axis) > index) {
          if (axis === "c") cell.c -= 1;
          else cell.r -= 1;
        }
    }
    index = 0;
    while (index < tracks.length - 1) {
      if (separated(layout, axis, index)) {
        index += 1;
        continue;
      }
      const left = tracks[index];
      const right = tracks[index + 1];
      if (!left || !right) break;
      left.size += right.size;
      left.flex ||= right.flex;
      tracks.splice(index + 1, 1);
      for (const cell of Object.values(layout.cells)) {
        if (start(cell, axis) > index + 1) {
          if (axis === "c") cell.c -= 1;
          else cell.r -= 1;
        } else if (start(cell, axis) <= index && end(cell, axis) > index + 1)
          if (axis === "c") cell.cs -= 1;
          else cell.rs -= 1;
      }
    }
  }
};
/** Give uncovered cells to an adjacent panel. A neighbour whose edge matches the hole exactly takes all of it; a wider hole is shared out in strips.
 * @param {Layout} layout Mutated in place.
 * @returns {void}
 */
const fill = layout => {
  for (let guard = 0; guard < 64; guard += 1) {
    const grid = coverage(layout);
    /** @type {{r:number,c:number}|null} */
    let hole = null;
    for (let r = 0; r < grid.length && !hole; r += 1)
      for (let c = 0; c < (grid[r]?.length ?? 0) && !hole; c += 1)
        if (grid[r]?.[c] === null) hole = { r, c };
    if (!hole) return;
    let width = 1;
    while (grid[hole.r]?.[hole.c + width] === null) width += 1;
    let height = 1;
    while (free(grid, hole.r + height, hole.c, width)) height += 1;
    const area = { c: hole.c, r: hole.r, cs: width, rs: height };
    /** @type {{id:string,edge:Edge,exact:boolean,size:number}[]} */
    const options = [];
    for (const [id, cell] of Object.entries(layout.cells)) {
      /** @type {Edge|null} */
      let edge = null;
      if (cell.c + cell.cs === area.c) edge = "right";
      else if (cell.c === area.c + area.cs) edge = "left";
      else if (cell.r + cell.rs === area.r) edge = "bottom";
      else if (cell.r === area.r + area.rs) edge = "top";
      if (!edge) continue;
      const vertical = edge === "left" || edge === "right";
      const axis = vertical ? "r" : "c";
      const cellStart = start(cell, axis);
      const cellEnd = end(cell, axis);
      const areaStart = start(area, axis);
      const areaEnd = end(area, axis);
      const overlaps = cellStart < areaEnd && cellEnd > areaStart;
      if (!overlaps) continue;
      const exact = cellStart === areaStart && cellEnd === areaEnd;
      const inside = cellStart >= areaStart && cellEnd <= areaEnd;
      if (!exact && !inside) continue;
      options.push({ id, edge, exact, size: cell.cs * cell.rs });
    }
    options.sort(
      (a, b) => Number(b.exact) - Number(a.exact) || b.size - a.size,
    );
    const pick = options[0];
    if (!pick) return;
    const cell = layout.cells[pick.id];
    if (!cell) return;
    if (pick.edge === "right") cell.cs += area.cs;
    else if (pick.edge === "left") {
      cell.c = area.c;
      cell.cs += area.cs;
    } else if (pick.edge === "bottom") cell.rs += area.rs;
    else {
      cell.r = area.r;
      cell.rs += area.rs;
    }
  }
};
/** Close gaps after a panel leaves the grid.
 * @param {Layout} layout Mutated in place.
 * @returns {void}
 */
const settle = layout => {
  for (let pass = 0; pass < 4; pass += 1) {
    prune(layout);
    fill(layout);
  }
  prune(layout);
};
/** Take a panel out of the grid. Neighbours grow into the space.
 * @param {Layout} layout
 * @param {string} id
 * @returns {Layout}
 */
export const undock = (layout, id) => {
  const next = clone(layout);
  delete next.cells[id];
  delete next.collapsed[id];
  settle(next);
  return next;
};
/** Insert a track and widen every panel that straddles it.
 * @param {Layout} layout Mutated.
 * @param {Axis} axis
 * @param {number} at
 * @param {number} size
 * @returns {void}
 */
const insertTrack = (layout, axis, at, size) => {
  tracksOf(layout, axis).splice(at, 0, track(size));
  for (const cell of Object.values(layout.cells)) {
    if (start(cell, axis) >= at) {
      if (axis === "c") cell.c += 1;
      else cell.r += 1;
    } else if (end(cell, axis) > at)
      if (axis === "c") cell.cs += 1;
      else cell.rs += 1;
  }
};
/** Dock a panel against one side of another panel. The panel gets a new column or row; every panel that crossed that line simply grows across it.
 * @param {Layout} layout
 * @param {string} id Panel to move.
 * @param {string} targetId Panel to dock beside.
 * @param {Edge} edge Side of the target.
 * @param {{cols:number[],rows:number[]}} metrics Current pixel track sizes.
 * @returns {Layout}
 */
export const dockBeside = (layout, id, targetId, edge, metrics) => {
  if (id === targetId || !layout.cells[targetId]) return layout;
  const next = undock(layout, id);
  delete next.floating[id];
  const target = next.cells[targetId];
  if (!target) return layout;
  const horizontal = edge === "left" || edge === "right";
  const axis = horizontal ? "c" : "r";
  const sizes = horizontal ? metrics.cols : metrics.rows;
  const targetPx = sizes
    .slice(start(target, axis), end(target, axis))
    .reduce((sum, item) => sum + item, 0);
  const fallback = horizontal ? DEFAULT_COLUMN : DEFAULT_ROW;
  const created = Math.max(
    MIN_NEW_TRACK,
    Math.min(fallback, Math.floor((targetPx || fallback * 2) / 2)),
  );
  const at =
    edge === "left" || edge === "top" ? start(target, axis) : end(target, axis);
  const own = tracksOf(next, axis);
  const only = span(target, axis) === 1 ? own[start(target, axis)] : null;
  insertTrack(next, axis, at, created);
  if (only && !only.flex)
    only.size = Math.max(MIN_NEW_TRACK, only.size - created);
  const placed = next.cells[targetId];
  if (!placed) return layout;
  next.cells[id] =
    axis === "c"
      ? { c: at, cs: 1, r: placed.r, rs: placed.rs }
      : { r: at, rs: 1, c: placed.c, cs: placed.cs };
  settle(next);
  return next;
};
/** Dock a panel along a window edge as a new full-height column or full-width row.
 * @param {Layout} layout
 * @param {string} id
 * @param {Edge} edge
 * @param {number} [size] Preferred size in pixels.
 * @returns {Layout}
 */
export const dockOuter = (layout, id, edge, size) => {
  const next = undock(layout, id);
  delete next.floating[id];
  const horizontal = edge === "left" || edge === "right";
  const axis = horizontal ? "c" : "r";
  const at =
    edge === "left" || edge === "top" ? 0 : tracksOf(next, axis).length;
  const preferred = size ?? (horizontal ? DEFAULT_COLUMN : DEFAULT_ROW);
  insertTrack(next, axis, at, Math.max(MIN_NEW_TRACK, preferred));
  const rows = next.rows.length;
  const cols = next.cols.length;
  next.cells[id] =
    axis === "c"
      ? { c: at, cs: 1, r: 0, rs: rows }
      : { r: at, rs: 1, c: 0, cs: cols };
  settle(next);
  return next;
};
/** Exchange the places of two docked panels.
 * @param {Layout} layout
 * @param {string} a
 * @param {string} b
 * @returns {Layout}
 */
export const swap = (layout, a, b) => {
  const next = clone(layout);
  const first = next.cells[a];
  const second = next.cells[b];
  if (!first || !second) return layout;
  next.cells[a] = second;
  next.cells[b] = first;
  const collapsed = { ...next.collapsed };
  delete next.collapsed[a];
  delete next.collapsed[b];
  if (collapsed[a]) next.collapsed[a] = collapsed[a];
  if (collapsed[b]) next.collapsed[b] = collapsed[b];
  for (const id of [a, b])
    if (next.collapsed[id] && collapseAxis(next, id) !== next.collapsed[id])
      delete next.collapsed[id];
  return next;
};
/** Detach a panel into a floating window.
 * @param {Layout} layout
 * @param {string} id
 * @param {FloatRect} rect
 * @returns {Layout}
 */
export const float = (layout, id, rect) => {
  const next = undock(layout, id);
  next.floating[id] = { ...rect };
  return next;
};
/** The Flows panel is one component in every workspace that shows it. */
export const SHARED_PANEL = "workspace";
/** @typedef {{edge:Edge,size:number,collapsed:boolean,floating:FloatRect|null}} Shared */
/** Describe where the shared Flows panel sits, so another layout can match it.
 * @param {Layout} layout
 * @returns {Shared} Edge, width or height, and collapsed or detached state.
 */
export const describeShared = layout => {
  const floating = layout.floating[SHARED_PANEL] ?? null;
  const cell = layout.cells[SHARED_PANEL];
  const collapsed = SHARED_PANEL in layout.collapsed;
  if (!cell) return { edge: "left", size: DEFAULT_COLUMN, collapsed, floating };
  const rows = layout.rows.length;
  const cols = layout.cols.length;
  const tall = cell.r === 0 && cell.rs === rows;
  const wide = cell.c === 0 && cell.cs === cols;
  /** @type {Edge} */
  let edge = "left";
  if (tall && cell.c > 0 && end(cell, "c") === cols) edge = "right";
  else if (!tall && wide) edge = cell.r === 0 ? "top" : "bottom";
  const axis = edge === "left" || edge === "right" ? "c" : "r";
  const size = tracksOf(layout, axis)
    .slice(start(cell, axis), end(cell, axis))
    .reduce((sum, item) => sum + item.size, 0);
  return { edge, size, collapsed, floating };
};
/** Check whether two descriptions place the shared panel the same way.
 * @param {Shared} a
 * @param {Shared} b
 * @returns {boolean}
 */
export const sameShared = (a, b) =>
  a.edge === b.edge &&
  a.collapsed === b.collapsed &&
  Math.abs(a.size - b.size) < 1 &&
  JSON.stringify(a.floating) === JSON.stringify(b.floating);
/** Put the shared panel where another workspace has it. Its old place is closed up, so no gap is left.
 * @param {Layout} layout
 * @param {Shared} shared
 * @returns {Layout}
 */
export const adoptShared = (layout, shared) => {
  if (shared.floating) return float(layout, SHARED_PANEL, shared.floating);
  const next = dockOuter(layout, SHARED_PANEL, shared.edge, shared.size);
  return shared.collapsed ? setCollapsed(next, SHARED_PANEL, true) : next;
};
/** The tracks a boundary really moves. A collapsed bar is rigid, so the line resizes the nearest open track on each side and the bar travels with it.
 * @param {Layout} layout
 * @param {Axis} axis
 * @param {number} index Boundary after this track.
 * @returns {{before:number,after:number}|null} Null when one side has no open track.
 */
const resizedTracks = (layout, axis, index) => {
  const effective = effectiveTracks(layout, axis);
  let before = index;
  while (before >= 0 && effective[before]?.collapsed) before -= 1;
  let after = index + 1;
  while (after < effective.length && effective[after]?.collapsed) after += 1;
  return before < 0 || after >= effective.length ? null : { before, after };
};
/** Whether dragging the boundary after track `index` can change anything.
 * @param {Layout} layout
 * @param {Axis} axis
 * @param {number} index
 * @returns {boolean}
 */
export const isResizable = (layout, axis, index) =>
  resizedTracks(layout, axis, index) !== null;
/** Pixel clamp for dragging the boundary after track `index`.
 * @param {Layout} layout
 * @param {Axis} axis
 * @param {number} index
 * @param {(id:string)=>Minimum} minimum
 * @param {{cols:number[],rows:number[]}} metrics
 * @returns {{low:number,high:number}} Allowed movement in pixels.
 */
export const resizeRange = (layout, axis, index, minimum, metrics) => {
  const sizes = axis === "c" ? metrics.cols : metrics.rows;
  const moved = resizedTracks(layout, axis, index);
  if (!moved) return { low: 0, high: 0 };
  /** Resolve preferred track sizes into constrained CSS pixel sizes.
   * @param {number} from
   * @param {number} to
   * @returns {number}
   */
  const pixels = (from, to) =>
    sizes.slice(from, to).reduce((sum, item) => sum + item, 0);
  let low = -Infinity;
  let high = Infinity;
  for (const [id, cell] of Object.entries(layout.cells)) {
    if (layout.collapsed[id]) continue;
    const grows =
      start(cell, axis) <= moved.before && end(cell, axis) > moved.before;
    const shrinks =
      start(cell, axis) <= moved.after && end(cell, axis) > moved.after;
    if (grows === shrinks) continue;
    const need = axis === "c" ? minimum(id).width : minimum(id).height;
    const current = pixels(start(cell, axis), end(cell, axis));
    if (grows) low = Math.max(low, need - current);
    else high = Math.min(high, current - need);
  }
  low = Math.max(low, MIN_NEW_TRACK / 2 - (sizes[moved.before] ?? 0));
  high = Math.min(high, (sizes[moved.after] ?? 0) - MIN_NEW_TRACK / 2);
  return { low: Math.min(low, 0), high: Math.max(high, 0) };
};
/** Move the boundary after track `index` by `delta` pixels. The open track before the line grows and the open track after it shrinks; the flexible track, wherever it is, absorbs whatever the fixed ones do not.
 * @param {Layout} layout
 * @param {Axis} axis
 * @param {number} index
 * @param {number} delta
 * @param {(id:string)=>Minimum} minimum
 * @param {{cols:number[],rows:number[]}} metrics
 * @returns {Layout}
 */
export const resizeBoundary = (
  layout,
  axis,
  index,
  delta,
  minimum,
  metrics,
) => {
  const next = clone(layout);
  const moved = resizedTracks(next, axis, index);
  if (!moved) return next;
  const range = resizeRange(next, axis, index, minimum, metrics);
  const move = Math.min(range.high, Math.max(range.low, delta));
  const tracks = tracksOf(next, axis);
  const effective = effectiveTracks(next, axis);
  const sizes = axis === "c" ? metrics.cols : metrics.rows;
  /** Distribute additional space across flexible tracks.
   * @param {number} at
   * @param {number} change
   */
  const grow = (at, change) => {
    const item = tracks[at];
    if (item) item.size = Math.max(0, (sizes[at] ?? item.size) + change);
  };
  if (!effective[moved.before]?.flex) grow(moved.before, move);
  if (!effective[moved.after]?.flex) grow(moved.after, -move);
  return next;
};
/** Boundaries that separate two different panels, one per contiguous stretch, so a resize handle exists only where it does something.
 * @param {Layout} layout
 * @param {Axis} axis
 * @returns {{index:number,from:number,to:number,before:string[],after:string[]}[]}
 */
export const boundaries = (layout, axis) => {
  const grid = coverage(layout);
  const across_ = across(axis);
  const lanes = across_ === "r" ? layout.rows.length : layout.cols.length;
  const count = tracksOf(layout, axis).length;
  /** @type {{index:number,from:number,to:number,before:string[],after:string[]}[]} */
  const result = [];
  for (let index = 0; index < count - 1; index += 1) {
    /** @type {{from:number,to:number,before:Set<string>,after:Set<string>}|null} */
    let open = null;
    for (let lane = 0; lane <= lanes; lane += 1) {
      const left =
        lane < lanes
          ? ((axis === "c" ? grid[lane]?.[index] : grid[index]?.[lane]) ?? null)
          : null;
      const right =
        lane < lanes
          ? ((axis === "c"
              ? grid[lane]?.[index + 1]
              : grid[index + 1]?.[lane]) ?? null)
          : null;
      const splits = lane < lanes && left && right && left !== right;
      if (splits) {
        open ??= {
          from: lane,
          to: lane + 1,
          before: new Set(),
          after: new Set(),
        };
        open.to = lane + 1;
        open.before.add(String(left));
        open.after.add(String(right));
      } else if (open) {
        result.push({
          index,
          from: open.from,
          to: open.to,
          before: [...open.before],
          after: [...open.after],
        });
        open = null;
      }
    }
  }
  return result;
};
