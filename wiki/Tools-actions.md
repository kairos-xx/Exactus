[Home](Home.md) > [Tools](Tools.md) > actions

# actions/

Executes declarative sequences of Exactus tool calls with named output
references. Recipes are JSON or TOML documents containing ordered calls;
each call may consume outputs produced by an earlier call.

Run a recipe with `python -m exactus.actions <recipe>`, through
`./exec/exactus --frontend --actions <recipe>`, or from Studio under
**Target & viewport → Actions recipe**.

## Files

  -----------------------------------------------------------------------
  File / path                         Description
  ----------------------------------- -----------------------------------
  `__init__.py`                       Package surface.

  `__main__.py`                       CLI entry: load a JSON/TOML recipe,
                                      orchestrate it, and report
                                      progress.

  `runner.py`                         Recipe parsing, validation, ordered
                                      execution, named output references,
                                      per-call output directories, and
                                      failure semantics.

  `process_control.py`                Vendored cross-invocation ownership
                                      and termination primitives.

  `conflict_copies.py`                Reconciles numbered synchronization
                                      copies without discarding unique
                                      data.

  `json_types.py`                     JSON value types used by recipe
                                      documents.

  `examples/`                         Shipped recipes, including crawler
                                      → record → frontend chains.
  -----------------------------------------------------------------------

## Model

-   Actions are orchestration data, not Studio projects. A recipe calls
    tools; a Studio project contains editable flows, timeline steps,
    assertions, and screenshot requests.
-   Recipes support JSON and TOML schema version `1`.
-   Calls execute in declaration order and IDs must be unique.
-   A call may reference outputs from an earlier completed call, for
    example `$discover.projects` or `$discover.server_log`.
-   References are resolved as data without shell interpolation. Invalid
    tools and forward references are rejected before execution.
-   Concrete arguments are validated before any call starts. Booleans
    are strict; crawl depth is 1--10, state count is 1--200, ports are
    0--65535, and viewport dimensions are integer pixels from 1--16384.
    Unknown arguments fail validation.
-   Each tool receives the selected root and its own output directory.
-   Ordinary recipes execute only the declared calls; pipeline
    dependencies are not expanded implicitly.
-   Setup failures stop the sequence while preserving failure evidence.
    A failed tool retains its result and report.
-   The runner uses the same process-control ownership rules as the
    orchestrator, so canonical termination interrupts recipe execution
    cleanly.
-   Recipes can live in a project and run independently of the recipe
    author's environment.

## Configuration

Frontend configuration selects an Actions recipe rather than an
application entrypoint:

``` toml
[tool.exactus.frontend]
actions = "demo/actions/frontend.json"
```

Configured paths resolve beside their `pyproject.toml`. An explicit
`--workspace` or `--url` replaces the configured recipe for that
invocation. Application entrypoint and port configuration belong to the
recipe's crawl call.

Run the same recipe directly or through the frontend orchestrator:

``` sh
python -m exactus.actions demo/actions/frontend.json \
  --output EXACTUS_RESULTS/ACTIONS

./exec/exactus --frontend --actions demo/actions/frontend.json
```

Studio can edit, import, export, and run the same JSON recipe. **Open
Actions report** opens its protected local report. The service owns an
application process launched by the recipe and stops it when execution
finishes.

## Recipe

A crawler-to-frontend recipe:

``` json
{
  "version": 1,
  "actions": [
    {
      "id": "discover",
      "tool": "record.crawl",
      "arguments": {
        "entrypoint": "server.py",
        "url": "http://127.0.0.1/",
        "port": 0,
        "screenshots": true,
        "server_errors": true,
        "javascript": ["() => document.title"],
        "max_depth": 2,
        "max_states": 20,
        "environments": [
          {"width": 390, "height": 844, "theme": "light"},
          {"width": 1440, "height": 900, "theme": "dark"}
        ]
      }
    },
    {
      "id": "verify",
      "tool": "frontend.run",
      "arguments": {
        "projects": "$discover.projects",
        "server_log": "$discover.server_log"
      }
    }
  ]
}
```

Entrypoints resolve relative to the recipe file when using the CLI and
relative to the selected project root in Studio. Port `0` selects an
available loopback port. Discovery and replay share the launched server.
Server stdout/stderr is retained in `server.log`; `server_errors`
controls promotion of server error diagnostics.

## Tools

### `record.crawl`

Discovers browser states and produces ordinary `.pwflow.json` Studio
projects. Supported controls include UI snapshots, `follow_links`,
`click_controls`, `include_selector`, depth/state limits, viewport/theme
`environments`, and explicit `javascript` expressions added to generated
flows.

UI snapshots are enabled by default. Each environment produces a project
at its configured viewport and theme with PNG assets stored inline. The
generated projects open directly in Studio and can be transferred as
single files. PNG imports verify SHA256, dimensions, and format before
writing.

### `frontend.run`

Replays generated projects at their respective viewport sizes and
themes. Its report contains workflow runs, action outcomes, JavaScript
responses, assertion evaluations, browser/server diagnostics, and
requested screenshots.

Discovery diagnostics remain separate from replay diagnostics. Aggregate
reporting groups repeated diagnostic causes while preserving independent
failed workflows.

### Catalog tools

Canonical Exactus tools can be called by catalog ID with an `argv` list:

``` json
{
  "id": "lint",
  "tool": "lints",
  "arguments": {
    "argv": ["--dry"]
  }
}
```

Catalog calls follow the same ordering, output-directory, validation,
failure, and process-control semantics as other recipe calls.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/tools/actions/`](../exactus/tools/actions/) | [`exactus/tests/tools/actions/`](../exactus/tests/tools/actions/) | [`DOCS.md`](../exactus/docs/tools/actions/DOCS.md) |

[Tools index](Tools.md) · [Tools-common >](Tools-common.md)
