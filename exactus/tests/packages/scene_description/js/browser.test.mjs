/** @file In-browser test suite for the scene evidence runtime. */
"use strict";
/**
 * In-page tests exercised by exactus/tests/test_js_runtime.py through Playwright.
 * Results are published on globalThis.__sceneTestResults.
 */
/**
 * @typedef {{name: string, error?: string}} TestFailure
 */
/**
 * @typedef {{
 *   passed: string[],
 *   failed: TestFailure[]
 * }} TestResults
 */
/**
 * @typedef {{
 *   pixelRatio?: number,
 *   backgroundColor?: string
 * }} HtmlToImageOptions
 */
/**
 * @typedef {{
 *   toCanvas: (
 *     element: HTMLElement,
 *     options?: HtmlToImageOptions
 *   ) => Promise<HTMLCanvasElement>
 * }} HtmlToImage
 */
/**
 * @typedef {{
 *   event: string,
 *   [key: string]: unknown
 * }} SinkPayload
 */
/**
 * @typedef {{
 *   type: string,
 *   [key: string]: unknown
 * }} RuntimeEvent
 */
/**
 * @typedef {{
 *   type: string
 * }} CaptureEvent
 */
/**
 * @typedef {new (...args: any[]) => Error} ErrorType
 */
/**
 * @template {Element} T
 * @typedef {new (...args: any[]) => T} ElementConstructor
 */
/**
 * @typedef {{
 *   manifest: Record<string, unknown>,
 *   files: Map<string, Blob>
 * }} TestSceneBundle
 */
/**
 * @typedef {{
 *   id: string,
 *   kind: string,
 *   size: number,
 *   segments?: unknown[],
 *   reason?: string,
 *   width?: number,
 *   transferId?: string,
 *   manifest?: Record<string, unknown>
 * }} CaptureResult
 */
/**
 * @typedef {{
 *   armed: boolean,
 *   configuredDuration?: number
 * }} CaptureStatus
 */
/**
 * @typedef {{
 *   fps: number,
 *   videoBitsPerSecond?: number
 * }} CaptureQuality
 */
/**
 * @typedef {{
 *   fps?: number,
 *   videoBitsPerSecond?: number
 * }} ConfigQuality
 */
/**
 * @typedef {{
 *   target?: unknown,
 *   quality?: string | ConfigQuality,
 *   eventPrefix?: string
 * }} CaptureConfig
 */
/**
 * @typedef {{
 *   on: (
 *     name: string,
 *     callback: (event: CaptureEvent) => void
 *   ) => () => void,
 *   arm: () => Promise<CaptureStatus>,
 *   disarm: (
 *     options?: Record<string, unknown>
 *   ) => Promise<CaptureStatus>,
 *   record: (
 *     options: Record<string, unknown>
 *   ) => Promise<CaptureResult>,
 *   start: (
 *     options?: Record<string, unknown>
 *   ) => Promise<CaptureResult>,
 *   stop: (
 *     id: string
 *   ) => Promise<CaptureResult | null>,
 *   done: (
 *     id: string
 *   ) => Promise<CaptureResult>,
 *   snapshot: (
 *     options?: Record<string, unknown>
 *   ) => Promise<CaptureResult>,
 *   transfer: (
 *     id: string,
 *     options?: Record<string, unknown>
 *   ) => Promise<CaptureResult>,
 *   set: (
 *     options: Record<string, unknown>
 *   ) => Promise<unknown>,
 *   setTarget: (
 *     target: unknown
 *   ) => Promise<unknown>,
 *   clear: () => RollingCaptureInstance,
 *   remove: (id: string) => unknown,
 *   config: () => CaptureConfig,
 *   readonly armed: boolean,
 *   readonly buffer: CaptureStatus,
 *   readonly quality: CaptureQuality
 * }} RollingCaptureInstance
 */
/**
 * @typedef {{
 *   config: () => CaptureConfig,
 *   status: () => {
 *     armed: boolean,
 *     modes: string[],
 *     memory: unknown
 *   },
 *   mark: (
 *     type: string,
 *     data?: Record<string, unknown>
 *   ) => unknown,
 *   markers: (
 *     options?: Record<string, unknown>
 *   ) => RuntimeEvent[],
 *   evidence: (
 *     options?: Record<string, unknown>
 *   ) => Promise<{
 *     video?: CaptureResult,
 *     capture?: CaptureResult,
 *     description?: CaptureResult,
 *     markers?: RuntimeEvent[]
 *   }>,
 *   describe: (
 *     options?: Record<string, unknown>
 *   ) => Promise<CaptureResult>,
 *   transfer: (
 *     id: string,
 *     options?: Record<string, unknown>
 *   ) => Promise<CaptureResult>,
 *   startDiagnostics: (
 *     options?: Record<string, unknown>
 *   ) => unknown,
 *   stopDiagnostics: () => unknown,
 *   diagnostics: () => unknown[],
 *   remove: (id: string) => boolean,
 *   clear: () => unknown,
 *   destroy: () => Promise<void>,
 *   addEventListener: (
 *     type: string,
 *     callback: (event: CustomEvent) => void
 *   ) => void
 * }} EvidenceRuntimeInstance
 */
/**
 * @typedef {{
 *   elements: Record<string, unknown>,
 *   metadata: {
 *     requestId?: string | number
 *   }
 * }} TestScene
 */
