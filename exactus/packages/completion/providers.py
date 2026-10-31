# Copyright (c) 2026
"""Dynamic completion providers.

Providers are read-only, bounded and deterministic: each receives a
narrow immutable context and returns candidates for one argument. The
filesystem provider lists a single directory level — never recursively
— and converts expected filesystem failures into an empty candidate
tuple so a TAB press can never break the shell.
"""

from __future__ import annotations

from dataclasses import dataclass
from os import scandir
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Final, final

from .catalog import ProviderId
from .model import CompletionCandidate, CompletionKind

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .model import CompletionContext, CompletionProvider


@final
class Constants:
    """Group module-level constants.

    Attributes:
        max_directory_entries: Grouped module constant.
        max_path_candidates: Grouped module constant.
        path_budget_seconds: Grouped module constant.

    """

    max_directory_entries: Final[int] = 4096
    max_path_candidates: Final[int] = 500
    path_budget_seconds: Final[float] = 0.1


"Maximum entries inspected per filesystem completion request."
"Maximum matching entries retained before sorting."
"Deadline checked between filesystem entries."


@dataclass(frozen=True, slots=True)
class _PathPrefix:
    """A user path prefix split into lookup and display parts.

    Attributes:
        lookup: Directory whose immediate children are listed.
        display_base: Text prepended to each child name so the
            insertion preserves the user's relative/absolute/home
            style.
        name_prefix: Basename filter.

    """

    lookup: Path
    display_base: str
    name_prefix: str


def _split_prefix(*, raw: str, cwd: Path) -> _PathPrefix:
    """Split a path prefix into a lookup directory and a name filter.

    Args:
        raw: Current value prefix, e.g. ``./pro`` or ``~/src/main``.
        cwd: Working directory relative paths resolve against.

    Returns:
        The parsed prefix parts.

    """
    directory, _, name = raw.rpartition("/")
    display_base: str = (
        f"{directory}/" if directory or raw.startswith("/") else ""
    )
    if directory.startswith("~"):
        lookup: Path = Path(directory).expanduser()
    elif directory.startswith("/"):
        lookup = Path(directory)
    elif raw.startswith("/"):
        lookup = Path("/")
    else:
        lookup = cwd / directory if directory else cwd
    return _PathPrefix(
        lookup=lookup,
        display_base=display_base,
        name_prefix=name,
    )


def _path_candidates(
    *,
    context: CompletionContext,
    directories_only: bool,
) -> tuple[CompletionCandidate, ...]:
    """List immediate children matching the path prefix.

    Args:
        context: Completion context carrying prefix and working
            directory.
        directories_only: Whether files are suppressed.

    Returns:
        File and/or directory candidates in deterministic order.

    """
    prefix: _PathPrefix = _split_prefix(
        raw=context.prefix,
        cwd=context.working_directory,
    )
    include_hidden: bool = prefix.name_prefix.startswith(".")
    candidates: list[CompletionCandidate] = []
    deadline: float = monotonic() + Constants.path_budget_seconds
    try:
        with scandir(path=prefix.lookup) as children:
            for index, child in enumerate(iterable=children):
                if (
                    index >= Constants.max_directory_entries
                    or len(candidates) >= Constants.max_path_candidates
                    or monotonic() >= deadline
                ):
                    break
                name: str = child.name
                if not name.startswith(prefix.name_prefix):
                    continue
                if name.startswith(".") and (not include_hidden):
                    continue
                try:
                    is_dir: bool = child.is_dir()
                except OSError:
                    continue
                if directories_only and (not is_dir):
                    continue
                suffix: str = "/" if is_dir else ""
                candidates.append(
                    CompletionCandidate(
                        value=f"{prefix.display_base}{name}{suffix}",
                        display=f"{name}{suffix}",
                        description="Directory" if is_dir else "File",
                        kind=CompletionKind.DIRECTORY
                        if is_dir
                        else CompletionKind.FILE,
                        append_space=not is_dir,
                    ),
                )
    except OSError:
        return ()
    return tuple(sorted(candidates, key=lambda candidate: candidate.value))


@dataclass(frozen=True, slots=True)
class PathCompletionProvider:
    """Complete files and directories one level at a time.

    Attributes:
        directories_only: Whether files are suppressed.

    """

    directories_only: bool = False

    def complete(
        self,
        *,
        context: CompletionContext,
    ) -> tuple[CompletionCandidate, ...]:
        """Return immediate children matching the current prefix.

        Args:
            context: Completion context.

        Returns:
            Path candidates preserving the user's path style.

        """
        return _path_candidates(
            context=context,
            directories_only=self.directories_only,
        )


@dataclass(frozen=True, slots=True)
class StaticNameProvider:
    """Complete names from an immutable local snapshot.

    Attributes:
        entries: ``(value, description)`` pairs offered verbatim.

    """

    entries: tuple[tuple[str, str], ...]

    def complete(
        self,
        *,
        context: CompletionContext,
    ) -> tuple[CompletionCandidate, ...]:
        """Return snapshot names beginning with the prefix.

        Args:
            context: Completion context.

        Returns:
            Matching name candidates.

        """
        return tuple(
            (
                CompletionCandidate(
                    value=value,
                    display=value,
                    description=description,
                    kind=CompletionKind.VALUE,
                    append_space=True,
                )
                for value, description in self.entries
                if value.startswith(context.prefix)
            ),
        )


@dataclass(frozen=True, slots=True)
class ScopedArgumentProvider:
    """Complete ``NAME::`` prefixes for ``--tool-arg`` values.

    Attributes:
        names: Tool identifiers that accept scoped arguments.

    """

    names: tuple[str, ...]

    def complete(
        self,
        *,
        context: CompletionContext,
    ) -> tuple[CompletionCandidate, ...]:
        """Return ``name::`` candidates matching the prefix.

        Args:
            context: Completion context.

        Returns:
            Scoped-argument prefixes; no trailing space so the user
            continues typing the forwarded argument.

        """
        return tuple(
            CompletionCandidate(
                value=f"{name}::",
                display=f"{name}::",
                description=f"Forward an argument to {name}",
                kind=CompletionKind.VALUE,
                append_space=False,
            )
            for name in self.names
            if f"{name}::".startswith(context.prefix)
        )


def default_providers(
    *,
    tools: Iterable[tuple[str, str]] = (),
    pipelines: Iterable[tuple[str, str]] = (),
) -> dict[ProviderId, CompletionProvider]:
    """Construct the provider registry for one completion run.

    Args:
        tools: ``(name, description)`` pairs for command providers.
        pipelines: ``(name, description)`` pairs for pipeline providers.

    Returns:
        Provider instances keyed by their catalog identifier — local,
        cheap, deterministic.

    """
    tool_entries: tuple[tuple[str, str], ...] = tuple(tools)
    return {
        ProviderId.PATH: PathCompletionProvider(directories_only=False),
        ProviderId.DIRECTORY: PathCompletionProvider(directories_only=True),
        ProviderId.TOOL: StaticNameProvider(entries=tool_entries),
        ProviderId.PIPELINE: StaticNameProvider(entries=tuple(pipelines)),
        ProviderId.TOOL_ARGUMENT: ScopedArgumentProvider(
            names=tuple((name for name, _description in tool_entries)),
        ),
    }
