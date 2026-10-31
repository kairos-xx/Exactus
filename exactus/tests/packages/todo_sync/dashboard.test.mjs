/** Exercise the real checklist dashboard and retain browser V8 coverage. */
import assert from "node:assert/strict";
import {
	execFileSync
} from "node:child_process";
import process from "node:process";
import test from "node:test";
import {
	browserTest,
	root
} from "../../common/browser.mjs";
const markdown = `# Plan
## Work
- [ ] **R01 — Record browser** P0 ONGOING
- [x] **R02 — Graph connections** P1
- [ ] **UI-O03 — Dock panels** P1
- [ ] </script><img src=x onerror=alert(1)>
`;
const {
	EXACTUS_PROJECT_PYTHON
} = process.env;
const html = execFileSync(EXACTUS_PROJECT_PYTHON || `${root}/.venv/bin/python`,
	["-c", "import sys; from exactus.packages.todo_sync.core import render_html; print(render_html(text=sys.stdin.read()))", ], {
		cwd: root,
		input: markdown,
		encoding: "utf8"
	}, ).replace(/src="data:text\/javascript;base64,[^"]+"/, 'src="/exactus/packages/todo_sync/web/dashboard.js"', );
for (const width of [390, 1440, 1728]) {
	test(`dashboard controls and saved state at ${width}px`, async t => {
		await browserTest(t, async (page, url) => {
			/** @type {string[]} */
			const errors = [];
			page.on("pageerror", ( /** @type {Error} */ error) => errors.push(error.message), );
			await page.setViewportSize({
				width,
				height: 900
			});
			await page.route("**/dashboard-test.html", ( /** @type {any} */ route) => route.fulfill({
				contentType: "text/html",
				body: html
			}), );
			await page.goto(`${url}/dashboard-test.html`);
			assert.equal(await page.title(), "TODO progress");
			assert.equal(await page.locator("article.task").count(), 4);
			assert.equal(await page.locator("#completion").innerText(), "25.0%");
			assert.equal(await page.locator("#tasks img").count(), 0);
			await page.locator("#search").fill("dock");
			assert.equal(await page.locator("article.task").count(), 1);
			await page.reload();
			assert.equal(await page.locator("#search").inputValue(), "dock");
			assert.equal(await page.locator("article.task").count(), 1);
			if (width === 390) {
				await page.locator("#mobileFilter").click();
				assert.equal(await page.locator("#mobileFilter").getAttribute("aria-expanded"), "true", );
				await page.locator("#sort").waitFor({ state: "visible" });
			}
			await page.locator("#search").fill("dck");
			await page.locator("#sort").selectOption("relevance");
			assert.equal(await page.locator("article.task").count(), 1);
			await page.locator("#search").fill("no-such-task");
			assert.equal(await page.locator(".empty").count(), 1);
			await page.locator("#search").press("Escape");
			assert.equal(await page.locator("article.task").count(), 4);
			const done = page.locator('button[data-field="status"][data-label="Done"]', );
			await done.click();
			assert.equal(await page.locator("article.task").count(), 1);
			await done.click();
			assert.equal(await page.locator("article.task").count(), 4);
			await ["priority", "category", "workstream", "prefix"].reduce(async (previous, group) => {
					await previous;
					await page.locator("#group").selectOption(group);
					assert.ok(await page.locator(".group-card").count() > 0);
				},
				Promise.resolve(), );
			await ["priority", "category", "id", "document"].reduce(async (previous, sort) => {
					await previous;
					await page.locator("#sort").selectOption(sort);
					assert.equal(await page.locator("article.task").count(), 4);
				},
				Promise.resolve(), );
			await page.locator("#theme").click();
			await page.reload();
			assert.equal(await page.locator("html").getAttribute("data-theme"), "light", );
			await page.locator("article.task .task-title").first().click();
			assert.equal(await page.locator("#docWorkspace").isVisible(), true);
			assert.ok(
				(await page.locator("#docView").innerText()).includes("Graph connections", ), );
			await page.reload();
			assert.equal(await page.locator("#docWorkspace").isVisible(), true);
			await page.locator("#tabTasks").click();
			if (width === 390) await page.locator("#mobileFilter").click();
			await page.locator("#reset").click();
			await page.locator("#search").fill("dock");
			const downloaded = page.waitForEvent("download");
			await page.locator("#export").click();
			const download = await downloaded;
			assert.equal(download.suggestedFilename(), "todo-filtered.json");
			await page.locator("#search").blur();
			await page.keyboard.press("/");
			assert.equal(await page.locator("#search").evaluate(
				( /** @type {HTMLElement} */ element) => element === document.activeElement, ), true, );
			await page.locator("#search").press("Escape");
			assert.equal(await page.locator("article.task").count(), 4);
			assert.equal(await page.evaluate(
				() => document.documentElement.scrollWidth <= innerWidth, ), true, );
			await page.goto(`${url}/dashboard-test.html#s=%invalid`);
			assert.equal(await page.locator("article.task").count(), 4);
			assert.deepEqual(errors, []);
		});
	});
}
