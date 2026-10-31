# Copyright (c) 2026
"""Tests for the package pipeline configuration loader."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from exactus.packages.package.config import (
    BuildConfig,
    BundleConfig,
    PackageConfig,
    PipelineConfig,
    load_config,
)
from exactus.tests.common.support import expect_equal

if TYPE_CHECKING:
    from pathlib import Path


def _write_config(*, tmp_path: Path, text: str) -> None:
    """Write a pyproject.toml fragment into the temporary root.

    Args:
        tmp_path: Temporary project root.
        text: Raw TOML fragment to write.

    """
    _ = (tmp_path / "pyproject.toml").write_text(data=text, encoding="utf-8")


def test_empty_project_returns_defaults(tmp_path: Path) -> None:
    """Missing pyproject.toml yields a fully default configuration.

    Args:
        tmp_path: Isolated project root.

    """
    config: PipelineConfig = load_config(root=tmp_path)
    expect_equal(actual=config.root, expected=tmp_path)
    expect_equal(actual=config.build, expected=BuildConfig(enabled=False))
    expect_equal(actual=config.bundle, expected=BundleConfig(enabled=False))
    expect_equal(actual=config.package, expected=PackageConfig(enabled=False))


def test_bundle_output_path_is_resolved(tmp_path: Path) -> None:
    """The optional bundle output is resolved against the project root.

    Args:
        tmp_path: Isolated project root.

    """
    _write_config(
        tmp_path=tmp_path,
        text='[tool.package.bundle]\noutput="dist/bundle.zip"\n',
    )
    config: PipelineConfig = load_config(root=tmp_path)
    expect_equal(
        actual=config.bundle.output,
        expected=tmp_path / "dist" / "bundle.zip",
    )


def test_load_config_rejects_non_string_list_items(tmp_path: Path) -> None:
    """A string list containing a non-string item raises TypeError.

    Args:
        tmp_path: Isolated project root.

    """
    _write_config(
        tmp_path=tmp_path,
        text='[tool.package.build]\ntargets=["all", 1]\n',
    )
    with pytest.raises(
        expected_exception=TypeError,
        match="must be a list of strings",
    ):
        load_config(root=tmp_path)


def test_load_config_rejects_non_boolean(tmp_path: Path) -> None:
    """A boolean field with a non-boolean value raises TypeError.

    Args:
        tmp_path: Isolated project root.

    """
    _write_config(
        tmp_path=tmp_path,
        text='[tool.package.build]\nenabled="true"\n',
    )
    with pytest.raises(
        expected_exception=TypeError,
        match="must be a boolean",
    ):
        load_config(root=tmp_path)


def test_load_config_rejects_non_string_path(tmp_path: Path) -> None:
    """A path field with a non-string value raises TypeError.

    Args:
        tmp_path: Isolated project root.

    """
    _write_config(
        tmp_path=tmp_path,
        text="[tool.package.bundle]\noutput=123\n",
    )
    with pytest.raises(
        expected_exception=TypeError,
        match="must be a string path",
    ):
        load_config(root=tmp_path)


def test_load_config_rejects_non_table_tool(tmp_path: Path) -> None:
    """A non-table ``tool`` entry falls back to defaults.

    Args:
        tmp_path: Isolated project root.

    """
    _write_config(tmp_path=tmp_path, text='tool = "invalid"\n')
    config: PipelineConfig = load_config(root=tmp_path)
    expect_equal(actual=config.build.enabled, expected=False)


def test_load_config_rejects_non_table_package(tmp_path: Path) -> None:
    """A non-table ``[tool.package]`` entry raises a clear TypeError.

    Args:
        tmp_path: Isolated project root.

    """
    _write_config(tmp_path=tmp_path, text='[tool]\npackage = "invalid"\n')
    with pytest.raises(expected_exception=TypeError, match="must be a table"):
        load_config(root=tmp_path)


def test_load_config_rejects_non_table_stage(tmp_path: Path) -> None:
    """A non-table stage setting raises a clear TypeError.

    Args:
        tmp_path: Isolated project root.

    """
    _write_config(
        tmp_path=tmp_path,
        text='[tool.package]\nbuild = "invalid"\n',
    )
    with pytest.raises(
        expected_exception=TypeError,
        match="stage settings must be tables",
    ):
        load_config(root=tmp_path)


def test_load_config_rejects_non_integer_part_bytes(tmp_path: Path) -> None:
    """A non-integer ``part-bytes`` value raises a clear TypeError.

    Args:
        tmp_path: Isolated project root.

    """
    _write_config(
        tmp_path=tmp_path,
        text='[tool.package.bundle]\npart-bytes = "big"\n',
    )
    with pytest.raises(
        expected_exception=TypeError,
        match="part-bytes must be an integer",
    ):
        load_config(root=tmp_path)


def test_load_config_rejects_non_string_node_version(tmp_path: Path) -> None:
    """A non-string ``node-version`` value raises a clear TypeError.

    Args:
        tmp_path: Isolated project root.

    """
    _write_config(
        tmp_path=tmp_path,
        text="[tool.package.bundle]\nnode-version = 22\n",
    )
    with pytest.raises(
        expected_exception=TypeError,
        match="node-version must be a string",
    ):
        load_config(root=tmp_path)


def test_load_config_rejects_non_list_targets(tmp_path: Path) -> None:
    """A non-list ``targets`` value raises a clear TypeError.

    Args:
        tmp_path: Isolated project root.

    """
    _write_config(
        tmp_path=tmp_path,
        text='[tool.package.build]\ntargets = "linux"\n',
    )
    with pytest.raises(
        expected_exception=TypeError,
        match="targets must be a list of strings",
    ):
        load_config(root=tmp_path)


def test_load_config_rejects_non_string_list_members(tmp_path: Path) -> None:
    """Non-string list members raise a clear TypeError.

    Args:
        tmp_path: Isolated project root.

    """
    _write_config(
        tmp_path=tmp_path,
        text="[tool.package.build]\ntargets = [1, 2]\n",
    )
    with pytest.raises(
        expected_exception=TypeError,
        match="must be a list of strings",
    ):
        load_config(root=tmp_path)


def test_load_config_rejects_non_bool_enabled(tmp_path: Path) -> None:
    """A non-boolean ``enabled`` flag raises a clear TypeError.

    Args:
        tmp_path: Isolated project root.

    """
    _write_config(
        tmp_path=tmp_path,
        text='[tool.package.build]\nenabled = "yes"\n',
    )
    with pytest.raises(
        expected_exception=TypeError,
        match="enabled must be a boolean",
    ):
        load_config(root=tmp_path)


def test_load_config_rejects_non_string_output(tmp_path: Path) -> None:
    """A non-string ``output`` path raises a clear TypeError.

    Args:
        tmp_path: Isolated project root.

    """
    _write_config(
        tmp_path=tmp_path,
        text="[tool.package.bundle]\noutput = 42\n",
    )
    with pytest.raises(
        expected_exception=TypeError,
        match="output must be a string path",
    ):
        load_config(root=tmp_path)


def test_load_config_non_dict_tool_returns_defaults(tmp_path: Path) -> None:
    """A scalar ``tool`` table falls back to pipeline defaults.

    Args:
        tmp_path: Isolated project root.

    """
    _write_config(tmp_path=tmp_path, text='tool = "oops"\n')
    config: PipelineConfig = load_config(root=tmp_path)
    expect_equal(actual=config.bundle.enabled, expected=False)


def test_load_config_rejects_non_dict_package(tmp_path: Path) -> None:
    """A scalar ``[tool.package]`` raises a clear TypeError.

    Args:
        tmp_path: Isolated project root.

    """
    _write_config(tmp_path=tmp_path, text='[tool]\npackage = "oops"\n')
    with pytest.raises(
        expected_exception=TypeError,
        match=r"tool\.package. must be a table",
    ):
        load_config(root=tmp_path)


def test_load_config_rejects_non_dict_stage(tmp_path: Path) -> None:
    """A scalar ``[tool.package.build]`` raises a clear TypeError.

    Args:
        tmp_path: Isolated project root.

    """
    _write_config(tmp_path=tmp_path, text='[tool.package]\nbuild = "oops"\n')
    with pytest.raises(
        expected_exception=TypeError,
        match="stage settings must be tables",
    ):
        load_config(root=tmp_path)


def test_load_config_rejects_non_int_part_bytes(tmp_path: Path) -> None:
    """A non-integer ``part-bytes`` raises a clear TypeError.

    Args:
        tmp_path: Isolated project root.

    """
    _write_config(
        tmp_path=tmp_path,
        text='[tool.package.bundle]\npart-bytes = "big"\n',
    )
    with pytest.raises(
        expected_exception=TypeError,
        match="part-bytes must be an integer",
    ):
        load_config(root=tmp_path)


def test_load_config_rejects_bool_part_bytes(tmp_path: Path) -> None:
    """A boolean ``part-bytes`` raises the integer TypeError.

    Args:
        tmp_path: Isolated project root.

    """
    _write_config(
        tmp_path=tmp_path,
        text="[tool.package.bundle]\npart-bytes = true\n",
    )
    with pytest.raises(
        expected_exception=TypeError,
        match="part-bytes must be an integer",
    ):
        load_config(root=tmp_path)
