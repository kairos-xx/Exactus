/* global process */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
const analyzer = fileURLToPath(
  new URL(
    "../../../../tools/lints/js/js_function_blocks_analyzer.js",
    import.meta.url,
  ),
);
const output = resolve(process.argv[2] ?? ".torture-validation");
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
assert.ok(espree, "Real Espree is required");
const { parse } = await import(espree);
const values = [0, 1, -1, 2, 7, 19, 101];
const operators = ["+", "-", "*", "%"];
const sources = [];
for (const value of values)
  for (const operator of operators) {
    const rhs = operator === "%" ? Math.abs(value) + 2 : value;
    sources.push(
      `function calc(x) { return x ${operator} ${rhs}; }\nprocess.stdout.write(String(calc(3)));`,
    );
  }
sources.push(
  "function f() { return arguments.length; } process.stdout.write(String(f(1,2)));",
  "function f() { return this.value; } process.stdout.write(String(f.call({value:7})));",
  "function Ctor() { return 1; } const Alias = Ctor; const x = new Alias(); process.stdout.write(String(x instanceof Ctor));",
  "function Ctor() { return 1; } Ctor.prototype.x = 2; process.stdout.write(String(Ctor.prototype.x));",
  "process.stdout.write(String(f())); function f() { return 9; }",
  "function* f() { yield 3; } process.stdout.write(String(f().next().value));",
  "class A { outer() { function inner() { return this.x; } return 2; } } process.stdout.write(String(new A().outer()));",
  "class A { constructor(){ this.x=2; } outer() { const inner = () => this.x; return inner(); } } process.stdout.write(String(new A().outer()));",
  "class A { get x(){ return 3; } } process.stdout.write(String(new A().x));",
  "class A { set x(v){ globalThis.y=v; } } new A().x=4; process.stdout.write(String(globalThis.y));",
  "class B { value(){ return 6; } } class A extends B { value(){ return super.value(); } } process.stdout.write(String(new A().value()));",
);
rmSync(output, {
  force: true,
  recursive: true,
});
mkdirSync(output, {
  recursive: true,
});
for (const [index, source] of sources.entries()) {
  const input = resolve(output, `input-${index}.js`);
  writeFileSync(input, source);
  /** @type {import("node:child_process").SpawnSyncReturns<string>} */
  const result = spawnSync(process.execPath, [analyzer], {
    encoding: "utf8",
    input: JSON.stringify({
      file: input,
      espree,
      action: "convert",
      direction: "normalize",
    }),
  });
  assert.equal(result.status, 0, result.stderr);
  const converted = JSON.parse(result.stdout).source;
  parse(converted, {
    ecmaVersion: "latest",
    sourceType: "script",
  });
  writeFileSync(resolve(output, `case-${index}.js`), converted);
}
process.stdout.write(`${sources.length}\n`);
