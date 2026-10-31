/** Run browser assertions against Studio modules on a blank page, with no editor. */
import { browserTest } from "../../../common/browser.mjs";
/** Where the Studio's web modules are served from. */
export const WEB = "/exactus/tools/record/studio/web";
/** Open the blank page, then run a test body against it.
 * @param {import('node:test').TestContext} t Test cleanup registry.
 * @param {(page:any)=>Promise<void>} body Browser assertions.
 * @returns {Promise<void>}
 */
export const modulePage = (t, body) =>
  browserTest(t, async (page, url) => {
    await page.goto(`${url}/exactus/tests/tools/record/js/blank.html`);
    await body(page);
  });
