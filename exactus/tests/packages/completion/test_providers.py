# Copyright (c) 2026
"""Coverage for the dynamic completion providers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from exactus.packages.completion import providers as path_providers
from exactus.packages.completion.catalog import ProviderId
from exactus.packages.completion.model import (
    CompletionCandidate,
    CompletionContext,
    CompletionKind,
    RecognizedArguments,
)
from exactus.packages.completion.providers import (
    Constants,
    PathCompletionProvider,
    ScopedArgumentProvider,
    StaticNameProvider,
    _PathPrefix,
    _split_prefix,
    default_providers,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_not_in,
    expect_true,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    import pytest

    from exactus.packages.completion.model import CompletionProvider


def _context(*, prefix: str, cwd: Path) -> CompletionContext:
    """Build a provider context for one prefix.

    Args:
        prefix: Current value prefix.
        cwd: Working directory.

    Returns:
        Immutable provider context.

    """
    return CompletionContext(
        command_path=(),
        words=(),
        prefix=prefix,
        recognized=RecognizedArguments(
            flags=frozenset(),
            values=(),
            multi_values=(),
            positionals=(),
            command_path=(),
        ),
        working_directory=cwd,
    )


def test_path_provider_lists_children(tmp_path: Path) -> None:
    """Immediate children complete, preserving relative style.

    Args:
        tmp_path: Directory with one file and one subdirectory.

    """
    _ = (tmp_path / "alpha.txt").write_text(data="x", encoding="utf-8")
    (tmp_path / "beta").mkdir()
    candidates: tuple[CompletionCandidate, ...] = PathCompletionProvider(
        directories_only=False,
    ).complete(context=_context(prefix="", cwd=tmp_path))
    values: tuple[str, ...] = tuple(c.value for c in candidates)
    expect_in(member="alpha.txt", container=values)
    expect_in(member="beta/", container=values)


def test_path_provider_filters_by_name_prefix(tmp_path: Path) -> None:
    """Only children matching the basename prefix are offered.

    Args:
        tmp_path: Directory with mixed names.

    """
    _ = (tmp_path / "apple").write_text(data="x", encoding="utf-8")
    _ = (tmp_path / "banana").write_text(data="x", encoding="utf-8")
    values: tuple[str, ...] = tuple(
        c.value
        for c in PathCompletionProvider(directories_only=False).complete(
            context=_context(prefix="ap", cwd=tmp_path),
        )
    )
    expect_equal(actual=values, expected=("apple",))


def test_path_provider_preserves_relative_base(tmp_path: Path) -> None:
    """``./x`` prefixes insert ``./``-prefixed values.

    Args:
        tmp_path: Working directory.

    """
    _ = (tmp_path / "sub").mkdir()
    values: tuple[str, ...] = tuple(
        c.value
        for c in PathCompletionProvider(directories_only=False).complete(
            context=_context(prefix="./s", cwd=tmp_path),
        )
    )
    expect_equal(actual=values, expected=("./sub/",))


def test_path_provider_absolute_prefix(tmp_path: Path) -> None:
    """Absolute prefixes keep the absolute base in insertions.

    Args:
        tmp_path: Directory used as the lookup root.

    """
    _ = (tmp_path / "child").mkdir()
    prefix: str = f"{tmp_path}/"
    values: tuple[str, ...] = tuple(
        c.value
        for c in PathCompletionProvider(directories_only=False).complete(
            context=_context(prefix=prefix, cwd=tmp_path),
        )
    )
    expect_equal(actual=values, expected=(f"{tmp_path}/child/",))


def test_path_provider_hides_dotfiles(tmp_path: Path) -> None:
    """Dotfiles appear only when the prefix starts with a dot.

    Args:
        tmp_path: Directory with a hidden and a visible entry.

    """
    _ = (tmp_path / ".hidden").write_text(data="x", encoding="utf-8")
    _ = (tmp_path / "visible").write_text(data="x", encoding="utf-8")
    provider: PathCompletionProvider = PathCompletionProvider(
        directories_only=False,
    )
    visible: tuple[str, ...] = tuple(
        c.value
        for c in provider.complete(context=_context(prefix="", cwd=tmp_path))
    )
    hidden: tuple[str, ...] = tuple(
        c.value
        for c in provider.complete(context=_context(prefix=".", cwd=tmp_path))
    )
    expect_not_in(member=".hidden", container=visible)
    expect_in(member=".hidden", container=hidden)


def test_directory_provider_suppresses_files(tmp_path: Path) -> None:
    """``directories_only`` providers skip files.

    Args:
        tmp_path: Directory with one file and one subdirectory.

    """
    _ = (tmp_path / "file.txt").write_text(data="x", encoding="utf-8")
    (tmp_path / "dir").mkdir()
    values: tuple[str, ...] = tuple(
        c.value
        for c in PathCompletionProvider(directories_only=True).complete(
            context=_context(prefix="", cwd=tmp_path),
        )
    )
    expect_equal(actual=values, expected=("dir/",))


def test_path_provider_missing_directory_is_empty(tmp_path: Path) -> None:
    """A nonexistent lookup directory yields no candidates.

    Args:
        tmp_path: Working directory.

    """
    values: tuple[CompletionCandidate, ...] = PathCompletionProvider(
        directories_only=False,
    ).complete(context=_context(prefix="missing/", cwd=tmp_path))
    expect_equal(actual=values, expected=())


def test_directory_candidates_do_not_append_space(tmp_path: Path) -> None:
    """Directory insertions continue the path — no trailing space.

    Args:
        tmp_path: Directory with one subdirectory.

    """
    (tmp_path / "sub").mkdir()
    candidates: tuple[CompletionCandidate, ...] = PathCompletionProvider(
        directories_only=False,
    ).complete(context=_context(prefix="", cwd=tmp_path))
    directory: CompletionCandidate = candidates[0]
    expect_false(condition=directory.append_space)
    expect_true(condition=directory.kind is CompletionKind.DIRECTORY)


def test_split_prefix_shapes() -> None:
    """``_split_prefix`` separates display base from name filter."""
    split: _PathPrefix = _split_prefix(raw="src/ma", cwd=Path("/cwd"))
    expect_equal(actual=str(object=split.lookup), expected="/cwd/src")
    expect_equal(actual=split.display_base, expected="src/")
    expect_equal(actual=split.name_prefix, expected="ma")
    split = _split_prefix(raw="/etc/ho", cwd=Path("/cwd"))
    expect_equal(actual=str(object=split.lookup), expected="/etc")
    split = _split_prefix(raw="~/pr", cwd=Path("/cwd"))
    expect_equal(actual=split.display_base, expected="~/")
    split = _split_prefix(raw="ma", cwd=Path("/cwd"))
    expect_equal(actual=split.display_base, expected="")


def test_static_name_provider_prefixes() -> None:
    """Static providers emit every entry; the engine filters."""
    provider: StaticNameProvider = StaticNameProvider(
        entries=(("lints", "Lint"), ("docs", "Docs")),
    )
    candidates: tuple[CompletionCandidate, ...] = provider.complete(
        context=_context(prefix="", cwd=Path("/")),
    )
    expect_equal(
        actual=tuple(c.value for c in candidates),
        expected=("lints", "docs"),
    )
    expect_equal(actual=candidates[0].kind, expected=CompletionKind.VALUE)


def test_scoped_argument_provider() -> None:
    """``--tool-arg`` values complete as ``name::`` prefixes."""
    provider: ScopedArgumentProvider = ScopedArgumentProvider(
        names=("lints", "docs"),
    )
    candidates: tuple[CompletionCandidate, ...] = provider.complete(
        context=_context(prefix="", cwd=Path("/")),
    )
    expect_equal(
        actual=tuple(c.value for c in candidates),
        expected=("lints::", "docs::"),
    )
    expect_false(condition=candidates[0].append_space)


def test_default_providers_cover_every_id() -> None:
    """The default registry wires every ``ProviderId``."""
    registry: dict[ProviderId, CompletionProvider] = default_providers()
    for provider_id in ProviderId:
        expect_in(member=provider_id, container=registry)


def test_default_tool_provider_uses_supplied_tools() -> None:
    """Tool candidates come from the caller's own catalog."""
    registry: dict[ProviderId, CompletionProvider] = default_providers(
        tools=(("lints", "Lint suite"), ("docs", "Docs suite")),
    )
    candidates: tuple[CompletionCandidate, ...] = registry[
        ProviderId.TOOL
    ].complete(context=_context(prefix="", cwd=Path("/")))
    values: tuple[str, ...] = tuple(c.value for c in candidates)
    expect_in(member="lints", container=values)
    expect_in(member="docs", container=values)


