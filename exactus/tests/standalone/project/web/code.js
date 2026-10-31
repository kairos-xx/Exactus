/**
 * Minimal JavaScript for the standalone fixture page.
 */
/**
 * Add two numbers.
 * @param {number} left - First operand.
 * @param {number} right - Second operand.
 * @returns {number} The sum of both operands.
 */
export const add = (left, right) => left + right;
/**
 * Report whether a number is even.
 * @param {number} value - Number under test.
 * @returns {boolean} True when the value divides evenly by two.
 */
export const isEven = value => value % 2 === 0;
/**
 * Format the demo sum for display.
 * @returns {string} The rendered sum text.
 */
export const sumText = () => String(add(2, 3));
