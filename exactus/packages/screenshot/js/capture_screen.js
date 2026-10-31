"use strict";
/**
 * @typedef {object} ViewportSize
 * @property {number} width Viewport width in pixels.
 * @property {number} height Viewport height in pixels.
 */
/**
 * Minimal Playwright element-handle surface used by this capture.
 * @typedef {object} ElementHandleLike
 * @property {(fn: (root: Element) => unknown) => Promise<unknown>} evaluate
 *   Run a function against the element in page context.
 */
/**
 * Minimal Playwright page surface used by this capture.
 * @typedef {object} PageLike
 * @property {() => ViewportSize | null} viewportSize Current viewport.
 * @property {(selector: string) => Promise<ElementHandleLike | null>} $
 *   Resolve a selector to an element handle.
 * @property {(fn: () => unknown) => Promise<unknown>} evaluate
 *   Run a function in page context.
 * @property {(size: ViewportSize) => Promise<unknown>} setViewportSize
 *   Resize the viewport.
 * @property {(options?: object) => Promise<Uint8Array>} screenshot
 *   Capture a screenshot.
 */
/**
 * @typedef {[HTMLElement | SVGElement, string | null]} StyleBackup
 *   Original inline style captured per mutated element.
 */
/**
 * @typedef {[HTMLElement, number, number]} ScrollBackup
 *   Original scroll offsets captured per mutated element.
 */
/**
 * @typedef {object} CaptureState
 * @property {StyleBackup[]} styles Saved inline styles to restore.
 * @property {ScrollBackup[]} scrolls Saved scroll offsets to restore.
 */
/**
 * Window carrying the cross-evaluate capture state stash.
 * @typedef {Window & typeof globalThis & {
 *   __snapshotCapture?: CaptureState,
 * }} CaptureWindow
 */
/**
 * @typedef {object} MeasureResult
 * @property {number} height Viewport height required for the full capture.
 * @property {string} signature Layout signature used to detect stability.
 * @property {number} viewportHeight Current viewport height in pixels.
 */
/**
 * Capture a full-height screenshot of a target element.
 */
export class SnapshotCapture {
  /**
   * @param {PageLike} page Playwright page used for capture.
   * @param {string | ElementHandleLike} target Selector or element handle.
   */
  constructor(page, target) {
    /** @type {PageLike} */
    this.page = page;
    /** @type {string | ElementHandleLike} */
    this.target = target;
  }
  /**
   * Expand the target to its natural height and screenshot it.
   * @param {object} [options] Capture options such as clip and path.
   * @returns {Promise<Uint8Array>} The screenshot result.
   * @throws {Error} When the page has no configured viewport.
   * @throws {TypeError} When the target element cannot be found.
   */
  async capture(options = {}) {
    const viewport = this.page.viewportSize();
    if (!viewport)
      throw new Error("Playwright page must have a configured viewport.");
    const root =
      typeof this.target === "string"
        ? await this.page.$(this.target)
        : this.target;
    if (!root) throw new TypeError("Target element was not found.");
    const settle = () =>
      this.page.evaluate(
        () =>
          new Promise(resolve => {
            requestAnimationFrame(() => requestAnimationFrame(resolve));
          }),
      );
    try {
      await root.evaluate(captureRoot => {
        const host = /** @type {CaptureWindow} */ (window);
        const state = /** @type {CaptureState} */ ({
          styles: [],
          scrolls: [],
        });
        host.__snapshotCapture = state;
        for (const element of [
          captureRoot,
          ...captureRoot.querySelectorAll("*"),
        ]) {
          if (!(
            element instanceof HTMLElement || element instanceof SVGElement
          ))
            continue;
          const { overflowY, maxHeight } = getComputedStyle(element);
          if (
            !["auto", "scroll", "hidden", "clip"].includes(overflowY) &&
            maxHeight === "none" &&
            element.scrollHeight <= element.clientHeight + 1
          )
            continue;
          state.styles.push([element, element.getAttribute("style")]);
          if (element instanceof HTMLElement)
            state.scrolls.push([
              element,
              element.scrollLeft,
              element.scrollTop,
            ]);
          element.style.cssText +=
            ";height:auto!important;max-height:none!important;overflow-y:visible!important";
        }
      });
      /**
       * Settle and resize one step at a time until the document stabilizes.
       * @param {number} iteration
       * @param {string|undefined} previous
       * @returns {Promise<void>}
       */
      const resizeUntilStable = async (iteration, previous) => {
        if (iteration >= 20) return;
        await settle();
        const { height, signature, viewportHeight } =
          /** @type {MeasureResult} */
          (
            await root.evaluate(captureRoot => {
              const values = [
                captureRoot,
                ...captureRoot.querySelectorAll("*"),
              ].map(element => {
                const { top, height: captureHeight } =
                  element.getBoundingClientRect();
                return `${Math.round(top)}:${Math.round(captureHeight)}:${element.scrollHeight ?? 0}:${element.clientHeight ?? 0}`;
              });
              const { top, bottom } = captureRoot.getBoundingClientRect();
              return {
                height: Math.ceil(
                  top +
                    captureRoot.scrollHeight +
                    Math.max(
                      document.documentElement.scrollHeight,
                      document.body?.scrollHeight ?? 0,
                    ) -
                    bottom,
                ),
                signature: values.join("|"),
                viewportHeight: innerHeight,
              };
            })
          );
        const current = `${height}|${signature}`;
        if (current === previous && height === viewportHeight) return;
        if (height !== viewportHeight)
          await this.page.setViewportSize({
            width: viewport.width,
            height,
          });
        await resizeUntilStable(iteration + 1, current);
      };
      await resizeUntilStable(0, undefined);
      await settle();
      return await this.page.screenshot({
        ...options,
        fullPage: true,
      });
    } finally {
      await root
        .evaluate(() => {
          const host = /** @type {CaptureWindow} */ (window);
          const state = host.__snapshotCapture;
          if (!state) return;
          for (const [element, style] of state.styles)
            style === null
              ? element.removeAttribute("style")
              : element.setAttribute("style", style);
          for (const [element, left, top] of state.scrolls)
            Object.assign(element, {
              scrollLeft: left,
              scrollTop: top,
            });
          delete host.__snapshotCapture;
        })
        .catch(() => {});
      await this.page.setViewportSize(viewport);
    }
  }
}