def test_path_provider_caps_results(tmp_path: Path) -> None:
    """Large directories retain bounded, sorted completion results.

    Args:
        tmp_path: Directory exceeding the candidate budget.

    """
    for index in range(Constants.max_path_candidates + 20):
        _ = (tmp_path / f"file-{index:04d}").touch()
    candidates: tuple[CompletionCandidate, ...] = PathCompletionProvider(
        directories_only=False,
    ).complete(context=_context(prefix="file-", cwd=tmp_path))
    expect_equal(
        actual=len(candidates),
        expected=Constants.max_path_candidates,
    )
    values: tuple[str, ...] = tuple(item.value for item in candidates)
    expect_equal(actual=values, expected=tuple(sorted(values)))


def test_path_provider_stops_at_entry_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scanning stops at its entry budget before retaining more results.

    Args:
        tmp_path: Filesystem fixture with multiple matches.
        monkeypatch: Provider budget override.

    """
    (tmp_path / "one").touch()
    (tmp_path / "two").touch()
    monkeypatch.setattr(
        target=path_providers.Constants,
        name="max_directory_entries",
        value=1,
    )
    candidates: tuple[CompletionCandidate, ...] = (
        PathCompletionProvider().complete(
            context=_context(prefix="", cwd=tmp_path),
        )
    )
    expect_equal(actual=len(candidates), expected=1)


def test_path_provider_stops_at_deadline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An elapsed deadline stops scanning without a wall-clock sleep.

    Args:
        tmp_path: Filesystem fixture with a matching entry.
        monkeypatch: Monotonic clock override.

    """
    (tmp_path / "one").touch()
    ticks: Iterator[float] = iter((0.0, 1.0))

    def clock() -> float:
        """Return the next deterministic deadline observation.

        Returns:
            Simulated monotonic time.

        """
        return next(ticks)

    monkeypatch.setattr(target=path_providers, name="monotonic", value=clock)
    expect_equal(
        actual=PathCompletionProvider().complete(
            context=_context(prefix="", cwd=tmp_path),
        ),
        expected=(),
    )
