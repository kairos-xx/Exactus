/** The condition language's tokens, type checks and next-step suggestions. */
import assert from "node:assert/strict";
import test from "node:test";
import {
  analyse,
  suggestNext,
  tokenize,
} from "../../../../tools/record/studio/web/condition-language.js";
/** @type {ConditionTerm[]} */
const terms = [
  {
    name: "flow_succeeded",
    kind: "system",
    value_type: "boolean",
    detail: "ok",
  },
  { name: "sel_card_count", kind: "probe", value_type: "integer", detail: "n" },
  { name: "sel_card_text", kind: "probe", value_type: "string", detail: "t" },
  {
    name: "sel_card_exists",
    kind: "probe",
    value_type: "boolean",
    detail: "e",
  },
];
/** Issue messages produced for a condition text.
 * @param {string} text Condition source.
 * @returns {string[]}
 */
const messages = text =>
  analyse(text, terms, ["card"]).issues.map(issue => issue.message);
test("each word gets the kind that colours it", () => {
  const kinds = tokenize(
    'flow_succeeded and sel_card_count >= 3 or contains(sel_card_text, "x")',
    terms,
  ).map(token => token.kind);
  assert.deepEqual(kinds, [
    "system",
    "logic",
    "probe",
    "compare",
    "number",
    "logic",
    "function",
    "paren",
    "probe",
    "comma",
    "string",
    "paren",
  ]);
});
test("valid conditions have no issues", () => {
  assert.deepEqual(messages("flow_succeeded and sel_card_count >= 3"), []);
  assert.deepEqual(
    messages("not sel_card_exists or sel_card_text in 'abc'"),
    [],
  );
});
test("the checks follow what the evaluator rejects", () => {
  assert.match(messages("sel_card_count")[0] ?? "", /not true or false/);
  assert.match(messages("sel_card_exists > 1")[0] ?? "", /not true or false/);
  assert.match(messages("sel_card_text > 3")[0] ?? "", /numbers with numbers/);
  assert.match(messages("contains(sel_card_text)")[0] ?? "", /takes 2 values/);
  assert.match(
    messages("sel_ghost_count > 1")[0] ?? "",
    /no selector named "ghost"/,
  );
  assert.match(
    messages("flow_succeded")[0] ?? "",
    /Did you mean flow_succeeded/,
  );
  assert.match(messages("a && b")[1] ?? "", /Write and instead/);
});
test("suggestions only offer what fits at the caret", () => {
  /** Suggestion texts offered at a caret position.
   * @param {string} before Text before the caret.
   * @param {string} [fragment] Partial token at the caret.
   * @returns {string[]}
   */
  const next = (before, fragment = "") =>
    suggestNext(before, fragment, terms).map(item => item.text);
  assert.ok(next("sel_card_count ").includes(">="));
  assert.ok(!next("sel_card_count ").includes("in"));
  assert.ok(next("sel_card_text ").includes("in"));
  assert.deepEqual(next("sel_card_count > "), ["sel_card_count"]);
  assert.ok(!next("sel_card_exists > ").includes("flow_succeeded"));
  assert.ok(next("contains(").includes("sel_card_text"));
  assert.ok(!next("contains(").includes("sel_card_count"));
});
