/** The icon set: generated from icons/*.svg and drawn as real inline SVG. */
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import test from "node:test";
import {
  render,
  shapesOf,
} from "../../../../tools/record/studio/web/icons/build-icon-set.mjs";
import { ICONS } from "../../../../tools/record/studio/web/icon-set.js";
const folder = new URL(
  "../../../../tools/record/studio/web/icons",
  import.meta.url,
);
test("icon-set.js matches the SVG files in icons/", () => {
  const generated = readFileSync(new URL("./icon-set.js", folder), "utf8");
  assert.equal(generated, render(), "run node icons/build-icon-set.mjs");
  const files = readdirSync(folder).filter(name => name.endsWith(".svg"));
  assert.deepEqual(
    Object.keys(ICONS).sort(),
    files.map(name => name.replace(/\.svg$/, "")).sort(),
  );
});
test("every icon is drawn on the shared 24 by 24 grid and carries no presentation", () => {
  for (const [name, shapes] of Object.entries(ICONS)) {
    assert.doesNotMatch(shapes, /\b(?:fill|stroke|width|height|style)=/, name);
    assert.match(shapes, /^<(?:path|g|circle|rect)\b/, name);
  }
  assert.throws(
    () =>
      shapesOf("odd.svg", '<svg viewBox="0 0 16 16"><path d="M0 0"/></svg>'),
    /24/,
  );
});