/**
 * @typedef {{
 *   Descriptor: {
 *     describe: (
 *       root: Element,
 *       options?: unknown
 *     ) => Promise<TestScene>,
 *     captureElementDataUrl: (
 *       element: Element,
 *       options?: unknown
 *     ) => Promise<string>,
 *     copyElementScreenshot: (
 *       element: Element,
 *       options?: unknown
 *     ) => Promise<{blob: Blob}>
 *   },
 *   SceneBinaryBundle: {
 *     create: (
 *       scene: TestScene
 *     ) => Promise<TestSceneBundle>,
 *     zip: (
 *       manifest: object,
 *       files: Map<string, Blob>
 *     ) => Promise<Blob | ArrayBuffer>,
 *     tar: (
 *       manifest: object,
 *       files: Map<string, Blob>
 *     ) => Promise<Blob | ArrayBuffer>,
 *     messagePack: (
 *       manifest: object,
 *       files: Map<string, Blob>
 *     ) => Promise<Blob | ArrayBuffer>,
 *     gzip: (
 *       manifest: object,
 *       files: Map<string, Blob>
 *     ) => Promise<Blob>,
 *     zstd: (
 *       manifest: object,
 *       files: Map<string, Blob>
 *     ) => Promise<Blob>,
 *     brotli: (
 *       manifest: object,
 *       files: Map<string, Blob>
 *     ) => Promise<Blob>,
 *     label: (format: string) => string,
 *     compressionSupported: (format: string) => boolean,
 *     download: (
 *       manifest: object,
 *       files: Map<string, Blob>,
 *       format: string
 *     ) => Promise<unknown>
 *   },
 *   RollingCapture: new (
 *     options?: Record<string, unknown>
 *   ) => RollingCaptureInstance,
 *   EvidenceRuntime: new (
 *     options?: Record<string, unknown>
 *   ) => EvidenceRuntimeInstance
 * }} RuntimeGlobals
 */
