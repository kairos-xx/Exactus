/** Graph layout stays deterministic and terminates for cyclic workspaces. */
import assert from "node:assert/strict";
import test from "node:test";
import { defaultGraphPositions } from "../../../../tools/record/studio/web/graph-surface.js";
const flows = ["setup", "checkout", "receipt", "recovery"].map(id => ({
  id,
  name: id,
}));
test("graph branches occupy downstream columns rather than wrapping across predecessors", () => {
  const positions = defaultGraphPositions(flows, [
    { source: "setup", target: "checkout" },
    { source: "checkout", target: "receipt" },
    { source: "checkout", target: "recovery", mode: "fallback" },
  ]);
  assert.deepEqual(positions, {
    setup: { x: 32, y: 32 },
    checkout: { x: 328, y: 32 },
    receipt: { x: 624, y: 32 },
    recovery: { x: 624, y: 272 },
  });
});
test("empty, disconnected, dangling, and cyclic graphs have finite positions", () => {
  assert.deepEqual(defaultGraphPositions([], []), {});
  for (const edges of [
    [],
    [
      { source: "setup", target: "checkout" },
      { source: "checkout", target: "setup" },
      { source: "missing", target: "receipt" },
    ],
    [{ source: "setup", target: "setup", mode: "retry" }],
  ]) {
    const positions = defaultGraphPositions(flows, edges);
    assert.equal(Object.keys(positions).length, flows.length);
    assert.ok(
      Object.values(positions).every(
        ({ x, y }) => Number.isFinite(x) && Number.isFinite(y),
      ),
    );
  }
});
