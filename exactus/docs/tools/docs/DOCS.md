# tools/docs/

The `docs` tool: audit documentation contracts — Google-style Python
docstrings and JSDoc blocks — from a single Python program.

It does more than count undocumented symbols: for every module, class,
function, method, and callable it checks that the documentation **exists**,
has a useful summary, and **matches the code** — parameters, returns,
yields, raises, and class attributes are all reconciled against the
signature and the body. Every finding carries a complete, generated
docstring/JSDoc skeleton that can be pasted in and filled out.

## Files

| File | Description |
|---|---|
| `arguments.py` | The docs CLI grammar, declared without importing the execution engine. |
| `core.py` | The entire engine: `PythonAnalyzer` (AST-based) and `JavaScriptAnalyzer` (pure-Python structural lexical recognition — no JS parser), finding/report model, discovery, metrics, and the `DocumentationExactus` orchestrator. |
| `main.py` | Entry point: resolve config/CLI, build `Config`, run `DocumentationExactus`, emit the `DOCS` report bundle. |
| `templates/` | `markdown/template.md` + `markdown/mapping.json` that render `result.md` from the normalized payload. |

## Pipeline

`DocumentationExactus.run` executes four stages:

1. **Discover** — `_discover` walks `root` once, collecting `.py` files
   (when `python` is in scope) and `.js`/`.mjs`/`.cjs` files (when
   `javascript` is). Pruned directories: the fixed `Constants.exclude_dirs`
   set (`.git`, `.venv`, `node_modules`, `__pycache__`, `build`, `dist`,
   `htmlcov`, `mutants`, `site-packages`, IDE/agent dirs, caches, …) plus
   every hidden directory; `*.min.js` is always excluded.
2. **Filter** — each discovered file is tested against the
   `--include`/`--exclude` globs (`match_path`). Rejected files are
   recorded as `scope.skipped` entries with reason
   `excluded by include/exclude rules`; metrics count only the eligible
   survivors.
3. **Analyze** — `PythonAnalyzer.analyze` parses each `.py` with `ast`;
   `JavaScriptAnalyzer` prepares JavaScript files in a background pass
   (read + syntax validation) and then audits them. Findings are sorted
   by file, line, column, code, qualname.
4. **Report + gate** — `report_data` builds the normalized envelope and
   `ReportBundle.write` emits `DOCS.md`, `DOCS.json`, and `DOCS_web/`.
   The exit status is decided by the `--fail-on` severity gate.

## Finding codes

Twelve rules, shared by both languages (severity `warning` unless noted;
confidence is `high` except DOC008 in both languages, DOC012, and the
JS DOC006, which are `medium`):

| Code | Title | What is flagged |
|---|---|---|
| `DOC001` | Missing documentation | Symbol has no docstring/JSDoc block at all. For Python the module itself is also checked. For JS, no whitespace-adjacent `/** … */` precedes the symbol. |
| `DOC002` | Missing parameter documentation | A signature parameter has no entry in `Args:`/`@param`. |
| `DOC003` | Stale parameter documentation | `Args:`/`@param` documents a name absent from the signature. |
| `DOC004` | Missing return documentation | The callable returns a value but has no `Returns:`/`@returns`. |
| `DOC005` | Return and yield mismatch | A generator (direct `yield`/`yield from`, or `function*`/`yield` in JS) lacks `Yields:`/`@yields` (or `@returns` for JS). |
| `DOC006` | Missing exception documentation | A directly raised/thrown exception has no `Raises:`/`@throws` entry. |
| `DOC007` | Missing attribute documentation | A public class attribute is not in `Attributes:` (Python only). |
| `DOC008` | Malformed documentation | A section entry does not match Google/JSDoc structure. |
| `DOC009` | Analysis failure | File unreadable or unparseable — severity **`error`**. |
| `DOC010` | Missing description | Docstring/JSDoc exists but has no useful summary line. |
| `DOC011` | Stale exception documentation | Documented exception not raised in the body (defined, not currently emitted). |
| `DOC012` | Stale attribute documentation | `Attributes:` names something the class never directly declares. |

## Python audit (`PythonAnalyzer`)

AST-based; no imports are executed.

### Symbols audited

- **Modules** — the module docstring itself (DOC001 when absent).
- **Functions** — module-level `def`/`async def`, qualified by name.
- **Methods** — classified by decorator into `method`, `staticmethod`,
  `classmethod`, or `property` kinds.
- **Classes** — including nested classes (recursed via `_exactus_class`).
- **Nested functions** — audited recursively as
  `outer.<locals>.inner`.

