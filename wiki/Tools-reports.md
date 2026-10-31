[Home](Home.md) > [Tools](Tools.md) > reports

# tools/reports/

Report bundle writing and normalized-report rendering — the bridge
between each tool's `result.json` and the shipped `result.md`/offline
web bundle.

## Files

| File | Description |
|---|---|
| `bundle.py` | `ReportBundle`: writes consistent `result.json`, `result.md` and the offline web bundle (`report.css`/`report.js`/`data.js`) for every tool — canonical names regardless of what the tool requested. |
| `render.py` | Render normalized `result.json` through each tool's template/mapping via the `exactus.markdown` engine. |

## Behavior

- Canonical naming: any `ReportPaths` a tool passes is rewritten to
  `result.*`, so `result.json` is always the semantic source.
- `render.py` composes tool-specific templates/mappings on the generic
  engine — the engine itself stays report-independent.
- Before rendering, `render.py` assigns every mapped finding a stable
  `finding-…` anchor id and builds `file_summary`: findings grouped per
  file with concise issue rows. The common template emits a "By file"
  resume that links each issue to its anchored finding section; the web
  renderer passes the `<a id>` markers through so `#finding-…` links
  work there too. `file_summary` is template-only and is excluded from
  the mapped web `view`.
- The web bundle is fully offline: no CDN, one `data.js` carries the
  model and `report.js` renders it client-side.
- Applies the shared stamp (`NormalizedStamp`) so every report carries
  the same envelope blocks before rendering.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/tools/reports/`](../exactus/tools/reports/) | [`exactus/tests/tools/reports/`](../exactus/tests/tools/reports/) | [`DOCS.md`](../exactus/docs/tools/reports/DOCS.md) |

[< Tools-record](Tools-record.md) · [Tools index](Tools.md) · [Tools-self_test >](Tools-self_test.md)
