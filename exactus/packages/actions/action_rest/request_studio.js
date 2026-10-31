/** @typedef {"params" | "headers" | "cookies"} RowKind */
/** @typedef {{enabled: boolean, key: string, value: string}} RequestRow */
/** @typedef {{name: string, value: string, secret: boolean}} Variable */
/** @typedef {{path: string, segment: string, branch: boolean, depth: number, count: number, variable: Variable | null}} CompletionItem */
/** @typedef {{editor: HTMLElement | null, startNode: Text | null, startOffset: number, query: string, selected: number, items: CompletionItem[], expanded: Set<string>}} Completion */
/** @typedef {{token: HTMLElement, side: "before" | "after"}} TokenBoundary */
/** @typedef {"http" | "websocket"} Transport */
/** @typedef {{rows: Record<RowKind, RequestRow[]>, variables: Variable[], url: string, body: string}} RequestStudioSeed */
/**
 * Interactive request studio: token editors, variables and HTTP/WebSocket
 * transports.
 */
export class RequestStudio {
	/** @param {RequestStudioSeed} data */
	constructor(data) {
		this.el = RequestStudio.elements();
		this.rows = data.rows;
		this.variables = data.variables;
		/** @type {Completion} */
		this.completion = {
			editor: null,
			startNode: null,
			startOffset: 0,
			query: "",
			selected: 0,
			items: [],
			expanded: new Set(),
		};
		/** @type {HTMLElement | null} */
		this.selectedToken = null;
		/** @type {ReturnType<typeof setTimeout> | undefined} */
		this.toastTimer = undefined;
		/** @type {unknown} */
		this.captureValue = null;
		/** @type {WeakMap<HTMLButtonElement, unknown>} */
		this.jsonValues = new WeakMap();
		/** @type {WebSocket | null} */
		this.socket = null;
		this.wsMessageCount = 0;
		this.bind();
		this.render(data.url, data.body);
	}
	static elements = () => ({
		shell: /** @type {HTMLElement} */ (document.getElementById("studio")),
		transport: /** @type {HTMLSelectElement} */ (document.getElementById("transport")),
		method: /** @type {HTMLSelectElement} */ (document.getElementById("method")),
		url: /** @type {HTMLElement} */ (document.getElementById("url")),
		resolved_url: /** @type {HTMLElement} */ (document.getElementById("resolved-url")),
		send: /** @type {HTMLButtonElement} */ (document.getElementById("send")),
		body: /** @type {HTMLElement} */ (document.getElementById("body")),
		body_format: /** @type {HTMLSelectElement} */ (document.getElementById("body-format")),
		body_format_action: /** @type {HTMLButtonElement} */ (document.getElementById("body-format-action")),
		body_tree: /** @type {HTMLElement} */ (document.getElementById("body-tree")),
		body_source: /** @type {HTMLElement} */ (document.getElementById("body-source")),
		body_mode: /** @type {HTMLElement} */ (document.getElementById("body-mode")),
		response_text: /** @type {HTMLElement} */ (document.getElementById("response-text")),
		response_view: /** @type {HTMLElement} */ (document.getElementById("response-view")),
		response_meta: /** @type {HTMLElement} */ (document.getElementById("response-meta")),
		copy: /** @type {HTMLButtonElement} */ (document.getElementById("copy")),
		capture: /** @type {HTMLFormElement} */ (document.getElementById("capture")),
		capture_path: /** @type {HTMLElement} */ (document.getElementById("capture-path")),
		capture_name: /** @type {HTMLInputElement} */ (document.getElementById("capture-name")),
		variables: /** @type {HTMLElement} */ (document.getElementById("variables")),
		variables_toggle: /** @type {HTMLButtonElement} */ (document.getElementById("variables-toggle")),
		variables_close: /** @type {HTMLButtonElement} */ (document.getElementById("variables-close")),
		variable_list: /** @type {HTMLElement} */ (document.getElementById("variable-list")),
		variable_add: /** @type {HTMLButtonElement} */ (document.getElementById("variable-add")),
		autocomplete: /** @type {HTMLElement} */ (document.getElementById("autocomplete")),
		toast: /** @type {HTMLElement} */ (document.getElementById("toast")),
		row_template: /** @type {HTMLTemplateElement} */ (document.getElementById("row-template")),
		variable_template: /** @type {HTMLTemplateElement} */ (document.getElementById("variable-template")),
		params_table: /** @type {HTMLElement} */ (document.getElementById("params-table")),
		headers_table: /** @type {HTMLElement} */ (document.getElementById("headers-table")),
		cookies_table: /** @type {HTMLElement} */ (document.getElementById("cookies-table")),
		params_count: /** @type {HTMLElement} */ (document.getElementById("params-count")),
		headers_count: /** @type {HTMLElement} */ (document.getElementById("headers-count")),
		cookies_count: /** @type {HTMLElement} */ (document.getElementById("cookies-count")),
		messages_count: /** @type {HTMLElement} */ (document.getElementById("messages-count")),
		ws_protocols: /** @type {HTMLInputElement} */ (document.getElementById("ws-protocols")),
		ws_state: /** @type {HTMLElement} */ (document.getElementById("ws-state")),
		ws_log: /** @type {HTMLElement} */ (document.getElementById("ws-log")),
		ws_message: /** @type {HTMLElement} */ (document.getElementById("ws-message")),
		ws_send: /** @type {HTMLButtonElement} */ (document.getElementById("ws-send")),
		ws_clear: /** @type {HTMLButtonElement} */ (document.getElementById("ws-clear")),
	});
	/** @param {string} text @returns {string} */
	static json = text => {
		try {
			return JSON.stringify(JSON.parse(text), null, 2);
		} catch {
			return text;
		}
	};
	/** @param {string | undefined} value @returns {value is RowKind} */
	static isRowKind = value => value === "params" || value === "headers" || value === "cookies";
	/**
	 * Wire every workspace event listener.
	 */
	bind() {
		document.querySelectorAll("[data-tab]").forEach(tab => {
			tab.addEventListener("click", () => this.activate(tab.getAttribute("data-tab") ?? undefined), );
		});
		document.querySelectorAll("[data-add]").forEach(button => {
			button.addEventListener("click", () => {
				const kind = button.getAttribute("data-add") ?? undefined;
				if (RequestStudio.isRowKind(kind)) this.addRow(kind);
			});
		});
		this.el.variables_toggle.addEventListener("click", () => this.toggleVariables(), );
		this.el.variables_close.addEventListener("click", () => this.toggleVariables(false), );
		this.el.variable_add.addEventListener("click", () => this.addVariable());
		this.el.send.addEventListener("click", () => this.send());
		this.el.transport.addEventListener("change", () => this.setTransport());
		this.el.ws_send.addEventListener("click", () => this.sendWebSocketMessage(), );
		this.el.ws_clear.addEventListener("click", () => this.clearWebSocketLog());
		this.el.copy.addEventListener("click", () => this.copy());
		document.addEventListener("input", event => this.editorInput(event));
		document.addEventListener("keydown", event => this.keydown(event));
		document.addEventListener("beforeinput", event => this.beforeInput(event), );
		document.addEventListener("copy", event => this.clipboard(event, false));
		document.addEventListener("cut", event => this.clipboard(event, true));
		document.addEventListener("paste", event => RequestStudio.paste(event));
		document.addEventListener("pointerdown", event => this.tokenPointerDown(event), true, );
		document.addEventListener("selectionchange", () => this.selectionChanged());
		document.addEventListener("pointerdown", event => this.outside(event));
	}
	/** @param {string} url @param {string} body */
	render(url, body) {
		RequestStudio.setEditorText(this.el.url, url);
		RequestStudio.setEditorText(this.el.body, body);
		/** @type {RowKind[]} */
		(["params", "headers", "cookies"]).forEach(kind => {
			this.renderRows(kind);
		});
		this.renderVariables();
		this.updateUrl();
		this.setTransport();
	}
	/** @param {HTMLElement} editor @param {string} text */
	static setEditorText = (editor, text) => {
		editor.replaceChildren();
		const pattern = /\{\{([^{}]+)\}\}/g;
		let offset = 0;
		for (const match of text.matchAll(pattern)) {
			const index = match.index ?? 0;
			if (index > offset) editor.append(document.createTextNode(text.slice(offset, index)));
			editor.append(RequestStudio.token(match[1] ?? ""), document.createTextNode("\u200b"), );
			offset = index + match[0].length;
		}
		if (offset < text.length) editor.append(document.createTextNode(text.slice(offset)));
		if (!editor.childNodes.length) editor.append(document.createTextNode(""));
	};
	/** @param {string} name @returns {HTMLElement} */
	static token = name => {
		const token = document.createElement("span");
		token.className = "token-pill";
		token.setAttribute("data-token", name);
		token.contentEditable = "false";
		token.setAttribute("aria-label", `Variable ${name}`);
		token.textContent = name;
		return token;
	};
	/** @param {HTMLElement} editor @returns {string} */
	static editorText = editor => {
		/** @param {Node} node @returns {string} */
		const serialize = node => {
			if (node instanceof Text) return node.data.replaceAll("\u200b", "");
			if (!(node instanceof HTMLElement)) return "";
			if (node.classList.contains("token-pill")) return `{{${node.getAttribute("data-token") ?? ""}}}`;
			if (node instanceof HTMLElement && node.tagName === "BR") return "\n";
			const content = [...node.childNodes].map(serialize).join("");
			return node === editor || ["SPAN"].includes(node.tagName) ? content : `${content}\n`;
		};
		return serialize(editor).replace(/\n$/, "");
	};
	/**
	 * Re-render all rows of one request section.
	 *
	 * @param {RowKind} kind
	 */
	renderRows(kind) {
		const table = this.el[`${kind}_table`];
		table.replaceChildren(...this.rows[kind].map((row, index) => this.row(kind, row, index)), );
		this.el[`${kind}_count`].textContent = String(this.rows[kind].filter(({
			enabled
		}) => enabled).length, );
	}
	/**
	 * Create one editable row for a request section.
	 *
	 * @param {RowKind} kind
	 * @param {RequestRow} row
	 * @param {number} index
	 * @returns {HTMLElement} 
	 */
	row(kind, row, index) {
		const node = /** @type {HTMLElement} */ (this.el.row_template.content.firstElementChild?.cloneNode(true));
		const enabled = /** @type {HTMLInputElement} */ (node.querySelector(".enabled"));
		const key = /** @type {HTMLElement} */ (node.querySelector(".key"));
		const value = /** @type {HTMLElement} */ (node.querySelector(".value"));
		enabled.checked = row.enabled;
		RequestStudio.setEditorText(key, row.key);
		RequestStudio.setEditorText(value, row.value);
		enabled.addEventListener("change", () => this.changeRow(kind, index, "enabled", enabled.checked), );
		key.addEventListener("input", () => this.changeRow(kind, index, "key", RequestStudio.editorText(key)), );
		value.addEventListener("input", () => this.changeRow(kind, index, "value", RequestStudio.editorText(value)), );
		/** @type {HTMLButtonElement} */
		(node.querySelector(".delete")).addEventListener("click", () => {
			this.rows[kind].splice(index, 1);
			this.renderRows(kind);
			this.updateUrl();
		});
		return node;
	}
	/**
	 * Apply an edit to one row field.
	 *
	 * @param {RowKind} kind
	 * @param {number} index
	 * @param {keyof RequestRow} property
	 * @param {boolean | string} value 
	 */
	changeRow(kind, index, property, value) {
		const row = this.rows[kind][index];
		if (!row) return;
		if (property === "enabled") row.enabled = value === true;
		else row[property] = String(value);
		this.el[`${kind}_count`].textContent = String(this.rows[kind].filter(({
			enabled
		}) => enabled).length, );
		this.updateUrl();
	}
	/**
	 * Append a blank row to a request section.
	 *
	 * @param {RowKind} kind
	 */
	addRow(kind) {
		this.rows[kind].push({
			enabled: true,
			key: "",
			value: "",
		});
		this.renderRows(kind);
		const key = this.el[`${kind}_table`].querySelector(".row:last-child .key");
		if (key instanceof HTMLElement) key.focus();
	}
	/**
	 * Render the variables table.
	 */
	renderVariables() {
		this.el.variable_list.replaceChildren(...this.variables.map((variable, index) => this.variable(variable, index), ), );
		this.updateUrl();
	}
	/**
	 * Create one variable row.
	 *
	 * @param {Variable} variable
	 * @param {number} index
	 * @returns {HTMLElement} 
	 */
	variable(variable, index) {
		const node = /** @type {HTMLElement} */ (this.el.variable_template.content.firstElementChild?.cloneNode(true));
		const name = /** @type {HTMLInputElement} */ (node.querySelector(".v-name"));
		const value = /** @type {HTMLInputElement} */ (node.querySelector(".v-value"));
		const secret = /** @type {HTMLButtonElement} */ (node.querySelector(".secret"));
		name.setAttribute("value", variable.name);
		value.value = variable.value;
		value.type = variable.secret ? "password" : "text";
		secret.setAttribute("aria-pressed", String(variable.secret));
		name.addEventListener("input", () => {
			const current = this.variables[index];
			if (current) current.name = name.value;
			this.updateUrl();
		});
		value.addEventListener("input", () => {
			const current = this.variables[index];
			if (current) current.value = value.value;
			this.updateUrl();
		});
		secret.addEventListener("click", () => {
			const current = this.variables[index];
			if (current) current.secret = !current.secret;
			this.renderVariables();
		});
		/** @type {HTMLButtonElement} */
		(node.querySelector(".v-delete")).addEventListener("click", () => {
			this.variables.splice(index, 1);
			this.renderVariables();
		});
		return node;
	}
	/**
	 * Append a blank variable.
	 */
	addVariable() {
		this.variables.push({
			name: `variable${this.variables.length + 1}`,
			value: "",
			secret: false,
		});
		this.renderVariables();
		const input = this.el.variable_list.querySelector(".variable:last-child .v-name", );
		if (input instanceof HTMLInputElement) input.select();
	}
	/**
	 * Switch the visible request tab.
	 *
	 * @param {string | undefined} name
	 */
	activate(name) {
		if (typeof this.closeCapture === "function") this.closeCapture();
		document.querySelectorAll("[data-tab]").forEach(tab => {
			const active = tab.getAttribute("data-tab") === name;
			tab.classList.toggle("active", active);
			tab.setAttribute("aria-selected", String(active));
		});
		document.querySelectorAll("[data-panel]").forEach(panel => {
			if (panel instanceof HTMLElement) panel.hidden = panel.getAttribute("data-panel") !== name;
		});
	}
	/**
	 * Open or close the variables drawer.
	 *
	 * @param {boolean=} force
	 */
	toggleVariables(force) {
		const open = force ?? this.el.variables.hidden !== false;
		this.el.variables.hidden = !open;
		this.el.variables.setAttribute("aria-hidden", String(!open));
		this.el.shell.classList.toggle("open", open);
		this.el.variables_toggle.setAttribute("aria-expanded", String(open));
	}
	/**
	 * Build the variable-name lookup.
	 *
	 * @returns {Map<string, string>}
	 */
	map() {
		return new Map(this.variables.filter(({
			name
		}) => name.trim()).map(({
			name,
			value
		}) => [name.trim(), value]), );
	}
	/**
	 * Expand {{variable}} tokens in text.
	 *
	 * @param {string} value
	 * @returns {string} 
	 */
	resolve(value) {
		const map = this.map();
		return value.replace(/\{\{([^{}]+)\}\}/g,
			(token, name) => map.get(name) ?? token, );
	}
	/**
	 * Build the resolved request URL.
	 *
	 * @returns {URL}
	 */
	url() {
		const url = new URL(this.resolve(RequestStudio.editorText(this.el.url).trim()), );
		this.rows.params.filter(({
			enabled,
			key
		}) => enabled && key).forEach(({
			key,
			value
		}) => {
			url.searchParams.set(this.resolve(key), this.resolve(value));
		});
		return url;
	}
	/**
	 * Refresh the resolved-URL preview.
	 */
	updateUrl() {
		try {
			this.el.resolved_url.textContent = (this.transport() === "websocket" ? this.webSocketUrl() : this.url()).toString();
		} catch {
			this.el.resolved_url.textContent = "Enter a valid absolute URL";
		}
	}
	/**
	 * Handle token-editor input events.
	 *
	 * @param {Event} event
	 */
	editorInput(event) {
		const editor = event.target instanceof Element ? event.target.closest(".token-editor") : null;
		if (!(editor instanceof HTMLElement)) return;
		this.updateUrl();
		this.detectCompletion(editor);
	}
	/**
	 * Detect an in-progress variable completion.
	 *
	 * @param {HTMLElement} editor
	 */
	detectCompletion(editor) {
		const selection = window.getSelection();
		if (!selection?.rangeCount || !editor.contains(selection.anchorNode) || !(selection.anchorNode instanceof Text)) {
			this.hideCompletion();
			return;
		}
		const node = selection.anchorNode;
		const offset = selection.anchorOffset;
		const before = node.data.slice(0, offset);
		const match = before.match(/@([A-Za-z0-9_./-]*)$/);
		if (!match) {
			this.hideCompletion();
			return;
		}
		const query = match[1] ?? "";
		const expanded = this.completion.editor === editor ? this.completion.expanded : new Set();
		this.completion = {
			editor,
			startNode: node,
			startOffset: offset - match[0].length,
			query,
			selected: 0,
			items: this.visibleItems(query, expanded),
			expanded,
		};
		this.renderCompletion();
	}
	/**
	 * Flatten the completion tree: every expanded branch is followed by its
	 * own children, one level deeper.
	 *
	 * @param {string} query
	 * @param {Set<string>} expanded
	 * @returns {CompletionItem[]}
	 */
	visibleItems(query, expanded) {
		/** @param {CompletionItem[]} level @returns {CompletionItem[]} */
		const flatten = level => level.flatMap(item => [
			item, ...(item.branch && expanded.has(item.path) ? flatten(this.hierarchy(`${item.path}/`).map(child => ({
				...child,
				depth: item.depth + 1,
			})), ) : []),
		]);
		return flatten(this.hierarchy(query));
	}
	/**
	 * List completion candidates below a variable path.
	 *
	 * @param {string} query
	 * @returns {CompletionItem[]} 
	 */
	hierarchy(query) {
		const slash = query.lastIndexOf("/");
		const parent = slash < 0 ? "" : query.slice(0, slash + 1);
		const leaf = slash < 0 ? query : query.slice(slash + 1);
		const names = this.variables.map(({
			name
		}) => name).filter(name => name.startsWith(parent));
		const branches = new Map();
		names.forEach(name => {
			const rest = name.slice(parent.length);
			const [segment = "", ...tail] = rest.split("/");
			if (!segment.toLowerCase().startsWith(leaf.toLowerCase())) return;
			const path = `${parent}${segment}`;
			const branch = tail.length > 0;
			if (!branches.has(path) || !branch) branches.set(path, {
				path,
				segment,
				branch,
				depth: 0,
				count: branch ? this.variables.filter(({
					name: variableName
				}) => variableName.startsWith(`${path}/`), ).length : 0,
				variable: branch ? null : this.variables.find(
					({
						name: variableName
					}) => variableName === path, ),
			});
		});
		return [...branches.values()].sort(
			(left, right) => Number(left.branch) - Number(right.branch) || left.segment.localeCompare(right.segment), );
	}
	/**
	 * Render the completion popup.
	 *
	 * @returns {void}
	 */
	renderCompletion() {
		const {
			editor,
			items,
			selected,
			query
		} = this.completion;
		if (!editor || !items.length) {
			this.hideCompletion();
			return;
		}
		const {
			expanded
		} = this.completion;
		this.el.autocomplete.replaceChildren();
		/** @type {HTMLElement[]} Container that receives each depth's rows. */
		const hosts = [this.el.autocomplete];
		/** @type {HTMLElement | null} */
		let selectedRow = null;
		items.forEach((item, index) => {
			const open = item.branch && expanded.has(item.path);
			const button = document.createElement("button");
			button.type = "button";
			button.className = `suggestion${index === selected ? " selected" : ""}`;
			button.setAttribute("role", item.branch ? "treeitem" : "option");
			button.setAttribute("aria-selected", String(index === selected));
			if (item.branch) button.setAttribute("aria-expanded", String(open));
			const mark = document.createElement(item.branch ? "i" : "b");
			mark.className = "suggestion-mark";
			mark.textContent = item.branch ? "" : "@";
			const name = document.createElement("span");
			name.textContent = item.segment;
			const value = document.createElement("small");
			value.textContent = item.branch ? String(item.count) : item.variable?.secret ? "••••••••" : (item.variable?.value ?? "");
			button.append(mark, name, value);
			button.addEventListener("pointerdown", pointerEvent => {
				pointerEvent.preventDefault();
				this.choose(item);
			});
			(hosts[item.depth] ?? this.el.autocomplete).append(button);
			if (index === selected) selectedRow = button;
			if (!open) return;
			const group = document.createElement("div");
			group.className = "suggestion-group";
			group.setAttribute("role", "group");
			(hosts[item.depth] ?? this.el.autocomplete).append(group);
			hosts[item.depth + 1] = group;
		});
		this.el.autocomplete.setAttribute("role", "tree");
		document.body.append(this.el.autocomplete);
		this.el.autocomplete.hidden = false;
		this.el.autocomplete.setAttribute("data-depth", String(query.split("/").length - 1), );
		this.positionCompletion(editor);
		/** @type {HTMLElement | null} */
		(selectedRow)?.scrollIntoView({
			block: "nearest",
		});
	}
	/**
	 * Expand or collapse one branch of the completion tree in place.
	 *
	 * @param {CompletionItem} item
	 * @param {boolean} [force] Open (true) or close (false) instead of toggling.
	 */
	toggleBranch(item, force) {
		const {
			expanded,
			query,
			items,
			selected
		} = this.completion;
		const open = force ?? !expanded.has(item.path);
		if (open) expanded.add(item.path);
		else expanded.delete(item.path);
		const focusPath = (items[selected] ?? item).path;
		const next = this.visibleItems(query, expanded);
		this.completion.items = next;
		this.completion.selected = Math.max(0, next.findIndex(({
			path
		}) => path === focusPath), );
		this.renderCompletion();
	}
	/**
	 * Arrow-key tree navigation: right opens a branch (or steps into it),
	 * left closes it (or steps out to its parent).
	 *
	 * @param {"ArrowRight" | "ArrowLeft"} key
	 * @returns {boolean} Whether the key was consumed.
	 */
	treeKey(key) {
		const {
			items,
			selected,
			expanded
		} = this.completion;
		const item = items[selected];
		if (!item) return false;
		const open = item.branch && expanded.has(item.path);
		if (key === "ArrowRight") {
			if (!item.branch) return false;
			if (!open) this.toggleBranch(item, true);
			else this.move(1);
			return true;
		}
		if (open) {
			this.toggleBranch(item, false);
			return true;
		}
		if (item.depth === 0) return false;
		for (let index = selected - 1; index >= 0; index -= 1)
			if ((items[index]?.depth ?? 0) < item.depth) {
				this.completion.selected = index;
				this.renderCompletion();
				return true;
			}
		return false;
	}
	/**
	 * Position the completion popup at the caret.
	 *
	 * @param {HTMLElement} editor
	 */
	positionCompletion(editor) {
		const selection = window.getSelection();
		const range = selection?.rangeCount ? selection.getRangeAt(0).cloneRange() : null;
		range?.collapse(true);
		const caret = range?.getBoundingClientRect();
		const fallback = editor.getBoundingClientRect();
		const anchorLeft = caret?.width || caret?.height ? caret.left : fallback.left;
		const anchorBottom = caret?.width || caret?.height ? caret.bottom : fallback.bottom;
		const popup = this.el.autocomplete.getBoundingClientRect();
		const gap = 6;
		const margin = 12;
		const left = Math.max(margin, Math.min(anchorLeft, window.innerWidth - popup.width - margin), );
		const below = anchorBottom + gap;
		const top = below + popup.height <= window.innerHeight - margin ? below : Math.max(margin, (caret?.top ?? fallback.top) - popup.height - gap);
		this.el.autocomplete.style.setProperty("--dynamic-completion-left", `${Math.round(left)}px`, );
		this.el.autocomplete.style.setProperty("--dynamic-completion-top", `${Math.round(top)}px`, );
	}
	/**
	 * Apply one completion candidate.
	 *
	 * @param {CompletionItem} item
	 */
	choose(item) {
		if (item.branch) {
			this.toggleBranch(item);
			return;
		}
		this.insertToken(item.path);
	}
	/**
	 * Replace the query text with the chosen variable.
	 *
	 * @param {string} text
	 */
	replaceCompletionText(text) {
		const {
			editor,
			startNode,
			startOffset
		} = this.completion;
		const selection = window.getSelection();
		if (!editor || !startNode || !selection?.rangeCount) return;
		const range = document.createRange();
		range.setStart(startNode, startOffset);
		if (!selection.anchorNode) return;
		range.setEnd(selection.anchorNode, selection.anchorOffset);
		range.deleteContents();
		const node = document.createTextNode(text);
		range.insertNode(node);
		range.setStart(node, node.data.length);
		range.collapse(true);
		selection.removeAllRanges();
		selection.addRange(range);
	}
	/**
	 * Insert a variable token at the caret.
	 *
	 * @param {string} name
	 */
	insertToken(name) {
		const {
			editor,
			startNode,
			startOffset
		} = this.completion;
		const selection = window.getSelection();
		if (!(editor instanceof HTMLElement) || !(startNode instanceof Text) || !startNode.isConnected || !selection?.rangeCount || selection.anchorNode !== startNode) return;
		const endOffset = selection.anchorOffset;
		if (endOffset < startOffset) return;
		const before = startNode.data.slice(0, startOffset);
		const after = startNode.data.slice(endOffset);
		const nodes = [];
		if (before) nodes.push(document.createTextNode(before));
		const token = RequestStudio.token(name);
		const boundary = document.createTextNode("\u200b");
		nodes.push(token, boundary);
		if (after) nodes.push(document.createTextNode(after));
		startNode.replaceWith(...nodes);
		const range = document.createRange();
		range.setStart(boundary, 1);
		range.collapse(true);
		selection.removeAllRanges();
		selection.addRange(range);
		this.hideCompletion();
		editor.dispatchEvent(new InputEvent("input", {
			bubbles: true,
			inputType: "insertReplacementText",
			data: null,
		}), );
		editor.focus({
			preventScroll: true,
		});
		this.selectionChanged();
	}
	/**
	 * Handle editor keydown events.
	 *
	 * @param {KeyboardEvent} event
	 */
	keydown(event) {
		const editor = event.target instanceof Element ? event.target.closest(".token-editor") : null;
		if (editor instanceof HTMLElement && (event.key === "Backspace" || event.key === "Delete") && this.removeSelectedToken(editor)) {
			event.preventDefault();
			return;
		}
		if (editor instanceof HTMLElement && (event.key === "Backspace" || event.key === "Delete") && this.dissolveAdjacentToken(editor, event.key)) {
			event.preventDefault();
			return;
		}
		if (this.el.autocomplete.hidden || !this.completion.editor) return;
		if (
			(event.key === " " || event.key === "Enter") && this.commitExactCompletion()) {
			event.preventDefault();
			return;
		}
		if (
			(event.key === "ArrowRight" || event.key === "ArrowLeft") && this.treeKey(event.key)) {
			event.preventDefault();
			return;
		}
		const actions = new Map([
			["ArrowDown", () => this.move(1)],
			["ArrowUp", () => this.move(-1)],
			["Enter", () => this.chooseSelected()],
			["Tab", () => this.chooseSelected()],
			["Escape", () => this.hideCompletion()],
		]);
		if (!actions.has(event.key)) return;
		event.preventDefault();
		actions.get(event.key)?.();
	}
	/** @param {Selection | null} selection @param {"Backspace" | "Delete"} key @returns {Node | null} */
	static adjacentToken = (selection, key) => {
		if (!selection?.isCollapsed || !selection.rangeCount) return null;
		const node = selection.anchorNode;
		const offset = selection.anchorOffset;
		if (node instanceof Text) {
			if (key === "Backspace" && node.data === "\u200b" && offset === 1) return node.previousSibling;
			if (key === "Backspace" && offset === 0) return node.previousSibling;
			if (key === "Delete" && node.data === "\u200b" && offset === 0) return node.previousSibling;
			if (key === "Delete" && offset === node.data.length) return node.nextSibling;
		}
		if (node instanceof HTMLElement) {
			const index = offset + (key === "Backspace" ? -1 : 0);
			return node.childNodes[index] ?? null;
		}
		return null;
	};
	/**
	 * Dissolve a boundary token on Backspace or Delete.
	 *
	 * @param {HTMLElement} editor
	 * @param {"Backspace" | "Delete"} key
	 * @returns {boolean} 
	 */
	dissolveAdjacentToken(editor, key) {
		const selection = window.getSelection();
		if (!selection?.isCollapsed || !selection.rangeCount || !editor.contains(selection.anchorNode)) return false;
		const token = RequestStudio.adjacentToken(selection, key);
		if (!(token instanceof HTMLElement) || !token.classList.contains("token-pill")) return false;
		const name = token.getAttribute("data-token") ?? "";
		const shortened = key === "Backspace" ? name.slice(0, -1) : name.slice(1);
		const text = document.createTextNode(`@${shortened}`);
		const boundary = token.nextSibling instanceof Text && token.nextSibling.data === "\u200b" ? token.nextSibling : null;
		token.replaceWith(text);
		boundary?.remove();
		const range = document.createRange();
		range.setStart(text, key === "Backspace" ? text.data.length : Math.min(1, text.data.length), );
		range.collapse(true);
		selection.removeAllRanges();
		selection.addRange(range);
		editor.dispatchEvent(new InputEvent("input", {
			bubbles: true,
			inputType: key === "Backspace" ? "deleteContentBackward" : "deleteContentForward",
			data: null,
		}), );
		this.detectCompletion(editor);
		return true;
	}
	/**
	 * Sanitize token-editor input before insertion.
	 *
	 * @param {Event} event
	 */
	beforeInput(event) {
		if (!(event instanceof InputEvent)) return;
		const editor = event.target instanceof Element ? event.target.closest(".token-editor") : null;
		if (!(editor instanceof HTMLElement)) return;
		const multiline = editor.getAttribute("aria-multiline") === "true";
		if (!multiline && ["insertParagraph", "insertLineBreak"].includes(event.inputType)) {
			event.preventDefault();
			return;
		}
		if (!multiline && event.inputType === "insertText" && event.data !== null && RequestStudio.insertAtElementBoundary(editor, event.data)) {
			event.preventDefault();
			return;
		}
		if (!["deleteContentBackward", "deleteContentForward"].includes(event.inputType, )) return;
		const key = event.inputType === "deleteContentBackward" ? "Backspace" : "Delete";
		if (!this.dissolveAdjacentToken(editor, key)) return;
		event.preventDefault();
	}
	/** @param {HTMLElement} editor @param {string} text @returns {boolean} */
	static insertAtElementBoundary = (editor, text) => {
		const selection = window.getSelection();
		if (!selection?.isCollapsed || !selection.rangeCount || selection.anchorNode !== editor) return false;
		const offset = selection.anchorOffset;
		const node = document.createTextNode(text.replace(/[\r\n]+/g, " "));
		const reference = editor.childNodes[offset] ?? null;
		editor.insertBefore(node, reference);
		const range = document.createRange();
		range.setStart(node, node.data.length);
		range.collapse(true);
		selection.removeAllRanges();
		selection.addRange(range);
		editor.dispatchEvent(new InputEvent("input", {
			bubbles: true,
			inputType: "insertText",
			data: node.data,
		}), );
		return true;
	};
	/** @param {ClipboardEvent} event */
	static paste = event => {
		const editor = event.target instanceof Element ? event.target.closest(".token-editor") : null;
		if (!(editor instanceof HTMLElement) || editor.getAttribute("aria-multiline") === "true") return;
		const text = event.clipboardData?.getData("text/plain");
		if (text === undefined) return;
		event.preventDefault();
		const normalized = text.replace(/[\r\n]+/g, " ");
		const selection = window.getSelection();
		if (!selection?.rangeCount || !editor.contains(selection.anchorNode)) return;
		const range = selection.getRangeAt(0);
		range.deleteContents();
		const node = document.createTextNode(normalized);
		range.insertNode(node);
		range.setStart(node, node.data.length);
		range.collapse(true);
		selection.removeAllRanges();
		selection.addRange(range);
		editor.dispatchEvent(new InputEvent("input", {
			bubbles: true,
			inputType: "insertFromPaste",
			data: normalized,
		}), );
	};
	/**
	 * Serialize the selection to plain text for copy and cut.
	 *
	 * @param {ClipboardEvent} event
	 * @param {boolean} cut 
	 * @returns {void}
	 */
	clipboard(event, cut) {
		const editor = event.target instanceof Element ? event.target.closest(".token-editor") : null;
		const selection = window.getSelection();
		if (!(editor instanceof HTMLElement) || !selection || selection.isCollapsed || !editor.contains(selection.anchorNode) || !editor.contains(selection.focusNode)) return;
		const fragment = selection.getRangeAt(0).cloneContents();
		const holder = document.createElement("div");
		holder.append(fragment);
		/** @param {Node} node @returns {string} */
		const serialize = node => {
			if (node instanceof Text) return node.data.replaceAll("\u200b", "");
			if (!(node instanceof HTMLElement)) return "";
			if (node.classList.contains("token-pill")) return `@${node.getAttribute("data-token") ?? ""}`;
			if (node instanceof HTMLElement && node.tagName === "BR") return editor.getAttribute("aria-multiline") === "true" ? "\n" : "";
			return [...node.childNodes].map(serialize).join("");
		};
		const text = [...holder.childNodes].map(serialize).join("").replace(editor.getAttribute("aria-multiline") === "true" ? /\u200b/g : /[\r\n\u200b]+/g, "", );
		event.preventDefault();
		event.clipboardData?.setData("text/plain", text);
		if (cut) {
			selection.deleteFromDocument();
			editor.dispatchEvent(new InputEvent("input", {
				bubbles: true,
				inputType: "deleteByCut",
				data: null,
			}), );
			this.selectionChanged();
		}
	}
	/**
	 * Clear the token-selection highlight.
	 */
	clearSelectedToken() {
		if (!(this.selectedToken instanceof HTMLElement)) return;
		this.selectedToken.classList.remove("token-selected");
		this.selectedToken = null;
	}
	/**
	 * Remove the selected token from its editor.
	 *
	 * @param {HTMLElement} editor
	 * @returns {boolean} 
	 */
	removeSelectedToken(editor) {
		const token = this.selectedToken;
		if (!(token instanceof HTMLElement) || !token.isConnected || token.closest(".token-editor") !== editor) return false;
		const next = token.nextSibling;
		const previous = token.previousSibling;
		token.remove();
		this.selectedToken = null;
		const target = next instanceof Text ? next : previous instanceof Text ? previous : document.createTextNode("");
		if (!target.isConnected) editor.append(target);
		const range = document.createRange();
		range.setStart(target, next instanceof Text ? 0 : target.data.length);
		range.collapse(true);
		const selection = window.getSelection();
		selection?.removeAllRanges();
		selection?.addRange(range);
		editor.dispatchEvent(new InputEvent("input", {
			bubbles: true,
			inputType: "deleteContentBackward",
			data: null,
		}), );
		return true;
	}
	/**
	 * Select a token on pointer press.
	 *
	 * @param {PointerEvent} event
	 */
	tokenPointerDown(event) {
		const token = event.target instanceof Element ? event.target.closest(".token-pill") : null;
		if (!(token instanceof HTMLElement)) {
			this.clearSelectedToken();
			return;
		}
		const editor = token.closest(".token-editor");
		if (!(editor instanceof HTMLElement)) return;
		event.preventDefault();
		this.clearSelectedToken();
		this.selectedToken = token;
		token.classList.add("token-selected");
		const selection = window.getSelection();
		const range = document.createRange();
		range.selectNode(token);
		selection?.removeAllRanges();
		selection?.addRange(range);
		editor.focus({
			preventScroll: true,
		});
		this.hideCompletion();
	}
	/** @param {HTMLElement} token @param {boolean} before @returns {Text} */
	static tokenBoundary = (token, before) => {
		const sibling = before ? token.previousSibling : token.nextSibling;
		if (sibling instanceof Text) {
			if (sibling.data.includes("\u200b") || sibling.data.length > 0) return sibling;
		}
		const boundary = document.createTextNode("\u200b");
		if (before) token.before(boundary);
		else token.after(boundary);
		return boundary;
	};
	static clearBoundaryCarets = () => {
		document.querySelectorAll(".token-pill.caret-after,.token-pill.caret-before").forEach(token => {
			token.classList.remove("caret-after", "caret-before");
		});
	};
	/** @param {Selection | null} selection @returns {TokenBoundary | null} */
	static boundaryCaretToken = selection => {
		if (!selection?.isCollapsed || !selection.rangeCount) return null;
		const node = selection.anchorNode;
		const offset = selection.anchorOffset;
		/** @param {Node | null} candidate @param {"before" | "after"} side @returns {TokenBoundary | null} */
		const result = (candidate, side) => candidate instanceof HTMLElement && candidate.classList.contains("token-pill") ? {
			token: candidate,
			side,
		} : null;
		if (node instanceof Text) {
			if (offset === 0) {
				const previous = node.previousSibling;
				if (result(previous, "after")) return result(previous, "after");
			}
			if (offset === node.data.length) {
				const next = node.nextSibling;
				if (result(next, "before")) return result(next, "before");
			}
			if (node.data === "\u200b") {
				if (offset === 1 && result(node.previousSibling, "after")) return result(node.previousSibling, "after");
				if (offset === 0 && result(node.nextSibling, "before")) return result(node.nextSibling, "before");
			}
		}
		if (node instanceof HTMLElement && node.classList.contains("token-editor")) {
			const before = node.childNodes[offset - 1] ?? null;
			const after = node.childNodes[offset] ?? null;
			if (result(before, "after")) return result(before, "after");
			if (result(after, "before")) return result(after, "before");
		}
		return null;
	};
	/**
	 * Refresh boundary carets when the selection moves.
	 */
	selectionChanged() {
		const selection = window.getSelection();
		const range = selection?.rangeCount ? selection.getRangeAt(0) : null;
		RequestStudio.clearBoundaryCarets();
		const boundary = RequestStudio.boundaryCaretToken(selection);
		if (boundary && boundary.token.closest(".token-editor")?.matches(":focus-within")) boundary.token.classList.add(boundary.side === "after" ? "caret-after" : "caret-before", );
		if (this.selectedToken instanceof HTMLElement && range && !range.intersectsNode(this.selectedToken)) this.clearSelectedToken();
		document.querySelectorAll(".token-pill.range-selected").forEach(token => {
			token.classList.remove("range-selected");
		});
		if (!selection || selection.isCollapsed || !range) return;
		document.querySelectorAll(".token-pill").forEach(token => {
			if (range.intersectsNode(token)) token.classList.add("range-selected");
		});
	}
	/**
	 * Accept an exact variable-name completion.
	 *
	 * @returns {boolean}
	 */
	commitExactCompletion() {
		const query = this.completion.query;
		const exact = this.variables.filter(({
			name
		}) => name === query);
		const competing = this.variables.filter(
			({
				name
			}) => name.startsWith(query) && name !== query, );
		if (exact.length !== 1 || competing.length) return false;
		this.insertToken(query);
		return true;
	}
	/**
	 * Move the highlighted completion entry.
	 *
	 * @param {number} delta
	 */
	move(delta) {
		const size = this.completion.items.length;
		this.completion.selected = (this.completion.selected + delta + size) % size;
		this.renderCompletion();
	}
	/**
	 * Accept the highlighted completion.
	 */
	chooseSelected() {
		const item = this.completion.items[this.completion.selected];
		if (item) this.choose(item);
	}
	/**
	 * Hide the completion popup.
	 */
	hideCompletion() {
		this.el.autocomplete.hidden = true;
		this.completion = {
			editor: null,
			startNode: null,
			startOffset: 0,
			query: "",
			selected: 0,
			items: [],
			expanded: new Set(),
		};
		document.body.append(this.el.autocomplete);
	}
	/**
	 * Close popups on pointer-down outside them.
	 *
	 * @param {PointerEvent} event
	 */
	outside(event) {
		if (!(event.target instanceof Node) || !this.el.autocomplete.contains(event.target) && !(event.target instanceof Element && event.target.closest(".token-editor"))) this.hideCompletion();
	}
	/**
	 * Collect the enabled request headers.
	 *
	 * @returns {Headers}
	 */
	headers() {
		const headers = new Headers();
		this.rows.headers.filter(({
			enabled,
			key
		}) => enabled && key).forEach(({
			key,
			value
		}) => {
			headers.set(this.resolve(key), this.resolve(value));
		});
		return headers;
	}
	/**
	 * Return the active transport kind.
	 *
	 * @returns {Transport}
	 */
	transport() {
		return this.el.transport.value === "websocket" ? "websocket" : "http";
	}
	/**
	 * Update the send button label.
	 *
	 * @param {string} label
	 */
	sendLabel(label) {
		const first = this.el.send.firstChild;
		if (first) first.textContent = label;
	}
	/**
	 * Apply transport-specific UI state.
	 */
	setTransport() {
		const websocket = this.transport() === "websocket";
		this.el.method.hidden = websocket;
		const methodSelect = this.el.method.closest(".select");
		if (methodSelect instanceof HTMLElement) methodSelect.hidden = websocket;
		document.querySelectorAll(".websocket-only").forEach(element => {
			if (element instanceof HTMLElement && element.matches("[role='tab']")) element.hidden = !websocket;
		});
		document.getElementById("body-tab")?.toggleAttribute("hidden", websocket);
		this.sendLabel(websocket ? (this.socket ? " Disconnect " : " Connect ") : " Send ", );
		this.el.url.setAttribute("data-placeholder", websocket ? "wss://host/path" : "Request URL", );
		if (websocket) this.activate("messages");
		else if (document.querySelector("[data-tab].active")?.getAttribute("data-tab") === "messages") this.activate("params");
		this.updateUrl();
	}
	/**
	 * Resolve the request URL to a ws: or wss: URL.
	 *
	 * @returns {URL}
	 * @throws {TypeError}
	 */
	webSocketUrl() {
		const url = this.url();
		if (url.protocol === "https:") url.protocol = "wss:";
		else if (url.protocol === "http:") url.protocol = "ws:";
		if (!["ws:", "wss:"].includes(url.protocol)) throw new TypeError("WebSocket URL must use ws:// or wss://.");
		return url;
	}
	/**
	 * Connect or disconnect the WebSocket.
	 */
	toggleWebSocket() {
		if (this.socket) {
			this.socket.close(1000, "Closed by user");
			return;
		}
		let url;
		try {
			url = this.webSocketUrl();
		} catch (error) {
			this.webSocketState("error", error instanceof Error ? error.message : "Invalid WebSocket URL", );
			return;
		}
		const protocols = this.el.ws_protocols.value.split(",").map(value => value.trim()).filter(Boolean);
		this.webSocketState("connecting", "Connecting…");
		try {
			const socket = protocols.length ? new WebSocket(url, protocols) : new WebSocket(url);
			this.socket = socket;
			this.sendLabel(" Disconnect ");
			socket.addEventListener("open", () => {
				if (this.socket !== socket) return;
				this.webSocketState("open", socket.protocol ? `Connected · ${socket.protocol}` : "Connected", );
				this.appendWebSocketLog("system", "Connection opened");
			});
			socket.addEventListener("message", event => {
				const value = typeof event.data === "string" ? event.data : `[Binary frame · ${event.data instanceof Blob ? event.data.size : "?"} bytes]`;
				this.appendWebSocketLog("received", value);
				this.response(value, "success", "WebSocket message");
			});
			socket.addEventListener("error", () => {
				if (this.socket === socket) this.webSocketState("error", "Connection error");
				this.appendWebSocketLog("error", "WebSocket connection error");
			});
			socket.addEventListener("close", event => {
				if (this.socket === socket) this.socket = null;
				this.sendLabel(" Connect ");
				this.webSocketState("closed", `Disconnected · ${event.code}${event.reason ? ` · ${event.reason}` : ""}`, );
				this.appendWebSocketLog("system", `Connection closed · ${event.code}${event.reason ? ` · ${event.reason}` : ""}`, );
			});
		} catch (error) {
			this.socket = null;
			this.sendLabel(" Connect ");
			this.webSocketState("error", error instanceof Error ? error.message : "Could not create WebSocket", );
		}
	}
	/**
	 * Update the connection-state indicator.
	 *
	 * @param {"closed" | "connecting" | "open" | "error"} state *
	 * @param {string} label
	 
	 */
	webSocketState(state, label) {
		this.el.ws_state.setAttribute("data-state", state);
		const last = this.el.ws_state.lastChild;
		if (last) last.textContent = ` ${label}`;
		this.el.ws_send.disabled = state !== "open";
	}
	/**
	 * Send the composed WebSocket message.
	 */
	sendWebSocketMessage() {
		if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return;
		const message = this.resolve(RequestStudio.editorText(this.el.ws_message));
		this.socket.send(message);
		this.appendWebSocketLog("sent", message);
	}
	/**
	 * Append a frame to the WebSocket log.
	 *
	 * @param {"sent" | "received" | "error" | "system"} kind *
	 * @param {string} value
	 
	 */
	appendWebSocketLog(kind, value) {
		this.el.ws_log.querySelector(".ws-empty")?.remove();
		const item = document.createElement("div");
		item.className = `ws-frame ${kind}`;
		const meta = document.createElement("span");
		meta.className = "ws-frame-meta";
		meta.textContent = `${kind === "sent" ? "↑ Sent" : kind === "received" ? "↓ Received" : kind === "error" ? "! Error" : "• Event"} · ${new Date().toLocaleTimeString()}`;
		const payload = document.createElement("pre");
		payload.textContent = value;
		item.append(meta, payload);
		this.el.ws_log.append(item);
		this.el.ws_log.scrollTop = this.el.ws_log.scrollHeight;
		this.wsMessageCount += 1;
		this.el.messages_count.textContent = String(this.wsMessageCount);
	}
	/**
	 * Reset the WebSocket message log.
	 */
	clearWebSocketLog() {
		this.el.ws_log.replaceChildren();
		const empty = document.createElement("p");
		empty.className = "ws-empty";
		empty.textContent = this.socket ? "No messages yet." : "Connect to send and receive messages.";
		this.el.ws_log.append(empty);
		this.wsMessageCount = 0;
		this.el.messages_count.textContent = "0";
	}
	/**
	 * Dispatch the request through the active transport.
	 */
	async send() {
		if (this.el.transport.value === "websocket") {
			this.toggleWebSocket();
			return;
		}
		let url;
		try {
			url = this.url();
		} catch {
			this.response("Invalid URL. Use an absolute URL before sending.", "error", "Invalid URL", );
			return;
		}
		const headers = this.headers();
		const method = this.el.method.value;
		const hasBody = !["GET", "HEAD"].includes(method);
		/** @type {Record<string, string>} */
		const types = {
			json: "application/json",
			text: "text/plain",
			xml: "application/xml",
		};
		if (hasBody && !headers.has("Content-Type")) headers.set("Content-Type", types[this.el.body_format.value] ?? "text/plain", );
		this.response("Sending request…", "", "Sending");
		const started = performance.now();
		try {
			const result = await fetch(url, {
				method,
				headers,
				body: hasBody ? this.resolve(RequestStudio.editorText(this.el.body)) : null,
				credentials: "include",
			});
			const elapsed = Math.round(performance.now() - started);
			const text = await result.text();
			this.response(result.headers.get("content-type")?.includes("json") ? RequestStudio.json(text) : text || "(empty response)", result.ok ? "success" : "error", `${result.status} ${result.statusText} · ${elapsed} ms`, );
		} catch (error) {
			this.response(`Request failed. Browser CORS rules still apply. Explicit Cookie headers are represented by the editor but browser fetch uses browser-managed cookies.\n\n${error instanceof Error ? error.message : String(error)}`, "error", "Network error", );
		}
	}
	/**
	 * Render a text or JSON response.
	 *
	 * @param {string} text
	 * @param {string} state
	 * @param {string} label 
	 */
	response(text, state, label) {
		this.el.response_view.classList.remove("json-mode");
		this.el.response_text.textContent = text;
		if (typeof text === "string") {
			try {
				this.showJson(JSON.parse(text));
			} catch {
				/* Plain response stays plain text. */
			}
		}
		this.el.response_meta.className = state;
		if (this.el.response_meta.lastChild) this.el.response_meta.lastChild.textContent = ` ${label}`;
	}
	/**
	 * Copy the response to the clipboard.
	 */
	async copy() {
		await navigator.clipboard.writeText(this.el.response_text.textContent ?? "", );
		this.toast("Response copied");
	}
	/**
	 * Show a transient status toast.
	 *
	 * @param {string} text
	 */
	toast(text) {
		clearTimeout(this.toastTimer);
		this.el.toast.textContent = text;
		this.el.toast.hidden = false;
		this.toastTimer = setTimeout(() => {
			this.el.toast.hidden = true;
		}, 1800);
	}
	/**
	 * Tint the method selector by its value.
	 */
	setMethodTone() {
		this.el.method.setAttribute("data-method", this.el.method.value);
	}
	/**
	 * Build one JSON tree node.
	 *
	 * @param {unknown} value
	 * @param {string} path
	 * @param {string | null} key
	 * @param {boolean} selectable
	 * @returns {HTMLElement} 
	 */
	jsonNode(value, path = "$", key = null, selectable = true) {
		const row = document.createElement("div");
		row.className = "json-node";
		row.setAttribute("data-path", path);
		const line = document.createElement("div");
		line.className = "json-row";
		/** @param {string} valueText @param {boolean} container @returns {HTMLElement} */
		const makePick = (valueText, container = false) => {
			const pick = document.createElement(selectable ? "button" : "span");
			if (pick instanceof HTMLButtonElement) pick.type = "button";
			pick.className = `json-pick${container ? " container-pick" : ""}`;
			pick.setAttribute("data-path", path);
			if (pick instanceof HTMLButtonElement) this.jsonValues.set(pick, value);
			if (key !== null) {
				const keySpan = document.createElement("span");
				keySpan.className = "json-key";
				keySpan.textContent = `${JSON.stringify(key)}:`;
				pick.append(keySpan, document.createTextNode(" "));
			}
			const valueSpan = document.createElement("span");
			valueSpan.className = "json-value";
			valueSpan.textContent = valueText;
			pick.append(valueSpan);
			return pick;
		};
		if (value !== null && typeof value === "object") {
			const array = Array.isArray(value);
			const toggle = document.createElement("button");
			toggle.type = "button";
			toggle.className = "json-toggle";
			toggle.textContent = "▾";
			toggle.setAttribute("aria-label", `Collapse ${path}`);
			toggle.addEventListener("click", () => {
				const collapsed = row.classList.toggle("collapsed");
				toggle.setAttribute("aria-label", `${collapsed ? "Expand" : "Collapse"} ${path}`, );
			});
			line.append(toggle, makePick(array ? "[" : "{", true));
			const summary = document.createElement("span");
			summary.className = "json-summary";
			summary.textContent = ` ${Object.keys(value).length} ${array ? "items" : "keys"}`;
			line.append(summary);
			row.append(line);
			const children = document.createElement("div");
			children.className = "json-children";
			Object.entries(value).forEach(([childKey, childValue]) => {
				const childPath = array ? `${path}[${childKey}]` : `${path}.${childKey}`;
				children.append(this.jsonNode(childValue, childPath, array ? null : childKey, selectable, ), );
			});
			row.append(children);
			const close = document.createElement("span");
			close.className = "json-close";
			close.textContent = array ? "]" : "}";
			row.append(close);
			return row;
		}
		const spacer = document.createElement("span");
		spacer.className = "json-toggle";
		line.append(spacer);
		const type = value === null ? "null" : typeof value;
		const pick = makePick(typeof value === "string" ? JSON.stringify(value) : String(value), );
		pick.classList.add(`json-${type}`);
		line.append(pick);
		row.append(line);
		return row;
	}
	/**
	 * Render a JSON response tree.
	 *
	 * @param {unknown} value
	 */
	showJson(value) {
		this.el.response_text.replaceChildren(this.jsonNode(value));
		this.el.response_view.classList.add("json-mode");
	}
	/**
	 * Position the capture popover at a JSON pick.
	 *
	 * @param {HTMLButtonElement} button
	 */
	placeCapture(button) {
		const popup = this.el.capture;
		const margin = 8;
		const gap = 8;
		const viewport = {
			left: margin,
			top: margin,
			right: window.innerWidth - margin,
			bottom: window.innerHeight - margin,
		};
		const anchor = button.getBoundingClientRect();
		const selected = button.closest(".json-node")?.getBoundingClientRect() ?? anchor;
		const popupRect = popup.getBoundingClientRect();
		const width = Math.min(popupRect.width, viewport.right - viewport.left);
		const height = popupRect.height;
		/** @param {number} value @param {number} low @param {number} high */
		const clamp = (value, low, high) => Math.min(Math.max(value, low), Math.max(low, high));
		const candidates = [{
			side: "bottom",
			left: anchor.left,
			top: selected.bottom + gap,
			space: viewport.bottom - selected.bottom,
		}, {
			side: "top",
			left: anchor.left,
			top: selected.top - height - gap,
			space: selected.top - viewport.top,
		}, {
			side: "right",
			left: selected.right + gap,
			top: anchor.top,
			space: viewport.right - selected.right,
		}, {
			side: "left",
			left: selected.left - width - gap,
			top: anchor.top,
			space: selected.left - viewport.left,
		}, ];
		/** @param {{side: string, left: number, top: number, space: number}} candidate */
		const fits = candidate => candidate.side === "top" || candidate.side === "bottom" ? candidate.space >= height + gap : candidate.space >= width + gap;
		const candidate = candidates.find(fits) ?? [...candidates].sort((a, b) => b.space - a.space)[0] ?? candidates[0] ?? {
			side: "bottom",
			left: anchor.left,
			top: anchor.bottom + gap,
			space: 0,
		};
		let left = candidate.left;
		let top = candidate.top;
		left = clamp(left, viewport.left, viewport.right - width);
		top = clamp(top, viewport.top, viewport.bottom - height);
		popup.setAttribute("data-side", candidate.side);
		popup.style.setProperty("--dynamic-capture-width", `${width}px`);
		popup.style.setProperty("--dynamic-capture-left", `${left}px`);
		popup.style.setProperty("--dynamic-capture-top", `${top}px`);
	}
	/**
	 * Open the capture popover for a JSON pick.
	 *
	 * @param {HTMLButtonElement} button
	 */
	captureJson(button) {
		this.el.response_text.querySelectorAll(".json-node.value-selected").forEach(node => {
			node.classList.remove("value-selected");
		});
		button.closest(".json-node")?.classList.add("value-selected");
		this.captureValue = this.jsonValues.get(button);
		this.el.capture_path.textContent = button.getAttribute("data-path") ?? "";
		this.el.capture.hidden = false;
		this.el.capture_name.value = "";
		this.placeCapture(button);
		this.el.capture_name.focus({
			preventScroll: true,
		});
	}
	/**
	 * Close the capture popover.
	 */
	closeCapture({
		focusResponse = false
	} = {}) {
		this.el.capture.hidden = true;
		this.el.response_text.querySelectorAll(".json-node.value-selected").forEach(node => {
			node.classList.remove("value-selected");
		});
		if (focusResponse) this.el.response_view.focus({
			preventScroll: true,
		});
	}
	/**
	 * Save the captured path as a variable.
	 *
	 * @param {Event} event
	 */
	saveCaptured(event) {
		event.preventDefault();
		const name = this.el.capture_name.value.trim();
		if (!/^[A-Za-z_][\w.-]*(?:\/[A-Za-z_][\w.-]*)*$/.test(name)) {
			this.toast("Use letters, numbers, _, -, . and /; each segment must start with a letter or _", );
			return;
		}
		const serialized = typeof this.captureValue === "string" ? this.captureValue : (JSON.stringify(this.captureValue) ?? "null");
		const existing = this.variables.find(variable => variable.name === name);
		if (existing) existing.value = serialized;
		else this.variables.push({
			name,
			value: serialized,
			secret: false,
		});
		this.renderVariables();
		this.closeCapture();
		this.toast(`Saved ${name}`);
	}
	/**
	 * Build one XML tree node.
	 *
	 * @param {Element} node
	 * @returns {HTMLElement} 
	 */
	xmlNode(node) {
		const wrap = document.createElement("div");
		wrap.className = "json-node";
		const line = document.createElement("div");
		line.className = "json-row";
		const children = [...node.children];
		const toggle = document.createElement("button");
		toggle.type = "button";
		toggle.className = "json-toggle";
		toggle.textContent = children.length ? "▾" : "";
		toggle.disabled = !children.length;
		if (children.length) toggle.addEventListener("click", () => wrap.classList.toggle("collapsed"), );
		line.append(toggle);
		const label = document.createElement("span");
		label.className = "json-pick json-string";
		const attrs = [...node.attributes].map(attr => ` ${attr.name}=${JSON.stringify(attr.value)}`).join("");
		const text = children.length ? "" : (node.textContent ?? "").trim();
		label.textContent = `<${node.tagName}${attrs}>${text}`;
		line.append(label);
		wrap.append(line);
		if (children.length) {
			const nested = document.createElement("div");
			nested.className = "json-children";
			children.forEach(child => {
				nested.append(this.xmlNode(child));
			});
			wrap.append(nested);
			const close = document.createElement("span");
			close.className = "json-close";
			close.textContent = `</${node.tagName}>`;
			wrap.append(close);
		} else label.textContent += `</${node.tagName}>`;
		return wrap;
	}
	/**
	 * Rebuild the body tree from the source text.
	 *
	 * @throws {Error}
	 */
	refreshBodyTree() {
		const format = this.el.body_format.value;
		const raw = RequestStudio.editorText(this.el.body);
		this.el.body_mode.hidden = format === "text";
		if (format === "text") {
			this.setBodyMode("source");
			return;
		}
		try {
			if (format === "json") {
				const resolved = this.resolve(raw);
				this.el.body_tree.replaceChildren(this.jsonNode(JSON.parse(resolved), "$", null, false), );
			} else {
				const documentNode = new DOMParser().parseFromString(this.resolve(raw), "application/xml", );
				if (documentNode.querySelector("parsererror")) throw new Error("Invalid XML");
				this.el.body_tree.replaceChildren(this.xmlNode(documentNode.documentElement), );
			}
			this.el.body_tree.setAttribute("data-valid", "true");
		} catch {
			this.el.body_tree.replaceChildren(Object.assign(document.createElement("span"), {
				textContent: `Invalid ${format.toUpperCase()} — edit Source to continue.`,
			}), );
			this.el.body_tree.setAttribute("data-valid", "false");
		}
	}
	/**
	 * Switch body editing between source and tree.
	 *
	 * @param {string} mode
	 */
	setBodyMode(mode) {
		const source = mode === "source" || this.el.body_format.value === "text";
		this.closeCapture();
		this.el.body_source.hidden = !source;
		this.el.body_tree.hidden = source;
		this.el.body_format_action.hidden = !source || this.el.body_format.value === "text";
		this.el.body_mode.querySelectorAll("button").forEach(button => {
			button.classList.toggle("active", button.getAttribute("data-body-mode") === (source ? "source" : "tree"), );
		});
		if (!source) this.refreshBodyTree();
	}
	/**
	 * Pretty-print XML source.
	 *
	 * @param {string} source
	 * @returns {string} 
	 * @throws {Error}
	 */
	static prettyXml = source => {
		const parsed = new DOMParser().parseFromString(source, "application/xml");
		if (parsed.querySelector("parsererror")) throw new Error("Invalid XML");
		/** @param {Node} node @param {number} depth @returns {string} */
		const indent = (node, depth) => {
			const pad = "  ".repeat(depth);
			if (node.nodeType === Node.TEXT_NODE) {
				const value = node.nodeValue?.trim() ?? "";
				return value ? `${pad}${value}` : "";
			}
			if (!(node instanceof Element)) return "";
			const attributes = [...node.attributes].map(attribute => ` ${attribute.name}=${JSON.stringify(attribute.value)}`, ).join("");
			const children = [...node.childNodes].filter(child => child.nodeType !== Node.TEXT_NODE || child.nodeValue?.trim(), );
			if (!children.length) return `${pad}<${node.tagName}${attributes}/>`;
			const [only] = children;
			if (children.length === 1 && only?.nodeType === Node.TEXT_NODE) return `${pad}<${node.tagName}${attributes}>${only.nodeValue?.trim() ?? ""}</${node.tagName}>`;
			return `${pad}<${node.tagName}${attributes}>\n${children
        .map((child) => indent(child, depth + 1))
        .filter(Boolean)
        .join("\n")}\n${pad}</${node.tagName}>`;
		};
		return indent(parsed.documentElement, 0);
	};
	/**
	 * Format the body source per its format.
	 */
	formatBodySource() {
		const format = this.el.body_format.value;
		const source = RequestStudio.editorText(this.el.body);
		try {
			const formatted = format === "json" ? JSON.stringify(JSON.parse(source), null, 2) : format === "xml" ? RequestStudio.prettyXml(source) : source;
			RequestStudio.setEditorText(this.el.body, formatted);
			this.refreshBodyTree();
			this.toast(`${format.toUpperCase()} formatted`);
		} catch {
			this.toast(`Cannot format invalid ${format.toUpperCase()}`);
		}
	}
}
