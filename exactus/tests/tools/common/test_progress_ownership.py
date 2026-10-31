# Copyright (c) 2026
"""Keep terminal progress tied to the invocation being displayed."""

from __future__ import annotations

from json import dumps
from typing import TYPE_CHECKING, Final

import pytest

from exactus.__main__ import Check
from exactus.tests.common.support import expect_equal, private_call, require
from exactus.tools.common.catalog import Constants, ToolSpec

if TYPE_CHECKING:
    from pathlib import Path
pytestmark: Final[pytest.MarkDecorator] = pytest.mark.usefixtures(
    "isolated_check",
)


@pytest.mark.parametrize("run_id", ["coverage-run", "pipeline:coverage-run"])
def test_progress_ignores_previous_run_until_current_heartbeat(
    run_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A completed old run cannot pin the next run's bar at 100 percent.

    Args:
        run_id: Standalone or pipeline invocation identity.
        tmp_path: Isolated report directory.
        monkeypatch: Redirect progress reads to disposable report data.

    """
    monkeypatch.setattr(
        target=Check,
        name="exactus_root",
        value=tmp_path / "EXACTUS_RESULTS",
    )
    tool: ToolSpec = require(
        value=Constants.exactus_catalog.tool(identifier="coverage_tests"),
    )
    activity: Path = (
        Check.exactus_root / tool.output / "ARTIFACTS" / "@activity.json"
    )
    activity.parent.mkdir(parents=True, exist_ok=True)
    _ = activity.write_text(
        data=dumps(
            obj={
                "run_id": "previous-run",
                "progress": {"fraction": 1.0, "step": "complete"},
            },
        ),
        encoding="utf-8",
    )
    expect_equal(
        actual=private_call(
            owner=Check,
            name="_read_progress",
            tool=tool,
            run_id=run_id,
        ),
        expected=(0.0, "starting", 0, None),
    )
    _ = activity.write_text(
        data=dumps(
            obj={
                "run_id": run_id,
                "progress": {
                    "fraction": 0.5778,
                    "percent": 57.78,
                    "completed": 17,
                    "total": 18,
                    "step": "pytest shard",
                },
            },
        ),
        encoding="utf-8",
    )
    expect_equal(
        actual=private_call(
            owner=Check,
            name="_read_progress",
            tool=tool,
            run_id=run_id,
        ),
        expected=(0.5778, "pytest shard", 0, None),
    )
