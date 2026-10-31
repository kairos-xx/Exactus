import assert from "node:assert/strict";
import test from "node:test";
import {
	browserTest
} from "../../../common/browser.mjs";
test("clock API supports timeline time, arrow callbacks and safe disposal", async t => {
	await browserTest(t, async (page, url) => {
		/** @type {string[]} */
		const errors = [];
		page.on("pageerror", ( /** @type {Error} */ error) => errors.push(error.message), );
		await page.goto(`${url}/exactus/packages/widgets/widget_clock/examples/web/index.html`);
		const result = await page.evaluate(() => {
			const Clock = /** @type {any} */ (globalThis).AnalogClock;
			const mount = document.createElement("div");
			mount.style.width = "640px";
			mount.style.height = "180px";
			document.body.append(mount);
			const clock = new Clock(mount, {
				live: false,
				recording: false
			});
			/** @type {string[]} */
			const failures = [];
			/** Record a failed expectation by name.
			 * @param {boolean} condition Whether the expectation held.
			 * @param {string} name Expectation label reported on failure.
			 * @returns {void}
			 */
			const check = (condition, name) => {
				if (!condition) failures.push(name);
			};
			/** Report whether an operation throws.
			 * @param {()=>unknown} operation Operation expected to throw.
			 * @returns {boolean}
			 */
			const rejects = operation => {
				try {
					operation();
					return false;
				} catch {
					return true;
				}
			};
			const setTime = clock.setTime.bind(clock);
			check(setTime(1234) === clock, "bound chainable setTime");
			check(clock.timecode === "00:00:01.07", "milliseconds at 30 fps");
			check(clock.timeMilliseconds === 1234 && clock.frameRequest === undefined, "external clock owns no playback loop", );
			clock.setFrame(1799);
			check(clock.timecode === "00:00:59.29", "frame before minute rollover");
			clock.setFrame(1800);
			check(clock.timecode === "00:01:00.00", "minute rollover");
			check(Clock.formatTime(3600000) === "01:00:00.00", "hour rollover");
			check(Clock.formatFrame(17, {
				fps: 24
			}) === "00:00:00.17", "24 fps formatting", );
			clock.set({
				template: "dd:dd:dd.ddd"
			}).setTime(1234);
			check(clock.timecode === "00:00:01.234", "timeline millisecond precision", );
			clock.set({
				template: "dd:dd:dd.dd"
			}).setFrame(1800);
			const snapshot = clock.getSettings();
			check(rejects(() => clock.set({
				padding: 8,
				fps: 0
			})), "invalid settings rejected", );
			check(clock.settings.padding === snapshot.padding, "invalid settings atomic", );
			check(rejects(() => clock.setTime(-1)) && rejects(() => clock.setTime(Infinity)), "invalid elapsed time rejected", );
			check(rejects(() => clock.setFrame(1.5)) && rejects(() => Clock.formatTime(360000000)), "frame and overflow validation", );
			check(rejects(() => {
				clock.value = "bad00123456";
			}), "malformed value rejected", );
			clock.set({
				mode: "matrix"
			});
			check(clock.timecode === "00:01:00.00" && Boolean(mount.querySelector(".sst-matrix")), "matrix switch retains timeline position", );
			clock.set({
				mode: "segment"
			});
			check(mount.querySelectorAll(".sst-on").length > 0, "segment rebuild restores lit digits", );
			clock.set({
				structure: [{
					type: "group",
					digits: 2
				}]
			});
			snapshot.structure = [{
				type: "group",
				digits: 12
			}];
			const structure = clock.normalizedStructure();
			structure[0].digits = 8;
			check(clock.digitCount() === 2, "defensive structure snapshots");
			check(rejects(() => clock.setTime(0)), "incompatible timeline structure rejected", );
			check(typeof Clock.prototype.setTime === "function" && clock.setTime === Clock.prototype.setTime, "methods live on the prototype", );
			check(Object.values(clock).every(value => typeof value !== "function"), "no instance arrow fields", );
			check(typeof Clock.matrixGlyph === "function", "pure glyph factory is static", );
			clock.destroy();
			clock.destroy();
			check(clock.destroyed && !mount.querySelector(".sst-root"), "idempotent disposal", );
			check(rejects(() => clock.setTime(0)), "destroyed instances reject updates", );
			mount.remove();
			return failures;
		});
		assert.deepEqual(result, []);
		assert.deepEqual(errors, []);
	});
});
test("target resizes by pointer and keyboard and controls remain functional", async t => {
	await browserTest(t, async (page, url) => {
		/** @type {string[]} */
		const errors = [];
		page.on("pageerror", ( /** @type {Error} */ error) => errors.push(error.message), );
		await page.goto(`${url}/exactus/packages/widgets/widget_clock/examples/web/index.html`);
		assert.equal(await page.title(), "AnalogClock Demo");
		assert.equal(await page.locator("#analog-clock-target").count(), 1);
		const target = page.locator("#analog-clock-target");
		const handle = page.locator(".target-resize-handle");
		const before = await target.boundingBox();
		const grip = await handle.boundingBox();
		assert.ok(before && grip);
		await page.mouse.move(grip.x + grip.width / 2, grip.y + grip.height / 2);
		await page.mouse.down();
		await page.mouse.move(grip.x - 100, grip.y - 80, {
			steps: 8
		});
		await page.mouse.up();
		const after = await target.boundingBox();
		assert.ok(after && after.width < before.width - 80 && after.height < before.height - 60, );
		assert.ok(after.width > 288 && after.height > 128);
		await handle.focus();
		await page.keyboard.press("ArrowRight");
		const keyboard = await target.boundingBox();
		assert.ok(keyboard && keyboard.width > after.width);
		await page.locator("#clear-values").click();
		await page.locator("#group-values input").first().fill("12");
		await page.locator("#group-values input").first().press("Tab");
		assert.equal(await page.locator(".sst-clock").getAttribute("aria-label"), "12:00:00.00", );
		await page.locator("#mode").selectOption("matrix");
		assert.equal(await page.locator(".sst-root").getAttribute("data-mode"), "matrix", );
		await page.locator("#mode").selectOption("segment");
		const length = page.locator(".structure-row").first().getByLabel("segmentLength value", {
			exact: true
		});
		const polygon = page.locator(".sst-digit polygon").first();
		const points = await polygon.getAttribute("points");
		await length.fill("95");
		assert.notEqual(await polygon.getAttribute("points"), points);
		assert.equal(await page.locator(".structure-row").first().getByLabel("segmentLength slider", {
			exact: true
		}).inputValue(), "95", );
		assert.deepEqual(errors, []);
		await [1440, 1728, 390].reduce(async (previous, width) => {
			await previous;
			await page.setViewportSize({
				width,
				height: 900
			});
			await page.screenshot({
				path: `/tmp/analog-clock-${width}.png`
			});
		}, Promise.resolve());
	});
});
test("CSS bindings update native styles and runtime rows; ESM import needs no external CSS", async t => {
	await browserTest(t, async (page, url) => {
		await page.goto(`${url}/exactus/packages/widgets/widget_clock/examples/web/index.html`);
		await page.evaluate(async () => {
			// The page serves this path; it is not a file the type checker can see.
			const specifier = "/exactus/packages/widgets/widget_clock/index.js";
			const {
				AnalogClock: Clock
			} = await import(specifier);
			const mount = document.createElement("div");
			mount.id = "bound-clock";
			mount.style.width = "600px";
			mount.style.height = "160px";
			mount.style.setProperty("--off-duration", "300ms");
			mount.style.setProperty("--rows", "9");
			document.body.append(mount);
			const clock = new Clock(mount, {
				live: false
			});
			Reflect.set(globalThis, "boundClock", clock);
			clock.setTime(1000);
			clock.settings.segmentOffDuration = "--off-duration";
			clock.settings.matrixRows = "--rows";
		});
		assert.equal(await page.locator("#bound-clock .sst-group").first().evaluate(( /** @type {Element} */ element) => getComputedStyle(element).getPropertyValue("--sst-off-time").trim(), ), "300ms", );
		await page.evaluate(() => {
			const mount = document.getElementById("bound-clock");
			mount?.style.setProperty("--off-duration", "0.5s");
			mount?.style.setProperty("--rows", "12");
		});
		await page.waitForFunction("Reflect.get(globalThis, 'boundClock').getSettings().matrixRows === '--rows' && Reflect.get(globalThis, 'boundClock').matrixPhysicalSize().rows === 12", );
		assert.equal(await page.locator("#bound-clock .sst-group").first().evaluate(( /** @type {Element} */ element) => getComputedStyle(element).getPropertyValue("--sst-off-time").trim(), ), "0.5s", );
		await page.evaluate(() => Reflect.get(globalThis, "boundClock").destroy());
	});
});
test("demo sidebar controls drive clock settings", async t => {
	await browserTest(t, async (page, url) => {
		/** @type {string[]} */
		const errors = [];
		page.on("pageerror", ( /** @type {Error} */ error) => errors.push(error.message), );
		await page.goto(`${url}/exactus/packages/widgets/widget_clock/examples/web/index.html`);
		// Numeric slider propagates to its readout and the clock.
		await page.locator("#fps").fill("60");
		assert.equal(await page.locator("#fps-out").textContent(), "60");
		// Boolean, text, colour and select controls apply through the set path.
		await page.locator("#live").uncheck();
		assert.equal(await page.locator("#live").isChecked(), false);
		await page.locator("#rec-label").fill("ALT");
		await page.locator("#background").fill("#112233");
		await page.locator("#matrix-layout").selectOption("target");
		await page.locator("#rec-visible").selectOption("hidden");
		await page.locator("#align").selectOption("flex-start");
		// Template import rebuilds the structure editor and group values.
		await page.locator("#template").fill("dd:dd");
		await page.locator("#import-template").click();
		const imported = await page.locator(".structure-row").count();
		assert.ok(imported >= 2);
		// add-group appends a marker row and a group row.
		await page.locator("#add-group").click();
		assert.equal(await page.locator(".structure-row").count(), imported + 2);
		// resume-live re-checks the live toggle; blink-now runs without error.
		await page.locator("#resume-live").click();
		assert.equal(await page.locator("#live").isChecked(), true);
		await page.locator("#blink-now").click();
		// reset-settings reloads the page into a fresh clock.
		await page.locator("#reset-settings").click();
		await page.waitForSelector("#analog-clock-mount .sst-root");
		assert.deepEqual(errors, []);
	});
});
