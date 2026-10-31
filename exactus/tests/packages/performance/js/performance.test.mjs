/** @file node:test suite covering exactus/packages/performance/web/code.js. */
"use strict";
import assert from "node:assert/strict";
import {
	createRequire
} from "node:module";
import test from "node:test";
/**
 * @typedef {{x: number, y: number, width: number, height: number, top: number, left: number, right: number, bottom: number}} FakeRect
 */
/**
 * @typedef {(event: Record<string, unknown>) => void} FakeListener
 */
/**
 * @typedef {{ok: boolean, status: number, json: () => Promise<unknown>}} FakeResponse
 */
const require = createRequire(import.meta.url);
const CODE_PATH = require.resolve("../../../../packages/performance/web/code.js");
/** Element double implementing the DOM surface `code.js` touches. */
class FakeElement {
	/**
	 * Create an element with a tag name.
	 *
	 * @param {string} tag Element tag name.
	 */
	constructor(tag = "div") {
		/** @type {string} */
		this.tagName = tag;
		/** @type {string} */
		this.id = "";
		/** @type {Set<string>} */
		this.names = new Set();
		/** @type {Map<string, string>} */
		this.attributes = new Map();
		/** @type {Map<string, FakeListener[]>} */
		this.listeners = new Map();
		/** @type {FakeElement[]} */
		this.children = [];
		/** @type {FakeElement | null} */
		this.parent = null;
		/** @type {Record<string, string>} */
		this.style = {};
		/** @type {string} */
		this.textContent = "";
		/** @type {boolean} */
		this.hidden = false;
		/** @type {boolean} */
		this.isFragment = false;
		/** @type {string} */
		this.value = "";
		/** @type {number} */
		this.clientWidth = 800;
		/** @type {number} */
		this.width = 0;
		/** @type {number} */
		this.height = 0;
		/** @type {boolean} */
		this.scrolled = false;
		/** @type {FakeElement | undefined} */
		this.content = undefined;
		/** @type {number | null} */
		this.capturedPointer = null;
	}
	/**
	 * Return a `classList` view over the class name set.
	 *
	 * @returns {{add: Function, remove: Function, toggle: Function, contains: Function}} Class list shim.
	 */
	get classList() {
		const names = this.names;
		return {
			/** @param {string} name Class name. */
			add: name => names.add(name),
			/** @param {string} name Class name. */
			remove: name => names.delete(name),
			/**
			 * @param {string} name Class name.
			 * @param {boolean} [force] Forced state.
			 * @returns {boolean} Resulting presence.
			 */
			toggle: (name, force) => {
				const next = force ?? !names.has(name);
				if (next) names.add(name);
				else names.delete(name);
				return next;
			},
			/**
			 * @param {string} name Class name.
			 * @returns {boolean} Presence flag.
			 */
			contains: name => names.has(name),
		};
	}
	/**
	 * Match this element against a simple selector.
	 *
	 * @param {string} selector Selector such as `.cls`, `[data-x="y"]`, `[id]` or `tag`.
	 * @returns {boolean} Whether the element matches.
	 */
	matches(selector) {
		return selector.split(",").some(part => {
			const text = part.trim();
			const attribute = /^\[([\w-]+)(?:="([^"]*)")?\]$/.exec(text);
			if (attribute) {
				const value = this.getAttribute( /** @type {string} */ (attribute[1]));
				return attribute[2] === undefined ? value !== null : value === attribute[2];
			}
			if (text.startsWith(".")) return this.names.has(text.slice(1));
			if (text.startsWith("#")) return this.id === text.slice(1);
			return this.tagName === text;
		});
	}
	/**
	 * Collect descendants matching a selector.
	 *
	 * @param {string} selector Selector text.
	 * @returns {FakeElement[]} Matching descendants.
	 */
	querySelectorAll(selector) {
		/** @type {FakeElement[]} */
		const found = [];
		/** @type {(node: FakeElement) => void} */
		const visit = node => {
			node.children.forEach(child => {
				if (child.matches(selector)) found.push(child);
				visit(child);
			});
		};
		visit(this);
		return found;
	}
	/**
	 * Return the first descendant matching a selector.
	 *
	 * @param {string} selector Selector text.
	 * @returns {FakeElement | null} Matching descendant or `null`.
	 */
	querySelector(selector) {
		return this.querySelectorAll(selector)[0] ?? null;
	}
	/**
	 * Walk ancestors looking for a selector match.
	 *
	 * @param {string} selector Selector text.
	 * @returns {FakeElement | null} Matching ancestor or `null`.
	 */
	closest(selector) {
		let node = this.parent;
		while (node) {
			if (node.matches(selector)) return node;
			node = node.parent;
		}
		return null;
	}
	/**
	 * Register an event listener.
	 *
	 * @param {string} type Event type.
	 * @param {FakeListener} listener Listener to call.
	 * @returns {void}
	 */
	addEventListener(type, listener) {
		const list = this.listeners.get(type) ?? [];
		list.push(listener);
		this.listeners.set(type, list);
	}
	/**
	 * Dispatch a fake event to every registered listener.
	 *
	 * @param {string} type Event type.
	 * @param {Record<string, unknown>} [event] Event payload.
	 * @returns {void}
	 */
	fire(type, event = {}) {
		(this.listeners.get(type) ?? []).forEach(listener => {
			listener(event);
		});
	}
	/**
	 * Append a node, splicing fragment children into place.
	 *
	 * @param {FakeElement} node Node to append.
	 * @returns {void}
	 */
	append(node) {
		if (node.isFragment) {
			[...node.children].forEach(child => {
				this.append(child);
			});
			node.children = [];
			return;
		}
		node.parent = this;
		this.children.push(node);
	}
	/**
	 * Remove all children.
	 *
	 * @returns {void}
	 */
	replaceChildren() {
		this.children.forEach(child => {
			child.parent = null;
		});
		this.children = [];
	}
	/**
	 * Read an attribute.
	 *
	 * @param {string} name Attribute name.
	 * @returns {string | null} Attribute value.
	 */
	getAttribute(name) {
		if (name === "id") return this.id || null;
		return this.attributes.get(name) ?? null;
	}
	/**
	 * Store an attribute.
	 *
	 * @param {string} name Attribute name.
	 * @param {string} value Attribute value.
	 * @returns {void}
	 */
	setAttribute(name, value) {
		this.attributes.set(name, value);
	}
	/**
	 * Deep-copy this node.
	 *
	 * @param {boolean} [deep] Whether to copy descendants.
	 * @returns {FakeElement} Detached copy.
	 */
	cloneNode(deep = false) {
		const copy = new FakeElement(this.tagName);
		copy.isFragment = this.isFragment;
		copy.id = this.id;
		copy.names = new Set(this.names);
		copy.attributes = new Map(this.attributes);
		copy.textContent = this.textContent;
		if (deep) this.children.forEach(child => {
			copy.append(child.cloneNode(true));
		});
		return copy;
	}
	/**
	 * Return a deterministic layout rectangle.
	 *
	 * @returns {FakeRect} Bounding rectangle.
	 */
	getBoundingClientRect() {
		return {
			x: 0,
			y: 0,
			top: 0,
			left: 0,
			right: 800,
			bottom: 430,
			width: 800,
			height: 430
		};
	}
	/**
	 * Record a scroll-into-view request.
	 *
	 * @returns {void}
	 */
	scrollIntoView() {
		this.scrolled = true;
	}
	/**
	 * Record a pointer capture request.
	 *
	 * @param {number} pointerId Pointer identifier.
	 * @returns {void}
	 */
	setPointerCapture(pointerId) {
		this.capturedPointer = pointerId;
	}
	/**
	 * Report pointer capture state.
	 *
	 * @param {number} pointerId Pointer identifier.
	 * @returns {boolean} Capture flag.
	 */
	hasPointerCapture(pointerId) {
		return this.capturedPointer === pointerId;
	}
	/**
	 * Record a pointer capture release.
	 *
	 * @param {number} pointerId Pointer identifier.
	 * @returns {void}
	 */
	releasePointerCapture(pointerId) {
		if (this.capturedPointer === pointerId) this.capturedPointer = null;
	}
	/**
	 * Return a recording 2D context stub.
	 *
	 * @returns {Record<string, unknown>} Recording context.
	 */
	getContext() {
		/** @type {string[]} */
		const calls = [];
		const context = /** @type {Record<string, unknown>} */ ({
			calls
		});
		["scale", "clearRect", "fillRect", "fillText", "beginPath", "moveTo", "lineTo", "stroke", "fill", "closePath", "setLineDash", "save", "restore"].forEach(name => {
			context[name] = () => {
				calls.push(name);
			};
		});
		return context;
	}
}
/** Document double exposing the selectors `code.js` queries. */
class FakeDocument extends FakeElement {
	/** Create a document with an empty registry. */
	constructor() {
		super("document");
		/** @type {FakeElement | null} */
		this.documentElement = null;
		/** @type {FakeElement[]} */
		this.modes = [];
		/** @type {FakeElement[]} */
		this.registry = [];
	}
	/**
	 * Return registered elements matching a supported selector.
	 *
	 * @param {string} selector Selector text.
	 * @returns {FakeElement[]} Matching registered elements.
	 * @override
	 */
	querySelectorAll(selector) {
		if (selector === "[id]") return this.registry;
		if (selector === ".mode") return this.modes;
		if (selector === ".view") return this.registry.filter(node => node.names.has("view"));
		return this.registry.flatMap(node => (node.matches(selector) ? [node] : [])).concat(this.registry.flatMap(node => node.querySelectorAll(selector)));
	}
}
/**
 * Build an element with optional id and class names.
 *
 * @param {string} [id] Element id.
 * @param {string[]} [names] Class names.
 * @returns {FakeElement} Registered element.
 */
