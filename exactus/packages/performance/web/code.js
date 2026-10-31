"use strict";
/**
 * @typedef {object} TraceEvent
 * @property {string} raw - Raw trace line.
 * @property {string} iso - ISO timestamp text, empty when unavailable.
 * @property {Date | null} time - Parsed timestamp.
 * @property {number} elapsed - Seconds since the trace started.
 * @property {number} gap - Silence before this event.
 * @property {string} message - Message column after the elapsed value.
 * @property {string} trimmed - Message without leading indentation.
 * @property {string} prefix - Text before the first ``:`` or `` — ``.
 * @property {number} index - Event position in the trace.
 * @property {number} depth - Indentation-derived nesting depth.
 * @property {string} thread - Emitting worker thread, ``main`` when untagged.
 * @property {number | null} span - Span identifier of a begin or end line.
 * @property {string} phase - ``begin``, ``end`` or ``point``.
 * @property {number | null} measured - Explicit duration in seconds, if any.
 * @property {number} inferred - Seconds until the lane's next event.
 * @property {string} template - Message with paths and numbers abstracted.
 * @property {string} previous - Message of the preceding event.
 */
/**
 * @typedef {object} ActorStat
 * @property {string} name - Actor label.
 * @property {number} count - Events emitted.
 * @property {number} inferred - Attributed seconds.
 * @property {number} measured - Explicitly measured seconds.
 * @property {number} longest - Largest single interval in seconds.
 * @property {number} p95 - 95th percentile interval in seconds.
 * @property {TraceEvent} peak - Event owning the longest interval.
 */
/**
 * @typedef {object} TemplateStat
 * @property {string} template - Normalized operation text.
 * @property {number} count - Occurrences.
 * @property {number} inferred - Attributed seconds.
 * @property {number} measured - Explicitly measured seconds.
 * @property {TraceEvent} first - First occurrence.
 * @property {TraceEvent} peak - Occurrence with the longest interval.
 */
/**
 * @typedef {object} ResourceSample
 * @property {number} elapsed - Sample time in seconds.
 * @property {number} cpu - CPU percent of one core across the process tree.
 * @property {number} rss - Resident memory in MiB.
 * @property {number} threads - Thread count.
 * @property {number} procs - Process count.
 * @property {number} read - Disk read rate in MiB/s.
 * @property {number} write - Disk write rate in MiB/s.
 */
/**
 * @typedef {object} GraphNode
 * @property {number} id - Position in the node list.
 * @property {TraceEvent} event - Event that opened the node.
 * @property {GraphNode | null} parent - Enclosing node on the same thread.
 * @property {GraphNode[]} children - Directly nested nodes.
 * @property {string} thread - Owning thread.
 * @property {number} level - Nesting level, zero for lane roots.
 * @property {number} start - Start in elapsed seconds.
 * @property {number} end - End in elapsed seconds.
 * @property {number} total - Wall-clock seconds from start to end.
 * @property {number} self - ``total`` minus the children's totals.
 * @property {number | null} measuredEnd - End implied by a measured span.
 */
/**
 * @typedef {object} GraphLane
 * @property {string} name - Thread name.
 * @property {GraphNode[]} roots - Top-level nodes.
 * @property {GraphNode[]} nodes - Every node on the thread.
 * @property {number} maxLevel - Deepest nesting level.
 */
/**
 * @typedef {object} ThreadStat
 * @property {string} name - Thread name.
 * @property {number} count - Events emitted.
 * @property {number} first - First event time in seconds.
 * @property {number} last - Last event time in seconds.
 * @property {number} busy - Attributed seconds.
 */
/**
 * @typedef {object} TraceStage
 * @property {string} name - Stage label without the ``stage:`` prefix.
 * @property {number} start - Stage start in elapsed seconds.
 * @property {number} duration - Stage duration in seconds.
 * @property {TraceEvent} event - Marker event that opened the stage.
 */
/**
 * @typedef {object} TraceTool
 * @property {string} name - Tool identifier.
 * @property {string} label - Human-readable tool name.
 * @property {string[]} lines - Raw trace lines.
 * @property {TraceEvent[]} events - Parsed events.
 * @property {number} duration - Trace duration in seconds.
 * @property {Date} start - First timestamp.
 * @property {Date} end - Last timestamp.
 * @property {TraceEvent[]} gaps - Positive-gap events sorted descending.
 * @property {Map<string, number>} prefixes - Prefix frequency table.
 * @property {TraceStage[]} stages - Inferred stage intervals.
 * @property {ActorStat[]} actors - Attributed time per actor, largest first.
 * @property {TemplateStat[]} templates - Operations by attributed time.
 * @property {TraceEvent[]} slowest - Events by cost, largest first.
 * @property {ThreadStat[]} threads - Per-thread activity, busiest first.
 * @property {ResourceSample[]} samples - CPU, memory and I/O samples.
 * @property {GraphLane[]} lanes - Per-thread execution trees.
 * @property {GraphNode[]} nodes - Every tree node in event order.
 * @property {number} silent - Seconds spent in stalls of 0.25 s or more.
 * @property {number} attributed - Total inferred seconds.
 * @property {string} color - Assigned lane color.
 */
/**
 * @typedef {object} DrillItem
 * @property {string} label - Breadcrumb label.
 * @property {string} [prefix] - Optional event-prefix filter.
 * @property {number} [start] - Optional viewport start in elapsed seconds.
 * @property {number} [end] - Optional viewport end in elapsed seconds.
 */
/**
 * Dashboard element index keyed by element id. Declared members return a
 * concrete element type; other ids resolve through the index signature.
 *
 * @typedef {Record<string, HTMLElement> & {
 *   status: HTMLElement, theme: HTMLElement, search: HTMLInputElement,
 *   drillbar: HTMLElement,
 *   "detail-chart": HTMLCanvasElement,
 *   "detail-tooltip": HTMLElement,
 *   "global-timeline": HTMLCanvasElement,
 *   "zoom-in": HTMLElement, "zoom-out": HTMLElement,
 *   "pan-left": HTMLElement, "pan-right": HTMLElement,
 *   "reset-view": HTMLElement, "zoom-label": HTMLElement,
 *   "kpi-wall": HTMLElement, "kpi-runtime": HTMLElement,
 *   "kpi-events": HTMLElement, "kpi-rate": HTMLElement,
 *   "kpi-gap": HTMLElement, "kpi-gap-tool": HTMLElement,
 *   "kpi-slowest": HTMLElement, "kpi-slowest-time": HTMLElement,
 *   "kpi-silent": HTMLElement, "kpi-silent-note": HTMLElement,
 *   "kpi-hot": HTMLElement, "kpi-hot-note": HTMLElement,
 *   "actor-list": HTMLElement, "actor-total": HTMLElement,
 *   "template-list": HTMLElement, "slow-list": HTMLElement,
 *   "share-chart": HTMLCanvasElement, "worker-chart": HTMLCanvasElement,
 *   "worker-list": HTMLElement, "worker-tooltip": HTMLElement,
 *   "inspect-thread": HTMLElement, "inspect-cost": HTMLElement,
 *   "graph-chart": HTMLCanvasElement, "graph-overview": HTMLCanvasElement,
 *   "graph-scroll": HTMLElement, "graph-crumbs": HTMLElement,
 *   "graph-up": HTMLElement, "graph-in": HTMLElement,
 *   "graph-color": HTMLSelectElement, "graph-tooltip": HTMLElement,
 *   "graph-node": HTMLElement, "graph-measures": HTMLElement,
 *   "graph-children": HTMLElement,
 *   "cpu-chart": HTMLCanvasElement, "mem-chart": HTMLCanvasElement,
 *   "io-chart": HTMLCanvasElement, "resource-tooltip": HTMLElement,
 *   "res-cpu-mean": HTMLElement, "res-cpu-peak": HTMLElement,
 *   "res-rss-peak": HTMLElement, "res-read": HTMLElement,
 *   "res-write": HTMLElement, "res-procs": HTMLElement,
 *   "resource-actors": HTMLElement, "resource-note": HTMLElement,
 *   "tool-list": HTMLElement, "tool-kicker": HTMLElement,
 *   "tool-name": HTMLElement, "tool-summary": HTMLElement,
 *   "gap-list": HTMLElement, "gap-total": HTMLElement,
 *   "prefix-list": HTMLElement, "stage-list": HTMLElement,
 *   "event-count": HTMLElement, "event-list": HTMLElement,
 *   "cursor-readout": HTMLElement, "cursor-rate": HTMLElement,
 *   "cursor-gap": HTMLElement, "cursor-position": HTMLElement,
 *   "cursor-nearby": HTMLElement,
 *   "inspect-index": HTMLElement, "inspect-elapsed": HTMLElement,
 *   "inspect-time": HTMLElement, "inspect-message": HTMLElement
 * }} ObservatoryDom
 */
/**
 * Interactive profiler that renders Exactus step-trace diagnostics in the
 * exported dashboard.
 */
