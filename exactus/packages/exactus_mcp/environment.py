# Copyright (c) 2026 João Lopes.
"""Minimal deterministic ``.env`` loading for command-line entry points."""

from collections.abc import MutableMapping
from pathlib import Path
from typing import Final, final


@final
class Constants:
    """Group module-level constants.

    Attributes:
        env_file_name: Grouped module constant.
        export_prefix: Grouped module constant.
        quoted_value_length: Grouped module constant.

    """

    env_file_name: Final[str] = ".env"
    export_prefix: Final[str] = "export "
    quoted_value_length: Final[int] = 2


class EnvironmentLoader:
    """Merge project ``.env`` values without overriding process variables."""

    @classmethod
    def load(
        cls,
        *,
        values: MutableMapping[str, str],
        directory: Path | None = None,
    ) -> Path | None:
        """Load the nearest project ``.env`` file into ``values``.

        Existing values always win, so shell/CI configuration has higher
        precedence than the file. Search starts at ``directory`` (or the
        current working directory) and walks toward the filesystem root.

        Args:
            values: Mutable environment-like mapping to augment.
            directory: Optional search starting directory.

        Returns:
            Loaded ``.env`` path, or ``None`` when no file exists.

        """
        start: Path = (directory or Path.cwd()).resolve()
        for candidate_directory in (start, *start.parents):
            candidate: Path = candidate_directory / Constants.env_file_name
            if candidate.is_file():
                cls._merge(values=values, path=candidate)
                return candidate
        return None

    @classmethod
    def _merge(cls, *, values: MutableMapping[str, str], path: Path) -> None:
        """Merge supported dotenv assignments from one file.

        Args:
            values: Mutable environment-like mapping to augment.
            path: Dotenv file to parse.

        """
        content: str = path.read_text(encoding="utf-8")
        for raw_line in content.splitlines():
            assignment: tuple[str, str] | None = cls._parse_line(line=raw_line)
            if assignment is None:
                continue
            key, value = assignment
            existing: str = values.setdefault(key, value)
            del existing

    @staticmethod
    def _parse_line(*, line: str) -> tuple[str, str] | None:
        """Parse one conservative dotenv assignment.

        Args:
            line: Raw dotenv line.

        Returns:
            Key/value pair, or ``None`` for comments and unsupported
            lines.

        """
        stripped: str = line.strip()
        if not stripped or stripped.startswith("#"):
            return None
        if stripped.startswith(Constants.export_prefix):
            stripped = stripped[len(Constants.export_prefix) :].lstrip()
        key, separator, raw_value = stripped.partition("=")
        normalized_key: str = key.strip()
        if not separator or not normalized_key.isidentifier():
            return None
        value: str = raw_value.strip()
        if (
            len(value) >= Constants.quoted_value_length
            and value[0] == value[-1]
            and (value[0] in "\"'")
        ):
            value = value[1:-1]
        return (normalized_key, value)
