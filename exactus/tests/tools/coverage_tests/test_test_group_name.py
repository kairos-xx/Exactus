# Copyright (c) 2026
"""Test paths map to stable TESTS report group names."""

from __future__ import annotations

import pytest

from exactus.tests.common.support import expect_equal, private_call
from exactus.tools.coverage_tests.core import CombinedCoverageRunner


@pytest.mark.parametrize(
    ("test", "group"),
    [
        ("exactus/tests/tools/x.py", "tests_tools"),
        ("exactus/tests/markdown/x.py", "tests_markdown"),
        ("exactus/tests/record/x.py", "tests_record"),
        ("exactus/tests/scripts/collect/x.py", "tests_collect"),
        ("exactus/tests/common/x.py", "tests"),
        ("exactus/tests/test_support.py", "tests"),
        ("exactus/tests/test_check_cli.py", "tests"),
        ("exactus/tests/other/x.py", "tests_other"),
        ("test_root.py", "ROOT"),
    ],
)
def test_test_group_name(*, test: str, group: str) -> None:
    """Mirror directories under ``tests`` are skipped when naming the group.

    Args:
        test: POSIX test path relative to the exactused root.
        group: Expected group name.

    """
    expect_equal(
        actual=private_call(
            owner=CombinedCoverageRunner,
            name="_test_group_name",
            test=test,
        ),
        expected=group,
    )
