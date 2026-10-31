/** Black-box Node tests for the meaningful Python CLI contract. */
import assert from "node:assert/strict";
import {
	mkdtempSync,
	mkdirSync,
	readFileSync,
	writeFileSync
} from "node:fs";
import {
	tmpdir
} from "node:os";
import {
	join,
	resolve
} from "node:path";
import {
	spawnSync
} from "node:child_process";
import test from "node:test";
/** Exercise the Python CLI through deterministic subprocess fixtures. */
class MeaningfulCliHarness {
	static root = resolve(import.meta.dirname, "../../../..");
	static python = "python3";
	/**
	 * Run the Python CLI with the given arguments.
	 * @param {string[]} args Arguments forwarded to ``python -m exactus.packages.meaningful``.
	 * @returns {import("node:child_process").SpawnSyncReturns<string>} Spawn result.
	 */
	static run = args => spawnSync(MeaningfulCliHarness.python,
		["-m", "exactus.packages.meaningful", ...args], {
			cwd: MeaningfulCliHarness.root,
			encoding: "utf8"
		}, );
	static fixture = () => {
		const root = mkdtempSync(join(tmpdir(), "meaningful-js-"));
		const source = join(root, "src");
		mkdirSync(source);
		writeFileSync(join(source, "keep.py"), "VALUE = 1\n", "utf8");
		writeFileSync(join(source, "behavior.py"), "def double(value: int) -> int:\n    return value * 2\n", "utf8", );
		return {
			root,
			source
		};
	};
}
test("CLI emits complete run JSON", () => {
	const {
		source
	} = MeaningfulCliHarness.fixture();
	const result = MeaningfulCliHarness.run([source, "--workers", "2"]);
	assert.equal(result.status, 0, result.stderr);
	const payload = JSON.parse(result.stdout);
	assert.equal(payload.findings.length, 2);
	assert.equal(payload.metadata.total_files, 2);
	assert.equal(payload.metadata.succeeded, 2);
	assert.ok(payload.metadata.duration_seconds >= 0);
});
test("CLI accepts thresholds, filters, and evidence context", () => {
	const {
		source
	} = MeaningfulCliHarness.fixture();
	const result = MeaningfulCliHarness.run([
		join(source, "*.py"), "--exclude",
		join(source, "keep.py"), "--threshold-test-0-to-1", "0", "--threshold-test-1-to-2", "0", "--threshold-test-2-to-3", "0", "--evidence-context", "0",
	]);
	assert.equal(result.status, 0, result.stderr);
	const payload = JSON.parse(result.stdout);
	assert.equal(payload.findings.length, 1);
	assert.equal(payload.findings[0].level, "TEST-3");
});
test("CLI writes JSON with output file", () => {
	const {
		root,
		source
	} = MeaningfulCliHarness.fixture();
	const output = join(root, "nested", "report.json");
	const result = MeaningfulCliHarness.run([source, "--output-file", output]);
	assert.equal(result.status, 0, result.stderr);
	assert.equal(result.stdout, "");
	assert.equal(JSON.parse(readFileSync(output, "utf8")).findings.length, 2);
});
test("CLI reports invalid paths", () => {
	const result = MeaningfulCliHarness.run(["definitely-missing.py"]);
	assert.equal(result.status, 2);
	assert.match(result.stderr, /^error:/u);
});
