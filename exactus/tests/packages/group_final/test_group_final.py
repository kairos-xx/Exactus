"""Exercise the group_final refactoring: discovery, plans and rewrites."""

from __future__ import annotations

from ast import AnnAssign, Module, Name, Store, parse, unparse
from io import StringIO
from pathlib import Path
from runpy import run_module, run_path
from textwrap import dedent
from typing import TYPE_CHECKING, cast

import pytest

from exactus.packages import project_python
from exactus.packages.group_final import (
    Arguments,
    Cli,
    ConstantBinding,
    FinalConstantsRefactor,
    ModulePlan,
    ScanReport,
    main,
)
from exactus.packages.group_final import core as core_module
from exactus.packages.group_final.core import (
    DirectImportReferenceTransformer,
    LocalReferenceTransformer,
    ProgressDisplay,
    QualifiedReferenceTransformer,
)
from exactus.packages.group_final.examples.run import main as example_main
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_not_in,
    expect_true,
    private,
    private_call,
    private_result,
    require_type,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType
sys: ModuleType = __import__("sys")


class FakeStdout:
    """Stand-in stream that reports itself as a terminal."""

    def __init__(self) -> None:
        """Initialize the captured writes buffer."""
        self.writes: list[str] = []

    @staticmethod
    def isatty() -> bool:
        """Report terminal status.

        Returns:
            Always ``True``.

        """
        return True

    def write(self, text: str) -> int:
        """Record written text.

        Args:
            text: Text written to the stream.

        Returns:
            Number of characters recorded.

        """
        self.writes.append(text)
        return len(text)

    def flush(self) -> None:
        """Accept flush requests without side effects."""


class PrintRecorder:
    """Stand-in for the module ``_print`` helper capturing messages."""

    def __init__(self) -> None:
        """Initialize the captured message list."""
        self.messages: list[str] = []

    def __call__(self, *args: str, file: object = None) -> None:
        """Record one printed line.

        Args:
            *args: Positional arguments joined like ``_print`` does.
            file: Ignored stream override.

        """
        del file
        self.messages.append(" ".join(args))


def record_print(*, monkeypatch: pytest.MonkeyPatch) -> PrintRecorder:
    """Patch the module ``_print`` helper with a recorder.

    Args:
        monkeypatch: Pytest patching helper.

    Returns:
        Recorder capturing every printed message.

    """
    recorder: PrintRecorder = PrintRecorder()
    monkeypatch.setattr(target=core_module, name="_print", value=recorder)
    return recorder


def make_refactor(
    *,
    root: Path,
    dry_run: bool = True,
) -> FinalConstantsRefactor:
    """Build a refactor rooted at ``root``.

    Args:
        root: Source tree root.
        dry_run: Whether the run analyzes without writing.

    Returns:
        Configured refactoring instance.

    """
    return FinalConstantsRefactor(root=root, dry_run=dry_run)


def assignment(*, source: str) -> AnnAssign:
    """Parse a single annotated assignment statement.

    Args:
        source: Module source holding one ``AnnAssign``.

    Returns:
        The parsed annotated assignment.

    """
    return require_type(value=parse(source=source).body[0], kind=AnnAssign)


def write_source(*, root: Path, relative: str, source: str) -> Path:
    """Create ``relative`` below ``root`` with ``source`` content.

    Args:
        root: Project root.
        relative: Slash-separated project-relative file path.
        source: Python source text.

    Returns:
        The written file path.

    """
    path: Path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data=source, encoding="utf-8")
    return path


def test_print_writes_and_flushes() -> None:
    """The print helper joins arguments and flushes the stream."""
    buffer: StringIO = StringIO()
    printer: Callable[..., None] = cast(
        typ="Callable[..., None]",
        val=private(owner=core_module, name="_print"),
    )
    printer("alpha", "beta", file=buffer)
    expect_equal(actual=buffer.getvalue(), expected="alpha beta\n")


def test_paint_wraps_or_passes_through() -> None:
    """ANSI painting wraps text only when enabled."""
    painted: str = cast(
        typ="str",
        val=private_call(
            owner=core_module,
            name="_paint",
            text="x",
            color="\x1b[31m",
        ),
    )
    expect_equal(actual=painted, expected="\x1b[31mx\x1b[0m")
    plain: str = cast(
        typ="str",
        val=private_call(
            owner=core_module,
            name="_paint",
            text="x",
            color="\x1b[31m",
            enabled=False,
        ),
    )
    expect_equal(actual=plain, expected="x")


def test_progress_disabled_without_terminal() -> None:
    """Non-terminal output produces no progress escape sequences."""
    display: ProgressDisplay = ProgressDisplay(label="files", total=0)
    display.render()
    display.finish()
    display.close()
    line: str = cast(typ="str", val=private_call(owner=display, name="_line"))
    expect_in(member="files", container=line)
    expect_in(member="100.00%", container=line)
    expect_in(member="1/0", container=line)
    expect_not_in(member="\x1b[", container=line)


def test_progress_renders_on_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Terminal output draws the bar with ANSI colors.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.delenv(name="NO_COLOR", raising=False)
    fake: FakeStdout = FakeStdout()
    monkeypatch.setattr(target=core_module, name="stdout", value=fake)
    display: ProgressDisplay = ProgressDisplay(label="files", total=2)
    display.render()
    display.finish()
    display.finish()
    display.close()
    text: str = "".join(fake.writes)
    expect_in(member="\x1b[2K", container=text)
    expect_in(member="2/2", container=text)
    expect_in(member="100.00%", container=text)
    expect_in(member="\x1b[32m", container=text)


def test_progress_no_color_keeps_plain_bar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``NO_COLOR`` keeps the bar but drops ANSI styling.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setenv(name="NO_COLOR", value="1")
    fake: FakeStdout = FakeStdout()
    monkeypatch.setattr(target=core_module, name="stdout", value=fake)
    display: ProgressDisplay = ProgressDisplay(label="files", total=4)
    display.render()
    display.finish()
    display.close()
    text: str = "".join(fake.writes)
    expect_in(member="\x1b[2K", container=text)
    expect_in(member="1/4", container=text)
    expect_not_in(member="\x1b[36m", container=text)
    expect_not_in(member="\x1b[32m", container=text)


