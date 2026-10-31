window.__REPORT_DATA__ = JSON.parse(`{
  "title": "Documentation Exactus",
  "status": "PASS",
  "tool": {
    "name": "docs",
    "display_name": "Documentation Exactus",
    "version": null
  },
  "summary": {
    "targets_eligible": 8,
    "targets_analyzed": 8,
    "findings_total": 0,
    "severity": {}
  },
  "analyzer": "documentation",
  "artifacts": [
    {
      "name": "@activity.json",
      "path": "ARTIFACTS/@activity.json",
      "bytes": 1648
    },
    {
      "name": "README.md",
      "path": "ARTIFACTS/README.md",
      "bytes": 448
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
      "bytes": 1754
    }
  ],
  "comparison": {
    "available": true,
    "previous_generated_at": "2026-10-31T02:56:19.786551+00:00",
    "previous_run_id": "f9656595c8b74d23b2b6aec3bd0db7de:docs",
    "previous_status": "PASS",
    "previous_duration_seconds": 0.664,
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
        "category": "DOC001",
        "title": "Missing documentation",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "DOC002",
        "title": "Missing parameter documentation",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "DOC003",
        "title": "Stale parameter documentation",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "DOC004",
        "title": "Missing return documentation",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "DOC005",
        "title": "Return and yield mismatch",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "DOC006",
        "title": "Missing exception documentation",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "DOC007",
        "title": "Missing attribute documentation",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "DOC008",
        "title": "Malformed documentation",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "DOC009",
        "title": "Analysis failure",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "DOC010",
        "title": "Missing description",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "DOC011",
        "title": "Stale exception documentation",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "DOC012",
        "title": "Stale attribute documentation",
        "current": 0,
        "previous": 0,
        "delta": 0
      }
    ]
  },
  "duration_seconds": 0.831,
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
        "value": "2c65e21142f34f8db22b09b30d9044d1"
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
        "value": "2c65e21142f34f8db22b09b30d9044d1:docs"
      },
      {
        "name": "EXACTUS_TOOL",
        "value": "docs"
      },
      {
        "name": "LANG",
        "value": "en_US.UTF-8"
      },
      {
        "name": "TERM",
        "value": "xterm-256color"
      }
    ]
  },
  "extension": {
    "languages": [
      {
        "discovered": 2,
        "parsed": 2,
        "failed": 0,
        "symbols": 3,
        "documented": 3,
        "findings": 0,
        "language": "javascript",
        "coverage_percent": 100.0
      },
      {
        "discovered": 6,
        "parsed": 6,
        "failed": 0,
        "symbols": 12,
        "documented": 12,
        "findings": 0,
        "language": "python",
        "coverage_percent": 100.0
      }
    ],
    "rules": [
      {
        "rule": "DOC001",
        "title": "Missing documentation",
        "count": 0
      },
      {
        "rule": "DOC002",
        "title": "Missing parameter documentation",
        "count": 0
      },
      {
        "rule": "DOC003",
        "title": "Stale parameter documentation",
        "count": 0
      },
      {
        "rule": "DOC004",
        "title": "Missing return documentation",
        "count": 0
      },
      {
        "rule": "DOC005",
        "title": "Return and yield mismatch",
        "count": 0
      },
      {
        "rule": "DOC006",
        "title": "Missing exception documentation",
        "count": 0
      },
      {
        "rule": "DOC007",
        "title": "Missing attribute documentation",
        "count": 0
      },
      {
        "rule": "DOC008",
        "title": "Malformed documentation",
        "count": 0
      },
      {
        "rule": "DOC009",
        "title": "Analysis failure",
        "count": 0
      },
      {
        "rule": "DOC010",
        "title": "Missing description",
        "count": 0
      },
      {
        "rule": "DOC011",
        "title": "Stale exception documentation",
        "count": 0
      },
      {
        "rule": "DOC012",
        "title": "Stale attribute documentation",
        "count": 0
      }
    ],
    "fail_on": "warning",
    "metrics": {
      "languages": [
        {
          "language": "javascript",
          "files_analyzed": 2,
          "lines_analyzed": 35
        },
        {
          "language": "python",
          "files_analyzed": 6,
          "lines_analyzed": 91
        }
      ]
    }
  },
  "findings": [],
  "fingerprint": {
    "commit": "282d5c7d9518d89751b13d3619d2ee2b3307402d",
    "tree": "5e6a63ecb4a3768a5f1d9d3776696e9531905933",
    "dirty": true,
    "python": "3.13.9",
    "ruff": "ruff 0.12.0",
    "basedpyright": "basedpyright 1.40.2"
  },
  "gate": {
    "status": "PASS",
    "reason": "No blocking findings"
  },
  "generated_at": "2026-10-31T05:10:43.649547+00:00",
  "generated_at_human": "31 October 2026, 05:10:43 UTC",
  "invocation": {
    "command": "/usr/local/bin/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=62416 --orchestrator-control-token=[redacted] --orchestrator-worker-port=62365 --orchestrator-worker-token=[redacted] '--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"docs\\",\\"module\\":\\"exactus.tools.docs.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/DOCS\\",\\"arguments\\":[],\\"run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1:docs\\",\\"pipeline_run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}'",
    "cwd": "/Users/joaolopes/Exactus/exactus/tests/standalone/project",
    "arguments": [
      "exactus.tools.common.tool_worker",
      "ExactusTool",
      "--orchestrator-control-port=62416",
      "--orchestrator-control-token=[redacted]",
      "--orchestrator-worker-port=62365",
      "--orchestrator-worker-token=[redacted]",
      "--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"docs\\",\\"module\\":\\"exactus.tools.docs.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/DOCS\\",\\"arguments\\":[],\\"run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1:docs\\",\\"pipeline_run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}"
    ]
  },
  "local_links": {
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
  "markdown": "# Documentation Exactus\\n\\n**Run time:** 31 October 2026, 05:10:43 UTC\\n\\n## Identity\\n\\n| Field | Value |\\n|---|---|\\n| Tool | docs |\\n| Run ID | 2c65e21142f34f8db22b09b30d9044d1:docs |\\n| Pipeline run | 2c65e21142f34f8db22b09b30d9044d1 |\\n| Status | PASS |\\n| Exit code | 0 |\\n| Started | 31 October 2026, 05:10:43 UTC |\\n| Finished | 31 October 2026, 05:10:44 UTC |\\n| Duration | 0.8 s |\\n| Previous duration | 0.664s |\\n\\n## What was checked\\n\\n**Result: PASS** — 0 findings across 8 of 8 eligible targets.\\n\\n| Severity | Count |\\n|---|---:|\\n| ERROR | 0 |\\n| WARNING | 0 |\\n| INFO | 0 |\\n\\n### Change since previous report\\n\\n| Metric | Current | Previous | Delta |\\n|---|---:|---:|---:|\\n| Findings | 0 | 0 | 0 |\\n| Previous duration | 0.664s | | |\\n\\n| Finding change | Count |\\n|---|---:|\\n| Added | 0 |\\n| Resolved | 0 |\\n| Unchanged | 0 |\\n\\n#### Category findings\\n\\n| Category | Title | Findings | Previous | Delta |\\n| --- | --- | --- | --- | --- |\\n| DOC001 | Missing documentation | 0 | 0 | 0 |\\n| DOC002 | Missing parameter documentation | 0 | 0 | 0 |\\n| DOC003 | Stale parameter documentation | 0 | 0 | 0 |\\n| DOC004 | Missing return documentation | 0 | 0 | 0 |\\n| DOC005 | Return and yield mismatch | 0 | 0 | 0 |\\n| DOC006 | Missing exception documentation | 0 | 0 | 0 |\\n| DOC007 | Missing attribute documentation | 0 | 0 | 0 |\\n| DOC008 | Malformed documentation | 0 | 0 | 0 |\\n| DOC009 | Analysis failure | 0 | 0 | 0 |\\n| DOC010 | Missing description | 0 | 0 | 0 |\\n| DOC011 | Stale exception documentation | 0 | 0 | 0 |\\n| DOC012 | Stale attribute documentation | 0 | 0 | 0 |\\n\\n### Scope\\n\\n**Included**\\n\\n- \`**/*.js\`\\n- \`**/*.mjs\`\\n- \`**/*.cjs\`\\n- \`**/*.py\`\\n\\n**Excluded**\\n\\n- \`**/.agents/**\`\\n- \`**/.build-cache/**\`\\n- \`**/.cache/**\`\\n- \`**/.claude/**\`\\n- \`**/.cursor/**\`\\n- \`**/.devin/**\`\\n- \`**/.eggs/**\`\\n- \`**/.git/**\`\\n- \`**/.history/**\`\\n- \`**/.mypy_cache/**\`\\n- \`**/.pytest_cache/**\`\\n- \`**/.ruff_cache/**\`\\n- \`**/.tox/**\`\\n- \`**/.venv/**\`\\n- \`**/EXACTUS_RESULTS/**\`\\n- \`**/__pycache__/**\`\\n- \`**/build/**\`\\n- \`**/coverage_report/**\`\\n- \`**/dist/**\`\\n- \`**/env/**\`\\n- \`**/htmlcov/**\`\\n- \`**/mutants/**\`\\n- \`**/node_modules/**\`\\n- \`**/site-packages/**\`\\n- \`**/venv/**\`\\n- \`**/.*/**\`\\n- \`**/*.min.js\`\\n\\n**Skipped targets**\\n\\nNo skipped targets.\\n\\n## Setup\\n\\n### Invocation\\n\\n~~~~shell\\n/usr/local/bin/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=62416 --orchestrator-control-token=[redacted] --orchestrator-worker-port=62365 --orchestrator-worker-token=[redacted] '--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"docs\\",\\"module\\":\\"exactus.tools.docs.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/DOCS\\",\\"arguments\\":[],\\"run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1:docs\\",\\"pipeline_run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}'\\n~~~~\\n\\n| Property | Value |\\n|---|---|\\n| Working directory | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |\\n| Arguments | \`exactus.tools.common.tool_worker\` \`ExactusTool\` \`--orchestrator-control-port=62416\` \`--orchestrator-control-token=[redacted]\` \`--orchestrator-worker-port=62365\` \`--orchestrator-worker-token=[redacted]\` \`--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"docs\\",\\"module\\":\\"exactus.tools.docs.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/DOCS\\",\\"arguments\\":[],\\"run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1:docs\\",\\"pipeline_run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}\` |\\n\\n### Environment\\n\\n| Property | Value |\\n|---|---|\\n| OS | Darwin 25.3.0 |\\n| Python | 3.13.9 |\\n| Node | v22.21.1 |\\n| CPU count | 18 |\\n\\n| Variable | Value |\\n| --- | --- |\\n| EXACTUS_ORCHESTRATED | 1 |\\n| EXACTUS_PIPELINE_RUN_ID | 2c65e21142f34f8db22b09b30d9044d1 |\\n| EXACTUS_REGISTRY | [/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/.runtime/runs.db](../.runtime/runs.db) |\\n| EXACTUS_ROOT | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |\\n| EXACTUS_RUN_ID | 2c65e21142f34f8db22b09b30d9044d1:docs |\\n| EXACTUS_TOOL | docs |\\n| LANG | en_US.UTF-8 |\\n| TERM | xterm-256color |\\n\\n## Gate\\n\\n> **Gate: PASS** — No blocking findings\\n\\nNo blocking findings.\\n\\n## Findings\\n\\nNo findings.\\n\\n## Artifacts\\n\\n| Artifact | Path | Bytes |\\n| --- | --- | --- |\\n| @activity.json | [ARTIFACTS/@activity.json](ARTIFACTS/%40activity.json) | 1648 |\\n| README.md | [ARTIFACTS/README.md](ARTIFACTS/README.md) | 448 |\\n| stderr.log | [ARTIFACTS/stderr.log](ARTIFACTS/stderr.log) | 0 |\\n| stdout.log | [ARTIFACTS/stdout.log](ARTIFACTS/stdout.log) | 0 |\\n| steps.txt | [ARTIFACTS/steps.txt](ARTIFACTS/steps.txt) | 1754 |\\n\\n## Documentation statistics\\n\\n| Language | Files | Parsed | Failed | Symbols | Documented | Coverage % | Findings |\\n| --- | --- | --- | --- | --- | --- | --- | --- |\\n| javascript | 2 | 2 | 0 | 3 | 3 | 100.0 | 0 |\\n| python | 6 | 6 | 0 | 12 | 12 | 100.0 | 0 |\\n\\n## Analyzed code\\n\\n| Language | Files | Lines |\\n| --- | --- | --- |\\n| javascript | 2 | 35 |\\n| python | 6 | 91 |\\n\\n## Rules\\n\\n| Rule | Title | Findings |\\n| --- | --- | --- |\\n| DOC001 | Missing documentation | 0 |\\n| DOC002 | Missing parameter documentation | 0 |\\n| DOC003 | Stale parameter documentation | 0 |\\n| DOC004 | Missing return documentation | 0 |\\n| DOC005 | Return and yield mismatch | 0 |\\n| DOC006 | Missing exception documentation | 0 |\\n| DOC007 | Missing attribute documentation | 0 |\\n| DOC008 | Malformed documentation | 0 |\\n| DOC009 | Analysis failure | 0 |\\n| DOC010 | Missing description | 0 |\\n| DOC011 | Stale exception documentation | 0 |\\n| DOC012 | Stale attribute documentation | 0 |\\n\\n## Suggested documentation\\n\\nNo suggestions.\\n\\n---\\n\\nExactus · docs · Run 2c65e21142f34f8db22b09b30d9044d1:docs · Result PASS · Duration 0.8 s\\n",
  "passed": true,
  "pipeline_run_id": "2c65e21142f34f8db22b09b30d9044d1",
  "previous_duration_seconds": 0.664,
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
    "id": "2c65e21142f34f8db22b09b30d9044d1:docs",
    "pipeline_id": "2c65e21142f34f8db22b09b30d9044d1",
    "status": "PASS",
    "exit_code": 0,
    "started_at": "2026-10-31T05:10:43.578851+00:00",
    "finished_at": "2026-10-31T05:10:44.411853+00:00",
    "at_human": "31 October 2026, 05:10:43 UTC",
    "started_at_human": "31 October 2026, 05:10:43 UTC",
    "finished_at_human": "31 October 2026, 05:10:44 UTC",
    "duration_seconds": 0.831,
    "duration_human": "0.8 s",
    "error": null
  },
  "run_at": "2026-10-31T05:10:43.578851+00:00",
  "run_at_human": "31 October 2026, 05:10:43 UTC",
  "run_id": "2c65e21142f34f8db22b09b30d9044d1:docs",
  "schema": "project-exactus-report/v1",
  "scope": {
    "include": [
      "**/*.js",
      "**/*.mjs",
      "**/*.cjs",
      "**/*.py"
    ],
    "exclude": [
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
      "**/EXACTUS_RESULTS/**",
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
      "**/.*/**",
      "**/*.min.js"
    ],
    "skipped": []
  },
  "sections": [
    {
      "level": 1,
      "title": "Documentation Exactus"
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
      "title": "Documentation statistics"
    },
    {
      "level": 2,
      "title": "Analyzed code"
    },
    {
      "level": 2,
      "title": "Rules"
    },
    {
      "level": 2,
      "title": "Suggested documentation"
    }
  ],
  "statistics": {
    "javascript": {
      "discovered": 2,
      "parsed": 2,
      "failed": 0,
      "symbols": 3,
      "documented": 3,
      "findings": 0
    },
    "python": {
      "discovered": 6,
      "parsed": 6,
      "failed": 0,
      "symbols": 12,
      "documented": 12,
      "findings": 0
    }
  },
  "view": {
    "tool": {
      "name": "docs",
      "display_name": "Documentation Exactus",
      "version": null
    },
    "run": {
      "id": "2c65e21142f34f8db22b09b30d9044d1:docs",
      "pipeline_id": "2c65e21142f34f8db22b09b30d9044d1",
      "status": "PASS",
      "exit_code": 0,
      "started_at": "2026-10-31T05:10:43.578851+00:00",
      "finished_at": "2026-10-31T05:10:44.411853+00:00",
      "at_human": "31 October 2026, 05:10:43 UTC",
      "started_at_human": "31 October 2026, 05:10:43 UTC",
      "finished_at_human": "31 October 2026, 05:10:44 UTC",
      "duration_seconds": 0.831,
      "duration_human": "0.8 s",
      "error": null
    },
    "previous_duration_seconds": 0.664,
    "summary": {
      "targets_eligible": 8,
      "targets_analyzed": 8,
      "findings_total": 0,
      "severity": {}
    },
    "comparison": {
      "available": true,
      "previous_generated_at": "2026-10-31T02:56:19.786551+00:00",
      "previous_run_id": "f9656595c8b74d23b2b6aec3bd0db7de:docs",
      "previous_status": "PASS",
      "previous_duration_seconds": 0.664,
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
          "category": "DOC001",
          "title": "Missing documentation",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "DOC002",
          "title": "Missing parameter documentation",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "DOC003",
          "title": "Stale parameter documentation",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "DOC004",
          "title": "Missing return documentation",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "DOC005",
          "title": "Return and yield mismatch",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "DOC006",
          "title": "Missing exception documentation",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "DOC007",
          "title": "Missing attribute documentation",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "DOC008",
          "title": "Malformed documentation",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "DOC009",
          "title": "Analysis failure",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "DOC010",
          "title": "Missing description",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "DOC011",
          "title": "Stale exception documentation",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "DOC012",
          "title": "Stale attribute documentation",
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
        "**/*.js",
        "**/*.mjs",
        "**/*.cjs",
        "**/*.py"
      ],
      "exclude": [
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
        "**/EXACTUS_RESULTS/**",
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
        "**/.*/**",
        "**/*.min.js"
      ],
      "skipped": []
    },
    "invocation": {
      "command": "/usr/local/bin/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=62416 --orchestrator-control-token=[redacted] --orchestrator-worker-port=62365 --orchestrator-worker-token=[redacted] '--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"docs\\",\\"module\\":\\"exactus.tools.docs.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/DOCS\\",\\"arguments\\":[],\\"run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1:docs\\",\\"pipeline_run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}'",
      "cwd": "/Users/joaolopes/Exactus/exactus/tests/standalone/project",
      "arguments": [
        "exactus.tools.common.tool_worker",
        "ExactusTool",
        "--orchestrator-control-port=62416",
        "--orchestrator-control-token=[redacted]",
        "--orchestrator-worker-port=62365",
        "--orchestrator-worker-token=[redacted]",
        "--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"docs\\",\\"module\\":\\"exactus.tools.docs.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/DOCS\\",\\"arguments\\":[],\\"run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1:docs\\",\\"pipeline_run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}"
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
          "value": "2c65e21142f34f8db22b09b30d9044d1"
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
          "value": "2c65e21142f34f8db22b09b30d9044d1:docs"
        },
        {
          "name": "EXACTUS_TOOL",
          "value": "docs"
        },
        {
          "name": "LANG",
          "value": "en_US.UTF-8"
        },
        {
          "name": "TERM",
          "value": "xterm-256color"
        }
      ]
    },
    "findings": [],
    "blocking": [],
    "artifacts": [
      {
        "name": "@activity.json",
        "path": "ARTIFACTS/@activity.json",
        "bytes": 1648
      },
      {
        "name": "README.md",
        "path": "ARTIFACTS/README.md",
        "bytes": 448
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
        "bytes": 1754
      }
    ],
    "extension": {
      "languages": [
        {
          "discovered": 2,
          "parsed": 2,
          "failed": 0,
          "symbols": 3,
          "documented": 3,
          "findings": 0,
          "language": "javascript",
          "coverage_percent": 100.0
        },
        {
          "discovered": 6,
          "parsed": 6,
          "failed": 0,
          "symbols": 12,
          "documented": 12,
          "findings": 0,
          "language": "python",
          "coverage_percent": 100.0
        }
      ],
      "rules": [
        {
          "rule": "DOC001",
          "title": "Missing documentation",
          "count": 0
        },
        {
          "rule": "DOC002",
          "title": "Missing parameter documentation",
          "count": 0
        },
        {
          "rule": "DOC003",
          "title": "Stale parameter documentation",
          "count": 0
        },
        {
          "rule": "DOC004",
          "title": "Missing return documentation",
          "count": 0
        },
        {
          "rule": "DOC005",
          "title": "Return and yield mismatch",
          "count": 0
        },
        {
          "rule": "DOC006",
          "title": "Missing exception documentation",
          "count": 0
        },
        {
          "rule": "DOC007",
          "title": "Missing attribute documentation",
          "count": 0
        },
        {
          "rule": "DOC008",
          "title": "Malformed documentation",
          "count": 0
        },
        {
          "rule": "DOC009",
          "title": "Analysis failure",
          "count": 0
        },
        {
          "rule": "DOC010",
          "title": "Missing description",
          "count": 0
        },
        {
          "rule": "DOC011",
          "title": "Stale exception documentation",
          "count": 0
        },
        {
          "rule": "DOC012",
          "title": "Stale attribute documentation",
          "count": 0
        }
      ],
      "fail_on": "warning",
      "metrics": {
        "languages": [
          {
            "language": "javascript",
            "files_analyzed": 2,
            "lines_analyzed": 35
          },
          {
            "language": "python",
            "files_analyzed": 6,
            "lines_analyzed": 91
          }
        ]
      }
    },
    "severity_levels": [
      "error",
      "warning",
      "info"
    ],
    "languages": [
      {
        "language": "javascript",
        "discovered": 2,
        "parsed": 2,
        "failed": 0,
        "symbols": 3,
        "documented": 3,
        "coverage": 100.0,
        "findings": 0
      },
      {
        "language": "python",
        "discovered": 6,
        "parsed": 6,
        "failed": 0,
        "symbols": 12,
        "documented": 12,
        "coverage": 100.0,
        "findings": 0
      }
    ],
    "rules": [
      {
        "rule": "DOC001",
        "title": "Missing documentation",
        "count": 0
      },
      {
        "rule": "DOC002",
        "title": "Missing parameter documentation",
        "count": 0
      },
      {
        "rule": "DOC003",
        "title": "Stale parameter documentation",
        "count": 0
      },
      {
        "rule": "DOC004",
        "title": "Missing return documentation",
        "count": 0
      },
      {
        "rule": "DOC005",
        "title": "Return and yield mismatch",
        "count": 0
      },
      {
        "rule": "DOC006",
        "title": "Missing exception documentation",
        "count": 0
      },
      {
        "rule": "DOC007",
        "title": "Missing attribute documentation",
        "count": 0
      },
      {
        "rule": "DOC008",
        "title": "Malformed documentation",
        "count": 0
      },
      {
        "rule": "DOC009",
        "title": "Analysis failure",
        "count": 0
      },
      {
        "rule": "DOC010",
        "title": "Missing description",
        "count": 0
      },
      {
        "rule": "DOC011",
        "title": "Stale exception documentation",
        "count": 0
      },
      {
        "rule": "DOC012",
        "title": "Stale attribute documentation",
        "count": 0
      }
    ],
    "analyzed_code": [
      {
        "language": "javascript",
        "files": 2,
        "lines": 35
      },
      {
        "language": "python",
        "files": 6,
        "lines": 91
      }
    ]
  },
  "view_columns": {
    "artifacts": [
      "name",
      "path",
      "bytes"
    ],
    "languages": [
      "language",
      "discovered",
      "parsed",
      "failed",
      "symbols",
      "documented",
      "coverage",
      "findings"
    ],
    "rules": [
      "rule",
      "title",
      "count"
    ],
    "analyzed_code": [
      "language",
      "files",
      "lines"
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
    "languages",
    "rules",
    "analyzed_code"
  ],
  "web": {
    "index": "index.html",
    "css": "report.css",
    "javascript": "report.js",
    "data": "data.json"
  }
}`);