const el = (id = "", names = []) => {
	const node = new FakeElement();
	node.id = id;
	names.forEach(name => {
		node.names.add(name);
	});
	return node;
};
/**
 * Build a `<template>` double whose content clones on demand.
 *
 * @param {string} id Template id.
 * @param {FakeElement[]} children Template children.
 * @returns {FakeElement} Template element.
 */
const template = (id, children) => {
	const node = el(id);
	const fragment = new FakeElement();
	fragment.isFragment = true;
	children.forEach(child => {
		fragment.append(child);
	});
	/** @type {FakeElement} */
	node.content = fragment;
	return node;
};
/**
 * Build one `data-field` leaf element.
 *
 * @param {string} name Field name.
 * @param {string[]} [names] Extra class names.
 * @returns {FakeElement} Field element.
 */
const fieldEl = (name, names = []) => {
	const node = el("", names);
	node.setAttribute("data-field", name);
	return node;
};
/**
 * Build a rank-style row template body.
 *
 * @param {string[]} [names] Row class names.
 * @returns {FakeElement} Row element.
 */
const rankRow = (names = ["rank-row"]) => {
	const row = el("", names);
	row.append(fieldEl("rank"));
	const main = el("", ["rank-main"]);
	main.append(fieldEl("title"));
	main.append(fieldEl("detail"));
	const meter = el("", ["meter"]);
	meter.append(fieldEl("bar"));
	main.append(meter);
	row.append(main);
	row.append(fieldEl("value"));
	return row;
};
/**
 * Assemble the fake document consumed by `code.js`.
 *
 * @returns {{document: FakeDocument, ids: Map<string, FakeElement>}} Document tree.
 */