### Skips and exemptions

- `--public-only` skips single-underscore names (`_private`); dunder
  methods are unaffected by that flag.
- Dunder methods are **skipped entirely** except the documented
  lifecycle set — `__init__`, `__call__`, `__enter__`, `__exit__`,
  `__aenter__`, `__aexit__` — which are audited like any callable.
- `self`/`cls` receivers are excluded from the expected-parameter set for
  methods.

### Contract checks (per documented callable)

- **Summary (DOC010)** — first non-empty line must exist and be more than
  bare quotes.
- **Args (DOC002/DOC003)** — expected = every positional, positional-only,
  keyword-only, `*args`, and `**kwargs` parameter (receivers excluded);
  documented = names parsed from the `Args:` section.
- **Returns/Yields (DOC004/DOC005)** — "returns a value" means a direct
  `return <expr>` exists in the callable's own scope, or the return
  annotation is not `None`/`NoReturn`/`Never`. Generators must document
  `Yields:` instead of `Returns:`.
- **Raises (DOC006)** — direct `raise X` / `raise mod.X()` statements in
  the callable's own scope; bare names must look like exceptions
  (uppercase) or be calls. Qualified `mod.Error` is matched by `Error`.
- **Attributes (DOC007/DOC012)** — expected = public names directly
  assigned or annotated in the class body; entries for `self.x` instance
  attributes declared with annotations inside methods are also accepted,
  anything else documented is stale.
- **Malformed entries (DOC008)** — recognized sections are `Args`,
  `Returns`, `Raises`, `Yields`, `Attributes`, `Notes`, `Examples`,
  `Warnings`, `References`, `See Also`. Inside `Args`/`Raises`/
  `Attributes`, each entry must match `    name: description` (leading
  `*`/`**` allowed; `Raises` entries may be dotted paths; deeper-indented
  lines continue the previous entry). Any other indented line is DOC008.
- **Scope discipline** — `_direct_nodes` excludes nested function/class
  bodies, so a parent's `Raises`/`Yields` contract is judged only on its
  own code; the nested callable is audited on its own terms.

### Suggestions

`_suggest_function`/`_suggest_class` generate a complete Google-style
docstring: a one-line summary derived from the symbol name, an `Args:`
entry per parameter (with a name-derived description), `Yields:` or
`Returns:` as the body requires, one `Raises:` entry per detected
exception, and `Attributes:` for classes.

## JavaScript audit (`JavaScriptAnalyzer`)

Pure Python — the analyzer masks strings, template literals, regexes, and
comments while preserving offsets (`_mask`), then recognizes structure
lexically. TypeScript syntax inside `.js` files is not parsed.

### Symbols audited

- `class` declarations and their methods (`_class_symbols`/
  `_class_methods`).
- `function`/`async function`/`function*` declarations and expressions.
- Arrow functions, including single-parameter arrows.
- `const`/`let`/`var` names whose initializer is a `function` expression
  or arrow (audited as `arrow` kind).
- Symbols are deduplicated on (offset, qualname); names inside class
  ranges are not double-counted.

### Skips and exemptions

- `Constants.js_exempt_names` never flagged: `constructor`, `render`,
  `init`, `mount`/`unmount`, `destroy`, `dispose`, `updated`,
  `shouldUpdate`, `firstUpdated`, `beforeMount`/`afterMount`,
  `beforeUnmount`/`afterUnmount`, the Web-Components callbacks
  (`connectedCallback`, `disconnectedCallback`,
  `attributeChangedCallback`, `adoptedCallback`), `toJSON`, `toString`,
  `valueOf`.
- `--public-only` also skips `_`- and `#`-prefixed names.

### Contract checks

A symbol is "documented" only when a `/** … */` block ends immediately
before it (whitespace-adjacent). For a documented symbol:

- **Summary (DOC010)** — a non-tag description line must exist.
- **`@param` (DOC002/DOC003)** — expected = parameters parsed from the
  signature text (destructuring and defaults handled); documented =
  `@param` tag names.
- **`@returns`/`@yields` (DOC004/DOC005)** — the masked body is scanned
  for `return <expr>` (not `return;`), `yield`, and `function*`; value
  returns need `@returns`, generators need `@yields` or `@returns`.
