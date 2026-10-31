/** @typedef {{pointer_action?:string, selector?:string, destination?:string, scroll_x?:string, scroll_y?:string, position_action?:string, x?:string, y?:string, duration_ms?:string, direction?:string, distance?:string, scale?:string, [name:string]:string|undefined}} PointerSeed */
/** @type {ReadonlyArray<readonly [string, string, string]>} */
const ACTIONS = Object.freeze([
	["click", "Mouse", "Click"],
	["double_click", "Mouse", "Double click"],
	["right_click", "Mouse", "Right click"],
	["hover", "Mouse", "Hover"],
	["drag", "Mouse", "Drag to"],
	["scroll", "Mouse", "Scroll"],
	["position_pointer", "Pointer", "Viewport position"],
	["touch_tap", "Touch", "Tap"],
	["touch_long_press", "Touch", "Long press"],
	["touch_swipe", "Touch", "Swipe"],
	["touch_pinch", "Touch", "Pinch / zoom"],
]);
/** @type {Readonly<Record<string, string>>} */
const DETAILS = Object.freeze({
	click: "Click the selected target once.",
	double_click: "Double-click the selected target.",
	right_click: "Open the selected target's context menu.",
	hover: "Move the pointer over the selected target.",
	drag: "Drag the selected target to another selector.",
	scroll: "Scroll a container or the page to exact offsets.",
	position_pointer: "Run a pointer operation at viewport coordinates.",
	touch_tap: "Tap the center of the selected target.",
	touch_long_press: "Press and hold the center of the selected target.",
	touch_swipe: "Swipe from the center of the selected target.",
	touch_pinch: "Pinch or zoom around the selected target.",
});
/** Create an HTML element.
 * @template {keyof HTMLElementTagNameMap} K
 * @param {K} tag Element tag.
 * @param {string} [className] CSS class.
 * @returns {HTMLElementTagNameMap[K]} Created element.
 */
const make = (tag, className = "") => {
	const element = document.createElement(tag);
	element.className = className;
	return element;
};
/** Create a select option.
 * @param {string} value Submitted value.
 * @param {string} label Visible label.
 * @returns {HTMLOptionElement} Created option.
 */
const option = (value, label) => {
	const element = document.createElement("option");
	element.value = value;
	element.textContent = label;
	return element;
};
/** Create a labelled input.
 * @param {string} name Submitted name.
 * @param {string} label Visible label.
 * @param {string} [type] Input type.
 * @param {string} [value] Initial value.
 * @returns {HTMLLabelElement} Label and input wrapper.
 */
const input = (name, label, type = "text", value = "") => {
	const wrap = make("label", "pointer-field");
	const text = make("span", "pointer-field-label");
	text.textContent = label;
	const control = document.createElement("input");
	control.name = name;
	control.type = type;
	control.value = value;
	control.setAttribute("aria-label", label);
	wrap.append(text, control);
	return wrap;
};
/** Create a labelled select.
 * @param {string} name Submitted name.
 * @param {string} label Visible label.
 * @param {ReadonlyArray<readonly [string, string]>} choices Value-label pairs.
 * @param {string} [value] Initial value.
 * @returns {HTMLLabelElement} Label and select wrapper.
 */
