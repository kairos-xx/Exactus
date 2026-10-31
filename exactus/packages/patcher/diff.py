"""Render read-only ANSI unified diffs for project snapshots."""

from difflib import unified_diff
from os import environ
from pathlib import PurePosixPath
from re import Pattern
from re import compile as compile_pattern
from types import ModuleType
from typing import Final, final

from exactus.packages.patcher.core import (
    EntryKind,
    ProjectSnapshot,
    SnapshotEntry,
)

sys: ModuleType = __import__("sys")


@final
class Constants:
    """Group module-level constants.

    Attributes:
        reset: Grouped module constant.
        red: Grouped module constant.
        green: Grouped module constant.
        cyan: Grouped module constant.
        yellow: Grouped module constant.
        magenta: Grouped module constant.
        blue: Grouped module constant.
        dim: Grouped module constant.
        token: Grouped module constant.
        highlight_suffixes: Grouped module constant.

    """

    reset: Final[str] = "\x1b[0m"
    red: Final[str] = "\x1b[31m"
    green: Final[str] = "\x1b[32m"
    cyan: Final[str] = "\x1b[36m"
    yellow: Final[str] = "\x1b[33m"
    magenta: Final[str] = "\x1b[35m"
    blue: Final[str] = "\x1b[34m"
    dim: Final[str] = "\x1b[2m"
    token: Final[Pattern[str]] = compile_pattern(
        pattern=(
            "(\\\"(?:\\\\.|[^\\\"\\\\])*\\\"|'(?:\\\\.|[^'\\\\])*'|\\b(?:true|"
            "false|null|None|True|False|class|def|return|import|from|const|let"
            "|var|function|if|else|for|while|async|await|new|display|position|"
            "color|background|DOCTYPE)\\b|\\b\\d+(?:\\.\\d+)?\\b|#[0-9A-Fa-f]{"
            "3,8}\\b)"
        ),
    )
    highlight_suffixes: Final[frozenset[str]] = frozenset(
        {
            ".js",
            ".mjs",
            ".cjs",
            ".css",
            ".html",
            ".htm",
            ".py",
            ".json",
            ".toml",
            ".xml",
        },
    )


