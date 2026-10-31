# Copyright (c) 2026
"""Tests for the SceneDescriptor Playwright bridge."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from exactus.packages.scene_description import (
    DescriptionOptions,
    SceneDescriptor,
)
from exactus.tests.common.support import private_as
from exactus.tests.packages.scene_description.conftest import FakePage
from exactus.tests.packages.scene_description.support import (
    expect_equal,
    expect_false,
    expect_raises,
    expect_true,
    require_json_dict,
)

if TYPE_CHECKING:
    from exactus.packages.scene_description.models import JsonValue


def test_init_uses_bundled_runtime() -> None:
    """The default script path points at the packaged JS runtime."""
    descriptor: SceneDescriptor = SceneDescriptor()
    script_path: Path = private_as(
        owner=descriptor,
        name="_script_path",
        kind=Path,
    )
    source: str = private_as(owner=descriptor, name="_source", kind=str)
    expect_equal(actual=script_path.name, expected="unified_evidence.js")
    expect_true(
        condition=source.startswith("/** @file"),
        message="bundled runtime was not loaded",
    )


def test_init_accepts_custom_script_path(tmp_path: Path) -> None:
    """A custom script path replaces the bundled runtime source.

    Args:
        tmp_path: Pytest fixture used by this test.

    """
    source: Path = tmp_path / "custom.js"
    _ = source.write_text(data="custom();", encoding="utf-8")
    descriptor: SceneDescriptor = SceneDescriptor(script_path=source)
    expect_equal(
        actual=private_as(owner=descriptor, name="_script_path", kind=Path),
        expected=source,
    )
    expect_equal(
        actual=private_as(owner=descriptor, name="_source", kind=str),
        expected="custom();",
    )


def test_install_injects_when_missing() -> None:
    """Pages lacking globalThis.Descriptor receive the runtime."""
    descriptor: SceneDescriptor = SceneDescriptor()
    page: FakePage = FakePage()
    descriptor.install(page=page)
    expect_equal(actual=len(page.script_tags), expected=1)
    expect_equal(
        actual=page.script_tags[0],
        expected=private_as(owner=descriptor, name="_source", kind=str),
    )


def test_install_skips_when_available() -> None:
    """Pages already exposing Descriptor are left alone."""
    descriptor: SceneDescriptor = SceneDescriptor()
    page: FakePage = FakePage()
    page.descriptor_installed = True
    descriptor.install(page=page)
    expect_false(condition=page.script_tags)


def test_describe_builds_browser_payload() -> None:
    """The evaluate call forwards selector and camelCase options."""
    descriptor: SceneDescriptor = SceneDescriptor()
    page: FakePage = FakePage()
    page.evaluate_result = {"elements": {"e": {}}}
    result: dict[str, JsonValue] = descriptor.describe(
        page=page,
        selector="#panel",
        options=DescriptionOptions(include_binary=True),
    )
    expect_equal(actual=result, expected={"elements": {"e": {}}})
    payload: dict[str, JsonValue] = require_json_dict(value=page.arguments[-1])
    expect_equal(actual=payload["selector"], expected="#panel")
    expect_true(
        condition=require_json_dict(value=payload["options"])["includeBinary"],
    )
    expect_equal(actual=len(page.expressions), expected=2)


def test_describe_defaults() -> None:
    """Default selector and options are supplied."""
    descriptor: SceneDescriptor = SceneDescriptor()
    page: FakePage = FakePage()
    page.evaluate_result = {}
    _ = descriptor.describe(page=page)
    payload: dict[str, JsonValue] = require_json_dict(value=page.arguments[-1])
    expect_equal(actual=payload["selector"], expected="html")
    expect_equal(
        actual=payload["options"],
        expected=DescriptionOptions().browser_options(),
    )


def test_describe_rejects_non_dict_result() -> None:
    """A non-object runtime result raises TypeError."""
    descriptor: SceneDescriptor = SceneDescriptor()
    page: FakePage = FakePage()
    page.evaluate_result = ["not", "a", "dict"]
    expect_raises(kind=TypeError, call=lambda: descriptor.describe(page=page))


def test_describe_installs_before_evaluate() -> None:
    """describe() injects the runtime when the page lacks it."""
    descriptor: SceneDescriptor = SceneDescriptor()
    page: FakePage = FakePage()
    page.evaluate_result = {"elements": {}}
    _ = descriptor.describe(page=page)
    expect_equal(actual=len(page.script_tags), expected=1)
    expect_true(
        condition=page.expressions[0].startswith("() =>"),
        message=page.expressions[0],
    )
