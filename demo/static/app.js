/**
 * Return the next visible status value.
 * @param {string | null} value Current status label.
 * @returns {string} The label shown after toggling.
 */
export const nextStatus = value => value === "Ready" ? "Active" : "Ready";
/**
 * Return the toggled value of an ARIA boolean attribute.
 * @param {string | null} value Current `aria-expanded`/`aria-checked` value.
 * @returns {"true" | "false"} The opposite boolean string.
 */
export const flipFlag = value => value === "true" ? "false" : "true";
/**
 * Return whether a tab panel stays hidden for the selected tab.
 * @param {string} panelId Identifier of the panel being updated.
 * @param {string} selectedPanelId Panel controlled by the selected tab.
 * @returns {boolean} `true` when the panel must be hidden.
 */
export const panelHidden = (panelId, selectedPanelId) => panelId !== selectedPanelId;
/** Wire every interactive demo surface to its unveiled interface. */
class DemoController {
	/**
	 * Bind listeners for the controls present on the current page.
	 * @param {Document} root Document containing the demo controls.
	 */
	constructor(root) {
		this.root = root;
		this.status = root.querySelector("[data-status]");
		this.preview = root.querySelector(".preview");
		root.querySelector("[data-toggle-status]")?.addEventListener("click", this.toggleStatus.bind(this));
		root.querySelector("[data-save-draft]")?.addEventListener("click", this.saveDraft.bind(this));
		for (const tab of root.querySelectorAll("[role=tab]")) tab.addEventListener("click", this.selectTab.bind(this));
		for (const button of root.querySelectorAll("[data-disclosure]")) button.addEventListener("click", this.toggleDisclosure.bind(this));
		root.querySelector("[data-density]")?.addEventListener("click", this.toggleDensity.bind(this));
		root.querySelector("[data-open-preview]")?.addEventListener("click", this.openPreview.bind(this));
		root.querySelector("[data-close-preview]")?.addEventListener("click", this.closePreview.bind(this));
	}
	/** Mark the draft as saved; a pure DOM change for explorer clicks. */
	saveDraft() {
		if (this.status instanceof HTMLElement) this.status.textContent = "Draft saved";
	}
	/** Flip the status label; a near-identical visual change. */
	toggleStatus() {
		if (this.status instanceof HTMLElement) this.status.textContent = nextStatus(this.status.textContent);
	}
	/**
	 * Select the clicked tab and reveal only its panel.
	 * @param {Event} event Click event raised by a tab.
	 */
	selectTab(event) {
		const selected = event.currentTarget;
		if (!(selected instanceof HTMLElement)) return;
		const selectedPanel = selected.getAttribute("aria-controls") ?? "";
		for (const tab of this.root.querySelectorAll("[role=tab]")) {
			const panelId = tab.getAttribute("aria-controls") ?? "";
			tab.setAttribute("aria-selected", String(!panelHidden(panelId, selectedPanel)), );
			const panel = this.root.getElementById(panelId);
			if (panel instanceof HTMLElement) panel.hidden = panelHidden(panelId, selectedPanel);
		}
	}
	/**
	 * Expand or collapse the region controlled by a disclosure button.
	 * @param {Event} event Click event raised by a disclosure button.
	 */
	toggleDisclosure(event) {
		const button = event.currentTarget;
		if (!(button instanceof HTMLElement)) return;
		const expanded = flipFlag(button.getAttribute("aria-expanded"));
		button.setAttribute("aria-expanded", expanded);
		const region = this.root.getElementById(button.getAttribute("aria-controls") ?? "", );
		if (region instanceof HTMLElement) region.hidden = expanded === "false";
	}
	/**
	 * Toggle the compact layout switch and the page density class.
	 * @param {Event} event Click event raised by the switch.
	 */
	toggleDensity(event) {
		const toggle = event.currentTarget;
		if (!(toggle instanceof HTMLElement)) return;
		const checked = flipFlag(toggle.getAttribute("aria-checked"));
		toggle.setAttribute("aria-checked", checked);
		this.root.body.classList.toggle("compact", checked === "true");
	}
	/** Show the non-modal preview panel. */
	openPreview() {
		if (this.preview instanceof HTMLDialogElement && !this.preview.open) this.preview.show();
	}
	/** Hide the preview panel, restoring an already captured state. */
	closePreview() {
		if (this.preview instanceof HTMLDialogElement) this.preview.close();
	}
}
if (typeof document !== "undefined") Reflect.set(globalThis, "demoController", new DemoController(document));
if (typeof document !== "undefined") fetch("/api/error").then(response => {
	if (!response.ok) console.warn("The demo HTTP error is intentional.");
});