def test_name_collector_loads_only() -> None:
    """Loaded names are collected while stored names are skipped."""
    names: set[str] = cast(
        typ="set[str]",
        val=private_call(
            owner=FinalConstantsRefactor,
            name="_loaded_names",
            node=parse(source="result = func(A, obj.B)\n"),
        ),
    )
    expect_equal(actual=names, expected={"func", "A", "obj"})
    stored: set[str] = cast(
        typ="set[str]",
        val=private_call(
            owner=FinalConstantsRefactor,
            name="_loaded_names",
            node=parse(source="x = 1\n"),
        ),
    )
    expect_equal(actual=stored, expected=set[str]())


def test_uppercase_convention() -> None:
    """Uppercase detection accepts constant-style names only."""
    uppercase: Callable[..., bool] = cast(
        typ="Callable[..., bool]",
        val=private(owner=FinalConstantsRefactor, name="_uppercase"),
    )
    for name in ("X", "_PRIVATE", "MAX_RETRIES", "_A1"):
        expect_true(condition=uppercase(name=name), message=name)
    for name in ("x", "Mixed", "_9", "_", "low_case"):
        expect_false(condition=uppercase(name=name), message=name)


def test_is_final_annotations() -> None:
    """Final annotation detection covers Name, Subscript and Attribute."""
    for source in (
        "X: Final = 1\n",
        "X: Final[int] = 1\n",
        "X: typing.Final = 1\n",
    ):
        expect_true(
            condition=cast(
                typ="bool",
                val=private_call(
                    owner=FinalConstantsRefactor,
                    name="_is_final",
                    annotation=assignment(source=source).annotation,
                ),
            ),
            message=source,
        )
    for source in ("X: int = 1\n", "X: list[int] = 1\n"):
        expect_false(
            condition=cast(
                typ="bool",
                val=private_call(
                    owner=FinalConstantsRefactor,
                    name="_is_final",
                    annotation=assignment(source=source).annotation,
                ),
            ),
            message=source,
        )


def test_candidate_accepts_uppercase_final() -> None:
    """Supported statements produce a binding with their index."""
    binding: ConstantBinding = private_result(
        owner=FinalConstantsRefactor,
        name="_candidate",
        kind=ConstantBinding,
        statement=assignment(source="X: Final[int] = 1\n"),
        statement_index=2,
    )
    expect_equal(actual=binding.name, expected="X")
    expect_equal(actual=binding.statement_index, expected=2)


def test_candidate_rejects_unsupported_statements() -> None:
    """Non-Final, lowercase, valueless and non-assign forms are skipped."""
    for source in (
        "x: Final[int] = 1\n",
        "X: int = 1\n",
        "X: Final[int]\n",
        "X = 1\n",
        "obj.X: Final[int] = 1\n",
        "import os\n",
    ):
        expect_none(
            value=private_call(
                owner=FinalConstantsRefactor,
                name="_candidate",
                statement=parse(source=source).body[0],
                statement_index=0,
            ),
        )


def test_is_excluded_matches_default_patterns() -> None:
    """Every default exclusion pattern rejects its subtree."""
    excluded: tuple[str, ...] = (
        "node_modules/dep.py",
        "frontend/node_modules/dep.py",
        "__pycache__/generated.py",
        "package/__pycache__/generated.py",
        "mutants/mutant.py",
        "package/mutants/mutant.py",
        "dist/generated.py",
        "build/generated.py",
        "EXACTUS_RESULTS/LINTS/artifact.py",
        "tests/fixture/EXACTUS_RESULTS/tmp/generated.py",
        ".build-cache/generated.py",
        "exactus/bundle/bundled.py",
        ".git/internal.py",
        ".hidden/internal.py",
        "package/.cache/internal.py",
        ".hidden.py",
    )
    for relative in excluded:
        expect_true(
            condition=cast(
                typ="bool",
                val=private_call(
                    owner=FinalConstantsRefactor,
                    name="_is_excluded",
                    path=Path(relative),
                ),
            ),
            message=relative,
        )
    for relative in ("app.py", "package/model.py", "exactus/pkg/tool.py"):
        expect_false(
            condition=cast(
                typ="bool",
                val=private_call(
                    owner=FinalConstantsRefactor,
                    name="_is_excluded",
                    path=Path(relative),
                ),
            ),
            message=relative,
        )


def test_python_files_prunes_excluded_trees(tmp_path: Path) -> None:
    """Discovery returns only non-excluded Python files, sorted.

    Args:
        tmp_path: Per-test temporary directory.

    """
    for relative in (
        "app.py",
        "package/model.py",
        "node_modules/dep.py",
        "frontend/node_modules/deep/nested.py",
        "__pycache__/generated.py",
        "package/__pycache__/generated.py",
        "mutants/mutant.py",
        "package/mutants/mutant.py",
        "dist/generated.py",
        "build/generated.py",
        "EXACTUS_RESULTS/LINTS/artifact.py",
        "tests/fixture/EXACTUS_RESULTS/tmp/generated.py",
        ".build-cache/generated.py",
        "exactus/bundle/bundled.py",
        ".git/internal.py",
        "package/.cache/internal.py",
        ".hidden.py",
        "package/readme.md",
    ):
        write_source(root=tmp_path, relative=relative, source="x = 1\n")
    found: list[Path] = cast(
        typ="list[Path]",
        val=private_call(
            owner=make_refactor(root=tmp_path),
            name="_python_files",
        ),
    )
    expect_equal(
        actual=[path.relative_to(tmp_path).as_posix() for path in found],
        expected=["app.py", "package/model.py"],
    )


