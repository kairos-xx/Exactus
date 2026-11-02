window.__REPORT_DATA__ = JSON.parse(`{
  "title": "Performance Exactus",
  "status": "PASS",
  "tool": "performance",
  "summary": {
    "runs": 7,
    "findings": 0,
    "severity": {
      "error": 0,
      "warning": 0,
      "info": 0
    }
  },
  "analyzer": "performance",
  "comparison": {
    "available": true,
    "previous_generated_at": "2026-11-02T04:27:21.917877+00:00",
    "previous_run_id": "4eb674a4eaf74587b6b16feda9b3d901:performance",
    "previous_status": "PASS",
    "previous_duration_seconds": 0.9,
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
  "duration_seconds": 1.12,
  "extension": {
    "output": "/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/PERFORMANCE",
    "serve": false,
    "gap_threshold": 0.25,
    "repetition_threshold": 10,
    "runs": [
      {
        "tool": "coverage_tests",
        "duration": 12.717,
        "events": 66,
        "events_per_second": 5.189903279075254,
        "largest_gap": 5.206,
        "silent": 11.931000000000001,
        "actors": 24,
        "threads": 3
      },
      {
        "tool": "docs",
        "duration": 0.824,
        "events": 18,
        "events_per_second": 21.844660194174757,
        "largest_gap": 0.7679999999999999,
        "silent": 0.7679999999999999,
        "actors": 4,
        "threads": 1
      },
      {
        "tool": "kwargs_typehints",
        "duration": 2.615,
        "events": 31,
        "events_per_second": 11.854684512428298,
        "largest_gap": 1.4000000000000001,
        "silent": 2.43,
        "actors": 7,
        "threads": 5
      },
      {
        "tool": "lints",
        "duration": 7.655,
        "events": 328,
        "events_per_second": 42.847811887655126,
        "largest_gap": 1.0780000000000003,
        "silent": 4.3660000000000005,
        "actors": 28,
        "threads": 19
      },
      {
        "tool": "performance",
        "duration": 0.001,
        "events": 2,
        "events_per_second": 2000.0,
        "largest_gap": 0.0,
        "silent": 0,
        "actors": 1,
        "threads": 1
      },
      {
        "tool": "readme",
        "duration": 0.637,
        "events": 19,
        "events_per_second": 29.827315541601255,
        "largest_gap": 0.626,
        "silent": 0.626,
        "actors": 6,
        "threads": 1
      },
      {
        "tool": "self_test",
        "duration": 603.223,
        "events": 111,
        "events_per_second": 0.1840115512836878,
        "largest_gap": 480.27500000000003,
        "silent": 598.3199999999999,
        "actors": 4,
        "threads": 1
      }
    ]
  },
  "findings": [],
  "fingerprint": {
    "commit": "3d9eec7e17a011978573b7cf5d68d0351fd43856",
    "tree": "d3c0507dcfef765aae70ed83e9536ad2d912e986",
    "dirty": true,
    "python": "3.13.9",
    "ruff": "ruff 0.12.0",
    "basedpyright": "basedpyright 1.40.2"
  },
  "generated_at": "2026-11-02T05:29:58.467410+00:00",
  "generated_at_human": "02 November 2026, 05:29:58 UTC",
  "local_links": {
    "/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/PERFORMANCE": ".",
    "../..": "../..",
    "../../..": "../../..",
    "result.md": "result.md",
    "result.json": "result.json",
    "/Users/joaolopes/Exactus/exactus/tests/standalone/project": "../.."
  },
  "markdown": "# Performance Exactus\\n\\n**Run time:** 02 November 2026, 05:29:58 UTC\\n\\n## Change since previous report\\n\\nPrevious run completed in **0.900s**.\\n\\n| Findings | Current | Previous | Delta | Added | Resolved | Unchanged |\\n|---|---:|---:|---:|---:|---:|---:|\\n| Overall | 0 | 0 | 0 | 0 | 0 | 0 |\\n",
  "passed": true,
  "previous_duration_seconds": 0.9,
  "project_href": "../../..",
  "project_root": "/Users/joaolopes/Exactus/exactus/tests/standalone/project",
  "report_bundle": {
    "markdown": "result.md",
    "json": "result.json",
    "web": "result_web"
  },
  "resume": "7 runs profiled — slowest self_test 603.2s",
  "run_at": "2026-11-02T05:29:58.467410+00:00",
  "run_at_human": "02 November 2026, 05:29:58 UTC",
  "schema": "project-exactus-report/v1",
  "scope": {
    "include": [
      "EXACTUS_RESULTS"
    ],
    "exclude": []
  },
  "sections": [
    {
      "level": 1,
      "title": "Performance Exactus"
    },
    {
      "level": 2,
      "title": "Change since previous report"
    }
  ],
  "web": {
    "index": "index.html",
    "css": "report.css",
    "javascript": "report.js",
    "data": "data.json"
  }
}`);