class Observatory {
	/**
	 * Initialize dashboard state and index all identified DOM nodes.
	 */
	constructor() {
		/** @type {Map<string, TraceTool>} */
		this.data = new Map();
		/** @type {string} */
		this.selected = "";
		this.query = "";
		this.cursorIndex = 0;
		this.viewStart = 0;
		this.viewEnd = 1;
		/** @type {DrillItem[]} */
		this.drill = [];
		/** @type {GraphNode | null} */
		this.focus = null;
		/** @type {GraphNode | null} */
		this.selectedNode = null;
		/** @type {{x: number, y: number, w: number, h: number, node: GraphNode}[]} */
		this.graphHits = [];
		this.dragging = false;
		/** @type {number | null} */
		this.hoverIndex = null;
		this.colors = ["#8fc7ff", "#b9f5cf", "#ffbd69", "#d6a5ff", "#ff7b86"];
		/** @type {ObservatoryDom} */
		this.dom = /** @type {ObservatoryDom} */ (
			/** @type {unknown} */
			(Object.fromEntries(
				[...document.querySelectorAll("[id]")].map(node => [node.id, node]), )));
	}
	/**
	 * Load every trace and render the dashboard.
	 *
	 * The ``data.js`` payload wins when present so exported reports also
	 * work over ``file://``; otherwise ``steps.json`` is fetched.
	 *
	 * @throws {Error} When no trace payload can be loaded or parsed.
	 */
	async start() {
		this.bind();
		try {
			const raw = await Observatory.loadSteps();
			Object.entries(raw).forEach(([name, lines], index) => {
				this.data.set(name, this.parse(name, lines, index));
			});
			this.selected = this.data.keys().next().value ?? "";
			this.resetInteractiveState();
			this.render();
		} catch (error) {
			this.dom.status.textContent = `Could not load data.js or steps.json. Serve this folder over HTTP (for example: python -m http.server). ${error}`;
			this.dom.status.classList.add("error");
		}
	}
	/**
	 * Return the embedded ``data.js`` payload or fetch ``steps.json``.
	 *
	 * @returns {Promise<Record<string, string[]>>} Tool trace lines.
	 * @throws {Error} When ``steps.json`` cannot be fetched or parsed.
	 */
	static loadSteps = async () => {
		const embedded = /** @type {{__PERFORMANCE_STEPS__?: Record<string, string[]>}} */ (window).__PERFORMANCE_STEPS__;
		if (embedded) return embedded;
		const response = await fetch("steps.json", {
			cache: "no-store"
		});
		if (!response.ok) throw new Error(`steps.json: HTTP ${response.status}`);
		return /** @type {Record<string, string[]>} */ (await response.json());
	};
	/**
	 * Attach theme, search, mode, zoom, and chart interaction listeners.
	 */
	bind() {
		this.dom.theme.addEventListener("click", () => document.documentElement.classList.toggle("light"));
		this.dom.search.addEventListener("input", event => {
			this.query = ( /** @type {HTMLInputElement | null} */ (event.target)?.value ?? "").toLowerCase().trim();
			this.renderDetail();
		});
		document.querySelectorAll(".mode").forEach(button => {
			button.addEventListener("click", () => {
				document.querySelectorAll(".mode").forEach(item => {
					item.classList.toggle("active", item === button);
				});
				document.querySelectorAll(".view").forEach(view => {
					view.classList.remove("active");
				});
				const mode = /** @type {HTMLElement} */ (button).getAttribute("data-mode") ?? "";
				this.dom[`${mode}-view`]?.classList.add("active");
				const tool = this.data.get(this.selected);
				if (tool) this.drawViews(tool);
			});
		});
		window.addEventListener("resize", () => {
			this.drawGlobal();
			const tool = this.data.get(this.selected);
			if (tool) this.drawViews(tool);
		});
		this.dom["zoom-in"].addEventListener("click", () => this.zoom(.55));
		this.dom["zoom-out"].addEventListener("click", () => this.zoom(1.8));
		this.dom["pan-left"].addEventListener("click", () => this.pan(-.25));
		this.dom["pan-right"].addEventListener("click", () => this.pan(.25));
		this.dom["reset-view"].addEventListener("click", () => {
			this.viewStart = 0;
			this.viewEnd = 1;
			this.drill = [];
			this.renderDetail();
		});
		this.bindViews();
		const chart = this.dom["detail-chart"];
		chart.addEventListener("pointerdown", event => {
			this.dragging = true;
			chart.closest(".timeline-shell")?.classList.add("scrubbing");
			chart.setPointerCapture(event.pointerId);
			this.scrub(event);
		});
		chart.addEventListener("pointermove", event => {
			this.hover(event);
			if (this.dragging) this.scrub(event);
		});
		chart.addEventListener("pointerup", event => {
			this.dragging = false;
			chart.closest(".timeline-shell")?.classList.remove("scrubbing");
			if (chart.hasPointerCapture(event.pointerId)) chart.releasePointerCapture(event.pointerId);
		});
		chart.addEventListener("pointercancel", () => {
			this.dragging = false;
			chart.closest(".timeline-shell")?.classList.remove("scrubbing");
		});
		chart.addEventListener("pointerleave", () => {
			this.hoverIndex = null;
			this.dom["detail-tooltip"].hidden = true;
			this.drawDetail();
		});
		chart.addEventListener("click", event => this.scrub(event));
		chart.addEventListener("wheel", event => {
			event.preventDefault();
			this.zoom(event.deltaY < 0 ? .72 : 1.38, this.pointerFraction(event));
		}, {
			passive: false
		});
		chart.addEventListener("keydown", event => {
			if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
			event.preventDefault();
			this.stepCursor((event.key === "ArrowRight" ? 1 : -1) * (event.shiftKey ? 10 : 1));
		});
	}
	/**
	 * Wire the graph, hotspot, worker, and resource canvases.
	 */
	bindViews() {
		const current = () => this.data.get(this.selected);
		["share-chart", "worker-chart"].forEach(id => {
			const canvas = this.dom[id];
			if (canvas) this.attachViewport(canvas, id === "share-chart" ? 8 : 120);
		});
		const graph = this.dom["graph-chart"];
		if (graph) {
			this.attachViewport(graph, 120, {
				tap: event => {
					const tool = current();
					if (tool) this.selectNode(tool, this.graphNodeAt(event), false);
				},
				hover: event => {
					const node = this.graphNodeAt(event);
					const tip = this.dom["graph-tooltip"];
					const tool = current();
					if (!node || !tool) {
						tip.hidden = true;
						return;
					}
					const rect = graph.getBoundingClientRect();
					tip.textContent = `${node.event.trimmed}\ntotal ${Observatory.duration(node.total)} · self ${Observatory.duration(node.self)} · ${(node.total / Math.max(tool.duration, .001) * 100).toFixed(1)}% of run\n${node.thread} · ${node.children.length} children`;
					tip.style.left = `${Math.max(8, Math.min(rect.width - 360, event.clientX - rect.left + 12))}px`;
					tip.style.top = `${Math.max(8, event.clientY - rect.top + 14)}px`;
					tip.hidden = false;
				},
				leave: () => {
					this.dom["graph-tooltip"].hidden = true;
				}
			});
			graph.addEventListener("dblclick", event => {
				const tool = current();
				const node = this.graphNodeAt(event);
				if (tool && node) this.selectNode(tool, node, true);
			});
			graph.addEventListener("keydown", event => {
				const tool = current();
				if (!tool) return;
				if (event.key === "Escape" || event.key === "Backspace") {
					event.preventDefault();
					this.focusUp(tool);
				} else if (event.key === "Enter" && this.selectedNode) {
					event.preventDefault();
					this.selectNode(tool, this.selectedNode, true);
				}
			});
		}
		this.dom["graph-up"]?.addEventListener("click", () => {
			const tool = current();
			if (tool) this.focusUp(tool);
		});
		this.dom["graph-in"]?.addEventListener("click", () => {
			const tool = current();
			if (tool && this.selectedNode) this.selectNode(tool, this.selectedNode, true);
		});
		this.dom["graph-color"]?.addEventListener("change", () => {
			const tool = current();
			if (tool) this.drawGraph(tool);
		});
		const overview = this.dom["graph-overview"];
		if (overview) {
			/** @type {(event: MouseEvent) => void} */
			const jump = event => {
				const tool = current();
				if (!tool) return;
				const width = this.viewEnd - this.viewStart;
				const center = Observatory.fractionAt(overview, event, 120);
				this.viewStart = Math.max(0, Math.min(1 - width, center - width / 2));
				this.viewEnd = this.viewStart + width;
				this.drawViews(tool);
				this.renderZoomLabel(tool);
			};
			let dragging = false;
			overview.addEventListener("pointerdown", event => {
				dragging = true;
				jump(event);
			});
			overview.addEventListener("pointermove", event => {
				if (dragging) jump(event);
			});
			overview.addEventListener("pointerup", () => {
				dragging = false;
			});
		}
		["cpu-chart", "mem-chart", "io-chart"].forEach(id => {
			const canvas = this.dom[id];
			if (!canvas) return;
			this.attachViewport(canvas, 120, {
				hover: event => {
					const tool = current();
					if (!tool?.samples.length) return;
					const at = this.timeAt(tool, canvas, event, 120);
					const sample = tool.samples.find(item => item.elapsed >= at) ?? tool.samples.at(-1);
					const running = tool.events.filter(item => item.elapsed <= at && item.thread === "main").at(-1);
					const tip = this.dom["resource-tooltip"];
					if (!sample) return;
					tip.textContent = `+${sample.elapsed.toFixed(2)}s  cpu ${sample.cpu.toFixed(0)}%  rss ${sample.rss.toFixed(0)} MiB\nread ${sample.read.toFixed(2)} · write ${sample.write.toFixed(2)} MiB/s · ${sample.procs} procs · ${sample.threads} threads${running ? `\nrunning: ${running.trimmed}` : ""}`;
					const rect = (canvas.closest(".timeline-shell") ?? canvas).getBoundingClientRect();
					tip.style.left = `${Math.max(8, Math.min(rect.width - 380, event.clientX - rect.left + 12))}px`;
					tip.style.top = `${Math.max(8, event.clientY - rect.top - 60)}px`;
					tip.hidden = false;
				},
				leave: () => {
					this.dom["resource-tooltip"].hidden = true;
				}
			});
		});
	}
	/**
	 * Parse one trace into events, gaps, prefixes, and stages.
	 *
	 * @param {string} name - Tool name owning the trace.
	 * @param {string[]} lines - Raw ``steps.txt`` lines.
	 * @param {number} index - Trace ordinal used to pick a lane color.
	 * @returns {TraceTool} Parsed tool record.
	 */
	parse(name, lines, index) {
		const regex = /^(\S+) \+\s*([0-9.]+)s (.*)$/;
		const samples = /** @type {ResourceSample[]} */ ([]);
		const kept = /** @type {{raw: string, match: RegExpMatchArray | null}[]} */ ([]);
		lines.forEach(raw => {
			const match = raw.match(regex);
			if (match?.[3]?.startsWith("~sample ")) {
				samples.push(Observatory.sample(Number(match[2]), match[3]));
				return;
			}
			kept.push({
				raw,
				match
			});
		});
		let previousElapsed = 0;
		const events = /** @type {TraceEvent[]} */ (kept.map(({
			raw,
			match
		}, i) => {
			const iso = match?.[1] ?? "";
			const elapsed = Number(match?.[2] ?? 0);
			const decoded = Observatory.decode(match?.[3] ?? raw);
			const previous = i ? previousElapsed : 0;
			previousElapsed = elapsed;
			const trimmed = decoded.message.trim();
			const prefix = trimmed.split(/:| — /, 1)[0] ?? "";
			const lead = Math.max(0, decoded.message.search(/[^ ]/));
			return {
				raw,
				iso,
				time: iso ? new Date(iso) : null,
				elapsed,
				gap: Math.max(0, elapsed - previous),
				message: decoded.message,
				trimmed,
				prefix,
				index: i,
				depth: Math.floor(lead / 2),
				thread: decoded.thread,
				span: decoded.span,
				phase: decoded.phase,
				measured: decoded.measured,
				inferred: 0,
				template: Observatory.template(trimmed),
				previous: ""
			};
		}));
		events.forEach((event, position) => {
			event.previous = events[position - 1]?.trimmed ?? "";
		});
		Observatory.attribute(events);
		const valid = events.filter(event => event.time);
		const duration = events.at(-1)?.elapsed ?? 0;
		const start = valid[0]?.time ?? new Date(0);
		const end = valid.at(-1)?.time ?? start;
		const gaps = events.slice(1).filter(event => event.gap > 0).sort((a, b) => b.gap - a.gap);
		const prefixes = /** @type {Map<string, number>} */ (new Map());
		events.forEach(event => {
			prefixes.set(event.prefix, (prefixes.get(event.prefix) ?? 0) + 1);
		});
		const stages = Observatory.stages(events, duration);
		return {
			name,
			label: name.replaceAll("_", " "),
			lines,
			events,
			duration,
			start,
			end,
			gaps,
			prefixes,
			stages,
			...Observatory.aggregate(events),
			samples,
			...Observatory.tree(events, duration),
			color: this.colors[index % this.colors.length] ?? "#8fc7ff"
		};
	}
	/**
	 * Split a message column into text and ``@key=value`` trailers.
	 *
	 * @param {string} message - Message column after the elapsed value.
	 * @returns {{message: string, thread: string, span: number | null, phase: string, measured: number | null}} Decoded fields.
	 */
	static decode = message => {
		let text = message;
		/** @type {Record<string, string>} */
		const trailers = {};
		for (;;) {
			const found = /\s@([a-z_]+)=(\S+)\s*$/.exec(text);
			if (!found) break;
			trailers[found[1] ?? ""] ??= found[2] ?? "";
			text = text.slice(0, found.index);
		}
		const trailer = (/** @type {string} */ key) => trailers[key];
		const span = /^\d+$/.test(trailer("span") ?? "") ? Number(trailer("span")) : null;
		const explicit = /^\d+(?:\.\d+)?s$/.test(trailer("dur") ?? "") ? Number.parseFloat(trailer("dur") ?? "") : null;
		const phrases = [...text.matchAll(/(?:\bin |, |\()(\d+(?:\.\d+)?)(ms|s)\b/g)];
		const last = phrases.at(-1);
		const embedded = last ? Number(last[1]) / (last[2] === "ms" ? 1000 : 1) : null;
		return {
			message: text,
			thread: trailer("thread") ?? "main",
			span,
			phase: span === null ? "point" : "dur" in trailers ? "end" : "begin",
			measured: explicit ?? embedded
		};
	};
	/**
	 * Decode one ``~sample`` resource line.
	 *
	 * @param {number} elapsed - Sample time in seconds.
	 * @param {string} body - Message column starting with ``~sample``.
	 * @returns {ResourceSample} Resource sample.
	 */
	static sample = (elapsed, body) => {
		/** @type {Record<string, number>} */
		const fields = {};
		body.split(/\s+/).slice(1).forEach(part => {
			const [key, value] = part.split("=");
			if (key && value !== undefined && Number.isFinite(Number(value))) fields[key] = Number(value);
		});
		const field = (/** @type {string} */ key) => fields[key] ?? 0;
		return {
			elapsed,
			cpu: field("cpu"),
			rss: field("rss"),
			threads: field("threads"),
			procs: field("procs"),
			read: field("read"),
			write: field("write")
		};
	};
	/**
	 * Build each thread's execution tree from depth and span information.
	 *
	 * A node runs from its event to the next event on the same thread at
	 * the same or a shallower depth (or to its measured span end), so its
	 * children nest inside it and ``self`` is what is left unexplained.
	 *
	 * @param {TraceEvent[]} events - Parsed events in execution order.
	 * @param {number} duration - Trace duration in seconds.
	 * @returns {{lanes: GraphLane[], nodes: GraphNode[]}} Trees per thread.
	 */
	static tree = (events, duration) => {
		const lanes = /** @type {Map<string, GraphLane & {stack: GraphNode[], last: number}>} */ (new Map());
		const nodes = /** @type {GraphNode[]} */ ([]);
		/** @type {(lane: GraphLane & {stack: GraphNode[]}, depth: number, at: number) => void} */
		const close = (lane, depth, at) => {
			while (lane.stack.length && (lane.stack.at(-1)?.event.depth ?? -1) >= depth) {
				const node = /** @type {GraphNode} */ (lane.stack.pop());
				node.end = Math.max(node.start, node.measuredEnd ?? at);
			}
		};
		events.forEach(event => {
			if (event.phase === "end") return;
			let lane = lanes.get(event.thread);
			if (!lane) {
				lane = {
					name: event.thread,
					roots: [],
					nodes: [],
					maxLevel: 0,
					stack: [],
					last: 0
				};
				lanes.set(event.thread, lane);
			}
			close(lane, event.depth, event.elapsed);
			const parent = lane.stack.at(-1) ?? null;
			/** @type {GraphNode} */
			const node = {
				id: nodes.length,
				event,
				parent,
				children: [],
				thread: event.thread,
				level: parent ? parent.level + 1 : 0,
				start: event.elapsed,
				end: event.elapsed,
				total: 0,
				self: 0,
				measuredEnd: event.phase === "begin" && event.measured !== null ? event.elapsed + event.measured : null
			};
			if (parent) parent.children.push(node);
			else lane.roots.push(node);
			lane.stack.push(node);
			lane.nodes.push(node);
			lane.maxLevel = Math.max(lane.maxLevel, node.level);
			lane.last = event.elapsed;
			nodes.push(node);
		});
		lanes.forEach(lane => {
			close(lane, -1, lane.name === "main" ? Math.max(duration, lane.last) : lane.last);
		});
		nodes.forEach(node => {
			node.total = Math.max(0, node.end - node.start);
		});
		nodes.forEach(node => {
			node.self = Math.max(0, node.total - node.children.reduce((sum, child) => sum + child.total, 0));
		});
		return {
			lanes: [...lanes.values()].sort((a, b) => a.name === "main" ? -1 : b.name === "main" ? 1 : b.nodes.length - a.nodes.length),
			nodes
		};
	};
	/**
	 * Integrate resource samples over an interval.
	 *
	 * Each sample describes the period since the previous one.
	 *
	 * @param {ResourceSample[]} samples - Samples in time order.
	 * @param {number} start - Interval start in seconds.
	 * @param {number} end - Interval end in seconds.
	 * @returns {{cpu: number, rss: number, read: number, write: number, covered: boolean}} Averages, peak memory and totals.
	 */
	static resourcesIn = (samples, start, end) => {
		let weight = 0;
		let cpu = 0;
		let rss = 0;
		let read = 0;
		let write = 0;
		let previous = 0;
		samples.forEach(sample => {
			const from = Math.max(previous, start);
			const to = Math.min(sample.elapsed, end);
			previous = sample.elapsed;
			if (to <= from) return;
			const width = to - from;
			weight += width;
			cpu += sample.cpu * width;
			read += sample.read * width;
			write += sample.write * width;
			rss = Math.max(rss, sample.rss);
		});
		return {
			cpu: weight > 0 ? cpu / weight : 0,
			rss,
			read,
			write,
			covered: weight > 0
		};
	};
	/**
	 * Abstract paths and numbers so repeated operations group together.
	 *
	 * @param {string} text - Message without indentation or trailers.
	 * @returns {string} Normalized operation text.
	 */
	static template = text => text.replace(/(?:[A-Za-z]:)?(?:\.{0,2}\/)?[\w.@+-]+(?:\/[\w.@+-]+)+\/?/g, "<path>").replace(/\d+(?:\.\d+)?/g, "#");
	/**
	 * Attribute each event the time until its thread's next event and copy
	 * span durations onto begin lines.
	 *
	 * @param {TraceEvent[]} events - Parsed events in execution order.
	 */
	static attribute = events => {
		const lanes = /** @type {Map<string, TraceEvent>} */ (new Map());
		const spans = /** @type {Map<number, number>} */ (new Map());
		events.forEach(event => {
			const before = lanes.get(event.thread);
			if (before) before.inferred = Math.max(0, event.elapsed - before.elapsed);
			lanes.set(event.thread, event);
			if (event.phase === "end" && event.span !== null && event.measured !== null) spans.set(event.span, event.measured);
		});
		events.forEach(event => {
			if (event.phase === "begin" && event.span !== null && spans.has(event.span)) event.measured = spans.get(event.span) ?? null;
		});
	};
	/**
	 * Cost of one event: its measured duration when known, else inferred.
	 *
	 * @param {TraceEvent} event - Parsed event.
	 * @returns {number} Cost in seconds.
	 */
	static cost = event => event.phase !== "end" && event.measured !== null ? event.measured : event.inferred;
	/**
	 * Build actor, operation, thread, and slowest-step rankings.
	 *
	 * @param {TraceEvent[]} events - Parsed events with attribution.
	 * @returns {{actors: ActorStat[], templates: TemplateStat[], slowest: TraceEvent[], threads: ThreadStat[], silent: number, attributed: number}} Aggregates.
	 */
	static aggregate = events => {
		const actors = /** @type {Map<string, TraceEvent[]>} */ (new Map());
		const templates = /** @type {Map<string, TraceEvent[]>} */ (new Map());
		const threads = /** @type {Map<string, TraceEvent[]>} */ (new Map());
		events.forEach(event => {
			const key = event.prefix || "unclassified";
			actors.set(key, [...(actors.get(key) ?? []), event]);
			templates.set(event.template, [...(templates.get(event.template) ?? []), event]);
			threads.set(event.thread, [...(threads.get(event.thread) ?? []), event]);
		});
		const sum = (/** @type {TraceEvent[]} */ items, /** @type {(event: TraceEvent) => number} */ pick) => items.reduce((total, item) => total + pick(item), 0);
		const peak = (/** @type {TraceEvent[]} */ items) => items.reduce((best, item) => item.inferred > best.inferred ? item : best, /** @type {TraceEvent} */ (items[0]));
		const measured = (/** @type {TraceEvent} */ event) => event.phase !== "end" ? event.measured ?? 0 : 0;
		return {
			actors: [...actors].map(([name, items]) => {
				const sorted = items.map(item => item.inferred).sort((a, b) => a - b);
				return {
					name,
					count: items.length,
					inferred: sum(items, item => item.inferred),
					measured: sum(items, measured),
					longest: peak(items).inferred,
					p95: sorted[Math.max(0, Math.ceil(.95 * sorted.length) - 1)] ?? 0,
					peak: peak(items)
				};
			}).sort((a, b) => b.inferred - a.inferred),
			templates: [...templates].map(([template, items]) => ({
				template,
				count: items.length,
				inferred: sum(items, item => item.inferred),
				measured: sum(items, measured),
				first: /** @type {TraceEvent} */ (items[0]),
				peak: peak(items)
			})).sort((a, b) => b.inferred - a.inferred),
			slowest: [...events].sort((a, b) => Observatory.cost(b) - Observatory.cost(a)).slice(0, 25),
			threads: [...threads].map(([name, items]) => ({
				name,
				count: items.length,
				first: items[0]?.elapsed ?? 0,
				last: items.at(-1)?.elapsed ?? 0,
				busy: sum(items, item => item.inferred)
			})).sort((a, b) => b.busy - a.busy),
			silent: events.slice(1).filter(event => event.gap >= .25).reduce((total, event) => total + event.gap, 0),
			attributed: sum(events, item => item.inferred)
		};
	};
	/**
	 * Derive stage intervals from ``stage:`` marker events.
	 *
	 * @param {TraceEvent[]} events - Parsed events in execution order.
	 * @param {number} duration - Total trace duration in seconds.
	 * @returns {TraceStage[]} Stage rows ordered by start time.
	 */
	static stages = (events, duration) => {
		const starts = events.filter(event => /^\s*stage:/.test(event.message));
		return starts.map((event, index) => ({
			name: event.trimmed.replace(/^stage:\s*/, ""),
			start: event.elapsed,
			duration: Math.max(0, (starts[index + 1]?.elapsed ?? duration) - event.elapsed),
			event
		}));
	};
	/**
	 * Re-render the KPI strip, tool list, detail pane, and global timeline.
	 */
	render() {
		this.dom.status.classList.remove("error");
		this.renderKpis();
		this.renderTools();
		this.renderDetail();
		this.drawGlobal();
	}
	/**
	 * Populate the aggregate KPI cards across all loaded traces.
	 */
	renderKpis() {
		const tools = [...this.data.values()];
		const minStart = new Date(Math.min(...tools.map(tool => tool.start.getTime())));
		const maxEnd = new Date(Math.max(...tools.map(tool => tool.end.getTime())));
		const wall = (maxEnd.getTime() - minStart.getTime()) / 1000;
		const runtime = tools.reduce((sum, tool) => sum + tool.duration, 0);
		const events = tools.reduce((sum, tool) => sum + tool.events.length, 0);
		const largest = tools.flatMap(tool => tool.gaps.map(gap => ({
			tool,
			gap
		}))).sort((a, b) => b.gap.gap - a.gap.gap)[0];
		const slowest = [...tools].sort((a, b) => b.duration - a.duration)[0];
		this.dom["kpi-wall"].textContent = Observatory.duration(wall);
		this.dom["kpi-runtime"].textContent = Observatory.duration(runtime);
		this.dom["kpi-events"].textContent = events.toLocaleString();
		this.dom["kpi-rate"].textContent = `${(events / Math.max(wall, 0.001)).toFixed(1)} events/s wall rate`;
		this.dom["kpi-gap"].textContent = Observatory.duration(largest?.gap.gap ?? 0);
		this.dom["kpi-gap-tool"].textContent = largest ? `${largest.tool.label} · ${largest.gap.trimmed.slice(0, 48)}` : "—";
		this.dom["kpi-slowest"].textContent = slowest?.label ?? "—";
		this.dom["kpi-slowest-time"].textContent = slowest ? `${Observatory.duration(slowest.duration)} trace runtime` : "—";
		const silent = tools.reduce((sum, tool) => sum + tool.silent, 0);
		this.dom["kpi-silent"].textContent = Observatory.duration(silent);
		this.dom["kpi-silent-note"].textContent = runtime > 0 ? `${(silent / runtime * 100).toFixed(0)}% of tool runtime in stalls ≥ 250 ms` : "—";
		const hot = tools.flatMap(tool => tool.actors.slice(0, 1).map(actor => ({
			tool,
			actor
		}))).sort((a, b) => b.actor.inferred - a.actor.inferred)[0];
		this.dom["kpi-hot"].textContent = hot ? hot.actor.name : "—";
		this.dom["kpi-hot-note"].textContent = hot ? `${hot.tool.label} · ${Observatory.duration(hot.actor.inferred)} (${(hot.actor.inferred / Math.max(hot.tool.attributed, .001) * 100).toFixed(0)}%)` : "—";
	}
	/**
	 * Render the selectable tool cards ordered by trace duration.
	 */
	renderTools() {
		this.dom["tool-list"].replaceChildren();
		[...this.data.values()].sort((a, b) => b.duration - a.duration).forEach(tool => {
			const node = this.clone("tool-template");
			const button = /** @type {HTMLElement} */ (node.querySelector(".tool-card"));
			button.classList.toggle("active", tool.name === this.selected);
			/** @type {HTMLElement} */
			(button.querySelector(".tool-marker")).style.background = tool.color;
			Observatory.field(node, "name", tool.label);
			Observatory.field(node, "meta", `${tool.events.length.toLocaleString()} events · ${tool.stages.length} stages`);
			Observatory.field(node, "duration", Observatory.duration(tool.duration));
			button.addEventListener("click", () => {
				this.selected = tool.name;
				this.resetInteractiveState();
				this.renderTools();
				this.renderDetail();
			});
			this.dom["tool-list"].append(node);
		});
	}
	/**
	 * Re-render every detail section for the selected tool.
	 */
	renderDetail() {
		const tool = this.data.get(this.selected);
		if (!tool) return;
		this.dom["tool-kicker"].textContent = `${tool.events.length.toLocaleString()} EVENTS · ${tool.stages.length} STAGES`;
		this.dom["tool-name"].textContent = tool.label;
		this.dom["tool-summary"].textContent = `${Observatory.duration(tool.duration)} total trace · ${Observatory.duration(tool.gaps[0]?.gap ?? 0)} largest silent interval · ${(tool.events.length / Math.max(tool.duration, .001)).toFixed(1)} events/s`;
		this.renderGaps(tool);
		this.renderPrefixes(tool);
		this.renderStages(tool);
		this.renderEvents(tool);
		this.renderHotspots(tool);
		this.renderWorkers(tool);
		this.renderGraphPanel(tool);
		this.renderDrillbar();
		this.updateCursor(tool);
		this.drawViews(tool);
	}
	/**
	 * Render the largest silent-interval ranking rows.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 */
	renderGaps(tool) {
		const list = tool.gaps.filter(event => this.matches(event.message)).slice(0, 12);
		const max = list[0]?.gap ?? 1;
		this.dom["gap-list"].replaceChildren();
		this.dom["gap-total"].textContent = `${tool.gaps.filter(item => item.gap >= .25).length} stalls ≥ 250 ms · ${Observatory.duration(tool.silent)} with no step logged`;
		list.forEach((event, index) => {
			const node = this.clone("gap-template");
			Observatory.field(node, "rank", String(index + 1).padStart(2, "0"));
			Observatory.field(node, "title", event.previous ? `${event.previous}  →  ${event.trimmed}` : event.trimmed);
			Observatory.field(node, "detail", `silent after the first step, before the second · at +${event.elapsed.toFixed(3)}s · event ${event.index + 1}${event.thread === "main" ? "" : ` · ${event.thread}`}`);
			Observatory.field(node, "value", Observatory.duration(event.gap));
			Observatory.fieldNode(node, "bar").style.width = `${Math.max(2, event.gap / max * 100)}%`;
			/** @type {HTMLElement} */
			(node.querySelector(".rank-row")).addEventListener("click", () => {
				const radius = Math.max(event.gap * 1.5, tool.duration * .015);
				this.drillTo(tool, Math.max(0, event.elapsed - event.gap - radius * .15), Math.min(tool.duration, event.elapsed + radius * .15), `gap ${Observatory.duration(event.gap)}`);
				this.cursorIndex = event.index;
				this.renderDetail();
			});
			this.dom["gap-list"].append(node);
		});
	}
	/**
	 * Render the event-prefix frequency ranking rows.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 */
	renderPrefixes(tool) {
		const rows = [...tool.prefixes].filter(([prefix]) => this.matches(prefix)).sort((a, b) => b[1] - a[1]).slice(0, 12);
		const max = rows[0]?.[1] ?? 1;
		this.dom["prefix-list"].replaceChildren();
		rows.forEach(([prefix, count], index) => {
			const node = this.clone("prefix-template");
			Observatory.field(node, "rank", String(index + 1).padStart(2, "0"));
			Observatory.field(node, "title", prefix || "unclassified");
			Observatory.field(node, "detail", `${(count / tool.events.length * 100).toFixed(1)}% of this trace`);
			Observatory.field(node, "value", count.toLocaleString());
			Observatory.fieldNode(node, "bar").style.width = `${Math.max(2, count / max * 100)}%`;
			/** @type {HTMLElement} */
			(node.querySelector(".rank-row")).addEventListener("click", () => {
				this.focusPrefix(tool, prefix);
			});
			this.dom["prefix-list"].append(node);
		});
	}
	/**
	 * Render the stage duration ranking rows.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 */
	renderStages(tool) {
		const rows = tool.stages.filter(stage => this.matches(stage.name));
		const max = Math.max(...rows.map(stage => stage.duration), 1);
		this.dom["stage-list"].replaceChildren();
		rows.forEach(stage => {
			const node = this.clone("stage-template");
			Observatory.field(node, "duration", Observatory.duration(stage.duration));
			Observatory.field(node, "start", `+${stage.start.toFixed(3)}s`);
			Observatory.field(node, "name", stage.name);
			Observatory.field(node, "detail", `${(stage.duration / Math.max(tool.duration, .001) * 100).toFixed(1)}% of tool runtime`);
			Observatory.fieldNode(node, "bar").style.width = `${Math.max(2, stage.duration / max * 100)}%`;
			/** @type {HTMLElement} */
			(node.querySelector(".stage-row")).addEventListener("click", () => {
				this.drillTo(tool, stage.start, stage.start + stage.duration, stage.name);
				this.cursorIndex = stage.event.index;
				this.renderDetail();
			});
			this.dom["stage-list"].append(node);
		});
	}
	/**
	 * Render the filtered, capped event list rows.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 */
	renderEvents(tool) {
		const rows = tool.events.filter(event => this.matches(event.message));
		this.dom["event-count"].textContent = `${rows.length.toLocaleString()} / ${tool.events.length.toLocaleString()}`;
		this.dom["event-list"].replaceChildren();
		rows.slice(0, 2500).forEach(event => {
			const node = this.clone("event-template");
			Observatory.field(node, "time", event.time ? event.time.toISOString().slice(11, 23) : "—");
			Observatory.field(node, "delta", `+${event.elapsed.toFixed(3)}s`);
			Observatory.field(node, "message", event.message);
			const row = /** @type {HTMLElement} */ (node.querySelector(".event-row"));
			row.setAttribute("data-index", String(event.index));
			row.classList.toggle("cursor-event", event.index === this.cursorIndex);
			row.classList.toggle("near-cursor", Math.abs(event.index - this.cursorIndex) <= 2);
			row.addEventListener("click", () => {
				this.cursorIndex = event.index;
				this.updateCursor(tool);
				this.drawDetail();
				this.renderEvents(tool);
			});
			this.dom["event-list"].append(node);
		});
	}
	/**
	 * Zoom the viewport onto every event of one actor prefix.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 * @param {string} prefix - Actor prefix to isolate.
	 */
	focusPrefix(tool, prefix) {
		this.drill.push({
			label: prefix || "unclassified",
			prefix
		});
		const hits = tool.events.filter(event => event.prefix === prefix);
		if (hits.length) {
			this.viewStart = Math.max(0, (hits[0]?.elapsed ?? 0) / Math.max(tool.duration, .001) - .02);
			this.viewEnd = Math.min(1, (hits.at(-1)?.elapsed ?? 0) / Math.max(tool.duration, .001) + .02);
			this.cursorIndex = hits[0]?.index ?? 0;
		}
		this.renderDetail();
	}
	/**
	 * Zoom onto one event's interval and put the cursor on it.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 * @param {TraceEvent} event - Event to inspect.
	 * @param {string} label - Breadcrumb label.
	 */
	focusEvent(tool, event, label) {
		const span = Math.max(Observatory.cost(event), tool.duration * .01);
		this.drillTo(tool, Math.max(0, event.elapsed - span * .5), Math.min(tool.duration, event.elapsed + span * 1.5), label);
		this.cursorIndex = event.index;
		this.renderDetail();
	}
	/**
	 * Append one ranking row built from the shared rank template.
	 *
	 * @param {HTMLElement} list - Destination list.
	 * @param {{rank: number, title: string, detail: string, value: string, fraction: number, click: () => void}} row - Row content.
	 */
	appendRank(list, row) {
		const node = this.clone("gap-template");
		Observatory.field(node, "rank", String(row.rank).padStart(2, "0"));
		Observatory.field(node, "title", row.title);
		Observatory.field(node, "detail", row.detail);
		Observatory.field(node, "value", row.value);
		Observatory.fieldNode(node, "bar").style.width = `${Math.max(2, row.fraction * 100)}%`;
		/** @type {HTMLElement} */
		(node.querySelector(".rank-row")).addEventListener("click", row.click);
		list.append(node);
	}
	/**
	 * Render where-the-time-goes rankings: actors, operations, slow steps.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 */
	renderHotspots(tool) {
		const total = Math.max(tool.attributed, .001);
		const actors = tool.actors.filter(actor => this.matches(actor.name)).slice(0, 14);
		this.dom["actor-list"].replaceChildren();
		this.dom["actor-total"].textContent = `${tool.actors.length} actors · shares of ${Observatory.duration(tool.attributed)} thread time`;
		actors.forEach((actor, index) => {
			this.appendRank(this.dom["actor-list"], {
				rank: index + 1,
				title: actor.name,
				detail: `${actor.count.toLocaleString()} steps · longest ${Observatory.duration(actor.longest)} · p95 ${Observatory.duration(actor.p95)}${actor.measured > 0 ? ` · ${Observatory.duration(actor.measured)} measured` : ""}`,
				value: `${(actor.inferred / total * 100).toFixed(1)}% · ${Observatory.duration(actor.inferred)}`,
				fraction: actor.inferred / Math.max(actors[0]?.inferred ?? 1, .001),
				click: () => this.focusPrefix(tool, actor.name === "unclassified" ? "" : actor.name)
			});
		});
		const templates = tool.templates.filter(item => this.matches(item.template)).slice(0, 14);
		this.dom["template-list"].replaceChildren();
		templates.forEach((item, index) => {
			this.appendRank(this.dom["template-list"], {
				rank: index + 1,
				title: item.template,
				detail: `${item.count.toLocaleString()}× · avg ${Observatory.duration(item.inferred / item.count)} · worst ${Observatory.duration(item.peak.inferred)}`,
				value: Observatory.duration(item.inferred),
				fraction: item.inferred / Math.max(templates[0]?.inferred ?? 1, .001),
				click: () => this.focusEvent(tool, item.peak, item.template.slice(0, 40))
			});
		});
		const slow = tool.slowest.filter(event => this.matches(event.message)).slice(0, 14);
		this.dom["slow-list"].replaceChildren();
		slow.forEach((event, index) => {
			this.appendRank(this.dom["slow-list"], {
				rank: index + 1,
				title: event.trimmed,
				detail: `${event.phase !== "end" && event.measured !== null ? "measured" : "until next event"} · at +${event.elapsed.toFixed(3)}s${event.thread === "main" ? "" : ` · ${event.thread}`}`,
				value: Observatory.duration(Observatory.cost(event)),
				fraction: Observatory.cost(event) / Math.max(Observatory.cost(slow[0] ?? event), .001),
				click: () => this.focusEvent(tool, event, event.trimmed.slice(0, 40))
			});
		});
	}
	/**
	 * Render the per-thread summary rows.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 */
	renderWorkers(tool) {
		const list = this.dom["worker-list"];
		list.replaceChildren();
		const busiest = Math.max(tool.threads[0]?.busy ?? 1, .001);
		tool.threads.filter(thread => this.matches(thread.name)).forEach((thread, index) => {
			this.appendRank(list, {
				rank: index + 1,
				title: thread.name,
				detail: `${thread.count.toLocaleString()} steps · active +${thread.first.toFixed(2)}s → +${thread.last.toFixed(2)}s · ${(thread.busy / Math.max(tool.duration, .001) * 100).toFixed(0)}% of runtime`,
				value: Observatory.duration(thread.busy),
				fraction: thread.busy / busiest,
				click: () => {
					this.drillTo(tool, thread.first, Math.max(thread.last, thread.first + .001), thread.name);
					this.renderDetail();
				}
			});
		});
	}
	/**
	 * Pick a stable color for an actor.
	 *
	 * @param {string} name - Actor label.
	 * @returns {string} CSS color.
	 */
	static actorColor = name => `hsl(${Math.abs(Observatory.hash(name)) % 360} 62% 62%)`;
	/**
	 * Draw the stacked "where the time goes over time" chart.
	 *
	 * Each event's attributed interval is spread over the time slices it
	 * covers, stacked by the six heaviest actors plus an "other" band.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 */
	drawShare(tool) {
		const canvas = this.dom["share-chart"];
		if (!canvas) return;
		const ratio = window.devicePixelRatio || 1;
		const width = Math.max(320, canvas.clientWidth);
		const height = 220;
		canvas.width = width * ratio;
		canvas.height = height * ratio;
		const ctx = canvas.getContext("2d");
		if (!ctx) return;
		ctx.scale(ratio, ratio);
		ctx.clearRect(0, 0, width, height);
		const css = getComputedStyle(document.documentElement);
		const left = 8;
		const bins = 80;
		const origin = tool.duration * this.viewStart;
		const duration = Math.max(.0001, tool.duration * (this.viewEnd - this.viewStart));
		const top = tool.actors.slice(0, 6).map(actor => actor.name);
		const stacks = /** @type {number[][]} */ (new Array(bins).fill(0).map(() => new Array(top.length + 1).fill(0)));
		tool.events.forEach(event => {
			if (event.inferred <= 0) return;
			const key = top.indexOf(event.prefix || "unclassified");
			const lane = key < 0 ? top.length : key;
			if (event.elapsed + event.inferred < origin || event.elapsed > origin + duration) return;
			const first = Math.max(0, Math.min(bins - 1, Math.floor((event.elapsed - origin) / duration * bins)));
			const last = Math.max(0, Math.min(bins - 1, Math.floor((event.elapsed + event.inferred - origin) / duration * bins)));
			for (let bin = first; bin <= last; bin++) {
				const from = Math.max(event.elapsed, origin + bin / bins * duration);
				const to = Math.min(event.elapsed + event.inferred, origin + (bin + 1) / bins * duration);
				const row = stacks[bin];
				if (row && to > from) row[lane] = (row[lane] ?? 0) + (to - from);
			}
		});
		const peak = Math.max(.001, ...stacks.map(row => row.reduce((sum, value) => sum + value, 0)));
		const slice = (width - left * 2) / bins;
		stacks.forEach((row, bin) => {
			let y = height - 26;
			row.forEach((value, lane) => {
				const h = value / peak * (height - 48);
				ctx.fillStyle = lane === top.length ? css.getPropertyValue("--line") : Observatory.actorColor(top[lane] ?? "");
				ctx.fillRect(left + bin * slice, y - h, Math.max(1, slice - .5), h);
				y -= h;
			});
		});
		ctx.font = "10px ui-monospace, SFMono-Regular, Menlo, monospace";
		ctx.textBaseline = "middle";
		ctx.fillStyle = css.getPropertyValue("--muted");
		ctx.fillText(`+${origin.toFixed(duration < 1 ? 3 : 1)}s`, left, height - 10);
		ctx.fillText(`+${(origin + duration).toFixed(duration < 1 ? 3 : 1)}s`, Math.max(left, width - 70), height - 10);
		let x = left;
		top.forEach(name => {
			ctx.fillStyle = Observatory.actorColor(name);
			ctx.fillRect(x, 6, 8, 8);
			ctx.fillStyle = css.getPropertyValue("--muted");
			ctx.fillText(name.slice(0, 18), x + 12, 10);
			x += 22 + Math.min(18, name.length) * 6.2;
		});
	}
	/**
	 * Draw the per-thread Gantt chart of attributed intervals.
	 *
	 * Every bar runs from an event to the next event on its thread and is
	 * colored by actor, so wide bars are exactly where that thread waited.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 */
	drawGantt(tool) {
		const canvas = this.dom["worker-chart"];
		if (!canvas) return;
		const lanes = tool.threads.slice(0, 24);
		const ratio = window.devicePixelRatio || 1;
		const width = Math.max(320, canvas.clientWidth);
		const height = 40 + Math.max(1, lanes.length) * 22;
		canvas.width = width * ratio;
		canvas.height = height * ratio;
		canvas.style.height = `${height}px`;
		const ctx = canvas.getContext("2d");
		if (!ctx) return;
		ctx.scale(ratio, ratio);
		ctx.clearRect(0, 0, width, height);
		const css = getComputedStyle(document.documentElement);
		const left = 120;
		const right = 12;
		const start = tool.duration * this.viewStart;
		const span = Math.max(.0001, tool.duration * this.viewEnd - start);
		const plot = Math.max(1, width - left - right);
		ctx.font = "10px ui-monospace, SFMono-Regular, Menlo, monospace";
		ctx.textBaseline = "middle";
		lanes.forEach((thread, row) => {
			const y = 12 + row * 22;
			ctx.fillStyle = css.getPropertyValue("--muted");
			ctx.fillText(thread.name.slice(0, 17), 4, y + 7);
			ctx.fillStyle = css.getPropertyValue("--line");
			ctx.fillRect(left, y + 14, plot, 1);
		});
		tool.events.forEach(event => {
			const row = lanes.findIndex(thread => thread.name === event.thread);
			if (row < 0 || event.inferred <= 0 || !this.eventInDrill(event)) return;
			const from = Math.max(event.elapsed, start);
			const to = Math.min(event.elapsed + event.inferred, start + span);
			if (to <= from) return;
			const x = left + (from - start) / span * plot;
			ctx.fillStyle = event.inferred >= .25 ? css.getPropertyValue("--danger") : Observatory.actorColor(event.prefix || "unclassified");
			ctx.globalAlpha = event.inferred >= .25 ? .9 : .75;
			ctx.fillRect(x, 12 + row * 22, Math.max(1, (to - from) / span * plot), 14);
			ctx.globalAlpha = 1;
		});
		ctx.fillStyle = css.getPropertyValue("--muted");
		ctx.fillText(`+${start.toFixed(span < 1 ? 3 : 1)}s`, left, height - 10);
		ctx.fillText(`+${(start + span).toFixed(span < 1 ? 3 : 1)}s`, Math.max(left, width - 90), height - 10);
	}
	/**
	 * Redraw every canvas that follows the shared viewport.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 */
	drawViews(tool) {
		this.drawDetail();
		this.drawShare(tool);
		this.drawGantt(tool);
		this.drawGraph(tool);
		this.drawOverview(tool);
		this.drawResources(tool);
	}
	/**
	 * Convert a pointer position into a viewport fraction for any canvas.
	 *
	 * @param {HTMLElement} canvas - Canvas under the pointer.
	 * @param {MouseEvent} event - Pointer event.
	 * @param {number} left - Plot left inset in pixels.
	 * @returns {number} Fraction between zero and one.
	 */
	static fractionAt = (canvas, event, left) => {
		const rect = canvas.getBoundingClientRect();
		return Math.max(0, Math.min(1, (event.clientX - rect.left - left) / Math.max(1, rect.width - left - 12)));
	};
	/**
	 * Convert a pointer position into elapsed seconds on the shared viewport.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 * @param {HTMLElement} canvas - Canvas under the pointer.
	 * @param {MouseEvent} event - Pointer event.
	 * @param {number} left - Plot left inset in pixels.
	 * @returns {number} Elapsed seconds.
	 */
	timeAt(tool, canvas, event, left) {
		return tool.duration * (this.viewStart + Observatory.fractionAt(canvas, event, left) * (this.viewEnd - this.viewStart));
	}
	/**
	 * Give a canvas wheel-zoom, drag-pan and double-click-reset behavior.
	 *
	 * @param {HTMLElement} canvas - Target canvas.
	 * @param {number} left - Plot left inset in pixels.
	 * @param {{tap?: (event: MouseEvent) => void, hover?: (event: MouseEvent) => void, leave?: () => void}} [handlers] - Optional pointer callbacks.
	 */
	attachViewport(canvas, left, handlers = {}) {
		/** @type {{x: number, start: number, end: number, moved: boolean} | null} */
		let drag = null;
		canvas.addEventListener("pointerdown", event => {
			drag = {
				x: event.clientX,
				start: this.viewStart,
				end: this.viewEnd,
				moved: false
			};
			canvas.setPointerCapture?.(event.pointerId);
		});
		canvas.addEventListener("pointermove", event => {
			const tool = this.data.get(this.selected);
			if (!drag || !tool) {
				handlers.hover?.(event);
				return;
			}
			if (Math.abs(event.clientX - drag.x) > 3) drag.moved = true;
			if (!drag.moved) return;
			const width = drag.end - drag.start;
			const rect = canvas.getBoundingClientRect();
			const shift = (event.clientX - drag.x) / Math.max(1, rect.width - left - 12) * width;
			this.viewStart = Math.max(0, Math.min(1 - width, drag.start - shift));
			this.viewEnd = this.viewStart + width;
			this.drawViews(tool);
			this.renderZoomLabel(tool);
		});
		const finish = (/** @type {MouseEvent} */ event, /** @type {boolean} */ tap) => {
			if (drag && !drag.moved && tap) handlers.tap?.(event);
			drag = null;
		};
		canvas.addEventListener("pointerup", event => finish(event, true));
		canvas.addEventListener("pointercancel", event => finish(event, false));
		canvas.addEventListener("pointerleave", () => {
			drag = null;
			handlers.leave?.();
		});
		canvas.addEventListener("wheel", event => {
			event.preventDefault();
			this.zoom(event.deltaY < 0 ? .72 : 1.38, Observatory.fractionAt(canvas, event, left));
		}, {
			passive: false
		});
		canvas.addEventListener("dblclick", () => {
			this.viewStart = 0;
			this.viewEnd = 1;
			this.renderDetail();
		});
	}
	/**
	 * Refresh the zoom label after a drag without a full re-render.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 */
	renderZoomLabel(tool) {
		const span = tool.duration * (this.viewEnd - this.viewStart);
		this.dom["zoom-label"].textContent = this.viewEnd - this.viewStart > .995 ? "full trace" : `${Observatory.duration(span)} window · ${(this.viewStart * 100).toFixed(1)}–${(this.viewEnd * 100).toFixed(1)}%`;
	}
	/**
	 * Collect a node and all of its descendants.
	 *
	 * @param {GraphNode} node - Subtree root.
	 * @returns {GraphNode[]} Nodes in depth-first order.
	 */
	static subtree = node => [node, ...node.children.flatMap(child => Observatory.subtree(child))];
	/**
	 * Pick the color of a graph node under the active color mode.
	 *
	 * @param {GraphNode} node - Node to color.
	 * @param {TraceTool} tool - Parsed tool record.
	 * @returns {string} CSS color.
	 */
	nodeColor(node, tool) {
		const mode = this.dom["graph-color"]?.value || "actor";
		if (mode === "thread") return Observatory.actorColor(node.thread);
		if (mode === "heat") {
			const heat = Math.min(1, Math.sqrt(node.self / Math.max(tool.duration, .001)) * 1.6);
			return `hsl(${Math.round(150 - heat * 150)} 70% ${Math.round(38 + heat * 12)}%)`;
		}
		return Observatory.actorColor(node.event.prefix || "unclassified");
	}
	/**
	 * Draw the drillable execution graph: one icicle per thread, rows by
	 * nesting depth, width by wall-clock time on the shared viewport.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 */
	drawGraph(tool) {
		const canvas = this.dom["graph-chart"];
		if (!canvas) return;
		const focus = this.focus;
		const lanes = focus ? tool.lanes.filter(lane => lane.name === focus.thread) : tool.lanes;
		const base = focus?.level ?? 0;
		const members = focus ? new Set(Observatory.subtree(focus).map(node => node.id)) : null;
		const rowHeight = 18;
		const head = 20;
		const ratio = window.devicePixelRatio || 1;
		const width = Math.max(320, canvas.clientWidth);
		const depthOf = (/** @type {GraphLane} */ lane) => focus ? Math.max(...Observatory.subtree(focus).map(node => node.level)) - base : lane.maxLevel;
		const layout = lanes.map(lane => Math.min(40, depthOf(lane)) + 1);
		const height = 30 + layout.reduce((sum, rows) => sum + head + rows * rowHeight + 8, 0);
		canvas.width = width * ratio;
		canvas.height = height * ratio;
		canvas.style.height = `${height}px`;
		const ctx = canvas.getContext("2d");
		if (!ctx) return;
		ctx.scale(ratio, ratio);
		ctx.clearRect(0, 0, width, height);
		const css = getComputedStyle(document.documentElement);
		const left = 120;
		const right = 12;
		const plot = Math.max(1, width - left - right);
		const start = tool.duration * this.viewStart;
		const span = Math.max(.0001, tool.duration * this.viewEnd - start);
		/** @type {(seconds: number) => number} */
		const xOf = seconds => left + (seconds - start) / span * plot;
		ctx.font = "10px ui-monospace, SFMono-Regular, Menlo, monospace";
		ctx.textBaseline = "middle";
		this.graphHits = [];
		let y = 6;
		lanes.forEach((lane, laneIndex) => {
			ctx.fillStyle = css.getPropertyValue("--muted");
			ctx.fillText(`${lane.name.slice(0, 16)} · ${lane.nodes.length.toLocaleString()}`, 4, y + head / 2);
			ctx.fillStyle = css.getPropertyValue("--line");
			ctx.fillRect(left, y + head - 2, plot, 1);
			const top = y + head;
			lane.nodes.forEach(node => {
				if (members && !members.has(node.id)) return;
				const row = node.level - base;
				if (row < 0 || row >= (layout[laneIndex] ?? 1)) return;
				if (node.end < start || node.start > start + span) return;
				const x1 = Math.max(left, xOf(node.start));
				const x2 = Math.min(left + plot, xOf(node.end));
				const w = Math.max(1, x2 - x1);
				const ny = top + row * rowHeight;
				ctx.fillStyle = this.nodeColor(node, tool);
				ctx.globalAlpha = node.total >= .25 ? 1 : .8;
				ctx.fillRect(x1, ny, Math.max(1, w - .6), rowHeight - 2);
				ctx.globalAlpha = 1;
				if (w > 54) {
					ctx.fillStyle = css.getPropertyValue("--bg");
					ctx.fillText(node.event.trimmed.slice(0, Math.floor((w - 6) / 6.1)), x1 + 3, ny + rowHeight / 2 - 1);
				}
				if (this.graphHits.length < 8000) this.graphHits.push({
					x: x1,
					y: ny,
					w,
					h: rowHeight - 2,
					node
				});
				if (node === this.selectedNode) {
					ctx.strokeStyle = css.getPropertyValue("--text");
					ctx.lineWidth = 2;
					ctx.beginPath();
					ctx.moveTo(x1, ny);
					ctx.lineTo(x1 + w, ny);
					ctx.lineTo(x1 + w, ny + rowHeight - 2);
					ctx.lineTo(x1, ny + rowHeight - 2);
					ctx.closePath();
					ctx.stroke();
					ctx.lineWidth = 1;
				}
			});
			y = top + (layout[laneIndex] ?? 1) * rowHeight + 8;
		});
		ctx.fillStyle = css.getPropertyValue("--muted");
		for (let i = 0; i <= 6; i++) {
			const value = start + span * i / 6;
			ctx.fillText(`+${value.toFixed(span < 1 ? 3 : 1)}s`, Math.min(left + plot * i / 6, width - 56), height - 10);
		}
	}
	/**
	 * Find the graph node under a pointer.
	 *
	 * @param {MouseEvent} event - Pointer event over the graph canvas.
	 * @returns {GraphNode | null} Node under the pointer.
	 */
	graphNodeAt(event) {
		const rect = this.dom["graph-chart"].getBoundingClientRect();
		const x = event.clientX - rect.left;
		const y = event.clientY - rect.top;
		return this.graphHits.find(hit => x >= hit.x && x <= hit.x + hit.w && y >= hit.y && y <= hit.y + hit.h)?.node ?? null;
	}
	/**
	 * Select a node, show its measures, and optionally drill into it.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 * @param {GraphNode | null} node - Node to select.
	 * @param {boolean} drill - Zoom and focus the node's subtree.
	 */
	selectNode(tool, node, drill) {
		this.selectedNode = node;
		if (node) this.cursorIndex = node.event.index;
		if (drill && node) {
			this.focus = node;
			const duration = Math.max(tool.duration, .001);
			const pad = Math.max(node.total * .04, duration * .0005);
			this.viewStart = Math.max(0, (node.start - pad) / duration);
			this.viewEnd = Math.min(1, Math.max(this.viewStart + .0001, (node.end + pad) / duration));
		}
		this.renderDetail();
	}
	/**
	 * Move the graph focus one level up, or back to all threads.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 */
	focusUp(tool) {
		const parent = this.focus?.parent ?? null;
		this.focus = parent;
		if (parent) {
			const duration = Math.max(tool.duration, .001);
			this.viewStart = Math.max(0, parent.start / duration);
			this.viewEnd = Math.min(1, Math.max(this.viewStart + .0001, parent.end / duration));
		} else {
			this.viewStart = 0;
			this.viewEnd = 1;
		}
		this.selectedNode = this.focus;
		this.renderDetail();
	}
	/**
	 * Render breadcrumbs, measures, and children of the graph selection.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 */
	renderGraphPanel(tool) {
		const crumbs = this.dom["graph-crumbs"];
		crumbs.replaceChildren();
		/** @type {(label: string, handler: () => void) => void} */
		const add = (label, handler) => {
			const node = this.clone("crumb-template");
			const button = Observatory.fieldNode(node, "label");
			button.textContent = label;
			button.addEventListener("click", handler);
			crumbs.append(node);
		};
		add("All threads", () => {
			this.focus = null;
			this.viewStart = 0;
			this.viewEnd = 1;
			this.renderDetail();
		});
		/** @type {GraphNode[]} */
		const chain = [];
		for (let node = this.focus; node; node = node.parent) chain.unshift(node);
		chain.forEach(node => {
			add(node.event.trimmed.slice(0, 36), () => this.selectNode(tool, node, true));
		});
		const node = this.selectedNode;
		const title = this.dom["graph-node"];
		const measures = this.dom["graph-measures"];
		this.dom["graph-children"].replaceChildren();
		if (!node) {
			title.textContent = "Select a bar to see its measures. Double-click (or press Enter) to drill in.";
			measures.textContent = "";
			return;
		}
		const run = Math.max(tool.duration, .001);
		const siblings = node.parent ? node.parent.children : tool.lanes.find(lane => lane.name === node.thread)?.roots ?? [];
		const rank = [...siblings].sort((a, b) => b.total - a.total).indexOf(node) + 1;
		const usage = Observatory.resourcesIn(tool.samples, node.start, node.end);
		const others = tool.events.filter(event => event.thread !== node.thread && event.inferred > 0 && event.elapsed < node.end && event.elapsed + event.inferred > node.start);
		const overlap = others.reduce((sum, event) => sum + Math.min(node.end, event.elapsed + event.inferred) - Math.max(node.start, event.elapsed), 0);
		const lines = [
			`total ${Observatory.duration(node.total)} · self ${Observatory.duration(node.self)} (${(node.self / Math.max(node.total, .001) * 100).toFixed(0)}% unexplained by children)`,
			`${(node.total / Math.max(node.parent?.total ?? run, .001) * 100).toFixed(1)}% of ${node.parent ? "parent" : "run"} · ${(node.total / run * 100).toFixed(1)}% of run`,
			`thread ${node.thread} · level ${node.level} · ${node.children.length} children · rank ${rank}/${siblings.length} among siblings`,
			`+${node.start.toFixed(3)}s → +${node.end.toFixed(3)}s`
		];
		if (node.event.measured !== null && node.event.phase !== "end") lines.push(`measured ${Observatory.duration(node.event.measured)}`);
		if (overlap > 0 && node.total > 0) lines.push(`${(overlap / node.total).toFixed(1)}× parallel work on ${new Set(others.map(event => event.thread)).size} other threads (${Observatory.duration(overlap)} thread time)`);
		if (usage.covered) lines.push(`cpu avg ${usage.cpu.toFixed(0)}% · rss peak ${usage.rss.toFixed(0)} MiB · read ${usage.read.toFixed(1)} MiB · write ${usage.write.toFixed(1)} MiB`);
		title.textContent = node.event.trimmed;
		measures.textContent = lines.join("\n");
		const kids = [...node.children].sort((a, b) => b.total - a.total).slice(0, 8);
		kids.forEach((child, index) => {
			this.appendRank(this.dom["graph-children"], {
				rank: index + 1,
				title: child.event.trimmed,
				detail: `self ${Observatory.duration(child.self)} · ${child.children.length} children`,
				value: Observatory.duration(child.total),
				fraction: child.total / Math.max(kids[0]?.total ?? 1, .001),
				click: () => this.selectNode(tool, child, false)
			});
		});
	}
	/**
	 * Draw the overview strip: event density, CPU, and the viewport window.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 */
	drawOverview(tool) {
		const canvas = this.dom["graph-overview"];
		if (!canvas) return;
		const ratio = window.devicePixelRatio || 1;
		const width = Math.max(320, canvas.clientWidth);
		const height = 56;
		canvas.width = width * ratio;
		canvas.height = height * ratio;
		const ctx = canvas.getContext("2d");
		if (!ctx) return;
		ctx.scale(ratio, ratio);
		ctx.clearRect(0, 0, width, height);
		const css = getComputedStyle(document.documentElement);
		const left = 120;
		const plot = Math.max(1, width - left - 12);
		const duration = Math.max(tool.duration, .001);
		const bins = Math.max(40, Math.floor(plot / 3));
		const counts = /** @type {number[]} */ (new Array(bins).fill(0));
		tool.events.forEach(event => {
			const bin = Math.min(bins - 1, Math.floor(event.elapsed / duration * bins));
			counts[bin] = (counts[bin] ?? 0) + 1;
		});
		const peak = Math.max(1, ...counts);
		counts.forEach((count, bin) => {
			const h = count / peak * (height - 14);
			ctx.fillStyle = css.getPropertyValue("--accent2");
			ctx.globalAlpha = .55;
			ctx.fillRect(left + bin * plot / bins, height - 6 - h, Math.max(1, plot / bins - .5), h);
			ctx.globalAlpha = 1;
		});
		const maxCpu = Math.max(100, ...tool.samples.map(sample => sample.cpu));
		/** @type {{x: number, y: number} | null} */
		let previous = null;
		tool.samples.forEach(sample => {
			const x = left + sample.elapsed / duration * plot;
			const y = height - 6 - sample.cpu / maxCpu * (height - 14);
			if (previous) {
				ctx.strokeStyle = css.getPropertyValue("--warn");
				ctx.beginPath();
				ctx.moveTo(previous.x, previous.y);
				ctx.lineTo(x, y);
				ctx.stroke();
			}
			previous = {
				x,
				y
			};
		});
		const x1 = left + this.viewStart * plot;
		const x2 = left + this.viewEnd * plot;
		ctx.fillStyle = "rgba(143,199,255,.18)";
		ctx.fillRect(x1, 2, Math.max(2, x2 - x1), height - 4);
		ctx.strokeStyle = css.getPropertyValue("--text");
		ctx.beginPath();
		ctx.moveTo(x1, 2);
		ctx.lineTo(x1, height - 2);
		ctx.moveTo(x2, 2);
		ctx.lineTo(x2, height - 2);
		ctx.stroke();
		ctx.fillStyle = css.getPropertyValue("--muted");
		ctx.font = "10px ui-monospace, SFMono-Regular, Menlo, monospace";
		ctx.textBaseline = "middle";
		ctx.fillText("overview", 4, 12);
		ctx.fillText(tool.samples.length ? "events · cpu" : "events", 4, 28);
	}
	/**
	 * Draw the CPU, memory and disk I/O charts and refresh the summary.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 */
	drawResources(tool) {
		const samples = tool.samples;
		const has = samples.length > 0;
		this.dom["resource-note"].textContent = has ? `${samples.length} samples · every ${Observatory.duration(tool.duration / Math.max(samples.length, 1))} on average · whole process tree` : "No resource samples in this trace. Set [tool.steps] sample = 0.5 in pyproject.toml to record CPU, memory and disk I/O.";
		const total = Observatory.resourcesIn(samples, 0, tool.duration);
		const text = (/** @type {string} */ id, /** @type {string} */ value) => {
			const target = this.dom[id];
			if (target) target.textContent = has ? value : "—";
		};
		text("res-cpu-mean", `${total.cpu.toFixed(0)}%`);
		text("res-cpu-peak", `${Math.max(0, ...samples.map(sample => sample.cpu)).toFixed(0)}%`);
		text("res-rss-peak", `${Math.max(0, ...samples.map(sample => sample.rss)).toFixed(0)} MiB`);
		text("res-read", `${total.read.toFixed(1)} MiB`);
		text("res-write", `${total.write.toFixed(1)} MiB`);
		text("res-procs", String(Math.max(0, ...samples.map(sample => sample.procs))));
		/** @type {[string, string, (sample: ResourceSample) => number[], string[]][]} */
		const charts = [
			["cpu-chart", "CPU % of a core", sample => [sample.cpu], ["#ffbd69"]],
			["mem-chart", "Memory MiB", sample => [sample.rss], ["#b9f5cf"]],
			["io-chart", "Disk MiB/s", sample => [sample.read, sample.write], ["#8fc7ff", "#d6a5ff"]]
		];
		charts.forEach(([id, label, values, colors]) => {
			const canvas = /** @type {HTMLCanvasElement | undefined} */ (this.dom[id]);
			if (!canvas) return;
			const ratio = window.devicePixelRatio || 1;
			const width = Math.max(320, canvas.clientWidth);
			const height = 120;
			canvas.width = width * ratio;
			canvas.height = height * ratio;
			const ctx = canvas.getContext("2d");
			if (!ctx) return;
			ctx.scale(ratio, ratio);
			ctx.clearRect(0, 0, width, height);
			const css = getComputedStyle(document.documentElement);
			const left = 120;
			const plot = Math.max(1, width - left - 12);
			const start = tool.duration * this.viewStart;
			const span = Math.max(.0001, tool.duration * this.viewEnd - start);
			const peak = Math.max(.001, ...samples.map(sample => values(sample).reduce((sum, value) => sum + value, 0)));
			ctx.font = "10px ui-monospace, SFMono-Regular, Menlo, monospace";
			ctx.textBaseline = "middle";
			ctx.fillStyle = css.getPropertyValue("--muted");
			ctx.fillText(label.slice(0, 18), 4, 14);
			ctx.fillText(has ? `peak ${peak.toFixed(peak < 10 ? 2 : 0)}` : "no samples", 4, 30);
			if (id === "io-chart")
				[["read", colors[0]], ["write", colors[1]]].forEach(([name, color], row) => {
					ctx.fillStyle = color ?? "#8fc7ff";
					ctx.fillRect(4, 42 + row * 14, 8, 8);
					ctx.fillStyle = css.getPropertyValue("--muted");
					ctx.fillText(name ?? "", 16, 46 + row * 14);
				});
			tool.gaps.filter(event => event.gap >= .25 && event.elapsed >= start && event.elapsed - event.gap <= start + span).forEach(event => {
				const x1 = Math.max(left, left + (event.elapsed - event.gap - start) / span * plot);
				const x2 = Math.min(left + plot, left + (event.elapsed - start) / span * plot);
				ctx.fillStyle = "rgba(255,123,134,.13)";
				ctx.fillRect(x1, 4, Math.max(1, x2 - x1), height - 20);
			});
			let previous = 0;
			samples.forEach(sample => {
				const x1 = left + (previous - start) / span * plot;
				const x2 = left + (sample.elapsed - start) / span * plot;
				previous = sample.elapsed;
				if (x2 < left || x1 > left + plot) return;
				let y = height - 16;
				values(sample).forEach((value, index) => {
					const h = value / peak * (height - 28);
					ctx.fillStyle = colors[index] ?? "#8fc7ff";
					ctx.fillRect(Math.max(left, x1), y - h, Math.max(1, Math.min(left + plot, x2) - Math.max(left, x1) - .4), h);
					y -= h;
				});
			});
			ctx.fillStyle = css.getPropertyValue("--muted");
			ctx.fillText(`+${start.toFixed(span < 1 ? 3 : 1)}s`, left, height - 6);
			ctx.fillText(`+${(start + span).toFixed(span < 1 ? 3 : 1)}s`, Math.max(left, width - 70), height - 6);
		});
		this.renderResourceActors(tool);
	}
	/**
	 * Rank actors by CPU use during their own intervals.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 * @returns {void}
	 */
	renderResourceActors(tool) {
		const list = this.dom["resource-actors"];
		list.replaceChildren();
		if (!tool.samples.length) return;
		const rows = tool.actors.slice(0, 40).map(actor => {
			let seconds = 0;
			let cpu = 0;
			let rss = 0;
			let read = 0;
			let write = 0;
			tool.events.filter(event => (event.prefix || "unclassified") === actor.name && event.inferred > 0).forEach(event => {
				const usage = Observatory.resourcesIn(tool.samples, event.elapsed, event.elapsed + event.inferred);
				if (!usage.covered) return;
				seconds += event.inferred;
				cpu += usage.cpu * event.inferred;
				rss = Math.max(rss, usage.rss);
				read += usage.read;
				write += usage.write;
			});
			return {
				actor,
				seconds,
				average: seconds > 0 ? cpu / seconds : 0,
				coreSeconds: cpu / 100,
				rss,
				read,
				write
			};
		}).filter(row => row.seconds > 0 && this.matches(row.actor.name)).sort((a, b) => b.coreSeconds - a.coreSeconds).slice(0, 12);
		rows.forEach((row, index) => {
			const verdict = row.average >= 80 ? "CPU-bound" : row.average < 15 ? "mostly waiting" : "mixed";
			this.appendRank(list, {
				rank: index + 1,
				title: row.actor.name,
				detail: `${verdict} · avg ${row.average.toFixed(0)}% cpu over ${Observatory.duration(row.seconds)} · rss peak ${row.rss.toFixed(0)} MiB · read ${row.read.toFixed(1)} / write ${row.write.toFixed(1)} MiB`,
				value: `${row.coreSeconds.toFixed(1)} core·s`,
				fraction: row.coreSeconds / Math.max(rows[0]?.coreSeconds ?? 1, .001),
				click: () => this.focusPrefix(tool, row.actor.name === "unclassified" ? "" : row.actor.name)
			});
		});
	}
	/**
	 * Draw the wall-clock overview lane for every loaded tool.
	 */
	drawGlobal() {
		const canvas = this.dom["global-timeline"];
		const tools = [...this.data.values()].sort((a, b) => a.start.getTime() - b.start.getTime());
		if (!tools.length) return;
		const ratio = window.devicePixelRatio || 1;
		const width = canvas.clientWidth;
		const height = 250;
		canvas.width = width * ratio;
		canvas.height = height * ratio;
		const ctx = canvas.getContext("2d");
		if (!ctx) return;
		ctx.scale(ratio, ratio);
		ctx.clearRect(0, 0, width, height);
		const start = Math.min(...tools.map(tool => tool.start.getTime()));
		const end = Math.max(...tools.map(tool => tool.end.getTime()));
		const span = Math.max(1, end - start);
		const left = 120;
		const right = 18;
		const usable = width - left - right;
		ctx.font = "10px ui-monospace, monospace";
		ctx.textBaseline = "middle";
		tools.forEach((tool, i) => {
			const y = 32 + i * 40;
			ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--muted");
			ctx.fillText(tool.label, 4, y);
			ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--line");
			ctx.fillRect(left, y - 5, usable, 10);
			const x = left + (tool.start.getTime() - start) / span * usable;
			const w = Math.max(2, (tool.end.getTime() - tool.start.getTime()) / span * usable);
			ctx.fillStyle = tool.color;
			ctx.fillRect(x, y - 5, w, 10);
			tool.gaps.slice(0, 6).filter(gap => gap.gap > .25).forEach(gap => {
				const gx = x + (gap.elapsed - gap.gap) / Math.max(tool.duration, .001) * w;
				const gw = gap.gap / Math.max(tool.duration, .001) * w;
				ctx.fillStyle = "#ff7b86";
				ctx.fillRect(gx, y - 5, Math.max(1, gw), 10);
			});
		});
		ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--muted");
		ctx.fillText("wall clock →", left, height - 12);
	}
	/**
	 * Draw the selected tool's stage, density, and event lanes.
	 */
	drawDetail() {
		const tool = this.data.get(this.selected);
		const canvas = this.dom["detail-chart"];
		if (!tool || !canvas) return;
		const ratio = window.devicePixelRatio || 1;
		const width = Math.max(320, canvas.clientWidth);
		const height = 430;
		canvas.width = width * ratio;
		canvas.height = height * ratio;
		const ctx = canvas.getContext("2d");
		if (!ctx) return;
		ctx.scale(ratio, ratio);
		ctx.clearRect(0, 0, width, height);
		const css = getComputedStyle(document.documentElement);
		const left = 72;
		const right = 16;
		const plotWidth = Math.max(1, width - left - right);
		const start = tool.duration * this.viewStart;
		const end = tool.duration * this.viewEnd;
		const span = Math.max(.0001, end - start);
		/** @type {(elapsed: number) => number} */
		const xOf = elapsed => left + (elapsed - start) / span * plotWidth;
		const visible = tool.events.filter(event => event.elapsed >= start && event.elapsed <= end && this.eventInDrill(event));
		const lanes = {
			stages: /** @type {[number, number]} */ ([32, 104]),
			density: /** @type {[number, number]} */ ([126, 242]),
			events: /** @type {[number, number]} */ ([264, 342]),
			axis: 382
		};
		ctx.font = "10px ui-monospace, SFMono-Regular, Menlo, monospace";
		ctx.textBaseline = "middle";
		ctx.fillStyle = css.getPropertyValue("--muted");
		/** @type {[string, number][]} */
		([
			["STAGES", 68],
			["DENSITY", 184],
			["EVENTS", 303]
		]).forEach(([label, y]) => {
			ctx.fillText(label, 5, y);
		});
		ctx.strokeStyle = css.getPropertyValue("--line");
		[116, 252, 352].forEach(y => {
			ctx.beginPath();
			ctx.moveTo(left, y);
			ctx.lineTo(width - right, y);
			ctx.stroke();
		});
		for (let i = 0; i <= 8; i++) {
			const x = left + plotWidth * i / 8;
			const value = start + span * i / 8;
			ctx.strokeStyle = css.getPropertyValue("--line");
			ctx.beginPath();
			ctx.moveTo(x, 18);
			ctx.lineTo(x, 360);
			ctx.stroke();
			ctx.fillStyle = css.getPropertyValue("--muted");
			ctx.fillText(`+${value.toFixed(span < 1 ? 3 : 1)}s`, Math.min(x + 2, width - 60), lanes.axis);
		}
		const significant = tool.gaps.filter(event => event.gap >= Math.max(.02, span / 800) && event.elapsed >= start && event.elapsed - event.gap <= end);
		significant.forEach(event => {
			const gx1 = Math.max(left, xOf(Math.max(start, event.elapsed - event.gap)));
			const gx2 = Math.min(width - right, xOf(Math.min(end, event.elapsed)));
			ctx.fillStyle = "rgba(255,123,134,.13)";
			ctx.fillRect(gx1, 18, Math.max(1, gx2 - gx1), 334);
			if (gx2 - gx1 > 18) {
				ctx.fillStyle = css.getPropertyValue("--danger");
				ctx.fillText(Observatory.duration(event.gap), gx1 + 4, 28);
			}
		});
		tool.stages.forEach((stage, index) => {
			const stageEnd = stage.start + stage.duration;
			if (stageEnd < start || stage.start > end) return;
			const x1 = Math.max(left, xOf(Math.max(start, stage.start)));
			const x2 = Math.min(width - right, xOf(Math.min(end, stageEnd)));
			const y = (lanes.stages[0] ?? 0) + index % 3 * 22;
			ctx.fillStyle = index % 2 ? "rgba(185,245,207,.32)" : "rgba(143,199,255,.34)";
			ctx.fillRect(x1, y, Math.max(2, x2 - x1), 16);
			if (x2 - x1 > 54) {
				ctx.fillStyle = css.getPropertyValue("--text");
				ctx.fillText(stage.name.slice(0, 42), x1 + 5, y + 8);
			}
		});
		const bins = Math.max(60, Math.min(260, Math.floor(plotWidth / 4)));
		const counts = /** @type {number[]} */ (new Array(bins).fill(0));
		visible.forEach(event => {
			const bin = Math.max(0, Math.min(bins - 1, Math.floor((event.elapsed - start) / span * bins)));
			counts[bin] = (counts[bin] ?? 0) + 1;
		});
		const maxCount = Math.max(1, ...counts);
		const densityHeight = (lanes.density[1] ?? 0) - (lanes.density[0] ?? 0);
		counts.forEach((count, index) => {
			const bw = plotWidth / bins;
			const bh = count / maxCount * densityHeight;
			ctx.fillStyle = count / maxCount > .72 ? css.getPropertyValue("--warn") : css.getPropertyValue("--accent2");
			ctx.fillRect(left + index * bw, (lanes.density[1] ?? 0) - bh, Math.max(1, bw - .5), bh);
		});
		const maxMarks = Math.max(1, Math.floor(plotWidth * 1.7));
		const stride = Math.max(1, Math.ceil(visible.length / maxMarks));
		visible.forEach((event, index) => {
			if (index % stride && event.index !== this.cursorIndex && event.index !== this.hoverIndex) return;
			const x = xOf(event.elapsed);
			const lane = Math.abs(Observatory.hash(event.prefix)) % 5;
			const y = (lanes.events[0] ?? 0) + 10 + lane * 12;
			ctx.strokeStyle = event.gap > span * .02 ? css.getPropertyValue("--danger") : tool.color;
			ctx.globalAlpha = stride > 1 ? .62 : .9;
			ctx.beginPath();
			ctx.moveTo(x, y - 4);
			ctx.lineTo(x, y + 4);
			ctx.stroke();
			ctx.globalAlpha = 1;
		});
		const hover = tool.events[this.hoverIndex ?? -1];
		if (hover && hover.elapsed >= start && hover.elapsed <= end) {
			const x = xOf(hover.elapsed);
			ctx.strokeStyle = css.getPropertyValue("--warn");
			ctx.setLineDash([3, 3]);
			ctx.beginPath();
			ctx.moveTo(x, 18);
			ctx.lineTo(x, 352);
			ctx.stroke();
			ctx.setLineDash([]);
		}
		const cursor = tool.events[this.cursorIndex];
		if (cursor && cursor.elapsed >= start && cursor.elapsed <= end) {
			const x = xOf(cursor.elapsed);
			ctx.strokeStyle = css.getPropertyValue("--text");
			ctx.lineWidth = 2;
			ctx.beginPath();
			ctx.moveTo(x, 14);
			ctx.lineTo(x, 358);
			ctx.stroke();
			ctx.lineWidth = 1;
			ctx.fillStyle = css.getPropertyValue("--text");
			ctx.beginPath();
			ctx.moveTo(x - 6, 14);
			ctx.lineTo(x + 6, 14);
			ctx.lineTo(x, 22);
			ctx.closePath();
			ctx.fill();
		}
		this.dom["zoom-label"].textContent = this.viewEnd - this.viewStart > .995 ? "full trace" : `${Observatory.duration(span)} window · ${(this.viewStart*100).toFixed(1)}–${(this.viewEnd*100).toFixed(1)}%`;
	}
	/**
	 * Compute a stable string hash used to assign event lanes.
	 *
	 * @param {string} value - Value to hash.
	 * @returns {number} Signed 32-bit hash.
	 */
	static hash = value => {
		let result = 0;
		for (let index = 0; index < value.length; index++) result = (result << 5) - result + value.charCodeAt(index) | 0;
		return result;
	};
	/**
	 * Binary-search the event index nearest to an elapsed target.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 * @param {number} target - Target elapsed time in seconds.
	 * @returns {number} Index of the nearest drill-visible event.
	 */
	nearestEvent(tool, target) {
		let low = 0;
		let high = tool.events.length - 1;
		while (low < high) {
			const mid = Math.floor((low + high) / 2);
			if ((tool.events[mid]?.elapsed ?? 0) < target) low = mid + 1;
			else high = mid;
		}
		const candidates = [low, Math.max(0, low - 1), Math.min(tool.events.length - 1, low + 1)].filter(index => {
			const event = tool.events[index];
			return event !== undefined && this.eventInDrill(event);
		});
		return candidates.reduce((best, index) => Math.abs((tool.events[index]?.elapsed ?? 0) - target) < Math.abs((tool.events[best]?.elapsed ?? 0) - target) ? index : best, candidates[0] ?? 0);
	}
	/**
	 * Show the tooltip for the event under the pointer.
	 *
	 * @param {MouseEvent} event - Pointer event over the detail chart.
	 */
	hover(event) {
		const tool = this.data.get(this.selected);
		if (!tool) return;
		const fraction = this.pointerFraction(event);
		const target = tool.duration * (this.viewStart + fraction * (this.viewEnd - this.viewStart));
		this.hoverIndex = this.nearestEvent(tool, target);
		const hovered = tool.events[this.hoverIndex];
		const tooltip = this.dom["detail-tooltip"];
		const rect = this.dom["detail-chart"].getBoundingClientRect();
		if (!hovered) return;
		tooltip.textContent = `#${hovered.index+1}  +${hovered.elapsed.toFixed(3)}s  Δ${Observatory.duration(hovered.gap)}  → next ${Observatory.duration(hovered.inferred)}${hovered.measured !== null && hovered.phase !== "end" ? `  ⏱ ${Observatory.duration(hovered.measured)}` : ""}${hovered.thread === "main" ? "" : `  [${hovered.thread}]`}\n${hovered.message}`;
		tooltip.style.left = `${Math.max(8,Math.min(rect.width-360,event.clientX-rect.left+12))}px`;
		tooltip.style.top = `${Math.max(8,event.clientY-rect.top-54)}px`;
		tooltip.hidden = false;
		this.drawDetail();
	}
	/**
	 * Reset cursor, viewport, and drill state to the full trace.
	 */
	resetInteractiveState() {
		this.cursorIndex = 0;
		this.viewStart = 0;
		this.viewEnd = 1;
		this.drill = [];
		this.focus = null;
		this.selectedNode = null;
	}
	/**
	 * Check whether an event passes the deepest prefix drill filter.
	 *
	 * @param {TraceEvent} event - Parsed event.
	 * @returns {boolean} True when the event is visible under the drill.
	 */
	eventInDrill(event) {
		const prefix = [...this.drill].reverse().find(item => item.prefix)?.prefix;
		return prefix === undefined || event.prefix === prefix;
	}
	/**
	 * Push a drill level and zoom the viewport to an elapsed interval.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 * @param {number} start - Interval start in elapsed seconds.
	 * @param {number} end - Interval end in elapsed seconds.
	 * @param {string} label - Breadcrumb label for the drill level.
	 */
	drillTo(tool, start, end, label) {
		const duration = Math.max(tool.duration, .001);
		this.viewStart = Math.max(0, start / duration);
		this.viewEnd = Math.min(1, Math.max(this.viewStart + .0001, end / duration));
		this.drill.push({
			label,
			start,
			end
		});
	}
	/**
	 * Render the breadcrumb trail for the current drill stack.
	 */
	renderDrillbar() {
		this.dom.drillbar.replaceChildren();
		/** @type {(label: string, handler: () => void) => void} */
		const add = (label, handler) => {
			const node = this.clone("crumb-template");
			const button = Observatory.fieldNode(node, "label");
			button.textContent = label;
			button.addEventListener("click", handler);
			this.dom.drillbar.append(node);
		};
		add("Full trace", () => {
			this.viewStart = 0;
			this.viewEnd = 1;
			this.drill = [];
			this.renderDetail();
		});
		this.drill.forEach((item, index) => {
			add(item.label, () => {
				this.drill = this.drill.slice(0, index + 1);
				if (item.start !== undefined) this.drillToView(item);
				this.renderDetail();
			});
		});
	}
	/**
	 * Highlight the stage row owning the cursor event and scroll it into view.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 */
	highlightRelated(tool) {
		const event = tool.events[this.cursorIndex];
		if (!event) return;
		document.querySelectorAll(".rank-row,.stage-row").forEach(node => {
			node.classList.remove("cursor-related");
		});
		const stage = tool.stages.find(item => event.elapsed >= item.start && event.elapsed <= item.start + item.duration);
		if (stage)[...this.dom["stage-list"].querySelectorAll(".stage-row")].forEach((node, index) => {
			node.classList.toggle("cursor-related", tool.stages[index] === stage);
		});
		const active = this.dom["event-list"].querySelector(".cursor-event");
		if (active) active.scrollIntoView({
			block: "nearest"
		});
	}
	/**
	 * Restore the viewport stored in a drill item.
	 *
	 * @param {DrillItem} item - Drill item carrying start and end bounds.
	 */
	drillToView(item) {
		const tool = this.data.get(this.selected);
		if (!tool) return;
		this.viewStart = (item.start ?? 0) / Math.max(tool.duration, .001);
		this.viewEnd = (item.end ?? tool.duration) / Math.max(tool.duration, .001);
	}
	/**
	 * Convert a pointer position into a fractional chart coordinate.
	 *
	 * @param {MouseEvent} event - Pointer event over the detail chart.
	 * @returns {number} Horizontal fraction between zero and one.
	 */
	pointerFraction(event) {
		const rect = this.dom["detail-chart"].getBoundingClientRect();
		const left = 45;
		const right = 12;
		return Math.max(0, Math.min(1, (event.clientX - rect.left - left) / Math.max(1, rect.width - left - right)));
	}
	/**
	 * Move the event cursor to the pointed elapsed time.
	 *
	 * @param {MouseEvent} event - Pointer event over the detail chart.
	 */
	scrub(event) {
		const tool = this.data.get(this.selected);
		if (!tool) return;
		const fraction = this.pointerFraction(event);
		const target = tool.duration * (this.viewStart + fraction * (this.viewEnd - this.viewStart));
		this.cursorIndex = this.nearestEvent(tool, target);
		this.updateCursor(tool);
		this.drawDetail();
		this.renderEvents(tool);
		this.highlightRelated(tool);
	}
	/**
	 * Step the event cursor by a signed offset across drill-visible events.
	 *
	 * @param {number} delta - Signed number of events to step.
	 */
	stepCursor(delta) {
		const tool = this.data.get(this.selected);
		if (!tool) return;
		let index = this.cursorIndex;
		for (let i = 0; i < Math.abs(delta); i++) {
			do index = Math.max(0, Math.min(tool.events.length - 1, index + Math.sign(delta))); while (index > 0 && index < tool.events.length - 1 && !this.eventInDrill( /** @type {TraceEvent} */ (tool.events[index])));
		}
		this.cursorIndex = index;
		const event = tool.events[index];
		if (!event) return;
		if (event.elapsed < tool.duration * this.viewStart || event.elapsed > tool.duration * this.viewEnd) this.centerOn(event.elapsed / Math.max(tool.duration, .001));
		this.updateCursor(tool);
		this.drawDetail();
		this.renderEvents(tool);
	}
	/**
	 * Center the current viewport width on a fractional position.
	 *
	 * @param {number} position - Fractional trace position between zero and one.
	 */
	centerOn(position) {
		const width = this.viewEnd - this.viewStart;
		this.viewStart = Math.max(0, Math.min(1 - width, position - width / 2));
		this.viewEnd = this.viewStart + width;
	}
	/**
	 * Scale the viewport width around an anchor fraction.
	 *
	 * @param {number} factor - Width multiplier; below one zooms in.
	 * @param {number} [anchor] - Viewport fraction held fixed while zooming.
	 */
	zoom(factor, anchor = .5) {
		const width = this.viewEnd - this.viewStart;
		const next = Math.max(.002, Math.min(1, width * factor));
		const pivot = this.viewStart + width * anchor;
		this.viewStart = Math.max(0, Math.min(1 - next, pivot - next * anchor));
		this.viewEnd = this.viewStart + next;
		this.renderDetail();
	}
	/**
	 * Shift the viewport by a fraction of its own width.
	 *
	 * @param {number} amount - Signed fraction of the viewport width to pan.
	 */
	pan(amount) {
		const width = this.viewEnd - this.viewStart;
		const shift = width * amount;
		this.viewStart = Math.max(0, Math.min(1 - width, this.viewStart + shift));
		this.viewEnd = this.viewStart + width;
		this.renderDetail();
	}
	/**
	 * Refresh the cursor readout and inspector panel for the cursor event.
	 *
	 * @param {TraceTool} tool - Parsed tool record.
	 */
	updateCursor(tool) {
		const event = tool.events[Math.max(0, Math.min(tool.events.length - 1, this.cursorIndex))];
		if (!event) return;
		const radius = Math.max(.05, tool.duration * (this.viewEnd - this.viewStart) * .025);
		const nearby = tool.events.filter(item => Math.abs(item.elapsed - event.elapsed) <= radius && this.eventInDrill(item));
		const localRate = nearby.length / Math.max(radius * 2, .001);
		this.dom["cursor-readout"].textContent = `event ${event.index + 1}/${tool.events.length} · +${event.elapsed.toFixed(3)}s`;
		this.dom["cursor-rate"].textContent = `${localRate.toFixed(1)} events/s`;
		this.dom["cursor-gap"].textContent = Observatory.duration(event.gap);
		this.dom["cursor-position"].textContent = `${(event.elapsed / Math.max(tool.duration, .001) * 100).toFixed(2)}%`;
		this.dom["cursor-nearby"].textContent = `${nearby.length} in ±${Observatory.duration(radius)}`;
		this.dom["inspect-index"].textContent = `#${event.index + 1}`;
		this.dom["inspect-elapsed"].textContent = `+${event.elapsed.toFixed(3)}s`;
		this.dom["inspect-time"].textContent = event.time ? event.time.toISOString().slice(11, 23) : "—";
		this.dom["inspect-message"].textContent = event.message;
		this.dom["inspect-thread"].textContent = event.thread;
		this.dom["inspect-cost"].textContent = `${Observatory.duration(event.inferred)} until next${event.phase !== "end" && event.measured !== null ? ` · ${Observatory.duration(event.measured)} measured` : ""}`;
		this.highlightRelated(tool);
	}
	/**
	 * Clone the template content registered under an element id.
	 *
	 * @param {string} id - Template element identifier.
	 * @returns {DocumentFragment} Detached template contents.
	 */
	clone(id) {
		return /** @type {DocumentFragment} */ ( /** @type {HTMLTemplateElement} */ (this.dom[id]).content.cloneNode(true));
	}
	/**
	 * Set the text of a named ``data-field`` element.
	 *
	 * @param {DocumentFragment | Element} root - Subtree to search.
	 * @param {string} name - ``data-field`` attribute value.
	 * @param {string} value - Text content to assign.
	 */
	static field = (root, name, value) => {
		Observatory.fieldNode(root, name).textContent = value;
	};
	/**
	 * Locate a named ``data-field`` element inside a subtree.
	 *
	 * @param {DocumentFragment | Element} root - Subtree to search.
	 * @param {string} name - ``data-field`` attribute value.
	 * @returns {HTMLElement} Matching element.
	 */
	static fieldNode = (root, name) => {
		return /** @type {HTMLElement} */ (root.querySelector(`[data-field="${name}"]`));
	};
	/**
	 * Check whether a value satisfies the active search query.
	 *
	 * @param {string} value - Candidate text.
	 * @returns {boolean} True when the value matches or no query is set.
	 */
	matches(value) {
		return !this.query || value.toLowerCase().includes(this.query);
	}
	/**
	 * Format a duration in seconds for compact display.
	 *
	 * @param {number} seconds - Duration in seconds.
	 * @returns {string} Human-readable duration.
	 */
	static duration = seconds => {
		if (seconds >= 60) return `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(1)}s`;
		if (seconds >= 1) return `${seconds.toFixed(seconds >= 10 ? 1 : 2)}s`;
		return `${(seconds * 1000).toFixed(0)}ms`;
	};
}
new Observatory().start();