def test_python_files_prunes_renamed_report_trees(tmp_path: Path) -> None:
    """Report trees are pruned by fingerprint, not by directory name.

    Args:
        tmp_path: Per-test temporary directory.

    """
    write_source(root=tmp_path, relative="app.py", source="x = 1\n")
    renamed_root: Path = tmp_path / "REPORTS"
    (renamed_root / ".runtime").mkdir(parents=True)
    write_source(
        root=tmp_path,
        relative="REPORTS/LINTS/artifact.py",
        source="x = 1\n",
    )
    bundle: Path = tmp_path / "out" / "DOCS"
    bundle.mkdir(parents=True)
    _ = (bundle / "result.json").write_text(data="{}", encoding="utf-8")
    _ = (bundle / "result.md").write_text(data="# Docs\n", encoding="utf-8")
    write_source(
        root=tmp_path,
        relative="out/DOCS/ARTIFACTS/generated.py",
        source="x = 1\n",
    )
    running: Path = tmp_path / "live" / "COVERAGE"
    (running / "ARTIFACTS").mkdir(parents=True)
    _ = (running / "ARTIFACTS" / "@activity.json").write_text(
        data="{}",
        encoding="utf-8",
    )
    write_source(
        root=tmp_path,
        relative="live/COVERAGE/tmp/generated.py",
        source="x = 1\n",
    )
    found: list[Path] = cast(
        typ="list[Path]",
        val=private_call(
            owner=make_refactor(root=tmp_path),
            name="_python_files",
        ),
    )
    expect_equal(
        actual=[path.relative_to(tmp_path).as_posix() for path in found],
        expected=["app.py"],
    )


def test_parse_trees_skips_vanished_files(tmp_path: Path) -> None:
    """Sources deleted between collection and parsing are skipped.

    Args:
        tmp_path: Per-test temporary directory.

    """
    existing: Path = write_source(
        root=tmp_path,
        relative="app.py",
        source="x = 1\n",
    )
    missing: Path = tmp_path / "gone.py"
    trees: dict[Path, Module] = cast(
        typ="dict[Path, Module]",
        val=private_call(
            owner=make_refactor(root=tmp_path),
            name="_parse_trees",
            paths=(existing, missing),
        ),
    )
    expect_equal(actual=list(trees.keys()), expected=[existing])


def test_module_name_resolution(tmp_path: Path) -> None:
    """Paths resolve to dotted names with ``__init__`` stripped.

    Args:
        tmp_path: Per-test temporary directory.

    """
    refactor: FinalConstantsRefactor = make_refactor(root=tmp_path)
    cases: tuple[tuple[str, str], ...] = (
        ("app.py", "app"),
        ("pkg/__init__.py", "pkg"),
        ("pkg/mod.py", "pkg.mod"),
        ("__init__.py", ""),
    )
    for relative, expected in cases:
        path: Path = write_source(
            root=tmp_path,
            relative=relative,
            source="x = 1\n",
        )
        expect_equal(
            actual=private_call(
                owner=refactor,
                name="_module_name",
                path=path.resolve(),
            ),
            expected=expected,
        )


def test_top_level_definitions(tmp_path: Path) -> None:
    """Definitions map names to body indices for every form.

    Args:
        tmp_path: Per-test temporary directory.

    """
    tree: Module = parse(
        source=(
            dedent(
                text=(
                    "    import a.b\n    import c as d\n    from e import "
                    "f\n    from g import h as i\n    class Klass: ...\n  "
                    "  def fn(): ...\n    async def af(): ...\n    Y: int "
                    "= 2\n    z = 3\n    "
                ),
            )
        ),
    )
    definitions: dict[str, int] = cast(
        typ="dict[str, int]",
        val=private_call(
            owner=make_refactor(root=tmp_path),
            name="_top_level_definitions",
            tree=tree,
        ),
    )
    expect_equal(
        actual=definitions,
        expected={
            "a": 0,
            "d": 1,
            "f": 2,
            "i": 3,
            "Klass": 4,
            "fn": 5,
            "af": 6,
            "Y": 7,
            "z": 8,
        },
    )


def test_required_insertion_index_follows_dependencies(tmp_path: Path) -> None:
    """Insertion lands after the latest top-level dependency.

    Args:
        tmp_path: Per-test temporary directory.

    """
    refactor: FinalConstantsRefactor = make_refactor(root=tmp_path)
    tree: Module = parse(
        source=(
            dedent(
                text=(
                    "    def helper() -> int:\n        return 0\n    X: Fi"
                    "nal[int] = helper() + len([1])\n    "
                ),
            )
        ),
    )
    binding: ConstantBinding = ConstantBinding(
        name="X",
        statement_index=1,
        statement=require_type(value=tree.body[1], kind=AnnAssign),
    )
    expect_equal(
        actual=private_call(
            owner=refactor,
            name="_required_insertion_index",
            binding=binding,
            tree=tree,
            candidate_names=frozenset({"X"}),
        ),
        expected=1,
    )
    valueless: ConstantBinding = ConstantBinding(
        name="Y",
        statement_index=0,
        statement=AnnAssign(
            target=Name(id="Y", ctx=Store()),
            annotation=Name(id="Final", ctx=Store()),
            value=None,
            simple=1,
        ),
    )
    expect_equal(
        actual=private_call(
            owner=refactor,
            name="_required_insertion_index",
            binding=valueless,
            tree=tree,
            candidate_names=frozenset({"Y"}),
        ),
        expected=0,
    )


def test_used_before_detects_early_reference(tmp_path: Path) -> None:
    """Early loads are detected unless the statement is ignored.

    Args:
        tmp_path: Per-test temporary directory.

    """
    refactor: FinalConstantsRefactor = make_refactor(root=tmp_path)
    used_before: Callable[..., bool] = cast(
        typ="Callable[..., bool]",
        val=private(owner=refactor, name="_used_before"),
    )
    tree: Module = parse(source="TOP = A\nA: Final[int] = 1\n")
    expect_true(
        condition=used_before(
            name="A",
            tree=tree,
            before_index=1,
            ignored_statement_indices=frozenset(),
        ),
    )
    expect_false(
        condition=used_before(
            name="A",
            tree=tree,
            before_index=1,
            ignored_statement_indices=frozenset({0}),
        ),
    )
    expect_false(
        condition=used_before(
            name="A",
            tree=tree,
            before_index=0,
            ignored_statement_indices=frozenset(),
        ),
    )


def plan_for(
    *,
    refactor: FinalConstantsRefactor,
    source: str,
) -> ModulePlan | None:
    """Build a plan for module source text.

    Args:
        refactor: Refactoring instance under test.
        source: Module source text.

    Returns:
        The computed plan, or ``None``.

    """
    return cast(
        typ="ModulePlan | None",
        val=private_call(
            owner=refactor,
            name="_plan",
            path=Path("module.py"),
            module_name="module",
            tree=parse(source=source),
        ),
    )


def test_plan_none_without_candidates(tmp_path: Path) -> None:
    """Modules without Final constants produce no plan.

    Args:
        tmp_path: Per-test temporary directory.

    """
    expect_none(
        value=plan_for(
            refactor=make_refactor(root=tmp_path),
            source="x = 1\n",
        ),
    )


