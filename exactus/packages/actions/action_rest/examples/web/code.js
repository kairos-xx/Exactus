import {
	RequestStudio
} from "../../index.js";
const query = new URLSearchParams(location.search);
const theme = query.get("theme");
if (theme === "light" || theme === "dark") document.documentElement.setAttribute("data-theme", theme);
if (query.has("embed")) document.documentElement.setAttribute("data-embed", "");
/** @type {import("../../request_studio.js").RequestStudioSeed} */
const DEMO = {
	rows: {
		params: [{
			enabled: true,
			key: "limit",
			value: "{{pagination/pageSize}}",
		}, {
			enabled: true,
			key: "include",
			value: "profile",
		}, ],
		headers: [{
			enabled: true,
			key: "Authorization",
			value: "Bearer {{auth/apiToken}}",
		}, {
			enabled: true,
			key: "Accept",
			value: "application/json",
		}, ],
		cookies: [{
			enabled: true,
			key: "workspace",
			value: "{{workspace/name}}",
		}, ],
	},
	variables: [{
		name: "api/version",
		value: "v1",
		secret: false,
	}, {
		name: "api/baseUrl",
		value: "https://api.example.com",
		secret: false,
	}, {
		name: "user/id",
		value: "usr_28491",
		secret: false,
	}, {
		name: "user/profile/name",
		value: "Ada",
		secret: false,
	}, {
		name: "pagination/pageSize",
		value: "25",
		secret: false,
	}, {
		name: "pagination/cursor",
		value: "",
		secret: false,
	}, {
		name: "workspace/name",
		value: "design-team",
		secret: false,
	}, {
		name: "workspace/id",
		value: "ws_104",
		secret: false,
	}, {
		name: "auth/apiToken",
		value: "sk_demo_12345678",
		secret: true,
	}, {
		name: "auth/scheme",
		value: "Bearer",
		secret: false,
	}, ],
	url: "{{api/baseUrl}}/{{api/version}}/users/{{user/id}}",
	body: '{\n  "user": "{{user/id}}",\n  "workspace": "{{workspace/name}}"\n}',
};
const studio = new RequestStudio(DEMO);
studio.el.method.addEventListener("change", () => studio.setMethodTone());
studio.setMethodTone();
studio.el.body_format_action.addEventListener("click", () => studio.formatBodySource(), );
studio.el.body_mode.addEventListener("click", event => {
	const button = event.target instanceof Element ? event.target.closest("button[data-body-mode]") : null;
	if (button) studio.setBodyMode(button.getAttribute("data-body-mode") ?? "source");
});
studio.el.body_format.addEventListener("change", () => {
	studio.refreshBodyTree();
	studio.setBodyMode(studio.el.body_format.value === "text" ? "source" : "tree", );
});
studio.el.body.addEventListener("input", () => studio.refreshBodyTree());
studio.refreshBodyTree();
studio.setBodyMode("tree");
studio.closeCapture();
studio.el.response_text.addEventListener("click", event => {
	const button = event.target instanceof Element ? event.target.closest(".json-pick") : null;
	if (button instanceof HTMLButtonElement) studio.captureJson(button);
});
studio.el.capture.addEventListener("submit", event => studio.saveCaptured(event), );
studio.el.capture_name.addEventListener("keydown", event => {
	if (event.key !== "Enter") return;
	event.preventDefault();
	studio.saveCaptured(event);
});
document.addEventListener("pointerdown", event => {
	if (!studio.el.capture.hidden && event.target instanceof Node && !studio.el.capture.contains(event.target) && !(event.target instanceof Element && event.target.closest(".json-pick"))) studio.closeCapture();
});
document.addEventListener("keydown", event => {
	if (event.key === "Escape" && !studio.el.capture.hidden) studio.closeCapture({
		focusResponse: true,
	});
});
window.addEventListener("resize", () => {
	if (studio.el.capture.hidden) return;
	const selected = studio.el.response_text.querySelector(".json-node.value-selected > .json-row > .json-pick", );
	if (selected instanceof HTMLButtonElement) studio.placeCapture(selected);
});
studio.showJson({
	id: "req_8f2c1",
	ok: true,
	user: {
		id: 28491,
		name: "Ada Lovelace",
		active: true,
		roles: ["admin", "developer"],
		profile: {
			email: "ada@example.com",
			timezone: null,
		},
	},
	pagination: {
		page: 1,
		pageSize: 25,
		hasNext: false,
	},
	tags: ["api", "studio"],
});
if (studio.el.response_meta.lastChild) studio.el.response_meta.lastChild.textContent = " 200 OK · 42 ms";
studio.el.response_meta.className = "success";
