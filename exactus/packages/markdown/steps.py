# Copyright (c) 2026
"""Concrete mapping directive steps."""

from __future__ import annotations

from functools import partial
from json import dumps
from typing import TYPE_CHECKING, ClassVar

from .directives import Step
from .errors import MappingError
from .paths import PathResolver
from .predicates import Predicates

if TYPE_CHECKING:
    from .directives import MappingHost
    from .json_types import JsonValue


class WhereStep(Step):
    """``$where``: keep list items matching a predicate.

    Attributes:
        keys: Directive keys that select this step.

    """

    keys: ClassVar[tuple[str, ...]] = ("$where",)

    def apply(
        self,
        *,
        value: JsonValue,
        spec: dict[str, JsonValue],
        root: JsonValue,
        host: MappingHost,
    ) -> JsonValue:
        """Filter a list.

        Args:
            value: List to filter.
            spec: Specification holding ``$where``.
            root: Whole document.
            host: Unused.

        Returns:
            The items whose predicate holds.

        """
        del host
        return [
            item
            for item in self.items(value=value, directive="$where")
            if Predicates.evaluate(
                spec=spec["$where"],
                current=item,
                root=root,
            )
        ]


class SortStep(Step):
    """``$sort_by`` / ``$reverse``: order a list by a path.

    Numbers sort by value and come first; everything else sorts by its
    casefolded text.

    Attributes:
        keys: Directive keys that select this step.

    """

    keys: ClassVar[tuple[str, ...]] = ("$sort_by",)

    def apply(
        self,
        *,
        value: JsonValue,
        spec: dict[str, JsonValue],
        root: JsonValue,
        host: MappingHost,
    ) -> JsonValue:
        """Sort a list.

        Args:
            value: List to sort.
            spec: Specification with ``$sort_by`` and ``$reverse``.
            root: Whole document.
            host: Unused.

        Returns:
            The sorted list.

        """
        del host
        key: partial[tuple[int, float, str]] = partial(
            self._key,
            path=str(object=spec["$sort_by"]),
            root=root,
        )
        return sorted(
            self.items(value=value, directive="$sort_by"),
            key=key,
            reverse=bool(spec.get("$reverse")),
        )

    @staticmethod
    def _key(
        item: JsonValue,
        *,
        path: str,
        root: JsonValue,
    ) -> tuple[int, float, str]:
        """Build the sort key of one item.

        Args:
            item: List item.
            path: Path to the sort value.
            root: Whole document.

        Returns:
            A tuple ordering numbers before text.

        """
        found: JsonValue = PathResolver.resolve(
            current=item,
            path=path,
            root=root,
        ).value
        if isinstance(found, int | float) and not isinstance(found, bool):
            return (0, float(found), "")
        return (1, 0.0, str(object=found).casefold())


class UniqueStep(Step):
    """``$unique`` / ``$unique_by``: drop duplicate list items.

    Attributes:
        keys: Directive keys that select this step.

    """

    keys: ClassVar[tuple[str, ...]] = ("$unique", "$unique_by")

    def applies(self, *, spec: dict[str, JsonValue]) -> bool:
        """Report whether deduplication was requested.

        Args:
            spec: Mapping specification object.

        Returns:
            Whether ``$unique`` is truthy or ``$unique_by`` is set.

        """
        return bool(spec.get("$unique")) or "$unique_by" in spec

    def apply(
        self,
        *,
        value: JsonValue,
        spec: dict[str, JsonValue],
        root: JsonValue,
        host: MappingHost,
    ) -> JsonValue:
        """Deduplicate a list, keeping first occurrences.

        Args:
            value: List to deduplicate.
            spec: Specification with ``$unique`` or ``$unique_by``.
            root: Whole document.
            host: Unused.

        Returns:
            The list without duplicates.

        """
        del host
        path: JsonValue = spec.get("$unique_by")
        seen: set[str] = set()
        kept: list[JsonValue] = []
        for item in self.items(value=value, directive="$unique"):
            chosen: JsonValue = (
                item
                if path is None
                else PathResolver.resolve(
                    current=item,
                    path=str(object=path),
                    root=root,
                ).value
            )
            marker: str = dumps(obj=chosen, ensure_ascii=False, sort_keys=True)
            if marker not in seen:
                seen.add(marker)
                kept.append(item)
        return kept


