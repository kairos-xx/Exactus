window.__REPORT_DATA__ = JSON.parse(`{
  "title": "Performance Exactus",
  "status": "PASS",
  "tool": "performance",
  "summary": {
    "runs": 6,
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
    "previous_generated_at": "2026-11-06T02:42:11.962403+00:00",
    "previous_run_id": "0aff3ce389f246459ce96ab2e4d75298:performance",
    "previous_status": "PASS",
    "previous_duration_seconds": 1.685,
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
  "duration_seconds": 1.422,
  "extension": {
    "output": "/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/PERFORMANCE",
    "serve": false,
    "gap_threshold": 0.25,
    "repetition_threshold": 10,
    "runs": [
      {
        "tool": "coverage_tests",
        "duration": 7.09,
        "events": 67,
        "events_per_second": 9.449929478138223,
        "largest_gap": 1.0780000000000003,
        "silent": 6.572,
        "actors": 22,
        "threads": 3
      },
      {
        "tool": "docs",
        "duration": 0.994,
        "events": 18,
        "events_per_second": 18.10865191146881,
        "largest_gap": 0.907,
        "silent": 0.907,
        "actors": 4,
        "threads": 1
      },
      {
        "tool": "kwargs_typehints",
        "duration": 2.269,
        "events": 31,
        "events_per_second": 13.662406346408108,
        "largest_gap": 1.368,
        "silent": 2.055,
        "actors": 7,
        "threads": 5
      },
      {
        "tool": "lints",
        "duration": 12.106,
        "events": 584,
        "events_per_second": 48.240541880059475,
        "largest_gap": 1.2240000000000002,
        "silent": 7.7230000000000025,
        "actors": 28,
        "threads": 37
      },
      {
        "tool": "performance",
        "duration": 0.003,
        "events": 2,
        "events_per_second": 666.6666666666666,
        "largest_gap": 0.0,
        "silent": 0,
        "actors": 1,
        "threads": 1
      },
      {
        "tool": "readme",
        "duration": 0.569,
        "events": 19,
        "events_per_second": 33.391915641476274,
        "largest_gap": 0.5539999999999999,
        "silent": 0.5539999999999999,
        "actors": 6,
        "threads": 1
      }
    ]
  },
  "findings": [],
  "fingerprint": {
    "commit": "82aa4af14783847df8265c9db323faeeed706c23",
    "tree": "1f2c5c1744667c3058a380081f7265d38c25721b",
    "dirty": true,
    "python": "3.13.9",
    "ruff": "ruff 0.12.0",
    "basedpyright": "basedpyright 1.40.2"
  },
  "generated_at": "2026-11-06T04:08:59.563490+00:00",
  "generated_at_human": "06 November 2026, 04:08:59 UTC",
  "local_links": {
    "/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS/PERFORMANCE": ".",
    "../..": "../..",
    "../../..": "../../..",
    "result.md": "result.md",
    "result.json": "result.json",
    "/Users/joaolopes/Exactus/exactus/tests/standalone/project": "../..",
    "/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS": ".."
  },
  "markdown": "# Performance Exactus\\n\\n**Run time:** 06 November 2026, 04:08:59 UTC\\n\\n## Change since previous report\\n\\nPrevious run completed in **1.685s**.\\n\\n| Findings | Current | Previous | Delta | Added | Resolved | Unchanged |\\n|---|---:|---:|---:|---:|---:|---:|\\n| Overall | 0 | 0 | 0 | 0 | 0 | 0 |\\n",
  "passed": true,
  "previous_duration_seconds": 1.685,
  "project_href": "../../..",
  "project_root": "/Users/joaolopes/Exactus/exactus/tests/standalone/project",
  "report_bundle": {
    "markdown": "result.md",
    "json": "result.json",
    "web": "result_web"
  },
  "resume": "6 runs profiled — slowest lints 12.1s",
  "run_at": "2026-11-06T04:08:59.563490+00:00",
  "run_at_human": "06 November 2026, 04:08:59 UTC",
  "schema": "project-exactus-report/v1",
  "scope": {
    "include": [
      "/Users/joaolopes/Exactus/exactus/tests/standalone/project/EXACTUS_RESULTS"
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