class DiffRenderer:
    """Render deterministic unified diffs without mutating either snapshot."""

    @classmethod
    def render(
        cls,
        *,
        before: ProjectSnapshot,
        after: ProjectSnapshot,
        color: bool = True,
        context: int = 3,
    ) -> str:
        """Return a human-readable delta between two snapshots.

        Args:
            before: Project snapshot representing the state before changes.
            after: Project snapshot representing the state after changes.
            color: Whether ANSI colors and syntax highlighting are enabled.
            context: Number of unchanged context lines around each diff hunk.

        Returns:
            Complete deterministic unified diff for all changed entries.

        """
        before_map: dict[PurePosixPath, SnapshotEntry] = before.by_path
        after_map: dict[PurePosixPath, SnapshotEntry] = after.by_path
        paths: tuple[PurePosixPath, ...] = tuple(
            sorted(set(before_map) | set(after_map), key=str),
        )
        sections: list[str] = []
        for path in paths:
            old: SnapshotEntry | None = before_map.get(path)
            new: SnapshotEntry | None = after_map.get(path)
            if (
                old is not None
                and new is not None
                and (old.identity == new.identity)
            ):
                continue
            sections.append(
                cls._entry(
                    path=path,
                    before=old,
                    after=new,
                    color=color,
                    context=context,
                ),
            )
        return "\n".join(section for section in sections if section)

    @classmethod
    def write(
        cls,
        *,
        before: ProjectSnapshot,
        after: ProjectSnapshot,
        color: bool | None = None,
        context: int = 3,
    ) -> None:
        """Write a rendered project diff to standard output.

        Args:
            before: Project snapshot representing the state before changes.
            after: Project snapshot representing the state after changes.
            color: Explicit ANSI-color setting, or ``None`` to honor the
                ``NO_COLOR`` environment variable.
            context: Number of unchanged context lines around each diff hunk.

        """
        enabled: bool = "NO_COLOR" not in environ if color is None else color
        _ = sys.stdout.write(
            cls.render(
                before=before,
                after=after,
                color=enabled,
                context=context,
            ),
        )
        _ = sys.stdout.flush()

    @classmethod
    def _entry(
        cls,
        *,
        path: PurePosixPath,
        before: SnapshotEntry | None,
        after: SnapshotEntry | None,
        color: bool,
        context: int,
    ) -> str:
        """Render one changed filesystem entry.

        Args:
            path: Project-relative path of the changed filesystem entry.
            before: Entry state before the change, or ``None`` when added.
            after: Entry state after the change, or ``None`` when removed.
            color: Whether ANSI colors and syntax highlighting are enabled.
            context: Number of unchanged context lines around each diff hunk.

        Returns:
            Rendered unified-diff section describing the entry transition.

        """
        old_name: str = "/dev/null" if before is None else f"a/{path}"
        new_name: str = "/dev/null" if after is None else f"b/{path}"
        if before is not None and before.kind is not EntryKind.FILE:
            return cls._metadata(
                path=path,
                before=before,
                after=after,
                color=color,
            )
        if after is not None and after.kind is not EntryKind.FILE:
            return cls._metadata(
                path=path,
                before=before,
                after=after,
                color=color,
            )
        old_bytes: bytes = b"" if before is None else before.content
        new_bytes: bytes = b"" if after is None else after.content
        if b"\x00" in old_bytes or b"\x00" in new_bytes:
            return cls._paint(
                text=f"diff --git a/{path} b/{path}\nBinary files differ\n",
                color=Constants.yellow,
                enabled=color,
            )
        try:
            old_text: str = old_bytes.decode(encoding="utf-8")
            new_text: str = new_bytes.decode(encoding="utf-8")
        except UnicodeDecodeError:
            return cls._paint(
                text=f"diff --git a/{path} b/{path}\nBinary files differ\n",
                color=Constants.yellow,
                enabled=color,
            )
        lines: list[str] = [f"diff --git a/{path} b/{path}\n"]
        lines.extend(
            unified_diff(
                a=old_text.splitlines(keepends=True),
                b=new_text.splitlines(keepends=True),
                fromfile=old_name,
                tofile=new_name,
                n=context,
            ),
        )
        return "".join(
            cls._line(path=path, line=line, color=color) for line in lines
        )

    @classmethod
    def _metadata(
        cls,
        *,
        path: PurePosixPath,
        before: SnapshotEntry | None,
        after: SnapshotEntry | None,
        color: bool,
    ) -> str:
        """Render a directory, symlink, or type transition.

        Args:
            path: Project-relative path of the changed filesystem entry.
            before: Entry state before the change, or ``None`` when added.
            after: Entry state after the change, or ``None`` when removed.
            color: Whether ANSI color output is enabled.

        Returns:
            Rendered metadata-diff section describing the entry transition.

        """
        old: str = "absent" if before is None else before.kind.value
        new: str = "absent" if after is None else after.kind.value
        details: str = f"{old} -> {new}"
        if after is not None and after.kind is EntryKind.SYMLINK:
            details += f" ({after.link_target})"
        return cls._paint(
            text=f"diff --git a/{path} b/{path}\n{details}\n",
            color=Constants.yellow,
            enabled=color,
        )

    @classmethod
    def _line(cls, *, path: PurePosixPath, line: str, color: bool) -> str:
        """Apply diff and lightweight language-aware ANSI highlighting.

        Args:
            path: Project-relative path used to determine the source format.
            line: Individual unified-diff line to render.
            color: Whether ANSI color and syntax highlighting are enabled.

        Returns:
            Original or ANSI-decorated unified-diff line.

        """
        if not color:
            return line
        if line.startswith(("+++", "---")):
            return cls._paint(text=line, color=Constants.cyan, enabled=True)
        if line.startswith("@@"):
            return cls._paint(text=line, color=Constants.magenta, enabled=True)
        if line.startswith("diff "):
            return cls._paint(text=line, color=Constants.blue, enabled=True)
        prefix: str = line[:1]
        base: str = (
            Constants.green
            if prefix == "+"
            else Constants.red
            if prefix == "-"
            else ""
        )
        body: str = line[1:] if prefix in {"+", "-", " "} else line
        if path.suffix.lower() in Constants.highlight_suffixes:
            body = Constants.token.sub(
                repl=(
                    lambda match: (
                        f"{Constants.yellow}"
                        f"{match.group(0)}"
                        f"{Constants.reset}"
                        f"{base}"
                    )
                ),
                string=body,
            )
        return (
            f"{base}{prefix}{body}{Constants.reset}"
            if base
            else f"{body}{Constants.reset}"
        )

    @staticmethod
    def _paint(*, text: str, color: str, enabled: bool) -> str:
        """Wrap text in one ANSI color when enabled.

        Args:
            text: Text to decorate.
            color: ANSI escape sequence to apply when coloring is enabled.
            enabled: Whether the ANSI decoration should be applied.

        Returns:
            ANSI-decorated text when enabled, otherwise the original text.

        """
        return f"{color}{text}{Constants.reset}" if enabled else text