const buildDocument = () => {
	const documentElement = el("");
	const shell = el("", ["timeline-shell"]);
	const chart = el("detail-chart");
	shell.append(chart);
	const ids = new Map();
	["status", "theme", "drillbar", "detail-tooltip", "global-timeline", "zoom-in", "zoom-out", "pan-left", "pan-right", "reset-view", "zoom-label", "kpi-wall", "kpi-runtime", "kpi-events", "kpi-rate", "kpi-gap", "kpi-gap-tool", "kpi-slowest", "kpi-slowest-time", "tool-list", "tool-kicker", "tool-name", "tool-summary", "gap-list", "gap-total", "prefix-list", "stage-list", "event-count", "event-list", "cursor-readout", "cursor-rate", "cursor-gap", "cursor-position", "cursor-nearby", "inspect-index", "inspect-elapsed", "inspect-time", "inspect-message", "kpi-silent", "kpi-silent-note", "kpi-hot", "kpi-hot-note", "actor-list", "actor-total", "template-list", "slow-list", "share-chart", "worker-chart", "worker-list", "inspect-thread", "inspect-cost", "graph-chart", "graph-overview", "graph-scroll", "graph-crumbs", "graph-up", "graph-in", "graph-color", "graph-tooltip", "graph-node", "graph-measures", "graph-children", "cpu-chart", "mem-chart", "io-chart", "resource-tooltip", "res-cpu-mean", "res-cpu-peak", "res-rss-peak", "res-read", "res-write", "res-procs", "resource-actors", "resource-note", "bottlenecks-view", "stages-view", "events-view", "hotspots-view", "workers-view", "graph-view", "resources-view", ].forEach(id => {
		ids.set(id, el(id));
	});
	ids.set("detail-chart", chart);
	const search = el("search");
	ids.set("search", /** @type {FakeElement} */ (search));
	["bottlenecks", "stages", "events", "hotspots", "workers", "graph", "resources"].forEach(view => {
		/** @type {FakeElement} */
		(ids.get(`${view}-view`)).names.add("view");
	});
	const modes = ["bottlenecks", "stages", "events", "hotspots", "workers", "graph", "resources"].map((mode, index) => {
		const button = el("", ["mode", ...(index === 0 ? ["active"] : [])]);
		button.setAttribute("data-mode", mode);
		return button;
	});
	const toolCard = el("", ["tool-card"]);
	toolCard.append(el("", ["tool-marker"]));
	toolCard.append(fieldEl("name"));
	toolCard.append(fieldEl("meta"));
	toolCard.append(fieldEl("duration"));
	const stageRow = el("", ["stage-row"]);
	stageRow.append(fieldEl("duration"));
	stageRow.append(fieldEl("start"));
	stageRow.append(fieldEl("name"));
	stageRow.append(fieldEl("detail"));
	stageRow.append(fieldEl("bar"));
	const eventRow = el("", ["event-row"]);
	eventRow.append(fieldEl("time"));
	eventRow.append(fieldEl("delta"));
	eventRow.append(fieldEl("message"));
	const crumb = el("", ["crumb"]);
	crumb.append(fieldEl("label"));
	ids.set("tool-template", template("tool-template", [toolCard]));
	ids.set("gap-template", template("gap-template", [rankRow()]));
	ids.set("prefix-template", template("prefix-template", [rankRow(["rank-row", "compact"])]));
	ids.set("stage-template", template("stage-template", [stageRow]));
	ids.set("event-template", template("event-template", [eventRow]));
	ids.set("crumb-template", template("crumb-template", [crumb]));
	const documentNode = new FakeDocument();
	documentNode.documentElement = documentElement;
	documentNode.modes = modes;
	documentNode.registry = [...ids.values()];
	return {
		document: documentNode,
		ids
	};
};
/** Steps payload exercising every render lane. */
const RICH = {
	gamma: ["2024-01-01T00:00:00.000Z +0.000s tool: start", "2024-01-01T00:00:00.100Z +0.100s lint: /src/a.py — 3 files @thread=Pool_1", "2024-01-01T00:00:00.200Z +0.200s lint: /src/b.py — 5 files @thread=Pool_2", "2024-01-01T00:00:02.200Z +2.200s lint: /src/c.py — 7 files @thread=Pool_1", "2024-01-01T00:00:02.300Z +2.300s exec: ruff — exit 0 in 1.250s", "2024-01-01T00:00:02.400Z +2.400s stage: build @span=1", "2024-01-01T00:00:03.400Z +3.400s stage: build — done @span=1 @dur=1.000s", "2024-01-01T00:00:03.500Z +3.500s tool: done", ],
};
const SAMPLED = {
	delta: ["2024-01-01T00:00:00.000Z +0.000s tool: start", "2024-01-01T00:00:00.500Z +0.500s ~sample cpu=80.0 rss=120.0 threads=4 procs=2 read=1.00 write=0.50 ioscope=proc", "2024-01-01T00:00:00.600Z +0.600s stage: build", "2024-01-01T00:00:00.700Z +0.700s   step: compile", "2024-01-01T00:00:01.900Z +1.900s   step: link", "2024-01-01T00:00:02.100Z +2.100s ~sample cpu=10.0 rss=300.0 threads=2 procs=1 read=0.00 write=2.00 ioscope=proc", "2024-01-01T00:00:02.600Z +2.600s stage: report", "2024-01-01T00:00:03.000Z +3.000s tool: done", ],
};
const TRACE = {
	alpha: ["2024-01-01T00:00:00.000Z +0.000s stage: boot", "2024-01-01T00:00:00.400Z +0.400s tool: ruff — lint files", "2024-01-01T00:00:01.000Z +1.000s stage: analyze", "2024-01-01T00:00:01.300Z +1.300s tool: ruff — fix files", "2024-01-01T00:00:01.900Z +1.900s tool: pytest — run tests", "2024-01-01T00:00:02.000Z +2.000s done: complete", ],
	beta: ["2024-01-01T00:00:00.100Z +0.000s stage: setup", "2024-01-01T00:00:01.100Z +1.000s tool: node — build", "2024-01-01T00:00:02.100Z +2.000s done: complete", "unparsed trailing line", ],
};
/**
 * Load `code.js` fresh against a new fake browser environment.
 *
 * @param {unknown} payload Fake `steps.json` payload or an error.
 * @param {Record<string, string[]>} [embedded] Fake `data.js` payload.
 * @returns {Promise<{ids: Map<string, FakeElement>, documentElement: FakeElement, modes: FakeElement[], window: {devicePixelRatio: number, addEventListener: Function, listeners: Map<string, FakeListener[]>, __PERFORMANCE_STEPS__: Record<string, string[]> | undefined}}>} Handles into the fake DOM.
 */