(async () => {
	/** @type {TestResults} */
	const results = {
		passed: [],
		failed: [],
	};
	/** @type {RuntimeGlobals} */
	const runtimeGlobals = /** @type {RuntimeGlobals} */ (
		/** @type {unknown} */
		(globalThis));
	/**
	 * Record a test result.
	 *
	 * @param {string} name Test name.
	 * @param {unknown} [error] Failure.
	 * @returns {void}
	 */
	const report = (name, error) => {
		if (error === undefined) {
			results.passed.push(name);
			return;
		}
		results.failed.push({
			name,
			error: error instanceof Error ? error.message : String(error),
		});
	};
	/**
	 * Execute one test.
	 *
	 * @param {string} name Test name.
	 * @param {() => void | Promise<void>} body Test body.
	 * @returns {Promise<void>}
	 */
	const test = async (name, body) => {
		try {
			await body();
			report(name);
		} catch (error) {
			report(name, error);
		}
	};
	/**
	 * Assert strict equality.
	 *
	 * @param {unknown} actual Actual value.
	 * @param {unknown} expected Expected value.
	 * @param {string} [label] Assertion label.
	 * @returns {void}
	 * @throws {Error} When the operation cannot complete.
	 */
	const eq = (actual, expected, label = "") => {
		if (actual !== expected) throw new Error(`${label} expected ${JSON.stringify(expected)}, got ${JSON.stringify(
          actual,
        )}`, );
	};
	/**
	 * Assert truthiness.
	 *
	 * @param {unknown} value Value.
	 * @param {string} [label] Assertion label.
	 * @returns {void}
	 * @throws {Error} When the operation cannot complete.
	 */
	const ok = (value, label = "") => {
		if (!value) throw new Error(`expected truthy ${label}`);
	};
	/**
	 * Assert an exception.
	 *
	 * @param {() => unknown | Promise<unknown>} call Operation.
	 * @param {ErrorType | null} [kind] Expected error type.
	 * @param {string} [label] Assertion label.
	 * @returns {Promise<unknown>}
	 * @throws {Error} When the operation cannot complete.
	 */
	const throws = async (call, kind = null, label = "") => {
		try {
			await call();
		} catch (error) {
			if (kind !== null && !(error instanceof kind)) throw new Error(`${label} expected ${kind.name}, got ${
            error instanceof Error ? error.constructor.name : typeof error
          }`, );
			return error;
		}
		throw new Error(`${label} expected an exception`);
	};
	/**
	 * Delay execution.
	 *
	 * @param {number} ms Milliseconds.
	 * @returns {Promise<void>}
	 */
	const sleep = ms => new Promise(resolve => {
		setTimeout(resolve, ms);
	});
	/**
	 * Resolve an element by ID and runtime type.
	 *
	 * @template {Element} T
	 * @param {string} id Element ID.
	 * @param {ElementConstructor<T>} type Constructor.
	 * @returns {T}
	 * @throws {TypeError} When the operation cannot complete.
	 */
	const elementById = (id, type) => {
		const element = document.getElementById(id);
		if (!(element instanceof type)) throw new TypeError(`Expected #${id} to be ${type.name}.`);
		return /** @type {T} */ (element);
	};
	/**
	 * Resolve a descendant and validate its runtime type.
	 *
	 * @template {Element} T
	 * @param {ParentNode} parent Parent.
	 * @param {string} selector Selector.
	 * @param {ElementConstructor<T>} type Constructor.
	 * @returns {T}
	 * @throws {TypeError} When the operation cannot complete.
	 */
	const queryElement = (parent, selector, type) => {
		const element = parent.querySelector(selector);
		if (!(element instanceof type)) throw new TypeError(`Expected ${selector} to be ${type.name}.`);
		return /** @type {T} */ (element);
	};
	/**
	 * Install a mutable global value without assigning through an awaited
	 * lexical alias.
	 *
	 * @param {string} name Property name.
	 * @param {unknown} value Property value.
	 * @returns {void}
	 */
	const setGlobal = (name, value) => {
		Object.defineProperty(globalThis, name, {
			configurable: true,
			writable: true,
			value,
		});
	};
	/**
	 * Remove a mutable global value.
	 *
	 * @param {string} name Property name.
	 * @returns {void}
	 */
	const removeGlobal = name => {
		Reflect.deleteProperty(globalThis, name);
	};
	const {
		Descriptor,
		SceneBinaryBundle,
		RollingCapture,
		EvidenceRuntime
	} = runtimeGlobals;
	ok(Descriptor, "Descriptor exposed");
	ok(SceneBinaryBundle, "SceneBinaryBundle exposed");
	ok(RollingCapture, "RollingCapture exposed");
	ok(EvidenceRuntime, "EvidenceRuntime exposed");
	// ── DOM fixture ─────────────────────────────────────────────────
	const fixtureStyle = document.createElement("style");
	fixtureStyle.textContent = ["body { margin: 0; font-family: sans-serif; }", ".box { position: relative; width: 900px; padding: 8px; }", ".card { position: relative; width: 240px; height: 80px; margin: 8px;", "  background: #def; border: 2px solid #369; border-radius: 6px; }", ".card::before { content: 'before'; color: #933; }", ".card::after { content: ''; display: block; width: 12px; height: 12px;", "  background: #393; }", ".moved { transform: translate(10px, 4px) rotate(2deg) scale(1.05); }", ".dim { opacity: 0.4; }", ".clipped { overflow: hidden; height: 20px; }", ".offscreen { position: absolute; left: -9999px; top: 0; }", ".scroller { width: 200px; height: 100px; overflow: auto; }", ".scroller > div { height: 600px; background: linear-gradient(#fff,#000); }", "mark { background: #fd3; }", "@media (min-width: 1px) { .card { outline: 1px solid #369; } }", ].join("\n");
	document.head.appendChild(fixtureStyle);
	const root = document.createElement("div");
	root.className = "box";
	root.id = "scene-root";
	root.innerHTML = `
    <h1 id="title">Fixture title</h1>
    <p>Body text with <mark>marked</mark> and <em>em</em> and
      <a href="https://example.com" target="_blank" rel="noopener">link</a>
      <a href="mailto:a@b.c">mail</a> <a href="tel:+123">tel</a>
      <a href="#title" download>anchor</a>.</p>
    <form id="form" aria-label="demo form">
      <fieldset><legend>Fields</legend>
        <label for="t1">Text</label>
        <input id="t1" type="text" value="hello" required placeholder="type">
        <input type="email" value="e@x.y" disabled>
        <input type="password" value="pw">
        <input type="search" value="find">
        <input type="tel" value="123">
        <input type="url" value="https://x.y">
        <input type="number" min="0" max="10" step="2" value="4">
        <input type="range" min="0" max="100" value="40" aria-label="range">
        <label><input type="checkbox" checked> Check</label>
        <label><input type="checkbox"> Unchecked</label>
        <input type="radio" name="r" checked aria-label="r1">
        <input type="radio" name="r" aria-label="r2">
        <input type="file" aria-label="file">
        <input type="color" value="#ff0000" aria-label="color">
        <input type="date" value="2026-01-02" aria-label="date">
        <input type="time" value="10:20" aria-label="time">
        <input type="datetime-local" value="2026-01-02T10:20" aria-label="dt">
        <input type="month" value="2026-01" aria-label="month">
        <input type="week" value="2026-W03" aria-label="week">
        <input type="hidden" value="h">
        <input type="button" value="IBtn">
        <input type="submit" value="Go">
        <input type="reset" value="Reset">
        <input type="image" src="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg'/>" alt="imgbtn">
        <select aria-label="sel"><option>one</option><option selected>two</option>
          <optgroup label="g"><option>three</option></optgroup></select>
        <select multiple size="2" aria-label="multi"><option selected>a</option><option>b</option></select>
        <textarea aria-label="ta" rows="2">some text</textarea>
        <progress value="30" max="100">30%</progress>
        <meter value="0.6" min="0" max="1">0.6</meter>
        <button type="button" aria-pressed="true">Btn</button>
        <button disabled>Disabled</button>
      </fieldset>
    </form>
    <details open><summary>Details</summary><p>expanded</p></details>
    <ul><li>i1</li><li role="listitem" aria-selected="true">i2</li></ul>
    <ol start="3"><li>o1</li></ol>
    <dl><dt>term</dt><dd>def</dd></dl>
    <table><caption>cap</caption><thead><tr><th>h</th></tr></thead>
      <tbody><tr><td colspan="2">cell</td></tr></tbody></table>
    <figure><figcaption>fig</figcaption>
      <img id="png" alt="pixel" src="">
      <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16'%3E%3Crect width='16' height='16' fill='%23f00'/%3E%3C/svg%3E" alt="svg">
    </figure>
    <canvas id="cv" width="64" height="48" aria-label="canvas"></canvas>
    <svg id="icon1" width="16" height="16" viewBox="0 0 16 16"><circle cx="8" cy="8" r="7" fill="#00f"/></svg>
    <svg id="icon2" width="16" height="16" viewBox="0 0 16 16"><circle cx="8" cy="8" r="7" fill="#00f"/></svg>
    <svg id="icon3" width="16" height="16" viewBox="0 0 16 16"><rect width="16" height="16" fill="#0f0"/></svg>
    <svg id="big" width="120" height="40"><text x="4" y="20">svgtext</text></svg>
    <video id="vid" width="80" height="45" controls muted></video>
    <audio id="aud" controls></audio>
    <div class="card moved" aria-live="polite">card</div>
    <div class="card dim">dim</div>
    <div class="card clipped">clipped text that overflows the box</div>
    <div class="offscreen">offscreen</div>
    <div class="scroller" tabindex="0"><div>scroll me</div></div>
    <div class="card" role="button" tabindex="0" aria-expanded="false"
      aria-controls="form" aria-describedby="title" aria-hidden="false">aria</div>
    <p aria-hidden="true">hidden para</p>
    <div class="card" contenteditable="true">editable</div>
    <code>code</code> <pre>pre</pre> <blockquote>quote</blockquote>
    <abbr title="abbreviation">abbr</abbr> <time datetime="2026-01-02">date</time>
    <hr> <br> <span draggable="true">drag</span>
    <a href="javascript:void(0)">js link</a> <a>no href</a>
    <div class="card" style="border-style: dashed; border-width: 1px 3px 5px 2px;
      border-radius: 14px;">fancy border</div>
    <div class="card" style="border: none; border-top: 3px solid #c33;">
      top line</div>
    <div class="card" style="border: none; border-left: 4px double #33c;
      border-bottom: 2px dotted #3c3;">two lines</div>
    <div class="card" style="border: none; border-right: 6px inset #c63;">
      right line</div>
    <div class="card" style="border-style: double dotted groove ridge;
      border-color: #f0a #0af #af0 #fa0;">edge styles</div>
    <div class="card" style="box-shadow: 4px 4px 8px #0008;
      outline: 3px solid #f80; outline-offset: 2px;">shadow</div>
    <div style="position: relative; z-index: 5; width: 200px; height: 70px;
      background: #fcc;">
      <div style="position: absolute; z-index: 9; inset: 4px;
        background: #cfc;">nested z</div>
      <div style="position: absolute; z-index: 3; top: 20px; left: 20px;
        width: 60px; height: 30px; background: #ccf;">overlap</div>
    </div>
    <div role="tablist" aria-label="tabs">
      <div role="tab" aria-selected="true" tabindex="0">tab1</div>
      <div role="tab" aria-selected="false">tab2</div>
    </div>
    <div role="listbox" aria-label="listbox">
      <div role="option" aria-selected="true">opt</div>
      <div role="option" aria-selected="false">opt2</div>
    </div>
    <div role="slider" aria-label="slider" aria-valuenow="40"
      aria-valuemin="0" aria-valuemax="100" tabindex="0"></div>
    <div role="progressbar" aria-label="pb" aria-valuenow="30"
      aria-valuemax="100"></div>
    <div role="switch" aria-checked="true" tabindex="0">sw</div>
    <div role="menu"><div role="menuitem">mi</div></div>
    <div role="tree"><div role="treeitem" aria-expanded="true">ti</div></div>
    <div role="alertdialog"><div role="alert">al</div></div>
    <div role="dialog" aria-modal="true">dlg</div>
    <img id="photo" alt="photo" style="object-fit: cover;
      object-position: 25% 75%; width: 100px; height: 60px;">
    <img id="photo2" alt="p2" style="object-fit: contain; width: 60px;
      height: 60px; border: 1px solid #000;">
    <div class="card" style="clip-path: inset(4px);">clip path</div>
    <div class="card" style="mask-image: linear-gradient(#000, transparent);">
      mask</div>
    <div class="card" style="mix-blend-mode: multiply; background: #fdd;">
      blend</div>
    <div class="card" style="filter: blur(0.4px);">filtered</div>
    <div class="card" style="backdrop-filter: blur(1px);">backdrop</div>
    <iframe title="frame" width="120" height="40"
      srcdoc="<p style='margin:0;background:#efe'>frame</p>"></iframe>
    <input type="search" list="dl" aria-label="listed">
    <datalist id="dl"><option>d1</option><option>d2</option></datalist>
    <ruby>rb<rt>rt</rt></ruby> <wbr>
    <kbd>key</kbd> <samp>samp</samp> <var>x</var> <ins>ins</ins> <del>del</del>
    <sup>sup</sup> <sub>sub</sub> <small>sm</small> <strong>st</strong>
    <div id="preview-card" class="card">
      <h3>Preview</h3>
      <p>card body text</p>
      <img id="card-img" alt="card" width="40" height="30">
      <button type="button">Action</button>
      <span class="dim">footnote</span>
    </div>`;
	document.body.appendChild(root);
	const cv = elementById("cv", HTMLCanvasElement);
	const ctx2d = cv.getContext("2d");
	if (ctx2d === null) throw new Error("2D canvas context is unavailable.");
	const gradient = ctx2d.createLinearGradient(0, 0, 64, 48);
	gradient.addColorStop(0, "#f00");
	gradient.addColorStop(1, "#00f");
	ctx2d.fillStyle = gradient;
	ctx2d.fillRect(0, 0, 64, 48);
	ctx2d.fillStyle = "#fff";
	ctx2d.fillText("cv", 8, 24);
	const pngUrl = cv.toDataURL("image/png");
	const pngImage = elementById("png", HTMLImageElement);
	const photo = elementById("photo", HTMLImageElement);
	const photo2 = elementById("photo2", HTMLImageElement);
	const cardImg = elementById("card-img", HTMLImageElement);
	pngImage.src = pngUrl;
	photo.src = pngUrl;
	photo2.src = cv.toDataURL("image/webp", 0.9);
	cardImg.src = pngUrl;
	await Promise.all(
		[pngImage, photo, photo2, cardImg].map(image => image.decode().catch(() => undefined), ), );
	const videoCanvas = document.createElement("canvas");
	videoCanvas.width = 96;
	videoCanvas.height = 54;
	const videoContext = videoCanvas.getContext("2d");
	if (videoContext === null) throw new Error("Video canvas 2D context is unavailable.");
	videoContext.fillRect(0, 0, 96, 54);
	document.body.appendChild(videoCanvas);
	/**
	 * Handle draw for scene-evidence processing.
	 */
	const draw = () => {
		videoContext.fillStyle = `hsl(${Date.now() % 360}, 60%, 50%)`;
		videoContext.fillRect(0, 0, 96, 54);
	};
	const vid = elementById("vid", HTMLVideoElement);
	vid.srcObject = videoCanvas.captureStream();
	vid.play().catch(() => undefined);
	const scroller = queryElement(root, ".scroller", HTMLDivElement);
	scroller.scrollTop = 40;
	await sleep(150);
	/** @type {HtmlToImage} */
	const htmlToImage = {
		toCanvas: async (element, options = {}) => {
			const rect = element.getBoundingClientRect();
			const ratio = options.pixelRatio ?? 1;
			const canvas = document.createElement("canvas");
			canvas.width = Math.max(1, Math.ceil(rect.width * ratio));
			canvas.height = Math.max(1, Math.ceil(rect.height * ratio));
			const context = canvas.getContext("2d");
			if (context === null) throw new Error("2D canvas context is unavailable.");
			const computedStyle = getComputedStyle(element);
			context.fillStyle = options.backgroundColor ?? computedStyle.backgroundColor ?? "#888";
			context.fillRect(0, 0, canvas.width, canvas.height);
			context.fillStyle = computedStyle.borderTopColor || "#333";
			context.fillRect(0, 0, canvas.width, Math.max(1, canvas.height / 6));
			context.fillStyle = computedStyle.color || "#000";
			context.font = computedStyle.font || "10px sans-serif";
			context.fillText(
				(element.textContent || element.tagName).trim().slice(0, 60), 2, canvas.height - 2, );
			return canvas;
		},
	};
	setGlobal("htmlToImage", htmlToImage);
	// ── Descriptor.describe ─────────────────────────────────────────
	/** @type {TestScene | null} */
	let scene = null;
	await test("describe returns a scene record", async () => {
		scene = await Descriptor.describe(root);
		ok(scene && typeof scene === "object", "scene object");
		ok(scene.elements && typeof scene.elements === "object", "elements map");
		ok(Object.keys(scene.elements).length > 10, "many elements");
		ok(scene.metadata, "metadata present");
	});
	await test("describe validates root and options", async () => {
		await throws(
			() => Descriptor.describe(
				/** @type {Element} */
				(
					/** @type {unknown} */
					("p")), ), TypeError, "string root", );
		await throws(
			() => Descriptor.describe(
				/** @type {Element} */
				(
					/** @type {unknown} */
					(null)), ), TypeError, "null root", );
		await throws(
			() => Descriptor.describe(root, {
				onComplete: 42,
			}), TypeError, "numeric callback", );
		await throws(
			() => Descriptor.describe(root, {
				requestId: {},
			}), TypeError, "object requestId", );
		const hidden = document.createElement("div");
		await throws(() => Descriptor.describe(hidden), null, "unattached root");
	});
	await test("describe accepts function and scalar shorthand options", async () => {
		let called = 0;
		const first = await Descriptor.describe(root, () => {
			called += 1;
		});
		ok(first, "callback options");
		eq(called, 1, "callback invoked");
		const second = await Descriptor.describe(root, "req-7");
		eq(second.metadata.requestId, "req-7", "requestId string");
		const third = await Descriptor.describe(root, {
			onComplete: () => {
				called += 1;
			},
			requestId: 9,
		});
		eq(third.metadata.requestId, 9, "requestId number");
		eq(called, 2, "onComplete invoked");
	});
	/** @type {Record<string, unknown>[]} */
	const optionSets = [{
		includeComputedStyle: true,
	}, {
		includeElementScreenshots: true,
		elementScreenshotMime: "image/webp",
		elementScreenshotQuality: 0.8,
		elementScreenshotMaxDimension: 200,
		elementScreenshotConcurrency: 2,
		elementScreenshotSkipAutoScale: true,
		elementScreenshotBackground: "#fff",
	}, {
		includeBinary: true,
		includeIconMarkup: true,
		includeIconBinary: true,
		compactSvgIcons: true,
		iconMaxWidthFraction: 0.9,
		iconMaxHeightFraction: 0.9,
		iconMaxAreaFraction: 0.9,
		iconGridColumns: 2,
		iconGridRows: 2,
	}, {
		compactSvgIcons: false,
	}, {
		includeRelationships: false,
		inferSpatialLayouts: false,
	}, {
		inferSpatialLayouts: true,
		spatialMaxTracks: 3,
		spatialTolerance: 0.2,
	}, {
		includeOffscreenScrollable: false,
	}, {
		opacityThreshold: 0.9,
	}, {
		gridColumns: 2,
		gridRows: 2,
		mediaRegionSimilarityContrast: 0.5,
		mediaRegionColorDistance: 0.5,
	}, {
		includeBinary: false,
	}, {
		maxRasterDimension: 64,
	}, {
		includeElementScreenshots: true,
		elementScreenshotSkipAutoScale: false,
		elementScreenshotMaxDimension: 3000,
		elementScreenshotMime: "image/png",
	}, {
		inferSpatialLayouts: true,
		spatialMaxTracks: 16,
	}, ];
	await Promise.all(optionSets.map((options, index) => test(`describe option set ${index}`, async () => {
		const output = await Descriptor.describe(root, options);
		ok(output && typeof output === "object", "scene produced");
	}), ), );
	await test("describe on nested subtree", async () => {
		const form = elementById("form", HTMLFormElement);
		const output = await Descriptor.describe(form, {
			includeRelationships: true,
		});
		ok(Object.keys(output.elements).length > 5, "form elements");
	});
	// ── SceneBinaryBundle ───────────────────────────────────────────
	/** @type {TestSceneBundle | null} */
	let bundle = null;
	await test("SceneBinaryBundle.create externalizes binary assets", async () => {
		const rich = await Descriptor.describe(root, {
			includeBinary: true,
			includeIconBinary: true,
		});
		bundle = await SceneBinaryBundle.create(rich);
		ok(bundle.manifest && typeof bundle.manifest === "object", "manifest");
		ok(bundle.files instanceof Map, "files map");
	});
	await test("SceneBinaryBundle codecs produce output", async () => {
		const manifest = {
			hello: "world",
			items: [1, 2, 3],
			negative: -42,
			big: 2 ** 40,
			float: 1.5,
			flag: true,
			none: null,
			nested: {
				deep: {
					deeper: [true, false, null, "x", -1, 3.14],
				},
			},
			unicode: "héllo→世界",
		};
		const files = new Map([
			["a.txt",
				new Blob(["hi"], {
					type: "text/plain",
				}),
			],
		]);
		const zipOutput = await SceneBinaryBundle.zip(manifest, files);
		ok(
			(zipOutput instanceof Blob ? zipOutput.size : zipOutput.byteLength) > 0, "zip output", );
		const tarOutput = await SceneBinaryBundle.tar(manifest, files);
		ok(
			(tarOutput instanceof Blob ? tarOutput.size : tarOutput.byteLength) > 0, "tar output", );
		const messagePackOutput = await SceneBinaryBundle.messagePack(manifest, files, );
		ok(
			(messagePackOutput instanceof Blob ? messagePackOutput.size : messagePackOutput.byteLength) > 0, "messagePack output", );
		const gzipOutput = await SceneBinaryBundle.gzip(manifest, files);
		ok(gzipOutput.size > 0, "gzip output");
		const zstdOutput = await SceneBinaryBundle.zstd(manifest, files);
		ok(zstdOutput.size > 0, "zstd output");
		if (SceneBinaryBundle.compressionSupported("brotli")) {
			const brotliOutput = await SceneBinaryBundle.brotli(manifest, files);
			ok(brotliOutput.size > 0, "brotli output");
		} else await throws(
			() => SceneBinaryBundle.brotli(manifest, files), Error, "brotli unsupported", );
	});
	await test("SceneBinaryBundle helpers", async () => {
		eq(SceneBinaryBundle.label("zip"), "JSON + ZIP");
		eq(SceneBinaryBundle.label("gzip"), "JSON + TAR.GZ");
		eq(SceneBinaryBundle.label("msgpack"), "MessagePack");
		eq(SceneBinaryBundle.label("unknown-format"), "unknown-format");
		eq(typeof SceneBinaryBundle.compressionSupported("gzip"), "boolean");
		let clicked = 0;
		const originalDescriptor = Object.getOwnPropertyDescriptor(HTMLAnchorElement.prototype, "click", );
		Object.defineProperty(HTMLAnchorElement.prototype, "click", {
			configurable: true,
			value: () => {
				clicked += 1;
			},
		});
		try {
			await SceneBinaryBundle.download({
				a: 1,
			}, new Map(), "zip", );
		} finally {
			if (originalDescriptor === undefined) Reflect.deleteProperty(HTMLAnchorElement.prototype, "click");
			else Object.defineProperty(HTMLAnchorElement.prototype, "click", originalDescriptor, );
		}
		eq(clicked, 1, "download click");
	});
	// ── Descriptor element capture APIs ─────────────────────────────
	await test("captureElementDataUrl returns an encoded frame", async () => {
		const card = queryElement(root, ".card", HTMLDivElement);
		const url = await Descriptor.captureElementDataUrl(card, {
			mime: "image/png",
		});
		ok(url.startsWith("data:image/"), "data url prefix");
	});
	await test("copyElementScreenshot captures or reports clipboard", async () => {
		const card = queryElement(root, ".card", HTMLDivElement);
		try {
			const result = await Descriptor.copyElementScreenshot(card, {
				mime: "image/png",
			});
			ok(result.blob.size > 0, "clipboard blob");
		} catch (error) {
			ok(/clipboard|not supported|denied|permission/i.test(String(error)), `unexpected copy error ${String(error)}`, );
		}
	});
	// ── RollingCapture ──────────────────────────────────────────────
	await test("RollingCapture validates configuration", async () => {
		await throws(
			() => new RollingCapture({
				quality: "bogus",
			}), Error, "quality", );
		await throws(
			() => new RollingCapture({
				window: 0,
			}), RangeError, "window", );
		await throws(
			() => new RollingCapture({
				segmentDuration: -1,
			}), RangeError, );
		await throws(
			() => new RollingCapture({
				maxCaptures: 0,
			}), RangeError, );
		await throws(
			() => new RollingCapture({
				target: "#missing-target",
			}), Error, "missing target", );
		await throws(
			() => new RollingCapture({
				target: document.createElement("div"),
			}), TypeError, "non-streamable target", );
	});
	const rolling = new RollingCapture({
		target: videoCanvas,
		quality: "low",
		window: 2000,
		segmentDuration: 60,
		eventPrefix: "testcap",
	});
	await test("RollingCapture lifecycle", async () => {
		ok(rolling.config().target === null, "config snapshot");
		eq(rolling.armed, false, "starts disarmed");
		/** @type {string[]} */
		const armedEvents = [];
		const off = rolling.on("armed", event => {
			armedEvents.push(event.type);
		});
		draw();
		const status = await rolling.arm();
		eq(rolling.armed, true, "armed");
		ok(armedEvents.includes("armed"), "armed event");
		off();
		ok(status.armed, "status armed");
		eq((await rolling.arm()).armed, true, "re-arm is idempotent");
		const warmup = setInterval(draw, 15);
		await sleep(350);
		clearInterval(warmup);
		const buffered = rolling.buffer;
		ok(buffered.armed && buffered.configuredDuration === 2000, "buffer report");
		ok(rolling.quality.fps === 15, "low quality preset");
		await throws(
			() => rolling.set({
				quality: "high",
			}), Error, "set while armed", );
		await throws(
			() => rolling.setTarget(videoCanvas), Error, "target while armed", );
	});
	await test("RollingCapture record/stop/results", async () => {
		const pump = setInterval(draw, 15);
		const video = await rolling.record({
			duration: 600,
			metadata: {
				t: 1,
			},
		});
		clearInterval(pump);
		ok(video.id, "video id");
		eq(video.kind, "video", "kind");
		ok(video.size >= 0, "size");
		ok(Array.isArray(video.segments), "segments");
		const again = await rolling.stop(video.id);
		ok(again === null || again.id === video.id, "stop returns cached result");
		await throws(() => rolling.record({}), Error, "record needs duration");
		await throws(() => rolling.done("nope"), Error, "unknown capture");
		ok(await rolling.stop("nope") === null, "stop unknown is null");
		await throws(
			() => rolling.start({
				before: -1,
			}), RangeError, "negative before", );
		await throws(
			() => rolling.start({
				before: 99999,
			}), RangeError, "before exceeds window", );
		const started = await rolling.start({
			id: "manual",
			duration: 0,
		});
		eq(started.id, "manual", "manual id");
		await throws(
			() => rolling.start({
				id: "manual",
			}), Error, "duplicate id", );
		const secondPump = setInterval(draw, 15);
		await sleep(200);
		const stopped = await rolling.stop("manual");
		clearInterval(secondPump);
		ok(stopped, "manual result");
		if (!stopped) throw new Error("manual stop returned null");
		eq(stopped.reason, "manual", "stop reason");
	});
	await test("RollingCapture snapshot and images", async () => {
		const image = await rolling.snapshot({
			target: videoCanvas,
			scale: 0.5,
		});
		eq(image.kind, "capture", "image kind");
		ok(image.size > 0, "image bytes");
		await throws(
			() => rolling.snapshot({
				target: videoCanvas,
				scale: 0,
			}), RangeError, "scale", );
		await throws(
			() => rolling.snapshot({
				target: "#nope",
			}), Error, "missing", );
	});
	await test("RollingCapture snapshot of plain elements", async () => {
		const card = queryElement(root, ".card", HTMLDivElement);
		const pngCapture = await rolling.snapshot({
			target: card,
			background: "#fff",
			scale: 1,
		});
		ok(pngCapture.size > 0, "dom snapshot bytes");
		const webp = await rolling.snapshot({
			target: card,
			type: "image/webp",
			quality: 0.7,
			metadata: {
				tag: "card",
			},
		});
		eq(webp.kind, "capture", "webp capture");
		const scaled = await rolling.snapshot({
			target: root,
			scale: 0.5,
		});
		ok(typeof scaled.width === "number" && scaled.width > 0, "scaled snapshot");
		const bigSvg = elementById("big", SVGSVGElement);
		const svgShot = await rolling.snapshot({
			target: bigSvg,
		});
		ok(svgShot.size > 0, "svg snapshot");
		const imgShot = await rolling.snapshot({
			target: photo,
		});
		ok(imgShot.size > 0, "img snapshot");
	});
	await test("RollingCapture snapshot without htmlToImage", async () => {
		removeGlobal("htmlToImage");
		try {
			const card = queryElement(root, ".card", HTMLDivElement);
			const output = await rolling.snapshot({
				target: card,
				scale: 0.5,
			});
			ok(output.size > 0, "fallback snapshot bytes");
			const title = document.getElementById("title");
			if (!(title instanceof HTMLElement)) throw new TypeError("Expected #title to be an HTMLElement.");
			const text = await rolling.snapshot({
				target: title,
			});
			ok(text.size > 0, "text snapshot bytes");
		} finally {
			setGlobal("htmlToImage", htmlToImage);
		}
	});
	await test("RollingCapture transfer uses the sink", async () => {
		/** @type {SinkPayload[]} */
		const transferEvents = [];
		setGlobal("__evidenceSink",
			/**
			 * Receive one evidence transfer payload.
			 *
			 * @param {SinkPayload} payload Transfer payload.
			 * @returns {Promise<void>}
			 */
			async payload => {
				transferEvents.push(payload);
			}, );
		const pump = setInterval(draw, 15);
		const video = await rolling.record({
			duration: 500,
		});
		clearInterval(pump);
		const output = await rolling.transfer(video.id, {
			chunkSize: 1024,
		});
		ok(output.transferId, "transfer id");
		ok(transferEvents.some(event => event.event === "transfer-start"), "start event", );
		ok(transferEvents.some(event => event.event === "transfer-end"), "end event", );
		await throws(
			() => rolling.transfer("missing-id"), Error, "unknown transfer", );
		await throws(
			() => rolling.transfer(video.id, {
				chunkSize: 0,
			}), RangeError, "chunkSize", );
		removeGlobal("__evidenceSink");
		await throws(() => rolling.transfer(video.id), Error, "no sink");
	});
	await test("RollingCapture disarm and clear", async () => {
		const pending = await rolling.start({
			id: "pending",
		});
		eq(pending.id, "pending", "pending started");
		await throws(() => rolling.disarm(), Error, "active captures block");
		const pump = setInterval(draw, 15);
		await sleep(400);
		const status = await rolling.disarm({
			force: true,
			clear: true,
		});
		clearInterval(pump);
		eq(status.armed, false, "disarmed");
		ok(rolling.clear() === rolling, "clear chainable");
		rolling.remove("manual");
	});
	await test("RollingCapture quality object merges", async () => {
		const custom = new RollingCapture({
			target: videoCanvas,
			quality: {
				fps: 12,
				videoBitsPerSecond: 123,
			},
			fps: 7,
		});
		eq(custom.quality.fps, 7, "fps override");
		eq(custom.quality.videoBitsPerSecond, 123, "bitrate");
		const configuredQuality = custom.config().quality;
		ok(typeof configuredQuality === "object" && configuredQuality !== null && "fps" in configuredQuality && configuredQuality.fps === 12, "config quality object", );
		const named = new RollingCapture({
			quality: "ultra",
			target: videoCanvas,
		});
		eq(named.quality.fps, 60, "ultra preset");
		named.remove("x");
	});
	// ── EvidenceRuntime ─────────────────────────────────────────────
	await test("EvidenceRuntime configuration and status", async () => {
		const runtime = new EvidenceRuntime({
			target: videoCanvas,
			eventPrefix: "testrt",
			diagnostics: {
				interval: 25,
			},
			maxDescriptions: 3,
			maxTimelineEntries: 50,
		});
		eq(runtime.config().eventPrefix, "testrt", "prefix");
		const status = runtime.status();
		ok(status.memory, "memory report");
		eq(status.modes.join(","), "video,capture,description", "modes");
		runtime.mark("note", {
			a: 1,
		});
		const marks = runtime.markers();
		eq(marks.length, 1, "one marker");
		eq(marks[0]?.type, "note", "marker type");
		eq(runtime.markers({
			since: Date.now() + 99999,
		}).length, 0, "since filter", );
		await throws(
			() => runtime.evidence({
				modes: ["bogus"],
			}), TypeError, "mode validation", );
		await throws(
			() => runtime.evidence({
				modes: ["video"],
				duration: 0,
			}), Error, "video needs duration", );
		runtime.startDiagnostics({
			interval: 20,
		});
		/**
		 * Append one diagnostic mutation.
		 *
		 * @param {number} index Mutation index.
		 * @returns {Promise<void>}
		 */
		const appendMutation = async index => {
			const node = document.createElement("span");
			node.textContent = `mut${index}`;
			root.appendChild(node);
			await sleep(15);
		};
		await [0, 1, 2, 3, 4].reduce(
			(previous, index) => previous.then(() => appendMutation(index)), Promise.resolve(), );
		ok(runtime.diagnostics().length > 0, "diagnostics collected");
		runtime.stopDiagnostics();
		await throws(() => runtime.transfer("nope"), Error, "no such transfer");
		const pump = setInterval(draw, 15);
		const output = await runtime.evidence({
			modes: ["capture", "description"],
			target: videoCanvas,
			metadata: {
				run: 1,
			},
			description: {
				options: {
					includeRelationships: false,
				},
			},
		});
		clearInterval(pump);
		ok(output.capture && output.capture.kind === "capture", "capture mode");
		ok(output.description && output.description.kind === "description", "describe mode", );
		ok(Array.isArray(output.markers), "markers in output");
		const described = await runtime.describe({
			target: videoCanvas,
			externalizeBinary: false,
		});
		ok(described.manifest, "describe alias manifest");
		/** @type {SinkPayload[]} */
		const sinkEvents = [];
		setGlobal("__rtSink",
			/**
			 * Receive one runtime transfer payload.
			 *
			 * @param {SinkPayload} payload Transfer payload.
			 * @returns {Promise<void>}
			 */
			async payload => {
				sinkEvents.push(payload);
			}, );
		const transfer = await runtime.transfer(described.id, {
			sink: "__rtSink",
		});
		ok(transfer.transferId, "description transfer");
		ok(sinkEvents.length >= 3, "sink received chunks");
		removeGlobal("__rtSink");
		await throws(() => runtime.transfer("gone"), Error, "missing description");
		ok(runtime.remove("gone") === false, "remove missing");
		runtime.clear();
		await runtime.destroy();
		eq(runtime.status().armed, false, "destroy disarms");
	});
	await test("EvidenceRuntime video mode end to end", async () => {
		const runtime = new EvidenceRuntime({
			target: videoCanvas,
			quality: "low",
			window: 1500,
			segmentDuration: 60,
			eventPrefix: "testvid",
		});
		/** @type {string[]} */
		const resultEvents = [];
		runtime.addEventListener("result", event => {
			const detail =
				/** @type {RuntimeEvent} */
				(event.detail);
			resultEvents.push(detail.type);
		});
		const pump = setInterval(draw, 15);
		const output = await runtime.evidence({
			modes: ["video"],
			duration: 500,
			before: 0,
			metadata: {
				m: 2,
			},
		});
		clearInterval(pump);
		ok(output.video && output.video.kind === "video", "video mode");
		if (!output.video) throw new Error("video mode missing");
		ok(resultEvents.length > 0, "result events fired");
		setGlobal("__evidenceSink", async () => {});
		const transfer = await runtime.transfer(output.video.id);
		ok(transfer.transferId, "video transfer");
		removeGlobal("__evidenceSink");
		await runtime.destroy();
	});
	setGlobal("__sceneTestResults", results);
	globalThis.dispatchEvent?.(new CustomEvent("scene-tests-done"));
})();
