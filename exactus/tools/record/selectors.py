# Copyright (c) 2026 Project contributors
"""Reusable selectors, targeting modes and pacing for recorded actions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from json import JSONDecodeError, dumps, loads
from os import fsync
from pathlib import Path
from re import fullmatch
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Final, cast, final

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        file_name: Grouped module constant.
        version: Grouped module constant.
        name_pattern: Grouped module constant.
        max_name_length: Grouped module constant.
        minimum_poll_ms: Grouped module constant.

    """

    file_name: Final[str] = "selectors.pwflow.json"
    version: Final[int] = 1
    name_pattern: Final[str] = "[A-Za-z][A-Za-z0-9_]*"
    max_name_length: Final[int] = 48
    minimum_poll_ms: Final[int] = 10


class SelectorError(ValueError):
    """Report an invalid selector, pace or selectors document."""


class TargetScope(StrEnum):
    """Say which of the matched elements an action applies to.

    Attributes:
        FIRST: Only the first match, in the selector's order.
        ALL: Every match.

    """

    FIRST = "first"
    ALL = "all"


class RunMode(StrEnum):
    """Say how an action treats several targets.

    Attributes:
        SEQUENTIAL: One target after another, in the selector's order.
        PARALLEL: All targets at once; only valid for ``free`` lane kinds.

    """

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Pace:
    """Describe a pause: a fixed delay and/or a condition to wait for.

    Attributes:
        delay_ms: Fixed pause before the condition is checked.
        until: Condition expression to wait for, in the edge-condition
            language; ``None`` waits for nothing.
        poll_ms: Interval between checks of ``until``.
        timeout_ms: Longest wait for ``until`` before the gate fails.

    """

    delay_ms: int = 0
    until: str | None = None
    poll_ms: int = 100
    timeout_ms: int = 5000

    def __post_init__(self) -> None:
        """Reject values that cannot be waited for.

        Raises:
            SelectorError: When a duration is out of range or blank.

        """
        if self.delay_ms < 0 or self.timeout_ms < 0:
            msg: str = "Pace durations cannot be negative."
            raise SelectorError(msg)
        if self.poll_ms < Constants.minimum_poll_ms:
            msg = (
                "Pace polling must be at least "
                f"{Constants.minimum_poll_ms} ms."
            )
            raise SelectorError(msg)
        if self.until is not None and (not self.until.strip()):
            msg = "A pace condition cannot be blank."
            raise SelectorError(msg)


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class ValidatedOn:
    """Record where a selector was last tested and what it found.

    Attributes:
        url: Page address the selector was tested on.
        at: UTC timestamp of the test, ISO 8601.
        matches: Number of elements it matched.

    """

    url: str
    at: str
    matches: int

    def __post_init__(self) -> None:
        """Reject empty evidence.

        Raises:
            SelectorError: When the address or count is invalid.

        """
        if not self.url or self.matches < 0:
            msg: str = "Validation evidence needs an address and a count."
            raise SelectorError(msg)


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class SelectorDef:
    """Describe one project-wide named selector.

    Attributes:
        selector_id: Stable identifier actions refer to.
        name: Unique, renameable name; also the probe and definition name.
        expression: ExtendedSelector expression, the only source of truth.
        expected_count: Exact match count the selector must find, or
            ``None`` for one or more.
        checks: Extended predicates every match must satisfy.
        validated_on: Pages the selector was last tested on.

    """

    selector_id: str
    name: str
    expression: str
    expected_count: int | None = 1
    checks: tuple[str, ...] = ()
    validated_on: tuple[ValidatedOn, ...] = ()

    def __post_init__(self) -> None:
        """Reject selectors that cannot be resolved.

        Raises:
            SelectorError: When a field is empty or out of range.

        """
        if not self.selector_id.strip():
            msg: str = "A selector needs an identifier."
            raise SelectorError(msg)
        if (
            len(self.name) > Constants.max_name_length
            or fullmatch(pattern=Constants.name_pattern, string=self.name)
            is None
        ):
            msg = (
                "Selector names start with a letter and use letters, digits "
                "and underscores only."
            )
            raise SelectorError(msg)
        if not self.expression.strip():
            msg = "A selector needs an expression."
            raise SelectorError(msg)
        if self.expected_count is not None and self.expected_count < 0:
            msg = "The expected match count cannot be negative."
            raise SelectorError(msg)
        if any(not check.strip() for check in self.checks):
            msg = "Selector checks cannot be blank."
            raise SelectorError(msg)


