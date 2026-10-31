/* global process */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, writeFileSync } from "node:fs";
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
const npmRoot = spawnSync("npm", ["root", "-g"], {
  encoding: "utf8",
}).stdout?.trim();
/** @type {*} */
const env = process.env;
/** @type {Array<string>} */
const espreeCandidates = [];
if (env.EXACTUS_ESPREE) espreeCandidates.push(env.EXACTUS_ESPREE);
if (npmRoot)
  espreeCandidates.push(
    join(npmRoot, "eslint", "node_modules", "espree", "dist", "espree.cjs"),
  );
const espree = espreeCandidates.find(path => existsSync(path));
assert.ok(espree, "Real Espree is required for the torture suite");
/**
 * Run the analyzer on one source string.
 * @param {string} source JavaScript source.
 * @param {string | null} [direction] Conversion direction.
 * @returns {*} Analyzer payload.
 */
const analyze = (source, direction = null) => {
  const dir = mkdtempSync(join(tmpdir(), "js-torture-"));
  const file = join(dir, "fixture.js");
  writeFileSync(file, source);
  const payload = direction
    ? {
        file,
        espree,
        action: "convert",
        direction,
      }
    : {
        file,
        espree,
        action: "analyze",
      };
  const result = spawnSync(process.execPath, [analyzer], {
    encoding: "utf8",
    input: JSON.stringify(payload),
  });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
};
/**
 * Execute one source string and capture its observable result.
 * @param {string} source JavaScript source.
 * @returns {string} Serialized execution outcome.
 */
const execute = source => {
  const result = spawnSync(process.execPath, ["-e", source], {
    encoding: "utf8",
  });
  return JSON.stringify({
    status: result.status,
    stdout: result.stdout,
    stderr: result.stderr,
  });
};
/**
 * Convert one source and compare runtime behavior.
 * @param {string} source JavaScript source.
 * @returns {*} Conversion payload.
 */
const differential = source => {
  const converted = analyze(source, "normalize");
  assert.equal(
    execute(converted.source),
    execute(source),
    `Semantic mismatch\nORIGINAL:\n${source}\nCONVERTED:\n${converted.source}`,
  );
  return converted;
};
const values = [0, 1, -1, 2, 7, 19, 101];
const operators = ["+", "-", "*", "%"];
test("generated safe standalone functions preserve runtime semantics", () => {
  let cases = 0;
  for (const value of values)
    for (const operator of operators) {
      const divisor = operator === "%" ? Math.abs(value) + 2 : value;
      const source = `function calc(x) { return x ${operator} ${divisor}; }\nprocess.stdout.write(JSON.stringify([calc(0), calc(3), calc(11)]));`;
      const converted = differential(source);
      assert.ok(converted.transformations >= 1);
      cases += 1;
    }
  assert.equal(cases, 28);
});
test("generated parameter shapes preserve runtime semantics", () => {
  const cases = [
    ["function f() { return 3; }", "f()"],
    ["function f(x) { return x * 2; }", "f(4)"],
    ["function f(a, b) { return a + b; }", "f(2, 5)"],
    ["function f(x = 9) { return x; }", "f()"],
    ["function f(...xs) { return xs.length; }", "f(1, 2, 3)"],
    ["function f({x}) { return x; }", "f({x: 8})"],
    ["function f([x]) { return x; }", "f([6])"],
    [
      "async function f(x) { return x + 1; }",
      "f(4).then(v => process.stdout.write(String(v)))",
    ],
  ];
  for (const [declaration, invocation] of cases)
    differential(
      `${declaration}\nPromise.resolve(${invocation}).then(v => { if (v !== undefined) process.stdout.write(String(v)); });`,
    );
});
test("constructibility and prototype observations block arrow conversion", () => {
  for (const suffix of [
    "const x = new Ctor(); process.stdout.write(String(x instanceof Ctor));",
    "Ctor.prototype.answer = 42; process.stdout.write(String(Ctor.prototype.answer));",
    "process.stdout.write(String(Object.hasOwn(Ctor, 'prototype')));",
    "const Alias = Ctor; const x = new Alias(); process.stdout.write(String(x instanceof Ctor));",
  ]) {
    const source = `function Ctor() { return 1; }\n${suffix}`;
    const converted = differential(source);
    assert.match(converted.source, /function Ctor\(\)/);
  }
});
test("dynamic ordinary-function bindings block arrows", () => {
  const cases = [
    "function f() { return arguments.length; } process.stdout.write(String(f(1,2,3)));",
    "function f() { return this.value; } process.stdout.write(String(f.call({value: 7})));",
    "function f() { return new.target ? 1 : 0; } process.stdout.write(String(new f()));",
    "function* f() { yield 3; } process.stdout.write(String(f().next().value));",
  ];
  for (const source of cases) {
    const converted = differential(source);
    assert.match(converted.source, /function\*? f\(/);
  }
});
test("pre-declaration references preserve function hoisting", () => {
  for (const expression of ["f()", "typeof f", "[f][0]()", "(() => f())()"]) {
    const source = `process.stdout.write(String(${expression}));\nfunction f() { return 9; }`;
    const converted = differential(source);
    assert.match(converted.source, /function f\(\)/);
  }
});
test("lexical arrows using this stay arrows under reverse conversion", () => {
  for (const value of values) {
    const source = `const obj = { value: ${value}, make() { return () => this.value; } }; const fn = obj.make(); process.stdout.write(String(fn()));`;
    const converted = analyze(source, "from_arrow");
    assert.equal(execute(converted.source), execute(source));
    assert.ok(converted.source.includes("=> this.value"));
  }
});
test("nested ordinary this does not poison enclosing static eligibility", () => {
  for (const value of values) {
    const source = `class A { outer() { function inner() { return this.x; } return ${value}; } } process.stdout.write(String(new A().outer()));`;
    const blocks = analyze(source);
    const outer = blocks.find(
      /** @param {*} item */ item => item.name === "outer",
    );
    assert.equal(outer.uses_this_or_super, false);
    assert.equal(outer.static_eligible, true);
    differential(source);
  }
});
test("nested lexical this prevents static promotion", () => {
  for (const value of values) {
    const source = `class A { constructor(){ this.x=${value}; } outer() { const inner = () => this.x; return inner(); } } process.stdout.write(String(new A().outer()));`;
    const blocks = analyze(source);
    const outer = blocks.find(
      /** @param {*} item */ item => item.name === "outer",
    );
    assert.equal(outer.uses_this_or_super, true);
    assert.equal(outer.static_eligible, false);
    differential(source);
  }
});
test("accessors constructors generators and super remain structurally valid", () => {
  const sources = [
    "class A { constructor(){ this.x=1; } } process.stdout.write(String(new A().x));",
    "class A { get x(){ return 3; } } process.stdout.write(String(new A().x));",
    "class A { set x(v){ globalThis.y=v; } } new A().x=4; process.stdout.write(String(globalThis.y));",
    "class A { *items(){ yield 5; } } process.stdout.write(String(new A().items().next().value));",
    "class B { value(){ return 6; } } class A extends B { value(){ return super.value(); } } process.stdout.write(String(new A().value()));",
  ];
  for (const source of sources) differential(source);
});
test("normalization is idempotent across generated safe cases", () => {
  for (const value of values) {
    const source = `function f(x) { return x + ${value}; } process.stdout.write(String(f(2)));`;
    const once = analyze(source, "normalize");
    const twice = analyze(once.source, "normalize");
    assert.equal(twice.source, once.source);
    assert.equal(twice.transformations, 0);
  }
});
