/** Runtime-neutral checks for the standalone JavaScript fixture. */
import {add, isEven, sumText} from "../web/code.js";
/**
 * Fail when an actual result differs from its expectation.
 * @param {number | boolean | string} actual - Computed result.
 * @param {number | boolean | string} expected - Required result.
 * @returns {void} Nothing.
 * @throws {Error} When the actual result differs from the expectation.
 */
const expectEqual = (actual, expected) => {
  if (actual !== expected) throw new Error(`Expected ${expected}, got ${actual}`);
};
expectEqual(add(2, 3), 5);
expectEqual(isEven(4), true);
expectEqual(isEven(5), false);
expectEqual(sumText(), "5");