def validate_selectors(*, selectors: tuple[SelectorDef, ...]) -> None:
    """Require unique identifiers and unique names.

    Args:
        selectors: Every selector in a project.

    Raises:
        SelectorError: When two selectors share an identifier or a name.

    """
    ids: set[str] = {item.selector_id for item in selectors}
    names: set[str] = {item.name for item in selectors}
    if len(ids) != len(selectors):
        msg: str = "Selectors must have unique identifiers."
        raise SelectorError(msg)
    if len(names) != len(selectors):
        msg = "Selectors must have unique names."
        raise SelectorError(msg)


@final
class SelectorCodec:
    """Read and write ``selectors.pwflow.json`` and pace records."""

    @classmethod
    def to_json_value(cls, *, selectors: tuple[SelectorDef, ...]) -> JsonValue:
        """Return the selectors document.

        Args:
            selectors: Every selector in a project.

        Returns:
            JSON object with a version and the selector list.

        """
        return {
            "version": Constants.version,
            "selectors": [
                cls.selector_to_json(item=item) for item in selectors
            ],
        }

    @classmethod
    def from_json_value(cls, *, value: JsonValue) -> tuple[SelectorDef, ...]:
        """Parse a selectors document.

        Args:
            value: Decoded JSON.

        Returns:
            The selectors in file order.

        Raises:
            SelectorError: When the document is malformed or inconsistent.

        """
        if not isinstance(value, dict):
            msg: str = "The selectors document must be an object."
            raise SelectorError(msg)
        if value.get("version") != Constants.version:
            msg = "Unsupported selectors document version."
            raise SelectorError(msg)
        items: JsonValue = value.get("selectors")
        if not isinstance(items, list):
            msg = "The selectors document needs a selectors list."
            raise SelectorError(msg)
        selectors: tuple[SelectorDef, ...] = tuple(
            cls.selector_from_json(value=item) for item in items
        )
        validate_selectors(selectors=selectors)
        return selectors

    @classmethod
    def selector_from_json(cls, *, value: JsonValue) -> SelectorDef:
        """Parse one selector.

        Args:
            value: Decoded JSON object.

        Returns:
            The selector.

        Raises:
            SelectorError: When a field has the wrong type.

        """
        if not isinstance(value, dict):
            msg: str = "Each selector must be an object."
            raise SelectorError(msg)
        checks: JsonValue = value.get("checks", [])
        seen: JsonValue = value.get("validated_on", [])
        count: JsonValue = value.get("expected_count", 1)
        if not isinstance(checks, list) or not isinstance(seen, list):
            msg = "Selector checks and validations must be lists."
            raise SelectorError(msg)
        if count is not None and (
            isinstance(count, bool) or not isinstance(count, int)
        ):
            msg = "The expected match count must be an integer or null."
            raise SelectorError(msg)
        return SelectorDef(
            selector_id=cls._text(value=value, key="selector_id"),
            name=cls._text(value=value, key="name"),
            expression=cls._text(value=value, key="expression"),
            expected_count=count,
            checks=tuple(cls._string(value=item) for item in checks),
            validated_on=tuple(cls._validated(value=item) for item in seen),
        )

    @classmethod
    def pace_from_json(cls, *, value: JsonValue) -> Pace | None:
        """Parse a pace.

        Args:
            value: Decoded JSON object, or ``None``.

        Returns:
            The pace, or ``None`` when absent.

        Raises:
            SelectorError: When a field has the wrong type.

        """
        if value is None:
            return None
        if not isinstance(value, dict):
            msg: str = "A pace must be an object."
            raise SelectorError(msg)
        until: JsonValue = value.get("until")
        if until is not None and (not isinstance(until, str)):
            msg = "A pace condition must be text."
            raise SelectorError(msg)
        return Pace(
            delay_ms=cls._number(value=value, key="delay_ms", default=0),
            until=until,
            poll_ms=cls._number(value=value, key="poll_ms", default=100),
            timeout_ms=cls._number(
                value=value,
                key="timeout_ms",
                default=5000,
            ),
        )

    @classmethod
    def save(cls, *, path: Path, selectors: tuple[SelectorDef, ...]) -> None:
        """Write the selectors document atomically.

        Args:
            path: Destination file.
            selectors: Every selector in a project.

        """
        validate_selectors(selectors=selectors)
        data: str = (
            dumps(
                obj=cls.to_json_value(selectors=selectors),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        temporary: str | None = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=".selectors-",
                delete=False,
            ) as stream:
                temporary = stream.name
                _ = stream.write(data)
                stream.flush()
                fsync(fd=stream.fileno())
            Path(temporary).replace(target=path)
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)

    @classmethod
    def load(cls, *, path: Path) -> tuple[SelectorDef, ...]:
        """Read a selectors document.

        Args:
            path: Source file.

        Returns:
            The selectors in file order.

        Raises:
            SelectorError: When the file cannot be read or parsed.

        """
        try:
            value: JsonValue = cast(
                typ="JsonValue",
                val=loads(s=path.read_text(encoding="utf-8")),
            )
        except (JSONDecodeError, OSError) as error:
            raise SelectorError(str(object=error)) from error
        return cls.from_json_value(value=value)

    @staticmethod
    def selector_to_json(*, item: SelectorDef) -> JsonValue:
        """Return one selector as JSON.

        Args:
            item: Selector to encode.

        Returns:
            JSON object.

        """
        return {
            "selector_id": item.selector_id,
            "name": item.name,
            "expression": item.expression,
            "expected_count": item.expected_count,
            "checks": list(item.checks),
            "validated_on": [
                {"url": seen.url, "at": seen.at, "matches": seen.matches}
                for seen in item.validated_on
            ],
        }

    @staticmethod
    def pace_to_json(*, pace: Pace | None) -> JsonValue:
        """Return a pace as JSON.

        Args:
            pace: Pace to encode, or ``None``.

        Returns:
            JSON object, or ``None``.

        """
        if pace is None:
            return None
        return {
            "delay_ms": pace.delay_ms,
            "until": pace.until,
            "poll_ms": pace.poll_ms,
            "timeout_ms": pace.timeout_ms,
        }

    @classmethod
    def _validated(cls, *, value: JsonValue) -> ValidatedOn:
        """Parse one validation record.

        Args:
            value: Decoded JSON object.

        Returns:
            The record.

        Raises:
            SelectorError: When the record is malformed.

        """
        if not isinstance(value, dict):
            msg: str = "Each validation record must be an object."
            raise SelectorError(msg)
        return ValidatedOn(
            url=cls._text(value=value, key="url"),
            at=cls._text(value=value, key="at"),
            matches=cls._number(value=value, key="matches", default=0),
        )

    @staticmethod
    def _text(*, value: dict[str, JsonValue], key: str) -> str:
        """Return a required string field.

        Args:
            value: JSON object.
            key: Field name.

        Returns:
            The text.

        Raises:
            SelectorError: When the field is missing or not text.

        """
        item: JsonValue = value.get(key)
        if not isinstance(item, str):
            msg: str = f"Expected '{key}' to be text."
            raise SelectorError(msg)
        return item

    @staticmethod
    def _string(*, value: JsonValue) -> str:
        """Return a list item that must be text.

        Args:
            value: JSON list item.

        Returns:
            The text.

        Raises:
            SelectorError: When the item is not text.

        """
        if not isinstance(value, str):
            msg: str = "Selector checks must be text."
            raise SelectorError(msg)
        return value

    @staticmethod
    def _number(*, value: dict[str, JsonValue], key: str, default: int) -> int:
        """Return an optional integer field.

        Args:
            value: JSON object.
            key: Field name.
            default: Result when the field is absent.

        Returns:
            The integer.

        Raises:
            SelectorError: When the field is present but not an integer.

        """
        item: JsonValue = value.get(key, default)
        if isinstance(item, bool) or not isinstance(item, int):
            msg: str = f"Expected '{key}' to be an integer."
            raise SelectorError(msg)
        return item
