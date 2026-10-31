/** Footer: pick, highlight, stats chips, stats panel and the pick result. */
import { icon } from "./icons.js";
/** @typedef {{count:number, visible:number, inView:number, enabled:number, scanned:number, truncated:boolean, elapsedMs:number, nodes:{path:number[], label:string, kind:string, count:number}[], first:{tag:string, css:string, text:string}|null}} Stats */
/**
 * Create an element with an optional class and text.
 * @param {string} tag Tag name.
 * @param {string} [className] Class list.
 * @param {string} [text] Text content.
 * @returns {HTMLElement} The new element.
 */
const make = (tag, className = "", text = "") => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
};
/**
 * Build the footer row, stats panel and pick list.
 * @returns {{element:HTMLElement, panel:HTMLElement, onValidation:Function, onText:Function, setStats:Function, armed:()=>boolean}} The footer API.
 */
export const createFooter = (/** @type {{host:{pick?:Function, highlight?:Function, stats?:Function, profiles?:Function}, getValue:()=>string, setValue:(v:string)=>void, usesLiveVariables:()=>boolean, expected?:()=>number|null}} */ { host, getValue, setValue, usesLiveVariables, expected }) => {
  const element = make("div", "ese-footer");
  const row = make("div", "ese-footer-row");
  const panel = make("div", "ese-panel");
  panel.hidden = true;
  const pickBox = make("div", "ese-pick");
  pickBox.hidden = true;
  /**
   * Build a labelled icon button.
   * @param {string} label Accessible label.
   * @param {keyof typeof import("./icons.js")|string} name Icon name.
   * @param {boolean} [labelled] Whether to render the text label.
   * @returns {HTMLButtonElement} The new button.
   */
  const button = (label, name, labelled = true) => {
    const node = /** @type {HTMLButtonElement} */ (make("button", "ese-btn"));
    node.type = "button";
    node.setAttribute("aria-label", label);
    node.title = label;
    node.append(icon(/** @type {any} */ (name)));
    if (labelled) node.append(make("span", "ese-btn-label", label.split(" ")[0]));
    return node;
  };
  const pick = button("Pick on page", "crosshair");
  const highlight = button("Highlight on page", "eye");
  highlight.setAttribute("aria-pressed", "false");
  const chevron = button("Show stats", "chevron", false);
  chevron.classList.add("ese-chevron");
  chevron.setAttribute("aria-expanded", "false");
  /** @type {Map<string, HTMLElement>} */
  const chips = new Map();
  /**
   * Build a stat chip.
   * @param {string} id Chip identifier.
   * @param {string} name Icon name.
   * @param {string} word Unit word.
   * @param {string} [min] Minimum breakpoint.
   * @param {boolean} [always] Whether the icon always renders.
   * @returns {HTMLElement} The new chip.
   */
  const chip = (id, name, word, min = "", always = false) => {
    const node = make("span", "ese-chip");
    node.setAttribute("data-chip", id);
    if (min) node.setAttribute("data-min", min);
    node.append(icon(/** @type {any} */ (name), always), make("span", "ese-num", "–"), make("span", "ese-word", ` ${word}`));
    chips.set(id, node);
    return node;
  };
  if (host.pick) row.append(pick);
  if (host.highlight) row.append(highlight);
  if (host.stats) {
    row.append(
      chip("matches", "target", "matches", "", true),
      chip("visible", "visible", "visible"),
      chip("inView", "view", "in view"),
      chip("time", "clock", "ms", "300"),
      chip("enabled", "enabled", "enabled", "560"),
      chip("verdict", "check", "expected", "680"),
      chip("scanned", "scan", "scanned", "780"),
      chip("devices", "devices", "profiles", "880"),
    );
    row.append(make("span", "ese-spacer"), chevron);
  }
  element.append(row, pickBox);
  /** @type {Stats|null} */
  let stats = null;
  let validState = "idle";
  let armed = false;
  let on = false;
  /**
   * Update a stat chip value, tone and tooltip.
   * @param {string} id Chip identifier.
   * @param {string|number} value Displayed value.
   * @param {string} [tone] Tone attribute.
   * @param {string} [title] Tooltip text.
   */
  const setChip = (id, value, tone = "", title = "") => {
    const node = chips.get(id);
    if (!node) return;
    const num = node.querySelector(".ese-num");
    if (num) num.textContent = String(value);
    if (tone) node.setAttribute("data-tone", tone);
    else node.removeAttribute("data-tone");
    node.title = title;
    node.setAttribute("aria-label", `${value} ${node.querySelector(".ese-word")?.textContent?.trim() ?? id}`);
  };
  /** Refresh the highlight button state against stats and validity. */
  const refreshHighlight = () => {
    const usable = (validState === "valid" || validState === "warning") && (stats?.visible ?? 0) >= 1;
    highlight.disabled = !usable;
    const reason = validState === "error" ? "Fix the errors to highlight" : (stats?.visible ?? 0) < 1 ? "No visible match to highlight" : "Highlight on page";
    highlight.title = reason;
    highlight.setAttribute("aria-label", usable ? "Highlight on page" : reason);
    if (!host.highlight) return;
    if (on && usable) {
      armed = false;
      host.highlight(getValue(), () => undefined);
    } else if (on) {
      armed = true;
      host.highlight("", () => undefined);
    }
    highlight.setAttribute("aria-pressed", String(on && usable));
    if (on && !usable) highlight.setAttribute("data-state", "armed");
    else highlight.removeAttribute("data-state");
  };
  /** Repaint the stats panel from the latest stats snapshot. */
  const paintPanel = () => {
    panel.replaceChildren();
    if (!stats) return;
    panel.append(make("div", "ese-pick-group", "Matches per part"));
    for (const node of stats.nodes) {
      const line = make("div", "ese-node");
      const dot = make("span", "ese-node-dot");
      dot.setAttribute("data-kind", node.kind);
      line.append(dot, make("span", "", `${"· ".repeat(node.path.length)}${node.label}`), make("span", "ese-node-count", String(node.count)));
      panel.append(line);
    }
    const want = expected?.() ?? null;
    if (want != null) panel.append(make("div", "ese-pick-note", stats.count === want ? `Matches the expected ${want}.` : `Expected ${want}, found ${stats.count}.`));
    if (stats.first) panel.append(make("div", "ese-pick-note", `First: ${stats.first.css}${stats.first.text ? ` “${stats.first.text}”` : ""}`));
  };
  /**
   * Apply a stats snapshot to chips and the panel.
   * @param {Stats|null} next Next stats snapshot.
   */
  const setStats = next => {
    stats = next;
    if (!next) {
      for (const id of chips.keys()) setChip(id, "–");
      setChip("matches", "–", "", "Matches paused");
    } else {
      const want = expected?.() ?? null;
      setChip("matches", next.count, next.count > 0 && (want == null || want === next.count) ? "ok" : want != null ? "bad" : "warn");
      setChip("visible", next.visible);
      setChip("inView", next.inView);
      setChip("time", Math.round(next.elapsedMs));
      setChip("enabled", next.enabled);
      setChip("verdict", want == null ? "–" : next.count === want ? "yes" : "no", want == null ? "" : next.count === want ? "ok" : "bad");
      setChip("scanned", next.truncated ? `${next.scanned}+` : next.scanned);
      setChip("devices", "–");
    }
    const devices = chips.get("devices");
    if (devices) devices.hidden = !usesLiveVariables();
    paintPanel();
    refreshHighlight();
  };
  /** @type {ReturnType<typeof setTimeout>|undefined} */
  let timer;
  /** Debounce a stats refresh through the host. */
  const requestStats = () => {
    clearTimeout(timer);
    if (!host.stats) return;
    if (validState === "error" || validState === "idle") {
      setStats(null);
      return;
    }
    const fetchStats = host.stats;
    timer = setTimeout(async () => {
      try {
        setStats(await fetchStats?.(getValue()) ?? null);
      } catch (error) {
        const needs = /** @type {any} */ (error)?.code === "missing-variable";
        setStats(null);
        setChip("matches", needs ? "needs a value" : "error", "bad", String(/** @type {Error} */ (error).message));
      }
    }, 200);
  };
  highlight.addEventListener("click", () => {
    on = !on;
    if (!on) {
      host.highlight?.("", () => undefined);
      highlight.setAttribute("aria-pressed", "false");
      highlight.removeAttribute("data-state");
      armed = false;
    } else refreshHighlight();
  });
  chevron.addEventListener("click", () => {
    panel.hidden = !panel.hidden;
    chevron.setAttribute("aria-expanded", String(!panel.hidden));
  });
  /**
   * Render the pick result with selector alternatives.
   * @param {any} picked Picked element payload.
   */
  const showPick = picked => {
    pickBox.replaceChildren();
    pickBox.hidden = false;
    const head = make("div", "ese-pick-head");
    head.append(make("span", "", `Picked ${picked.element?.tag ?? "element"}${picked.element?.text ? ` “${picked.element.text}”` : ""}`));
    const close = button("Dismiss", "close", false);
    close.classList.add("ese-push");
    close.addEventListener("click", () => {
      pickBox.hidden = true;
    });
    head.append(close);
    pickBox.append(head, make("div", "ese-pick-note", "Choose how to select it. The change applies as you choose."));
    /** @type {{strategy:string, selector:string, matches:number}[]} */
    const alts = picked.alternatives ?? [{ strategy: "picked", selector: picked.selector, matches: picked.matches ?? 0 }];
    const best = alts.find(a => a.matches === 1) ?? alts[0];
    /**
     * Append a group of selectable selector alternatives.
     * @param {string} title Group title.
     * @param {typeof alts} list Alternatives to render.
     */
    const group = (title, list) => {
      if (!list.length) return;
      pickBox.append(make("div", "ese-pick-group", title));
      for (const alt of list) {
        const rowEl = make("label", "ese-pick-row");
        const input = /** @type {HTMLInputElement} */ (make("input"));
        input.type = "radio";
        input.name = "ese-pick";
        input.checked = alt === best;
        input.addEventListener("change", () => setValue(alt.selector));
        const body = make("span", "ese-pick-sel", `${alt.strategy}  ${alt.selector}`);
        const badge = make("span", "ese-badge", String(alt.matches));
        if (alt.matches === 1) badge.setAttribute("data-tone", "ok");
        rowEl.append(body, badge);
        rowEl.prepend(input);
        pickBox.append(rowEl);
      }
    };
    group("Recommended", best ? [best] : []);
    group("Other options", alts.filter(a => a !== best));
    if (best) setValue(best.selector);
  };
  pick.addEventListener("click", () => {
    host.pick?.((/** @type {any} */ picked) => showPick(picked));
  });
  return {
    element,
    panel,
    /** @param {{state:string}} result */
    onValidation: result => {
      validState = result.state;
      requestStats();
      refreshHighlight();
    },
    onText: requestStats,
    setStats,
    armed: () => armed,
  };
};
