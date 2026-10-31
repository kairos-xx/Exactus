# Copyright (c) 2026
"""Tests for the DescriptionOptions model and JSON aliases."""

from dataclasses import FrozenInstanceError

from exactus.packages.scene_description import DescriptionOptions
from exactus.tests.packages.scene_description.support import (
    expect_equal,
    expect_raises,
    expect_true,
)


def test_browser_options_defaults() -> None:
    """Default flags serialize with the browser camelCase API."""
    options: DescriptionOptions = DescriptionOptions()
    expect_equal(
        actual=options.browser_options(),
        expected={
            "includeComputedStyle": False,
            "includeRelationships": True,
            "inferSpatialLayouts": True,
            "includeBinary": False,
            "includeElementScreenshots": False,
        },
    )


def test_browser_options_reflects_overrides() -> None:
    """Non-default flags flow through to the browser payload."""
    options: DescriptionOptions = DescriptionOptions(
        include_computed_style=True,
        include_relationships=False,
        infer_spatial_layouts=False,
        include_binary=True,
        include_element_screenshots=True,
    )
    expect_equal(
        actual=options.browser_options(),
        expected={
            "includeComputedStyle": True,
            "includeRelationships": False,
            "inferSpatialLayouts": False,
            "includeBinary": True,
            "includeElementScreenshots": True,
        },
    )


def test_options_are_frozen() -> None:
    """The options dataclass rejects attribute mutation."""
    options: DescriptionOptions = DescriptionOptions()
    expect_raises(
        kind=FrozenInstanceError,
        call=lambda: setattr(options, "include_binary", True),
    )


def test_package_exports() -> None:
    """Every documented export resolves on the package namespace."""
    name: str
    for name in (
        scene_description := __import__(
            name="exactus.packages.scene_description",
            fromlist=["__all__"],
        )
    ).__all__:
        expect_true(
            condition=hasattr(scene_description, name),
            message=f"missing export {name}",
        )
