window.__REPORT_DATA__ = JSON.parse(`{
  "title": "Python Call, Import, and Typing Exactus",
  "status": "PASS",
  "tool": {
    "name": "kwargs_typehints",
    "display_name": "Python Call, Import, and Typing Exactus",
    "version": "0.5.0"
  },
  "summary": {
    "python_files": 6,
    "parse_failures": 0,
    "positional_findings": 0,
    "bare_import_findings": 0,
    "missing_type_hints": 0,
    "ambiguous_calls": 0,
    "unresolved_callees": 0,
    "unresolved_call_sites": 0,
    "call_sites": 3,
    "resolved_call_sites": 3,
    "exempt_call_sites": 0,
    "functions_checked": 5,
    "parameters_checked": 5,
    "targets_eligible": 6,
    "targets_analyzed": 6,
    "findings_total": 0,
    "auto_fixes": 0,
    "severity": {
      "error": 0,
      "warning": 0,
      "info": 0
    }
  },
  "ambiguous": [],
  "analyzer": "static",
  "artifacts": [
    {
      "name": "@activity.json",
      "path": "ARTIFACTS/@activity.json",
      "bytes": 1867
    },
    {
      "name": "README.md",
      "path": "ARTIFACTS/README.md",
      "bytes": 460
    },
    {
      "name": "heuristics.json",
      "path": "ARTIFACTS/heuristics.json",
      "bytes": 3915721
    },
    {
      "name": "stderr.log",
      "path": "ARTIFACTS/stderr.log",
      "bytes": 0
    },
    {
      "name": "stdout.log",
      "path": "ARTIFACTS/stdout.log",
      "bytes": 0
    },
    {
      "name": "steps.txt",
      "path": "ARTIFACTS/steps.txt",
      "bytes": 4275
    }
  ],
  "auto_fixes": [],
  "bare_imports": [],
  "comparison": {
    "available": true,
    "previous_generated_at": "2026-10-31T02:36:02.109043+00:00",
    "previous_run_id": "121cfe10a875424b95e7d42f9947eb9a:kwargs_typehints",
    "previous_status": "PASS",
    "previous_duration_seconds": 1.682,
    "current_total": 0,
    "previous_total": 0,
    "delta": 0,
    "added_count": 0,
    "resolved_count": 0,
    "unchanged_count": 0,
    "added": [],
    "resolved": [],
    "finding_details_available": true,
    "subsections": [],
    "categories": [
      {
        "category": "ambiguous-call",
        "title": "Ambiguous calls",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "bare-import",
        "title": "Bare imports",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "missing-hint",
        "title": "Missing type hints",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "missing-kwargs",
        "title": "Missing keyword arguments",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "parse-failure",
        "title": "Parse failures",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "unresolved-callee",
        "title": "Unresolved callees",
        "current": 0,
        "previous": 0,
        "delta": 0
      }
    ]
  },
  "duration_seconds": 1.523,
  "environment": {
    "os": "Darwin 25.3.0",
    "python": "3.13.9",
    "node": "v22.21.1",
    "cpu_count": 18,
    "variables": [
      {
        "name": "EXACTUS_ORCHESTRATED",
        "value": "1"
      },
      {
        "name": "EXACTUS_PIPELINE_RUN_ID",
        "value": "f9656595c8b74d23b2b6aec3bd0db7de"
      },
      {
        "name": "EXACTUS_REGISTRY",
        "value": "/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/.runtime/runs.db"
      },
      {
        "name": "EXACTUS_ROOT",
        "value": "/Users/joaolopes/Exactus/exactus/tests/standalone/project"
      },
      {
        "name": "EXACTUS_RUN_ID",
        "value": "f9656595c8b74d23b2b6aec3bd0db7de:kwargs_typehints"
      },
      {
        "name": "EXACTUS_TOOL",
        "value": "kwargs_typehints"
      },
      {
        "name": "LANG",
        "value": "C.UTF-8"
      }
    ]
  },
  "extension": {
    "metrics": {
      "overview": {
        "files_scanned": 6,
        "files_analyzed": 6,
        "parse_failures": 0,
        "call_sites": 3,
        "resolved_call_sites": 3,
        "resolution_percent": 100.0,
        "exempt_call_sites": 0,
        "unresolved_call_sites": 0,
        "skipped_call_sites": 0,
        "functions_checked": 5,
        "parameters_checked": 5,
        "missing_parameter_hints": 0,
        "missing_return_hints": 0,
        "missing_variable_hints": 0,
        "hint_coverage_percent": 100.0,
        "findings": 0,
        "blocking_findings": 0,
        "auto_fixes": 0
      },
      "categories": [
        {
          "category": "missing-kwargs",
          "label": "Missing keyword arguments",
          "severity": "error",
          "blocking": true,
          "count": 0
        },
        {
          "category": "bare-import",
          "label": "Bare imports",
          "severity": "error",
          "blocking": true,
          "count": 0
        },
        {
          "category": "missing-hint",
          "label": "Missing type hints",
          "severity": "error",
          "blocking": true,
          "count": 0
        },
        {
          "category": "parse-failure",
          "label": "Parse failures",
          "severity": "error",
          "blocking": true,
          "count": 0
        },
        {
          "category": "ambiguous-call",
          "label": "Ambiguous calls",
          "severity": "warning",
          "blocking": false,
          "count": 0
        },
        {
          "category": "unresolved-callee",
          "label": "Unresolved callees",
          "severity": "info",
          "blocking": false,
          "count": 0
        }
      ]
    },
    "unresolved_callees": [],
    "ambiguous_call_sites": [],
    "bare_imports": [],
    "auto_fixes": [],
    "methodology": [
      "Signatures come from a repository-wide AST index (functions, methods, dataclass and \`NamedTuple\` fields, imports, \`self.attr\` assignments, annotations), \`inspect.signature\` for external callables and the typeshed stubs bundled with basedpyright.",
      "Confidence of a missing-keyword finding: \`resolved\` (project index), \`constructor\` (project class constructor), \`external\` (\`inspect.signature\`), \`stub\` (typeshed), \`stub-rt\` (typeshed checked by a runtime probe), \`unique-name\` (one class defines the method), \`ambiguous-all-flag\` (every candidate flags it).",
      "Arguments after a \`*unpack\`, beyond the named parameters of a \`*args\` signature, or already passed by keyword are not reported.",
      "Calls to \`pytest.mark.*\`, standard-library positional-only methods and Qt-style \`lowerCamelCase\` methods are counted as exempt, not as unresolved.",
      "A variable needs one annotation per lexical scope; parameters own their type, walrus bindings, TypeVar declarations and Enum members are exempt, \`self\`/\`cls\` need none, and lambdas cannot be annotated.",
      "Hint coverage counts the parameters (receivers excluded) and return annotations of every function; variables are not part of the ratio.",
      "Unresolved callees (dynamic objects, \`*args\` wrappers, mocks, higher-order results) are listed so they can be checked by hand; they never fail the run.",
      "\`ARTIFACTS/heuristics.json\` holds the argument types observed by fuzzing builtin callables."
    ]
  },
  "filters": {
    "include": [],
    "exclude": [
      ".*/**",
      "**/.*/**",
      "EXACTUS_RESULTS/**",
      "**/EXACTUS_RESULTS/**",
      "node_modules/**",
      "build/**",
      "dist/**",
      "*.egg-info/**",
      "**/__pycache__/**",
      "**/.agents/**",
      "**/.build-cache/**",
      "**/.cache/**",
      "**/.claude/**",
      "**/.cursor/**",
      "**/.devin/**",
      "**/.eggs/**",
      "**/.git/**",
      "**/.history/**",
      "**/.mypy_cache/**",
      "**/.pytest_cache/**",
      "**/.ruff_cache/**",
      "**/.tox/**",
      "**/.venv/**",
      "**/build/**",
      "**/coverage_report/**",
      "**/dist/**",
      "**/env/**",
      "**/htmlcov/**",
      "**/mutants/**",
      "**/node_modules/**",
      "**/site-packages/**",
      "**/venv/**"
    ]
  },
  "findings": [],
  "fingerprint": {
    "commit": "44699a6d15abc067a4fca0d73349a1b51d916daa",
    "tree": "da1ed611a023a1100d5395906351fec79ba6db1b",
    "dirty": true,
    "python": "3.13.9",
    "ruff": "ruff 0.12.0",
    "basedpyright": "basedpyright 1.40.2"
  },
  "gate": {
    "status": "PASS",
    "reason": "No blocking findings"
  },
  "generated_at": "2026-10-31T02:56:29.358318+00:00",
  "generated_at_human": "31 October 2026, 02:56:29 UTC",
  "invocation": {
    "command": "/Users/joaolopes/Exactus/bin/release/exactus_macos_arm64/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=60276 --orchestrator-control-token=[redacted] --orchestrator-worker-port=60256 --orchestrator-worker-token=[redacted] '--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"kwargs_typehints\\",\\"module\\":\\"exactus.tools.kwargs_typehints.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/KWARGS_TYPEHINTS\\",\\"arguments\\":[],\\"run_id\\":\\"f9656595c8b74d23b2b6aec3bd0db7de:kwargs_typehints\\",\\"pipeline_run_id\\":\\"f9656595c8b74d23b2b6aec3bd0db7de\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}'",
    "cwd": "/Users/joaolopes/Exactus/exactus/tests/standalone/project",
    "arguments": [
      "exactus.tools.common.tool_worker",
      "ExactusTool",
      "--orchestrator-control-port=60276",
      "--orchestrator-control-token=[redacted]",
      "--orchestrator-worker-port=60256",
      "--orchestrator-worker-token=[redacted]",
      "--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"kwargs_typehints\\",\\"module\\":\\"exactus.tools.kwargs_typehints.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/KWARGS_TYPEHINTS\\",\\"arguments\\":[],\\"run_id\\":\\"f9656595c8b74d23b2b6aec3bd0db7de:kwargs_typehints\\",\\"pipeline_run_id\\":\\"f9656595c8b74d23b2b6aec3bd0db7de\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}"
    ]
  },
  "local_links": {
    "ARTIFACTS/heuristics.json": "ARTIFACTS/heuristics.json",
    "../../..": "../../..",
    "/Users/joaolopes/Exactus/exactus/tests/standalone/project": "../..",
    "result.md": "result.md",
    "result.json": "result.json",
    "/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/.runtime/runs.db": "../.runtime/runs.db",
    "ARTIFACTS/@activity.json": "ARTIFACTS/%40activity.json",
    "README.md": "../../README.md",
    "ARTIFACTS/README.md": "ARTIFACTS/README.md",
    "ARTIFACTS/stderr.log": "ARTIFACTS/stderr.log",
    "ARTIFACTS/stdout.log": "ARTIFACTS/stdout.log",
    "ARTIFACTS/steps.txt": "ARTIFACTS/steps.txt"
  },
  "markdown": "# Python Call, Import, and Typing Exactus\\n\\n**Run time:** 31 October 2026, 02:56:29 UTC\\n\\n## Identity\\n\\n| Field | Value |\\n|---|---|\\n| Tool | kwargs_typehints 0.5.0 |\\n| Run ID | f9656595c8b74d23b2b6aec3bd0db7de:kwargs_typehints |\\n| Pipeline run | f9656595c8b74d23b2b6aec3bd0db7de |\\n| Status | PASS |\\n| Exit code | 0 |\\n| Started | 31 October 2026, 02:56:29 UTC |\\n| Finished | 31 October 2026, 02:56:30 UTC |\\n| Duration | 1.5 s |\\n| Previous duration | 1.682s |\\n\\n## What was checked\\n\\n**Result: PASS** — 0 findings across 6 of 6 eligible targets.\\n\\n| Severity | Count |\\n|---|---:|\\n| ERROR | 0 |\\n| WARNING | 0 |\\n| INFO | 0 |\\n\\n### Metrics\\n\\n| Metric | Value |\\n| --- | --- |\\n| Python files analyzed | 6 |\\n| Files that failed to parse | 0 |\\n| Call sites with positional arguments | 3 |\\n| Call sites resolved to a signature | 3 |\\n| Resolved (%) | 100.0 |\\n| Exempt call sites (positional-only or dynamic APIs) | 0 |\\n| Unresolved call sites | 0 |\\n| Other unchecked call sites | 0 |\\n| Functions checked | 5 |\\n| Parameters checked | 5 |\\n| Signature hint coverage (%) | 100.0 |\\n| Missing variable and attribute hints | 0 |\\n| Blocking findings | 0 |\\n\\n#### Findings by category\\n\\n| Category | Severity | Blocking | Findings |\\n|---|---|---|---:|\\n| Missing keyword arguments | error | Yes | 0 |\\n| Bare imports | error | Yes | 0 |\\n| Missing type hints | error | Yes | 0 |\\n| Parse failures | error | Yes | 0 |\\n| Ambiguous calls | warning | No | 0 |\\n| Unresolved callees | info | No | 0 |\\n\\n### Change since previous report\\n\\n| Metric | Current | Previous | Delta |\\n|---|---:|---:|---:|\\n| Findings | 0 | 0 | 0 |\\n| Previous duration | 1.682s | | |\\n\\n| Finding change | Count |\\n|---|---:|\\n| Added | 0 |\\n| Resolved | 0 |\\n| Unchanged | 0 |\\n\\n#### Category findings\\n\\n| Category | Title | Findings | Previous | Delta |\\n| --- | --- | --- | --- | --- |\\n| ambiguous-call | Ambiguous calls | 0 | 0 | 0 |\\n| bare-import | Bare imports | 0 | 0 | 0 |\\n| missing-hint | Missing type hints | 0 | 0 | 0 |\\n| missing-kwargs | Missing keyword arguments | 0 | 0 | 0 |\\n| parse-failure | Parse failures | 0 | 0 | 0 |\\n| unresolved-callee | Unresolved callees | 0 | 0 | 0 |\\n\\n### Scope\\n\\n**Included**\\n\\n- \`**/*.py\`\\n\\n**Excluded**\\n\\n- \`.*/**\`\\n- \`**/.*/**\`\\n- \`EXACTUS_RESULTS/**\`\\n- \`**/EXACTUS_RESULTS/**\`\\n- \`node_modules/**\`\\n- \`build/**\`\\n- \`dist/**\`\\n- \`*.egg-info/**\`\\n- \`**/__pycache__/**\`\\n- \`**/.agents/**\`\\n- \`**/.build-cache/**\`\\n- \`**/.cache/**\`\\n- \`**/.claude/**\`\\n- \`**/.cursor/**\`\\n- \`**/.devin/**\`\\n- \`**/.eggs/**\`\\n- \`**/.git/**\`\\n- \`**/.history/**\`\\n- \`**/.mypy_cache/**\`\\n- \`**/.pytest_cache/**\`\\n- \`**/.ruff_cache/**\`\\n- \`**/.tox/**\`\\n- \`**/.venv/**\`\\n- \`**/build/**\`\\n- \`**/coverage_report/**\`\\n- \`**/dist/**\`\\n- \`**/env/**\`\\n- \`**/htmlcov/**\`\\n- \`**/mutants/**\`\\n- \`**/node_modules/**\`\\n- \`**/site-packages/**\`\\n- \`**/venv/**\`\\n\\n**Skipped targets**\\n\\nNo skipped targets.\\n\\n## Setup\\n\\n### Invocation\\n\\n~~~~shell\\n/Users/joaolopes/Exactus/bin/release/exactus_macos_arm64/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=60276 --orchestrator-control-token=[redacted] --orchestrator-worker-port=60256 --orchestrator-worker-token=[redacted] '--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"kwargs_typehints\\",\\"module\\":\\"exactus.tools.kwargs_typehints.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/KWARGS_TYPEHINTS\\",\\"arguments\\":[],\\"run_id\\":\\"f9656595c8b74d23b2b6aec3bd0db7de:kwargs_typehints\\",\\"pipeline_run_id\\":\\"f9656595c8b74d23b2b6aec3bd0db7de\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}'\\n~~~~\\n\\n| Property | Value |\\n|---|---|\\n| Working directory | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |\\n| Arguments | \`exactus.tools.common.tool_worker\` \`ExactusTool\` \`--orchestrator-control-port=60276\` \`--orchestrator-control-token=[redacted]\` \`--orchestrator-worker-port=60256\` \`--orchestrator-worker-token=[redacted]\` \`--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"kwargs_typehints\\",\\"module\\":\\"exactus.tools.kwargs_typehints.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/KWARGS_TYPEHINTS\\",\\"arguments\\":[],\\"run_id\\":\\"f9656595c8b74d23b2b6aec3bd0db7de:kwargs_typehints\\",\\"pipeline_run_id\\":\\"f9656595c8b74d23b2b6aec3bd0db7de\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}\` |\\n\\n### Environment\\n\\n| Property | Value |\\n|---|---|\\n| OS | Darwin 25.3.0 |\\n| Python | 3.13.9 |\\n| Node | v22.21.1 |\\n| CPU count | 18 |\\n\\n| Variable | Value |\\n| --- | --- |\\n| EXACTUS_ORCHESTRATED | 1 |\\n| EXACTUS_PIPELINE_RUN_ID | f9656595c8b74d23b2b6aec3bd0db7de |\\n| EXACTUS_REGISTRY | [/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/.runtime/runs.db](../.runtime/runs.db) |\\n| EXACTUS_ROOT | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |\\n| EXACTUS_RUN_ID | f9656595c8b74d23b2b6aec3bd0db7de:kwargs_typehints |\\n| EXACTUS_TOOL | kwargs_typehints |\\n| LANG | C.UTF-8 |\\n\\n## Gate\\n\\n> **Gate: PASS** — No blocking findings\\n\\nNo blocking findings.\\n\\n## Findings\\n\\nNo findings.\\n\\n## Artifacts\\n\\n| Artifact | Path | Bytes |\\n| --- | --- | --- |\\n| @activity.json | [ARTIFACTS/@activity.json](ARTIFACTS/%40activity.json) | 1867 |\\n| README.md | [ARTIFACTS/README.md](ARTIFACTS/README.md) | 460 |\\n| heuristics.json | [ARTIFACTS/heuristics.json](ARTIFACTS/heuristics.json) | 3915721 |\\n| stderr.log | [ARTIFACTS/stderr.log](ARTIFACTS/stderr.log) | 0 |\\n| stdout.log | [ARTIFACTS/stdout.log](ARTIFACTS/stdout.log) | 0 |\\n| steps.txt | [ARTIFACTS/steps.txt](ARTIFACTS/steps.txt) | 4275 |\\n\\n## Unresolved callees\\n\\nCallees with no known signature, so positional use at these call sites was not checked. Most call sites first; the Finding column names the finding with the source excerpt.\\n\\nNo unresolved callees: every checked call site resolved to a signature or is exempt.\\n\\n## Ambiguous call sites\\n\\nNo ambiguous call sites.\\n\\n## Bare imports\\n\\nNo bare imports.\\n\\n## Automatic fixes\\n\\nNo automatic source edits were applicable.\\n\\n## Methodology and caveats\\n\\n- Signatures come from a repository-wide AST index (functions, methods, dataclass and \`NamedTuple\` fields, imports, \`self.attr\` assignments, annotations), \`inspect.signature\` for external callables and the typeshed stubs bundled with basedpyright.\\n- Confidence of a missing-keyword finding: \`resolved\` (project index), \`constructor\` (project class constructor), \`external\` (\`inspect.signature\`), \`stub\` (typeshed), \`stub-rt\` (typeshed checked by a runtime probe), \`unique-name\` (one class defines the method), \`ambiguous-all-flag\` (every candidate flags it).\\n- Arguments after a \`*unpack\`, beyond the named parameters of a \`*args\` signature, or already passed by keyword are not reported.\\n- Calls to \`pytest.mark.*\`, standard-library positional-only methods and Qt-style \`lowerCamelCase\` methods are counted as exempt, not as unresolved.\\n- A variable needs one annotation per lexical scope; parameters own their type, walrus bindings, TypeVar declarations and Enum members are exempt, \`self\`/\`cls\` need none, and lambdas cannot be annotated.\\n- Hint coverage counts the parameters (receivers excluded) and return annotations of every function; variables are not part of the ratio.\\n- Unresolved callees (dynamic objects, \`*args\` wrappers, mocks, higher-order results) are listed so they can be checked by hand; they never fail the run.\\n- [\`ARTIFACTS/heuristics.json\`](ARTIFACTS/heuristics.json) holds the argument types observed by fuzzing builtin callables.\\n\\n---\\n\\nExactus · kwargs_typehints 0.5.0 · Run f9656595c8b74d23b2b6aec3bd0db7de:kwargs_typehints · Result PASS · Duration 1.5 s\\n",
  "parse_failure_files": [],
  "passed": true,
  "pipeline_run_id": "f9656595c8b74d23b2b6aec3bd0db7de",
  "previous_duration_seconds": 1.682,
  "project_href": "../../..",
  "project_root": "/Users/joaolopes/Exactus/exactus/tests/standalone/project",
  "report_bundle": {
    "markdown": "result.md",
    "json": "result.json",
    "web": "result_web"
  },
  "resume": "PASS: analyzer completed with exit status 0.",
  "root": "/Users/joaolopes/Exactus/exactus/tests/standalone/project",
  "run": {
    "id": "f9656595c8b74d23b2b6aec3bd0db7de:kwargs_typehints",
    "pipeline_id": "f9656595c8b74d23b2b6aec3bd0db7de",
    "status": "PASS",
    "exit_code": 0,
    "started_at": "2026-10-31T02:56:29.212389+00:00",
    "finished_at": "2026-10-31T02:56:30.736326+00:00",
    "at_human": "31 October 2026, 02:56:29 UTC",
    "started_at_human": "31 October 2026, 02:56:29 UTC",
    "finished_at_human": "31 October 2026, 02:56:30 UTC",
    "duration_seconds": 1.523,
    "duration_human": "1.5 s",
    "error": null
  },
  "run_at": "2026-10-31T02:56:29.212389+00:00",
  "run_at_human": "31 October 2026, 02:56:29 UTC",
  "run_id": "f9656595c8b74d23b2b6aec3bd0db7de:kwargs_typehints",
  "schema": "project-exactus-report/v1",
  "scope": {
    "include": [
      "**/*.py"
    ],
    "exclude": [
      ".*/**",
      "**/.*/**",
      "EXACTUS_RESULTS/**",
      "**/EXACTUS_RESULTS/**",
      "node_modules/**",
      "build/**",
      "dist/**",
      "*.egg-info/**",
      "**/__pycache__/**",
      "**/.agents/**",
      "**/.build-cache/**",
      "**/.cache/**",
      "**/.claude/**",
      "**/.cursor/**",
      "**/.devin/**",
      "**/.eggs/**",
      "**/.git/**",
      "**/.history/**",
      "**/.mypy_cache/**",
      "**/.pytest_cache/**",
      "**/.ruff_cache/**",
      "**/.tox/**",
      "**/.venv/**",
      "**/build/**",
      "**/coverage_report/**",
      "**/dist/**",
      "**/env/**",
      "**/htmlcov/**",
      "**/mutants/**",
      "**/node_modules/**",
      "**/site-packages/**",
      "**/venv/**"
    ],
    "skipped": []
  },
  "sections": [
    {
      "level": 1,
      "title": "Python Call, Import, and Typing Exactus"
    },
    {
      "level": 2,
      "title": "Identity"
    },
    {
      "level": 2,
      "title": "What was checked"
    },
    {
      "level": 3,
      "title": "Metrics"
    },
    {
      "level": 4,
      "title": "Findings by category"
    },
    {
      "level": 3,
      "title": "Change since previous report"
    },
    {
      "level": 4,
      "title": "Category findings"
    },
    {
      "level": 3,
      "title": "Scope"
    },
    {
      "level": 2,
      "title": "Setup"
    },
    {
      "level": 3,
      "title": "Invocation"
    },
    {
      "level": 3,
      "title": "Environment"
    },
    {
      "level": 2,
      "title": "Gate"
    },
    {
      "level": 2,
      "title": "Findings"
    },
    {
      "level": 2,
      "title": "Artifacts"
    },
    {
      "level": 2,
      "title": "Unresolved callees"
    },
    {
      "level": 2,
      "title": "Ambiguous call sites"
    },
    {
      "level": 2,
      "title": "Bare imports"
    },
    {
      "level": 2,
      "title": "Automatic fixes"
    },
    {
      "level": 2,
      "title": "Methodology and caveats"
    }
  ],
  "type_hints": [],
  "unresolved": [],
  "unresolved_sites": [],
  "view": {
    "tool": {
      "name": "kwargs_typehints",
      "display_name": "Python Call, Import, and Typing Exactus",
      "version": "0.5.0"
    },
    "run": {
      "id": "f9656595c8b74d23b2b6aec3bd0db7de:kwargs_typehints",
      "pipeline_id": "f9656595c8b74d23b2b6aec3bd0db7de",
      "status": "PASS",
      "exit_code": 0,
      "started_at": "2026-10-31T02:56:29.212389+00:00",
      "finished_at": "2026-10-31T02:56:30.736326+00:00",
      "at_human": "31 October 2026, 02:56:29 UTC",
      "started_at_human": "31 October 2026, 02:56:29 UTC",
      "finished_at_human": "31 October 2026, 02:56:30 UTC",
      "duration_seconds": 1.523,
      "duration_human": "1.5 s",
      "error": null
    },
    "previous_duration_seconds": 1.682,
    "summary": {
      "python_files": 6,
      "parse_failures": 0,
      "positional_findings": 0,
      "bare_import_findings": 0,
      "missing_type_hints": 0,
      "ambiguous_calls": 0,
      "unresolved_callees": 0,
      "unresolved_call_sites": 0,
      "call_sites": 3,
      "resolved_call_sites": 3,
      "exempt_call_sites": 0,
      "functions_checked": 5,
      "parameters_checked": 5,
      "targets_eligible": 6,
      "targets_analyzed": 6,
      "findings_total": 0,
      "auto_fixes": 0,
      "severity": {
        "error": 0,
        "warning": 0,
        "info": 0
      }
    },
    "comparison": {
      "available": true,
      "previous_generated_at": "2026-10-31T02:36:02.109043+00:00",
      "previous_run_id": "121cfe10a875424b95e7d42f9947eb9a:kwargs_typehints",
      "previous_status": "PASS",
      "previous_duration_seconds": 1.682,
      "current_total": 0,
      "previous_total": 0,
      "delta": 0,
      "added_count": 0,
      "resolved_count": 0,
      "unchanged_count": 0,
      "added": [],
      "resolved": [],
      "finding_details_available": true,
      "subsections": [],
      "categories": [
        {
          "category": "ambiguous-call",
          "title": "Ambiguous calls",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "bare-import",
          "title": "Bare imports",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "missing-hint",
          "title": "Missing type hints",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "missing-kwargs",
          "title": "Missing keyword arguments",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "parse-failure",
          "title": "Parse failures",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "unresolved-callee",
          "title": "Unresolved callees",
          "current": 0,
          "previous": 0,
          "delta": 0
        }
      ]
    },
    "gate": {
      "status": "PASS",
      "reason": "No blocking findings"
    },
    "scope": {
      "include": [
        "**/*.py"
      ],
      "exclude": [
        ".*/**",
        "**/.*/**",
        "EXACTUS_RESULTS/**",
        "**/EXACTUS_RESULTS/**",
        "node_modules/**",
        "build/**",
        "dist/**",
        "*.egg-info/**",
        "**/__pycache__/**",
        "**/.agents/**",
        "**/.build-cache/**",
        "**/.cache/**",
        "**/.claude/**",
        "**/.cursor/**",
        "**/.devin/**",
        "**/.eggs/**",
        "**/.git/**",
        "**/.history/**",
        "**/.mypy_cache/**",
        "**/.pytest_cache/**",
        "**/.ruff_cache/**",
        "**/.tox/**",
        "**/.venv/**",
        "**/build/**",
        "**/coverage_report/**",
        "**/dist/**",
        "**/env/**",
        "**/htmlcov/**",
        "**/mutants/**",
        "**/node_modules/**",
        "**/site-packages/**",
        "**/venv/**"
      ],
      "skipped": []
    },
    "invocation": {
      "command": "/Users/joaolopes/Exactus/bin/release/exactus_macos_arm64/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=60276 --orchestrator-control-token=[redacted] --orchestrator-worker-port=60256 --orchestrator-worker-token=[redacted] '--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"kwargs_typehints\\",\\"module\\":\\"exactus.tools.kwargs_typehints.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/KWARGS_TYPEHINTS\\",\\"arguments\\":[],\\"run_id\\":\\"f9656595c8b74d23b2b6aec3bd0db7de:kwargs_typehints\\",\\"pipeline_run_id\\":\\"f9656595c8b74d23b2b6aec3bd0db7de\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}'",
      "cwd": "/Users/joaolopes/Exactus/exactus/tests/standalone/project",
      "arguments": [
        "exactus.tools.common.tool_worker",
        "ExactusTool",
        "--orchestrator-control-port=60276",
        "--orchestrator-control-token=[redacted]",
        "--orchestrator-worker-port=60256",
        "--orchestrator-worker-token=[redacted]",
        "--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"kwargs_typehints\\",\\"module\\":\\"exactus.tools.kwargs_typehints.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/KWARGS_TYPEHINTS\\",\\"arguments\\":[],\\"run_id\\":\\"f9656595c8b74d23b2b6aec3bd0db7de:kwargs_typehints\\",\\"pipeline_run_id\\":\\"f9656595c8b74d23b2b6aec3bd0db7de\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}"
      ]
    },
    "environment": {
      "os": "Darwin 25.3.0",
      "python": "3.13.9",
      "node": "v22.21.1",
      "cpu_count": 18,
      "variables": [
        {
          "name": "EXACTUS_ORCHESTRATED",
          "value": "1"
        },
        {
          "name": "EXACTUS_PIPELINE_RUN_ID",
          "value": "f9656595c8b74d23b2b6aec3bd0db7de"
        },
        {
          "name": "EXACTUS_REGISTRY",
          "value": "/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/.runtime/runs.db"
        },
        {
          "name": "EXACTUS_ROOT",
          "value": "/Users/joaolopes/Exactus/exactus/tests/standalone/project"
        },
        {
          "name": "EXACTUS_RUN_ID",
          "value": "f9656595c8b74d23b2b6aec3bd0db7de:kwargs_typehints"
        },
        {
          "name": "EXACTUS_TOOL",
          "value": "kwargs_typehints"
        },
        {
          "name": "LANG",
          "value": "C.UTF-8"
        }
      ]
    },
    "findings": [],
    "blocking": [],
    "artifacts": [
      {
        "name": "@activity.json",
        "path": "ARTIFACTS/@activity.json",
        "bytes": 1867
      },
      {
        "name": "README.md",
        "path": "ARTIFACTS/README.md",
        "bytes": 460
      },
      {
        "name": "heuristics.json",
        "path": "ARTIFACTS/heuristics.json",
        "bytes": 3915721
      },
      {
        "name": "stderr.log",
        "path": "ARTIFACTS/stderr.log",
        "bytes": 0
      },
      {
        "name": "stdout.log",
        "path": "ARTIFACTS/stdout.log",
        "bytes": 0
      },
      {
        "name": "steps.txt",
        "path": "ARTIFACTS/steps.txt",
        "bytes": 4275
      }
    ],
    "extension": {
      "metrics": {
        "overview": {
          "files_scanned": 6,
          "files_analyzed": 6,
          "parse_failures": 0,
          "call_sites": 3,
          "resolved_call_sites": 3,
          "resolution_percent": 100.0,
          "exempt_call_sites": 0,
          "unresolved_call_sites": 0,
          "skipped_call_sites": 0,
          "functions_checked": 5,
          "parameters_checked": 5,
          "missing_parameter_hints": 0,
          "missing_return_hints": 0,
          "missing_variable_hints": 0,
          "hint_coverage_percent": 100.0,
          "findings": 0,
          "blocking_findings": 0,
          "auto_fixes": 0
        },
        "categories": [
          {
            "category": "missing-kwargs",
            "label": "Missing keyword arguments",
            "severity": "error",
            "blocking": true,
            "count": 0
          },
          {
            "category": "bare-import",
            "label": "Bare imports",
            "severity": "error",
            "blocking": true,
            "count": 0
          },
          {
            "category": "missing-hint",
            "label": "Missing type hints",
            "severity": "error",
            "blocking": true,
            "count": 0
          },
          {
            "category": "parse-failure",
            "label": "Parse failures",
            "severity": "error",
            "blocking": true,
            "count": 0
          },
          {
            "category": "ambiguous-call",
            "label": "Ambiguous calls",
            "severity": "warning",
            "blocking": false,
            "count": 0
          },
          {
            "category": "unresolved-callee",
            "label": "Unresolved callees",
            "severity": "info",
            "blocking": false,
            "count": 0
          }
        ]
      },
      "unresolved_callees": [],
      "ambiguous_call_sites": [],
      "bare_imports": [],
      "auto_fixes": [],
      "methodology": [
        "Signatures come from a repository-wide AST index (functions, methods, dataclass and \`NamedTuple\` fields, imports, \`self.attr\` assignments, annotations), \`inspect.signature\` for external callables and the typeshed stubs bundled with basedpyright.",
        "Confidence of a missing-keyword finding: \`resolved\` (project index), \`constructor\` (project class constructor), \`external\` (\`inspect.signature\`), \`stub\` (typeshed), \`stub-rt\` (typeshed checked by a runtime probe), \`unique-name\` (one class defines the method), \`ambiguous-all-flag\` (every candidate flags it).",
        "Arguments after a \`*unpack\`, beyond the named parameters of a \`*args\` signature, or already passed by keyword are not reported.",
        "Calls to \`pytest.mark.*\`, standard-library positional-only methods and Qt-style \`lowerCamelCase\` methods are counted as exempt, not as unresolved.",
        "A variable needs one annotation per lexical scope; parameters own their type, walrus bindings, TypeVar declarations and Enum members are exempt, \`self\`/\`cls\` need none, and lambdas cannot be annotated.",
        "Hint coverage counts the parameters (receivers excluded) and return annotations of every function; variables are not part of the ratio.",
        "Unresolved callees (dynamic objects, \`*args\` wrappers, mocks, higher-order results) are listed so they can be checked by hand; they never fail the run.",
        "\`ARTIFACTS/heuristics.json\` holds the argument types observed by fuzzing builtin callables."
      ]
    },
    "severity_levels": [
      "error",
      "warning",
      "info"
    ],
    "source_label": "Category",
    "metrics": [
      {
        "metric": "Python files analyzed",
        "value": 6
      },
      {
        "metric": "Files that failed to parse",
        "value": 0
      },
      {
        "metric": "Call sites with positional arguments",
        "value": 3
      },
      {
        "metric": "Call sites resolved to a signature",
        "value": 3
      },
      {
        "metric": "Resolved (%)",
        "value": 100.0
      },
      {
        "metric": "Exempt call sites (positional-only or dynamic APIs)",
        "value": 0
      },
      {
        "metric": "Unresolved call sites",
        "value": 0
      },
      {
        "metric": "Other unchecked call sites",
        "value": 0
      },
      {
        "metric": "Functions checked",
        "value": 5
      },
      {
        "metric": "Parameters checked",
        "value": 5
      },
      {
        "metric": "Signature hint coverage (%)",
        "value": 100.0
      },
      {
        "metric": "Missing variable and attribute hints",
        "value": 0
      },
      {
        "metric": "Blocking findings",
        "value": 0
      }
    ],
    "findings_by_category": [
      {
        "category": "Missing keyword arguments",
        "severity": "error",
        "blocking": true,
        "findings": 0
      },
      {
        "category": "Bare imports",
        "severity": "error",
        "blocking": true,
        "findings": 0
      },
      {
        "category": "Missing type hints",
        "severity": "error",
        "blocking": true,
        "findings": 0
      },
      {
        "category": "Parse failures",
        "severity": "error",
        "blocking": true,
        "findings": 0
      },
      {
        "category": "Ambiguous calls",
        "severity": "warning",
        "blocking": false,
        "findings": 0
      },
      {
        "category": "Unresolved callees",
        "severity": "info",
        "blocking": false,
        "findings": 0
      }
    ],
    "unresolved_callees": [],
    "ambiguous_call_sites": [],
    "bare_imports": [],
    "auto_fixes": [],
    "methodology_and_caveats": [
      "Signatures come from a repository-wide AST index (functions, methods, dataclass and \`NamedTuple\` fields, imports, \`self.attr\` assignments, annotations), \`inspect.signature\` for external callables and the typeshed stubs bundled with basedpyright.",
      "Confidence of a missing-keyword finding: \`resolved\` (project index), \`constructor\` (project class constructor), \`external\` (\`inspect.signature\`), \`stub\` (typeshed), \`stub-rt\` (typeshed checked by a runtime probe), \`unique-name\` (one class defines the method), \`ambiguous-all-flag\` (every candidate flags it).",
      "Arguments after a \`*unpack\`, beyond the named parameters of a \`*args\` signature, or already passed by keyword are not reported.",
      "Calls to \`pytest.mark.*\`, standard-library positional-only methods and Qt-style \`lowerCamelCase\` methods are counted as exempt, not as unresolved.",
      "A variable needs one annotation per lexical scope; parameters own their type, walrus bindings, TypeVar declarations and Enum members are exempt, \`self\`/\`cls\` need none, and lambdas cannot be annotated.",
      "Hint coverage counts the parameters (receivers excluded) and return annotations of every function; variables are not part of the ratio.",
      "Unresolved callees (dynamic objects, \`*args\` wrappers, mocks, higher-order results) are listed so they can be checked by hand; they never fail the run.",
      "\`ARTIFACTS/heuristics.json\` holds the argument types observed by fuzzing builtin callables."
    ]
  },
  "view_columns": {
    "artifacts": [
      "name",
      "path",
      "bytes"
    ],
    "metrics": [
      "metric",
      "value"
    ],
    "findings_by_category": [
      "category",
      "severity",
      "blocking",
      "findings"
    ]
  },
  "view_order": [
    "tool",
    "run",
    "previous_duration_seconds",
    "summary",
    "comparison",
    "gate",
    "scope",
    "invocation",
    "environment",
    "findings",
    "blocking",
    "artifacts",
    "extension",
    "severity_levels",
    "source_label",
    "metrics",
    "findings_by_category",
    "unresolved_callees",
    "ambiguous_call_sites",
    "bare_imports",
    "auto_fixes",
    "methodology_and_caveats"
  ],
  "web": {
    "index": "index.html",
    "css": "report.css",
    "javascript": "report.js",
    "data": "data.json"
  }
}`);