def test_plan_groups_movable_constants(tmp_path: Path) -> None:
    """A safe module plans every uppercase Final constant.

    Args:
        tmp_path: Per-test temporary directory.

    """
    plan: ModulePlan = require_type(
        value=plan_for(
            refactor=make_refactor(root=tmp_path),
            source=(
                dedent(
                    text=(
                        "    from typing import Final\n    A: Final[int] ="
                        " 1\n    B: Final[str] = 's'\n    "
                    ),
                )
            ),
        ),
        kind=ModulePlan,
    )
    expect_equal(actual=plan.names, expected=frozenset({"A", "B"}))
    expect_equal(actual=plan.module_name, expected="module")
    expect_equal(actual=plan.insertion_index, expected=1)


def test_plan_uses_first_safe_contiguous_group(tmp_path: Path) -> None:
    """A single class replaces one contiguous declaration block in place.

    Args:
        tmp_path: Per-test temporary directory.

    """
    plan: ModulePlan = require_type(
        value=plan_for(
            refactor=make_refactor(root=tmp_path),
            source=(
                dedent(
                    text=(
                        "    A: Final[int] = 1\n    TOP = A\n    def helpe"
                        "r() -> int:\n        return 0\n    B: Final[int] "
                        "= helper()\n    "
                    ),
                )
            ),
        ),
        kind=ModulePlan,
    )
    expect_equal(actual=plan.names, expected=frozenset({"A"}))
    expect_equal(actual=plan.insertion_index, expected=0)


def test_plan_does_not_move_across_intervening_statements(
    tmp_path: Path,
) -> None:
    """Separated constants never move across intervening statements.

    Args:
        tmp_path: Per-test temporary directory.

    """
    plan: ModulePlan = require_type(
        value=plan_for(
            refactor=make_refactor(root=tmp_path),
            source=(
                dedent(
                    text=(
                        "    A: Final[int] = 1\n    TOP = A\n    ALSO = B"
                        "\n    B: Final[int] = h()\n    def h() -> int:\n "
                        "       return 0\n    "
                    ),
                )
            ),
        ),
        kind=ModulePlan,
    )
    expect_equal(actual=plan.names, expected=frozenset({"A"}))
    expect_equal(actual=plan.insertion_index, expected=0)


def test_module_aliases_for_import_forms(tmp_path: Path) -> None:
    """Import aliases map plain, aliased and dotted module imports.

    Args:
        tmp_path: Per-test temporary directory.

    """
    aliases: dict[str, frozenset[str]] = cast(
        typ="dict[str, frozenset[str]]",
        val=private_call(
            owner=make_refactor(root=tmp_path),
            name="_module_aliases",
            tree=parse(
                source=(
                    dedent(
                        text=(
                            "    import app\n    import app as shorthand\n"
                            "    import pkg.mod\n    x = 1\n    "
                        ),
                    )
                ),
            ),
            moved_by_module={
                "app": frozenset({"X"}),
                "pkg.mod": frozenset({"Y"}),
            },
        ),
    )
    expect_equal(
        actual=aliases,
        expected={
            "app": frozenset({"X"}),
            "shorthand": frozenset({"X"}),
            "pkg": frozenset({"Y"}),
        },
    )


def test_rewrite_imports_splits_moved_names() -> None:
    """Direct imports of moved constants become Constants imports."""
    tree: Module = parse(
        source=(
            dedent(
                text=(
                    "    from app import X, KEEP\n    from app import Y\n "
                    "   from .app import Z\n    from other import W\n    p"
                    "rint(X, Y, KEEP, W)\n    "
                ),
            )
        ),
    )
    private_call(
        owner=FinalConstantsRefactor,
        name="_rewrite_imports",
        tree=tree,
        moved_by_module={"app": frozenset({"X", "Y"})},
    )
    output: str = unparse(ast_obj=tree)
    expect_in(member="from app import KEEP", container=output)
    expect_in(member="from app import Constants", container=output)
    expect_in(member="from .app import Z", container=output)
    expect_in(member="from other import W", container=output)
    expect_in(member="Constants.x", container=output)
    expect_in(member="Constants.y", container=output)


def test_local_reference_transformer() -> None:
    """Moved constant loads are qualified; stores and others stay."""
    tree: Module = parse(source="X = 1\nY = X + Z\n")
    transformer: LocalReferenceTransformer = LocalReferenceTransformer(
        names=frozenset({"X"}),
    )
    transformer.visit(node=tree)
    output: str = unparse(ast_obj=tree)
    expect_in(member="X = 1", container=output)
    expect_in(member="Y = Constants.x + Z", container=output)
    expect_not_in(member="Constants.Z", container=output)


def test_qualified_reference_transformer() -> None:
    """Module-qualified references gain the Constants hop."""
    tree: Module = parse(source="print(app.X, app.Y, other.X, obj.inner.X)\n")
    transformer: QualifiedReferenceTransformer = QualifiedReferenceTransformer(
        module_aliases={"app": frozenset({"X"})},
    )
    transformer.visit(node=tree)
    output: str = unparse(ast_obj=tree)
    expect_in(member="app.Constants.x", container=output)
    expect_in(member="app.Y", container=output)
    expect_in(member="other.X", container=output)
    expect_in(member="obj.inner.X", container=output)


def test_direct_import_reference_transformer() -> None:
    """Directly imported names qualify through Constants."""
    tree: Module = parse(source="X = 1\nprint(X, OTHER)\n")
    transformer: DirectImportReferenceTransformer = (
        DirectImportReferenceTransformer(replacements={"X": "REAL_X"})
    )
    transformer.visit(node=tree)
    output: str = unparse(ast_obj=tree)
    expect_in(member="X = 1", container=output)
    expect_in(member="print(Constants.REAL_X, OTHER)", container=output)


def test_run_dry_run_reports_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dry-run reports would-be changes and leaves files untouched.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    printed: PrintRecorder = record_print(monkeypatch=monkeypatch)
    source: str = "from typing import Final\n\nLIMIT: Final[int] = 10\n"
    target: Path = write_source(
        root=tmp_path,
        relative="app.py",
        source=source,
    )
    report: ScanReport = make_refactor(root=tmp_path).run()
    expect_equal(actual=report.files, expected=1)
    expect_equal(actual=report.planned, expected=1)
    expect_equal(actual=report.constants, expected=1)
    expect_equal(actual=report.changed, expected=1)
    expect_true(condition=report.dry_run)
    expect_equal(actual=target.read_text(encoding="utf-8"), expected=source)
    expect_in(member="WOULD UPDATE app.py", container=printed.messages)


