/** Exercise report rendering, filtering, safe links, evidence and source excerpts. */
/* global ExactusReport */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { pathToFileURL } from "node:url";
import { join } from "node:path";
import { browserTest, root } from "../../../common/browser.mjs";
const source = join(root, "exactus/tools/common/templates/html/report.js");
const context = {
  document: {
    addEventListener: () => {},
  },
};
runInNewContext(
  `${readFileSync(source, "utf8")}\nglobalThis.Report = ExactusReport;`,
  context,
  {
    filename: pathToFileURL(source).href,
  },
);
const Report = /** @type {any} */ (context).Report;
test("artifact names are plain and only the Path column contains a link", async t => {
  await browserTest(t, async (page, url) => {
    await page.goto(`${url}/exactus/tools/actions/examples/web/index.html`);
    await page.setContent('<main id="report-view"></main>');
    await page.addScriptTag({
      url: `${url}/exactus/tools/common/templates/html/report.js`,
    });
    await page.evaluate(() => {
      ExactusReport.localLinks = {
        "README.md": "../../README.md",
        "ARTIFACTS/README.md": "ARTIFACTS/README.md",
      };
      const section = ExactusReport.viewSections({
        view: {
          artifacts: [
            {
              name: "README.md",
              path: "ARTIFACTS/README.md",
              bytes: 5,
            },
          ],
        },
        view_columns: {
          artifacts: ["name", "path", "bytes"],
        },
      }).find(entry => entry.title === "Artifacts");
      const target = document.querySelector("#report-view");
      if (target && section) target.innerHTML = section.body;
    });
    const cells = page.locator("tbody tr").first().locator("td");
    assert.equal(await cells.nth(0).innerText(), "README.md");
    assert.equal(await cells.nth(0).locator("a").count(), 0);
    assert.equal(await cells.nth(1).locator("a").count(), 1);
    assert.equal(
      await cells.nth(1).locator("a").getAttribute("href"),
      "../ARTIFACTS/README.md",
    );
  });
});
test("report Markdown escapes code, rejects active links, and preserves relative links", () => {
  assert.match(Report.markdown("~~~js\nalert('<x>')\n~~~"), /&lt;x&gt;/);
  for (const scheme of [
    `${"javascript"}:alert(1)`,
    "data:text/html,x",
    "vbscript:run",
  ])
    assert.ok(!Report.inline(`[link](${scheme})`).includes("<a "));
  for (const href of [
    "#finding",
    "exactus/docs/report.md",
    "https://example.com",
    "/source.py",
  ])
    assert.match(Report.inline(`[file](${href})`), /<a href=/);
  assert.match(
    Report.markdown(
      "# Heading\n\n- first\n- second\n\n> quote\n\n| A | B |\n|---|---|\n|1|2|",
    ),
    /<h[12][ >]/,
  );
  assert.match(
    Report.inline("`f(*args)` **strong** *em*"),
    /<code>f\(\*args\)<\/code>/,
  );
});
test("subsection comparisons distinguish a first run and unavailable historical detail", () => {
  assert.match(
    Report.comparisonSection({
      comparison: {
        available: false,
      },
    }),
    /baseline/,
  );
  assert.match(
    Report.comparisonSection({
      comparison: {
        available: true,
        current_total: 2,
        previous_total: 3,
        delta: -1,
        added_count: null,
        categories: [
          {
            category: "ruff",
            title: "Ruff",
            current: 2,
            previous: 3,
            delta: -1,
          },
        ],
        metrics: [
          {
            metric: "coverage",
            current: 95,
            previous: 90,
            delta: 5,
          },
        ],
      },
    }),
    /Category findings/,
  );
  assert.match(
    Report.recordTable("Values", [
      {
        name: "<script>",
        total: 0,
      },
      {
        name: "link",
        total: 2,
      },
    ]),
    /&lt;script&gt;/,
  );
});
test("normalized report views render findings, source snippets, filtering, and sorted delta tables", async t => {
  await browserTest(t, async (page, url) => {
    await page.goto(`${url}/exactus/tools/actions/examples/web/index.html`);
    await page.setContent(
      '<h1 id="report-title"></h1><div id="report-status"></div><div id="report-resume"></div><div id="report-metrics"></div><main id="report-view"></main><article id="report"></article><dl id="report-context"></dl>',
    );
    await page.addScriptTag({
      url: `${url}/exactus/tools/common/templates/html/report.js`,
    });
    await page.addScriptTag({
      content: "globalThis.reportRenderer = ExactusReport;",
    });
    const data = JSON.parse(
      readFileSync(
        join(
          root,
          "exactus/tools/common/templates/markdown/examples/result.json",
        ),
        "utf8",
      ),
    );
    data.comparison = {
      available: true,
      current_total: 3,
      previous_total: 4,
      delta: -1,
      added_count: 0,
      resolved_count: 1,
      unchanged_count: 3,
      categories: [
        {
          category: "ruff",
          title: "Ruff",
          current: 3,
          previous: 4,
          delta: -1,
        },
        {
          category: "E722",
          title: "Bare except",
          current: 0,
          previous: 0,
          delta: 0,
        },
      ],
      metrics: [
        {
          metric: "coverage",
          current: 95,
          previous: 90,
          delta: 5,
        },
      ],
    };
    await page.evaluate((/** @type {any} */ model) => {
      /** @type {any} */
      (globalThis).__REPORT_DATA__ = {
        title: "Exactus example",
        analyzer: "lints",
        status: "FAIL",
        view: model,
        comparison: model.comparison,
      };
      /** @type {any} */
      (globalThis).reportRenderer.init();
    }, data);
    assert.match(
      await page.locator("#report-view").innerText(),
      /Findings|findings/,
    );
    const table = page
      .getByRole("region", {
        name: "Category findings",
        exact: true,
      })
      .locator("table");
    await table.locator('[data-sort-column="3"]').click();
    assert.equal(
      await table.locator("th[aria-sort]").getAttribute("aria-sort"),
      "ascending",
    );
    await table.locator('[data-sort-column="3"]').click();
    assert.equal(
      await table.locator("th[aria-sort]").getAttribute("aria-sort"),
      "descending",
    );
    await page.evaluate(() => {
      const snippet = /** @type {any} */ (
        globalThis
      ).reportRenderer.snippetViewer(
        {
          start: 1,
          line: 2,
          text: "a\nb\nc",
        },
        "Example",
      );
      const host = /** @type {HTMLElement} */ (
        document.getElementById("report")
      );
      host.innerHTML = snippet;
      /** @type {any} */
      (globalThis).reportRenderer.bindSnippets(host);
    });
  });
});
test("coverage reports filter lanes and paths, preserve expanded files, and adjust source context", async t => {
  await browserTest(t, async (page, url) => {
    await page.goto(`${url}/exactus/tools/actions/examples/web/index.html`);
    await page.setContent(
      '<h1 id="report-title"></h1><div id="report-status"></div><div id="report-resume"></div><div id="report-metrics"></div><main id="report-view"></main><article id="report"></article><dl id="report-context"></dl>',
    );
    await page.addScriptTag({
      url: `${url}/exactus/tools/common/templates/html/report.js`,
    });
    await page.addScriptTag({
      content: "globalThis.reportRenderer = ExactusReport;",
    });
    const snippets = {
      context: 3,
      language: "python",
      truncated: true,
      hunks: [
        {
          lines: Array.from(
            {
              length: 9,
            },
            (_, i) => ({
              n: i + 1,
              text: i === 4 ? 'return "missing"' : "# context",
              hit: i === 4,
            }),
          ),
        },
      ],
    };
    await page.evaluate((/** @type {any} */ sourceSnippets) => {
      /** @type {any} */
      (globalThis).__REPORT_DATA__ = {
        analyzer: "coverage",
        status: "FAIL",
        project_href: "../..",
        test_execution: {
          failed_tests: ["test_save"],
        },
        coverage: {
          totals: {
            percent_covered: 50,
            num_statements: 10,
            missing_lines: 5,
          },
          files: {
            "src/run.py": {
              summary: {
                percent_covered: 50,
                num_statements: 10,
                missing_lines: 5,
              },
              missing_lines: [2, 3, 5],
              snippets: sourceSnippets,
            },
          },
        },
        javascript: {
          percent_covered: 75,
          files: [
            {
              path: "app.js",
              num_statements: 4,
              covered_lines: 3,
              missing_lines: 1,
              uncovered_lines: [5],
              percent_covered: 75,
              snippets: {
                ...sourceSnippets,
                language: "javascript",
              },
            },
          ],
        },
      };
      /** @type {any} */
      (globalThis).reportRenderer.init();
    }, snippets);
    assert.match(await page.locator("#uncovered-count").innerText(), /2 files/);
    await page.locator("#expand-all").click();
    assert.equal(
      await page.locator("#uncovered-groups details[open]").count(),
      2,
    );
    await page.locator("#context-lines").fill("0");
    assert.equal(await page.locator("#context-value").innerText(), "0");
    assert.equal(
      await page.locator("#uncovered-groups details[open]").count(),
      2,
    );
    await page.locator("#collapse-all").click();
    assert.equal(
      await page.locator("#uncovered-groups details[open]").count(),
      0,
    );
    await page.locator(".code-index a").first().click();
    assert.equal(
      await page.locator("#uncovered-groups details[open]").count(),
      1,
    );
    await page.locator('button[data-lane="javascript"]').click();
    assert.match(await page.locator("#uncovered-count").innerText(), /1 file/);
    await page.locator("#uncovered-search").fill("absent");
    assert.match(
      await page.locator("#uncovered-count").innerText(),
      /No files match/,
    );
    await page.locator("#uncovered-search").fill("app");
    assert.match(await page.locator("#uncovered-count").innerText(), /1 file/);
  });
});
test("fallback findings, frontend evidence and pipeline reports expose their real outcomes", async t => {
  await browserTest(t, async (page, url) => {
    await page.goto(`${url}/exactus/tools/actions/examples/web/index.html`);
    await page.setContent(
      '<h1 id="report-title"></h1><div id="report-status"></div><div id="report-resume"></div><div id="report-metrics"></div><main id="report-view"></main><article id="report"></article><dl id="report-context"></dl>',
    );
    await page.addScriptTag({
      url: `${url}/exactus/tools/common/templates/html/report.js`,
    });
    await page.addScriptTag({
      content: "globalThis.reportRenderer = ExactusReport;",
    });
    const render = async (/** @type {any} */ data) =>
      page.evaluate((/** @type {any} */ payload) => {
        /** @type {any} */
        (globalThis).__REPORT_DATA__ = payload;
        /** @type {any} */
        (globalThis).reportRenderer.init();
      }, data);
    await render({
      analyzer: "lints",
      status: "FAIL",
      findings: [
        {
          path: "src/a.py",
          line: 2,
          rule: "E1",
          severity: "error",
          message: "Broken save",
        },
        {
          path: "src/b.py",
          line: 1,
          rule: "W1",
          severity: "warning",
          message: "Slow save",
        },
      ],
    });
    assert.match(
      await page.locator("#finding-count").innerText(),
      /2 findings/,
    );
    await page.locator('button[data-severity="error"]').click();
    assert.match(await page.locator("#finding-count").innerText(), /1 finding/);
    await page.locator("#finding-search").fill("absent");
    assert.match(
      await page.locator("#finding-count").innerText(),
      /No findings match/,
    );
    await render({
      analyzer: "frontend",
      status: "FAIL",
      flows: [
        {
          flow_id: "checkout",
          run_id: "run1",
          status: "failed",
          error: "Missing confirmation",
          action_records: [
            {
              event_id: "save",
              flow_id: "checkout",
              label: "Save order",
              kind: "javascript",
              status: "failed",
              started_ms: 0,
              finished_ms: 100,
              script: "document.title",
              response: {
                title: "Order",
              },
              assertions: [
                {
                  outcome: "failed",
                  assertion_id: "saved",
                  details: "Missing confirmation",
                  actual: "Pending",
                },
              ],
              screenshot_artifact_ids: ["shot"],
            },
          ],
        },
      ],
      evidence: [
        {
          type: "screenshot",
          artifact_id: "shot",
          path: "order.png",
        },
      ],
      findings: [
        {
          message: "Missing confirmation",
        },
      ],
      actions: [
        {
          id: "test",
          tool: "frontend",
          status: "failed",
        },
      ],
      discovery_diagnostics: ["Navigation timed out"],
      server_diagnostics: ["Server ready"],
    });
    assert.match(await page.locator("#report-view").innerText(), /Save order/);
    assert.equal(await page.locator(".flow-step").getAttribute("open"), "");
    assert.match(
      await page.locator(".flow-step").innerText(),
      /document.title/,
    );
    assert.equal(await page.locator(".flow-step img").count(), 1);
    await page.locator(".flow-step summary").click();
    assert.equal(await page.locator(".flow-step").getAttribute("open"), null);
    await page.locator(".flow-step summary").click();
    assert.match(
      await page.locator(".flow-step").innerText(),
      /document.title/,
    );
    await render({
      kind: "pipeline",
      status: "FAIL",
      tools: {
        lints: {
          passed: false,
          status: "FAIL",
          duration_seconds: 2,
          resume: "One finding",
          report_web_href: "../../LINTS/result_web/index.html",
        },
        readme: {
          passed: true,
          status: "PASS",
          report_web: "/project/README/result_web/index.html",
        },
      },
    });
    assert.match(await page.locator("#report-resume").innerText(), /Fix lints/);
    assert.equal(
      await page.locator("a.tool-link").first().getAttribute("href"),
      "../../LINTS/result_web/index.html",
    );
    await render({
      kind: "pipeline",
      passed: true,
      tools: {
        readme: {
          passed: true,
          status: "PASS",
        },
      },
    });
    assert.match(
      await page.locator("#report-resume").innerText(),
      /Every tool passed/,
    );
    await render({
      analyzer: "lints",
      findings: [],
    });
    assert.match(
      await page.locator("#report-resume").innerText(),
      /No findings/,
    );
  });
});
test("source excerpts retain safe syntax highlighting and bounded context controls", async t => {
  await browserTest(t, async (page, url) => {
    await page.goto(`${url}/exactus/tools/actions/examples/web/index.html`);
    await page.addScriptTag({
      url: `${url}/exactus/tools/common/templates/html/report.js`,
    });
    await page.addScriptTag({
      content: "globalThis.reportRenderer = ExactusReport;",
    });
    await page.evaluate(() => {
      document.body.innerHTML = /** @type {any} */ (
        globalThis
      ).reportRenderer.snippetViewer(
        {
          line: 3,
          language: "python",
          clipped: true,
          lines: [
            {
              n: 1,
              text: "def save():",
            },
            {
              n: 2,
              text: "    # safe <script>",
            },
            {
              n: 3,
              text: '    return "Saved"',
            },
            {
              n: 4,
              text: "",
            },
            {
              n: 5,
              text: "save()",
            },
          ],
        },
        "E1",
      );
      /** @type {any} */
      (globalThis).reportRenderer.bindSnippets(document.body);
    });
    assert.equal(await page.locator(".snippet-view script").count(), 0);
    await page
      .getByRole("button", {
        name: "Fewer lines",
      })
      .click();
    await page
      .getByRole("button", {
        name: "Fewer lines",
      })
      .click();
    assert.equal(await page.locator("tr[data-n]:not([hidden])").count(), 1);
    assert.match(await page.locator(".snippet-range").innerText(), /Line 3/);
    await page
      .getByRole("button", {
        name: "More lines",
      })
      .click();
    assert.equal(await page.locator("tr[data-n]:not([hidden])").count(), 3);
  });
});
