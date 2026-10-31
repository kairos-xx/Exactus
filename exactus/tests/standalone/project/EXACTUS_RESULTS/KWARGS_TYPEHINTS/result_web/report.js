/**
 * Keys the report reads from exactus payloads. Listing them (instead of an
 * index signature) keeps dot access valid for both TypeScript and ESLint and
 * turns key typos into type errors.
 * @typedef {"outcome" | "actual" | "details" | "assertion_id" | "actions" | "discovery_diagnostics" | "artifact_root" | "flows" | "flow_id" | "action_id" | "height" | "theme" | "action_records" | "response" | "script" | "event_id" | "assertions" | "screenshots" | "screenshot_artifact_ids" | "evidence" | "artifact_id" | "type" | "error" | "started_ms" | "finished_ms" | "action" | "added" | "added_count" | "analyzer" | "available" | "argument" | "arguments" | "artifacts" | "bare_imports" | "blocked_requests" | "blocking" | "bytes" | "callee" | "candidates" | "captures" | "category" | "change" | "clipped" | "code" | "column" | "command" | "subsections" | "metrics" | "metric" | "current" | "previous" | "categories" | "comparison" | "context" | "comparison_key" | "coverage" | "cpu_count" | "current_total" | "cwd" | "delta" | "detail" | "diagnostic_findings" | "diagnostics" | "display_name" | "duration_human" | "duration_seconds" | "end" | "environment" | "error_count" | "events" | "excerpt" | "exclude" | "exit_code" | "extension" | "failed_tests" | "file" | "files" | "findings" | "findings_total" | "fingerprint" | "finished_at" | "gate" | "generated_at" | "hit" | "hunks" | "id" | "include" | "invocation" | "javascript" | "kind" | "label" | "language" | "line" | "lines" | "markdown" | "message" | "method" | "missing_lines" | "n" | "name" | "node" | "num_statements" | "os" | "parts" | "passed" | "path" | "percent_covered" | "pipeline_id" | "pipeline_run_id" | "position" | "previous_generated_at" | "previous_run_id" | "previous_status" | "previous_total" | "project_href" | "project_root" | "python" | "reason" | "report" | "report_web" | "report_web_href" | "resolved" | "resolved_count" | "resume" | "root" | "rule" | "run" | "run_id" | "schema" | "scope" | "server_diagnostics" | "severity" | "severity_levels" | "signature" | "skipped" | "snippets" | "source" | "source_label" | "start" | "started_at" | "started_at_human" | "finished_at_human" | "at_human" | "run_at" | "run_at_human" | "generated_at_human" | "states" | "status" | "suggestion" | "summary" | "target" | "targets_analyzed" | "targets_eligible" | "test" | "test_execution" | "text" | "title" | "tool" | "tools" | "total_states" | "totals" | "truncated" | "type_hints" | "unchanged_count" | "uncovered_lines" | "url" | "value" | "variables" | "variants" | "version" | "view" | "view_columns" | "view_order" | "width"} JsonKey
 */
/**
 * @typedef {Partial<Record<JsonKey, unknown>>} Json
 */
/**
 * @typedef {object} Finding
 * @property {string} severity Lowercase severity (error, warning, info).
 * @property {string} rule Rule or check identifier.
 * @property {string} file Project-relative location group.
 * @property {number} line One-based line, or 0 when unknown.
 * @property {number} column One-based column, or 0 when unknown.
 * @property {string} message What is wrong.
 * @property {string} detail Suggested fix or extra context.
 * @property {string} source Tool that produced the finding.
 * @property {string} change Run-over-run state (added or unchanged).
 * @property {string} category Browser or server issue type.
 */
/**
 * @typedef {object} ClickStep
 * @property {string} label Accessible label of the clicked element.
 * @property {string} tag Element tag name.
 * @property {string} selector CSS selector of the clicked element.
 * @property {string} url Page URL where the click happened.
 * @property {number} x Absolute document x of the element centre.
 * @property {number} y Absolute document y of the element centre.
 */
/**
 * @typedef {object} ScreenState
 * @property {string} id State identifier.
 * @property {string | null} parent_id Parent state identifier.
 * @property {ClickStep[]} path Clicks replaying the state.
 * @property {string} url URL shown by the state.
 * @property {string} screenshot Screenshot filename.
 * @property {number | null} similarity_to_parent Similarity to the parent.
 */
/**
 * Render an exactus report bundle's JSON into an interactive page.
 */
