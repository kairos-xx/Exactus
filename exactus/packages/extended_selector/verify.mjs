import process from "node:process";
import { getCssSelector } from "css-selector-generator";
import * as optimalModule from "optimal-select";
import { finder } from "@medv/finder";
import { ExtendedSelector } from "./editor/extended-selector.js";
import { bestLocalSelector } from "./editor/selector-adapters.js";
const optimal = optimalModule.default ?? optimalModule;
for (const [name, ok] of Object.entries({
  generator: typeof getCssSelector === "function",
  optimal: typeof optimal.getSingleSelector === "function",
  finder: typeof finder === "function",
  engine: typeof ExtendedSelector.prototype.bestSelector === "function",
  adapter: typeof bestLocalSelector === "function",
})) {
  if (!ok) throw new Error(`${name}: missing export`);
  process.stdout.write(`${name}: OK\n`);
}
