window.__REPORT_DATA__ = JSON.parse(`{
  "title": "README Exactus",
  "status": "PASS",
  "tool": {
    "name": "readme",
    "display_name": "README Exactus",
    "version": null
  },
  "summary": {
    "targets_eligible": 4,
    "targets_analyzed": 4,
    "findings_total": 0,
    "severity": {},
    "directories": 4,
    "findings": 0,
    "by_rule": {}
  },
  "analyzer": "readme",
  "artifacts": [
    {
      "name": "@activity.json",
      "path": "ARTIFACTS/@activity.json",
      "bytes": 1662
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
      "bytes": 0
    },
    {
      "name": "steps.txt",
      "path": "ARTIFACTS/steps.txt",
      "bytes": 1609
    }
  ],
  "comparison": {
    "available": true,
    "previous_generated_at": "2026-10-31T02:56:40.730117+00:00",
    "previous_run_id": "f9656595c8b74d23b2b6aec3bd0db7de:readme",
    "previous_status": "PASS",
    "previous_duration_seconds": 0.649,
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
        "category": "RDM001",
        "title": "Missing README.md",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "RDM002",
        "title": "Undocumented subdirectory",
        "current": 0,
        "previous": 0,
        "delta": 0
      },
      {
        "category": "RDM003",
        "title": "Undocumented file",
        "current": 0,
        "previous": 0,
        "delta": 0
      }
    ]
  },
  "directories": [
    ".",
    "python",
    "tests",
    "web"
  ],
  "duration_seconds": 0.809,
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
        "value": "2c65e21142f34f8db22b09b30d9044d1:readme"
      },
      {
        "name": "EXACTUS_TOOL",
        "value": "readme"
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
    "metrics": {
      "markdown": {
        "files": 4,
        "bytes": 2669,
        "lines": 80,
        "readme_files": 4,
        "largest_readme": {
          "path": "README.md",
          "bytes": 1187
        },
        "smallest_readme": {
          "path": "python/README.md",
          "bytes": 438
        }
      },
      "directories_without_readme": []
    },
    "directories": [
      {
        "path": ".",
        "has_readme": true,
        "readme_bytes": 1187,
        "entries": 6,
        "documented": 6,
        "missing": 0
      },
      {
        "path": "python",
        "has_readme": true,
        "readme_bytes": 438,
        "entries": 2,
        "documented": 2,
        "missing": 0
      },
      {
        "path": "tests",
        "has_readme": true,
        "readme_bytes": 579,
        "entries": 3,
        "documented": 3,
        "missing": 0
      },
      {
        "path": "web",
        "has_readme": true,
        "readme_bytes": 465,
        "entries": 3,
        "documented": 3,
        "missing": 0
      }
    ],
    "rules": [
      {
        "rule": "RDM001",
        "title": "Missing README.md",
        "count": 0
      },
      {
        "rule": "RDM002",
        "title": "Undocumented subdirectory",
        "count": 0
      },
      {
        "rule": "RDM003",
        "title": "Undocumented file",
        "count": 0
      }
    ]
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
  "generated_at": "2026-10-31T05:10:57.315309+00:00",
  "generated_at_human": "31 October 2026, 05:10:57 UTC",
  "invocation": {
    "command": "/usr/local/bin/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=64240 --orchestrator-control-token=[redacted] --orchestrator-worker-port=64223 --orchestrator-worker-token=[redacted] '--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"readme\\",\\"module\\":\\"exactus.tools.readme.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/README\\",\\"arguments\\":[],\\"run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1:readme\\",\\"pipeline_run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}'",
    "cwd": "/Users/joaolopes/Exactus/exactus/tests/standalone/project",
    "arguments": [
      "exactus.tools.common.tool_worker",
      "ExactusTool",
      "--orchestrator-control-port=64240",
      "--orchestrator-control-token=[redacted]",
      "--orchestrator-worker-port=64223",
      "--orchestrator-worker-token=[redacted]",
      "--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"readme\\",\\"module\\":\\"exactus.tools.readme.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/README\\",\\"arguments\\":[],\\"run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1:readme\\",\\"pipeline_run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}"
    ]
  },
  "local_links": {
    "README.md": "../../README.md",
    "python/README.md": "../../python/README.md",
    "../../..": "../../..",
    "/Users/joaolopes/Exactus/exactus/tests/standalone/project": "../..",
    "result.md": "result.md",
    "result.json": "result.json",
    "/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/.runtime/runs.db": "../.runtime/runs.db",
    "ARTIFACTS/@activity.json": "ARTIFACTS/%40activity.json",
    "ARTIFACTS/README.md": "ARTIFACTS/README.md",
    "ARTIFACTS/stderr.log": "ARTIFACTS/stderr.log",
    "ARTIFACTS/stdout.log": "ARTIFACTS/stdout.log",
    "ARTIFACTS/steps.txt": "ARTIFACTS/steps.txt"
  },
  "markdown": "# README Exactus\\n\\n**Run time:** 31 October 2026, 05:10:57 UTC\\n\\n## Identity\\n\\n| Field | Value |\\n|---|---|\\n| Tool | readme |\\n| Run ID | 2c65e21142f34f8db22b09b30d9044d1:readme |\\n| Pipeline run | 2c65e21142f34f8db22b09b30d9044d1 |\\n| Status | PASS |\\n| Exit code | 0 |\\n| Started | 31 October 2026, 05:10:57 UTC |\\n| Finished | 31 October 2026, 05:10:58 UTC |\\n| Duration | 0.8 s |\\n| Previous duration | 0.649s |\\n\\n## What was checked\\n\\n**Result: PASS** — 0 findings across 4 of 4 eligible targets.\\n\\n| Severity | Count |\\n|---|---:|\\n| ERROR | 0 |\\n\\n### Change since previous report\\n\\n| Metric | Current | Previous | Delta |\\n|---|---:|---:|---:|\\n| Findings | 0 | 0 | 0 |\\n| Previous duration | 0.649s | | |\\n\\n| Finding change | Count |\\n|---|---:|\\n| Added | 0 |\\n| Resolved | 0 |\\n| Unchanged | 0 |\\n\\n#### Category findings\\n\\n| Category | Title | Findings | Previous | Delta |\\n| --- | --- | --- | --- | --- |\\n| RDM001 | Missing README.md | 0 | 0 | 0 |\\n| RDM002 | Undocumented subdirectory | 0 | 0 | 0 |\\n| RDM003 | Undocumented file | 0 | 0 | 0 |\\n\\n### Scope\\n\\n**Included**\\n\\n- \`src/**\`\\n- \`tests/**\`\\n- \`examples/**\`\\n- \`scripts/**\`\\n- \`resources/**\`\\n- \`docs/**\`\\n- \`**/README.md\`\\n\\n**Excluded**\\n\\n- \`**/.agents/**\`\\n- \`**/.build-cache/**\`\\n- \`**/.cache/**\`\\n- \`**/.claude/**\`\\n- \`**/.cursor/**\`\\n- \`**/.devin/**\`\\n- \`**/.eggs/**\`\\n- \`**/.git/**\`\\n- \`**/.history/**\`\\n- \`**/.mypy_cache/**\`\\n- \`**/.pytest_cache/**\`\\n- \`**/.ruff_cache/**\`\\n- \`**/.tox/**\`\\n- \`**/.venv/**\`\\n- \`**/DEBUG.txt/**\`\\n- \`**/EXACTUS_RESULTS/**\`\\n- \`**/__pycache__/**\`\\n- \`**/build/**\`\\n- \`**/coverage_report/**\`\\n- \`**/debug/**\`\\n- \`**/dist/**\`\\n- \`**/env/**\`\\n- \`**/htmlcov/**\`\\n- \`**/mutants/**\`\\n- \`**/node_modules/**\`\\n- \`**/site-packages/**\`\\n- \`**/venv/**\`\\n- \`**/.*\`\\n- \`**/*.egg-info/**\`\\n- \`**/*.dist-info/**\`\\n\\n**Skipped targets**\\n\\nNo skipped targets.\\n\\n## Setup\\n\\n### Invocation\\n\\n~~~~shell\\n/usr/local/bin/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=64240 --orchestrator-control-token=[redacted] --orchestrator-worker-port=64223 --orchestrator-worker-token=[redacted] '--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"readme\\",\\"module\\":\\"exactus.tools.readme.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/README\\",\\"arguments\\":[],\\"run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1:readme\\",\\"pipeline_run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}'\\n~~~~\\n\\n| Property | Value |\\n|---|---|\\n| Working directory | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |\\n| Arguments | \`exactus.tools.common.tool_worker\` \`ExactusTool\` \`--orchestrator-control-port=64240\` \`--orchestrator-control-token=[redacted]\` \`--orchestrator-worker-port=64223\` \`--orchestrator-worker-token=[redacted]\` \`--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"readme\\",\\"module\\":\\"exactus.tools.readme.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/README\\",\\"arguments\\":[],\\"run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1:readme\\",\\"pipeline_run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}\` |\\n\\n### Environment\\n\\n| Property | Value |\\n|---|---|\\n| OS | Darwin 25.3.0 |\\n| Python | 3.13.9 |\\n| Node | v22.21.1 |\\n| CPU count | 18 |\\n\\n| Variable | Value |\\n| --- | --- |\\n| EXACTUS_ORCHESTRATED | 1 |\\n| EXACTUS_PIPELINE_RUN_ID | 2c65e21142f34f8db22b09b30d9044d1 |\\n| EXACTUS_REGISTRY | [/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/.runtime/runs.db](../.runtime/runs.db) |\\n| EXACTUS_ROOT | [/Users/joaolopes/Exactus/exactus/tests/standalone/project](../..) |\\n| EXACTUS_RUN_ID | 2c65e21142f34f8db22b09b30d9044d1:readme |\\n| EXACTUS_TOOL | readme |\\n| LANG | en_US.UTF-8 |\\n| TERM | xterm-256color |\\n\\n## Gate\\n\\n> **Gate: PASS** — No blocking findings\\n\\nNo blocking findings.\\n\\n## Findings\\n\\nNo findings.\\n\\n## Artifacts\\n\\n| Artifact | Path | Bytes |\\n| --- | --- | --- |\\n| @activity.json | [ARTIFACTS/@activity.json](ARTIFACTS/%40activity.json) | 1662 |\\n| README.md | [ARTIFACTS/README.md](ARTIFACTS/README.md) | 450 |\\n| stderr.log | [ARTIFACTS/stderr.log](ARTIFACTS/stderr.log) | 0 |\\n| stdout.log | [ARTIFACTS/stdout.log](ARTIFACTS/stdout.log) | 0 |\\n| steps.txt | [ARTIFACTS/steps.txt](ARTIFACTS/steps.txt) | 1609 |\\n\\n## Directory inventory\\n\\n| Directory | README | README bytes | Entries | Documented | Missing |\\n| --- | --- | --- | --- | --- | --- |\\n| . | present | 1187 | 6 | 6 | 0 |\\n| python | present | 438 | 2 | 2 | 0 |\\n| tests | present | 579 | 3 | 3 | 0 |\\n| web | present | 465 | 3 | 3 | 0 |\\n\\n## Documentation files\\n\\n| Metric | Value |\\n| --- | --- |\\n| Markdown files | 4 |\\n| Markdown bytes | 2669 |\\n| Markdown lines | 80 |\\n| README files | 4 |\\n\\n### README sizes\\n\\n| README | Path | Bytes |\\n| --- | --- | --- |\\n| Largest | [README.md](../../README.md) | 1187 |\\n| Smallest | [python/README.md](../../python/README.md) | 438 |\\n\\n### Directories without a README\\n\\nN/A — every directory with analyzed source files has a README.\\n\\n## Rules\\n\\n| Rule | Title | Findings |\\n| --- | --- | --- |\\n| RDM001 | Missing README.md | 0 |\\n| RDM002 | Undocumented subdirectory | 0 |\\n| RDM003 | Undocumented file | 0 |\\n\\n---\\n\\nExactus · readme · Run 2c65e21142f34f8db22b09b30d9044d1:readme · Result PASS · Duration 0.8 s\\n",
  "passed": true,
  "pipeline_run_id": "2c65e21142f34f8db22b09b30d9044d1",
  "previous_duration_seconds": 0.649,
  "project_href": "../../..",
  "project_root": "/Users/joaolopes/Exactus/exactus/tests/standalone/project",
  "report_bundle": {
    "markdown": "result.md",
    "json": "result.json",
    "web": "result_web"
  },
  "resume": "PASS: analyzer completed with exit status 0.",
  "run": {
    "id": "2c65e21142f34f8db22b09b30d9044d1:readme",
    "pipeline_id": "2c65e21142f34f8db22b09b30d9044d1",
    "status": "PASS",
    "exit_code": 0,
    "started_at": "2026-10-31T05:10:57.284063+00:00",
    "finished_at": "2026-10-31T05:10:58.094710+00:00",
    "at_human": "31 October 2026, 05:10:57 UTC",
    "started_at_human": "31 October 2026, 05:10:57 UTC",
    "finished_at_human": "31 October 2026, 05:10:58 UTC",
    "duration_seconds": 0.809,
    "duration_human": "0.8 s",
    "error": null
  },
  "run_at": "2026-10-31T05:10:57.284063+00:00",
  "run_at_human": "31 October 2026, 05:10:57 UTC",
  "run_id": "2c65e21142f34f8db22b09b30d9044d1:readme",
  "schema": "project-exactus-report/v1",
  "scope": {
    "include": [
      "src/**",
      "tests/**",
      "examples/**",
      "scripts/**",
      "resources/**",
      "docs/**",
      "**/README.md"
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
      "**/DEBUG.txt/**",
      "**/EXACTUS_RESULTS/**",
      "**/__pycache__/**",
      "**/build/**",
      "**/coverage_report/**",
      "**/debug/**",
      "**/dist/**",
      "**/env/**",
      "**/htmlcov/**",
      "**/mutants/**",
      "**/node_modules/**",
      "**/site-packages/**",
      "**/venv/**",
      "**/.*",
      "**/*.egg-info/**",
      "**/*.dist-info/**"
    ],
    "skipped": []
  },
  "sections": [
    {
      "level": 1,
      "title": "README Exactus"
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
      "title": "Directory inventory"
    },
    {
      "level": 2,
      "title": "Documentation files"
    },
    {
      "level": 3,
      "title": "README sizes"
    },
    {
      "level": 3,
      "title": "Directories without a README"
    },
    {
      "level": 2,
      "title": "Rules"
    }
  ],
  "view": {
    "tool": {
      "name": "readme",
      "display_name": "README Exactus",
      "version": null
    },
    "run": {
      "id": "2c65e21142f34f8db22b09b30d9044d1:readme",
      "pipeline_id": "2c65e21142f34f8db22b09b30d9044d1",
      "status": "PASS",
      "exit_code": 0,
      "started_at": "2026-10-31T05:10:57.284063+00:00",
      "finished_at": "2026-10-31T05:10:58.094710+00:00",
      "at_human": "31 October 2026, 05:10:57 UTC",
      "started_at_human": "31 October 2026, 05:10:57 UTC",
      "finished_at_human": "31 October 2026, 05:10:58 UTC",
      "duration_seconds": 0.809,
      "duration_human": "0.8 s",
      "error": null
    },
    "previous_duration_seconds": 0.649,
    "summary": {
      "targets_eligible": 4,
      "targets_analyzed": 4,
      "findings_total": 0,
      "severity": {},
      "directories": 4,
      "findings": 0,
      "by_rule": {}
    },
    "comparison": {
      "available": true,
      "previous_generated_at": "2026-10-31T02:56:40.730117+00:00",
      "previous_run_id": "f9656595c8b74d23b2b6aec3bd0db7de:readme",
      "previous_status": "PASS",
      "previous_duration_seconds": 0.649,
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
          "category": "RDM001",
          "title": "Missing README.md",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "RDM002",
          "title": "Undocumented subdirectory",
          "current": 0,
          "previous": 0,
          "delta": 0
        },
        {
          "category": "RDM003",
          "title": "Undocumented file",
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
        "src/**",
        "tests/**",
        "examples/**",
        "scripts/**",
        "resources/**",
        "docs/**",
        "**/README.md"
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
        "**/DEBUG.txt/**",
        "**/EXACTUS_RESULTS/**",
        "**/__pycache__/**",
        "**/build/**",
        "**/coverage_report/**",
        "**/debug/**",
        "**/dist/**",
        "**/env/**",
        "**/htmlcov/**",
        "**/mutants/**",
        "**/node_modules/**",
        "**/site-packages/**",
        "**/venv/**",
        "**/.*",
        "**/*.egg-info/**",
        "**/*.dist-info/**"
      ],
      "skipped": []
    },
    "invocation": {
      "command": "/usr/local/bin/exactus/exactus/packages/pmanager/class_runner.py exactus.tools.common.tool_worker ExactusTool --orchestrator-control-port=64240 --orchestrator-control-token=[redacted] --orchestrator-worker-port=64223 --orchestrator-worker-token=[redacted] '--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"readme\\",\\"module\\":\\"exactus.tools.readme.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/README\\",\\"arguments\\":[],\\"run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1:readme\\",\\"pipeline_run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}'",
      "cwd": "/Users/joaolopes/Exactus/exactus/tests/standalone/project",
      "arguments": [
        "exactus.tools.common.tool_worker",
        "ExactusTool",
        "--orchestrator-control-port=64240",
        "--orchestrator-control-token=[redacted]",
        "--orchestrator-worker-port=64223",
        "--orchestrator-worker-token=[redacted]",
        "--orchestrator-call={\\"args\\":[],\\"kwargs\\":{\\"request\\":{\\"identifier\\":\\"readme\\",\\"module\\":\\"exactus.tools.readme.main\\",\\"output\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/README\\",\\"arguments\\":[],\\"run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1:readme\\",\\"pipeline_run_id\\":\\"2c65e21142f34f8db22b09b30d9044d1\\",\\"project_root\\":\\"/Users/joaolopes/Exactus/exactus/tests/standalone/project\\"}}}"
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
          "value": "2c65e21142f34f8db22b09b30d9044d1:readme"
        },
        {
          "name": "EXACTUS_TOOL",
          "value": "readme"
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
        "bytes": 1662
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
        "bytes": 0
      },
      {
        "name": "steps.txt",
        "path": "ARTIFACTS/steps.txt",
        "bytes": 1609
      }
    ],
    "extension": {
      "metrics": {
        "markdown": {
          "files": 4,
          "bytes": 2669,
          "lines": 80,
          "readme_files": 4,
          "largest_readme": {
            "path": "README.md",
            "bytes": 1187
          },
          "smallest_readme": {
            "path": "python/README.md",
            "bytes": 438
          }
        },
        "directories_without_readme": []
      },
      "directories": [
        {
          "path": ".",
          "has_readme": true,
          "readme_bytes": 1187,
          "entries": 6,
          "documented": 6,
          "missing": 0
        },
        {
          "path": "python",
          "has_readme": true,
          "readme_bytes": 438,
          "entries": 2,
          "documented": 2,
          "missing": 0
        },
        {
          "path": "tests",
          "has_readme": true,
          "readme_bytes": 579,
          "entries": 3,
          "documented": 3,
          "missing": 0
        },
        {
          "path": "web",
          "has_readme": true,
          "readme_bytes": 465,
          "entries": 3,
          "documented": 3,
          "missing": 0
        }
      ],
      "rules": [
        {
          "rule": "RDM001",
          "title": "Missing README.md",
          "count": 0
        },
        {
          "rule": "RDM002",
          "title": "Undocumented subdirectory",
          "count": 0
        },
        {
          "rule": "RDM003",
          "title": "Undocumented file",
          "count": 0
        }
      ]
    },
    "severity_levels": [
      "error"
    ],
    "inventory": [
      {
        "directory": ".",
        "readme": "present",
        "bytes": 1187,
        "entries": 6,
        "documented": 6,
        "missing": 0
      },
      {
        "directory": "python",
        "readme": "present",
        "bytes": 438,
        "entries": 2,
        "documented": 2,
        "missing": 0
      },
      {
        "directory": "tests",
        "readme": "present",
        "bytes": 579,
        "entries": 3,
        "documented": 3,
        "missing": 0
      },
      {
        "directory": "web",
        "readme": "present",
        "bytes": 465,
        "entries": 3,
        "documented": 3,
        "missing": 0
      }
    ],
    "rules": [
      {
        "rule": "RDM001",
        "title": "Missing README.md",
        "count": 0
      },
      {
        "rule": "RDM002",
        "title": "Undocumented subdirectory",
        "count": 0
      },
      {
        "rule": "RDM003",
        "title": "Undocumented file",
        "count": 0
      }
    ],
    "documentation_files": [
      {
        "metric": "Markdown files",
        "value": 4
      },
      {
        "metric": "Markdown bytes",
        "value": 2669
      },
      {
        "metric": "Markdown lines",
        "value": 80
      },
      {
        "metric": "README files",
        "value": 4
      }
    ],
    "readme_sizes": [
      {
        "readme": "Largest",
        "path": "README.md",
        "bytes": 1187
      },
      {
        "readme": "Smallest",
        "path": "python/README.md",
        "bytes": 438
      }
    ],
    "directories_without_readme": []
  },
  "view_columns": {
    "artifacts": [
      "name",
      "path",
      "bytes"
    ],
    "inventory": [
      "directory",
      "readme",
      "bytes",
      "entries",
      "documented",
      "missing"
    ],
    "rules": [
      "rule",
      "title",
      "count"
    ],
    "documentation_files": [
      "metric",
      "value"
    ],
    "readme_sizes": [
      "readme",
      "path",
      "bytes"
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
    "inventory",
    "rules",
    "documentation_files",
    "readme_sizes",
    "directories_without_readme"
  ],
  "web": {
    "index": "index.html",
    "css": "report.css",
    "javascript": "report.js",
    "data": "data.json"
  }
}`);
