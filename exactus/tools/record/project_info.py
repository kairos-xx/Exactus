# Copyright (c) 2026 Project contributors
"""Describe a project: its name, purpose, tags and authorship."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, cast, final

if TYPE_CHECKING:
    from collections.abc import Sequence

    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        max_name: Grouped module constant.
        max_text: Grouped module constant.
        max_short: Grouped module constant.
        max_tag: Grouped module constant.
        max_tags: Grouped module constant.

    """

    max_name: Final[int] = 80
    max_text: Final[int] = 2000
    max_short: Final[int] = 80
    max_tag: Final[int] = 32
    max_tags: Final[int] = 20


class ProjectInfoError(ValueError):
    """Raise when project details cannot be used."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectInfo:
    """Describe a project for people and for the project gallery.

    Everything but the name is optional. The address the project's tests
    start from is the target's URL, not a second copy kept here.

    Attributes:
        name: Display name, unique among the projects of a library.
        description: What the project tests and why.
        tags: Short labels the gallery filters by.
        author: Who owns the project.
        version: Version of the project, in whatever scheme the author uses.
        created_at: When the project was created, as an ISO 8601 UTC time.

    """

    name: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()
    author: str = ""
    version: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        """Reject details that are too long or malformed.

        Raises:
            ProjectInfoError: When a value exceeds its limit.

        """
        limits: tuple[tuple[str, str, int], ...] = (
            ("name", self.name, Constants.max_name),
            ("description", self.description, Constants.max_text),
            ("author", self.author, Constants.max_short),
            ("version", self.version, Constants.max_short),
        )
        for label, value, limit in limits:
            if len(value) > limit:
                msg: str = f"The project {label} is longer than {limit}."
                raise ProjectInfoError(msg)
        if len(self.tags) > Constants.max_tags:
            msg = f"A project has at most {Constants.max_tags} tags."
            raise ProjectInfoError(msg)
        if any(not tag or len(tag) > Constants.max_tag for tag in self.tags):
            msg = f"A tag is 1 to {Constants.max_tag} characters."
            raise ProjectInfoError(msg)


class ProjectInfoCodec:
    """Convert project details to and from JSON."""

    @classmethod
    def from_json_value(cls, *, value: JsonValue) -> ProjectInfo:
        """Read details saved in a project file.

        Args:
            value: A JSON object, or nothing for a project without details.

        Returns:
            The details; unknown or malformed fields are ignored.

        """
        if not isinstance(value, dict):
            return ProjectInfo()

        def text(key: str) -> str:
            """Read one trimmed string field.

            Args:
                key: JSON object key to read.

            Returns:
                Trimmed string, empty when absent or not a string.

            """
            item: JsonValue = value.get(key)
            return item.strip() if isinstance(item, str) else ""

        return ProjectInfo(
            name=text(key="name"),
            description=text(key="description"),
            tags=cls.clean_tags(tags=value.get("tags")),
            author=text(key="author"),
            version=text(key="version"),
            created_at=text(key="created_at"),
        )

    @classmethod
    def from_form(
        cls,
        *,
        data: dict[str, JsonValue],
        base: ProjectInfo,
    ) -> ProjectInfo:
        """Apply an editor form to existing details.

        Args:
            data: Form fields; absent fields keep their current value.
            base: The details being edited.

        Returns:
            The new details.

        """

        def text(key: str, current: str) -> str:
            """Read one trimmed form field with a fallback.

            Args:
                key: Form field name to read.
                current: Value kept when the field is absent.

            Returns:
                Trimmed string, or ``current`` when absent or not a
                string.

            """
            item: JsonValue = data.get(key)
            return item.strip() if isinstance(item, str) else current

        return ProjectInfo(
            name=text(key="name", current=base.name),
            description=text(key="description", current=base.description),
            tags=cls.clean_tags(tags=data["tags"])
            if "tags" in data
            else base.tags,
            author=text(key="author", current=base.author),
            version=text(key="version", current=base.version),
            created_at=base.created_at,
        )

    @staticmethod
    def clean_tags(*, tags: JsonValue) -> tuple[str, ...]:
        """Normalize tags typed by a person or read from a file.

        Args:
            tags: A list of text, or one comma-separated text.

        Returns:
            Trimmed tags without blanks or case-insensitive repeats.

        """
        items: Sequence[object] = (
            tags.split(sep=",")
            if isinstance(tags, str)
            else cast(typ="Sequence[object]", val=tags)
            if isinstance(tags, (list, tuple))
            else ()
        )
        seen: set[str] = set()
        clean: list[str] = []
        for item in items:
            tag: str = str(object=item).strip()
            if tag and tag.lower() not in seen:
                seen.add(tag.lower())
                clean.append(tag)
        return tuple(clean)

    @staticmethod
    def to_json_value(*, info: ProjectInfo) -> dict[str, JsonValue]:
        """Return the details as saved in the project file.

        Args:
            info: The project details.

        Returns:
            A JSON object.

        """
        return cast(
            typ="dict[str, JsonValue]",
            val={
                "name": info.name,
                "description": info.description,
                "tags": list(info.tags),
                "author": info.author,
                "version": info.version,
                "created_at": info.created_at,
            },
        )