- **`@throws` (DOC006)** — `throw new Name` expressions in the body must
  have matching `@throws`/`@exception` entries (medium confidence —
  aliases and conditional throws can't be proven statically).
- **Malformed tags (DOC008)** — `@param`/`@returns`/`@throws` lines that
  cannot be parsed into `{type} name — description` shape.

`_suggest` produces a complete JSDoc skeleton the same way — summary,
`@param` per parameter, `@returns`/`@yields`, `@throws` per detected
exception.

### Syntax validation

Unless `--no-js-check`, each file is validated before analysis: when a
Node toolchain is resolvable (`exactus_tool_prefix("node")`), `node
--check` decides; otherwise the analyzer falls back to a masked
delimiter-balance check. Failures are reported as `DOC009` errors and the
file contributes no symbols.

## CLI and configuration

```bash
python -m exactus.tools.docs.main [ROOT] [options]
```

| Option | Effect |
|---|---|
| `root` (positional) | Project root (default: current directory). |
| `-o`, `--output-dir PATH` | Report bundle directory (default: `EXACTUS_RESULTS/DOCS`). |
| `--include GLOB` / `--exclude GLOB` | Restrict scope; repeatable. |
| `--context-lines N` | Source lines embedded around each finding excerpt. |
| `--language both\|python\|javascript` | Restrict the audit to one language family (default: `both`). |
| `--public-only` | Audit only public symbols (`_`/`#` names skipped). |
| `--no-js-check` | Skip JavaScript syntax validation entirely. |
| `--fail-on error\|warning\|info\|never` | Severity threshold that fails the run (default: `warning`). |
| `--collect-files` | Bundle every file with findings into a `FILES/` folder beside the report. |

Configuration (`resolve_arguments`): `pyproject.toml` `[tool.exactus]`
and `[tool.exactus.docs]` accept the same options — `fail-on`,
`public-only`, `language`, `no-js-check`, `include`/`exclude`,
`context-lines`. Explicit CLI arguments take precedence.

## Report

`report_data` emits the normalized envelope:

- **`summary`** — `targets_eligible` (files discovered), `targets_analyzed`
  (eligible minus glob-skipped), `findings_total`, and per-severity
  counts.
- **`scope`** — `include`/`exclude` globs and `skipped`: files excluded
  by the globs (with reason) — these never enter the metrics.
- **`findings`** — normalized rows `DOCS-001`… sorted by file/line/
  column/code; each carries `code`, `language`, `severity`, `confidence`,
  `file`, `line`, `column`, `kind` (`module`, `class`, `function`,
  `method`, `staticmethod`, `classmethod`, `property`, `arrow`), a
  `qualname`/`subject`, the rendered `signature`, `message`, `reason`,
  and the full `suggestion` docstring.
- **`extension.languages`** — per-language statistics: `discovered`,
  `parsed`, `failed`, `symbols`, `documented`, `findings`, and
  `coverage_percent` (`documented / symbols`).
- **`extension.rules`** — every DOC code with its title and count.
- **`extension.metrics.languages`** — `files_analyzed` and
  `lines_analyzed` per language.
- **`extension.fail_on`** — the gate in effect (`never` when disabled).

### Exit status

`run` returns `1` at the first finding whose severity rank meets the
`--fail-on` threshold (ranks: `info` = 1 < `warning` = 2 < `error` = 3;
a finding blocks when `rank(finding) >= rank(fail_on)`), `0` when below
threshold or `never`. With the default `warning`, any contract violation
fails the run; only DOC009 is `error`, so `--fail-on error` tolerates
documentation gaps and fails only on unreadable/unparseable sources.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Docs exactus tool. |
| `arguments.py` | Declare the docs grammar without importing its execution engine. |
| `core.py` | Exactus Python docstrings and JavaScript JSDoc from one Python program. |
| `main.py` | Exactus Python docstrings and JavaScript JSDoc. |
| `templates/` | Subdirectory. |

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `--language` |  | choices=('both', 'python', 'javascript'), default='both' |
| `--public-only` |  | action='store_true' |
| `--no-js-check` |  | action='store_true' |
| `--fail-on` |  | choices=('error', 'warning', 'info', 'never'), default='warning' |
| `root` |  | nargs='?', default='.' |
| `--markdown` |  | default='DOCUMENTATION_EXACTUS.md' |
| `--json` |  | dest='json_output', default='DOCUMENTATION_EXACTUS.json' |
| `--language` |  | choices=('both', 'python', 'javascript'), default='both' |
| `--exclude` |  | action='append' |
| `--public-only` |  | action='store_true' |
| `--no-js-check` |  | action='store_true' |
| `--fail-on` |  | choices=('error', 'warning', 'info', 'never'), default='never' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Docs exactus tool.


### `arguments.py`

Declare the docs grammar without importing its execution engine.

- `create_parser() -> ArgumentParser` — Create parser.

### `core.py`

Exactus Python docstrings and JavaScript JSDoc from one Python program.

- `class Constants` — Represent constants.
  - `exclude_dirs` = `ExactusCommonTables.DEFAULT_EXCLUDED_DIRS`
  - `python_sections` = `('Args', 'Returns', 'Raises', 'Yields', 'Attributes')`
  - `js_exempt_names` = `frozenset({'adoptedCallback', 'afterMount', 'afterUnmount', 'attributeCha...`
  - `python_exempt_dunders` = `frozenset({'__aenter__', '__aexit__', '__call__', '__enter__', '__exit__'...`
  - `severity_rank` = `{'info': 1, 'warning': 2, 'error': 3}`
  - `code_titles` = `{'DOC001': 'Missing documentation', 'DOC002': 'Missing parameter document...`
  - `id_prefix` = `'DOCS'`
  - `excluded_reason` = `'excluded by include/exclude rules'`
  - `default_includes` = `{'python': ('**/*.py',), 'javascript': ('**/*.js', '**/*.mjs', '**/*.cjs')}`
  - `builtin_excludes` = `('**/*.min.js',)`
- `class Code` — Represent code.
  - `MISSING_DOCUMENTATION` = `'DOC001'`
  - `MISSING_PARAMETER` = `'DOC002'`
  - `STALE_PARAMETER` = `'DOC003'`
  - `MISSING_RETURN` = `'DOC004'`
  - `RETURN_YIELD_MISMATCH` = `'DOC005'`
  - `MISSING_EXCEPTION` = `'DOC006'`
  - `MISSING_ATTRIBUTE` = `'DOC007'`
  - `MALFORMED_DOCUMENTATION` = `'DOC008'`
  - `ANALYSIS_FAILURE` = `'DOC009'`
  - `MISSING_DESCRIPTION` = `'DOC010'`
  - `STALE_EXCEPTION` = `'DOC011'`
  - `STALE_ATTRIBUTE` = `'DOC012'`
- `class Config` — Represent config.
  - `includes` = `()`
  - `excludes` = `()`
  - `include_files` = `()`
  - `context_lines` = `SnippetLimits.default_context`
  - Fields: `root: Path`, `markdown: Path`, `json_output: Path`, `languages: frozenset[Language]`, `exclude_dirs: frozenset[str]`, `exclude_hidden_dirs: bool`, `public_only: bool`, `validate_javascript: bool`, `fail_on: Severity | None`
- `class Skip` — One discovered source file that was not exactused.
  - Fields: `target: str`, `reason: str`
- `class Finding` — Represent finding.
  - `subject` = `''`
  - Fields: `code: Code`, `language: Language`, `severity: Severity`, `confidence: Confidence`, `file: Path`, `line: int`, `column: int`, `kind: SymbolKind`, `qualname: str`, `signature: str`, `message: str`, `reason: str`, `suggestion: str`
  - `relative_dict(self: Self, root: Path) -> dict[str, str | int]` — Return a JSON-safe finding relative to the repository root.
- `class Statistics` — Represent statistics.
  - `discovered` = `0`
  - `parsed` = `0`
  - `failed` = `0`
  - `symbols` = `0`
  - `documented` = `0`
  - `findings` = `0`
- `empty_statistics() -> dict[Language, Statistics]` — Return zeroed counters for every exactused language.
- `empty_lines() -> dict[Language, int]` — Return a zeroed line counter for every exactused language.
- `class Report` — Represent report.
  - `findings` = `field(default_factory=list)`
  - `statistics` = `field(default_factory=empty_statistics)`
  - `lines` = `field(default_factory=empty_lines)`
  - `add(self: Self, finding: Finding) -> None` — Append one finding and update counters.
- `class ParsedGoogleDoc` — Represent parsed google doc.
  - Fields: `summary: str`, `sections: dict[str, tuple[str, ...]]`, `malformed: tuple[str, ...]`
- `class JsDoc` — Represent js doc.
  - Fields: `summary: str`, `params: tuple[str, ...]`, `returns: bool`, `yields: bool`, `throws: tuple[str, ...]`, `properties: tuple[str, ...]`, `malformed: tuple[str, ...]`
- `class JsDocBlock` — Represent js doc block.
  - Fields: `start: int`, `end: int`, `content: str`
- `class JsSymbol` — Represent js symbol.
  - Fields: `name: str`, `qualname: str`, `kind: SymbolKind`, `start: int`, `body_start: int | None`, `body_end: int | None`, `params_text: str`, `signature: str`, `is_async: bool`, `is_generator: bool`
- `class Text` — Pure text utilities shared by both analyzers.
  - `description(cls: type[Self], name: str, kind: SymbolKind, *, returns: bool=False) -> str` — Infer a concise documentation summary from a symbol name.
  - `parameter_description(cls: type[Self], name: str) -> str` — Infer a short parameter description.
  - `balanced_split(cls: type[Self], value: str) -> tuple[str, ...]` — Split a comma list without splitting nested expressions.
  - `words(name: str) -> list[str]` — Split snake/camel/pascal identifiers into lowercase words.
  - `line_column(source: str, offset: int) -> tuple[int, int]` — Convert a character offset to one-based line and zero-based column.
- `class PythonFindingArgs` — Represent python finding args.
  - Fields: `code: Code`, `file: Path`, `node: AST`, `kind: SymbolKind`, `qualname: str`, `signature: str`, `confidence: NotRequired[Confidence]`, `message: str`, `reason: str`, `suggestion: str`, `subject: NotRequired[str]`
- `class PythonAnalyzer` — Analyze Google-style Python documentation contracts.
  - `__init__(self: Self, config: Config, report: Report) -> None` — Initialize the analyzer.
  - `analyze(self: Self, file: Path) -> None` — Analyze one Python file.
- `class JavaScriptAnalyzer` — Analyze JSDoc using Python-only structural lexical recognition.
  - `__init__(self: Self, config: Config, report: Report) -> None` — Initialize the analyzer.
  - `prepare(self: Self, *, files: tuple[Path, ...]) -> None` — Read and prevalidate JavaScript files in one concurrent batch.
  - `prepare_background(self: Self, *, files: tuple[Path, ...]) -> None` — Start JavaScript preparation while Python analysis proceeds.
  - `finish_prepare(self: Self) -> None` — Wait for background JavaScript preparation to finish.
  - `analyze(self: Self, file: Path) -> None` — Analyze one JavaScript file.
- `report_data(*, config: Config, report: Report, eligible: int, skipped: tuple[Skip, ...]) -> dict[str, JsonValue]` — Return the normalized JSON payload of one documentation exactus.
- `class DocumentationExactus` — Coordinate discovery, analysis, reporting, and exit status.
  - `__init__(self: Self, config: Config, *, file_filter: Callable[[Path], bool] | None=None) -> None` — Initialize the exactus.
  - `files(self: Self) -> tuple[Path, ...]` — Discover source files deterministically.
  - `run(self: Self) -> int` — Execute the exactus and write reports.
- `parse_args() -> Config` — Parse command-line arguments.
- `main() -> int` — Run the documentation exactus.

### `main.py`

Exactus Python docstrings and JavaScript JSDoc.

- `create_parser() -> ArgumentParser` — Return the shared CLI grammar used by execution and completion.
- `parse_args(*, arguments: tuple[str, ...] | None=None) -> Namespace` — Parse args.
- `main(*, arguments: tuple[str, ...] | None=None) -> int` — Return main.

## Dependencies and consumers

- Other packages: [`argument_parser`](../../packages/argument_parser/DOCS.md), [`project_python`](../../packages/project_python/DOCS.md), [`steps`](../../packages/steps/DOCS.md), [`common`](../common/DOCS.md), [`reports`](../reports/DOCS.md)
- Used by: `__main__.py`, `tests/tools/common/test_context_lines.py`, `tests/tools/docs/test_docs_metrics.py`, `tests/tools/docs/test_docs_report.py`, `tests/tools/reports/test_report_snippets.py`

## Tests

Tests live in `exactus/tests/tools/docs/`.

- `test_docs_metrics.py` — DOCS reports docstring and JSDoc analysis volume. (7 tests)
  - `test_code_lines_count_line_feeds`
  - `test_empty_metrics_say_why_nothing_is_listed`
  - `test_empty_sources_report_zero_code_volume`
  - `test_failed_and_excluded_sources_are_not_counted`
  - `test_languages_report_files_and_lines`
  - `test_legacy_language_table_is_unchanged`
  - `test_missing_metrics_render_na`
- `test_docs_report.py` — DOCS renders result.md from its normalized result.json and template. (6 tests)
  - `test_clean_docs_run_states_no_findings`
  - `test_crash_render_shows_error_and_na_blocks`
  - `test_execute_exactus_renders_docs_from_template`
  - `test_golden_result_renders_expected_markdown`
  - `test_overload_signatures_need_no_docstring`
  - `test_report_data_is_normalized`

<!-- exactus:reference:end -->
