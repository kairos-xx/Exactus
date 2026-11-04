window.__REPORT_DATA__ = JSON.parse(`{
  "title": "Lint Exactus",
  "status": "PASS",
  "tool": {
    "name": "lints",
    "display_name": "Lint Exactus",
    "version": "0.7.1"
  },
  "summary": {
    "timing": {
      "date_time": "04/11/2026 12:36:25",
      "finished_date_time": "04/11/2026 12:36:29",
      "timezone": "WET",
      "duration_seconds": 4.473163,
      "duration_human": "00:00:04.473163"
    },
    "host": {
      "hostname": "Mac",
      "operating_system": "Darwin",
      "platform": "macOS-26.3.2-arm64-arm-64bit-Mach-O",
      "architecture": "arm64",
      "python_version": "3.13.9"
    },
    "analysis": {
      "working_directory": "/Users/joaolopes/Exactus/exactus/tests/standalone/project",
      "output_file": "/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/LINTS/LINTS.json",
      "targets": [
        "."
      ],
      "ignore_patterns": [
        ".*/**",
        "**/.*/**",
        "**/__pycache__/**",
        "**/build/**",
        "**/coverage_report/**",
        "**/dist/**",
        "**/env/**",
        "**/htmlcov/**",
        "**/mutants/**",
        "**/node_modules/**",
        "**/site-packages/**",
        "**/venv/**",
        "*.egg-info/**",
        "*.dist-info/**",
        "EXACTUS_RESULTS/**",
        "**/EXACTUS_RESULTS/**",
        "EXACTUS_RESULTS",
        "EXACTUS_RESULTS/**"
      ],
      "files": {
        "python": 6,
        "javascript_jsx": 2,
        "css": 1,
        "html": 1,
        "unique_analyzed": 10,
        "with_findings": 0
      },
      "files_with_issues": [],
      "findings": {
        "total": 0,
        "errors": 0,
        "warnings": 0,
        "information": 0,
        "unique_rules": 0,
        "affected_files": 0
      }
    },
    "tools": {
      "configured": 17,
      "executed": 17,
      "names": [
        "custom_compliance",
        "custom_shebang",
        "custom_python",
        "custom_python_long_lines",
        "custom_javascript",
        "custom_javascript_delimiters",
        "custom_javascript_notation",
        "custom_css",
        "custom_html",
        "ruff",
        "ruff_docs",
        "basedpyright",
        "pyrefly",
        "eslint",
        "typescript",
        "stylelint",
        "htmlhint"
      ]
    },
    "clean": true,
    "targets_eligible": 10,
    "targets_analyzed": 10,
    "findings_total": 0,
    "severity": {}
  },
  "all_lints": {
    "schema_version": 2,
    "generated_at": "2026-11-04T12:36:28.332799+00:00",
    "started_at": "2026-11-04T12:36:26.124680+00:00",
    "duration_seconds": 2.208087,
    "root": "/Users/joaolopes/Exactus/exactus/tests/standalone/project",
    "ok": true,
    "summary": {
      "tools": 9,
      "passed": 8,
      "failed": 0,
      "unavailable": 1,
      "optional_unavailable": 1,
      "files": 40,
      "files_with_issues": 0,
      "errors": 0,
      "warnings": 0,
      "diagnostics": 0
    },
    "tools": {
      "ruff": {
        "name": "ruff",
        "status": "passed",
        "duration_seconds": 0.071641,
        "total_files": 6,
        "completed_files": 6,
        "files_with_issues": 0,
        "diagnostics": [],
        "files": []
      },
      "refurb": {
        "name": "refurb",
        "status": "unavailable",
        "duration_seconds": 0.0,
        "total_files": 6,
        "completed_files": 6,
        "files_with_issues": 0,
        "diagnostics": [],
        "files": []
      },
      "ruff_docs": {
        "name": "ruff_docs",
        "status": "passed",
        "duration_seconds": 0.071641,
        "total_files": 6,
        "completed_files": 6,
        "files_with_issues": 0,
        "diagnostics": [],
        "files": []
      },
      "basedpyright": {
        "name": "basedpyright",
        "status": "passed",
        "duration_seconds": 1.661184,
        "total_files": 6,
        "completed_files": 6,
        "files_with_issues": 0,
        "diagnostics": [],
        "files": []
      },
      "pyrefly": {
        "name": "pyrefly",
        "status": "passed",
        "duration_seconds": 0.390393,
        "total_files": 6,
        "completed_files": 6,
        "files_with_issues": 0,
        "diagnostics": [],
        "files": []
      },
      "eslint": {
        "name": "eslint",
        "status": "passed",
        "duration_seconds": 1.150793,
        "total_files": 4,
        "completed_files": 4,
        "files_with_issues": 0,
        "diagnostics": [],
        "files": []
      },
      "stylelint": {
        "name": "stylelint",
        "status": "passed",
        "duration_seconds": 1.200203,
        "total_files": 1,
        "completed_files": 1,
        "files_with_issues": 0,
        "diagnostics": [],
        "files": []
      },
      "htmlint": {
        "name": "htmlint",
        "status": "passed",
        "duration_seconds": 0.187376,
        "total_files": 1,
        "completed_files": 1,
        "files_with_issues": 0,
        "diagnostics": [],
        "files": []
      },
      "typescript": {
        "name": "typescript",
        "status": "passed",
        "duration_seconds": 2.145754,
        "total_files": 4,
        "completed_files": 4,
        "files_with_issues": 0,
        "diagnostics": [],
        "files": []
      }
    },
    "diagnostics": []
  },
  "analyzer": "lints",
  "artifacts": [
    {
      "name": "@activity.json",
      "path": "ARTIFACTS/@activity.json",
      "bytes": 2797
    },
    {
      "name": "README.md",
      "path": "ARTIFACTS/README.md",
      "bytes": 450
    },
    {
      "name": "stderr.log",
      "path": "ARTIFACTS/stderr.log",
      "bytes": 0
    },
    {
      "name": "stdout.log",
      "path": "ARTIFACTS/stdout.log",
      "bytes": 433
    },
    {
      "name": "steps.txt",
      "path": "ARTIFACTS/steps.txt",
      "bytes": 69010
    }
  ],
  "comparison": {
    "available": true,
    "previous_generated_at": "2026-11-04T11:55:43.411354+00:00",
    "previous_run_id": "4f11bb392321406fba06a95f800a8d2a:lints",
    "previous_status": "PASS",
    "previous_duration_seconds": 17.682,
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
        "category": "CMP000",
        "title": "Module does not parse",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "CMP001",
        "title": "Suppression marker",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "CMP002",
        "title": "typing.Any usage",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "CMP003",
        "title": "object annotation",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "CMP004",
        "title": "Lint ignore configuration",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "CMP005",
        "title": "Type-check suppression",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "CMP006",
        "title": "pyproject.toml missing",
        "current": 0,
        "previous": 0,
        "delta": 0
      }
    ]
  },
  "duration_seconds": 11.381,
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
        "value": "aa9f5f9f35a74d85857a1b2dfecca441"
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
        "value": "aa9f5f9f35a74d85857a1b2dfecca441:lints"
      },
      {
        "name": "EXACTUS_TOOL",
        "value": "lints"
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
        "linters_run": 17,
        "linters_unavailable": 0,
        "files_analyzed": 10,
        "files_with_findings": 0,
        "rules_triggered": 0,
        "findings": 0
      },
      "linters": [
        {
          "linter": "custom_compliance",
          "status": "ran",
          "version": "built-in",
          "files": 6,
          "findings": 0,
          "errors": 0,
          "warnings": 0,
          "information": 0,
          "exit_code": 0,
          "duration_seconds": 0.0012783330166712403
        },
        {
          "linter": "custom_shebang",
          "status": "ran",
          "version": "built-in",
          "files": 6,
          "findings": 0,
          "errors": 0,
          "warnings": 0,
          "information": 0,
          "exit_code": 0,
          "duration_seconds": 0.003667250042781234
        },
        {
          "linter": "custom_python",
          "status": "ran",
          "version": "built-in",
          "files": 6,
          "findings": 0,
          "errors": 0,
          "warnings": 0,
          "information": 0,
          "exit_code": 0,
          "duration_seconds": 0.006
        },
        {
          "linter": "custom_python_long_lines",
          "status": "ran",
          "version": "built-in",
          "files": 6,
          "findings": 0,
          "errors": 0,
          "warnings": 0,
          "information": 0,
          "exit_code": 0,
          "duration_seconds": 5.5917014833539724e-05
        },
        {
          "linter": "custom_javascript",
          "status": "ran",
          "version": "built-in",
          "files": 2,
          "findings": 0,
          "errors": 0,
          "warnings": 0,
          "information": 0,
          "exit_code": 0,
          "duration_seconds": 0.0
        },
        {
          "linter": "custom_javascript_delimiters",
          "status": "ran",
          "version": "built-in",
          "files": 2,
          "findings": 0,
          "errors": 0,
          "warnings": 0,
          "information": 0,
          "exit_code": 0,
          "duration_seconds": 0.0002464170102030039
        },
        {
          "linter": "custom_javascript_notation",
          "status": "ran",
          "version": "built-in",
          "files": 2,
          "findings": 0,
          "errors": 0,
          "warnings": 0,
          "information": 0,
          "exit_code": 0,
          "duration_seconds": 3.6999990697950125e-05
        },
        {
          "linter": "custom_css",
          "status": "ran",
          "version": "built-in",
          "files": 1,
          "findings": 0,
          "errors": 0,
          "warnings": 0,
          "information": 0,
          "exit_code": 0,
          "duration_seconds": 0.003
        },
        {
          "linter": "custom_html",
          "status": "ran",
          "version": "built-in",
          "files": 1,
          "findings": 0,
          "errors": 0,
          "warnings": 0,
          "information": 0,
          "exit_code": 0,
          "duration_seconds": 0.0
        },
        {
          "linter": "ruff",
          "status": "ran",
          "version": "0.15.22",
          "files": 6,
          "findings": 0,
          "errors": 0,
          "warnings": 0,
          "information": 0,
          "exit_code": 0,
          "duration_seconds": 0.071641
        },
        {
          "linter": "ruff_docs",
          "status": "ran",
          "version": "0.15.22",
          "files": 6,
          "findings": 0,
          "errors": 0,
          "warnings": 0,
          "information": 0,
          "exit_code": 0,
          "duration_seconds": 0.071641
        },
        {
          "linter": "basedpyright",
          "status": "ran",
          "version": "1.40.2",
          "files": 6,
          "findings": 0,
          "errors": 0,
          "warnings": 0,
          "information": 0,
          "exit_code": 0,
          "duration_seconds": 1.661184
        },
        {
          "linter": "pyrefly",
          "status": "ran",
          "version": "0.63.0",
          "files": 6,
          "findings": 0,
          "errors": 0,
          "warnings": 0,
          "information": 0,
          "exit_code": 0,
          "duration_seconds": 0.276
        },
        {
          "linter": "eslint",
          "status": "ran",
          "version": "10.14.0",
          "files": 2,
          "findings": 0,
          "errors": 0,
          "warnings": 0,
          "information": 0,
          "exit_code": 0,
          "duration_seconds": 1.150793
        },
        {
          "linter": "typescript",
          "status": "ran",
          "version": "6.0.3",
          "files": 2,
          "findings": 0,
          "errors": 0,
          "warnings": 0,
          "information": 0,
          "exit_code": 0,
          "duration_seconds": 2.145754
        },
        {
          "linter": "stylelint",
          "status": "ran",
          "version": "17.16.0",
          "files": 1,
          "findings": 0,
          "errors": 0,
          "warnings": 0,
          "information": 0,
          "exit_code": 0,
          "duration_seconds": 1.200203
        },
        {
          "linter": "htmlhint",
          "status": "ran",
          "version": "1.9.2",
          "files": 1,
          "findings": 0,
          "errors": 0,
          "warnings": 0,
          "information": 0,
          "exit_code": 0,
          "duration_seconds": 0.187376
        }
      ],
      "top_rules": [],
      "top_files": [],
      "severity_by_linter": []
    },
    "rules": [
      {
        "rule": "CMP000",
        "title": "Module does not parse",
        "category": "Parsing",
        "count": 0
      },
      {
        "rule": "CMP001",
        "title": "Suppression marker",
        "category": "Suppression",
        "count": 0
      },
      {
        "rule": "CMP002",
        "title": "typing.Any usage",
        "category": "Typing",
        "count": 0
      },
      {
        "rule": "CMP003",
        "title": "object annotation",
        "category": "Typing",
        "count": 0
      },
      {
        "rule": "CMP004",
        "title": "Lint ignore configuration",
        "category": "Configuration",
        "count": 0
      },
      {
        "rule": "CMP005",
        "title": "Type-check suppression",
        "category": "Configuration",
        "count": 0
      },
      {
        "rule": "CMP006",
        "title": "pyproject.toml missing",
        "category": "Configuration",
        "count": 0
      }
    ]
  },
  "findings": [],
  "fingerprint": {
    "commit": "ce47630806edce94544dfaacf41b56473c05c3f7",
    "tree": "c1f5559cd1439149d0c11b1e214b6b7d96a57f7a",
    "dirty": true,
    "python": "3.13.9",
    "ruff": "ruff 0.12.0",
    "basedpyright": "basedpyright 1.40.2"
  },
  "gate": {
    "status": "PASS",
    "reason": "No blocking findings"
  },
  "generated_at": "2026-11-04T12:36:29.837674+00:00",
  "generated_at_human": "04 November 2026, 12:36:29 UTC",
  "group_final": {
    "files": 6,
    "planned": 0,
    "constants": 0,
    "changed": 0,
    "dry_run": true
  },
  "invocation": {
    "command": "/Users/joaolopes/Exactus/bin/release/exactus_macos_arm64/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=57183 --orchestrator-control-token=[redacted] --orchestrator-worker-port=57173 --orchestrator-worker-token=[redacted] '--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"lints\\",\\"module\\":\\"exactus.tools.lints.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/LINTS\\",\\"arguments\\":[],\\"explicit_arguments\\":[],\\"run_id\\":\\"aa9f5f9f35a74d85857a1b2dfecca441:lints\\",\\"pipeline_run_id\\":\\"aa9f5f9f35a74d85857a1b2dfecca441\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}'",
    "cwd": "/Users/joaolopes/Exactus/exactus/tests/standalone/project",
    "arguments": [
      "exactus.tools.common.tool_worker",
      "ExactusTool",
      "--orchestrator-control-port=57183",
      "--orchestrator-control-token=[redacted]",
      "--orchestrator-worker-port=57173",
      "--orchestrator-worker-token=[redacted]",
      "--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"lints\\",\\"module\\":\\"exactus.tools.lints.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/LINTS\\",\\"arguments\\":[],\\"explicit_arguments\\":[],\\"run_id\\":\\"aa9f5f9f35a74d85857a1b2dfecca441:lints\\",\\"pipeline_run_id\\":\\"aa9f5f9f35a74d85857a1b2dfecca441\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}"
    ]
  },
  "local_links": {
    "/Users/joaolopes/Exactus/exactus/tests/standalone/project": "../..",
    "../../..": "../../..",
    "result.md": "result.md",
    "result.json": "result.json",
    "/Users/joaolopes/Exactus/.venv/bin/ruff": "../../../../../../.venv/bin/ruff",
    "__init__.py": "../../__init__.py",
    "conftest.py": "../../conftest.py",
    "python/__init__.py": "../../python/__init__.py",
    "python/calc.py": "../../python/calc.py",
    "tests/__init__.py": "../../tests/__init__.py",
    "tests/test_calc.py": "../../tests/test_calc.py",
    "/Users/joaolopes/Exactus/.venv/bin/basedpyright": "../../../../../../.venv/bin/basedpyright",
    "/opt/anaconda3/bin/pyrefly": "../../../../../../../../../opt/anaconda3/bin/pyrefly",
    "/Users/joaolopes/Exactus/.venv/bin/python": "../../../../../../.venv/bin/python",
    "/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/eslint": "../../../../../../../.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/eslint",
    "tests/code.test.mjs": "../../tests/code.test.mjs",
    "web/code.js": "../../web/code.js",
    "/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/stylelint": "../../../../../../../.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/stylelint",
    "web/style.css": "../../web/style.css",
    "/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/htmlhint": "../../../../../../../.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/htmlhint",
    "web/index.html": "../../web/index.html",
    "/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/tsc": "../../../../../../../.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/tsc",
    "/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/.runtime/runs.db": "../.runtime/runs.db",
    "ARTIFACTS/@activity.json": "ARTIFACTS/%40activity.json",
    "README.md": "../../README.md",
    "ARTIFACTS/README.md": "ARTIFACTS/README.md",
    "ARTIFACTS/stderr.log": "ARTIFACTS/stderr.log",
    "ARTIFACTS/stdout.log": "ARTIFACTS/stdout.log",
    "ARTIFACTS/steps.txt": "ARTIFACTS/steps.txt"
  },
  "markdown": "# Lint Exactus\\n\\n**Run time:** 04 November 2026, 12:36:19 UTC\\n\\n## Identity\\n\\n| Field | Value |\\n|---|---|\\n| Tool | lints 0.7.1 |\\n| Run ID | aa9f5f9f35a74d85857a1b2dfecca441:lints |\\n| Pipeline run | aa9f5f9f35a74d85857a1b2dfecca441 |\\n| Status | PASS |\\n| Exit code | 0 |\\n| Started | 04 November 2026, 12:36:19 UTC |\\n| Finished | 04 November 2026, 12:36:30 UTC |\\n| Duration | 11.4 s |\\n| Previous duration | 17.682s |\\n\\n## What was checked\\n\\n**Result: PASS** — 0 findings across 10 of 10 eligible targets.\\n\\n| Severity | Count |\\n|---|---:|\\n| ERROR | 0 |\\n| WARNING | 0 |\\n| INFORMATION | 0 |\\n\\n### Change since previous report\\n\\n| Metric | Current | Previous | Delta |\\n|---|---:|---:|---:|\\n| Findings | 0 | 0 | 0 |\\n| Previous duration | 17.682s | | |\\n\\n| Finding change | Count |\\n|---|---:|\\n| Added | 0 |\\n| Resolved | 0 |\\n| Unchanged | 0 |\\n\\n#### Category findings\\n\\n| Category | Title | Findings | Previous | Delta |\\n| --- | --- | --- | --- | --- |\\n| CMP000 | Module does not parse | 0 | 0 | 0 |\\n| CMP001 | Suppression marker | 0 | 0 | 0 |\\n| CMP002 | typing.Any usage | 0 | 0 | 0 |\\n| CMP003 | object annotation | 0 | 0 | 0 |\\n| CMP004 | Lint ignore configuration | 0 | 0 | 0 |\\n| CMP005 | Type-check suppression | 0 | 0 | 0 |\\n| CMP006 | pyproject.toml missing | 0 | 0 | 0 |\\n\\n### Scope\\n\\n**Included**\\n\\n- \`.\`\\n\\n**Excluded**\\n\\n- \`.*/**\`\\n- \`**/.*/**\`\\n- \`**/__pycache__/**\`\\n- \`**/build/**\`\\n- \`**/coverage_report/**\`\\n- \`**/dist/**\`\\n- \`**/env/**\`\\n- \`**/htmlcov/**\`\\n- \`**/mutants/**\`\\n- \`**/node_modules/**\`\\n- \`**/site-packages/**\`\\n- \`**/venv/**\`\\n- \`*.egg-info/**\`\\n- \`*.dist-info/**\`\\n- \`EXACTUS_RESULTS/**\`\\n- \`**/EXACTUS_RESULTS/**\`\\n- \`EXACTUS_RESULTS\`\\n- \`EXACTUS_RESULTS/**\`\\n\\n**Skipped targets**\\n\\nNo skipped targets.\\n\\n## Setup\\n\\n### Invocation\\n\\n~~~~shell\\n/Users/joaolopes/Exactus/bin/release/exactus_macos_arm64/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=57183 --orchestrator-control-token=[redacted] --orchestrator-worker-port=57173 --orchestrator-worker-token=[redacted] '--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"lints\\",\\"module\\":\\"exactus.tools.lints.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/LINTS\\",\\"arguments\\":[],\\"explicit_arguments\\":[],\\"run_id\\":\\"aa9f5f9f35a74d85857a1b2dfecca441:lints\\",\\"pipeline_run_id\\":\\"aa9f5f9f35a74d85857a1b2dfecca441\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}'\\n~~~~\\n\\n| Property | Value |\\n|---|---|\\n| Working directory | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |\\n| Arguments | \`exactus.tools.common.tool_worker\` \`ExactusTool\` \`--orchestrator-control-port=57183\` \`--orchestrator-control-token=[redacted]\` \`--orchestrator-worker-port=57173\` \`--orchestrator-worker-token=[redacted]\` \`--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"lints\\",\\"module\\":\\"exactus.tools.lints.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/LINTS\\",\\"arguments\\":[],\\"explicit_arguments\\":[],\\"run_id\\":\\"aa9f5f9f35a74d85857a1b2dfecca441:lints\\",\\"pipeline_run_id\\":\\"aa9f5f9f35a74d85857a1b2dfecca441\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}\` |\\n\\n### Environment\\n\\n| Property | Value |\\n|---|---|\\n| OS | Darwin 25.3.0 |\\n| Python | 3.13.9 |\\n| Node | v22.21.1 |\\n| CPU count | 18 |\\n\\n| Variable | Value |\\n| --- | --- |\\n| EXACTUS_ORCHESTRATED | 1 |\\n| EXACTUS_PIPELINE_RUN_ID | aa9f5f9f35a74d85857a1b2dfecca441 |\\n| EXACTUS_REGISTRY | [/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/.runtime/runs.db](../.runtime/runs.db) |\\n| EXACTUS_ROOT | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |\\n| EXACTUS_RUN_ID | aa9f5f9f35a74d85857a1b2dfecca441:lints |\\n| EXACTUS_TOOL | lints |\\n| LANG | C.UTF-8 |\\n\\n## Gate\\n\\n> **Gate: PASS** — No blocking findings\\n\\nNo blocking findings.\\n\\n## Findings\\n\\nNo findings.\\n\\n## Artifacts\\n\\n| Artifact | Path | Bytes |\\n| --- | --- | --- |\\n| @activity.json | [ARTIFACTS/@activity.json](ARTIFACTS/%40activity.json) | 2797 |\\n| README.md | [ARTIFACTS/README.md](ARTIFACTS/README.md) | 450 |\\n| stderr.log | [ARTIFACTS/stderr.log](ARTIFACTS/stderr.log) | 0 |\\n| stdout.log | [ARTIFACTS/stdout.log](ARTIFACTS/stdout.log) | 433 |\\n| steps.txt | [ARTIFACTS/steps.txt](ARTIFACTS/steps.txt) | 69010 |\\n\\n## Integrated stages\\n\\n### group_final\\n\\n| Files scanned | Modules planned | Constants moved | Files changed | Dry run |\\n|---:|---:|---:|---:|---|\\n| 6 | 0 | 0 | 0 | True |\\n\\n### all_lints\\n\\n| Tools | Passed | Failed | Unavailable | File checks | Diagnostics |\\n|---:|---:|---:|---:|---:|---:|\\n| 9 | 8 | 0 | 1 | 40 | 0 |\\n\\n## Rules\\n\\n| Rule | Title | Category | Findings |\\n| --- | --- | --- | --- |\\n| CMP000 | Module does not parse | Parsing | 0 |\\n| CMP001 | Suppression marker | Suppression | 0 |\\n| CMP002 | typing.Any usage | Typing | 0 |\\n| CMP003 | object annotation | Typing | 0 |\\n| CMP004 | Lint ignore configuration | Configuration | 0 |\\n| CMP005 | Type-check suppression | Configuration | 0 |\\n| CMP006 | pyproject.toml missing | Configuration | 0 |\\n\\n\\n## Lint metrics\\n\\n| Metric | Value |\\n| --- | --- |\\n| Linters run | 17 |\\n| Linters unavailable | 0 |\\n| Files analyzed | 10 |\\n| Files with findings | 0 |\\n| Rules triggered | 0 |\\n| Findings | 0 |\\n\\n### Linters\\n\\n| Linter | Status | Version | Files | Findings | Errors | Warnings | Information | Exit code | Duration (s) |\\n|---|---|---|---:|---:|---:|---:|---:|---:|---:|\\n| custom_compliance | ran | built-in | 6 | 0 | 0 | 0 | 0 | 0 | 0.0012783330166712403 |\\n| custom_shebang | ran | built-in | 6 | 0 | 0 | 0 | 0 | 0 | 0.003667250042781234 |\\n| custom_python | ran | built-in | 6 | 0 | 0 | 0 | 0 | 0 | 0.006 |\\n| custom_python_long_lines | ran | built-in | 6 | 0 | 0 | 0 | 0 | 0 | 5.5917014833539724e-05 |\\n| custom_javascript | ran | built-in | 2 | 0 | 0 | 0 | 0 | 0 | 0.0 |\\n| custom_javascript_delimiters | ran | built-in | 2 | 0 | 0 | 0 | 0 | 0 | 0.0002464170102030039 |\\n| custom_javascript_notation | ran | built-in | 2 | 0 | 0 | 0 | 0 | 0 | 3.6999990697950125e-05 |\\n| custom_css | ran | built-in | 1 | 0 | 0 | 0 | 0 | 0 | 0.003 |\\n| custom_html | ran | built-in | 1 | 0 | 0 | 0 | 0 | 0 | 0.0 |\\n| ruff | ran | 0.15.22 | 6 | 0 | 0 | 0 | 0 | 0 | 0.071641 |\\n| ruff_docs | ran | 0.15.22 | 6 | 0 | 0 | 0 | 0 | 0 | 0.071641 |\\n| basedpyright | ran | 1.40.2 | 6 | 0 | 0 | 0 | 0 | 0 | 1.661184 |\\n| pyrefly | ran | 0.63.0 | 6 | 0 | 0 | 0 | 0 | 0 | 0.276 |\\n| eslint | ran | 10.14.0 | 2 | 0 | 0 | 0 | 0 | 0 | 1.150793 |\\n| typescript | ran | 6.0.3 | 2 | 0 | 0 | 0 | 0 | 0 | 2.145754 |\\n| stylelint | ran | 17.16.0 | 1 | 0 | 0 | 0 | 0 | 0 | 1.200203 |\\n| htmlhint | ran | 1.9.2 | 1 | 0 | 0 | 0 | 0 | 0 | 0.187376 |\\n\\n### Top rules\\n\\nN/A — no rule reported a finding.\\n\\n### Files with the most findings\\n\\nN/A — no file has a finding.\\n\\n---\\n\\nExactus · lints 0.7.1 · Run aa9f5f9f35a74d85857a1b2dfecca441:lints · Result PASS · Duration 11.4 s\\n",
  "organize": {
    "files": 8,
    "python_files": 6,
    "javascript_files": 2,
    "changed": 0,
    "skipped": 0,
    "classes_seen": 1,
    "classes_reordered": 0,
    "methods_seen": 0,
    "methods_moved": 0,
    "lines_moved": 0,
    "dry_run": true
  },
  "passed": true,
  "pipeline_run_id": "aa9f5f9f35a74d85857a1b2dfecca441",
  "previous_duration_seconds": 17.682,
  "project_href": "../../..",
  "project_root": "/Users/joaolopes/Exactus/exactus/tests/standalone/project",
  "report_bundle": {
    "markdown": "result.md",
    "json": "result.json",
    "web": "result_web"
  },
  "resume": "PASS: analyzer completed with exit status 0.",
  "run": {
    "id": "aa9f5f9f35a74d85857a1b2dfecca441:lints",
    "pipeline_id": "aa9f5f9f35a74d85857a1b2dfecca441",
    "status": "PASS",
    "exit_code": 0,
    "started_at": "2026-11-04T12:36:19.565434+00:00",
    "finished_at": "2026-11-04T12:36:30.950103+00:00",
    "at_human": "04 November 2026, 12:36:19 UTC",
    "started_at_human": "04 November 2026, 12:36:19 UTC",
    "finished_at_human": "04 November 2026, 12:36:30 UTC",
    "duration_seconds": 11.381,
    "duration_human": "11.4 s",
    "error": null
  },
  "run_at": "2026-11-04T12:36:19.565434+00:00",
  "run_at_human": "04 November 2026, 12:36:19 UTC",
  "run_id": "aa9f5f9f35a74d85857a1b2dfecca441:lints",
  "schema": "project-exactus-report/v1",
  "scope": {
    "include": [
      "."
    ],
    "exclude": [
      ".*/**",
      "**/.*/**",
      "**/__pycache__/**",
      "**/build/**",
      "**/coverage_report/**",
      "**/dist/**",
      "**/env/**",
      "**/htmlcov/**",
      "**/mutants/**",
      "**/node_modules/**",
      "**/site-packages/**",
      "**/venv/**",
      "*.egg-info/**",
      "*.dist-info/**",
      "EXACTUS_RESULTS/**",
      "**/EXACTUS_RESULTS/**",
      "EXACTUS_RESULTS",
      "EXACTUS_RESULTS/**"
    ],
    "skipped": []
  },
  "sections": [
    {
      "level": 1,
      "title": "Lint Exactus"
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
      "title": "Integrated stages"
    },
    {
      "level": 3,
      "title": "group_final"
    },
    {
      "level": 3,
      "title": "all_lints"
    },
    {
      "level": 2,
      "title": "Rules"
    },
    {
      "level": 2,
      "title": "Lint metrics"
    },
    {
      "level": 3,
      "title": "Linters"
    },
    {
      "level": 3,
      "title": "Top rules"
    },
    {
      "level": 3,
      "title": "Files with the most findings"
    }
  ],
  "tools": {
    "custom_shebang": {
      "returncode": 0,
      "count": 0,
      "version": "built-in",
      "files": 6,
      "duration_seconds": 0.003667250042781234,
      "findings": [],
      "healed": [],
      "skipped_files": []
    },
    "custom_python": {
      "tool": "custom_python",
      "command": [],
      "returncode": 0,
      "stderr": "",
      "count": 0,
      "findings": [],
      "duration_seconds": 0.006
    },
    "custom_javascript_delimiters": {
      "returncode": 0,
      "count": 0,
      "version": "built-in",
      "files": 2,
      "duration_seconds": 0.0002464170102030039,
      "findings": [],
      "healed": []
    },
    "custom_javascript_notation": {
      "returncode": 0,
      "count": 0,
      "version": "built-in",
      "files": 2,
      "duration_seconds": 3.6999990697950125e-05,
      "findings": [],
      "healed": []
    },
    "custom_javascript": {
      "tool": "custom_javascript",
      "command": [],
      "returncode": 0,
      "stderr": "",
      "count": 0,
      "findings": [],
      "duration_seconds": 0.0
    },
    "custom_css": {
      "tool": "custom_css",
      "command": [],
      "returncode": 0,
      "stderr": "",
      "count": 0,
      "findings": [],
      "duration_seconds": 0.003
    },
    "custom_html": {
      "tool": "custom_html",
      "command": [],
      "returncode": 0,
      "stderr": "",
      "count": 0,
      "findings": [],
      "duration_seconds": 0.0
    },
    "custom_python_simplify": {
      "returncode": 0,
      "count": 0,
      "files": 6,
      "version": "built-in",
      "findings": [],
      "proposals": 0,
      "skipped": 0,
      "healed": 0
    },
    "ruff": {
      "tool": "ruff",
      "command": [
        "/Users/joaolopes/Exactus/.venv/bin/ruff",
        "check",
        "--select",
        "ALL",
        "--ignore",
        "D203,D213",
        "--output-format",
        "json",
        "__init__.py"
      ],
      "commands": [
        [
          "/Users/joaolopes/Exactus/.venv/bin/ruff",
          "check",
          "--select",
          "ALL",
          "--ignore",
          "D203,D213",
          "--output-format",
          "json",
          "__init__.py"
        ],
        [
          "/Users/joaolopes/Exactus/.venv/bin/ruff",
          "check",
          "--select",
          "ALL",
          "--ignore",
          "D203,D213",
          "--output-format",
          "json",
          "conftest.py"
        ],
        [
          "/Users/joaolopes/Exactus/.venv/bin/ruff",
          "check",
          "--select",
          "ALL",
          "--ignore",
          "D203,D213",
          "--output-format",
          "json",
          "python/__init__.py"
        ],
        [
          "/Users/joaolopes/Exactus/.venv/bin/ruff",
          "check",
          "--select",
          "ALL",
          "--ignore",
          "D203,D213",
          "--output-format",
          "json",
          "python/calc.py"
        ],
        [
          "/Users/joaolopes/Exactus/.venv/bin/ruff",
          "check",
          "--select",
          "ALL",
          "--ignore",
          "D203,D213",
          "--output-format",
          "json",
          "tests/__init__.py"
        ],
        [
          "/Users/joaolopes/Exactus/.venv/bin/ruff",
          "check",
          "--select",
          "ALL",
          "--ignore",
          "D203,D213",
          "--output-format",
          "json",
          "tests/test_calc.py"
        ]
      ],
      "files": [
        "__init__.py",
        "conftest.py",
        "python/__init__.py",
        "python/calc.py",
        "tests/__init__.py",
        "tests/test_calc.py"
      ],
      "invocations": 6,
      "returncode": 0,
      "stderr": "",
      "count": 0,
      "findings": [],
      "skipped": false,
      "skipped_files": [],
      "duration_seconds": 0.071641,
      "files_checked": 6,
      "version": "0.15.22"
    },
    "refurb": {
      "tool": "refurb",
      "command": [],
      "commands": [],
      "files": [],
      "invocations": 0,
      "returncode": 1,
      "stderr": "refurb is not installed.",
      "count": 0,
      "findings": [],
      "skipped": true,
      "skipped_files": [],
      "duration_seconds": 0.0,
      "files_checked": 6
    },
    "ruff_docs": {
      "tool": "ruff_docs",
      "command": [
        "/Users/joaolopes/Exactus/.venv/bin/ruff",
        "check",
        "--select",
        "ALL",
        "--ignore",
        "D203,D213",
        "--output-format",
        "json",
        "__init__.py"
      ],
      "commands": [
        [
          "/Users/joaolopes/Exactus/.venv/bin/ruff",
          "check",
          "--select",
          "ALL",
          "--ignore",
          "D203,D213",
          "--output-format",
          "json",
          "__init__.py"
        ],
        [
          "/Users/joaolopes/Exactus/.venv/bin/ruff",
          "check",
          "--select",
          "ALL",
          "--ignore",
          "D203,D213",
          "--output-format",
          "json",
          "conftest.py"
        ],
        [
          "/Users/joaolopes/Exactus/.venv/bin/ruff",
          "check",
          "--select",
          "ALL",
          "--ignore",
          "D203,D213",
          "--output-format",
          "json",
          "python/__init__.py"
        ],
        [
          "/Users/joaolopes/Exactus/.venv/bin/ruff",
          "check",
          "--select",
          "ALL",
          "--ignore",
          "D203,D213",
          "--output-format",
          "json",
          "python/calc.py"
        ],
        [
          "/Users/joaolopes/Exactus/.venv/bin/ruff",
          "check",
          "--select",
          "ALL",
          "--ignore",
          "D203,D213",
          "--output-format",
          "json",
          "tests/__init__.py"
        ],
        [
          "/Users/joaolopes/Exactus/.venv/bin/ruff",
          "check",
          "--select",
          "ALL",
          "--ignore",
          "D203,D213",
          "--output-format",
          "json",
          "tests/test_calc.py"
        ]
      ],
      "files": [
        "__init__.py",
        "conftest.py",
        "python/__init__.py",
        "python/calc.py",
        "tests/__init__.py",
        "tests/test_calc.py"
      ],
      "invocations": 6,
      "returncode": 0,
      "stderr": "",
      "count": 0,
      "findings": [],
      "skipped": false,
      "skipped_files": [],
      "duration_seconds": 0.071641,
      "files_checked": 6,
      "version": "0.15.22"
    },
    "basedpyright": {
      "tool": "basedpyright",
      "command": [
        "/Users/joaolopes/Exactus/.venv/bin/basedpyright",
        "__init__.py",
        "--outputjson",
        "conftest.py"
      ],
      "commands": [
        [
          "/Users/joaolopes/Exactus/.venv/bin/basedpyright",
          "__init__.py",
          "--outputjson",
          "conftest.py"
        ],
        [
          "/Users/joaolopes/Exactus/.venv/bin/basedpyright",
          "python/__init__.py",
          "--outputjson",
          "python/calc.py"
        ],
        [
          "/Users/joaolopes/Exactus/.venv/bin/basedpyright",
          "tests/__init__.py",
          "--outputjson",
          "tests/test_calc.py"
        ]
      ],
      "files": [
        "__init__.py",
        "conftest.py",
        "python/__init__.py",
        "python/calc.py",
        "tests/__init__.py",
        "tests/test_calc.py"
      ],
      "invocations": 3,
      "returncode": 0,
      "stderr": "",
      "count": 0,
      "findings": [],
      "skipped": false,
      "skipped_files": [],
      "duration_seconds": 1.661184,
      "files_checked": 6,
      "version": "1.40.2"
    },
    "pyrefly": {
      "tool": "pyrefly",
      "command": [
        "/opt/anaconda3/bin/pyrefly",
        "check",
        "--python-interpreter-path",
        "/Users/joaolopes/Exactus/.venv/bin/python",
        "--min-severity",
        "warn",
        "--output-format=json",
        "__init__.py",
        "conftest.py",
        "python/__init__.py",
        "python/calc.py",
        "tests/__init__.py",
        "tests/test_calc.py"
      ],
      "returncode": 0,
      "stderr": " WARN PYTHONPATH environment variable is set to \`/Users/joaolopes/Exactus/exactus/tests/standalone/project/src:/Users/joaolopes/Exactus/exactus/tests/standalone/project:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/basedpyright_coverage_pyrefly_pytest_ruff/python:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/build_twine/python:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/defusedxml/python:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/fastapi_httpx_httpx2_mcp_pydantic_uvicorn/python:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/hypothesis_mutmut/python:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/jinja2/python:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/pillow/python:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/playwright/python:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/psutil/python:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/tree-sitter_tree-sitter-language-pack/python:/Users/joaolopes/Exactus/bin/release/exactus_macos_arm64/exactus\`. Checks in other environments may not include these paths.\\n WARN PYTHONPATH environment variable is set to \`/Users/joaolopes/Exactus/exactus/tests/standalone/project/src:/Users/joaolopes/Exactus/exactus/tests/standalone/project:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/basedpyright_coverage_pyrefly_pytest_ruff/python:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/build_twine/python:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/defusedxml/python:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/fastapi_httpx_httpx2_mcp_pydantic_uvicorn/python:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/hypothesis_mutmut/python:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/jinja2/python:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/pillow/python:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/playwright/python:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/psutil/python:/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/tree-sitter_tree-sitter-language-pack/python:/Users/joaolopes/Exactus/bin/release/exactus_macos_arm64/exactus\`. Checks in other environments may not include these paths.\\n",
      "count": 0,
      "findings": [],
      "skipped_files": [],
      "duration_seconds": 0.276,
      "version": "0.63.0"
    },
    "eslint": {
      "tool": "eslint",
      "command": [
        "/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/eslint",
        "eslint.config.mjs",
        "--format",
        "json",
        "--no-warn-ignored"
      ],
      "commands": [
        [
          "/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/eslint",
          "eslint.config.mjs",
          "--format",
          "json",
          "--no-warn-ignored"
        ],
        [
          "/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/eslint",
          "stylelint.config.mjs",
          "--format",
          "json",
          "--no-warn-ignored"
        ],
        [
          "/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/eslint",
          "tests/code.test.mjs",
          "--format",
          "json",
          "--no-warn-ignored"
        ],
        [
          "/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/eslint",
          "web/code.js",
          "--format",
          "json",
          "--no-warn-ignored"
        ]
      ],
      "files": [
        "eslint.config.mjs",
        "stylelint.config.mjs",
        "tests/code.test.mjs",
        "web/code.js"
      ],
      "invocations": 4,
      "returncode": 0,
      "stderr": "",
      "count": 0,
      "findings": [],
      "skipped": false,
      "skipped_files": [],
      "duration_seconds": 1.150793,
      "files_checked": 4,
      "version": "10.14.0"
    },
    "stylelint": {
      "tool": "stylelint",
      "command": [
        "/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/stylelint",
        "web/style.css",
        "--formatter",
        "json"
      ],
      "commands": [
        [
          "/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/stylelint",
          "web/style.css",
          "--formatter",
          "json"
        ]
      ],
      "files": [
        "web/style.css"
      ],
      "invocations": 1,
      "returncode": 0,
      "stderr": "[{\\"source\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/web/style.css\\",\\"deprecations\\":[],\\"invalidOptionWarnings\\":[],\\"parseErrors\\":[],\\"errored\\":false,\\"warnings\\":[]}]",
      "count": 0,
      "findings": [],
      "skipped": false,
      "skipped_files": [],
      "duration_seconds": 1.200203,
      "files_checked": 1,
      "version": "17.16.0"
    },
    "htmlhint": {
      "tool": "htmlhint",
      "command": [
        "/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/htmlhint",
        "web/index.html"
      ],
      "commands": [
        [
          "/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/htmlhint",
          "web/index.html"
        ]
      ],
      "files": [
        "web/index.html"
      ],
      "invocations": 1,
      "returncode": 0,
      "stderr": "",
      "count": 0,
      "findings": [],
      "skipped": false,
      "skipped_files": [],
      "duration_seconds": 0.187376,
      "files_checked": 1,
      "version": "1.9.2"
    },
    "typescript": {
      "tool": "typescript",
      "command": [
        "/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/tsc",
        "--noEmit",
        "--pretty",
        "false",
        "--project",
        "/Users/joaolopes/Exactus/exactus/tests/standalone/project/.exactus-typescript-58424.json"
      ],
      "commands": [
        [
          "/Users/joaolopes/.cache/exactus-tools/8b7ef0f2198b3e6d3236bca167ecdaed2ec455101542db5323ad77e76f44bef0/components/eslint_htmlhint_jslint_prettier_stylelint_tsc/js/node_modules/.bin/tsc",
          "--noEmit",
          "--pretty",
          "false",
          "--project",
          "/Users/joaolopes/Exactus/exactus/tests/standalone/project/.exactus-typescript-58424.json"
        ]
      ],
      "files": [
        "eslint.config.mjs",
        "stylelint.config.mjs",
        "tests/code.test.mjs",
        "web/code.js"
      ],
      "invocations": 1,
      "returncode": 0,
      "stderr": "",
      "count": 0,
      "findings": [],
      "skipped": false,
      "skipped_files": [],
      "duration_seconds": 2.145754,
      "files_checked": 4,
      "version": "6.0.3"
    },
    "custom_python_long_lines": {
      "returncode": 0,
      "count": 0,
      "version": "built-in",
      "files": 6,
      "duration_seconds": 5.5917014833539724e-05,
      "findings": [],
      "healed": [],
      "skipped_files": []
    },
    "custom_compliance": {
      "returncode": 0,
      "count": 0,
      "version": "built-in",
      "files": 6,
      "duration_seconds": 0.0012783330166712403,
      "findings": [],
      "skipped_files": []
    }
  },
  "transaction": {
    "state": "committed",
    "files": 6,
    "stages": [
      {
        "name": "lints:group-final",
        "paths": []
      },
      {
        "name": "lints:organize",
        "paths": []
      },
      {
        "name": "lints:clean",
        "paths": [
          "conftest.py",
          "python/calc.py",
          "tests/test_calc.py"
        ]
      },
      {
        "name": "lints:convention-fixes",
        "paths": []
      },
      {
        "name": "lints:python-simplify",
        "paths": []
      },
      {
        "name": "lints:external-fixes",
        "paths": [
          "conftest.py",
          "python/calc.py",
          "tests/test_calc.py"
        ]
      },
      {
        "name": "lints:inference",
        "paths": [
          "__init__.py",
          "conftest.py",
          "python/__init__.py",
          "python/calc.py",
          "tests/__init__.py",
          "tests/test_calc.py"
        ]
      },
      {
        "name": "lints:group-final",
        "paths": []
      },
      {
        "name": "lints:organize",
        "paths": []
      },
      {
        "name": "lints:convention-fixes",
        "paths": []
      },
      {
        "name": "lints:python-simplify",
        "paths": []
      },
      {
        "name": "lints:external-fixes",
        "paths": []
      },
      {
        "name": "lints:inference",
        "paths": []
      }
    ]
  },
  "version": 1,
  "view": {
    "tool": {
      "name": "lints",
      "display_name": "Lint Exactus",
      "version": "0.7.1"
    },
    "run": {
      "id": "aa9f5f9f35a74d85857a1b2dfecca441:lints",
      "pipeline_id": "aa9f5f9f35a74d85857a1b2dfecca441",
      "status": "PASS",
      "exit_code": 0,
      "started_at": "2026-11-04T12:36:19.565434+00:00",
      "finished_at": "2026-11-04T12:36:30.950103+00:00",
      "at_human": "04 November 2026, 12:36:19 UTC",
      "started_at_human": "04 November 2026, 12:36:19 UTC",
      "finished_at_human": "04 November 2026, 12:36:30 UTC",
      "duration_seconds": 11.381,
      "duration_human": "11.4 s",
      "error": null
    },
    "previous_duration_seconds": 17.682,
    "summary": {
      "timing": {
        "date_time": "04/11/2026 12:36:25",
        "finished_date_time": "04/11/2026 12:36:29",
        "timezone": "WET",
        "duration_seconds": 4.473163,
        "duration_human": "00:00:04.473163"
      },
      "host": {
        "hostname": "Mac",
        "operating_system": "Darwin",
        "platform": "macOS-26.3.2-arm64-arm-64bit-Mach-O",
        "architecture": "arm64",
        "python_version": "3.13.9"
      },
      "analysis": {
        "working_directory": "/Users/joaolopes/Exactus/exactus/tests/standalone/project",
        "output_file": "/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/LINTS/LINTS.json",
        "targets": [
          "."
        ],
        "ignore_patterns": [
          ".*/**",
          "**/.*/**",
          "**/__pycache__/**",
          "**/build/**",
          "**/coverage_report/**",
          "**/dist/**",
          "**/env/**",
          "**/htmlcov/**",
          "**/mutants/**",
          "**/node_modules/**",
          "**/site-packages/**",
          "**/venv/**",
          "*.egg-info/**",
          "*.dist-info/**",
          "EXACTUS_RESULTS/**",
          "**/EXACTUS_RESULTS/**",
          "EXACTUS_RESULTS",
          "EXACTUS_RESULTS/**"
        ],
        "files": {
          "python": 6,
          "javascript_jsx": 2,
          "css": 1,
          "html": 1,
          "unique_analyzed": 10,
          "with_findings": 0
        },
        "files_with_issues": [],
        "findings": {
          "total": 0,
          "errors": 0,
          "warnings": 0,
          "information": 0,
          "unique_rules": 0,
          "affected_files": 0
        }
      },
      "tools": {
        "configured": 17,
        "executed": 17,
        "names": [
          "custom_compliance",
          "custom_shebang",
          "custom_python",
          "custom_python_long_lines",
          "custom_javascript",
          "custom_javascript_delimiters",
          "custom_javascript_notation",
          "custom_css",
          "custom_html",
          "ruff",
          "ruff_docs",
          "basedpyright",
          "pyrefly",
          "eslint",
          "typescript",
          "stylelint",
          "htmlhint"
        ]
      },
      "clean": true,
      "targets_eligible": 10,
      "targets_analyzed": 10,
      "findings_total": 0,
      "severity": {}
    },
    "comparison": {
      "available": true,
      "previous_generated_at": "2026-11-04T11:55:43.411354+00:00",
      "previous_run_id": "4f11bb392321406fba06a95f800a8d2a:lints",
      "previous_status": "PASS",
      "previous_duration_seconds": 17.682,
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
          "category": "CMP000",
          "title": "Module does not parse",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "CMP001",
          "title": "Suppression marker",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "CMP002",
          "title": "typing.Any usage",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "CMP003",
          "title": "object annotation",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "CMP004",
          "title": "Lint ignore configuration",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "CMP005",
          "title": "Type-check suppression",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "CMP006",
          "title": "pyproject.toml missing",
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
        "."
      ],
      "exclude": [
        ".*/**",
        "**/.*/**",
        "**/__pycache__/**",
        "**/build/**",
        "**/coverage_report/**",
        "**/dist/**",
        "**/env/**",
        "**/htmlcov/**",
        "**/mutants/**",
        "**/node_modules/**",
        "**/site-packages/**",
        "**/venv/**",
        "*.egg-info/**",
        "*.dist-info/**",
        "EXACTUS_RESULTS/**",
        "**/EXACTUS_RESULTS/**",
        "EXACTUS_RESULTS",
        "EXACTUS_RESULTS/**"
      ],
      "skipped": []
    },
    "invocation": {
      "command": "/Users/joaolopes/Exactus/bin/release/exactus_macos_arm64/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=57183 --orchestrator-control-token=[redacted] --orchestrator-worker-port=57173 --orchestrator-worker-token=[redacted] '--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"lints\\",\\"module\\":\\"exactus.tools.lints.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/LINTS\\",\\"arguments\\":[],\\"explicit_arguments\\":[],\\"run_id\\":\\"aa9f5f9f35a74d85857a1b2dfecca441:lints\\",\\"pipeline_run_id\\":\\"aa9f5f9f35a74d85857a1b2dfecca441\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}'",
      "cwd": "/Users/joaolopes/Exactus/exactus/tests/standalone/project",
      "arguments": [
        "exactus.tools.common.tool_worker",
        "ExactusTool",
        "--orchestrator-control-port=57183",
        "--orchestrator-control-token=[redacted]",
        "--orchestrator-worker-port=57173",
        "--orchestrator-worker-token=[redacted]",
        "--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"lints\\",\\"module\\":\\"exactus.tools.lints.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/LINTS\\",\\"arguments\\":[],\\"explicit_arguments\\":[],\\"run_id\\":\\"aa9f5f9f35a74d85857a1b2dfecca441:lints\\",\\"pipeline_run_id\\":\\"aa9f5f9f35a74d85857a1b2dfecca441\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}"
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
          "value": "aa9f5f9f35a74d85857a1b2dfecca441"
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
          "value": "aa9f5f9f35a74d85857a1b2dfecca441:lints"
        },
        {
          "name": "EXACTUS_TOOL",
          "value": "lints"
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
        "bytes": 2797
      },
      {
        "name": "README.md",
        "path": "ARTIFACTS/README.md",
        "bytes": 450
      },
      {
        "name": "stderr.log",
        "path": "ARTIFACTS/stderr.log",
        "bytes": 0
      },
      {
        "name": "stdout.log",
        "path": "ARTIFACTS/stdout.log",
        "bytes": 433
      },
      {
        "name": "steps.txt",
        "path": "ARTIFACTS/steps.txt",
        "bytes": 69010
      }
    ],
    "extension": {
      "metrics": {
        "overview": {
          "linters_run": 17,
          "linters_unavailable": 0,
          "files_analyzed": 10,
          "files_with_findings": 0,
          "rules_triggered": 0,
          "findings": 0
        },
        "linters": [
          {
            "linter": "custom_compliance",
            "status": "ran",
            "version": "built-in",
            "files": 6,
            "findings": 0,
            "errors": 0,
            "warnings": 0,
            "information": 0,
            "exit_code": 0,
            "duration_seconds": 0.0012783330166712403
          },
          {
            "linter": "custom_shebang",
            "status": "ran",
            "version": "built-in",
            "files": 6,
            "findings": 0,
            "errors": 0,
            "warnings": 0,
            "information": 0,
            "exit_code": 0,
            "duration_seconds": 0.003667250042781234
          },
          {
            "linter": "custom_python",
            "status": "ran",
            "version": "built-in",
            "files": 6,
            "findings": 0,
            "errors": 0,
            "warnings": 0,
            "information": 0,
            "exit_code": 0,
            "duration_seconds": 0.006
          },
          {
            "linter": "custom_python_long_lines",
            "status": "ran",
            "version": "built-in",
            "files": 6,
            "findings": 0,
            "errors": 0,
            "warnings": 0,
            "information": 0,
            "exit_code": 0,
            "duration_seconds": 5.5917014833539724e-05
          },
          {
            "linter": "custom_javascript",
            "status": "ran",
            "version": "built-in",
            "files": 2,
            "findings": 0,
            "errors": 0,
            "warnings": 0,
            "information": 0,
            "exit_code": 0,
            "duration_seconds": 0.0
          },
          {
            "linter": "custom_javascript_delimiters",
            "status": "ran",
            "version": "built-in",
            "files": 2,
            "findings": 0,
            "errors": 0,
            "warnings": 0,
            "information": 0,
            "exit_code": 0,
            "duration_seconds": 0.0002464170102030039
          },
          {
            "linter": "custom_javascript_notation",
            "status": "ran",
            "version": "built-in",
            "files": 2,
            "findings": 0,
            "errors": 0,
            "warnings": 0,
            "information": 0,
            "exit_code": 0,
            "duration_seconds": 3.6999990697950125e-05
          },
          {
            "linter": "custom_css",
            "status": "ran",
            "version": "built-in",
            "files": 1,
            "findings": 0,
            "errors": 0,
            "warnings": 0,
            "information": 0,
            "exit_code": 0,
            "duration_seconds": 0.003
          },
          {
            "linter": "custom_html",
            "status": "ran",
            "version": "built-in",
            "files": 1,
            "findings": 0,
            "errors": 0,
            "warnings": 0,
            "information": 0,
            "exit_code": 0,
            "duration_seconds": 0.0
          },
          {
            "linter": "ruff",
            "status": "ran",
            "version": "0.15.22",
            "files": 6,
            "findings": 0,
            "errors": 0,
            "warnings": 0,
            "information": 0,
            "exit_code": 0,
            "duration_seconds": 0.071641
          },
          {
            "linter": "ruff_docs",
            "status": "ran",
            "version": "0.15.22",
            "files": 6,
            "findings": 0,
            "errors": 0,
            "warnings": 0,
            "information": 0,
            "exit_code": 0,
            "duration_seconds": 0.071641
          },
          {
            "linter": "basedpyright",
            "status": "ran",
            "version": "1.40.2",
            "files": 6,
            "findings": 0,
            "errors": 0,
            "warnings": 0,
            "information": 0,
            "exit_code": 0,
            "duration_seconds": 1.661184
          },
          {
            "linter": "pyrefly",
            "status": "ran",
            "version": "0.63.0",
            "files": 6,
            "findings": 0,
            "errors": 0,
            "warnings": 0,
            "information": 0,
            "exit_code": 0,
            "duration_seconds": 0.276
          },
          {
            "linter": "eslint",
            "status": "ran",
            "version": "10.14.0",
            "files": 2,
            "findings": 0,
            "errors": 0,
            "warnings": 0,
            "information": 0,
            "exit_code": 0,
            "duration_seconds": 1.150793
          },
          {
            "linter": "typescript",
            "status": "ran",
            "version": "6.0.3",
            "files": 2,
            "findings": 0,
            "errors": 0,
            "warnings": 0,
            "information": 0,
            "exit_code": 0,
            "duration_seconds": 2.145754
          },
          {
            "linter": "stylelint",
            "status": "ran",
            "version": "17.16.0",
            "files": 1,
            "findings": 0,
            "errors": 0,
            "warnings": 0,
            "information": 0,
            "exit_code": 0,
            "duration_seconds": 1.200203
          },
          {
            "linter": "htmlhint",
            "status": "ran",
            "version": "1.9.2",
            "files": 1,
            "findings": 0,
            "errors": 0,
            "warnings": 0,
            "information": 0,
            "exit_code": 0,
            "duration_seconds": 0.187376
          }
        ],
        "top_rules": [],
        "top_files": [],
        "severity_by_linter": []
      },
      "rules": [
        {
          "rule": "CMP000",
          "title": "Module does not parse",
          "category": "Parsing",
          "count": 0
        },
        {
          "rule": "CMP001",
          "title": "Suppression marker",
          "category": "Suppression",
          "count": 0
        },
        {
          "rule": "CMP002",
          "title": "typing.Any usage",
          "category": "Typing",
          "count": 0
        },
        {
          "rule": "CMP003",
          "title": "object annotation",
          "category": "Typing",
          "count": 0
        },
        {
          "rule": "CMP004",
          "title": "Lint ignore configuration",
          "category": "Configuration",
          "count": 0
        },
        {
          "rule": "CMP005",
          "title": "Type-check suppression",
          "category": "Configuration",
          "count": 0
        },
        {
          "rule": "CMP006",
          "title": "pyproject.toml missing",
          "category": "Configuration",
          "count": 0
        }
      ]
    },
    "severity_levels": [
      "error",
      "warning",
      "information"
    ],
    "source_label": "Linter",
    "all_lints_summary": {
      "tools": 9,
      "passed": 8,
      "failed": 0,
      "unavailable": 1,
      "optional_unavailable": 1,
      "files": 40,
      "files_with_issues": 0,
      "errors": 0,
      "warnings": 0,
      "diagnostics": 0
    },
    "group_final_summary": {
      "files": 6,
      "planned": 0,
      "constants": 0,
      "changed": 0,
      "dry_run": true
    },
    "lint_overview": [
      {
        "metric": "Linters run",
        "value": 17
      },
      {
        "metric": "Linters unavailable",
        "value": 0
      },
      {
        "metric": "Files analyzed",
        "value": 10
      },
      {
        "metric": "Files with findings",
        "value": 0
      },
      {
        "metric": "Rules triggered",
        "value": 0
      },
      {
        "metric": "Findings",
        "value": 0
      }
    ],
    "linters": [
      {
        "linter": "custom_compliance",
        "status": "ran",
        "version": "built-in",
        "files": 6,
        "findings": 0,
        "errors": 0,
        "warnings": 0,
        "information": 0,
        "exit_code": 0,
        "duration_seconds": 0.0012783330166712403
      },
      {
        "linter": "custom_shebang",
        "status": "ran",
        "version": "built-in",
        "files": 6,
        "findings": 0,
        "errors": 0,
        "warnings": 0,
        "information": 0,
        "exit_code": 0,
        "duration_seconds": 0.003667250042781234
      },
      {
        "linter": "custom_python",
        "status": "ran",
        "version": "built-in",
        "files": 6,
        "findings": 0,
        "errors": 0,
        "warnings": 0,
        "information": 0,
        "exit_code": 0,
        "duration_seconds": 0.006
      },
      {
        "linter": "custom_python_long_lines",
        "status": "ran",
        "version": "built-in",
        "files": 6,
        "findings": 0,
        "errors": 0,
        "warnings": 0,
        "information": 0,
        "exit_code": 0,
        "duration_seconds": 5.5917014833539724e-05
      },
      {
        "linter": "custom_javascript",
        "status": "ran",
        "version": "built-in",
        "files": 2,
        "findings": 0,
        "errors": 0,
        "warnings": 0,
        "information": 0,
        "exit_code": 0,
        "duration_seconds": 0.0
      },
      {
        "linter": "custom_javascript_delimiters",
        "status": "ran",
        "version": "built-in",
        "files": 2,
        "findings": 0,
        "errors": 0,
        "warnings": 0,
        "information": 0,
        "exit_code": 0,
        "duration_seconds": 0.0002464170102030039
      },
      {
        "linter": "custom_javascript_notation",
        "status": "ran",
        "version": "built-in",
        "files": 2,
        "findings": 0,
        "errors": 0,
        "warnings": 0,
        "information": 0,
        "exit_code": 0,
        "duration_seconds": 3.6999990697950125e-05
      },
      {
        "linter": "custom_css",
        "status": "ran",
        "version": "built-in",
        "files": 1,
        "findings": 0,
        "errors": 0,
        "warnings": 0,
        "information": 0,
        "exit_code": 0,
        "duration_seconds": 0.003
      },
      {
        "linter": "custom_html",
        "status": "ran",
        "version": "built-in",
        "files": 1,
        "findings": 0,
        "errors": 0,
        "warnings": 0,
        "information": 0,
        "exit_code": 0,
        "duration_seconds": 0.0
      },
      {
        "linter": "ruff",
        "status": "ran",
        "version": "0.15.22",
        "files": 6,
        "findings": 0,
        "errors": 0,
        "warnings": 0,
        "information": 0,
        "exit_code": 0,
        "duration_seconds": 0.071641
      },
      {
        "linter": "ruff_docs",
        "status": "ran",
        "version": "0.15.22",
        "files": 6,
        "findings": 0,
        "errors": 0,
        "warnings": 0,
        "information": 0,
        "exit_code": 0,
        "duration_seconds": 0.071641
      },
      {
        "linter": "basedpyright",
        "status": "ran",
        "version": "1.40.2",
        "files": 6,
        "findings": 0,
        "errors": 0,
        "warnings": 0,
        "information": 0,
        "exit_code": 0,
        "duration_seconds": 1.661184
      },
      {
        "linter": "pyrefly",
        "status": "ran",
        "version": "0.63.0",
        "files": 6,
        "findings": 0,
        "errors": 0,
        "warnings": 0,
        "information": 0,
        "exit_code": 0,
        "duration_seconds": 0.276
      },
      {
        "linter": "eslint",
        "status": "ran",
        "version": "10.14.0",
        "files": 2,
        "findings": 0,
        "errors": 0,
        "warnings": 0,
        "information": 0,
        "exit_code": 0,
        "duration_seconds": 1.150793
      },
      {
        "linter": "typescript",
        "status": "ran",
        "version": "6.0.3",
        "files": 2,
        "findings": 0,
        "errors": 0,
        "warnings": 0,
        "information": 0,
        "exit_code": 0,
        "duration_seconds": 2.145754
      },
      {
        "linter": "stylelint",
        "status": "ran",
        "version": "17.16.0",
        "files": 1,
        "findings": 0,
        "errors": 0,
        "warnings": 0,
        "information": 0,
        "exit_code": 0,
        "duration_seconds": 1.200203
      },
      {
        "linter": "htmlhint",
        "status": "ran",
        "version": "1.9.2",
        "files": 1,
        "findings": 0,
        "errors": 0,
        "warnings": 0,
        "information": 0,
        "exit_code": 0,
        "duration_seconds": 0.187376
      }
    ],
    "top_rules": [],
    "top_files": [],
    "rules": [
      {
        "rule": "CMP000",
        "title": "Module does not parse",
        "category": "Parsing",
        "count": 0
      },
      {
        "rule": "CMP001",
        "title": "Suppression marker",
        "category": "Suppression",
        "count": 0
      },
      {
        "rule": "CMP002",
        "title": "typing.Any usage",
        "category": "Typing",
        "count": 0
      },
      {
        "rule": "CMP003",
        "title": "object annotation",
        "category": "Typing",
        "count": 0
      },
      {
        "rule": "CMP004",
        "title": "Lint ignore configuration",
        "category": "Configuration",
        "count": 0
      },
      {
        "rule": "CMP005",
        "title": "Type-check suppression",
        "category": "Configuration",
        "count": 0
      },
      {
        "rule": "CMP006",
        "title": "pyproject.toml missing",
        "category": "Configuration",
        "count": 0
      }
    ]
  },
  "view_columns": {
    "artifacts": [
      "name",
      "path",
      "bytes"
    ],
    "lint_overview": [
      "metric",
      "value"
    ],
    "linters": [
      "linter",
      "status",
      "version",
      "files",
      "findings",
      "errors",
      "warnings",
      "information",
      "exit_code",
      "duration_seconds"
    ],
    "rules": [
      "rule",
      "title",
      "category",
      "count"
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
    "all_lints_summary",
    "group_final_summary",
    "lint_overview",
    "linters",
    "top_rules",
    "top_files",
    "rules"
  ],
  "web": {
    "index": "index.html",
    "css": "report.css",
    "javascript": "report.js",
    "data": "data.json"
  }
}`);