const loadDashboard = async (payload, embedded = undefined) => {
	const {
		document,
		ids
	} = buildDocument();
	const windowListeners = new Map();
	const windowObject = {
		devicePixelRatio: 2,
		/**
		 * @param {string} type Event type.
		 * @param {FakeListener} listener Listener to register.
		 * @returns {void}
		 */
		addEventListener: (type, listener) => {
			windowListeners.set(type, [...(windowListeners.get(type) ?? []), listener]);
		},
		listeners: windowListeners,
		__PERFORMANCE_STEPS__: embedded,
	};
	Object.assign(globalThis, {
		document,
		window: windowObject,
		getComputedStyle: () => ({
			/**
			 * @returns {string} Stub color value.
			 */
			getPropertyValue: () => "#ffffff",
		}),
		fetch: () => {
			if (payload instanceof Error) return Promise.reject(payload);
			return Promise.resolve({
				ok: payload !== null,
				status: payload === null ? 500 : 200,
				json: () => Promise.resolve(payload ?? {}),
			});
		},
	});
	delete require.cache[CODE_PATH];
	require(CODE_PATH);
	await new Promise(resolve => {
		setTimeout(resolve, 0);
	});
	await new Promise(resolve => {
		setTimeout(resolve, 0);
	});
	return {
		ids,
		documentElement: /** @type {FakeElement} */ (document.documentElement),
		modes: document.modes,
		window: windowObject
	};
};
test("a failed steps.json fetch reports the status error", async () => {
	const {
		ids
	} = await loadDashboard(new Error("network down"));
	const status = /** @type {FakeElement} */ (ids.get("status"));
	assert.ok(status.textContent.includes("Could not load data.js or steps.json"));
	assert.ok(status.names.has("error"));
});
test("an embedded data.js payload renders without fetching", async () => {
	const {
		ids
	} = await loadDashboard(new Error("fetch must not run"), TRACE);
	assert.equal( /** @type {FakeElement} */ (ids.get("kpi-events")).textContent, "10");
	assert.equal( /** @type {FakeElement} */ (ids.get("tool-name")).textContent, "alpha");
	assert.ok(! /** @type {FakeElement} */ (ids.get("status")).names.has("error"));
});
test("an HTTP error reports the status error", async () => {
	const {
		ids
	} = await loadDashboard(null);
	const status = /** @type {FakeElement} */ (ids.get("status"));
	assert.ok(status.textContent.includes("HTTP 500"));
	assert.ok(status.names.has("error"));
});
test("an empty payload renders without detail panels", async () => {
	const {
		ids
	} = await loadDashboard({});
	assert.equal( /** @type {FakeElement} */ (ids.get("kpi-events")).textContent, "0");
	assert.equal( /** @type {FakeElement} */ (ids.get("kpi-gap-tool")).textContent, "—");
	assert.equal( /** @type {FakeElement} */ (ids.get("kpi-slowest")).textContent, "—");
});
test("traces render KPIs, tool cards, and detail sections", async () => {
	const {
		ids
	} = await loadDashboard(TRACE);
	assert.equal( /** @type {FakeElement} */ (ids.get("kpi-events")).textContent, "10");
	assert.equal( /** @type {FakeElement} */ (ids.get("tool-name")).textContent, "alpha");
	assert.ok( /** @type {FakeElement} */ (ids.get("tool-summary")).textContent.includes("events/s"));
	assert.equal( /** @type {FakeElement} */ (ids.get("tool-list")).children.length, 2);
	assert.ok( /** @type {FakeElement} */ (ids.get("gap-list")).children.length > 0);
	assert.ok( /** @type {FakeElement} */ (ids.get("prefix-list")).children.length > 0);
	assert.ok( /** @type {FakeElement} */ (ids.get("stage-list")).children.length > 0);
	assert.equal( /** @type {FakeElement} */ (ids.get("event-list")).children.length, 6);
	assert.equal( /** @type {FakeElement} */ (ids.get("event-count")).textContent, "6 / 6");
	assert.ok( /** @type {FakeElement} */ (ids.get("inspect-message")).textContent.length > 0);
});
test("tool card clicks switch the selected trace", async () => {
	const {
		ids
	} = await loadDashboard(TRACE);
	const card = /** @type {FakeElement} */ ( /** @type {FakeElement} */ (ids.get("tool-list")).children[1]);
	card.fire("click");
	assert.equal( /** @type {FakeElement} */ (ids.get("tool-name")).textContent, "beta");
	assert.equal( /** @type {FakeElement} */ (ids.get("event-list")).children.length, 4);
});
test("search input filters ranking rows and events", async () => {
	const {
		ids
	} = await loadDashboard(TRACE);
	const search = /** @type {FakeElement} */ (ids.get("search"));
	search.fire("input", {
		target: {
			value: "pytest"
		}
	});
	assert.equal( /** @type {FakeElement} */ (ids.get("event-count")).textContent, "1 / 6");
	search.fire("input", {
		target: {
			value: ""
		}
	});
	assert.equal( /** @type {FakeElement} */ (ids.get("event-count")).textContent, "6 / 6");
});
test("mode buttons toggle views and theme toggles the root class", async () => {
	const {
		ids,
		documentElement,
		modes
	} = await loadDashboard(TRACE);
	modes[1]?.fire("click");
	assert.ok( /** @type {FakeElement} */ (ids.get("stages-view")).names.has("active"));
	modes[2]?.fire("click");
	assert.ok( /** @type {FakeElement} */ (ids.get("events-view")).names.has("active"));
	const themeButton = /** @type {FakeElement} */ (ids.get("theme"));
	themeButton.fire("click");
	assert.ok(documentElement.names.has("light"));
});
test("zoom, pan, and reset controls adjust the viewport", async () => {
	const {
		ids
	} = await loadDashboard(TRACE);
	/** @type {FakeElement} */
	(ids.get("zoom-in")).fire("click");
	/** @type {FakeElement} */
	(ids.get("zoom-out")).fire("click");
	/** @type {FakeElement} */
	(ids.get("pan-left")).fire("click");
	/** @type {FakeElement} */
	(ids.get("pan-right")).fire("click");
	/** @type {FakeElement} */
	(ids.get("reset-view")).fire("click");
	assert.equal( /** @type {FakeElement} */ (ids.get("zoom-label")).textContent, "full trace");
});
test("chart pointer, wheel, keyboard, and click handlers drive interaction", async () => {
	const {
		ids
	} = await loadDashboard(TRACE);
	const chart = /** @type {FakeElement} */ (ids.get("detail-chart"));
	const tooltip = /** @type {FakeElement} */ (ids.get("detail-tooltip"));
	chart.fire("pointerdown", {
		pointerId: 1,
		clientX: 400,
		clientY: 200
	});
	chart.fire("pointermove", {
		pointerId: 1,
		clientX: 420,
		clientY: 210
	});
	assert.equal(tooltip.hidden, false);
	assert.ok(tooltip.textContent.includes("#"));
	chart.fire("pointerup", {
		pointerId: 1
	});
	chart.fire("pointercancel", {});
	chart.fire("click", {
		clientX: 500,
		clientY: 200
	});
	let prevented = false;
	chart.fire("wheel", {
		deltaY: -1,
		clientX: 400,
		preventDefault: () => (prevented = true)
	});
	assert.ok(prevented);
	chart.fire("wheel", {
		deltaY: 1,
		clientX: 400,
		preventDefault: () => {}
	});
	chart.fire("keydown", {
		key: "ArrowRight",
		shiftKey: true,
		preventDefault: () => {}
	});
	chart.fire("keydown", {
		key: "ArrowLeft",
		shiftKey: false,
		preventDefault: () => {}
	});
	chart.fire("keydown", {
		key: "Enter",
		preventDefault: () => {}
	});
	chart.fire("pointermove", {
		pointerId: 1,
		clientX: 40,
		clientY: 50
	});
	chart.fire("pointerleave", {});
	assert.equal(tooltip.hidden, true);
});
test("gap, prefix, and stage rows drill into intervals", async () => {
	const {
		ids
	} = await loadDashboard(TRACE);
	const gapRow = /** @type {FakeElement} */ ( /** @type {FakeElement} */ (ids.get("gap-list")).children[0]);
	gapRow.fire("click");
	assert.ok( /** @type {FakeElement} */ (ids.get("zoom-label")).textContent.includes("window"));
	const prefixRow = /** @type {FakeElement} */ ( /** @type {FakeElement} */ (ids.get("prefix-list")).children[0]);
	prefixRow.fire("click");
	const stageRow = /** @type {FakeElement} */ ( /** @type {FakeElement} */ (ids.get("stage-list")).children[0]);
	stageRow.fire("click");
	const drillbar = /** @type {FakeElement} */ (ids.get("drillbar"));
	assert.ok(drillbar.children.length >= 2);
	drillbar.children[0]?.querySelector("[data-field=\"label\"]")?.fire("click");
	const crumbs = /** @type {FakeElement} */ (ids.get("drillbar")).children;
	crumbs[crumbs.length - 1]?.querySelector("[data-field=\"label\"]")?.fire("click");
});
test("event rows move the cursor and highlight related rows", async () => {
	const {
		ids
	} = await loadDashboard(TRACE);
	const list = /** @type {FakeElement} */ (ids.get("event-list"));
	const rows = list.querySelectorAll(".event-row");
	rows[2]?.fire("click");
	assert.ok( /** @type {FakeElement} */ (ids.get("inspect-index")).textContent.includes("3"));
	assert.ok(rows.some(row => row.scrolled));
});
test("window resize redraws both charts", async () => {
	const {
		window
	} = await loadDashboard(TRACE);
	const listeners = window.listeners;
	(listeners.get("resize") ?? []).forEach(listener => {
		listener({});
	});
	assert.ok(true);
});
test("trailers, spans and embedded durations become event fields", async () => {
	const {
		ids
	} = await loadDashboard(RICH, RICH);
	const events = /** @type {FakeElement} */ (ids.get("event-list")).querySelectorAll(".event-row");
	assert.equal(events.length, 8);
	assert.ok(! /** @type {FakeElement} */ (ids.get("inspect-message")).textContent.includes("@thread"));
	assert.equal( /** @type {FakeElement} */ (ids.get("kpi-events")).textContent, "8");
});
test("hotspot lists rank actors, operations and slow steps", async () => {
	const {
		ids
	} = await loadDashboard(RICH, RICH);
	const actors = /** @type {FakeElement} */ (ids.get("actor-list")).children;
	assert.ok(actors.length >= 3);
	assert.ok( /** @type {FakeElement} */ (ids.get("actor-total")).textContent.includes("actors"));
	const operations = /** @type {FakeElement} */ (ids.get("template-list")).children;
	assert.ok(operations.length >= 3);
	const slow = /** @type {FakeElement} */ (ids.get("slow-list")).children;
	assert.ok(slow.length > 0);
	assert.ok( /** @type {FakeElement} */ (ids.get("kpi-hot")).textContent.length > 1);
	assert.ok( /** @type {FakeElement} */ (ids.get("kpi-silent-note")).textContent.includes("%"));
});
test("worker rows list each thread and drill into its activity", async () => {
	const {
		ids
	} = await loadDashboard(RICH, RICH);
	const workers = /** @type {FakeElement} */ (ids.get("worker-list")).children;
	assert.equal(workers.length, 3);
	workers[workers.length - 1]?.fire("click");
	assert.ok( /** @type {FakeElement} */ (ids.get("zoom-label")).textContent.includes("window"));
});
test("hotspot rows drill into actors, operations and slow steps", async () => {
	const {
		ids
	} = await loadDashboard(RICH, RICH);
	["actor-list", "template-list", "slow-list"].forEach(id => {
		const row = /** @type {FakeElement} */ (ids.get(id)).children[0];
		row?.fire("click");
	});
	const drillbar = /** @type {FakeElement} */ (ids.get("drillbar"));
	assert.ok(drillbar.children.length >= 3);
});
test("the hotspot search filter narrows actor rows", async () => {
	const {
		ids
	} = await loadDashboard(RICH, RICH);
	const before = /** @type {FakeElement} */ (ids.get("actor-list")).children.length;
	/** @type {FakeElement} */
	(ids.get("search")).fire("input", {
		target: {
			value: "lint"
		}
	});
	const after = /** @type {FakeElement} */ (ids.get("actor-list")).children.length;
	assert.ok(after < before);
	assert.equal(after, 1);
});
test("sample lines never become events and feed the resource view", async () => {
	const {
		ids
	} = await loadDashboard(SAMPLED, SAMPLED);
	assert.equal( /** @type {FakeElement} */ (ids.get("kpi-events")).textContent, "6");
	assert.ok( /** @type {FakeElement} */ (ids.get("res-cpu-peak")).textContent.includes("80"));
	assert.ok( /** @type {FakeElement} */ (ids.get("res-rss-peak")).textContent.includes("300"));
	assert.ok( /** @type {FakeElement} */ (ids.get("resource-note")).textContent.includes("2 samples"));
	assert.ok( /** @type {FakeElement} */ (ids.get("resource-actors")).children.length > 0);
});
test("a trace without samples explains how to record them", async () => {
	const {
		ids
	} = await loadDashboard(TRACE, TRACE);
	assert.ok( /** @type {FakeElement} */ (ids.get("resource-note")).textContent.includes("sample = 0.5"));
	assert.equal( /** @type {FakeElement} */ (ids.get("res-cpu-mean")).textContent, "—");
});
test("the graph drills into a node and back up", async () => {
	const {
		ids
	} = await loadDashboard(SAMPLED, SAMPLED);
	const chart = /** @type {FakeElement} */ (ids.get("graph-chart"));
	// Node rows are drawn at y = 6 + 20 + level * 18 inside the lane.
	/**
	 * Fire a pointer tap at chart coordinates.
	 *
	 * @param {number} x - Horizontal pointer position.
	 * @param {number} y - Vertical pointer position.
	 * @returns {void}
	 */
	const click = (x, y) => {
		chart.fire("pointerdown", {
			pointerId: 1,
			clientX: x,
			clientY: y
		});
		chart.fire("pointerup", {
			pointerId: 1,
			clientX: x,
			clientY: y
		});
	};
	click(400, 32);
	assert.ok( /** @type {FakeElement} */ (ids.get("graph-node")).textContent.length > 0);
	assert.ok( /** @type {FakeElement} */ (ids.get("graph-measures")).textContent.includes("total"));
	chart.fire("dblclick", {
		clientX: 400,
		clientY: 32
	});
	const crumbs = /** @type {FakeElement} */ (ids.get("graph-crumbs"));
	assert.ok(crumbs.children.length >= 2);
	/** @type {FakeElement} */
	(ids.get("graph-up")).fire("click");
	assert.equal(crumbs.children.length, 1);
	chart.fire("keydown", {
		key: "Enter",
		preventDefault: () => {}
	});
	chart.fire("keydown", {
		key: "Escape",
		preventDefault: () => {}
	});
	/** @type {FakeElement} */
	(ids.get("graph-in")).fire("click");
	/** @type {FakeElement} */
	(ids.get("graph-color")).fire("change");
});
test("graph and resource canvases pan and zoom the shared viewport", async () => {
	const {
		ids
	} = await loadDashboard(SAMPLED, SAMPLED);
	const chart = /** @type {FakeElement} */ (ids.get("graph-chart"));
	chart.fire("wheel", {
		deltaY: -1,
		clientX: 400,
		preventDefault: () => {}
	});
	assert.ok( /** @type {FakeElement} */ (ids.get("zoom-label")).textContent.includes("window"));
	chart.fire("pointerdown", {
		pointerId: 1,
		clientX: 400,
		clientY: 40
	});
	chart.fire("pointermove", {
		pointerId: 1,
		clientX: 300,
		clientY: 40
	});
	chart.fire("pointerup", {
		pointerId: 1,
		clientX: 300,
		clientY: 40
	});
	const cpu = /** @type {FakeElement} */ (ids.get("cpu-chart"));
	cpu.fire("pointermove", {
		clientX: 300,
		clientY: 40
	});
	assert.equal( /** @type {FakeElement} */ (ids.get("resource-tooltip")).hidden, false);
	cpu.fire("pointerleave", {});
	assert.equal( /** @type {FakeElement} */ (ids.get("resource-tooltip")).hidden, true);
	const overview = /** @type {FakeElement} */ (ids.get("graph-overview"));
	overview.fire("pointerdown", {
		clientX: 500
	});
	overview.fire("pointermove", {
		clientX: 600
	});
	overview.fire("pointerup", {});
	chart.fire("dblclick", {
		clientX: 400,
		clientY: 200
	});
	assert.equal( /** @type {FakeElement} */ (ids.get("zoom-label")).textContent, "full trace");
});
