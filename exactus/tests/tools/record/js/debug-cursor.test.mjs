/* Temporary geometry probe for the timeline playhead scroll failure. */
import test from "node:test";
import { browserTest } from "../../../common/browser.mjs";
import { studio } from "./studio.test.mjs";
test("cursor debug probe", async t => {
  await browserTest(t, async (page, url) => {
    await studio(page, url);
    /** Log the timeline and playhead geometry under a phase label.
     * @param {string} tag Label printed before the serialized geometry.
     * @returns {Promise<void>}
     */
    const dump = async tag =>
      console.log(
        tag,
        JSON.stringify(
          await page.evaluate(() => {
            const ti = document.querySelector("#timeline");
            const c = document.querySelector(".timeline-cursor");
            const r = ti?.querySelector(".ruler-ticks");
            const l = ti?.querySelector(".track-label");
            if (!(ti instanceof HTMLElement) || !(c instanceof HTMLElement))
              return { dead: true };
            return {
              ms: c.getAttribute("aria-valuenow"),
              scrollLeft: ti.scrollLeft,
              clientWidth: ti.clientWidth,
              scrollWidth: ti.scrollWidth,
              cursorStyleLeft: c.style.left,
              cursorBoxX: c.getBoundingClientRect().left,
              timelineX: ti.getBoundingClientRect().left,
              rulerViewX:
                r instanceof HTMLElement
                  ? r.getBoundingClientRect().left -
                    ti.getBoundingClientRect().left
                  : null,
              labelViewRight:
                l instanceof HTMLElement
                  ? l.getBoundingClientRect().right -
                    ti.getBoundingClientRect().left
                  : null,
              labelPos: l ? getComputedStyle(l).position : null,
              vis: getComputedStyle(c).visibility,
              display: getComputedStyle(c).display,
              w: c.getBoundingClientRect().width,
            };
          }),
        ),
      );
    const ruler = await page.locator(".ruler-ticks").boundingBox();
    await page.mouse.click(ruler.x + 144, ruler.y + 12);
    const cursor = page.locator(".timeline-cursor");
    await dump("after ruler click");
    const handle = await cursor.boundingBox();
    await page.mouse.move(handle.x + handle.width / 2, handle.y + 12);
    await page.mouse.down();
    await page.mouse.move(handle.x + handle.width / 2 + 96, handle.y + 12);
    await page.waitForFunction(
      () =>
        document
          .querySelector(".timeline-cursor")
          ?.getAttribute("aria-valuenow") === "2500",
    );
    await page.mouse.up();
    await cursor.press("ArrowRight");
    await page.locator("#timeline-zoom").press("End");
    await dump("after zoom end");
    const timeline = await page.locator("#timeline").boundingBox();
    const dragHead = await cursor.boundingBox();
    console.log("dragHead", JSON.stringify(dragHead));
    await page.mouse.move(dragHead.x + dragHead.width / 2, dragHead.y + 12);
    await page.mouse.down();
    await page.mouse.move(timeline.x + timeline.width - 5, timeline.y + 12);
    await page.waitForFunction(
      () => (document.querySelector("#timeline")?.scrollLeft ?? 0) > 0,
    );
    await page.keyboard.press("Escape");
    await page.mouse.up();
    await dump("after edge drag + escape");
    await page
      .locator("#timeline")
      .evaluate((/** @type {HTMLElement} */ element) => {
        element.scrollTop = 80;
        element.scrollLeft = 0;
      });
    await dump("after scroll reset");
    const beforeScroll = await cursor.boundingBox();
    console.log("beforeScroll", JSON.stringify(beforeScroll));
    await dump("after beforeScroll bbox");
    await page
      .locator("#timeline")
      .evaluate((/** @type {HTMLElement} */ element) => {
        element.scrollLeft = 100;
      });
    await page.waitForFunction(
      () => document.querySelector("#timeline")?.scrollLeft === 100,
    );
    await dump("after scroll 100");
    const afterScroll = await cursor.boundingBox();
    console.log("afterScroll", JSON.stringify(afterScroll));
    await dump("final");
  });
});
