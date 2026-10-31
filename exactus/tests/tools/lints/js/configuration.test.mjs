/** Verify project and portable lint configuration contracts. */
import assert from "node:assert/strict";
import test from "node:test";
import eslint from "../../../../../eslint.config.mjs";
import stylelint from "../../../../../stylelint.config.mjs";
import bundledEslint from "../../../../tools/lints/templates/eslint.config.mjs";
import bundledStylelint from "../../../../tools/lints/templates/stylelint.config.mjs";
test("project and portable JavaScript lint configurations enforce core safety rules", () => {
  for (const config of [eslint, bundledEslint]) {
    const rules = config.find(item => item.rules)?.rules;
    assert.ok(rules);
    assert.equal(rules["no-eval"], "error");
    assert.equal(rules["no-undef"], "error");
    assert.equal(rules["no-unreachable"], "error");
  }
});
test("project and portable CSS configurations reject invalid syntax", () => {
  for (const config of [stylelint, bundledStylelint]) {
    assert.equal(config.rules["block-no-empty"], true);
    assert.equal(config.rules["property-no-unknown"], true);
  }
});
