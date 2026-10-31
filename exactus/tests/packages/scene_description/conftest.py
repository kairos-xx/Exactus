# Copyright (c) 2026
"""Shared fixtures and fakes for the scene_description tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from exactus.packages.scene_description.models import JsonValue


def element(
    *,
    selector: str = "#node",
    frame: dict[str, JsonValue] | None = None,
    visual_cause_selector: JsonValue = None,
    **fields: JsonValue,
) -> dict[str, JsonValue]:
    """Build one scene-graph element entry.

    Args:
        selector: Stable selector stored on the element.
        frame: Optional viewport-frame geometry.
        visual_cause_selector: Optional Visual Cause selector alias.
        fields: Evidence fields such as ``name``, ``text``, ``tag``,
            or ``role`` stored verbatim on the record.

    Returns:
        Serializable element record matching the descriptor output shape.

    """
    record: dict[str, JsonValue] = {
        "selector": selector,
        "name": None,
        "text": None,
        "tag": "button",
        "role": "button",
        **fields,
    }
    if visual_cause_selector is not None:
        record["visualCauseSelector"] = visual_cause_selector
    if frame is not None:
        record["visual"] = {"viewportFrame": frame}
    return record


def scene(
    *,
    elements: dict[str, dict[str, JsonValue]] | None = None,
    metadata: JsonValue = None,
    reference: JsonValue = None,
) -> dict[str, JsonValue]:
    """Build one descriptor scene manifest.

    Args:
        elements: Element records keyed by registry identifier.
        metadata: Optional scene metadata block.
        reference: Optional scene reference block.

    Returns:
        Serializable scene manifest.

    """
    element_map: dict[str, JsonValue] = {}
    if elements is not None:
        element_map.update(elements)
    return {
        "elements": element_map,
        "metadata": metadata or {},
        "reference": reference or {},
    }


def report(*, trees: JsonValue = None) -> dict[str, JsonValue]:
    """Build a minimal Visual Cause report.

    Args:
        trees: Optional ``change_trees`` payload; omitted when ``None``.

    Returns:
        Serializable report skeleton.

    """
    document: dict[str, JsonValue] = {"schema": "visual-cause/v1"}
    if trees is not None:
        document["change_trees"] = trees
    return document


class FakePage:
    """In-memory ``PageLike`` fake recording browser interactions.

    Attributes:
        descriptor_installed: Whether evaluate reports a Descriptor global.
        evaluate_result: Value returned for non-availability expressions.
        script_tags: Sources passed to ``add_script_tag``.
        expressions: Every evaluated expression.
        arguments: Payloads passed alongside evaluated expressions.

    """

    descriptor_installed: bool = False
    evaluate_result: JsonValue = None

    def __init__(self) -> None:
        """Initialize empty interaction journals."""
        self.script_tags: list[str] = []
        self.expressions: list[str] = []
        self.arguments: list[JsonValue] = []

    def add_script_tag(self, *, content: str) -> JsonValue:
        """Record an injected script source.

        Args:
            content: JavaScript source delivered by the descriptor.

        Returns:
            A sentinel handle mirroring the Playwright contract.

        """
        self.script_tags.append(content)
        return {"content": content}

    def evaluate(self, *, expression: str, arg: JsonValue = None) -> JsonValue:
        """Record an evaluation and return the configured result.

        Args:
            expression: JavaScript expression text.
            arg: Optional evaluation payload.

        Returns:
            The scripted availability or descriptor result.

        """
        self.expressions.append(expression)
        self.arguments.append(arg)
        if "typeof globalThis.Descriptor" in expression:
            return self.descriptor_installed
        return self.evaluate_result


@pytest.fixture
def make_scene() -> Callable[..., dict[str, JsonValue]]:
    """Expose the scene manifest builder as a fixture.

    Returns:
        Builder producing descriptor scene manifests.

    """
    return scene
