window.__REPORT_DATA__ = JSON.parse(`{
  "title": "tests Test Analyzer",
  "status": "PASS",
  "analyzer": "tests-tests",
  "comparison": {
    "available": true,
    "previous_generated_at": "2026-10-31T02:56:20.752171+00:00",
    "previous_run_id": null,
    "previous_status": "PASS",
    "previous_duration_seconds": null,
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
    "categories": []
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
  "generated_at": "2026-10-31T05:10:46.221558+00:00",
  "generated_at_human": "31 October 2026, 05:10:46 UTC",
  "local_links": {
    "tests/test_calc.py": "../../../../tests/test_calc.py",
    "/Users/joaolopes/Exactus/exactus/tests/standalone/project": "../../../..",
    "../../../../..": "../../../../..",
    "result.md": "result.md",
    "result.json": "result.json"
  },
  "markdown": "# tests Test Analyzer\\n\\n**Run time:** 31 October 2026, 05:10:46 UTC\\n\\n## Change since previous report\\n\\n| Findings | Current | Previous | Delta | Added | Resolved | Unchanged |\\n|---|---:|---:|---:|---:|---:|---:|\\n| Overall | 0 | 0 | 0 | 0 | 0 | 0 |\\n\\n\\n\\n- Status: **PASS**\\n- Execution: shared with COVERAGE (no duplicate pytest run)\\n- Matching test files: **1**\\n- Tests run: **2**\\n\\n## Test files\\n\\n### [\`tests/test_calc.py\`](../../../../tests/test_calc.py) — 2 tests\\n\\n| Test | Outcome |\\n| --- | --- |\\n| \`test_add_sums_operands\` | PASSED |\\n| \`test_is_even_flags_parity\` | PASSED |\\n",
  "passed": true,
  "project_href": "../../../../..",
  "project_root": "/Users/joaolopes/Exactus/exactus/tests/standalone/project",
  "report_bundle": {
    "markdown": "result.md",
    "json": "result.json",
    "web": "result_web"
  },
  "run_at": "2026-10-31T05:10:46.221558+00:00",
  "run_at_human": "31 October 2026, 05:10:46 UTC",
  "schema": "project-exactus-report/v1",
  "sections": [
    {
      "level": 1,
      "title": "tests Test Analyzer"
    },
    {
      "level": 2,
      "title": "Change since previous report"
    },
    {
      "level": 2,
      "title": "Test files"
    },
    {
      "level": 3,
      "title": "[\`tests/test_calc.py\`](../../../../tests/test_calc.py) — 2 tests"
    }
  ],
  "shared_execution": "COVERAGE",
  "shared_execution_status": 0,
  "test_execution": {
    "status": 0,
    "duration_seconds": 4.073,
    "tests": [
      {
        "shard": 0,
        "test": "tests/test_calc.py::test_add_sums_operands",
        "outcome": "PASSED",
        "log": "ARTIFACTS/TESTS/pytest-shards/shard-000.log"
      },
      {
        "shard": 0,
        "test": "tests/test_calc.py::test_is_even_flags_parity",
        "outcome": "PASSED",
        "log": "ARTIFACTS/TESTS/pytest-shards/shard-000.log"
      }
    ],
    "shards": [
      {
        "index": 0,
        "returncode": 0,
        "log": "ARTIFACTS/TESTS/pytest-shards/shard-000.log",
        "collected": 2,
        "tests": [
          {
            "shard": 0,
            "test": "tests/test_calc.py::test_add_sums_operands",
            "outcome": "PASSED"
          },
          {
            "shard": 0,
            "test": "tests/test_calc.py::test_is_even_flags_parity",
            "outcome": "PASSED"
          }
        ],
        "failures": [],
        "warnings": [],
        "skipped": []
      }
    ],
    "failed_tests": [],
    "skipped_tests": [],
    "warnings": []
  },
  "test_files": [
    "tests/test_calc.py"
  ],
  "tests": {
    "tests/test_calc.py": [
      {
        "name": "test_add_sums_operands",
        "outcome": "PASSED"
      },
      {
        "name": "test_is_even_flags_parity",
        "outcome": "PASSED"
      }
    ]
  },
  "tests_run": 2,
  "web": {
    "index": "index.html",
    "css": "report.css",
    "javascript": "report.js",
    "data": "data.json"
  }
}`);
