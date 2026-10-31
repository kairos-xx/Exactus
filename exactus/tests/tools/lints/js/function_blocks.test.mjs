/* global process */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
const analyzer = fileURLToPath(
  new URL(
    "../../../../packages/organize/js/class_organizer.js",
    import.meta.url,
  ),
);
const espree = fileURLToPath(new URL("./fake_espree.cjs", import.meta.url));
/**
 * Return execute.
 * @param {*} source Source.
 * @param {Object} extra Extra.
 * @returns {*} The resulting value.
 */
const execute = (source, extra = {}) => {
  const dir = mkdtempSync(join(tmpdir(), "js-blocks-"));
  const file = join(dir, "fixture.js");
  writeFileSync(file, source);
  return spawnSync(process.execPath, [analyzer], {
    encoding: "utf8",
    input: JSON.stringify({
      action: "analyze",
      file,
      espree,
      ...extra,
    }),
  });
};
/**
 * Return output.
 * @param {*} result Result.
 * @returns {*} The resulting value.
 */
const output = result => {
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
};
test("analyzes declarations, methods, arrows and class ownership", () => {
  const result = output(
    execute(
      `/*SCENARIO_ANALYZE*/\nfunction free(x) { return x; }\nclass Demo { method(y) { return y; } }\nconst arrow = z => z;`,
    ),
  );
  assert.equal(result.length, 3);
  assert.deepEqual(
    result.map(/** @param {*} item */ item => item.kind),
    ["function_declaration", "method", "arrow_function"],
  );
  assert.equal(result[1].class_name, "Demo");
  assert.equal(result[1].recommendation, "make static arrow");
  assert.equal(result[2].arrow_current, true);
});
test("converts compact arrows including object returns and static methods", () => {
  const source = `/*SCENARIO_TO_ARROW*/\nfunction double(x) { return x * 2; }\nfunction make(x) { return { value: x }; }\nclass Demo { method(a, b) { return a + b; } }`;
  const result = output(
    execute(source, {
      action: "convert",
      direction: "to_arrow",
    }),
  );
  assert.equal(result.transformations, 3);
  assert.match(result.source, /const double = x => x \* 2;/);
  assert.match(result.source, /const make = x => \(\{ value: x \}\);/);
  assert.match(result.source, /static method = \(a, b\) => a \+ b;/);
});
test("reports semantic blockers and leaves blocked methods unchanged", () => {
  const source = `/*SCENARIO_BLOCKERS*/\nclass Demo { constructor() { this.x; } get value() { arguments; } set value(v) { new.target; } gen() { yield 1; } }`;
  const analysis = output(execute(source));
  assert.equal(analysis.length, 4);
  assert.ok(analysis[0].arrow_blockers.includes("constructor"));
  assert.ok(analysis[0].arrow_blockers.includes("dynamic this/super"));
  assert.ok(analysis[1].arrow_blockers.includes("getter"));
  assert.ok(analysis[1].arrow_blockers.includes("arguments"));
  assert.ok(analysis[2].arrow_blockers.includes("setter"));
  assert.ok(analysis[2].arrow_blockers.includes("new.target"));
  assert.ok(analysis[3].arrow_blockers.includes("generator/yield"));
  const converted = output(
    execute(source, {
      action: "convert",
      direction: "to_arrow",
    }),
  );
  assert.equal(converted.changed, false);
  assert.equal(converted.transformations, 0);
});
test("converts arrows back to ordinary function and static method notation", () => {
  const source = `/*SCENARIO_FROM_ARROW*/\nconst inc = x => x + 1;\nclass Demo { static twice = x => x * 2; }`;
  const result = output(
    execute(source, {
      action: "convert",
      direction: "from_arrow",
    }),
  );
  assert.equal(result.transformations, 2);
  assert.match(
    result.source,
    /const inc = function\(x\) \{ return x \+ 1; \};/,
  );
  assert.match(result.source, /static twice\(x\) \{ return x \* 2; \}/);
});
test("falls back from module to script parsing", () => {
  const result = output(execute("/*SCENARIO_SCRIPT_FALLBACK*/"));
  assert.deepEqual(result, []);
});
test("rejects unsupported conversion directions", () => {
  const result = execute("/*SCENARIO_SCRIPT_FALLBACK*/", {
    action: "convert",
    direction: "sideways",
  });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Unsupported conversion direction/);
});
test("covers function expressions, class fields, static methods and object methods", () => {
  const source = `/*SCENARIO_MISC*/\ntarget.work = function(a) { const q = 1; return q; };\nclass Misc { field = function(v) { return v; }; static ready() { return 1; } }\nconst obj = { run(x) { return x; } };`;
  const analysis = output(execute(source));
  assert.deepEqual(
    analysis.map(/** @param {*} item */ item => item.kind),
    ["function_expression", "class_field", "method", "object_method"],
  );
  assert.equal(analysis[0].name, "work");
  assert.equal(analysis[2].recommendation, "use static arrow");
  const converted = output(
    execute(source, {
      action: "convert",
      direction: "to_arrow",
    }),
  );
  assert.equal(converted.transformations, 4);
  assert.match(
    converted.source,
    /target\.work = async a => \{ const q = 1; return q; \}/,
  );
  assert.match(converted.source, /field = v => v;/);
  assert.match(converted.source, /static ready = \(\) => 1;/);
  assert.match(converted.source, /run: x => x/);
});
test("does not reverse lexical arrows that use this", () => {
  const source = `/*SCENARIO_ARROW_BLOCKED*/\nconst blocked = x => this.x;`;
  const result = output(
    execute(source, {
      action: "convert",
      direction: "from_arrow",
    }),
  );
  assert.equal(result.transformations, 0);
  assert.equal(result.changed, false);
});
test("rethrows the original module parse error if script parsing also fails", () => {
  const result = execute("/*SCENARIO_PARSE_FAIL*/");
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Unknown fixture scenario|script failure/);
});
test("distinguishes nested ordinary and lexical receiver ownership", () => {
  const source = `/*SCENARIO_DEEP_METHODS*/\nclass Deep { nestedRegular() { function inner() { return this.x; } return 1; } nestedArrow() { const inner = () => this.x; return inner(); } receiver() { return this.x; } static utility(x) { return x; } plain(x) { return x; } async load(x) { return x; } get value() { return this.x; } set value(v) { this.x = v; } constructor() { this.x = 1; } *items() { yield 1; } }`;
  const result = output(execute(source));
  /** @type {*} */
  const byName = Object.fromEntries(
    result
      .filter(/** @param {*} item */ item => item.kind === "method")
      .map(
        /** @param {*} item */ item => [
          `${item.name}:${item.method_kind}`,
          item,
        ],
      ),
  );
  assert.equal(byName["nestedRegular:method"].uses_this_or_super, false);
  assert.equal(byName["nestedRegular:method"].static_eligible, true);
  assert.equal(
    byName["nestedRegular:method"].recommendation,
    "make static arrow",
  );
  assert.equal(byName["nestedArrow:method"].uses_this_or_super, true);
  assert.equal(byName["nestedArrow:method"].static_eligible, false);
  assert.equal(byName["receiver:method"].recommendation, "keep");
  assert.equal(byName["utility:method"].static_current, true);
  assert.equal(byName["utility:method"].recommendation, "use static arrow");
  assert.equal(byName["plain:method"].recommendation, "make static arrow");
  assert.equal(byName["load:method"].recommendation, "make static arrow");
});
test("classifies accessors constructors and generators as non-arrow callables", () => {
  const source = `/*SCENARIO_DEEP_METHODS*/\nclass Deep { nestedRegular() { function inner() { return this.x; } return 1; } nestedArrow() { const inner = () => this.x; return inner(); } receiver() { return this.x; } static utility(x) { return x; } plain(x) { return x; } async load(x) { return x; } get value() { return this.x; } set value(v) { this.x = v; } constructor() { this.x = 1; } *items() { yield 1; } }`;
  const methods = output(execute(source)).filter(
    /** @param {*} item */ item => item.kind === "method",
  );
  const getter = methods.find(
    /** @param {*} item */ item => item.method_kind === "get",
  );
  const setter = methods.find(
    /** @param {*} item */ item => item.method_kind === "set",
  );
  const constructor = methods.find(
    /** @param {*} item */ item => item.method_kind === "constructor",
  );
  const generator = methods.find(
    /** @param {*} item */ item => item.name === "items",
  );
  assert.deepEqual(getter.arrow_blockers.sort(), [
    "dynamic this/super",
    "getter",
  ]);
  assert.deepEqual(setter.arrow_blockers.sort(), [
    "dynamic this/super",
    "setter",
  ]);
  assert.ok(constructor.arrow_blockers.includes("constructor"));
  assert.ok(generator.arrow_blockers.includes("generator/yield"));
  assert.equal(getter.static_eligible, false);
  assert.equal(setter.static_eligible, false);
  assert.equal(constructor.static_eligible, false);
});
test("automatic normalization follows static and arrow conventions", () => {
  const source = `/*SCENARIO_DEEP_METHODS*/\nclass Deep { nestedRegular() { function inner() { return this.x; } return 1; } nestedArrow() { const inner = () => this.x; return inner(); } receiver() { return this.x; } static utility(x) { return x; } plain(x) { return x; } async load(x) { return x; } get value() { return this.x; } set value(v) { this.x = v; } constructor() { this.x = 1; } *items() { yield 1; } }`;
  const result = output(
    execute(source, {
      action: "convert",
      direction: "normalize",
    }),
  );
  assert.equal(result.transformations, 1);
  assert.match(result.source, /nestedRegular\(\) \{/);
  assert.match(result.source, /nestedArrow\(\) \{/);
  assert.match(result.source, /receiver\(\) \{/);
  assert.match(result.source, /static utility = x =>/);
  assert.match(result.source, /plain\(x\) \{/);
  assert.match(result.source, /async load\(x\) \{/);
  assert.match(result.source, /get value\(\)/);
  assert.match(result.source, /set value\(v\)/);
  assert.match(result.source, /constructor\(\)/);
  assert.match(result.source, /\*items\(\)/);
  assert.doesNotMatch(result.source, /static \*items/);
});
test("normalization applies compact parameter conventions", () => {
  const source = `/*SCENARIO_PARAMETERS*/\nclass Params { one(x) { return x; } many(a, b) { return a; } none() { return 1; } }`;
  const result = output(
    execute(source, {
      action: "convert",
      direction: "normalize",
    }),
  );
  assert.equal(result.transformations, 0);
  assert.equal(result.source, source);
});
test("normalization is idempotent for already-arrow callables", () => {
  const source = `/*SCENARIO_FROM_ARROW*/\nconst inc = x => x + 1;\nclass Demo { static twice = x => x * 2; }`;
  const result = output(
    execute(source, {
      action: "convert",
      direction: "normalize",
    }),
  );
  assert.equal(result.transformations, 0);
  assert.equal(result.changed, false);
  assert.equal(result.source, source);
});
test("blocks receiver-free functions whose ordinary identity is observable", () => {
  const source = `/*SCENARIO_IDENTITY_FRINGE*/\nhoisted();\nfunction hoisted() { return 1; }\nfunction Ctor() { return 1; }\nnew Ctor();\nfunction Proto() { return 1; }\nProto.prototype.x = 1;\nfunction safe() { return 1; }\nfunction argsOnly() { return arguments.length; }\nfunction targetOnly() { return new.target; }\nfunction* gen() { yield 1; }\nconst named = function recur() { return 1; };`;
  const analysis = output(execute(source));
  /** @type {*} */
  const byName = Object.fromEntries(
    analysis.map(/** @param {*} item */ item => [item.name, item]),
  );
  assert.ok(byName.hoisted.arrow_blockers.includes("declaration hoisting"));
  assert.ok(byName.Ctor.arrow_blockers.includes("constructible/new"));
  assert.ok(byName.Proto.arrow_blockers.includes("prototype"));
  assert.deepEqual(byName.safe.arrow_blockers, []);
  assert.equal(byName.safe.recommendation, "use arrow");
  assert.ok(byName.argsOnly.arrow_blockers.includes("arguments"));
  assert.ok(byName.targetOnly.arrow_blockers.includes("new.target"));
  assert.ok(byName.gen.arrow_blockers.includes("generator/yield"));
  assert.ok(byName.recur.arrow_blockers.includes("named function expression"));
});
test("normalization converts only the semantically safe receiver-free function", () => {
  const source = `/*SCENARIO_IDENTITY_FRINGE*/\nhoisted();\nfunction hoisted() { return 1; }\nfunction Ctor() { return 1; }\nnew Ctor();\nfunction Proto() { return 1; }\nProto.prototype.x = 1;\nfunction safe() { return 1; }\nfunction argsOnly() { return arguments.length; }\nfunction targetOnly() { return new.target; }\nfunction* gen() { yield 1; }\nconst named = function recur() { return 1; };`;
  const result = output(
    execute(source, {
      action: "convert",
      direction: "normalize",
    }),
  );
  assert.equal(result.transformations, 1);
  assert.match(result.source, /const safe = \(\) => 1;/);
  assert.match(result.source, /function hoisted\(\)/);
  assert.match(result.source, /function Ctor\(\)/);
  assert.match(result.source, /function Proto\(\)/);
  assert.match(result.source, /function argsOnly\(\)/);
  assert.match(result.source, /function targetOnly\(\)/);
  assert.match(result.source, /function\* gen\(\)/);
  assert.match(result.source, /function recur\(\)/);
});
test("never converts lexical arrows to ordinary functions when lexical bindings matter", () => {
  const source = `/*SCENARIO_LEXICAL_ARROWS*/\nconst lexicalThis = () => this.x;\nconst lexicalArgs = () => arguments[0];\nconst lexicalTarget = () => new.target;\nconst safeArrow = () => 1;`;
  const analysis = output(execute(source));
  /** @type {*} */
  const byName = Object.fromEntries(
    analysis.map(/** @param {*} item */ item => [item.name, item]),
  );
  assert.equal(byName.lexicalThis.uses_this_or_super, true);
  assert.equal(byName.lexicalArgs.uses_arguments, true);
  assert.equal(byName.lexicalTarget.uses_new_target, true);
  const result = output(
    execute(source, {
      action: "convert",
      direction: "from_arrow",
    }),
  );
  assert.equal(result.transformations, 1);
  assert.match(result.source, /const lexicalThis = \(\) => this\.x;/);
  assert.match(result.source, /const lexicalArgs = \(\) => arguments\[0\];/);
  assert.match(result.source, /const lexicalTarget = \(\) => new\.target;/);
  assert.match(
    result.source,
    /const safeArrow = function\(\) \{ return 1; \};/,
  );
});
test("receiver-free arguments method becomes static but never arrow", () => {
  const source = `/*SCENARIO_METHOD_FRINGE*/\nclass Fringe { argsOnly() { return arguments.length; } targetOnly() { return new.target; } *gen() { yield 1; } constructor() { return 1; } get value() { return 1; } set value(v) { cache = v; } plain() { return 1; } }`;
  const methods = output(execute(source));
  const argsOnly = methods.find(
    /** @param {*} item */ item => item.name === "argsOnly",
  );
  assert.equal(argsOnly.uses_this_or_super, false);
  assert.equal(argsOnly.static_eligible, true);
  assert.equal(argsOnly.arrow_eligible, false);
  assert.equal(argsOnly.recommendation, "make static");
  const normalized = output(
    execute(source, {
      action: "convert",
      direction: "normalize",
    }),
  );
  assert.match(normalized.source, /class Fringe \{ argsOnly\(\)/);
  assert.doesNotMatch(normalized.source, /static argsOnly\s*=/);
});
test("receiver-free new.target method becomes static but remains ordinary", () => {
  const source = `/*SCENARIO_METHOD_FRINGE*/\nclass Fringe { argsOnly() { return arguments.length; } targetOnly() { return new.target; } *gen() { yield 1; } constructor() { return 1; } get value() { return 1; } set value(v) { cache = v; } plain() { return 1; } }`;
  const target = output(execute(source)).find(
    /** @param {*} item */ item => item.name === "targetOnly",
  );
  assert.equal(target.static_eligible, true);
  assert.ok(target.arrow_blockers.includes("new.target"));
  assert.equal(target.recommendation, "make static");
  const normalized = output(
    execute(source, {
      action: "convert",
      direction: "normalize",
    }),
  );
  assert.match(normalized.source, /targetOnly\(\)/);
  assert.doesNotMatch(normalized.source, /static targetOnly/);
});
test("receiver-free generator becomes static generator but never arrow", () => {
  const source = `/*SCENARIO_METHOD_FRINGE*/\nclass Fringe { argsOnly() { return arguments.length; } targetOnly() { return new.target; } *gen() { yield 1; } constructor() { return 1; } get value() { return 1; } set value(v) { cache = v; } plain() { return 1; } }`;
  const generator = output(execute(source)).find(
    /** @param {*} item */ item => item.name === "gen",
  );
  assert.equal(generator.static_eligible, true);
  assert.ok(generator.arrow_blockers.includes("generator/yield"));
  const normalized = output(
    execute(source, {
      action: "convert",
      direction: "normalize",
    }),
  );
  assert.match(normalized.source, /\*gen\(\)/);
  assert.doesNotMatch(normalized.source, /static \*gen/);
});
test("receiver-free constructor and accessors are never promoted to static", () => {
  const source = `/*SCENARIO_METHOD_FRINGE*/\nclass Fringe { argsOnly() { return arguments.length; } targetOnly() { return new.target; } *gen() { yield 1; } constructor() { return 1; } get value() { return 1; } set value(v) { cache = v; } plain() { return 1; } }`;
  const methods = output(execute(source));
  const constructor = methods.find(
    /** @param {*} item */ item => item.method_kind === "constructor",
  );
  const getter = methods.find(
    /** @param {*} item */ item => item.method_kind === "get",
  );
  const setter = methods.find(
    /** @param {*} item */ item => item.method_kind === "set",
  );
  assert.equal(constructor.static_eligible, false);
  assert.equal(getter.static_eligible, false);
  assert.equal(setter.static_eligible, false);
  const normalized = output(
    execute(source, {
      action: "convert",
      direction: "normalize",
    }),
  );
  assert.match(normalized.source, /constructor\(\)/);
  assert.match(normalized.source, /get value\(\)/);
  assert.match(normalized.source, /set value\(v\)/);
  assert.doesNotMatch(
    normalized.source,
    /static constructor|static get value|static set value/,
  );
});
test("receiver-free ordinary method still follows static arrow convention", () => {
  const source = `/*SCENARIO_METHOD_FRINGE*/\nclass Fringe { argsOnly() { return arguments.length; } targetOnly() { return new.target; } *gen() { yield 1; } constructor() { return 1; } get value() { return 1; } set value(v) { cache = v; } plain() { return 1; } }`;
  const plain = output(execute(source)).find(
    /** @param {*} item */ item => item.name === "plain",
  );
  assert.equal(plain.static_eligible, true);
  assert.equal(plain.arrow_eligible, true);
  assert.equal(plain.recommendation, "make static arrow");
  const normalized = output(
    execute(source, {
      action: "convert",
      direction: "normalize",
    }),
  );
  assert.match(normalized.source, /plain\(\)/);
  assert.doesNotMatch(normalized.source, /static plain/);
});
test("forced to-arrow refuses hoisted constructor prototype and named-expression cases", () => {
  const source = `/*SCENARIO_IDENTITY_FRINGE*/\nhoisted();\nfunction hoisted() { return 1; }\nfunction Ctor() { return 1; }\nnew Ctor();\nfunction Proto() { return 1; }\nProto.prototype.x = 1;\nfunction safe() { return 1; }\nfunction argsOnly() { return arguments.length; }\nfunction targetOnly() { return new.target; }\nfunction* gen() { yield 1; }\nconst named = function recur() { return 1; };`;
  const result = output(
    execute(source, {
      action: "convert",
      direction: "to_arrow",
    }),
  );
  assert.equal(result.transformations, 1);
  assert.match(result.source, /const safe = \(\) => 1;/);
  assert.match(result.source, /function hoisted/);
  assert.match(result.source, /function Ctor/);
  assert.match(result.source, /function Proto/);
  assert.match(result.source, /function recur/);
});
test("lexical this arrow remains arrow under forced reverse conversion", () => {
  const source = `/*SCENARIO_LEXICAL_ARROWS*/\nconst lexicalThis = () => this.x;\nconst lexicalArgs = () => arguments[0];\nconst lexicalTarget = () => new.target;\nconst safeArrow = () => 1;`;
  const result = output(
    execute(source, {
      action: "convert",
      direction: "from_arrow",
    }),
  );
  assert.match(result.source, /lexicalThis = \(\) => this\.x/);
});
test("lexical arguments arrow remains arrow under forced reverse conversion", () => {
  const source = `/*SCENARIO_LEXICAL_ARROWS*/\nconst lexicalThis = () => this.x;\nconst lexicalArgs = () => arguments[0];\nconst lexicalTarget = () => new.target;\nconst safeArrow = () => 1;`;
  const result = output(
    execute(source, {
      action: "convert",
      direction: "from_arrow",
    }),
  );
  assert.match(result.source, /lexicalArgs = \(\) => arguments\[0\]/);
});
test("lexical new.target arrow remains arrow under forced reverse conversion", () => {
  const source = `/*SCENARIO_LEXICAL_ARROWS*/\nconst lexicalThis = () => this.x;\nconst lexicalArgs = () => arguments[0];\nconst lexicalTarget = () => new.target;\nconst safeArrow = () => 1;`;
  const result = output(
    execute(source, {
      action: "convert",
      direction: "from_arrow",
    }),
  );
  assert.match(result.source, /lexicalTarget = \(\) => new\.target/);
});
