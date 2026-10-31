"use strict";
/**
 * Maintains and renders a textual event log.
 */
class EventLog {
  /**
   * Create an event log.
   *
   * @param {HTMLElement} output Element that receives the rendered entries.
   */
  constructor(output) {
    /** @type {HTMLElement} */
    this.output = output;
    /** @type {string[]} */
    this.entries = [];
  }
  /**
   * Append an entry and render the updated log.
   *
   * @param {string} message Message to append.
   * @returns {void}
   */
  add(message) {
    this.entries.push(message);
    this.render();
  }
  /**
   * Remove every entry and render the empty log.
   *
   * @returns {void}
   */
  clear() {
    this.entries.length = 0;
    this.render();
  }
  /**
   * Render the current entries into the output element.
   *
   * @returns {void}
   */
  render() {
    this.output.textContent = this.entries.join("\n");
  }
}
/**
 * Controls the interactive browser lifecycle example.
 */
class BrowserExample {
  /**
   * Create and initialize the browser example.
   *
   * @param {Document} documentRef Document containing the example controls.
   * @param {Window} windowRef Window used for browser-level operations.
   */
  constructor(documentRef, windowRef) {
    /** @type {Document} */
    this.document = documentRef;
    /** @type {Window} */
    this.window = windowRef;
    /** @type {EventLog} */
    this.log = new EventLog(this.getElement("#events"));
    this.bind();
  }
  /**
   * Return a required example element.
   *
   * @param {string} selector CSS selector identifying the element.
   * @returns {HTMLElement} Matching element.
   * @throws {Error} When the required element does not exist.
   */
  getElement(selector) {
    const element = this.document.querySelector(selector);
    if (!(element instanceof HTMLElement))
      throw new Error(`Required element not found: ${selector}`);
    return element;
  }
  /**
   * Bind the example controls to their browser actions.
   *
   * @returns {void}
   */
  bind() {
    this.getElement("#open").addEventListener("click", () => {
      this.window.open("about:blank", "_blank");
    });
    this.getElement("#log").addEventListener("click", () => {
      this.log.add("event");
    });
    this.getElement("#clear").addEventListener("click", () => {
      this.log.clear();
    });
    this.getElement("#close").addEventListener("click", () => {
      this.window.close();
    });
  }
}
/**
 * Window extended with the active browser example controller.
 *
 * @typedef {Window & {
 *   browserExample?: BrowserExample,
 * }} BrowserExampleWindow
 */
/** @type {BrowserExampleWindow} */ (window).browserExample =
  new BrowserExample(document, window);