class SliceStep(Step):
    """``$offset`` / ``$limit``: window a list.

    Attributes:
        keys: Directive keys that select this step.

    """

    keys: ClassVar[tuple[str, ...]] = ("$offset", "$limit")

    def apply(
        self,
        *,
        value: JsonValue,
        spec: dict[str, JsonValue],
        root: JsonValue,
        host: MappingHost,
    ) -> JsonValue:
        """Slice a list.

        Args:
            value: List to slice.
            spec: Specification with ``$offset`` and ``$limit``.
            root: Unused.
            host: Unused.

        Returns:
            The requested window.

        """
        del root, host
        items: list[JsonValue] = self.items(
            value=value,
            directive="$offset/$limit",
        )
        offset: int = self.integer(
            value=spec.get("$offset"),
            directive="$offset",
            default=0,
        )
        limit: JsonValue = spec.get("$limit")
        if limit is None:
            return items[offset:]
        count: int = self.integer(value=limit, directive="$limit", default=0)
        return items[offset : offset + count]


class EachStep(Step):
    """``$each``: map every list item through a nested specification.

    Attributes:
        keys: Directive keys that select this step.

    """

    keys: ClassVar[tuple[str, ...]] = ("$each",)

    def apply(
        self,
        *,
        value: JsonValue,
        spec: dict[str, JsonValue],
        root: JsonValue,
        host: MappingHost,
    ) -> JsonValue:
        """Project each item.

        Args:
            value: List to project.
            spec: Specification holding ``$each``.
            root: Whole document.
            host: Mapper used for the nested specification.

        Returns:
            The projected list.

        """
        return [
            host.map_value(spec=spec["$each"], current=item, root=root)
            for item in self.items(value=value, directive="$each")
        ]


class FlattenStep(Step):
    """``$flatten``: splice nested lists one level.

    Attributes:
        keys: Directive keys that select this step.

    """

    keys: ClassVar[tuple[str, ...]] = ("$flatten",)

    def applies(self, *, spec: dict[str, JsonValue]) -> bool:
        """Report whether flattening was requested.

        Args:
            spec: Mapping specification object.

        Returns:
            Whether ``$flatten`` is truthy.

        """
        return bool(spec.get("$flatten"))

    def apply(
        self,
        *,
        value: JsonValue,
        spec: dict[str, JsonValue],
        root: JsonValue,
        host: MappingHost,
    ) -> JsonValue:
        """Flatten one level.

        Args:
            value: List of lists and scalars.
            spec: Unused.
            root: Unused.
            host: Unused.

        Returns:
            The flattened list.

        """
        del spec, root, host
        flat: list[JsonValue] = []
        for item in self.items(value=value, directive="$flatten"):
            if isinstance(item, list):
                flat.extend(item)
            else:
                flat.append(item)
        return flat


class PickStep(Step):
    """``$pick``: keep only the named keys of an object.

    Attributes:
        keys: Directive keys that select this step.

    """

    keys: ClassVar[tuple[str, ...]] = ("$pick",)

    def apply(
        self,
        *,
        value: JsonValue,
        spec: dict[str, JsonValue],
        root: JsonValue,
        host: MappingHost,
    ) -> JsonValue:
        """Select keys.

        Args:
            value: Object to reduce.
            spec: Specification holding ``$pick``.
            root: Unused.
            host: Unused.

        Returns:
            The object with only the present picked keys.

        """
        del root, host
        members: dict[str, JsonValue] = self.members(
            value=value,
            directive="$pick",
        )
        names: list[JsonValue] = self.items(
            value=spec["$pick"],
            directive="$pick",
        )
        return {key: members[key] for key in map(str, names) if key in members}


