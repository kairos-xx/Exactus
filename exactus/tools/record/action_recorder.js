"use strict";
/**
 * One recorded locator strategy, strongest first.
 * @typedef {object} LocatorCandidate
 * @property {string} kind Strategy: test_id, role, label, placeholder, css.
 * @property {string} [value] Selector or attribute value.
 * @property {string} [role] ARIA role for ``role`` candidates.
 * @property {string} [name] Accessible name for ``role`` candidates.
 */
/**
 * Metadata describing the element an action touched.
 * @typedef {object} TargetMetadata
 * @property {string} tag Lowercased tag name.
 * @property {string} text Visible text, truncated to 256 characters.
 * @property {{x: number, y: number, width: number, height: number}} box
 *   Bounding client rect.
 * @property {LocatorCandidate[]} locators Locator candidates.
 */
/**
 * Pointer position where a potential drag started.
 * @typedef {object} PointerStart
 * @property {HTMLElement} el Element under the pointer.
 * @property {number} x Client X coordinate.
 * @property {number} y Client Y coordinate.
 */
/**
 * Window carrying the recorder install guard flag.
 * @typedef {Window & typeof globalThis & {
 *   __exactusActionRecorderInstalled?: boolean,
 * }} RecorderWindow
 */
(() => {
  const guard = /** @type {RecorderWindow} */ (window);
  if (guard.__exactusActionRecorderInstalled) return;
  guard.__exactusActionRecorderInstalled = true;
  /**
   * Record semantic user interactions and emit them as console payloads.
   */
  class ActionRecorder {
    /** @type {Map<HTMLElement, ReturnType<typeof setTimeout>>} */
    static inputTimers = new Map();
    /** @type {Map<HTMLElement,number>} */
    static inputTimes = new Map();
    /** @type {WeakMap<HTMLElement, ReturnType<typeof setTimeout>>} */
    static scrollTimers = new WeakMap();
    /** @type {ReturnType<typeof setTimeout> | null} */
    static windowScrollTimer = null;
    /** @type {PointerStart | null} */
    static pointer = null;
    /** @type {HTMLElement | null} */
    static drag = null;
    static sequence = 0;
    /** Hover listener types that make an element react to being hovered. */
    static HOVER_EVENTS = new Set([
      "mouseover",
      "mouseenter",
      "pointerover",
      "pointerenter",
      "mousemove",
      "pointermove",
    ]);
    /** Inline handler properties checked on the hovered chain. */
    static HOVER_PROPS = [
      "onmouseover",
      "onmouseenter",
      "onpointerover",
      "onpointerenter",
      "onmousemove",
      "onpointermove",
    ];
    /** @type {WeakSet<EventTarget>} Elements with a hover listener. */
    static hoverListeners = new WeakSet();
    /** @type {{target: TargetMetadata, timer: ReturnType<typeof setTimeout>} | null} */
    static pendingHover = null;
    /** @type {MutationObserver | null} */
    static hoverObserver = null;
    /**
     * Render a value as a JSON-quoted selector fragment.
     * @param {unknown} value Value to quote.
     * @returns {string} JSON string literal.
     */
    static quote = value => JSON.stringify(String(value));
    /**
     * Extract an element's collapsed visible text.
     * @param {Element | null | undefined} el Source element.
     * @returns {string} Whitespace-collapsed text.
     */
    static text = el =>
      ((el instanceof HTMLElement ? el.innerText : el?.textContent) || "")
        .replace(/\s+/gu, " ")
        .trim();
    /**
     * Emit one action record through the console bridge.
     * @param {Record<string, unknown> & {type?: string}} event Action payload fields.
     * @returns {void}
     */
    static emit = event => {
      if (event.type !== "fill" && event.type !== "contenteditable")
        for (const [el, timer] of ActionRecorder.inputTimers) {
          clearTimeout(timer);
          ActionRecorder.flushInput(el);
        }
      console.debug(
        `__EXACTUS_ACTION__${JSON.stringify({
          id: ++ActionRecorder.sequence,
          timestamp: Date.now(),
          url: location.href,
          frameUrl: location.href,
          ...event,
        })}`,
      );
    };
    /**
     * Emit pending input before a subsequent action.
     * @param {HTMLElement} el Input element.
     * @returns {void}
     */
    static flushInput = el => {
      ActionRecorder.inputTimers.delete(el);
      const timestamp = ActionRecorder.inputTimes.get(el) ?? Date.now();
      ActionRecorder.inputTimes.delete(el);
      ActionRecorder.emit({
        timestamp,
        type: el.isContentEditable ? "contenteditable" : "fill",
        target: ActionRecorder.metadata(el),
        value: el.isContentEditable
          ? el.innerText
          : /** @type {HTMLInputElement | HTMLTextAreaElement} */ (el).value,
      });
    };
    /**
     * Promote an event target to its nearest interactive ancestor.
     * @param {EventTarget | null} value Raw event target.
     * @returns {Element | null} Closest interactive element, if any.
     */
    static target = value =>
      value instanceof Element
        ? value.closest(
            "button,a,input,select,textarea,[role],[tabindex],[draggable='true'],[contenteditable='true']",
          ) || value
        : null;
    /**
     * Resolve an element's associated label text.
     * @param {Element | null} el Element to describe.
     * @returns {string} Label, aria-label, or placeholder text.
     */
    static label = el => {
      if (!(el instanceof HTMLElement)) return "";
      const control = /** @type {HTMLInputElement} */ (el);
      if (control.labels?.length)
        return [...control.labels]
          .map(ActionRecorder.text)
          .filter(Boolean)
          .join(" ");
      const aria = el.getAttribute("aria-label")?.trim();
      if (aria) return aria;
      if (el.id) {
        const label = document.querySelector(
          `label[for="${CSS.escape(el.id)}"]`,
        );
        if (label) return ActionRecorder.text(label);
      }
      return el.getAttribute("placeholder")?.trim() || "";
    };
    /**
     * Infer an element's effective ARIA role.
     * @param {HTMLElement} el Element to classify.
     * @returns {string} Explicit or implicit role, else empty.
     */
    static role = el => {
      const explicit = el.getAttribute("role");
      if (explicit) return explicit;
      const tag = el.tagName.toLowerCase();
      if (tag === "button") return "button";
      if (tag === "a" && el.hasAttribute("href")) return "link";
      if (tag === "select") return "combobox";
      if (tag === "textarea") return "textbox";
      if (tag !== "input") return "";
      const type = (el.getAttribute("type") || "text").toLowerCase();
      if (type === "checkbox") return "checkbox";
      if (type === "radio") return "radio";
      if (["button", "submit", "reset"].includes(type)) return "button";
      if (
        [
          "text",
          "email",
          "password",
          "search",
          "tel",
          "url",
          "number",
        ].includes(type)
      )
        return "textbox";
      return "";
    };
    /**
     * Resolve an element's accessible name.
     * @param {HTMLElement} el Element to name.
     * @returns {string} Label, input value, or visible text.
     */
    static name = el =>
      ActionRecorder.label(el) ||
      (el instanceof HTMLInputElement ? el.value : "") ||
      ActionRecorder.text(el);
    /**
     * Build ordered locator candidates for an element.
     * @param {Element | null} el Element to locate later.
     * @returns {LocatorCandidate[]} Candidates, strongest first.
     */
    static candidates = el => {
      if (!(el instanceof HTMLElement)) return [];
      /** @type {LocatorCandidate[]} */
      const result = [];
      const testId =
        el.getAttribute("data-testid") ||
        el.getAttribute("data-test-id") ||
        el.getAttribute("data-test");
      if (testId)
        result.push({
          kind: "test_id",
          value: testId,
        });
      const role = ActionRecorder.role(el);
      const name = ActionRecorder.name(el);
      if (role && name)
        result.push({
          kind: "role",
          role,
          name,
        });
      const label = ActionRecorder.label(el);
      if (label && el.matches("input,textarea,select,[contenteditable='true']"))
        result.push({
          kind: "label",
          value: label,
        });
      const placeholder = el.getAttribute("placeholder");
      if (placeholder)
        result.push({
          kind: "placeholder",
          value: placeholder,
        });
      if (el.id)
        result.push({
          kind: "css",
          value: `#${CSS.escape(el.id)}`,
        });
      const attrName = el.getAttribute("name");
      if (attrName)
        result.push({
          kind: "css",
          value: `${el.tagName.toLowerCase()}[name=${ActionRecorder.quote(attrName)}]`,
        });
      /** @type {string[]} */
      const path = [];
      let current = el;
      while (
        current instanceof HTMLElement &&
        current !== document.documentElement
      ) {
        const parent = current.parentElement;
        const tag = current.tagName.toLowerCase();
        if (!parent) {
          path.unshift(tag);
          break;
        }
        const tagName = current.tagName;
        const siblings = [...parent.children].filter(
          child => child.tagName === tagName,
        );
        path.unshift(
          siblings.length === 1
            ? tag
            : `${tag}:nth-of-type(${siblings.indexOf(current) + 1})`,
        );
        current = parent;
      }
      if (path.length)
        result.push({
          kind: "css",
          value: path.join(" > "),
        });
      return result.filter(candidate => {
        if (candidate.kind !== "css") return true;
        if (!candidate.value) return false;
        const matches = document.querySelectorAll(candidate.value);
        return matches.length === 1 && matches[0] === el;
      });
    };
    /**
     * Capture element metadata for an emitted action.
     * @param {HTMLElement} el Element the action touched.
     * @returns {TargetMetadata} Recorded element metadata.
     */
    static metadata = el => {
      const rect = el.getBoundingClientRect();
      return {
        tag: el.tagName.toLowerCase(),
        text: ActionRecorder.text(el).slice(0, 256),
        box: {
          x: rect.x,
          y: rect.y,
          width: rect.width,
          height: rect.height,
        },
        locators: ActionRecorder.candidates(el),
      };
    };
    /**
     * Emit a click-family action for a mouse event.
     * @param {MouseEvent} event Originating mouse event.
     * @param {string} type Action type to emit.
     * @returns {void}
     */
    static mouse = (event, type) => {
      const el = ActionRecorder.target(event.target);
      if (!(el instanceof HTMLElement)) return;
      ActionRecorder.emit({
        type,
        target: ActionRecorder.metadata(el),
        button: event.button,
        modifiers: {
          alt: event.altKey,
          control: event.ctrlKey,
          meta: event.metaKey,
          shift: event.shiftKey,
        },
      });
    };
    /**
     * Emit a debounced fill action for an input event.
     * @param {Event} event Originating input event.
     * @returns {void}
     */
    static input = event => {
      const el = event.target;
      if (!(
        el instanceof HTMLInputElement ||
        el instanceof HTMLTextAreaElement ||
        el instanceof HTMLElement && el.isContentEditable
      ))
        return;
      if (
        el instanceof HTMLInputElement &&
        ["checkbox", "radio", "button", "submit", "reset", "file"].includes(
          el.type,
        )
      )
        return;
      const prior = ActionRecorder.inputTimers.get(el);
      ActionRecorder.inputTimes.set(el, Date.now());
      if (prior) clearTimeout(prior);
      ActionRecorder.inputTimers.set(
        el,
        setTimeout(() => ActionRecorder.flushInput(el), 300),
      );
    };
    /**
     * Emit select and check actions for a change event.
     * @param {Event} event Originating change event.
     * @returns {void}
     */
    static change = event => {
      const el = event.target;
      if (el instanceof HTMLSelectElement)
        ActionRecorder.emit({
          type: "select",
          target: ActionRecorder.metadata(el),
          values: [...el.selectedOptions].map(o => o.value),
        });
      else if (
        el instanceof HTMLInputElement &&
        ["checkbox", "radio"].includes(el.type)
      )
        ActionRecorder.emit({
          type: el.checked ? "check" : "uncheck",
          target: ActionRecorder.metadata(el),
          checked: el.checked,
        });
    };
    /**
     * Emit a key action for semantic keypresses only.
     * @param {KeyboardEvent} event Originating keydown event.
     * @returns {void}
     */
    static key = event => {
      if (event.isComposing || event.repeat) return;
      const el = event.target instanceof HTMLElement ? event.target : null;
      const textInput =
        el?.matches(
          "input:not([type='checkbox']):not([type='radio']),textarea,[contenteditable='true']",
        ) ?? false;
      const modified = event.ctrlKey || event.altKey || event.metaKey;
      if (textInput && event.key.length === 1 && !modified) return;
      if (textInput && ["Backspace", "Delete"].includes(event.key) && !modified)
        return;
      ActionRecorder.emit({
        type: "key",
        target: el ? ActionRecorder.metadata(el) : null,
        key: event.key,
        modifiers: {
          alt: event.altKey,
          control: event.ctrlKey,
          meta: event.metaKey,
          shift: event.shiftKey,
        },
      });
    };
    /**
     * Emit a debounced scroll action.
     * @param {Event} event Originating scroll event.
     * @returns {void}
     */
    static scroll = event => {
      const el = event.target;
      if (
        el === document ||
        el === document.documentElement ||
        el === document.body
      ) {
        if (ActionRecorder.windowScrollTimer)
          clearTimeout(ActionRecorder.windowScrollTimer);
        ActionRecorder.windowScrollTimer = setTimeout(
          () =>
            ActionRecorder.emit({
              type: "scroll",
              target: null,
              x: scrollX,
              y: scrollY,
            }),
          250,
        );
        return;
      }
      if (!(el instanceof HTMLElement)) return;
      const prior = ActionRecorder.scrollTimers.get(el);
      if (prior) clearTimeout(prior);
      ActionRecorder.scrollTimers.set(
        el,
        setTimeout(() => {
          ActionRecorder.emit({
            type: "scroll",
            target: ActionRecorder.metadata(el),
            x: el.scrollLeft,
            y: el.scrollTop,
          });
          ActionRecorder.scrollTimers.delete(el);
        }, 250),
      );
    };
    /**
     * Emit a wheel action.
     * @param {WheelEvent} event Originating wheel event.
     * @returns {void}
     */
    static wheel = event =>
      ActionRecorder.emit({
        type: "wheel",
        target:
          event.target instanceof HTMLElement
            ? ActionRecorder.metadata(event.target)
            : null,
        deltaX: event.deltaX,
        deltaY: event.deltaY,
        deltaMode: event.deltaMode,
      });
    /**
     * Remember where a potential pointer drag started.
     * @param {PointerEvent} event Originating pointerdown event.
     * @returns {void}
     */
    static pointerDown = event => {
      if (event.button === 0 && event.target instanceof HTMLElement)
        ActionRecorder.pointer = {
          el: event.target,
          x: event.clientX,
          y: event.clientY,
        };
    };
    /**
     * Emit a drag action when the pointer travels far enough.
     * @param {PointerEvent} event Originating pointerup event.
     * @returns {void}
     */
    static pointerUp = event => {
      const start = ActionRecorder.pointer;
      ActionRecorder.pointer = null;
      if (
        !start ||
        !(event.target instanceof HTMLElement) ||
        Math.hypot(event.clientX - start.x, event.clientY - start.y) < 5
      )
        return;
      ActionRecorder.emit({
        type: "drag",
        source: ActionRecorder.metadata(start.el),
        target: ActionRecorder.metadata(event.target),
        start: {
          x: start.x,
          y: start.y,
        },
        end: {
          x: event.clientX,
          y: event.clientY,
        },
      });
    };
    /**
     * Remember the element a native drag started on.
     * @param {DragEvent} event Originating dragstart event.
     * @returns {void}
     */
    static dragStart = event => {
      if (event.target instanceof HTMLElement)
        ActionRecorder.drag = event.target;
    };
    /**
     * Emit a drag action on a native drop.
     * @param {DragEvent} event Originating drop event.
     * @returns {void}
     */
    static drop = event => {
      const source = ActionRecorder.drag;
      ActionRecorder.drag = null;
      if (
        source &&
        event.target instanceof HTMLElement &&
        source !== event.target
      )
        ActionRecorder.emit({
          type: "drag",
          source: ActionRecorder.metadata(source),
          target: ActionRecorder.metadata(event.target),
        });
    };
    /**
     * Emit a focus action.
     * @param {FocusEvent} event Originating focusin event.
     * @returns {void}
     */
    static focus = event => {
      if (event.target instanceof HTMLElement)
        ActionRecorder.emit({
          type: "focus",
          target: ActionRecorder.metadata(event.target),
        });
    };
    /**
     * Whether hovering runs element-scoped JS: any node from the raw
     * event target through the promoted target listens for a hover
     * event or carries an inline ``on*`` handler. Listeners delegated to
     * page roots (document, window, framework containers) are outside
     * that chain on purpose, so framework apps do not flag every hover.
     * @param {MouseEvent} event Originating mouseover event.
     * @param {HTMLElement} el Promoted hover target.
     * @returns {boolean} True when the hover runs element-scoped JS.
     */
    static handlesHover = (event, el) => {
      const path = event.composedPath();
      const limit = path.indexOf(el);
      const chain = limit < 0 ? path.slice(0, 1) : path.slice(0, limit + 1);
      for (const node of chain) {
        if (!(node instanceof Element)) continue;
        if (ActionRecorder.hoverListeners.has(node)) return true;
        const control = /** @type {HTMLElement} */ (node);
        for (const prop of ActionRecorder.HOVER_PROPS) {
          const handler = control[/** @type {keyof HTMLElement} */ (prop)];
          if (typeof handler === "function" || node.hasAttribute(prop))
            return true;
        }
      }
      return false;
    };
    /**
     * Stop watching for a DOM change caused by the pending hover.
     * @returns {void}
     */
    static cancelHover = () => {
      if (ActionRecorder.pendingHover)
        clearTimeout(ActionRecorder.pendingHover.timer);
      ActionRecorder.pendingHover = null;
      if (ActionRecorder.hoverObserver)
        ActionRecorder.hoverObserver.disconnect();
    };
    /**
     * Emit a hover action when its DOM change lands within the window.
     * @param {TargetMetadata} target Hover target captured at dispatch.
     * @returns {void}
     */
    static armHover = target => {
      ActionRecorder.cancelHover();
      ActionRecorder.hoverObserver ||= new MutationObserver(() => {
        const pending = ActionRecorder.pendingHover;
        if (!pending) return;
        ActionRecorder.cancelHover();
        ActionRecorder.emit({
          type: "hover",
          target: pending.target,
        });
      });
      ActionRecorder.pendingHover = {
        target,
        timer: setTimeout(ActionRecorder.cancelHover, 250),
      };
      ActionRecorder.hoverObserver.observe(document, {
        subtree: true,
        childList: true,
        attributes: true,
        characterData: true,
      });
    };
    /**
     * Emit a hover action only when hovering runs element-scoped JS or
     * produces a DOM change; pure pointer traversal is dropped.
     * @param {MouseEvent} event Originating mouseover event.
     * @returns {void}
     */
    static hover = event => {
      const el = ActionRecorder.target(event.target);
      if (!(el instanceof HTMLElement)) return;
      const target = ActionRecorder.metadata(el);
      if (ActionRecorder.handlesHover(event, el)) {
        ActionRecorder.emit({
          type: "hover",
          target,
        });
        return;
      }
      ActionRecorder.armHover(target);
    };
    /**
     * Track elements that register hover listeners so ``handlesHover``
     * can tell whether hovering runs element-scoped JS. Runs after
     * ``install`` so the recorder's own listeners are never counted.
     * @returns {void}
     */
    static hookListeners = () => {
      const original = EventTarget.prototype.addEventListener;
      /**
       * Record elements that register hover listeners.
       * @param {string} type Event type being registered.
       * @param {EventListenerOrEventListenerObject | null} listener Handler.
       * @param {boolean | AddEventListenerOptions} [options] Options.
       * @returns {void}
       */
      EventTarget.prototype.addEventListener = function (
        type,
        listener,
        options,
      ) {
        if (ActionRecorder.HOVER_EVENTS.has(String(type)))
          ActionRecorder.hoverListeners.add(this);
        return original.call(this, type, listener, options);
      };
    };
    /**
     * Attach every capture listener to the document.
     * @returns {void}
     */
    static install = () => {
      document.addEventListener(
        "click",
        event =>
          ActionRecorder.mouse(
            event,
            event.detail === 2 ? "double_click" : "click",
          ),
        true,
      );
      document.addEventListener(
        "contextmenu",
        event => ActionRecorder.mouse(event, "right_click"),
        true,
      );
      document.addEventListener("input", ActionRecorder.input, true);
      document.addEventListener("__EXACTUS_RECORDER_FLUSH__", () => {
        for (const [element, timer] of ActionRecorder.inputTimers) {
          clearTimeout(timer);
          ActionRecorder.flushInput(element);
        }
      });
      document.addEventListener("change", ActionRecorder.change, true);
      document.addEventListener("keydown", ActionRecorder.key, true);
      document.addEventListener("scroll", ActionRecorder.scroll, true);
      document.addEventListener("wheel", ActionRecorder.wheel, {
        capture: true,
        passive: true,
      });
      document.addEventListener(
        "pointerdown",
        ActionRecorder.pointerDown,
        true,
      );
      document.addEventListener("pointerup", ActionRecorder.pointerUp, true);
      document.addEventListener("dragstart", ActionRecorder.dragStart, true);
      document.addEventListener("drop", ActionRecorder.drop, true);
      document.addEventListener("focusin", ActionRecorder.focus, true);
      document.addEventListener("mouseover", ActionRecorder.hover, true);
    };
  }
  ActionRecorder.install();
  ActionRecorder.hookListeners();
})();
