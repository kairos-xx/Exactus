# Copyright (c) 2026
"""Reshape a source document into a template context."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol

from .errors import MappingError
from .paths import Lookup, PathResolver
from .pipeline import Pipeline
from .predicates import Predicates

if TYPE_CHECKING:
    from .json_types import JsonValue


class Renderer(Protocol):
    """Render a named template with a context."""

    def __call__(self, *, name: str, context: dict[str, JsonValue]) -> str:
        """Render ``name``.

        Args:
            name: Template name relative to a configured root.
            context: Render context.

        Returns:
            The rendered text.

        """
        ...


class Mapper:
    """Evaluate mapping specifications."""

    def __init__(self, *, renderer: Renderer) -> None:
        """Store the template renderer.

        Args:
            renderer: Callable used by ``$template`` directives.

        """
        self._renderer = renderer
        self._pipeline = Pipeline()

    def render_name(self, *, name: str, context: dict[str, JsonValue]) -> str:
        """Render a named template through the configured renderer.

        Args:
            name: Template name.
            context: Render context.

        Returns:
            The rendered text.

        """
        return self._renderer(name=name, context=context)

    def context(
        self,
        *,
        source: JsonValue,
        mapping: dict[str, JsonValue] | None,
    ) -> dict[str, JsonValue]:
        """Build the template context.

        Args:
            source: Source document (usually ``result.json``).
            mapping: Mapping from context names to specifications, or
                ``None`` to expose the source directly.

        Returns:
            The context, always including the original as ``source``.

        """
        if mapping is None:
            base: dict[str, JsonValue] = (
                dict(source) if isinstance(source, dict) else {"data": source}
            )
        else:
            base = {
                key: self.map_value(spec=spec, current=source, root=source)
                for key, spec in mapping.items()
            }
        base["source"] = source
        return base

    def map_value(
        self,
        *,
        spec: JsonValue,
        current: JsonValue,
        root: JsonValue,
    ) -> JsonValue:
        """Map ``spec`` and discard the found flag.

        Args:
            spec: Mapping specification.
            current: Value relative paths start from.
            root: Whole document.

        Returns:
            The mapped value, ``None`` when nothing was found.

        """
        return self.map(spec=spec, current=current, root=root).value

    def map(
        self,
        *,
        spec: JsonValue,
        current: JsonValue,
        root: JsonValue,
    ) -> Lookup:
        """Evaluate one mapping specification.

        Args:
            spec: A path string, list, plain object, or ``$`` directive
                object.
            current: Value relative paths start from.
            root: Whole document.

        Returns:
            The mapped value, or a miss when a path was absent.

        """
        if isinstance(spec, str):
            return PathResolver.resolve(current=current, path=spec, root=root)
        if isinstance(spec, list):
            return Lookup.hit(
                value=[
                    self.map_value(spec=item, current=current, root=root)
                    for item in spec
                ],
            )
        if not isinstance(spec, dict):
            return Lookup.hit(value=spec)
        if not any(key.startswith("$") for key in spec):
            return Lookup.hit(
                value={
                    key: self.map_value(spec=item, current=current, root=root)
                    for key, item in spec.items()
                },
            )
        return self._directive(spec=spec, current=current, root=root)

    @staticmethod
    def _operands(*, spec: dict[str, JsonValue], key: str) -> list[JsonValue]:
        """Require a directive operand list.

        Args:
            spec: Directive object.
            key: Directive name.

        Returns:
            The operand list.

        Raises:
            MappingError: The operand is not a list.

        """
        operands: JsonValue = spec[key]
        if not isinstance(operands, list):
            msg: str = f"{key} requires a list"
            raise MappingError(msg)
        return operands

    @staticmethod
    def _base(
        *,
        spec: dict[str, JsonValue],
        current: JsonValue,
        root: JsonValue,
    ) -> Lookup:
        """Resolve ``$path`` with ``$default`` / ``$required`` handling.

        Args:
            spec: Directive object.
            current: Value relative paths start from.
            root: Whole document.

        Returns:
            The base value, or a miss.

        Raises:
            MappingError: A required path is absent.

        """
        path: str = str(object=spec.get("$path", "."))
        lookup: Lookup = PathResolver.resolve(
            current=current,
            path=path,
            root=root,
        )
        if not lookup.found:
            if "$default" in spec:
                return Lookup.hit(value=spec["$default"])
            if spec.get("$required"):
                msg: str = f"Required path missing: {path}"
                raise MappingError(msg)
            return Lookup.miss()
        if (
            lookup.value is None
            and spec.get("$default_on_null")
            and "$default" in spec
        ):
            return Lookup.hit(value=spec["$default"])
        return lookup

    def _directive(
        self,
        *,
        spec: dict[str, JsonValue],
        current: JsonValue,
        root: JsonValue,
    ) -> Lookup:
        """Evaluate a ``$`` directive object.

        Args:
            spec: Directive object.
            current: Value relative paths start from.
            root: Whole document.

        Returns:
            The directive result.

        """
        if "$literal" in spec:
            base: Lookup = Lookup.hit(value=spec["$literal"])
        else:
            early: Lookup | None = self._early(
                spec=spec,
                current=current,
                root=root,
            )
            if early is not None:
                return early
            base = self._base(spec=spec, current=current, root=root)
        if not base.found:
            return base
        return Lookup.hit(
            value=self._pipeline.run(
                value=base.value,
                spec=spec,
                root=root,
                host=self,
            ),
        )

    def _early(
        self,
        *,
        spec: dict[str, JsonValue],
        current: JsonValue,
        root: JsonValue,
    ) -> Lookup | None:
        """Evaluate directives that bypass the pipeline.

        Args:
            spec: Directive object.
            current: Value relative paths start from.
            root: Whole document.

        Returns:
            The result of ``$when``, ``$coalesce`` or ``$merge``, else
            ``None``.

        Raises:
            MappingError: A merged value is not an object, or an operand
                is not a list.

        """
        if "$when" in spec:
            branch: Literal["$else", "$then"] = (
                "$then"
                if Predicates.evaluate(
                    spec=spec["$when"],
                    current=current,
                    root=root,
                )
                else "$else"
            )
            return self.map(spec=spec.get(branch), current=current, root=root)
        if "$coalesce" in spec:
            for candidate in self._operands(spec=spec, key="$coalesce"):
                found: Lookup = self.map(
                    spec=candidate,
                    current=current,
                    root=root,
                )
                if found.found and found.value is not None:
                    return found
            return Lookup.hit(value=spec.get("$default"))
        if "$merge" in spec:
            merged: dict[str, JsonValue] = {}
            for candidate in self._operands(spec=spec, key="$merge"):
                part: Lookup = self.map(
                    spec=candidate,
                    current=current,
                    root=root,
                )
                if not part.found:
                    continue
                if not isinstance(part.value, dict):
                    msg: str = "$merge values must be objects"
                    raise MappingError(msg)
                merged.update(part.value)
            return Lookup.hit(value=merged)
        return None