def test_run_apply_rewrites_local_references(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Apply mode groups constants and rewrites local references.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    printed: PrintRecorder = record_print(monkeypatch=monkeypatch)
    target: Path = write_source(
        root=tmp_path,
        relative="app.py",
        source=(
            dedent(
                text=(
                    "    from typing import Final\n    \n    LIMIT: Final["
                    "int] = 10\n    NAME: Final[str] = 'x'\n    \n    def "
                    "describe() -> str:\n        return f'{NAME} {LIMIT}'"
                    "\n    "
                ),
            )
        ),
    )
    report: ScanReport = make_refactor(root=tmp_path, dry_run=False).run()
    expect_equal(actual=report.files, expected=1)
    expect_equal(actual=report.planned, expected=1)
    expect_equal(actual=report.constants, expected=2)
    expect_equal(actual=report.changed, expected=1)
    expect_false(condition=report.dry_run)
    output: str = target.read_text(encoding="utf-8")
    expect_in(member="@final", container=output)
    expect_in(member="class Constants:", container=output)
    expect_in(member="limit: Final[int] = 10", container=output)
    expect_in(member="name: Final[str] = 'x'", container=output)
    expect_in(member="Constants.name", container=output)
    expect_in(member="Constants.limit", container=output)
    expect_in(member="from typing import Final, final", container=output)
    expect_in(member='"""Group module-level constants.', container=output)
    expect_in(member="UPDATE app.py", container=printed.messages)


def test_run_apply_rewrites_cross_module_references(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct and qualified imports follow moved constants.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    printed: PrintRecorder = record_print(monkeypatch=monkeypatch)
    write_source(
        root=tmp_path,
        relative="settings.py",
        source=(
            dedent(
                text=(
                    "    from typing import Final\n    \n    DEBUG: Final["
                    "bool] = True\n    LEVEL: Final[int] = 3\n    "
                ),
            )
        ),
    )
    consumer: Path = write_source(
        root=tmp_path,
        relative="consumer.py",
        source=(
            dedent(
                text=(
                    "    import settings\n    import settings as cfg\n    "
                    "from settings import DEBUG, LEVEL\n    \n    print(se"
                    "ttings.DEBUG, cfg.LEVEL, DEBUG, LEVEL)\n    "
                ),
            )
        ),
    )
    report: ScanReport = make_refactor(root=tmp_path, dry_run=False).run()
    expect_equal(actual=report.changed, expected=2)
    rewritten: str = consumer.read_text(encoding="utf-8")
    expect_in(member="from settings import Constants", container=rewritten)
    expect_in(member="settings.Constants.debug", container=rewritten)
    expect_in(member="cfg.Constants.level", container=rewritten)
    expect_in(member="Constants.debug", container=rewritten)
    expect_in(member="Constants.level", container=rewritten)
    expect_in(member="UPDATE consumer.py", container=printed.messages)
    expect_in(member="UPDATE settings.py", container=printed.messages)


def test_run_preserves_statement_order_and_annotation_dependencies(
    tmp_path: Path,
) -> None:
    """The generated class replaces its declaration at the same boundary.

    Args:
        tmp_path: Isolated test filesystem.

    """
    target: Path = write_source(
        root=tmp_path,
        relative="app.py",
        source=(
            dedent(
                text=(
                    "    from typing import Final\n    \n    items: list[i"
                    "nt] = []\n    items.append(1)\n    class Token:\n    "
                    "    pass\n    \n    X: Final[Token | None] = None\n  "
                    "  Y: Final[int] = len(items)\n    "
                ),
            )
        ),
    )
    make_refactor(root=tmp_path, dry_run=False).run()
    output: str = target.read_text(encoding="utf-8")
    final_index: int = output.index("@final")
    expect_true(condition=output.index("items.append(1)") < final_index)
    expect_true(condition=output.index("class Token:") < final_index)
    namespace: dict[str, object] = run_path(path_name=str(object=target))
    constants: object = namespace["Constants"]
    expect_equal(actual=vars(constants)["y"], expected=1)


def test_run_skips_locally_shadowed_candidate(tmp_path: Path) -> None:
    """A parameter or local binding prevents unsafe global replacement.

    Args:
        tmp_path: Isolated test filesystem.

    """
    source: str = dedent(
        text=(
            "    from typing import Final\n    X: Final[int] = 1\n    def valu"
            "e(X: int) -> int:\n        return X\n    "
        ),
    )
    target: Path = write_source(
        root=tmp_path,
        relative="app.py",
        source=source,
    )
    report: ScanReport = make_refactor(root=tmp_path, dry_run=False).run()
    expect_equal(actual=report.planned, expected=0)
    expect_equal(actual=target.read_text(encoding="utf-8"), expected=source)


def test_run_rewrites_relative_direct_imports(tmp_path: Path) -> None:
    """Package-relative imports follow a moved constant.

    Args:
        tmp_path: Isolated test filesystem.

    """
    write_source(root=tmp_path, relative="pkg/__init__.py", source="")
    write_source(
        root=tmp_path,
        relative="pkg/settings.py",
        source="from typing import Final\nX: Final[int] = 1\n",
    )
    consumer: Path = write_source(
        root=tmp_path,
        relative="pkg/consumer.py",
        source="from .settings import X\nVALUE = X\n",
    )
    make_refactor(root=tmp_path, dry_run=False).run()
    output: str = consumer.read_text(encoding="utf-8")
    expect_in(member="from .settings import Constants", container=output)
    expect_in(member="VALUE = Constants.x", container=output)


def test_run_leaves_star_import_provider_unchanged(tmp_path: Path) -> None:
    """A star-imported provider is excluded instead of breaking its API.

    Args:
        tmp_path: Isolated test filesystem.

    """
    provider_source: str = "from typing import Final\nX: Final[int] = 1\n"
    provider: Path = write_source(
        root=tmp_path,
        relative="settings.py",
        source=provider_source,
    )
    write_source(
        root=tmp_path,
        relative="consumer.py",
        source="from settings import *\nVALUE = X\n",
    )
    report: ScanReport = make_refactor(root=tmp_path, dry_run=False).run()
    expect_equal(actual=report.planned, expected=0)
    expect_equal(
        actual=provider.read_text(encoding="utf-8"),
        expected=provider_source,
    )


def test_run_avoids_constants_and_final_name_collisions(
    tmp_path: Path,
) -> None:
    """Generated imports use aliases when consumer or provider names clash.

    Args:
        tmp_path: Isolated test filesystem.

    """
    write_source(
        root=tmp_path,
        relative="settings.py",
        source="from typing import Final\nX: Final[int] = 1\n",
    )
    consumer: Path = write_source(
        root=tmp_path,
        relative="consumer.py",
        source=(
            dedent(
                text=(
                    "    from other import Constants\n    from settings im"
                    "port X\n    VALUE = (Constants, X)\n    "
                ),
            )
        ),
    )
    write_source(
        root=tmp_path,
        relative="other.py",
        source="Constants = 'other'\n",
    )
    provider: Path = write_source(
        root=tmp_path,
        relative="colliding.py",
        source=(
            dedent(
                text=(
                    "    from typing import Final\n    Y: Final[int] = 2\n"
                    "    from other import final\n    "
                ),
            )
        ),
    )
    make_refactor(root=tmp_path, dry_run=False).run()
    rewritten: str = consumer.read_text(encoding="utf-8")
    expect_in(
        member="from settings import Constants as _GroupFinalConstants",
        container=rewritten,
    )
    expect_in(member="_GroupFinalConstants.x", container=rewritten)
    provider_output: str = provider.read_text(encoding="utf-8")
    expect_in(member="final as _group_final_final", container=provider_output)
    expect_in(member="@_group_final_final", container=provider_output)


def test_run_skips_provider_when_import_name_is_rebound(
    tmp_path: Path,
) -> None:
    """A module-level consumer rebind prevents an ambiguous rewrite.

    Args:
        tmp_path: Isolated test filesystem.

    """
    provider_source: str = "from typing import Final\nX: Final[int] = 1\n"
    provider: Path = write_source(
        root=tmp_path,
        relative="settings.py",
        source=provider_source,
    )
    write_source(
        root=tmp_path,
        relative="consumer.py",
        source="from settings import X\nBEFORE = X\nX = 7\nAFTER = X\n",
    )
    report: ScanReport = make_refactor(root=tmp_path, dry_run=False).run()
    expect_equal(actual=report.planned, expected=0)
    expect_equal(
        actual=provider.read_text(encoding="utf-8"),
        expected=provider_source,
    )


def test_run_leaves_partial_and_excluded_files_alone(tmp_path: Path) -> None:
    """Unsafe constants stay and excluded files are never parsed.

    Args:
        tmp_path: Per-test temporary directory.

    """
    write_source(
        root=tmp_path,
        relative="node_modules/broken.py",
        source="def broken(:\n",
    )
    partial: Path = write_source(
        root=tmp_path,
        relative="app.py",
        source=(
            dedent(
                text=(
                    "    from typing import Final\n    A: Final[int] = 1\n"
                    "    TOP = A\n    def helper() -> int:\n        return"
                    " 0\n    B: Final[int] = helper()\n    "
                ),
            )
        ),
    )
    report: ScanReport = make_refactor(root=tmp_path, dry_run=False).run()
    expect_equal(actual=report.files, expected=1)
    expect_equal(actual=report.planned, expected=1)
    expect_equal(actual=report.constants, expected=1)
    output: str = partial.read_text(encoding="utf-8")
    expect_in(member="class Constants:", container=output)
    expect_in(member="a: Final[int] = 1", container=output)
    expect_in(member="from typing import Final, final", container=output)
    expect_in(member="TOP = Constants.a", container=output)
    expect_equal(
        actual=(tmp_path / "node_modules" / "broken.py").read_text(
            encoding="utf-8",
        ),
        expected="def broken(:\n",
    )


def test_run_strips_private_prefix_from_member_names(tmp_path: Path) -> None:
    """Private-prefixed constants lose leading underscores as members.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = write_source(
        root=tmp_path,
        relative="app.py",
        source=(
            dedent(
                text=(
                    "    from typing import Final\n    \n    _LIMIT: Final"
                    "[int] = 10\n    \n    print(_LIMIT)\n    "
                ),
            )
        ),
    )
    report: ScanReport = make_refactor(root=tmp_path, dry_run=False).run()
    expect_equal(actual=report.constants, expected=1)
    output: str = target.read_text(encoding="utf-8")
    expect_in(member="limit: Final[int] = 10", container=output)
    expect_in(member="print(Constants.limit)", container=output)
    expect_not_in(member="_LIMIT", container=output)


def test_run_renames_private_references_between_members(
    tmp_path: Path,
) -> None:
    """Later members use the public spelling of an earlier private member.

    Args:
        tmp_path: Isolated test filesystem.

    """
    target: Path = write_source(
        root=tmp_path,
        relative="app.py",
        source=(
            dedent(
                text=(
                    "    from typing import Final\n    _BASE: Final[int] ="
                    " 2\n    TOTAL: Final[int] = _BASE + 3\n    "
                ),
            )
        ),
    )
    make_refactor(root=tmp_path, dry_run=False).run()
    output: str = target.read_text(encoding="utf-8")
    expect_in(member="base: Final[int] = 2", container=output)
    expect_in(member="total: Final[int] = base + 3", container=output)
    expect_not_in(member="_BASE", container=output)
    namespace: dict[str, object] = run_path(path_name=str(object=target))
    constants: object = namespace["Constants"]
    expect_equal(actual=vars(constants)["total"], expected=5)


def test_run_skips_underscore_member_collisions(tmp_path: Path) -> None:
    """Constants colliding after prefix stripping stay module level.

    Args:
        tmp_path: Per-test temporary directory.

    """
    source: str = dedent(
        text=(
            "    from typing import Final\n    \n    _X: Final[int] = 1\n    X"
            ": Final[int] = 2\n    \n    print(_X, X)\n    "
        ),
    )
    target: Path = write_source(
        root=tmp_path,
        relative="app.py",
        source=source,
    )
    report: ScanReport = make_refactor(root=tmp_path, dry_run=False).run()
    expect_equal(actual=report.planned, expected=0)
    expect_equal(actual=target.read_text(encoding="utf-8"), expected=source)


def test_run_merges_typing_imports_in_member_order(tmp_path: Path) -> None:
    """New typing names merge into existing imports in isort order.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = write_source(
        root=tmp_path,
        relative="app.py",
        source=(
            dedent(
                text=(
                    "    from typing import Final, Protocol\n    \n    X: "
                    "Final[int] = 1\n    \n    class P(Protocol):\n       "
                    " pass\n    "
                ),
            )
        ),
    )
    make_refactor(root=tmp_path, dry_run=False).run()
    output: str = target.read_text(encoding="utf-8")
    expect_in(
        member="from typing import Final, Protocol, final",
        container=output,
    )
    expect_in(member="x: Final[int] = 1", container=output)


def test_run_inserts_typing_import_when_absent(tmp_path: Path) -> None:
    """Qualified Final annotations gain a sorted bare typing import.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = write_source(
        root=tmp_path,
        relative="app.py",
        source=(
            dedent(
                text=(
                    '    """Module."""\n    import typing\n    \n    X: ty'
                    "ping.Final[int] = 1\n    \n    print(X)\n    "
                ),
            )
        ),
    )
    make_refactor(root=tmp_path, dry_run=False).run()
    output: str = target.read_text(encoding="utf-8")
    expect_in(
        member="import typing\nfrom typing import final",
        container=output,
    )
    expect_in(member="x: typing.Final[int] = 1", container=output)
    expect_in(member="print(Constants.x)", container=output)


def test_run_keeps_final_import_when_still_used(tmp_path: Path) -> None:
    """A remaining Final reference preserves the typing import name.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = write_source(
        root=tmp_path,
        relative="app.py",
        source=(
            dedent(
                text=(
                    "    from typing import Final\n    \n    KEEP_ME: Fina"
                    "l[int] = 1\n    other: Final[int] = 2\n    "
                ),
            )
        ),
    )
    make_refactor(root=tmp_path, dry_run=False).run()
    output: str = target.read_text(encoding="utf-8")
    expect_in(member="from typing import Final, final", container=output)
    expect_in(member="keep_me: Final[int] = 1", container=output)
    expect_in(member="other: Final[int] = 2", container=output)


def test_run_places_class_after_docstring_and_imports(tmp_path: Path) -> None:
    """The Constants class lands after the docstring and imports.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = write_source(
        root=tmp_path,
        relative="app.py",
        source=(
            dedent(
                text=(
                    '    """Module docstring."""\n    import os\n    from '
                    "typing import Final\n    \n    X: Final[int] = 1\n   "
                    " \n    print(X, os.sep)\n    "
                ),
            )
        ),
    )
    make_refactor(root=tmp_path, dry_run=False).run()
    output: str = target.read_text(encoding="utf-8")
    expect_in(
        member=(
            dedent(
                text=(
                    '    """Module docstring."""\n    import os\n    from '
                    "typing import Final, final\n    \n    @final\n    cla"
                    "ss Constants:"
                ),
            )
        ),
        container=output,
    )


def test_run_empty_directory(tmp_path: Path) -> None:
    """An empty tree reports zero counts and prints no updates.

    Args:
        tmp_path: Per-test temporary directory.

    """
    report: ScanReport = make_refactor(root=tmp_path).run()
    expect_equal(actual=report.files, expected=0)
    expect_equal(actual=report.planned, expected=0)
    expect_equal(actual=report.constants, expected=0)
    expect_equal(actual=report.changed, expected=0)


def test_summary_table_labels_modes() -> None:
    """The summary table switches the changed label per mode."""
    dry: str = private_result(
        owner=Cli,
        name="_summary",
        kind=str,
        report=ScanReport(
            files=3,
            planned=1,
            constants=2,
            changed=1,
            dry_run=True,
        ),
    )
    expect_in(member="metric", container=dry)
    expect_in(member="files scanned", container=dry)
    expect_in(member="modules planned", container=dry)
    expect_in(member="constants moved", container=dry)
    expect_in(member="files that would change", container=dry)
    applied: str = private_result(
        owner=Cli,
        name="_summary",
        kind=str,
        report=ScanReport(
            files=3,
            planned=1,
            constants=2,
            changed=1,
            dry_run=False,
        ),
    )
    expect_in(member="files changed", container=applied)
    expect_not_in(member="\x1b[", container=applied)


def test_summary_colored_on_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Terminal output decorates the summary with ANSI codes.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.delenv(name="NO_COLOR", raising=False)
    fake: FakeStdout = FakeStdout()
    monkeypatch.setattr(target=core_module, name="stdout", value=fake)
    summary: str = private_result(
        owner=Cli,
        name="_summary",
        kind=str,
        report=ScanReport(
            files=1,
            planned=1,
            constants=1,
            changed=1,
            dry_run=False,
        ),
    )
    expect_in(member="\x1b[1m", container=summary)


def test_cli_parser_defaults_and_dry_run(tmp_path: Path) -> None:
    """The parser defaults to apply mode and honors --dry-run.

    Args:
        tmp_path: Per-test temporary directory.

    """
    arguments: Arguments = Cli.parser().parse_args(
        args=[str(object=tmp_path)],
        namespace=Arguments(),
    )
    expect_equal(actual=arguments.root, expected=tmp_path)
    expect_false(condition=arguments.dry_run)
    dry: Arguments = Cli.parser().parse_args(
        args=[str(object=tmp_path), "--dry-run"],
        namespace=Arguments(),
    )
    expect_true(condition=dry.dry_run)


def test_run_rewrites_legacy_reference_to_snake_case_member(
    tmp_path: Path,
) -> None:
    """A stale uppercase reference follows an already-normalized provider.

    Args:
        tmp_path: Isolated test filesystem.

    """
    write_source(
        root=tmp_path,
        relative="provider.py",
        source=(
            dedent(
                text=(
                    "    from typing import Final, final\n    \n    @final"
                    '\n    class Constants:\n        """Group module-level'
                    " constants.\n    \n        Attributes:\n            w"
                    "orkspace_version:\n                Grouped module con"
                    'stant.\n        """\n        workspace_version: Final'
                    "[int] = 3\n    "
                ),
            )
        ),
    )
    consumer: Path = write_source(
        root=tmp_path,
        relative="consumer.py",
        source=(
            dedent(
                text=(
                    "    from provider import Constants\n    \n    VALUE ="
                    " Constants.WORKSPACE_VERSION\n    "
                ),
            )
        ),
    )
    make_refactor(root=tmp_path, dry_run=False).run()
    output: str = consumer.read_text(encoding="utf-8")
    expect_in(member="Constants.workspace_version", container=output)
    expect_not_in(member="Constants.WORKSPACE_VERSION", container=output)