const select = (name, label, choices, value = "") => {
	const wrap = make("label", "pointer-field");
	const text = make("span", "pointer-field-label");
	text.textContent = label;
	const control = document.createElement("select");
	control.name = name;
	control.setAttribute("aria-label", label);
	control.append(...choices.map(([choice, title]) => option(choice, title)));
	if (value) control.value = value;
	wrap.append(text, control);
	return wrap;
};
/** Render the shared pointer and touch action form. */
export class PointerStudio {
	/** Create the action form.
	 * @param {HTMLElement} host Element receiving the form.
	 * @param {PointerSeed} [seed] Initial field values.
	 * @param {{selectorField?: (label: string, seed: PointerSeed) => HTMLElement}} [options] Host-provided field builders.
	 */
	constructor(host, seed = {}, options = {}) {
		this.host = host;
		this.seed = {
			...seed
		};
		this.selectorField = options.selectorField ?? null;
		this.root = make("section", "pointer-studio");
		this.root.setAttribute("aria-label", "Pointer action");
		this.action = document.createElement("select");
		this.action.name = "pointer_action";
		this.action.setAttribute("aria-label", "Pointer or touch action");
		for (const family of ["Mouse", "Pointer", "Touch"]) {
			const group = document.createElement("optgroup");
			group.label = family;
			group.append(...ACTIONS.filter(item => item[1] === family).map(item => option(item[0], item[2])));
			this.action.append(group);
		}
		this.action.value = seed.pointer_action ?? "click";
		this.description = make("p", "pointer-description");
		this.description.id = `pointer-description-${crypto.randomUUID()}`;
		this.action.setAttribute("aria-describedby", this.description.id);
		this.fields = make("div", "pointer-fields");
		const heading = make("div", "pointer-heading");
		const label = make("label", "pointer-action-label");
		const labelText = make("span", "pointer-field-label");
		labelText.textContent = "Interaction";
		label.append(labelText, this.action);
		heading.append(label, this.description);
		this.root.append(heading, this.fields);
		host.replaceChildren(this.root);
		this.action.addEventListener("change", () => {
			this.remember();
			this.render();
		});
		this.render();
	}
	/** Return the selected concrete operation.
	 * @returns {string} Operation identifier.
	 */
	value() {
		return this.action.value;
	}
	/** Preserve visible values before changing operation. */
	remember() {
		for (const control of this.fields.querySelectorAll("[name]"))
			if (control instanceof HTMLInputElement || control instanceof HTMLSelectElement) this.seed[control.name] = control.value;
	}
	render() {
		const action = this.value();
		this.description.textContent = DETAILS[action] ?? "Configure a pointer action.";
		const fields = [];
		if (action !== "position_pointer") {
			const label = action === "drag" ? "From" : action === "scroll" ? "Scroll container" : "Target";
			fields.push(this.selectorField
				? this.selectorField(label, this.seed)
				: input("selector", label, "text", this.seed.selector ?? (action === "scroll" ? "html" : "")));
		}
		if (action === "drag") fields.push(input("destination", "To selector", "text", this.seed.destination ?? ""));
		if (action === "scroll") fields.push(input("scroll_x", "Horizontal position", "number", this.seed.scroll_x ?? "0"), input("scroll_y", "Vertical position", "number", this.seed.scroll_y ?? "600"));
		if (action === "position_pointer") fields.push(select("position_action", "Operation", [
			["hover", "Hover"],
			["click", "Click"],
			["double_click", "Double click"],
			["right_click", "Right click"]
		], this.seed.position_action ?? "hover"), input("x", "X coordinate", "number", this.seed.x ?? "0"), input("y", "Y coordinate", "number", this.seed.y ?? "0"));
		if (action === "touch_long_press") fields.push(input("duration_ms", "Hold for (ms)", "number", this.seed.duration_ms ?? "650"));
		if (action === "touch_swipe") fields.push(select("direction", "Direction", [
			["up", "Up"],
			["down", "Down"],
			["left", "Left"],
			["right", "Right"]
		], this.seed.direction ?? "up"), input("distance", "Distance (px)", "number", this.seed.distance ?? "240"), input("duration_ms", "Duration (ms)", "number", this.seed.duration_ms ?? "350"));
		if (action === "touch_pinch") fields.push(input("scale", "Scale", "number", this.seed.scale ?? "1.5"), input("duration_ms", "Duration (ms)", "number", this.seed.duration_ms ?? "350"));
		this.fields.replaceChildren(...fields);
		this.root.dispatchEvent(new CustomEvent("pointer-action-change", {
			bubbles: true,
			detail: {
				action
			}
		}));
	}
}
/** Mount the shared action frontend.
 * @param {HTMLElement} host Element receiving the form.
 * @param {PointerSeed} [seed] Initial field values.
 * @param {{selectorField?: (label: string, seed: PointerSeed) => HTMLElement}} [options] Host-provided field builders.
 * @returns {PointerStudio} Mounted frontend API.
 */
export const mountPointerStudio = (host, seed = {}, options = {}) => new PointerStudio(host, seed, options);
