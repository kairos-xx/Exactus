# Copyright (c) 2026
"""Apply mapping directive steps in their fixed order."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .steps import (
    EachStep,
    FlattenStep,
    JoinStep,
    OmitStep,
    PickStep,
    SliceStep,
    SortStep,
    TemplateStep,
    UniqueStep,
    WhereStep,
)

if TYPE_CHECKING:
    from .directives import MappingHost, Step
    from .json_types import JsonValue


class Pipeline:
    """Run every activated directive step, in order.

    Order: where, sort, unique, slice, each, flatten, pick, omit, join,
    template.
    """

    def __init__(self) -> None:
        """Build the ordered step list."""
        self._steps: tuple[Step, ...] = (
            WhereStep(),
            SortStep(),
            UniqueStep(),
            SliceStep(),
            EachStep(),
            FlattenStep(),
            PickStep(),
            OmitStep(),
            JoinStep(),
            TemplateStep(),
        )

    def run(
        self,
        *,
        value: JsonValue,
        spec: dict[str, JsonValue],
        root: JsonValue,
        host: MappingHost,
    ) -> JsonValue:
        """Apply the steps that ``spec`` activates.

        Args:
            value: Resolved base value.
            spec: Mapping specification object.
            root: Whole document.
            host: Mapper services.

        Returns:
            The transformed value.

        """
        result: JsonValue = value
        for step in self._steps:
            if step.applies(spec=spec):
                result = step.apply(
                    value=result,
                    spec=spec,
                    root=root,
                    host=host,
                )
        return result