class OmitStep(Step):
    """``$omit``: drop the named keys of an object.

    Attributes:
        keys: Directive keys that select this step.

    """

    keys: ClassVar[tuple[str, ...]] = ("$omit",)

    def apply(
        self,
        *,
        value: JsonValue,
        spec: dict[str, JsonValue],
        root: JsonValue,
        host: MappingHost,
    ) -> JsonValue:
        """Remove keys.

        Args:
            value: Object to reduce.
            spec: Specification holding ``$omit``.
            root: Unused.
            host: Unused.

        Returns:
            The object without the omitted keys.

        """
        del root, host
        members: dict[str, JsonValue] = self.members(
            value=value,
            directive="$omit",
        )
        omitted: set[str] = set(
            map(str, self.items(value=spec["$omit"], directive="$omit")),
        )
        return {k: v for k, v in members.items() if k not in omitted}


class JoinStep(Step):
    """``$join``: join list items into one string.

    Attributes:
        keys: Directive keys that select this step.

    """

    keys: ClassVar[tuple[str, ...]] = ("$join",)

    def apply(
        self,
        *,
        value: JsonValue,
        spec: dict[str, JsonValue],
        root: JsonValue,
        host: MappingHost,
    ) -> JsonValue:
        """Join items.

        Args:
            value: List to join.
            spec: Specification holding the separator in ``$join``.
            root: Unused.
            host: Unused.

        Returns:
            The joined string.

        """
        del root, host
        items: list[JsonValue] = self.items(value=value, directive="$join")
        return str(object=spec["$join"]).join(
            str(object=item) for item in items
        )


class TemplateStep(Step):
    """``$template``: render a named template with the value.

    Attributes:
        keys: Directive keys that select this step.

    """

    keys: ClassVar[tuple[str, ...]] = ("$template",)

    def apply(
        self,
        *,
        value: JsonValue,
        spec: dict[str, JsonValue],
        root: JsonValue,
        host: MappingHost,
    ) -> JsonValue:
        """Render the template once, or once per list item.

        Args:
            value: Value (or list, with ``$template_each``) to render.
            spec: Specification with ``$template``, ``$as``, ``$with``,
                ``$template_each`` and ``$separator``.
            root: Whole document, exposed as ``source``.
            host: Mapper that resolves ``$with`` and renders.

        Returns:
            The rendered text.

        """
        alias: str = str(object=spec.get("$as", "item"))
        name: str = str(object=spec["$template"])
        extra: dict[str, JsonValue] = self._extra(
            value=value,
            spec=spec,
            root=root,
            host=host,
        )
        if not spec.get("$template_each"):
            return host.render_name(
                name=name,
                context={"source": root, alias: value, **extra},
            )
        separator: str = str(object=spec.get("$separator", ""))
        items: list[JsonValue] = self.items(
            value=value,
            directive="$template_each",
        )
        return separator.join(
            host.render_name(
                name=name,
                context={"source": root, alias: item, "index": index, **extra},
            )
            for index, item in enumerate(iterable=items)
        )

    @staticmethod
    def _extra(
        *,
        value: JsonValue,
        spec: dict[str, JsonValue],
        root: JsonValue,
        host: MappingHost,
    ) -> dict[str, JsonValue]:
        """Resolve the ``$with`` extras.

        Args:
            value: Value the extras map relative to.
            spec: Specification possibly holding ``$with``.
            root: Whole document.
            host: Mapper used for each extra.

        Returns:
            Extra template variables.

        Raises:
            MappingError: ``$with`` is not an object.

        """
        extras: JsonValue = spec.get("$with", {})
        if not isinstance(extras, dict):
            msg: str = "$with requires an object"
            raise MappingError(msg)
        return {
            key: host.map_value(spec=item, current=value, root=root)
            for key, item in extras.items()
        }
