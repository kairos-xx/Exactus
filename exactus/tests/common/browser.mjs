import process from "node:process";
/** Run browser assertions and retain their V8 coverage for the exactus gate. */
import { execFileSync } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { createRequire } from "node:module";
import { join, resolve, extname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { randomUUID } from "node:crypto";
export const root = fileURLToPath(new URL("../../..", import.meta.url));
const { EXACTUS_PROJECT_PYTHON } = process.env;
const python = EXACTUS_PROJECT_PYTHON || join(root, ".venv/bin/python");
const driver = execFileSync(
  python,
  [
    "-c",
    "from pathlib import Path; import playwright; print(Path(playwright.__file__).parent / 'driver' / 'package')",
  ],
  {
    encoding: "utf8",
  },
).trim();
const { chromium } = createRequire(import.meta.url)(driver);
/** Serve the repository over loopback and run a Chromium test body.
 * @param {import('node:test').TestContext} t Test cleanup registry.
 * @param {(page:any,url:string)=>Promise<void>} exercise Async browser body.
 * @returns {Promise<void>}
 * @throws {Error} When Chromium cannot launch or the body rejects.
 */
export const browserTest = async (t, exercise) => {
  const server = createServer(async (request, response) => {
    const path = resolve(
      root,
      `.${new URL(request.url ?? "/", "http://localhost").pathname}`,
    );
    if (!path.startsWith(root)) {
      response.writeHead(403).end();
      return;
    }
    try {
      const bytes = await readFile(path);
      /** @type {Record<string, string>} */
      const mime = {
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".html": "text/html",
        ".css": "text/css",
        ".json": "application/json",
      };
      response.setHeader(
        "Content-Type",
        mime[extname(path)] || "application/octet-stream",
      );
      response.end(bytes);
    } catch {
      response.writeHead(404).end();
    }
  });
  await /** @type {Promise<void>} */ (
    new Promise(done => {
      server.listen(0, "127.0.0.1", () => done());
    })
  );
  const browser = await chromium.launch({
    headless: true,
  });
  const page = await browser.newPage({
    viewport: {
      width: 1440,
      height: 900,
    },
  });
  page.setDefaultTimeout(5000);
  t.after(async () => {
    await browser.close();
    await /** @type {Promise<void>} */ (
      new Promise(done => {
        server.close(() => done());
      })
    );
  });
  await page.coverage.startJSCoverage({
    resetOnNavigation: false,
  });
  const address = server.address();
  if (address === null || typeof address === "string")
    throw new Error("Probe server has no port.");
  const url = `http://127.0.0.1:${address.port}`;
  try {
    await exercise(page, url);
  } finally {
    const entries = await page.coverage.stopJSCoverage();
    const { NODE_V8_COVERAGE } = process.env;
    if (NODE_V8_COVERAGE) {
      const result = entries
        .filter((/** @type {any} */ entry) => entry.url.startsWith(url))
        .map((/** @type {any} */ entry) => ({
          ...entry,
          url: pathToFileURL(join(root, new URL(entry.url).pathname)).href,
        }));
      await writeFile(
        join(NODE_V8_COVERAGE, `coverage-browser-${randomUUID()}.json`),
        JSON.stringify({
          result,
        }),
      );
    }
  }
};
