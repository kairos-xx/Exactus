/// <reference types="node" />
import assert from "node:assert/strict";
import test from "node:test";
import { add, isEven, sumText } from "../web/code.js";
test("add sums operands", () => {
  assert.equal(add(2, 3), 5);
});
test("isEven reports parity", () => {
  assert.ok(isEven(4));
  assert.equal(isEven(5), false);
});
test("sumText renders the sum", () => {
  assert.equal(sumText(), "5");
});
