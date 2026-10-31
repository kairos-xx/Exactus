# Copyright (c) 2026
"""Round-trip JSON reports through every subsystem serializer."""

from __future__ import annotations

from importlib import import_module
from json import loads
from typing import TYPE_CHECKING, Final, cast, final

import pytest

from exactus.tests.common.support import expect_equal, expect_in

if TYPE_CHECKING:
    from collections.abc import Callable

    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        modules: Grouped module constant.

    """

    modules: Final[tuple[str, ...]] = (
        "exactus.tools.actions.json_types",
        "exactus.packages.completion.json_types",
        "exactus.packages.markdown.json_types",
        "exactus.tools.record.json_types",
        "exactus.packages.server.json_types",
        "exactus.tools.common.json_types",
    )


@pytest.mark.parametrize("module", Constants.modules)
def test_report_serializer_preserves_unicode_and_nested_values(
    module: str,
) -> None:
    """Keep diagnostics, booleans, null responses and Unicode unchanged.

    Args:
        module: Subsystem whose serializer is exercised.

    """
    factory: Callable[..., object] = cast(
        typ="Callable[..., object]",
        val=import_module(name=module).JsonDict,
    )
    payload: dict[str, JsonValue] = {
        "title": "Execução",
        "status": "FAIL",
        "findings": [{"message": "É inválido", "response": None}],
        "summary": {"checked": 3, "passed": False},
    }
    document: object = factory(payload)
    text: str = str(object=getattr(document, "tojson", ""))
    expect_equal(actual=loads(s=text), expected=payload)
    expect_in(member="É inválido", container=text)