def test_cli_main_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI entrypoint parses argv and runs the refactor.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    write_source(root=tmp_path, relative="app.py", source="X: Final = 1\n")
    monkeypatch.setattr(
        target=sys,
        name="argv",
        value=["group_final", str(object=tmp_path)],
    )
    expect_equal(actual=Cli.main(), expected=0)
    expect_in(
        member="class Constants:",
        container=(tmp_path / "app.py").read_text(encoding="utf-8"),
    )


def test_main_delegates_to_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The module main forwards to the CLI and returns its status.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=sys,
        name="argv",
        value=["group_final", str(object=tmp_path), "--dry-run"],
    )
    expect_equal(actual=main(), expected=0)


def test_main_module_executes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``python -m group_final`` exits with the CLI status.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=project_python,
        name="switch_to_project_venv",
        value=lambda: None,
    )
    monkeypatch.setattr(
        target=sys,
        name="argv",
        value=["group_final", str(object=tmp_path), "--dry-run"],
    )
    with pytest.raises(expected_exception=SystemExit) as captured:
        run_module(
            mod_name="exactus.packages.group_final",
            run_name="__main__",
        )
    expect_equal(actual=captured.value.code, expected=0)


def test_example_dry_run_completes() -> None:
    """The bundled example finishes a dry-run demonstration."""
    expect_equal(actual=example_main(), expected=0)