class ExactusReport {
  /** @type {Record<string, unknown>} Verified report-relative local destinations. */
  static localLinks = {};
  /**
   * @param {unknown} value Value to escape for HTML.
   * @returns {string} Escaped text.
   */
  static escape = value =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  /**
   * Resolve a Markdown link target to a safe href. Only ``http``/``https``
   * URLs, fragment links, absolute paths and relative paths are allowed;
   * any other scheme (``javascript:``, ``data:``, ``file:`` ...) yields
   * ``null`` so the caller renders the link as plain text.
   * @param {string} href Raw Markdown link target.
   * @returns {string | null} href rebased for the ``result_web`` directory,
   *     or ``null`` when the target must not become a link.
   */
  static linkHref = href => {
    if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(href)) {
      return /^https?:\/\//i.test(href) ? href : null;
    }
    return /^[#/]/.test(href) ? href : `../${href}`;
  };
  /**
   * @param {string} text Markdown prose without code spans or links.
   * @returns {string} Escaped HTML with bold and italic markup applied.
   */
  static emphasis = text =>
    ExactusReport.escape(text)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>");
  /**
   * @param {string} label Link text.
   * @param {string} href Raw link target.
   * @returns {string} Anchor markup, or escaped text for unsafe targets.
   */
  static link = (label, href) => {
    const target = ExactusReport.linkHref(href);
    return target === null
      ? ExactusReport.escape(`[${label}](${href})`)
      : `<a href="${ExactusReport.escape(target)}">${label.startsWith("`") && label.endsWith("`") ? `<code>${ExactusReport.escape(label.slice(1, -1))}</code>` : ExactusReport.emphasis(label)}</a>`;
  };
  /**
   * @param {string} text Markdown prose without code spans.
   * @returns {string} HTML with links and emphasis applied.
   */
  static prose = (text) => {
    const parts = text.split(/\[([^\]]+)\]\(([^)]+)\)/);
    return parts
      .map((part, index) => {
        if (index % 3 === 0) return ExactusReport.emphasis(part);
        if (index % 3 === 1)
          return ExactusReport.link(part, parts[index + 1] ?? "");
        return "";
      })
      .join("");
  };
  /**
   * Code spans are rendered as escaped text only; emphasis and links
   * apply to the prose between them.
   * @param {string} value Markdown inline text.
   * @returns {string} HTML with inline markup applied.
   */
  static inline = (value) =>
    String(value ?? "")
      .split(/(\[[^\]]+\]\([^)]+\)|`[^`]+`)/)
      .map(part => {
        const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
        if (link?.[1] && link[2]) return ExactusReport.link(link[1], link[2]);
        if (part.startsWith("`") && part.endsWith("`")) {
          const label = part.slice(1, -1);
          const href = ExactusReport.localLinks[label];
          const code = `<code>${ExactusReport.escape(label)}</code>`;
          return typeof href === "string"
            ? `<a href="${ExactusReport.escape(ExactusReport.linkHref(href))}">${code}</a>`
            : code;
        }
        return ExactusReport.prose(part);
      })
      .join("");
  /**
   * @param {string} value Heading text.
   * @returns {string} Anchor slug.
   */
  static slug = value =>
    value
      .toLowerCase()
      .replace(/<[^>]*>/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "") || "section";
  /**
   * @param {string[]} lines Markdown table rows.
   * @returns {string} Rendered table HTML.
   */
  static table = lines => {
    /**
     * Split one Markdown table row into trimmed cell texts.
     * @param {string} line Table row source.
     * @returns {string[]} Trimmed cells.
     */
    const splitCells = line =>
      line
        .trim()
        .replace(/^\||\|$/g, "")
        .split("|")
        .map(cell => cell.trim());
    const rows = lines.map(splitCells);
    const head = rows[0] ?? [];
    const body = rows.slice(2);
    return `<div class="table-wrap"><table class="ds-table"><thead><tr>${head
      .map((cell) => `<th scope="col">${ExactusReport.inline(cell)}</th>`)
      .join("")}</tr></thead><tbody>${body
      .map((row) => {
        const cells = row.map(
          (cell) => `<td>${ExactusReport.inline(cell)}</td>`,
        );
        return `<tr>${cells.join("")}</tr>`;
      })
      .join("")}</tbody></table></div>`;
  };
  /**
   * @param {string} source Markdown source text.
   * @returns {string} Rendered HTML.
   */
  static markdown = source => {
    const lines = source.replaceAll("\r\n", "\n").split("\n");
    const html = /** @type {string[]} */ ([]);
    let index = 0;
    /** Opening fence of the open code block, or "" outside one. */
    let fence = "";
    /** @type {string[]} Escaped lines of the open code block. */
    let code = [];
    /** Emit the open code block as one escaped ``pre`` element. */
    const closeCode = () => {
      html.push(`<pre><code>${code.join("\n")}</code></pre>`);
      fence = "";
      code = [];
    };
    /** @type {"ul" | "ol" | null} */
    let list = null;
    /** Close the open Markdown list, if any. */
    const closeList = () => {
      if (list) html.push(`</${list}>`);

      list = null;
    };
    while (index < lines.length) {
      const line = lines[index] ?? "";
      const marker = /^ {0,3}(`{3,}|~{3,})/.exec(line)?.[1] ?? "";
      if (
        fence
          ? marker.startsWith(fence) && !line.trim().slice(marker.length)
          : marker
      ) {
        closeList();
        if (fence) closeCode();
        else fence = marker;
        index += 1;
        continue;
      }
      if (fence) {
        code.push(ExactusReport.escape(line));
        index += 1;
        continue;
      }
      if (line === "> [!WARNING]" || line === "> [!CAUTION]") {
        closeList();
        const variant = line.includes("CAUTION")
          ? "ds-badge-danger"
          : "ds-badge-warn";
        /** @type {string[]} */
        const content = [];
        index += 1;
        while ((lines[index] ?? "").startsWith(">")) {
          content.push((lines[index] ?? "").replace(/^> ?/, ""));
          index += 1;
        }
        html.push(
          `<p class="report-alert"><span class="ds-badge ${variant}">${ExactusReport.inline(content.join(" "))}</span></p>`,
        );
        continue;
      }
      const heading = /^(#{1,6})\s+(.*)$/.exec(line);
      if (heading) {
        closeList();
        const [, marks = "", text = ""] = heading;
        const level = Math.min(marks.length + 1, 6);
        html.push(
          `<h${level} id="md-${ExactusReport.slug(text)}">${ExactusReport.inline(text)}</h${level}>`,
        );
        index += 1;
        continue;
      }
      if (
        line.includes("|") &&
        index + 1 < lines.length &&
        /^\s*\|?\s*:?-+/.test(lines[index + 1] ?? "")
      ) {
        closeList();
        const table = [line, lines[index + 1] ?? ""];
        index += 2;
        while (index < lines.length) {
          const row = lines[index] ?? "";
          if (!row.includes("|") || !row.trim()) break;
          table.push(row);
          index += 1;
        }
        html.push(ExactusReport.table(table));
        continue;
      }
      const anchor = /^<a id="([a-zA-Z][a-zA-Z0-9_-]*)"><\/a>$/.exec(line);
      if (anchor) {
        closeList();
        html.push(`<a id="${anchor[1]}"></a>`);
        index += 1;
        continue;
      }
      const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
      const ordered = /^\s*\d+\.\s+(.*)$/.exec(line);
      const item = bullet ?? ordered;
      if (item) {
        const wanted = bullet ? "ul" : "ol";
        if (list !== wanted) {
          closeList();
          list = wanted;
          html.push(`<${wanted}>`);
        }
        html.push(`<li>${ExactusReport.inline(item[1] ?? "")}</li>`);
        index += 1;
        continue;
      }
      closeList();
      if (line.trim()) html.push(`<p>${ExactusReport.inline(line)}</p>`);
      index += 1;
    }
    closeList();
    if (fence) closeCode();
    return html.join("\n");
  };
  /**
   * @param {unknown} value Possibly an object.
   * @returns {Json} The object, or an empty one.
   */
  static object = value =>
    value && typeof value === "object" && !Array.isArray(value)
      ? /** @type {Json} */ (value)
      : {};
  /**
   * @param {unknown} value Possibly an array.
   * @returns {unknown[]} The array, or an empty one.
   */
  static array = value => Array.isArray(value) ? value : [];
  /**
   * @param {number} count Item count.
   * @param {string} noun Singular noun.
   * @returns {string} Pluralized phrase such as "1 file" or "3 files".
   */
  static plural = (count, noun) =>
    `${count.toLocaleString()} ${noun}${count === 1 ? "" : "s"}`;
  /**
   * @param {unknown} value Percentage value.
   * @returns {string} Formatted percentage.
   */
  static percent = value =>
    `${Number(value ?? 0).toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
  /**
   * @param {string} key Snake-case key.
   * @returns {string} Sentence-case label.
   */
  static humanize = key => {
    const text = key.replaceAll("_", " ").replaceAll("-", " ").trim();
    return text.charAt(0).toUpperCase() + text.slice(1);
  };
  /**
   * @param {string} path Absolute or relative path.
   * @param {string} root Project root.
   * @returns {string} Path relative to the project root.
   */
  static relative = (path, root) =>
    root && path.startsWith(`${root}/`) ? path.slice(root.length + 1) : path;
  /**
   * @param {string} url Absolute URL.
   * @returns {string} Path, query and hash of the URL.
   */
  static urlPath = url => {
    try {
      const parsed = new URL(url);
      return `${parsed.pathname}${parsed.search}${parsed.hash}`;
    } catch {
      return url;
    }
  };
  /**
   * @param {unknown} status Tool status such as PASS or FAIL.
   * @returns {string} Status badge HTML with a text label.
   */
  static statusBadge = status => {
    const value = String(status ?? "").toUpperCase();
    /** @type {Record<string, [string, string]>} */
    const variants = {
      PASS: ["ds-badge-safe", "Passed"],
      DONE: ["ds-badge-safe", "Passed"],
      FAIL: ["ds-badge-danger", "Failed"],
      ERROR: ["ds-badge-danger", "Error"],
      INVALID_RESULT: ["ds-badge-danger", "Invalid result"],
      INTERRUPT: ["ds-badge-warn", "Interrupted"],
      TIMEOUT: ["ds-badge-warn", "Timed out"],
      RUNNING: ["ds-badge-verified", "Running"],
    };
    const [variant, label] = variants[value] ?? [
      "ds-badge-unknown",
      value || "Unknown",
    ];
    return `<span class="ds-badge ${variant}">${ExactusReport.escape(label)}</span>`;
  };
  /**
   * @param {string} severity Finding severity.
   * @returns {string} Severity badge HTML with a text label.
   */
  static severityBadge = severity => {
    /** @type {Record<string, [string, string]>} */
    const variants = {
      error: ["ds-badge-danger", "Error"],
      warning: ["ds-badge-warn", "Warning"],
      info: ["ds-badge-verified", "Info"],
      information: ["ds-badge-verified", "Info"],
      log: ["ds-badge-verified", "Log"],
    };
    const [variant, label] = variants[severity] ?? [
      "ds-badge-unknown",
      ExactusReport.humanize(severity || "note"),
    ];
    return `<span class="ds-badge ${variant}">${ExactusReport.escape(label)}</span>`;
  };
  /**
   * @param {[string, string][]} items Label/value pairs.
   * @returns {string} Metric list items.
   */
  static metrics = items =>
    items
      .map(
        ([label, value]) =>
          `<div class="metric"><dt class="metric-label">${ExactusReport.escape(label)}</dt><dd class="metric-value">${ExactusReport.escape(value)}</dd></div>`,
      )
      .join("");
  /**
   * @param {Json} item Raw finding from any exactus tool.
   * @returns {string} Human-readable message.
   */
  static describe = item => {
    if (typeof item.message === "string") return item.message;
    if (typeof item.reason === "string") return item.reason;
    if (item.callee && item.argument)
      return `Pass \`${String(item.argument)}\` to \`${String(item.callee)}()\` by keyword`;
    return Object.entries(item)
      .filter(([, value]) => typeof value !== "object")
      .map(([key, value]) => `${key}: ${String(value)}`)
      .join(", ");
  };
  /**
   * @param {Json} data Report payload.
   * @returns {Finding[]} Findings normalized across tools.
   */
  static findings = data => {
    const root = String(data.project_root ?? data.root ?? "");
    /** @type {[JsonKey, string][]} */
    const lists = [
      ["findings", "finding"],
      ["type_hints", "missing-type-hint"],
      ["bare_imports", "bare-import"],
    ];
    return lists.flatMap(([key, fallback]) =>
      ExactusReport.array(data[key]).map(raw => {
        const item = ExactusReport.object(raw);
        const file = ExactusReport.relative(
          String(item.file ?? item.path ?? ""),
          root,
        );
        return {
          severity: String(item.severity ?? "error").toLowerCase(),
          rule: String(
            item.rule ??
              item.code ??
              (item.callee ? "positional-argument" : fallback),
          ),
          file: file || "Project",
          line: Number(item.line ?? 0),
          column: Number(item.column ?? 0),
          message: ExactusReport.describe(item),
          detail: String(item.suggestion ?? item.signature ?? ""),
          source: String(item.tool ?? data.analyzer ?? ""),
          change: String(item.change ?? ""),
          category: String(item.category ?? ""),
        };
      }),
    );
  };
  /**
   * @param {Json} data Report or mapped view payload.
   * @returns {string} Previous-run comparison markup.
   */
  static comparisonSection = data => {
    const comparison = ExactusReport.object(data.comparison);
    if (!Object.keys(comparison).length) return "";
    if (comparison.available !== true)
      return "<p>No previous report exists; this run establishes the baseline.</p>";
    const delta = Number(comparison.delta ?? 0);
    /**
     * Format a recorded count without inventing absent baseline data.
     * @param {string} key Comparison count key.
     * @returns {string} Count or unavailable label.
     */
    const count = key => {
      const value = ExactusReport.record(comparison)[key];
      return value == null ? "N/A" : Number(value).toLocaleString();
    };
    const metrics = ExactusReport.metrics([
      ["Current", Number(comparison.current_total ?? 0).toLocaleString()],
      ["Previous", Number(comparison.previous_total ?? 0).toLocaleString()],
      ["Net delta", `${delta > 0 ? "+" : ""}${delta.toLocaleString()}`],
      ["Added", count("added_count")],
      ["Resolved", count("resolved_count")],
      ["Unchanged", count("unchanged_count")],
    ]);
    /**
     * @param {unknown} items Comparison finding entries.
     * @param {string} state List title.
     * @returns {string} Comparison list markup.
     */
    /**
     * Render one finding-change group.
     * @param {unknown} items Raw finding list.
     * @param {string} state Group heading.
     * @returns {string} Finding-change list markup.
     */
    const list = (items, state) => {
      const rows = ExactusReport.array(items).map(ExactusReport.object);
      if (!rows.length) return "";
      return `<div><h3 class="ds-subsection-title">${ExactusReport.escape(state)}</h3><ul class="comparison-list">${rows
        .map(
          (item) =>
            `<li><span class="ds-badge ds-badge-outline">${ExactusReport.escape(String(item.rule ?? item.code ?? "finding"))}</span><span>${ExactusReport.inline(ExactusReport.describe(item))}</span><span class="ds-muted">${ExactusReport.escape(String(item.path ?? item.file ?? "Project"))}</span></li>`,
        )
        .join("")}</ul></div>`;
    };
    const tables = [
      [
        "Category findings",
        "categories",
        ["category", "title", "current", "previous", "delta"],
      ],
    ]
      .map(([label, key, columns]) => {
        const rows = ExactusReport.array(
          ExactusReport.record(comparison)[String(key)],
        );
        if (!rows.length || !Array.isArray(columns)) return "";
        const records = rows.map(row =>
          Object.fromEntries(
            columns.map(column => [
              column,
              ExactusReport.record(row)[String(column)],
            ]),
          ),
        );
        return `<h3 class="ds-subsection-title">${ExactusReport.escape(String(label))}</h3>${ExactusReport.recordTable(String(label), records, null, columns)}`;
      })
      .join("");
    return `<div class="comparison-summary"><dl class="metrics">${metrics}</dl><div class="comparison-details">${list(comparison.added, "Added findings")}${list(comparison.resolved, "Resolved findings")}</div>${tables}</div>`;
  };
  /**
   * @param {Finding[]} rows Normalized findings.
   * @returns {string} Findings section markup.
   */
  static findingsSection = rows => {
    if (!rows.length) return "";
    const severities = [...new Set(rows.map(row => row.severity))];
    const chips = [
      `<button class="ds-chip" type="button" data-severity="" aria-pressed="true">All ${rows.length}</button>`,
      ...severities.map(
        severity =>
          `<button class="ds-chip" type="button" data-severity="${ExactusReport.escape(severity)}" aria-pressed="false">${ExactusReport.escape(ExactusReport.humanize(severity))} ${rows.filter((row) => row.severity === severity).length}</button>`,
      ),
    ];
    return `<section class="section" aria-labelledby="findings-title"><h2 class="ds-section-title" id="findings-title">Findings</h2><div class="toolbar"><div class="search"><label class="ds-label" for="finding-search">Filter by file, rule or message</label><input class="ds-input" id="finding-search" type="search" autocomplete="off"></div><div class="filters" role="group" aria-label="Severity">${chips.join("")}</div></div><p class="ds-supporting result-count" role="status" id="finding-count"></p><div id="finding-groups"></div></section>`;
  };
  /**
   * @param {Finding} row Normalized finding.
   * @returns {string} Finding list item markup.
   */
  static findingItem = row => {
    const location = row.line
      ? `Line ${row.line}${row.column ? `:${row.column}` : ""}`
      : "";
    const detail = row.detail
      ? `<pre class="code finding-detail">${ExactusReport.escape(row.detail)}</pre>`
      : "";
    const issue =
      row.category === "server"
        ? '<span class="ds-badge ds-badge-danger">Server error</span>'
        : ["console", "pageerror"].includes(row.category)
          ? '<span class="ds-badge ds-badge-warn">Console error</span>'
          : "";
    const change =
      row.change === "added"
        ? '<span class="ds-badge ds-badge-warning">Added</span>'
        : "";
    return `<li class="finding"><div class="finding-meta">${issue}${ExactusReport.severityBadge(row.severity)}${change}<span class="location">${location}</span></div><div class="finding-meta"><span class="ds-badge ds-badge-outline">${ExactusReport.escape(row.rule)}</span><span class="ds-muted">${ExactusReport.escape(row.source)}</span></div><p class="finding-message">${ExactusReport.inline(row.message)}</p>${detail}</li>`;
  };
  /**
   * Link a project-relative path when it looks like a file.
   * @param {string} file Project-relative path or group label.
   * @param {string} base Relative URL of the project root.
   * @param {string} label Visible file label.
   * @returns {string} Link or plain label markup.
   */
  static fileLink = (file, base, label = file) => {
    const verified = ExactusReport.localLinks[file];
    const href =
      typeof verified === "string"
        ? ExactusReport.linkHref(verified)
        : base &&
            /[/.]/.test(file) &&
            !/^(?:\/|[a-zA-Z][a-zA-Z0-9+.-]*:)/.test(file)
          ? `${base}/${file.split("/").map(encodeURIComponent).join("/")}`
          : null;
    return href
      ? `<a class="file-path" href="${ExactusReport.escape(href)}">${ExactusReport.escape(label)}</a>`
      : `<span class="file-path">${ExactusReport.escape(label)}</span>`;
  };
  /**
   * @param {Finding[]} rows Findings to group.
   * @param {string} base Relative URL of the project root.
   * @returns {string} Grouped-by-file markup.
   */
  static findingGroups = (rows, base) => {
    /** @type {Map<string, Finding[]>} */
    const groups = new Map();
    for (const row of rows)
      groups.set(row.file, [...(groups.get(row.file) ?? []), row]);
    const ordered = [...groups.entries()].sort(
      ([left, a], [right, b]) =>
        b.filter(row => row.severity === "error").length -
          a.filter(row => row.severity === "error").length ||
        left.localeCompare(right),
    );
    const open = ordered.length <= 12 ? " open" : "";
    return ordered
      .map(([file, items]) => {
        const sorted = [...items].sort((a, b) => a.line - b.line);
        return `<details class="file-group"${open}><summary class="file-summary">${ExactusReport.fileLink(file, base)}<span class="ds-badge">${ExactusReport.plural(items.length, "finding")}</span></summary><ul class="finding-list">${sorted.map(ExactusReport.findingItem).join("")}</ul></details>`;
      })
      .join("");
  };
  /**
   * @param {Finding[]} rows All findings rendered by the section.
   * @param {string} base Relative URL of the project root.
   */
  static bindFindings = (rows, base) => {
    const search = document.querySelector("#finding-search");
    const groups = document.querySelector("#finding-groups");
    const count = document.querySelector("#finding-count");
    const chips = [...document.querySelectorAll("[data-severity]")];
    if (!(search instanceof HTMLInputElement) || !groups || !count) return;
    const filter = {
      severity: "",
    };
    /** Re-render the findings that match the search and severity filter. */
    const update = () => {
      const query = search.value.trim().toLowerCase();
      const shown = rows.filter(
        row =>
          (!filter.severity || row.severity === filter.severity) &&
          (!query ||
            `${row.file} ${row.rule} ${row.message} ${row.source}`
              .toLowerCase()
              .includes(query)),
      );
      const files = new Set(shown.map(row => row.file)).size;
      count.textContent = shown.length
        ? `Showing ${ExactusReport.plural(shown.length, "finding")} in ${ExactusReport.plural(files, "file")}.`
        : "No findings match. Clear the filter to see all of them.";
      groups.innerHTML = ExactusReport.findingGroups(shown, base);
    };
    for (const chip of chips)
      chip.addEventListener("click", () => {
        filter.severity = chip.getAttribute("data-severity") ?? "";
        for (const other of chips)
          other.setAttribute("aria-pressed", String(other === chip));
        update();
      });
    search.addEventListener("input", update);
    update();
  };
  /**
   * @param {Json} data Report payload.
   * @param {Finding[]} rows Normalized findings.
   * @returns {[string, string][]} Metric pairs for findings tools.
   */
  static findingMetrics = (data, rows) => {
    const summary = ExactusReport.object(data.summary);
    /** @type {[string, string][]} */
    const pairs = [
      ["Findings", rows.length.toLocaleString()],
      [
        "Files affected",
        new Set(rows.map(row => row.file)).size.toLocaleString(),
      ],
    ];
    for (const [key, value] of Object.entries(summary)) {
      if (typeof value === "number" && pairs.length < 6 && key !== "findings")
        pairs.push([ExactusReport.humanize(key), value.toLocaleString()]);
    }
    return pairs;
  };
  /**
   * @param {number[]} lines Line numbers.
   * @returns {string} Compressed ranges such as "3-5, 9".
   */
  static ranges = lines => {
    const sorted = [...lines].sort((a, b) => a - b);
    /** @type {string[]} */
    const parts = [];
    let start = sorted[0];
    let previous = start;
    for (const line of [...sorted.slice(1), Number.NaN]) {
      if (line !== (previous ?? 0) + 1) {
        if (start !== undefined)
          parts.push(
            start === previous
              ? `${start}`
              : previous === start + 1
                ? `${start}, ${previous}`
                : `${start}-${previous}`,
          );
        start = line;
      }
      previous = line;
    }
    return parts.join(", ");
  };
  /**
   * @param {string} label Accessible name of the bar.
   * @param {number} value Percentage between 0 and 100.
   * @returns {string} Progress bar markup.
   */
  static bar = (label, value) =>
    `<div class="ds-progress" role="progressbar" aria-label="${ExactusReport.escape(label)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(value)}"><div class="ds-progress-bar" data-percent="${Math.round(value)}"></div></div>`;
  /**
   * Ordered token patterns keyed by highlight language. Each pattern
   * exposes named groups ``comment``, ``string``, ``keyword``,
   * ``builtin``, ``number`` and ``decorator``; whichever group matched
   * becomes the token's span class.
   * @type {Record<string, RegExp>}
   */
  static TOKEN_RULES = {
    python: new RegExp(
      [
        "(?<comment>#[^\\n]*)",
        "(?<string>[fFbBrRuU]{0,3}\"\"\"[\\s\\S]*?\"\"\"|[fFbBrRuU]{0,3}'''[\\s\\S]*?'''|[fFbBrRuU]{0,3}\"(?:[^\"\\\\\\n]|\\\\.)*\"|[fFbBrRuU]{0,3}'(?:[^'\\\\\\n]|\\\\.)*')",
        "(?<keyword>\\b(?:False|None|True|and|as|assert|async|await|break|case|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|match|nonlocal|not|or|pass|raise|return|try|while|with|yield)\\b)",
        "(?<builtin>\\b(?:abs|all|any|bool|callable|classmethod|dataclass|dict|dir|enumerate|filter|float|format|getattr|hasattr|hash|id|input|int|isinstance|iter|len|list|map|max|min|next|object|open|print|property|range|repr|self|set|setattr|sorted|staticmethod|str|sum|super|tuple|type|vars|zip|BaseException|Exception|KeyError|RuntimeError|TypeError|ValueError)\\b)",
        "(?<number>\\b0[xX][\\da-fA-F_]+\\b|\\b0[bB][01_]+\\b|\\b0[oO][0-7_]+\\b|\\b\\d[\\d_]*(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b)",
        "(?<decorator>@[\\w.]+)",
      ].join("|"),
      "g",
    ),
    javascript: new RegExp(
      [
        "(?<comment>//[^\\n]*|/\\*[\\s\\S]*?\\*/)",
        "(?<string>`(?:[^`\\\\]|\\\\.)*`|\"(?:[^\"\\\\\\n]|\\\\.)*\"|'(?:[^'\\\\\\n]|\\\\.)*')",
        "(?<keyword>\\b(?:async|await|break|case|catch|class|const|continue|debugger|default|delete|do|else|export|extends|finally|for|from|function|get|if|import|in|instanceof|let|new|null|of|return|set|static|super|switch|this|throw|true|try|typeof|undefined|var|void|while|with|yield)\\b)",
        "(?<builtin>\\b(?:Array|Boolean|JSON|Map|Math|Number|Object|Promise|Set|String|console|document|fetch|window)\\b)",
        "(?<number>\\b0[xX][\\da-fA-F_]+\\b|\\b0[bB][01_]+\\b|\\b0[oO][0-7_]+\\b|\\b\\d[\\d_]*(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b)",
      ].join("|"),
      "g",
    ),
  };
  /**
   * Highlight language used for a fence language the rules lack.
   * @type {Record<string, string>}
   */
  static TOKEN_ALIASES = {
    typescript: "javascript",
  };
  /**
   * Syntax-highlight one source text, returning per-line HTML so spans
   * never straddle row boundaries (multiline strings/comments reopen
   * their span on the next line).
   * @param {string} source Raw source text of one hunk or run.
   * @param {string} language Highlight language (python, javascript).
   * @returns {string[]} Escaped, tokenized HTML for each source line.
   */
  static codeLines = (source, language) => {
    const rule =
      ExactusReport.TOKEN_RULES[
        ExactusReport.TOKEN_ALIASES[language] ?? language
      ];
    /** @type {string[][]} */
    const rows = [[]];
    /**
     * Append one chunk to the current row, splitting on newlines.
     * @param {string} cls Token span class, or empty for plain text.
     * @param {string} chunk Raw text possibly containing newlines.
     */
    const push = (cls, chunk) => {
      for (const [index, part] of chunk.split("\n").entries()) {
        if (index > 0) rows.push([]);
        if (part)
          rows
            .at(-1)
            ?.push(
              cls
                ? `<span class="tok-${cls}">${ExactusReport.escape(part)}</span>`
                : ExactusReport.escape(part),
            );
      }
    };
    if (rule) {
      rule.lastIndex = 0;
      let cursor = 0;
      for (const match of source.matchAll(rule)) {
        const index = match.index ?? 0;
        push("", source.slice(cursor, index));
        const kind = Object.keys(match.groups ?? {}).find(
          key => match.groups?.[key] !== undefined,
        );
        push(kind ?? "", match[0]);
        cursor = index + match[0].length;
      }
      push("", source.slice(cursor));
    } else push("", source);
    return rows.map(pieces => pieces.join(""));
  };
  /**
   * @param {Json} line Snippet line entry (coverage hunk or excerpt).
   * @returns {string} Row class of a marked line: ``code-miss`` for an
   *   uncovered line, ``code-target`` for a finding line, else empty.
   */
  static snippetMark = line => {
    if (line.hit === true) return "code-miss";
    return line.target === true ? "code-target" : "";
  };
  /**
   * Trim a hunk's lines to those within ``context`` of a marked
   * (uncovered or finding) line, returning contiguous visible runs.
   * @param {Json[]} lines Hunk line entries.
   * @param {number} context Visible context around uncovered lines.
   * @returns {Json[][]} Contiguous line runs to render.
   */
  static snippetRuns = (lines, context) => {
    const hits = lines
      .filter(line => ExactusReport.snippetMark(line) !== "")
      .map(line => Number(line.n ?? 0));
    /** @type {Json[][]} */
    const runs = [];
    for (const line of lines) {
      const number = Number(line.n ?? 0);
      const near =
        line.hit === true ||
        hits.some(hit => Math.abs(hit - number) <= context);
      if (!near) continue;
      const last = runs.at(-1);
      if (last && Number(last.at(-1)?.n ?? 0) + 1 === number) last.push(line);
      else runs.push([line]);
    }
    return runs;
  };
  /**
   * Render one source hunk as a line-numbered, highlighted table.
   * @param {Json[][]} runs Contiguous line runs.
   * @param {string} language Highlight language.
   * @returns {string} Snippet table markup.
   */
  static snippetTable = (runs, language) => {
    /** @type {string[]} */
    const rows = [];
    for (const [index, run] of runs.entries()) {
      if (index > 0)
        rows.push(
          '<tr class="code-gap" aria-hidden="true"><td class="code-gutter"></td><td class="code-line">⋮</td></tr>',
        );
      const source = run.map(line => String(line.text ?? "")).join("\n");
      const highlighted = ExactusReport.codeLines(source, language);
      for (const [offset, line] of run.entries()) {
        const number = Number(line.n ?? 0);
        const marked = ExactusReport.snippetMark(line);
        const note = marked
          ? `<span class="visually-hidden"> (${marked === "code-miss" ? "uncovered" : "finding line"})</span>`
          : "";
        rows.push(
          `<tr data-n="${number}"${marked ? ` class="${marked}"` : ""}><td class="code-gutter">${number}${note}</td><td class="code-line"><code>${highlighted[offset] || "&nbsp;"}</code></td></tr>`,
        );
      }
    }
    return `<div class="snippet-scroll"><table class="code-snippet"><tbody>${rows.join("")}</tbody></table></div>`;
  };
  /**
   * @param {Json} snippets Snippet manifest embedded by the analyzer.
   * @param {number} context Visible context lines.
   * @returns {string} All rendered hunk blocks for one file.
   */
  static snippetBlocks = (snippets, context) => {
    const embedded = Number(snippets.context ?? 0);
    const shown = Math.min(context, embedded);
    const language = String(snippets.language ?? "");
    const blocks = ExactusReport.array(snippets.hunks)
      .map(ExactusReport.object)
      .map(hunk =>
        ExactusReport.snippetTable(
          ExactusReport.snippetRuns(
            ExactusReport.array(hunk.lines).map(ExactusReport.object),
            shown,
          ),
          language,
        ),
      );
    const flag = snippets.truncated
      ? '<p class="ds-supporting">Snippet list truncated; the file has more uncovered regions.</p>'
      : "";
    return `${blocks.join("")}${flag}`;
  };
  /**
   * @param {Json} data Coverage payload.
   * @returns {{path: string, lane: string, missing: number, percent: number, snippets: Json}[]} Files with embedded snippets.
   */
  static uncoveredFiles = data => {
    /** @type {{path: string, lane: string, missing: number, percent: number, snippets: Json}[]} */
    const entries = [];
    const report = ExactusReport.object(data.coverage);
    for (const [path, raw] of Object.entries(
      ExactusReport.object(report.files),
    )) {
      const entry = ExactusReport.object(raw);
      const snippets = ExactusReport.object(entry.snippets);
      if (!ExactusReport.array(snippets.hunks).length) continue;
      entries.push({
        path,
        lane: "python",
        missing: ExactusReport.array(entry.missing_lines).length,
        percent: Number(
          ExactusReport.object(entry.summary).percent_covered ?? 0,
        ),
        snippets,
      });
    }
    for (const raw of ExactusReport.array(
      ExactusReport.object(data.javascript).files,
    )) {
      const entry = ExactusReport.object(raw);
      const snippets = ExactusReport.object(entry.snippets);
      if (!ExactusReport.array(snippets.hunks).length) continue;
      entries.push({
        path: String(entry.path ?? ""),
        lane: "javascript",
        missing:
          ExactusReport.array(entry.uncovered_lines).length ||
          Number(entry.missing_lines ?? 0),
        percent: Number(entry.percent_covered ?? 0),
        snippets,
      });
    }
    return entries.sort(
      (a, b) => b.missing - a.missing || a.path.localeCompare(b.path),
    );
  };
  /**
   * @param {string} path Project-relative source path.
   * @returns {string} Directory grouping label for the path.
   */
  static directoryOf = path =>
    path.includes("/")
      ? path.split("/").slice(0, -1).join("/")
      : "project root";
  /**
   * Render the grouped uncovered-code groups for the active filters.
   * @param {{path: string, lane: string, missing: number, percent: number, snippets: Json}[]} entries Normalized files.
   * @param {number} context Visible context lines.
   * @param {string} base Relative URL of the project root.
   * @returns {string} Directory sections markup.
   */
  static uncoveredGroups = (entries, context, base) => {
    /** @type {Map<string, typeof entries>} */
    const directories = new Map();
    for (const entry of entries) {
      const directory = ExactusReport.directoryOf(entry.path);
      directories.set(directory, [
        ...(directories.get(directory) ?? []),
        entry,
      ]);
    }
    return [...directories.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([directory, files]) => {
        const total = files.reduce((sum, file) => sum + file.missing, 0);
        const groups = files
          .map(
            file =>
              `<details class="file-group code-file" id="cov-${ExactusReport.slug(file.path)}" data-lane="${ExactusReport.escape(file.lane)}"><summary class="file-summary">${ExactusReport.fileLink(file.path, base)}<span class="ds-badge ds-badge-outline">${ExactusReport.escape(file.lane)}</span><span class="ds-badge ds-badge-danger">${ExactusReport.plural(file.missing, "uncovered line")}</span><span class="ds-badge">${ExactusReport.percent(file.percent)} covered</span></summary><div class="snippet-blocks">${ExactusReport.snippetBlocks(file.snippets, context)}</div></details>`,
          )
          .join("");
        return `<section class="snippet-dir" aria-labelledby="dir-${ExactusReport.slug(directory)}"><h3 class="ds-card-title snippet-dir-title" id="dir-${ExactusReport.slug(directory)}">${ExactusReport.escape(directory)}</h3><p class="ds-supporting">${ExactusReport.plural(files.length, "file")}, ${ExactusReport.plural(total, "uncovered line")}</p>${groups}</section>`;
      })
      .join("");
  };
  /**
   * Section chrome (toolbar + index) for uncovered code.
   * @param {{path: string, lane: string, missing: number, percent: number, snippets: Json}[]} entries Files with snippets.
   * @param {number} maxContext Largest embedded context depth.
   * @returns {string} Section markup.
   */
  static uncoveredSection = (entries, maxContext) => {
    const index = entries
      .map(
        entry =>
          `<a class="ds-chip index-chip" href="#cov-${ExactusReport.slug(entry.path)}">${ExactusReport.escape(entry.path)}<span class="chip-count">${entry.missing}</span></a>`,
      )
      .join("");
    return `<section class="section" aria-labelledby="uncovered-title"><h2 class="ds-section-title" id="uncovered-title">Uncovered code</h2><div class="toolbar"><div class="search"><label class="ds-label" for="uncovered-search">Filter by path</label><input class="ds-input" id="uncovered-search" type="search" autocomplete="off"></div><div class="filters" role="group" aria-label="Lane"><button class="ds-chip" type="button" data-lane="" aria-pressed="true">All</button><button class="ds-chip" type="button" data-lane="python" aria-pressed="false">Python</button><button class="ds-chip" type="button" data-lane="javascript" aria-pressed="false">JavaScript</button></div><div class="context-stepper"><label class="ds-label" for="context-lines">Context lines</label><input id="context-lines" type="range" min="0" max="${maxContext}" step="1" value="${maxContext}"><span class="ds-supporting" id="context-value">${maxContext}</span></div><div class="filters" role="group" aria-label="Expand"><button class="ds-chip" type="button" id="expand-all">Expand all</button><button class="ds-chip" type="button" id="collapse-all">Collapse all</button></div></div><nav class="code-index" aria-label="Uncovered files">${index}</nav><p class="ds-supporting result-count" role="status" id="uncovered-count"></p><div id="uncovered-groups"></div></section>`;
  };
  /**
   * Wire filtering, context stepper and index navigation for the
   * uncovered-code section.
   * @param {Json} data Coverage payload.
   */
  static bindCoverage = data => {
    const search = document.querySelector("#uncovered-search");
    const groups = document.querySelector("#uncovered-groups");
    const count = document.querySelector("#uncovered-count");
    const range = document.querySelector("#context-lines");
    const rangeValue = document.querySelector("#context-value");
    const expand = document.querySelector("#expand-all");
    const collapse = document.querySelector("#collapse-all");
    const chips = [...document.querySelectorAll("[data-lane]")];
    if (
      !(search instanceof HTMLInputElement) ||
      !(range instanceof HTMLInputElement) ||
      !groups ||
      !count ||
      !rangeValue
    )
      return;
    const base = String(data.project_href ?? "");
    const entries = ExactusReport.uncoveredFiles(data);
    const state = {
      lane: "",
      query: "",
      context: Number(range.value),
    };
    /** Re-render visible file groups from the current state. */
    const update = () => {
      const shown = entries.filter(
        entry =>
          (!state.lane || entry.lane === state.lane) &&
          (!state.query || entry.path.toLowerCase().includes(state.query)),
      );
      count.textContent = shown.length
        ? `Showing ${ExactusReport.plural(shown.length, "file")} with uncovered code.`
        : "No files match. Clear the filter to see all of them.";
      const open = new Set(
        [...groups.querySelectorAll("details[open]")].map(item => item.id),
      );
      groups.innerHTML = ExactusReport.uncoveredGroups(
        shown,
        state.context,
        base,
      );
      for (const item of groups.querySelectorAll("details")) {
        if (open.has(item.id)) item.open = true;
      }
    };
    search.addEventListener("input", () => {
      state.query = search.value.trim().toLowerCase();
      update();
    });
    for (const chip of chips)
      chip.addEventListener("click", () => {
        state.lane = chip.getAttribute("data-lane") ?? "";
        for (const other of chips)
          other.setAttribute("aria-pressed", String(other === chip));
        update();
      });
    range.addEventListener("input", () => {
      state.context = Number(range.value);
      rangeValue.textContent = range.value;
      update();
    });
    expand?.addEventListener("click", () => {
      for (const item of groups.querySelectorAll("details")) {
        if (item instanceof HTMLDetailsElement) item.open = true;
      }
    });
    collapse?.addEventListener("click", () => {
      for (const item of groups.querySelectorAll("details")) {
        if (item instanceof HTMLDetailsElement) item.open = false;
      }
    });
    document
      .querySelector(".code-index")
      ?.addEventListener("click", event => {
        const link =
          event.target instanceof Element
            ? event.target.closest("a[href^='#cov-']")
            : null;
        const target = link
          ? document.querySelector(link.getAttribute("href") ?? "")
          : null;
        if (target instanceof HTMLDetailsElement) target.open = true;
      });
    update();
  };
  /**
   * @param {Json} data Coverage payload.
   * @returns {{ metrics: [string, string][], summary: string, view: string }} Coverage view.
   */
  static coverage = data => {
    const base = String(data.project_href ?? "");
    const report = ExactusReport.object(data.coverage);
    const totals = ExactusReport.object(report.totals);
    const files = ExactusReport.object(report.files);
    const js = ExactusReport.object(data.javascript);
    const execution = ExactusReport.object(data.test_execution);
    const failed = ExactusReport.array(execution.failed_tests);
    const pyPercent = Number(totals.percent_covered ?? 0);
    const jsPercent = Number(js.percent_covered ?? 0);
    const pyRows = Object.entries(files)
      .map(([path, raw]) => {
        const entry = ExactusReport.object(raw);
        const summary = ExactusReport.object(entry.summary);
        const missing = ExactusReport.array(entry.missing_lines).map(Number);
        return {
          path,
          summary,
          missing,
        };
      })
      .sort(
        (a, b) =>
          Number(a.summary.percent_covered ?? 0) -
          Number(b.summary.percent_covered ?? 0),
      );
    const pyTable = `<div class="table-wrap"><table class="ds-table"><caption class="ds-supporting">Python files, least covered first</caption><thead><tr><th scope="col">File</th><th scope="col" class="cell-number">Statements</th><th scope="col" class="cell-number">Missing</th><th scope="col" class="bar-cell">Coverage</th><th scope="col" class="cell-number">%</th><th scope="col">Missing lines</th></tr></thead><tbody>${pyRows
      .map(
        (row) =>
          `<tr><td>${ExactusReport.fileLink(row.path, base)}</td><td class="cell-number">${Number(row.summary.num_statements ?? 0)}</td><td class="cell-number">${Number(row.summary.missing_lines ?? 0)}</td><td class="bar-cell">${ExactusReport.bar(row.path, Number(row.summary.percent_covered ?? 0))}</td><td class="cell-number">${ExactusReport.percent(row.summary.percent_covered)}</td><td>${ExactusReport.escape(ExactusReport.ranges(row.missing)) || "None"}</td></tr>`,
      )
      .join("")}</tbody></table></div>`;
    const jsRows = ExactusReport.array(js.files).map(ExactusReport.object);
    const jsTable = jsRows.length
      ? `<div class="table-wrap"><table class="ds-table"><caption class="ds-supporting">JavaScript files</caption><thead><tr><th scope="col">File</th><th scope="col" class="cell-number">Lines</th><th scope="col" class="cell-number">Missing</th><th scope="col" class="bar-cell">Coverage</th><th scope="col" class="cell-number">%</th></tr></thead><tbody>${jsRows
          .map(
            (row) =>
              `<tr><td>${ExactusReport.fileLink(String(row.path), base)}</td><td class="cell-number">${Number(row.num_statements ?? 0)}</td><td class="cell-number">${Number(row.missing_lines ?? 0)}</td><td class="bar-cell">${ExactusReport.bar(String(row.path), Number(row.percent_covered ?? 0))}</td><td class="cell-number">${ExactusReport.percent(row.percent_covered)}</td></tr>`,
          )
          .join("")}</tbody></table></div>`
      : `<p class="ds-supporting">No JavaScript tests importing node:test were found.</p>`;
    const failures = failed.length
      ? `<section class="section" aria-labelledby="failed-title"><h2 class="ds-section-title" id="failed-title">Failed tests</h2><ul class="finding-list">${failed
          .map((raw) => {
            const item = ExactusReport.object(raw);
            return `<li class="finding"><div class="finding-meta">${ExactusReport.severityBadge("error")}</div><p class="finding-message"><code>${ExactusReport.escape(item.test)}</code> ${ExactusReport.escape(item.detail ?? "")}</p></li>`;
          })
          .join("")}</ul></section>`
      : "";
    const uncovered = ExactusReport.uncoveredFiles(data);
    const maxContext = Math.max(
      0,
      ...uncovered.map(entry => Number(entry.snippets.context ?? 0)),
    );
    const uncoveredSection = uncovered.length
      ? ExactusReport.uncoveredSection(uncovered, maxContext)
      : "";
    return {
      metrics: [
        ["Python coverage", ExactusReport.percent(pyPercent)],
        [
          "JavaScript coverage",
          jsRows.length ? ExactusReport.percent(jsPercent) : "None",
        ],
        ["Statements", Number(totals.num_statements ?? 0).toLocaleString()],
        ["Missing lines", Number(totals.missing_lines ?? 0).toLocaleString()],
        ["Failed tests", failed.length.toLocaleString()],
      ],
      summary: `${ExactusReport.percent(pyPercent)} of Python statements and ${jsRows.length ? ExactusReport.percent(jsPercent) : "no"} JavaScript lines are covered by tests.`,
      view: `${failures}${uncoveredSection}<section class="section" aria-labelledby="python-title"><h2 class="ds-section-title" id="python-title">Python</h2>${pyTable}</section><section class="section" aria-labelledby="js-title"><h2 class="ds-section-title" id="js-title">JavaScript</h2>${jsTable}</section>`,
    };
  };
  /**
   * @param {Json} data Unified payload.
   * @returns {{ metrics: [string, string][], summary: string, view: string }} Pipeline view.
   */
  static unified = data => {
    const tools = Object.entries(ExactusReport.object(data.tools)).map(
      ([name, raw]) => ({
        name,
        entry: ExactusReport.object(raw),
      }),
    );
    const failed = tools.filter(tool => !tool.entry.passed);
    const rows = tools
      .map(({ name, entry }) => {
        const legacy = String(entry.report_web ?? "")
          .split("/")
          .slice(-3)
          .join("/");
        const web = entry.report_web_href
          ? String(entry.report_web_href)
          : legacy && `../../${legacy}`;
        const link = web
          ? `<a class="tool-link" href="${ExactusReport.escape(web)}">${ExactusReport.escape(name)}</a>`
          : ExactusReport.escape(name);
        return `<tr><td>${link}</td><td>${ExactusReport.statusBadge(entry.status)}</td><td class="cell-number">${Number(entry.duration_seconds ?? 0).toFixed(1)} s</td><td>${ExactusReport.escape(entry.resume ?? "")}</td></tr>`;
      })
      .join("");
    return {
      metrics: [
        ["Tools", tools.length.toLocaleString()],
        ["Passed", (tools.length - failed.length).toLocaleString()],
        ["Failed", failed.length.toLocaleString()],
      ],
      summary: failed.length
        ? `Fix ${failed.map((tool) => tool.name).join(", ")} first; each link opens that tool's report.`
        : "Every tool passed.",
      view: `<section class="section" aria-labelledby="tools-title"><h2 class="ds-section-title" id="tools-title">Tools</h2><div class="table-wrap"><table class="ds-table"><thead><tr><th scope="col">Tool</th><th scope="col">Result</th><th scope="col" class="cell-number">Duration</th><th scope="col">Outcome</th></tr></thead><tbody>${rows}</tbody></table></div></section>`,
    };
  };
  /**
   * @param {Json} data Frontend workflow evidence.
   * @returns {{ metrics: [string, string][], summary: string, view: string }} Frontend execution view.
   */
  static frontend = data => {
    const runs = ExactusReport.array(data.flows).map(ExactusReport.object);
    const evidence = ExactusReport.array(data.evidence).map(
      ExactusReport.object,
    );
    const screenshots = evidence.filter(item => item.type === "screenshot");
    const steps = runs.flatMap(run =>
      ExactusReport.array(run.action_records),
    );
    const artifactRoot = String(data.artifact_root || "../ARTIFACTS/RUN");
    const view = runs
      .map(run => {
        const records = ExactusReport.array(run.action_records).map(
          ExactusReport.object,
        );
        return `<section class="section"><h2>${ExactusReport.escape(run.name || run.flow_id)} <small>${ExactusReport.escape(run.status)}</small></h2><p>${run.action_id ? `Action ${ExactusReport.escape(run.action_id)} · ` : ""}Flow ${ExactusReport.escape(run.flow_id)} · Run ${ExactusReport.escape(run.run_id)}${run.width ? ` · ${ExactusReport.escape(run.width)} × ${ExactusReport.escape(run.height)} · ${ExactusReport.escape(run.theme || "")}` : ""}</p>${run.error ? `<p>${ExactusReport.escape(run.error)}</p>` : ""}${records
          .map((record) => {
            const images = screenshots.filter((item) =>
              ExactusReport.array(record.screenshot_artifact_ids).includes(
                item.artifact_id,
              ),
            );
            return `<details class="flow-step"${record.status === "failed" ? " open" : ""}><summary>${ExactusReport.escape(record.label || record.event_id)} · ${ExactusReport.escape(record.kind)} · ${ExactusReport.escape(record.status)}</summary><p>${ExactusReport.escape(record.started_ms)}–${ExactusReport.escape(record.finished_ms)} ms · ${ExactusReport.escape(record.flow_id)}/${ExactusReport.escape(record.event_id)}</p>${record.script ? `<h3>JavaScript call</h3><pre>${ExactusReport.escape(record.script)}</pre><h3>Response</h3><pre>${ExactusReport.escape(JSON.stringify(record.response, null, 2))}</pre>` : ""}${
              ExactusReport.array(record.assertions).length
                ? `<h3>Evaluations and assertions</h3>${ExactusReport.array(
                    record.assertions,
                  )
                    .map(ExactusReport.object)
                    .map(
                      check =>
                        `<p><strong>${ExactusReport.escape(check.outcome)}</strong> · ${ExactusReport.escape(check.assertion_id)}<br>${ExactusReport.escape(check.details)}${check.actual !== null && check.actual !== undefined ? `<br>Actual: ${ExactusReport.escape(check.actual)}` : ""}</p>`,
                    )
                    .join("")}`
                : ""
            }${record.error ? `<p>${ExactusReport.escape(record.error)}</p>` : ""}${images
              .map((image) => {
                const filename =
                  String(image.path || "")
                    .split(/[\\/]/)
                    .pop() || "";
                const path = String(image.path || "");
                const href =
                  path && !path.startsWith("/")
                    ? `../${path.split("/").map(encodeURIComponent).join("/")}`
                    : `${String(run.artifact_root || artifactRoot)}/screenshots/${encodeURIComponent(filename)}`;
                return `<a href="${ExactusReport.escape(href)}"><img loading="lazy" alt="Screenshot for ${ExactusReport.escape(record.label || record.event_id)}" src="${ExactusReport.escape(href)}" style="max-width:100%"></a>`;
              })
              .join("")}</details>`;
          })
          .join(
            "",
          )}${ExactusReport.array(run.diagnostics).length ? `<details><summary>Browser diagnostics (${ExactusReport.array(run.diagnostics).length})</summary><pre>${ExactusReport.escape(JSON.stringify(run.diagnostics, null, 2))}</pre></details>` : ""}</section>`;
      })
      .join("");
    return {
      metrics: [
        ["Workflow runs", String(runs.length)],
        ["Actions", String(steps.length)],
        ["Screenshots", String(screenshots.length)],
        ["Findings", String(ExactusReport.array(data.findings).length)],
      ],
      summary:
        "Execution evidence grouped by workflow run and action. Screenshots follow each flow's capture policy.",
      view: `${
        data.actions
          ? `<section class="section"><h2>Tool sequence</h2>${ExactusReport.array(
              data.actions,
            )
              .map(ExactusReport.object)
              .map(
                (action) =>
                  `<p><strong>${ExactusReport.escape(action.id)}</strong> · ${ExactusReport.escape(action.tool)} · ${ExactusReport.escape(action.status)}</p>`,
              )
              .join("")}</section>`
          : ""
      }${data.discovery_diagnostics ? `<section class="section"><h2>Discovery diagnostics</h2><pre>${ExactusReport.escape(JSON.stringify(data.discovery_diagnostics, null, 2))}</pre></section>` : ""}${view}${ExactusReport.array(data.server_diagnostics).length ? `<section class="section"><h2>Server diagnostics</h2><pre>${ExactusReport.escape(JSON.stringify(data.server_diagnostics, null, 2))}</pre></section>` : ""}`,
    };
  };
  /**
   * @param {Json} data Frontend workflow evidence.
   * @returns {{ metrics: [string, string][], summary: string, view: string }} Frontend execution view.
   */
  static BASE_VIEW_KEYS = [
    "artifacts",
    "blocking",
    "comparison",
    "environment",
    "extension",
    "findings",
    "gate",
    "invocation",
    "run",
    "scope",
    "severity_levels",
    "source_label",
    "summary",
    "tool",
  ];
  /**
   * Normalized finding keys shown in a finding's header; every other key
   * is listed under the finding's details.
   * @type {string[]}
   */
  static FINDING_KEYS = [
    "blocking",
    "column",
    "excerpt",
    "id",
    "line",
    "message",
    "path",
    "rule",
    "severity",
    "source",
    "title",
  ];
  /**
   * @param {unknown} value Possibly an object.
   * @returns {Record<string, unknown>} The object as a generic record.
   */
  static record = (value) =>
    value && typeof value === "object" && !Array.isArray(value)
      ? /** @type {Record<string, unknown>} */ (value)
      : {};
  /**
   * @param {unknown} value View-model value.
   * @returns {boolean} Whether the value is absent or blank.
   */
  static blank = (value) =>
    value === null || value === undefined || value === "";
  /**
   * @param {unknown} value One view-model value.
   * @param {boolean} linkLocal Whether local files become links.
   * @returns {string} Display HTML for the value.
   */
  static cell = (value, linkLocal = true) => {
    if (ExactusReport.blank(value)) {
      return '<span class="ds-muted">N/A</span>';
    }
    if (typeof value === "boolean") {
      return value ? "Yes" : "No";
    }
    if (typeof value === "number") {
      return ExactusReport.escape(value.toLocaleString());
    }
    if (Array.isArray(value)) {
      return value
        .map(
          (item) =>
            `<code>${ExactusReport.escape(typeof item === "object" ? JSON.stringify(item) : item)}</code>`,
        )
        .join(" ");
    }
    if (typeof value === "object") {
      return `<code>${ExactusReport.escape(JSON.stringify(value))}</code>`;
    }
    const href = ExactusReport.localLinks[String(value)];
    return linkLocal && typeof href === "string"
      ? ExactusReport.link(String(value), href)
      : ExactusReport.escape(value);
  };
  /**
   * @param {unknown} value One view-model value.
   * @returns {string} Plain text used to sort a table column.
   */
  static sortText = (value) => {
    if (ExactusReport.blank(value)) {
      return "";
    }
    return typeof value === "object" ? JSON.stringify(value) : String(value);
  };
  /**
   * @param {string} label Accessible table name.
   * @param {[string, string][]} pairs Label and value-HTML pairs.
   * @returns {string} Two-column key-value table markup.
   */
  static keyValues = (label, pairs) =>
    `<div class="table-wrap"><table class="ds-table kv-table" aria-label="${ExactusReport.escape(label)}"><tbody>${pairs
      .map(
        ([key, value]) =>
          `<tr><th scope="row">${ExactusReport.escape(key)}</th><td>${value}</td></tr>`,
      )
      .join("")}</tbody></table></div>`;
  /**
   * Identifying columns lead a table, in this order; the web data is
   * serialized with sorted keys, so the source order is otherwise lost.
   * @type {string[]}
   */
  static LEADING_COLUMNS = [
    "id",
    "name",
    "callee",
    "module",
    "rule",
    "code",
    "target",
    "path",
    "line",
    "directory",
    "language",
    "title",
    "category",
    "reason",
    "metric",
    "value",
  ];
  /**
   * Order table columns: identifying columns first, then the mapping's
   * column order, then any remaining keys.
   * @param {string[]} columns Row keys.
   * @param {string[]} order Column order recorded with the view model.
   * @returns {string[]} Ordered columns.
   */
  static orderColumns = (columns, order) => {
    /**
     * Rank identifying columns before the configured and remaining columns.
     * @param {string} column Row key.
     * @returns {number} Sort rank of the column.
     */
    const rank = (column) => {
      const leading = ExactusReport.LEADING_COLUMNS.indexOf(column);
      if (leading >= 0) return leading;
      const mapped = order.indexOf(column);
      return (
        ExactusReport.LEADING_COLUMNS.length +
        (mapped >= 0 ? mapped : order.length)
      );
    };
    return [...columns].sort(
      (left, right) =>
        rank(left) - rank(right) ||
        columns.indexOf(left) - columns.indexOf(right),
    );
  };
  /**
   * @param {Record<string, unknown>} row Table row.
   * @returns {string} Id of the finding a row reports, or nothing.
   */
  static rowFinding = (row) => {
    const { finding } = row;
    return typeof finding === "string" ? finding : "";
  };
  /**
   * Render a list of objects as a table whose column headings sort it.
   * A row naming a ``finding`` links its first cell to that finding and
   * is clickable as a whole; a row naming a sub-``report`` directory
   * (relative to the tool output) links its first cell to that report's
   * web page.
   * @param {string} label Accessible table name.
   * @param {unknown[]} rows Row objects; their keys become the columns.
   * @param {((row: Record<string, unknown>) => string) | null} linkOf
   *   Optional href for the selected link column of each row.
   * @param {unknown} order Column order recorded with the view model.
   * @param {string | null} linkColumn Named link column; null uses the first.
   * @returns {string} Sortable table markup.
   */
  static recordTable = (label, rows, linkOf, order, linkColumn = null) => {
    const records = rows.map(ExactusReport.record);
    const columns = ExactusReport.orderColumns(
      [...new Set(records.flatMap((row) => Object.keys(row)))],
      ExactusReport.array(order).map(String),
    );
    const numeric = columns.map((column) =>
      records.every(
        (row) =>
          ExactusReport.blank(row[column]) || typeof row[column] === "number",
      ),
    );
    const head = columns
      .map(
        (column, index) =>
          `<th scope="col"${numeric[index] ? ' class="cell-number"' : ""}><button class="sort-button" type="button" data-sort-column="${index}" data-numeric="${numeric[index] === true}">${ExactusReport.escape(ExactusReport.humanize(column))}</button></th>`,
      )
      .join("");
    const prefix = `row-${ExactusReport.slug(label)}`;
    const body = records
      .map((row, position) => {
        const finding = ExactusReport.rowFinding(row);
        const cells = columns.map((column, index) => {
          const value = row[column];
          const linked =
            linkColumn === null ? index === 0 : column === linkColumn;
          let href = linked && linkOf ? linkOf(row) : "";
          const { report } = row;
          if (index === 0 && !href && typeof report === "string") {
            href = `../${report}/result_web/index.html`;
          }
          if (index === 0 && finding) {
            href = `#${ExactusReport.findingAnchor(finding)}`;
          }
          const content = href
            ? `<a href="${ExactusReport.escape(href)}"${finding ? ` data-finding-link="${ExactusReport.escape(finding)}"` : ""}>${ExactusReport.cell(value, false)}</a>`
            : ExactusReport.cell(value, linkColumn === null || linked);
          return `<td${numeric[index] ? ' class="cell-number"' : ""} data-sort="${ExactusReport.escape(ExactusReport.sortText(value))}">${content}</td>`;
        });
        const attributes = finding
          ? ` class="row-link" id="${prefix}-${position + 1}" tabindex="-1" data-finding-row="${ExactusReport.escape(finding)}" data-return-label="${ExactusReport.escape(label)}"`
          : "";
        return `<tr${attributes}>${cells.join("")}</tr>`;
      })
      .join("");
    return `<div class="table-wrap" role="region" aria-label="${ExactusReport.escape(label)}" tabindex="0"><table class="ds-table record-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
  };
  /**
   * Sort a record table by one column; a repeated press reverses it.
   * @param {Element} button Pressed column-heading button.
   */
  static sortBy = (button) => {
    const header = button.closest("th");
    const table = button.closest("table");
    const body = table?.querySelector("tbody");
    if (!header || !table || !body) return;
    const column = Number(button.getAttribute("data-sort-column") ?? 0);
    const numeric = button.getAttribute("data-numeric") === "true";
    const ascending = header.getAttribute("aria-sort") !== "ascending";
    for (const other of table.querySelectorAll("th[aria-sort]")) {
      other.removeAttribute("aria-sort");
    }
    header.setAttribute("aria-sort", ascending ? "ascending" : "descending");
    /**
     * Read the selected cell's normalized sort text.
     * @param {Element} row Table row.
     * @returns {string} Sort text of the row's cell in the column.
     */
    const key = (row) => row.children[column]?.getAttribute("data-sort") ?? "";
    /**
     * Convert the selected cell to a number, sorting blanks first.
     * @param {Element} row Table row.
     * @returns {number} Numeric sort value; blanks sort first.
     */
    const amount = (row) =>
      key(row) === "" ? Number.NEGATIVE_INFINITY : Number(key(row));
    const rows = [...body.querySelectorAll("tr")].sort((left, right) => {
      const order = numeric
        ? Number(amount(left) > amount(right)) -
          Number(amount(left) < amount(right))
        : key(left).localeCompare(key(right), undefined, {
            numeric: true,
            sensitivity: "base",
          });
      return ascending ? order : -order;
    });
    body.append(...rows);
  };
  /**
   * @param {string} title Section heading.
   * @returns {string} Fragment identifier of the section.
   */
  static sectionId = (title) => `view-${ExactusReport.slug(title)}`;
  /**
   * @param {string} id Finding identifier.
   * @returns {string} Fragment identifier of the finding.
   */
  static findingAnchor = (id) => `finding-${ExactusReport.slug(id)}`;
  /**
   * @param {string} what Block the tool did not report.
   * @returns {string} Not-available note markup.
   */
  static notReported = (what) =>
    `<p class="ds-supporting">N/A — the tool reported no ${ExactusReport.escape(what)}.</p>`;
  /**
   * Render a composed gate's part gates (``gate.parts``: name to
   * ``{status, reason, label?, position?}``) as one card each, ordered by
   * ``position`` then name. A card links to the findings whose
   * ``source`` is the part's label.
   * @param {Json} model View model.
   * @returns {string} Part-gate cards markup, or nothing without parts.
   */
  static gateParts = (model) => {
    const parts = Object.entries(
      ExactusReport.record(ExactusReport.object(model.gate).parts),
    )
      .map(
        /**
         * @param {[string, unknown]} entry Part name and gate.
         * @returns {[string, Json]} Part name and gate object.
         */
        ([name, part]) => [name, ExactusReport.object(part)],
      )
      .sort(
        ([left, first], [right, second]) =>
          Number(first.position ?? 0) - Number(second.position ?? 0) ||
          left.localeCompare(right),
      );
    if (!parts.length) return "";
    const findings = ExactusReport.array(model.findings).map(
      ExactusReport.object,
    );
    const sources = new Set(findings.map((item) => String(item.source ?? "")));
    const cards = parts.map(([name, part]) => {
      const status = String(part.status ?? "ERROR").toUpperCase();
      const label = String(part.label ?? ExactusReport.humanize(name));
      const count = findings.filter(
        (item) => String(item.source ?? "") === label,
      ).length;
      const target =
        sources.size > 1
          ? `findings-group-${ExactusReport.slug(label)}`
          : ExactusReport.sectionId("Findings");
      const link = count
        ? `<a class="gate-part-link" href="#${target}">See ${ExactusReport.escape(ExactusReport.plural(count, "finding"))}</a>`
        : "";
      return `<li class="gate-part" data-gate="${ExactusReport.escape(status.toLowerCase())}"><div class="gate-part-head"><h3 class="gate-part-name">${ExactusReport.escape(label)}</h3>${ExactusReport.statusBadge(status)}</div><p class="gate-part-reason">${ExactusReport.escape(part.reason ?? "")}</p>${link}</li>`;
    });
    return `<ul class="gate-parts" aria-label="Gate parts">${cards.join("")}</ul>`;
  };
  /**
   * @param {Json} model View model.
   * @returns {string} Gate banner markup.
   */
  static gateSection = (model) => {
    const gate = ExactusReport.object(model.gate);
    const status = String(gate.status ?? "ERROR").toUpperCase();
    const blocking = ExactusReport.array(model.blocking).map(
      ExactusReport.object,
    );
    let detail = '<p class="ds-supporting">No blocking findings.</p>';
    if (model.findings === null || model.findings === undefined) {
      detail = ExactusReport.notReported("findings list");
    } else if (blocking.length) {
      detail = `<p class="label-title">Blocking findings</p><ul class="gate-list">${blocking
        .map(
          item =>
            `<li><a href="#${ExactusReport.findingAnchor(String(item.id ?? ""))}">${ExactusReport.escape(item.id)}</a> ${ExactusReport.inline(String(item.title ?? ""))}</li>`,
        )
        .join("")}</ul>`;
    }
    return `<div class="gate" data-gate="${ExactusReport.escape(status.toLowerCase())}"><p class="gate-title">${ExactusReport.statusBadge(status)}<span class="gate-reason">${ExactusReport.escape(gate.reason ?? "")}</span></p>${ExactusReport.gateParts(model)}${detail}</div>`;
  };
  /**
   * @param {Json} summary Summary block.
   * @returns {string} One-sentence summary of what the run checked.
   */
  static summarySentence = (summary) => {
    const total = Number(summary.findings_total ?? 0);
    return `${ExactusReport.plural(total, "finding")} across ${Number(summary.targets_analyzed ?? 0).toLocaleString()} of ${Number(summary.targets_eligible ?? 0).toLocaleString()} eligible targets.`;
  };
  /**
   * @param {unknown} values Glob patterns.
   * @param {string} empty Text shown when there are none.
   * @returns {string} Pattern list markup.
   */
  static globList = (values, empty) => {
    const items = ExactusReport.array(values);
    return items.length
      ? `<ul class="glob-list">${items.map(item => `<li><code>${ExactusReport.escape(item)}</code></li>`).join("")}</ul>`
      : `<p class="ds-supporting">${ExactusReport.escape(empty)}</p>`;
  };
  /**
   * @param {Json} model View model.
   * @returns {string} "What was checked" markup: totals, severities, scope.
   */
  static checkedSection = (model) => {
    const summary = ExactusReport.object(model.summary);
    const severity = ExactusReport.record(summary.severity);
    const levels = ExactusReport.array(model.severity_levels).map(String);
    const counts = Object.keys(summary).length
      ? `<p class="summary-lead">${ExactusReport.escape(ExactusReport.summarySentence(summary))}</p><ul class="severity-list" aria-label="Findings by severity">${levels
          .map(level => {
            const count = Number(severity[level] ?? 0);
            return `<li class="severity-item${count ? "" : " severity-none"}">${ExactusReport.severityBadge(level)}<span class="severity-count">${count.toLocaleString()}</span></li>`;
          })
          .join("")}</ul>`
      : ExactusReport.notReported("summary");
    const scope = ExactusReport.object(model.scope);
    const skipped = ExactusReport.array(scope.skipped);
    const scopeBody = Object.keys(scope).length
      ? `<div class="scope-grid"><div class="scope-part"><h4 class="label-title">Included</h4>${ExactusReport.globList(scope.include, "No include rules.")}</div><div class="scope-part"><h4 class="label-title">Excluded</h4>${ExactusReport.globList(scope.exclude, "No exclude rules.")}</div></div><h4 class="label-title">Skipped targets</h4>${
          skipped.length
            ? ExactusReport.recordTable("Skipped targets", skipped, null, [])
            : '<p class="ds-supporting">No skipped targets.</p>'
        }`
      : ExactusReport.notReported("scope");
    return `${counts}<h3 class="subsection-title">Scope</h3>${scopeBody}`;
  };
  /**
   * @param {Json} finding View-model finding.
   * @param {string} base Relative URL of the project root.
   * @returns {string} Location link (path and line) markup.
   */
  static findingLocation = (finding, base) => {
    const path = String(finding.path ?? "");
    const line = Number(finding.line ?? 0);
    const column = Number(finding.column ?? 0);
    const label = `${path}${line ? `:${line}` : ""}${line && column ? `:${column}` : ""}`;
    if (!path) return "";
    return ExactusReport.fileLink(path, base, label);
  };
  /**
   * Render a finding's excerpt as a snippet viewer: numbered lines, the
   * finding line highlighted, and buttons that narrow or widen the
   * visible context within the captured lines.
   * @param {unknown} raw Excerpt stored on the finding.
   * @param {string} label Finding id naming the viewer's controls.
   * @returns {string} Viewer markup, or nothing without captured lines.
   */
  static snippetViewer = (raw, label) => {
    const excerpt = ExactusReport.object(raw);
    const lines = ExactusReport.array(excerpt.lines).map(ExactusReport.object);
    if (!lines.length) return "";
    const target = Number(excerpt.line ?? 0);
    const widest = Math.max(
      ...lines.map((line) => Math.abs(Number(line.n ?? 0) - target)),
    );
    const language = String(excerpt.language ?? "text");
    const controls =
      widest > 0
        ? `<div class="snippet-controls" role="group" aria-label="Context lines around ${ExactusReport.escape(label)}"><button class="ds-chip" type="button" data-snippet-step="-1">Fewer lines</button><button class="ds-chip" type="button" data-snippet-step="1">More lines</button></div>`
        : "";
    const clipped =
      excerpt.clipped === true
        ? '<p class="ds-supporting snippet-note">Long lines are shortened (…).</p>'
        : "";
    return `<figure class="snippet-view" data-snippet-target="${target}" data-snippet-widest="${widest}" data-snippet-context="${widest}"><figcaption class="snippet-head"><output class="snippet-range" aria-live="polite"></output><span class="ds-badge ds-badge-outline">${ExactusReport.escape(language)}</span>${controls}</figcaption>${ExactusReport.snippetTable([lines], language)}${clipped}</figure>`;
  };
  /**
   * Show the rows of one snippet viewer within ``context`` lines of its
   * finding line, and refresh its range text and button states.
   * @param {Element} viewer Snippet viewer figure.
   * @param {number} context Requested context lines.
   */
  static snippetContext = (viewer, context) => {
    const target = Number(viewer.getAttribute("data-snippet-target"));
    const widest = Number(viewer.getAttribute("data-snippet-widest"));
    const shown = Math.min(Math.max(context, 0), widest);
    viewer.setAttribute("data-snippet-context", String(shown));
    /** @type {number[]} */
    const visible = [];
    for (const row of viewer.querySelectorAll("tr[data-n]")) {
      const number = Number(row.getAttribute("data-n"));
      const near = Math.abs(number - target) <= shown;
      row.toggleAttribute("hidden", !near);
      if (near) visible.push(number);
    }
    const range = viewer.querySelector(".snippet-range");
    if (range) {
      const first = Math.min(...visible);
      const last = Math.max(...visible);
      range.textContent =
        first === last
          ? `Line ${first}`
          : `Lines ${first}–${last} · ${ExactusReport.plural(shown, "line")} of context`;
    }
    for (const button of viewer.querySelectorAll("[data-snippet-step]")) {
      const step = Number(button.getAttribute("data-snippet-step"));
      const limit = step < 0 ? shown === 0 : shown === widest;
      button.setAttribute("aria-disabled", String(limit));
    }
  };
  /**
   * Initialize every snippet viewer under ``root`` and wire its context
   * buttons (one delegated listener; disabled steps are ignored so focus
   * stays on the button).
   * @param {Element} root Rendered report view.
   */
  static bindSnippets = (root) => {
    for (const viewer of root.querySelectorAll(".snippet-view")) {
      ExactusReport.snippetContext(
        viewer,
        Number(viewer.getAttribute("data-snippet-context")),
      );
    }
    root.addEventListener("click", (event) => {
      const button =
        event.target instanceof Element
          ? event.target.closest("[data-snippet-step]")
          : null;
      const viewer = button?.closest(".snippet-view");
      if (!button || !viewer || button.getAttribute("aria-disabled") === "true")
        return;
      ExactusReport.snippetContext(
        viewer,
        Number(viewer.getAttribute("data-snippet-context")) +
          Number(button.getAttribute("data-snippet-step")),
      );
    });
  };
  /**
   * @param {Json} finding View-model finding.
   * @returns {string} Details disclosure for the tool-specific fields.
   */
  static findingExtras = (finding) => {
    const duplicates = [
      String(finding.path ?? ""),
      String(finding.rule ?? ""),
      String(finding.source ?? ""),
    ];
    const extras = Object.entries(finding).filter(
      ([key, value]) =>
        !ExactusReport.FINDING_KEYS.includes(key) &&
        !ExactusReport.blank(value) &&
        !(typeof value === "string" && duplicates.includes(value)),
    );
    if (!extras.length) return "";
    const rows = extras
      .map(([key, value]) => {
        const text = typeof value === "string" ? value : "";
        const shown = text.includes("\n")
          ? `<pre class="code"><code>${ExactusReport.escape(text)}</code></pre>`
          : ExactusReport.cell(value);
        return `<dt>${ExactusReport.escape(ExactusReport.humanize(key))}</dt><dd>${shown}</dd>`;
      })
      .join("");
    return `<details class="finding-extra"><summary class="finding-extra-summary">Details</summary><dl class="context">${rows}</dl></details>`;
  };
  /**
   * @param {Json} finding View-model finding.
   * @param {string} base Relative URL of the project root.
   * @param {number} level Heading level of the finding title.
   * @returns {string} Finding list item markup.
   */
  static viewFinding = (finding, base, level) => {
    const id = String(finding.id ?? "");
    const severity = String(finding.severity ?? "").toLowerCase();
    const rule = String(finding.rule ?? "");
    const source = String(finding.source ?? "");
    const title = String(finding.title ?? "");
    const message = String(finding.message ?? "");
    const text = [id, title, finding.path, rule, source, message]
      .map((part) => String(part ?? ""))
      .join(" ")
      .toLowerCase();
    const blocking =
      finding.blocking === true
        ? '<span class="ds-badge ds-badge-outline">Blocking</span>'
        : "";
    const origin = source
      ? `<span class="ds-badge ds-badge-outline finding-source">${ExactusReport.escape(source)}</span>`
      : "";
    const lines = message.trim().split("\n");
    const rest = lines[0]?.trim() === title.trim() ? lines.slice(1) : lines;
    const body = rest.join("").trim()
      ? `<p class="finding-message">${rest
          .map(line => ExactusReport.inline(line.trim()))
          .filter(Boolean)
          .join("<br>")}</p>`
      : "";
    return `<li class="vfinding" id="${ExactusReport.findingAnchor(id)}" data-severity="${ExactusReport.escape(severity)}" data-rule="${ExactusReport.escape(rule)}" data-source="${ExactusReport.escape(source)}" data-text="${ExactusReport.escape(text)}"><div class="finding-head"><span class="finding-id">${ExactusReport.escape(id)}</span>${ExactusReport.severityBadge(severity)}<span class="ds-badge ds-badge-outline">${ExactusReport.escape(rule)}</span>${origin}${blocking}</div><h${level} class="finding-title">${ExactusReport.inline(title)}</h${level}><p class="location">${ExactusReport.findingLocation(finding, base)}</p>${body}${ExactusReport.snippetViewer(finding.excerpt, id)}${ExactusReport.findingExtras(finding)}</li>`;
  };
  /**
   * @param {string} noun Singular English noun.
   * @returns {string} Its plural ("category" → "categories").
   */
  static pluralNoun = (noun) =>
    /[^aeiou]y$/.test(noun) ? `${noun.slice(0, -1)}ies` : `${noun}s`;
  /**
   * @param {string[]} values One facet value of every finding.
   * @returns {[string, number][]} Distinct values (first-seen order) with
   *   their counts.
   */
  static tally = (values) => {
    /** @type {Map<string, number>} */
    const counts = new Map();
    for (const value of values) {
      counts.set(value, (counts.get(value) ?? 0) + 1);
    }
    return [...counts.entries()];
  };
  /**
   * @param {string} id Select element id.
   * @param {string} label Visible label.
   * @param {string} noun Plural noun of the "all" option.
   * @param {[string, number][]} values Option values with counts.
   * @param {number} total Number of findings.
   * @returns {string} Labelled filter select markup.
   */
  static filterSelect = (id, label, noun, values, total) =>
    `<div class="select-filter"><label class="ds-label" for="${id}">${ExactusReport.escape(label)}</label><select class="ds-select" id="${id}"><option value="">All ${ExactusReport.escape(noun)} (${total})</option>${values
      .map(
        ([value, count]) =>
          `<option value="${ExactusReport.escape(value)}">${ExactusReport.escape(value)} (${count})</option>`,
      )
      .join("")}</select></div>`;
  /**
   * List findings, grouped under one heading per source when they come
   * from more than one source (in report order).
   * @param {Json[]} findings View-model findings.
   * @param {[string, number][]} sources Sources with their counts.
   * @param {string} base Relative URL of the project root.
   * @returns {string} Findings list markup.
   */
  static findingList = (findings, sources, base) => {
    if (sources.length < 2) {
      return `<ol class="findings-list">${findings
        .map(item => ExactusReport.viewFinding(item, base, 3))
        .join("")}</ol>`;
    }
    return sources
      .map(([source]) => {
        const id = `findings-group-${ExactusReport.slug(source)}`;
        const items = findings.filter(
          (item) => String(item.source ?? "") === source,
        );
        return `<section class="finding-group" data-group="${ExactusReport.escape(source)}" aria-labelledby="${id}"><h3 class="group-title" id="${id}">${ExactusReport.escape(source)} <span class="group-count ds-supporting">${ExactusReport.plural(items.length, "finding")}</span></h3><ol class="findings-list">${items
          .map(item => ExactusReport.viewFinding(item, base, 4))
          .join("")}</ol></section>`;
      })
      .join("");
  };
  /**
   * @param {Json} model View model.
   * @param {string} base Relative URL of the project root.
   * @returns {string} Findings toolbar and list markup.
   */
  static viewFindings = (model, base) => {
    if (model.findings === null || model.findings === undefined) {
      return ExactusReport.notReported("findings list");
    }
    const findings = ExactusReport.array(model.findings).map(
      ExactusReport.object,
    );
    if (!findings.length) {
      return '<p class="ds-supporting">No findings.</p>';
    }
    const levels = ExactusReport.array(model.severity_levels).map(String);
    const severities = ExactusReport.tally(
      findings.map((item) => String(item.severity ?? "").toLowerCase()),
    ).sort(
      ([left], [right]) =>
        (levels.indexOf(left) + 1 || levels.length + 1) -
          (levels.indexOf(right) + 1 || levels.length + 1) ||
        left.localeCompare(right),
    );
    const rules = ExactusReport.tally(
      findings.map((item) => String(item.rule ?? "")),
    ).sort(([left], [right]) => left.localeCompare(right));
    const sources = ExactusReport.tally(
      findings.map((item) => String(item.source ?? "")),
    ).filter(([source]) => source);
    const chips = [
      `<button class="ds-chip" type="button" data-view-severity="" aria-pressed="true">All <span class="chip-count">${findings.length}</span></button>`,
      ...severities.map(
        ([severity, count]) =>
          `<button class="ds-chip" type="button" data-view-severity="${ExactusReport.escape(severity)}" aria-pressed="false">${ExactusReport.escape(ExactusReport.humanize(severity || "unknown"))} <span class="chip-count">${count}</span></button>`,
      ),
    ].join("");
    const sourceFilter =
      sources.length > 1
        ? ExactusReport.filterSelect(
            "findings-source",
            String(model.source_label ?? "Source"),
            ExactusReport.pluralNoun(
              String(model.source_label ?? "source").toLowerCase(),
            ),
            sources,
            findings.length,
          )
        : "";
    return `<div class="toolbar"><div class="search"><label class="ds-label" for="findings-search">Search findings</label><input class="ds-input" id="findings-search" type="search" autocomplete="off" placeholder="ID, title, path or message"></div>${sourceFilter}${ExactusReport.filterSelect("findings-rule", "Rule", "rules", rules, findings.length)}<div class="filters" role="group" aria-label="Severity">${chips}</div></div><p class="ds-supporting result-count" role="status" id="findings-count"></p><div class="empty-filter" id="findings-empty" hidden><p class="ds-supporting" id="findings-empty-text"></p><button class="ds-btn ds-btn-outline ds-btn-sm" type="button" id="findings-clear">Clear filters</button></div><div class="findings-body" id="findings-list">${ExactusReport.findingList(findings, sources, base)}</div>`;
  };
  /**
   * @param {Json} model View model.
   * @returns {string} Identity key-value table markup.
   */
  static identitySection = (model) => {
    const tool = ExactusReport.object(model.tool);
    const run = ExactusReport.object(model.run);
    return ExactusReport.keyValues("Identity", [
      [
        "Tool",
        ExactusReport.escape(
          [tool.name, tool.version]
            .filter((part) => !ExactusReport.blank(part))
            .join(" "),
        ) || ExactusReport.cell(null),
      ],
      ["Run ID", ExactusReport.cell(run.id)],
      ["Pipeline run", ExactusReport.cell(run.pipeline_id)],
      ["Status", ExactusReport.statusBadge(run.status)],
      ["Exit code", ExactusReport.cell(run.exit_code)],
      ["Run time", ExactusReport.cell(run.at_human)],
      ["Started", ExactusReport.cell(run.started_at_human ?? run.started_at)],
      [
        "Finished",
        ExactusReport.cell(run.finished_at_human ?? run.finished_at),
      ],
      ["Duration", ExactusReport.cell(run.duration_human)],
    ]);
  };
  /**
   * @param {Json} model View model.
   * @returns {string} Invocation and environment markup.
   */
  static setupSection = (model) => {
    const invocation = ExactusReport.object(model.invocation);
    const environment = ExactusReport.object(model.environment);
    const variables = ExactusReport.array(environment.variables);
    const command = String(invocation.command ?? "");
    return `<h3 class="subsection-title">Invocation</h3>${
      command
        ? `<pre class="code"><code>${ExactusReport.escape(command)}</code></pre>`
        : ExactusReport.notReported("command")
    }${ExactusReport.keyValues("Invocation", [
      ["Working directory", ExactusReport.cell(invocation.cwd)],
      ["Arguments", ExactusReport.cell(invocation.arguments)],
    ])}<h3 class="subsection-title">Environment</h3>${ExactusReport.keyValues(
      "Environment",
      [
        ["Operating system", ExactusReport.cell(environment.os)],
        ["Python", ExactusReport.cell(environment.python)],
        ["Node", ExactusReport.cell(environment.node)],
        ["CPU count", ExactusReport.cell(environment.cpu_count)],
      ],
    )}${
      variables.length
        ? ExactusReport.recordTable(
            "Environment variables",
            variables,
            null,
            [],
          )
        : '<p class="ds-supporting">No allowlisted environment variables are set.</p>'
    }`;
  };
  /**
   * @param {string} title Block heading.
   * @param {unknown} value Tool extension block.
   * @param {unknown} order Column order recorded with the view model.
   * @returns {string} Generic rendering of one extension block.
   */
  static extensionBlock = (title, value, order) => {
    if (ExactusReport.blank(value)) {
      return ExactusReport.notReported(title.toLowerCase());
    }
    if (Array.isArray(value)) {
      if (!value.length) {
        return '<p class="ds-supporting">None reported.</p>';
      }
      if (value.every((item) => item && typeof item === "object")) {
        return ExactusReport.recordTable(title, value, null, order);
      }
      return value.every((item) => typeof item === "string" && /\s/.test(item))
        ? `<ul class="note-list">${value.map(item => `<li>${ExactusReport.inline(String(item))}</li>`).join("")}</ul>`
        : ExactusReport.globList(value, "None reported.");
    }
    if (typeof value === "object") {
      return ExactusReport.keyValues(
        title,
        Object.entries(ExactusReport.record(value)).map(([key, item]) => [
          ExactusReport.humanize(key),
          ExactusReport.cell(item),
        ]),
      );
    }
    return `<p>${ExactusReport.cell(value)}</p>`;
  };
  /**
   * Build the report sections of a migrated tool from its view model;
   * the outcome (gate, totals, findings) comes before run context.
   * @param {Json} data Report payload holding the view model.
   * @returns {{title: string, body: string}[]} Ordered sections.
   */
  static viewSections = (data) => {
    const model = ExactusReport.object(data.view);
    const base = String(data.project_href ?? "");
    const record = ExactusReport.record(data.view);
    const sequence = ExactusReport.array(data.view_order).map(String);
    /**
     * @param {string} key View-model key.
     * @returns {number} Mapping position of the key; unknown keys last.
     */
    const position = (key) =>
      sequence.includes(key) ? sequence.indexOf(key) : sequence.length;
    let toolKeys = Object.keys(record)
      .filter((key) => !ExactusReport.BASE_VIEW_KEYS.includes(key))
      .sort((left, right) => position(left) - position(right));
    let blocks = record;
    if (!toolKeys.length) {
      blocks = ExactusReport.record(model.extension);
      toolKeys = Object.keys(blocks);
    }
    const artifacts = ExactusReport.array(model.artifacts);
    const order = ExactusReport.record(data.view_columns);
    return [
      {
        title: "Gate",
        body: ExactusReport.gateSection(model),
      },
      {
        title: "What was checked",
        body: ExactusReport.checkedSection(model),
      },
      ...(ExactusReport.comparisonSection(model)
        ? [
            {
              title: "Change since previous report",
              body: ExactusReport.comparisonSection(model),
            },
          ]
        : []),
      {
        title: "Findings",
        body: ExactusReport.viewFindings(model, base),
      },
      ...toolKeys.map((key) => ({
        title:
          key === "workflow_rows"
            ? "Workflows and actions"
            : ExactusReport.humanize(key),
        body:
          key === "workflow_rows"
            ? ExactusReport.frontend({
                flows: ExactusReport.array(blocks[key]),
                evidence: ExactusReport.array(
                  ExactusReport.object(blocks).screenshots,
                ),
              }).view
            : ExactusReport.extensionBlock(
                ExactusReport.humanize(key),
                blocks[key],
                order[key],
              ),
      })),
      {
        title: "Artifacts",
        body: artifacts.length
          ? ExactusReport.recordTable(
              "Artifacts",
              artifacts,
              (row) => {
                const path = ExactusReport.sortText(
                  ExactusReport.object(row).path,
                );
                const verified = ExactusReport.localLinks[path];
                if (typeof verified === "string")
                  return ExactusReport.linkHref(verified) ?? "";
                return /^(?:\/|[a-zA-Z][a-zA-Z0-9+.-]*:)/.test(path)
                  ? ""
                  : `../${path.split("/").map(encodeURIComponent).join("/")}`;
              },
              ExactusReport.object(data.view_columns).artifacts,
              "path",
            )
          : '<p class="ds-supporting">No auxiliary artifacts.</p>',
      },
      {
        title: "Identity",
        body: ExactusReport.identitySection(model),
      },
      {
        title: "Setup",
        body: ExactusReport.setupSection(model),
      },
    ];
  };
  /**
   * @param {{title: string, body: string}[]} sections Ordered sections.
   * @returns {string} Section navigation plus section cards markup.
   */
  static viewMarkup = (sections) => {
    const links = sections
      .map(
        (section) =>
          `<li><a class="ds-chip" href="#${ExactusReport.sectionId(section.title)}">${ExactusReport.escape(section.title)}</a></li>`,
      )
      .join("");
    const cards = sections
      .map((section) => {
        const id = ExactusReport.sectionId(section.title);
        return `<section class="section ds-card view-card" id="${id}" aria-labelledby="${id}-title"><h2 class="ds-section-title" id="${id}-title">${ExactusReport.escape(section.title)}</h2>${section.body}</section>`;
      })
      .join("");
    return `<nav class="section-nav" aria-label="Report sections"><ul class="section-nav-list">${links}</ul></nav>${cards}`;
  };
  /**
   * Select a finding: clear filters that hide it, mark it selected, add a
   * link back to the table row that led to it, scroll it into view and
   * move focus to it.
   * @param {Element} root Rendered report view.
   * @param {string} id Finding identifier.
   * @param {Element | null} origin Table row the user came from.
   * @returns {boolean} Whether the finding exists.
   */
  static revealFinding = (root, id, origin) => {
    const item = root.querySelector(`#${ExactusReport.findingAnchor(id)}`);
    if (!(item instanceof HTMLElement)) return false;
    const clear = root.querySelector("#findings-clear");
    if (item.hidden && clear instanceof HTMLElement) {
      clear.dispatchEvent(new CustomEvent("reset-filters"));
    }
    for (const other of root.querySelectorAll(".vfinding.is-selected")) {
      other.classList.remove("is-selected");
      other.querySelector(".finding-return")?.remove();
    }
    item.classList.add("is-selected");
    if (origin?.id) {
      const back = document.createElement("a");
      back.className = "finding-return";
      back.href = `#${origin.id}`;
      back.textContent = `Back to ${origin.getAttribute("data-return-label") ?? "the table"}`;
      item.querySelector(".finding-head")?.append(back);
    }
    item.setAttribute("tabindex", "-1");
    item.scrollIntoView({
      block: "start",
      behavior: matchMedia("(prefers-reduced-motion: no-preference)").matches
        ? "smooth"
        : "auto",
    });
    item.focus({
      preventScroll: true,
    });
    return true;
  };
  /**
   * Follow in-page links to findings (table rows, gate list) and back to
   * the row they came from; a click anywhere on a linked row follows its
   * link.
   * @param {Element} root Rendered report view.
   */
  static bindFindingLinks = (root) => {
    root.addEventListener("click", (event) => {
      const target = event.target instanceof Element ? event.target : null;
      if (!target) return;
      const back = target.closest(".finding-return");
      if (back instanceof HTMLAnchorElement) {
        const row = root.querySelector(back.hash);
        if (!(row instanceof HTMLElement)) return;
        event.preventDefault();
        history.pushState(null, "", back.hash);
        row.scrollIntoView({
          block: "center",
        });
        row.focus({
          preventScroll: true,
        });
        return;
      }
      const link = target.closest('a[href^="#finding-"]');
      const row = target.closest("tr[data-finding-row]");
      if (!link && (!row || target.closest("a, button, input, select"))) {
        return;
      }
      const href = link?.getAttribute("href") ?? "";
      const id =
        row?.getAttribute("data-finding-row") ??
        link?.getAttribute("data-finding-link") ??
        "";
      const anchor = id ? `#${ExactusReport.findingAnchor(id)}` : href;
      const item = root.querySelector(anchor);
      const finding = item?.id.startsWith("finding-")
        ? (item.querySelector(".finding-id")?.textContent ?? "")
        : "";
      if (!finding) return;
      event.preventDefault();
      history.pushState(null, "", anchor);
      ExactusReport.revealFinding(root, finding, row);
    });
  };
  /**
   * Wire table sorting and the findings search, rule and severity filters.
   * @param {Element} root Rendered report view.
   */
  static bindView = (root) => {
    root.addEventListener("click", (event) => {
      const button =
        event.target instanceof Element
          ? event.target.closest(".sort-button")
          : null;
      if (button) ExactusReport.sortBy(button);
    });
    ExactusReport.bindFindingLinks(root);
    const search = root.querySelector("#findings-search");
    const rule = root.querySelector("#findings-rule");
    const source = root.querySelector("#findings-source");
    const sourceValue = () =>
      source instanceof HTMLSelectElement ? source.value : "";
    const groups = [...root.querySelectorAll(".finding-group")];
    const sourceName = (
      root.querySelector('label[for="findings-source"]')?.textContent ??
      "source"
    ).toLowerCase();
    const count = root.querySelector("#findings-count");
    const empty = root.querySelector("#findings-empty");
    const emptyText = root.querySelector("#findings-empty-text");
    const clear = root.querySelector("#findings-clear");
    const chips = [...root.querySelectorAll("[data-view-severity]")];
    const items = [...root.querySelectorAll(".vfinding")];
    if (
      !(search instanceof HTMLInputElement) ||
      !(rule instanceof HTMLSelectElement) ||
      !(empty instanceof HTMLElement) ||
      !count ||
      !emptyText ||
      !clear
    )
      return;
    const filter = {
      severity: "",
    };
    /** Show the findings matching the search, rule and severity filters. */
    const update = () => {
      const query = search.value.trim().toLowerCase();
      let shown = 0;
      for (const item of items) {
        const match =
          (!filter.severity ||
            item.getAttribute("data-severity") === filter.severity) &&
          (!rule.value || item.getAttribute("data-rule") === rule.value) &&
          (!sourceValue() ||
            item.getAttribute("data-source") === sourceValue()) &&
          (!query || (item.getAttribute("data-text") ?? "").includes(query));
        item.toggleAttribute("hidden", !match);
        shown += Number(match);
      }
      for (const group of groups) {
        const members = [...group.querySelectorAll(".vfinding")];
        const visible = members.filter((item) => !item.hasAttribute("hidden"));
        group.toggleAttribute("hidden", !visible.length);
        const tally = group.querySelector(".group-count");
        if (tally) {
          tally.textContent =
            visible.length === members.length
              ? ExactusReport.plural(members.length, "finding")
              : `${visible.length.toLocaleString()} of ${ExactusReport.plural(members.length, "finding")}`;
        }
      }
      const active = [
        filter.severity ? `severity “${filter.severity}”` : "",
        sourceValue() ? `${sourceName} “${sourceValue()}”` : "",
        rule.value ? `rule “${rule.value}”` : "",
        query ? `text “${query}”` : "",
      ].filter(Boolean);
      count.textContent =
        shown === items.length
          ? `Showing all ${ExactusReport.plural(items.length, "finding")}.`
          : `Showing ${shown.toLocaleString()} of ${ExactusReport.plural(items.length, "finding")}.`;
      empty.hidden = shown > 0;
      emptyText.textContent = `No findings match ${active.join(" and ")}.`;
    };
    for (const chip of chips) {
      chip.addEventListener("click", () => {
        filter.severity = chip.getAttribute("data-view-severity") ?? "";
        for (const other of chips) {
          other.setAttribute("aria-pressed", String(other === chip));
        }
        update();
      });
    }
    /** Reset every findings filter and show all findings. */
    const reset = () => {
      search.value = "";
      rule.value = "";
      if (source instanceof HTMLSelectElement) source.value = "";
      filter.severity = "";
      for (const chip of chips) {
        chip.setAttribute(
          "aria-pressed",
          String(chip.getAttribute("data-view-severity") === ""),
        );
      }
      update();
    };
    clear.addEventListener("click", () => {
      reset();
      search.focus();
    });
    clear.addEventListener("reset-filters", reset);
    search.addEventListener("input", update);
    rule.addEventListener("change", update);
    source?.addEventListener("change", update);
    update();
  };
  /**
   * Render a migrated tool's report from its view model.
   * @param {Json} data Report payload holding the view model.
   * @param {{view: Element, status: Element, resume: Element, metrics: Element}} parts
   *   Page elements to fill.
   */
  static renderView = (data, parts) => {
    const model = ExactusReport.object(data.view);
    const run = ExactusReport.object(model.run);
    const summary = ExactusReport.object(model.summary);
    const findings = ExactusReport.array(model.findings);
    parts.status.innerHTML = ExactusReport.statusBadge(
      run.status ?? data.status,
    );
    parts.resume.textContent = Object.keys(summary).length
      ? ExactusReport.summarySentence(summary)
      : String(ExactusReport.object(model.gate).reason ?? "");
    parts.metrics.innerHTML = ExactusReport.metrics([
      ["Findings", findings.length.toLocaleString()],
      ["Blocking", ExactusReport.array(model.blocking).length.toLocaleString()],
      [
        "Targets analyzed",
        Object.keys(summary).length
          ? `${Number(summary.targets_analyzed ?? 0).toLocaleString()} of ${Number(summary.targets_eligible ?? 0).toLocaleString()}`
          : "N/A",
      ],
      ["Duration", String(run.duration_human ?? "N/A")],
    ]);
    parts.view.innerHTML = ExactusReport.viewMarkup(
      ExactusReport.viewSections(data),
    );
    ExactusReport.bindView(parts.view);
    ExactusReport.bindSnippets(parts.view);
    const hash = decodeURIComponent(location.hash.slice(1));
    const target = hash.startsWith("finding-")
      ? parts.view.querySelector(`#${CSS.escape(hash)} .finding-id`)
      : null;
    if (target?.textContent) {
      ExactusReport.revealFinding(parts.view, target.textContent, null);
    }
  };
  /**
   * @param {Json} data Report payload.
   * @returns {[string, string][]} Run context pairs.
   */
  static context = (data) => {
    const fingerprint = ExactusReport.object(data.fingerprint);
    /** @type {[string, unknown][]} */
    const pairs = [
      ["Outcome", data.resume],
      ["Project", data.project_root ?? data.root],
      ["Run time", data.run_at_human],
      ["Generated", data.generated_at_human ?? data.generated_at],
      [
        "Duration",
        data.duration_seconds === undefined
          ? undefined
          : `${Number(data.duration_seconds).toFixed(2)} s`,
      ],
      ["Run", data.run_id],
      ["Pipeline run", data.pipeline_run_id],
      ["Report schema", data.schema],
      ...Object.entries(fingerprint).map(
        /**
         * @param {[string, unknown]} entry Fingerprint entry.
         * @returns {[string, unknown]} Labelled entry.
         */
        ([key, value]) => [ExactusReport.humanize(key), value],
      ),
    ];
    return pairs
      .filter(
        ([, value]) => value !== undefined && value !== null && value !== "",
      )
      .map(([label, value]) => [
        label,
        typeof value === "object" ? JSON.stringify(value) : String(value),
      ]);
  };
  static init = () => {
    const view = document.querySelector("#report-view");
    const markdown = document.querySelector("#report");
    const status = document.querySelector("#report-status");
    const resume = document.querySelector("#report-resume");
    const metrics = document.querySelector("#report-metrics");
    const context = document.querySelector("#report-context");
    const title = document.querySelector("#report-title");
    if (
      !view ||
      !markdown ||
      !status ||
      !resume ||
      !metrics ||
      !context ||
      !title
    )
      return;
    const data = ExactusReport.object(
      Reflect.get(globalThis, "__REPORT_DATA__"),
    );
    ExactusReport.localLinks = ExactusReport.object(
      Reflect.get(data, "local_links"),
    );
    if (!Object.keys(data).length) {
      view.innerHTML =
        '<p class="ds-supporting">Report data unavailable — regenerate the report bundle.</p>';
      return;
    }
    const analyzer = String(data.analyzer ?? "");
    document.title = String(data.title ?? "Exactus report");
    title.textContent = document.title;
    status.innerHTML = ExactusReport.statusBadge(
      data.status ?? (data.passed ? "PASS" : "FAIL"),
    );
    markdown.innerHTML = ExactusReport.markdown(String(data.markdown ?? ""));
    context.innerHTML = ExactusReport.context(data)
      .map(
        ([label, value]) =>
          `<dt>${ExactusReport.escape(label)}</dt><dd>${ExactusReport.escape(value)}</dd>`,
      )
      .join("");
    if (Object.keys(ExactusReport.object(data.view)).length) {
      ExactusReport.renderView(data, {
        view,
        status,
        resume,
        metrics,
      });
      return;
    }
    const coverage = analyzer === "coverage" || analyzer === "coverage-tests";
    if (
      coverage ||
      analyzer === "frontend" ||
      data.kind === "pipeline" ||
      (data.tools && !data.findings)
    ) {
      const result = coverage
        ? ExactusReport.coverage(data)
        : analyzer === "frontend"
          ? ExactusReport.frontend(data)
          : ExactusReport.unified(data);
      metrics.innerHTML = ExactusReport.metrics(result.metrics);
      resume.textContent = result.summary;
      const comparison = ExactusReport.comparisonSection(data);
      view.innerHTML = `${comparison ? `<section class="section" aria-labelledby="comparison-title"><h2 class="ds-section-title" id="comparison-title">Change since previous report</h2>${comparison}</section>` : ""}${result.view}`;
      if (coverage) ExactusReport.bindCoverage(data);
      for (const fill of view.querySelectorAll(
        ".ds-progress-bar[data-percent]",
      )) {
        fill.setAttribute(
          "style",
          `width:${fill.getAttribute("data-percent")}%`,
        );
      }
      return;
    }
    const rows = ExactusReport.findings(data);
    const files = new Set(rows.map((row) => row.file)).size;
    metrics.innerHTML = ExactusReport.metrics(
      ExactusReport.findingMetrics(data, rows),
    );
    resume.textContent = rows.length
      ? `${ExactusReport.plural(rows.length, "finding")} in ${ExactusReport.plural(files, "file")}; files with the most errors come first.`
      : "No findings in this run.";
    const comparison = ExactusReport.comparisonSection(data);
    view.innerHTML = `${comparison ? `<section class="section" aria-labelledby="comparison-title"><h2 class="ds-section-title" id="comparison-title">Change since previous report</h2>${comparison}</section>` : ""}${ExactusReport.findingsSection(rows)}`;
    ExactusReport.bindFindings(rows, String(data.project_href ?? ""));
  };
}
document.addEventListener("DOMContentLoaded", ExactusReport.init);
