/** Present the real Playwright page, forwarding input in target CSS pixels.
 */
export class LiveTarget {
  /** @type {boolean} */
  picking = false;
  /** Most recent hover request timestamp.
   */
  inspectedAt = 0;
  /** @type {HTMLImageElement} */
  image;
  /** @type {(payload:Record<string,string|number|boolean>)=>Promise<unknown>} */
  send;
  /** @type {()=>{width:number,height:number}} */
  viewport;
  /** @type {()=>boolean} */
  touchMode;
  /** @type {(element:Record<string,unknown>)=>void} */
  onPicked;
  /** @type {string|null} */
  frameUrl = null;
  /** Consecutive failed preview requests, used for backoff. */
  failures = 0;
  /** Set once polling must stop for good. */
  destroyed = false;
  /** @type {number|undefined} */
  timer;
  /** Serialize pointer and key events to preserve recording order.
   */
  pending = Promise.resolve();
  /** @type {Record<string,string|number|boolean>|null} */
  latestMove = null;
  /** @type {number|undefined} */
  moveFrame;
  /** @type {Set<number>} */
  activePointers = new Set();
  /** function Object() { [native code] }
   * @param {HTMLImageElement} image Real page image and input surface.
   * @param {(payload:Record<string,string|number|boolean>)=>Promise<unknown>} send Input transport.
   * @param {()=>{width:number,height:number}} viewport Target CSS dimensions.
   * @param {()=>boolean} touchMode Whether pointer gestures emulate touch.
   * @param {(element:Record<string,unknown>)=>void} [onPicked] Receives a picked element.
   */
  constructor(image, send, viewport, touchMode = () => false, onPicked = () => {}) {
    this.image = image;
    this.send = send;
    this.viewport = viewport;
    this.touchMode = touchMode;
    this.onPicked = onPicked;
    document
      .getElementById("live-target-maximize")
      ?.addEventListener("click", () =>
        this.maximize(
          !image
            .closest("[data-panel-id]")
            ?.hasAttribute("data-live-maximized"),
        ),
      );
    document
      .getElementById("live-target-pick")
      ?.addEventListener("click", () => {
        if (this.picking) this.stopPicking();
        else this.startPicking();
      });
    image.addEventListener("pointerdown", event => this.pointerDown(event));
    image.addEventListener("pointermove", event => this.pointerMove(event));
    image.addEventListener("pointerup", event => this.pointerUp(event));
    image.addEventListener("pointercancel", event =>
      this.pointerUp(event, true),
    );
    image.addEventListener("pointerleave", event => {
      if (this.picking || event.buttons || this.activePointers.size) return;
      this.input({ action: "pointer_leave" });
    });
    image.addEventListener("contextmenu", event => event.preventDefault());
    image.addEventListener(
      "wheel",
      event => {
        event.preventDefault();
        const at = this.point(event);
        if (!at) return;
        this.input({
          action: "wheel",
          ...at,
          dx: Math.max(-2000, Math.min(2000, event.deltaX)),
          dy: Math.max(-2000, Math.min(2000, event.deltaY)),
        });
      },
      { passive: false },
    );
    image.addEventListener("keydown", event => {
      if (
        event.key === "Escape" &&
        (this.picking || image.closest("[data-live-maximized]"))
      ) {
        event.preventDefault();
        event.stopPropagation();
        this.maximize(false);
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      this.input({
        action: "key_down",
        key: event.key === " " ? "Space" : event.key,
        code: event.code,
      });
    });
    image.addEventListener("keyup", event => {
      event.preventDefault();
      event.stopPropagation();
      this.input({
        action: "key_up",
        key: event.key === " " ? "Space" : event.key,
        code: event.code,
      });
    });
    image.addEventListener("dragstart", event => event.preventDefault());
    // Escape restores from anywhere inside the maximized panel, not only the image.
    document.addEventListener("keydown", event => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      if (!image.closest("[data-live-maximized]")) return;
      event.preventDefault();
      this.maximize(false);
    });
    // Changing workspace or reloading never leaves the browser maximized or picking.
    const app = document.getElementById("app");
    if (app)
      new MutationObserver(() => this.maximize(false)).observe(app, {
        attributes: true,
        attributeFilter: ["data-workspace-mode"],
      });
    this.refresh();
  }
  /** Start element picking and enlarge the browser target.
   * @returns {void}
   */
  startPicking() {
    this.picking = true;
    document
      .getElementById("live-target-pick")
      ?.setAttribute("aria-pressed", "true");
    this.maximize(true);
  }
  /** Stop element picking without changing the browser size.
   * @returns {void}
   */
  stopPicking() {
    this.picking = false;
    document
      .getElementById("live-target-pick")
      ?.setAttribute("aria-pressed", "false");
  }
  /** Forward a pointer press as mouse or touch input.
   * @param {PointerEvent} event
   * @returns {void}
   */
  pointerDown(event) {
    this.image.focus();
    const at = this.point(event);
    if (!at) return;
    if (this.picking) {
      this.input({ action: "inspect", picked: true, ...at });
      return;
    }
    event.preventDefault();
    this.image.setPointerCapture(event.pointerId);
    this.activePointers.add(event.pointerId);
    this.input({
      action: this.isTouch(event) ? "touch_start" : "pointer_down",
      ...at,
      pointer_id: event.pointerId,
      button: event.button,
      buttons: event.buttons,
    });
  }
  /** Forward hover and active drag movement without building a stale backlog.
   * @param {PointerEvent} event
   * @returns {void}
   */
  pointerMove(event) {
    const at = this.point(event);
    if (!at) return;
    if (this.picking) {
      if (performance.now() - this.inspectedAt < 150) return;
      this.inspectedAt = performance.now();
      this.input({ action: "inspect", picked: false, ...at });
      return;
    }
    if (event.buttons || this.activePointers.has(event.pointerId))
      event.preventDefault();
    this.queueMove({
      action: this.isTouch(event) ? "touch_move" : "pointer_move",
      ...at,
      pointer_id: event.pointerId,
      buttons: event.buttons,
    });
  }
  /** Forward pointer release or cancellation after the final coalesced move.
   * @param {PointerEvent} event
   * @param {boolean} [cancelled]
   * @returns {void}
   */
  pointerUp(event, cancelled = false) {
    if (!this.activePointers.has(event.pointerId)) return;
    event.preventDefault();
    const at = this.point(event) ?? { x: 0, y: 0 };
    const touch = this.isTouch(event);
    this.activePointers.delete(event.pointerId);
    if (this.image.hasPointerCapture(event.pointerId))
      this.image.releasePointerCapture(event.pointerId);
    this.input({
      action: touch
        ? cancelled
          ? "touch_cancel"
          : "touch_end"
        : "pointer_up",
      ...at,
      pointer_id: event.pointerId,
      button: event.button,
      buttons: event.buttons,
    });
  }
  /** Treat a physical touch or a touch device profile as touch input.
   * @param {PointerEvent} event
   * @returns {boolean}
   */
  isTouch(event) {
    return event.pointerType === "touch" || this.touchMode();
  }
  /** Expand or restore the live browser without mutating its saved dock layout.
   * @param {boolean} enabled
   * @returns {void}
   */
  maximize(enabled) {
    const wasMaximized = Boolean(this.image.closest("[data-live-maximized]"));
    this.image
      .closest("[data-panel-id]")
      ?.toggleAttribute("data-live-maximized", enabled);
    const button = document.getElementById("live-target-maximize");
    if (button) {
      const label = button.querySelector(".tool-label");
      if (label) label.textContent = enabled ? "Restore" : "Maximize";
      button.setAttribute("aria-pressed", String(enabled));
    }
    if (!enabled) {
      this.picking = false;
      document
        .getElementById("live-target-pick")
        ?.setAttribute("aria-pressed", "false");
      if (wasMaximized && this.image.contains(document.activeElement))
        button?.focus();
    }
  }
  /** Draw a numbered box over every element a selector test matched.
   * Boxes are placed against the page as drawn and keep the selector's order.
   * @param {{index:number,rect:{x:number,y:number,width:number,height:number}}[]} matches
   * @returns {void}
   */
  showMatches(matches) {
    const layer = document.getElementById("live-target-matches");
    if (!layer) return;
    layer.replaceChildren();
    layer.hidden = !matches.length;
    if (!matches.length) return;
    const viewport = this.viewport();
    const frame = layer.parentElement?.getBoundingClientRect();
    const page = this.content();
    const offsetX = frame ? page.left - frame.left : 0;
    const offsetY = frame ? page.top - frame.top : 0;
    for (const match of matches) {
      const box = document.createElement("div");
      box.className = "live-target-match";
      const label = document.createElement("span");
      label.textContent = String(match.index + 1);
      box.append(label);
      for (const [property, value] of Object.entries({
        left: offsetX + match.rect.x / viewport.width * page.width,
        top: offsetY + match.rect.y / viewport.height * page.height,
        width: match.rect.width / viewport.width * page.width,
        height: match.rect.height / viewport.height * page.height,
      }))
        box.style.setProperty(property, `${value}px`);
      layer.append(box);
    }
  }
  /** Remove the numbered match boxes.
   * @returns {void}
   */
  static clearMatches = () => {
    const layer = document.getElementById("live-target-matches");
    if (!layer) return;
    layer.replaceChildren();
    layer.hidden = true;
  };
  /** Show the inspected element bounds and update the picked selector.
   * @param {{picked?:boolean,element?:{selector:string,text:string,role?:string,name?:string,matches?:number,frame?:string,page?:string,unsupported?:string,alternatives?:{strategy:string,selector:string,matches:number}[],rect:{x:number,y:number,width:number,height:number}}}} result
   * @returns {void}
   */
  inspect(result) {
    const element = result.element;
    const highlight = document.getElementById("live-target-highlight");
    const viewport = this.viewport();
    if (!element || !highlight) return;
    highlight.hidden = false;
    // Position against the page as drawn, not the letterboxed image box.
    const frame = highlight.parentElement?.getBoundingClientRect();
    const page = this.content();
    const offsetX = frame ? page.left - frame.left : 0;
    const offsetY = frame ? page.top - frame.top : 0;
    for (const [property, value] of Object.entries({
      left: offsetX + element.rect.x / viewport.width * page.width,
      top: offsetY + element.rect.y / viewport.height * page.height,
      width: element.rect.width / viewport.width * page.width,
      height: element.rect.height / viewport.height * page.height,
    }))
      highlight.style.setProperty(property, `${value}px`);
    highlight.title = element.text || element.selector;
    if (!result.picked) return;
    LiveTarget.present(element);
    this.onPicked(element);
    this.stopPicking();
  }
  /** Show the picked element's identity, selector strategies and ambiguity.
   * @param {NonNullable<Parameters<LiveTarget["inspect"]>[0]["element"]>} element
   * @returns {void}
   */
  static present = element => {
    const selector = document.getElementById("live-target-selector");
    const use = document.getElementById("live-target-use");
    const strategy = document.getElementById("live-target-strategy");
    const identity = document.getElementById("live-target-identity");
    const selection = document.getElementById("live-target-selection");
    if (selection) selection.hidden = false;
    const choices = element.alternatives?.length
      ? element.alternatives
      : [
          {
            strategy: "css",
            selector: element.selector,
            matches: element.matches ?? 1,
          },
        ];
    /** @param {{strategy:string,selector:string,matches:number}} choice */
    const apply = choice => {
      if (selector instanceof HTMLInputElement)
        selector.value = choice.selector;
      if (use instanceof HTMLButtonElement)
        use.disabled = choice.matches < 1 || Boolean(element.unsupported);
      if (!identity) return;
      const what = [element.role, element.name && `“${element.name}”`]
        .filter(Boolean)
        .join(" ");
      const where = [element.frame, element.page].filter(Boolean).join(" · ");
      const count =
        choice.matches === 1
          ? "1 match"
          : choice.matches === 0
            ? "No match — choose another strategy"
            : `${choice.matches} matches — choose a more specific strategy`;
      identity.textContent = element.unsupported
        ? `${what || "Element"} · ${where}. ${element.unsupported}`
        : `${what || "Element"} · ${count}${where ? ` · ${where}` : ""}`;
      identity.hidden = false;
      identity.toggleAttribute(
        "data-ambiguous",
        choice.matches !== 1 || Boolean(element.unsupported),
      );
    };
    if (strategy instanceof HTMLSelectElement) {
      strategy.replaceChildren(
        ...choices.map((choice, index) => {
          const option = document.createElement("option");
          option.value = String(index);
          option.textContent = `${choice.strategy} (${choice.matches})`;
          return option;
        }),
      );
      // Prefer the first strategy that identifies exactly one element.
      const best = Math.max(
        0,
        choices.findIndex(choice => choice.matches === 1),
      );
      strategy.value = String(best);
      strategy.hidden = choices.length < 2;
      strategy.onchange = () => {
        const choice = choices[Number(strategy.value)];
        if (choice) apply(choice);
      };
      const first = choices[best];
      if (first) apply(first);
    }
  };
  /** Rectangle the page actually occupies inside the image box.
   * An `object-fit: contain` image is letterboxed when its box and its
   * natural size differ in proportion, so the box is not the page.
   * @returns {{left:number,top:number,width:number,height:number}}
   */
  content() {
    const box = this.image.getBoundingClientRect();
    const { naturalWidth: width, naturalHeight: height } = this.image;
    if (!width || !height || !box.width || !box.height) return box;
    const scale = Math.min(box.width / width, box.height / height);
    const shown = { width: width * scale, height: height * scale };
    return {
      left: box.left + (box.width - shown.width) / 2,
      top: box.top + (box.height - shown.height) / 2,
      ...shown,
    };
  }
  /** Map a pointer position in the displayed page to target CSS coordinates.
   * @param {MouseEvent} event
   * @returns {{x:number,y:number}|null} Null outside the displayed page.
   */
  point(event) {
    const rect = this.content();
    const viewport = this.viewport();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    if (x < 0 || y < 0 || x > rect.width || y > rect.height) return null;
    return {
      x: Math.min(viewport.width - 1, x * viewport.width / rect.width),
      y: Math.min(viewport.height - 1, y * viewport.height / rect.height),
    };
  }
  /** Serialize forwarded input so target interactions preserve order.
   * @param {Record<string,string|number|boolean>} payload
   * @returns {void}
   */
  input(payload) {
    if (this.latestMove) {
      const move = this.latestMove;
      this.latestMove = null;
      this.pending = this.pending.then(async () => {
        await this.send(move);
      });
    }
    this.pending = this.pending
      .then(async () => {
        await this.send(payload);
      })
      .catch(() => undefined);
  }
  /** Coalesce high-frequency movement to one transport operation per frame.
   * @param {Record<string,string|number|boolean>} payload
   * @returns {void}
   */
  queueMove(payload) {
    this.latestMove = payload;
    if (this.moveFrame !== undefined) return;
    this.moveFrame = window.requestAnimationFrame(() => {
      this.moveFrame = undefined;
      this.pending = this.pending
        .then(async () => {
          const move = this.latestMove;
          this.latestMove = null;
          if (move) await this.send(move);
        })
        .catch(() => undefined);
    });
  }
  /** Fetch and display the latest frame of the Playwright-controlled page.
   * Failures back off so a broken service is never polled at frame rate.
   * @returns {Promise<void>}
   * @throws {Error} When the preview endpoint answers an unexpected status.
   */
  async refresh() {
    const visible = Boolean(this.image.parentElement?.offsetParent);
    let delay = visible ? 250 : 1000;
    try {
      // A hidden panel or tab does no work; it resumes when shown again.
      if (visible && !document.hidden && !this.destroyed) {
        const response = await fetch("/api/target-preview", {
          cache: "no-store",
        });
        if (response.status === 401 || response.status === 403) {
          // The session cookie is gone or changed; a reload obtains a new one.
          this.clear();
          this.show("unauthorized");
          delay = 5000;
        } else if (response.status === 204) {
          this.clear();
          // A browser that is open but has sent no frame yet is "loading";
          // one that is not open is simply closed.
          const open = document
            .getElementById("app")
            ?.hasAttribute("data-target-ready");
          this.show(open ? "loading" : "closed");
          this.failures = 0;
        } else if (response.ok) {
          const blob = await response.blob();
          if (blob.size === 0) {
            // An empty body is not a frame; keep what is shown and wait.
            this.show(this.frameUrl ? "stale" : "loading");
          } else {
            const age = Number(response.headers.get("X-Frame-Age-Ms"));
            // A frame older than three seconds means the page stopped painting.
            const stale = age > 3000;
            this.image.toggleAttribute("data-stale", stale);
            this.image.title = stale ? "Last frame is out of date" : "";
            this.image.setAttribute(
              "data-frame-age",
              Number.isFinite(age) ? String(Math.round(age)) : "",
            );
            const frame = URL.createObjectURL(blob);
            const previous = this.frameUrl;
            this.image.src = frame;
            this.image.hidden = false;
            this.frameUrl = frame;
            if (previous) URL.revokeObjectURL(previous);
            this.show(stale ? "stale" : "live");
          }
          this.failures = 0;
        } else throw new Error(`preview ${response.status}`);
      }
    } catch {
      this.failures += 1;
      this.show("error");
      delay = Math.min(4000, 250 * 2 ** this.failures);
    } finally {
      if (!this.destroyed)
        this.timer = window.setTimeout(() => this.refresh(), delay);
    }
  }
  /** Drop the shown frame and release its object URL.
   * @returns {void}
   */
  clear() {
    this.image.removeAttribute("src");
    this.image.removeAttribute("data-stale");
    // Without a frame the image would show its broken-image icon.
    this.image.hidden = true;
    if (this.frameUrl) URL.revokeObjectURL(this.frameUrl);
    this.frameUrl = null;
  }
  /** Stop polling and release the shown frame.
   * @returns {void}
   */
  destroy() {
    this.destroyed = true;
    window.clearTimeout(this.timer);
    window.cancelAnimationFrame(this.moveFrame ?? 0);
    this.clear();
  }
  /** Name the preview state so loading, closed and failed look different.
   * @param {"loading"|"live"|"stale"|"closed"|"error"|"unauthorized"} state
   * @returns {void}
   */
  show(state) {
    const frame = this.image.closest(".live-target-frame");
    if (frame instanceof HTMLElement) frame.setAttribute("data-preview", state);
    // With the browser gone there is nothing to enlarge or pick from.
    if (state === "closed" || state === "unauthorized") this.maximize(false);
  }
}