def test_examples_main_module_executes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``python -m group_final.examples`` exits successfully.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=project_python,
        name="switch_to_project_venv",
        value=lambda: None,
    )
    with pytest.raises(expected_exception=SystemExit) as captured:
        run_module(
            mod_name="exactus.packages.group_final.examples",
            run_name="__main__",
        )
    expect_equal(actual=captured.value.code, expected=0)


def test_run_merges_constants_into_existing_class(tmp_path: Path) -> None:
    """Module constants join an existing generated ``Constants`` class.

    Args:
        tmp_path: Isolated test filesystem.

    """
    target: Path = write_source(
        root=tmp_path,
        relative="module.py",
        source=(
            dedent(
                text=(
                    "    from typing import Final, final\n    \n    \n    "
                    '@final\n    class Constants:\n        """Group module'
                    "-level constants.\n    \n        Attributes:\n       "
                    "     docstring_width: Grouped module constant.\n    "
                    '\n        """\n    \n        docstring_width: Final[i'
                    "nt] = 70\n    \n    \n    REPAIR_SOURCES: Final[tuple"
                    "[str, ...]] = ('x = 1\\n',)\n    CONCAT_SOURCES: Fina"
                    "l[tuple[str, ...]] = ('y = 2\\n',)\n    print(REPAIR_"
                    "SOURCES, CONCAT_SOURCES)\n    "
                ),
            )
        ),
    )
    report: ScanReport = make_refactor(root=tmp_path, dry_run=False).run()
    expect_equal(actual=report.planned, expected=1)
    expect_equal(actual=report.constants, expected=2)
    rewritten: str = target.read_text(encoding="utf-8")
    expect_in(
        member="    repair_sources: Final[tuple[str, ...]]",
        container=rewritten,
    )
    expect_in(
        member="    concat_sources: Final[tuple[str, ...]]",
        container=rewritten,
    )
    expect_in(
        member="        repair_sources: Grouped module constant.",
        container=rewritten,
    )
    expect_in(member="Constants.repair_sources", container=rewritten)
    expect_in(member="Constants.concat_sources", container=rewritten)
    expect_not_in(member="REPAIR_SOURCES: Final", container=rewritten)
    second: ScanReport = make_refactor(root=tmp_path, dry_run=False).run()
    expect_equal(actual=second.planned, expected=0)
    expect_equal(actual=target.read_text(encoding="utf-8"), expected=rewritten)


def test_run_skips_merging_into_unrelated_constants(tmp_path: Path) -> None:
    """A non-generated ``Constants`` class still blocks the rewrite.

    Args:
        tmp_path: Isolated test filesystem.

    """
    target: Path = write_source(
        root=tmp_path,
        relative="module.py",
        source=(
            dedent(
                text=(
                    "    from typing import Final\n    \n    class Constan"
                    "ts:\n        pass\n    \n    VALUE: Final[int] = 1\n "
                    "   "
                ),
            )
        ),
    )
    report: ScanReport = make_refactor(root=tmp_path, dry_run=False).run()
    expect_equal(actual=report.planned, expected=0)
    expect_equal(
        actual=target.read_text(encoding="utf-8"),
        expected=(
            dedent(
                text=(
                    "    from typing import Final\n    \n    class Constan"
                    "ts:\n        pass\n    \n    VALUE: Final[int] = 1\n "
                    "   "
                ),
            )
        ),
    )


def test_run_skips_member_name_collision_on_merge(tmp_path: Path) -> None:
    """A constant whose member name already exists is left alone.

    Args:
        tmp_path: Isolated test filesystem.

    """
    target: Path = write_source(
        root=tmp_path,
        relative="module.py",
        source=(
            dedent(
                text=(
                    "    from typing import Final, final\n    \n    \n    "
                    '@final\n    class Constants:\n        """Group module'
                    "-level constants.\n    \n        Attributes:\n       "
                    '     value: Grouped module constant.\n    \n        "'
                    '""\n    \n        value: Final[int] = 1\n    \n    \n'
                    "    VALUE: Final[int] = 2\n    print(VALUE)\n    "
                ),
            )
        ),
    )
    report: ScanReport = make_refactor(root=tmp_path, dry_run=False).run()
    expect_equal(actual=report.planned, expected=0)
    rewritten: str = target.read_text(encoding="utf-8")
    expect_in(member="VALUE: Final[int] = 2", container=rewritten)
    expect_in(member="print(VALUE)", container=rewritten)
