# Copyright (c) 2026
"""CLI-level behavior of the project renamer: plans, prompts, rollback."""

from __future__ import annotations

from io import StringIO
from shutil import which
from subprocess import CalledProcessError, CompletedProcess, run
from sys import modules, stdin
from textwrap import dedent
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.tests.packages.rename_project.assertions import (
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
)
from rename_project import ask, main, move

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from types import ModuleType


@final
class Constants:
    """Group module-level constants.

    Attributes:
        old: Grouped module constant.
        new: Grouped module constant.
        rp: Grouped module constant.
        cli_help: Grouped module constant.

    """

    old: Final[str] = "abc_cde"
    new: Final[str] = "foo_bar"
    rp: Final[ModuleType] = modules["rename_project"]
    cli_help: Final[ModuleType] = modules["cli_help"]


def _project(*, tmp_path: Path, files: dict[str, str | bytes]) -> Path:
    """Create a project directory named ``abc_cde`` holding ``files``.

    Args:
        tmp_path: Per-test temporary directory.
        files: Relative path to text or bytes content.

    Returns:
        The project root.

    """
    root: Path = tmp_path / Constants.old
    for relative, content in files.items():
        path: Path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            _ = path.write_bytes(data=content)
        else:
            _ = path.write_text(data=content, encoding="utf-8", newline="")
    return root


def _rename(*, root: Path, extra: tuple[str, ...] = ()) -> int:
    """Run the script non-interactively on ``root``.

    Args:
        root: Project root.
        extra: Additional command-line tokens.

    Returns:
        The exit status.

    """
    return main(
        arguments=[str(object=root), "--name", Constants.new, "--yes", *extra],
    )


def _dry(*, root: Path) -> int:
    """Run the script as a dry run on ``root``.

    Args:
        root: Project root.

    Returns:
        The exit status.

    """
    return _rename(root=root, extra=("--dry-run",))


def test_restyles_every_casing(tmp_path: Path) -> None:
    """Each spelling is rendered in the matching style of the new name.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(
        tmp_path=tmp_path,
        files={
            "mod.txt": (
                dedent(
                    text=(
                        "    abc_cde ABC_CDE abc-cde AbcCde abcCde abccde "
                        "abc.cde\n    # Abc Cde ABC CDE abc cde\n    "
                    ),
                )
            ),
        },
    )
    expect_equal(
        actual=_rename(root=root, extra=("--dotted-code",)),
        expected=0,
    )
    moved: Path = tmp_path / Constants.new
    expect_false(condition=root.exists())
    expect_equal(
        actual=(moved / "mod.txt").read_text(encoding="utf-8"),
        expected=(
            dedent(
                text=(
                    "    foo_bar FOO_BAR foo-bar FooBar fooBar foobar foo."
                    "bar\n    # Foo Bar FOO BAR foo bar\n    "
                ),
            )
        ),
    )


def test_markdown_heading_and_inline_code(tmp_path: Path) -> None:
    """Headings use Title Case while inline code keeps its style.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(
        tmp_path=tmp_path,
        files={"README.md": "# abc_cde\n\nUse `abc_cde` and abc_cde.\n"},
    )
    expect_equal(actual=_rename(root=root), expected=0)
    expect_equal(
        actual=(tmp_path / Constants.new / "README.md").read_text(
            encoding="utf-8",
        ),
        expected="# Foo Bar\n\nUse `foo_bar` and foo_bar.\n",
    )


def test_single_word_name_follows_file_kind(tmp_path: Path) -> None:
    """An ambiguous spelling resolves by whether the file is code or prose.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "exactus"
    root.mkdir()
    _ = (root / "code.py").write_text(
        data="import exactus\nclass Exactus: ...\nEXACTUS = 1\n",
        encoding="utf-8",
    )
    _ = (root / "doc.md").write_text(
        data="The exactus tool. Exactus it.\n",
        encoding="utf-8",
    )
    status: int = main(
        arguments=[str(object=root), "--name", Constants.new, "--yes"],
    )
    expect_equal(actual=status, expected=0)
    moved: Path = tmp_path / Constants.new
    expect_equal(
        actual=(moved / "code.py").read_text(encoding="utf-8"),
        expected="import foo_bar\nclass FooBar: ...\nFOO_BAR = 1\n",
    )
    expect_equal(
        actual=(moved / "doc.md").read_text(encoding="utf-8"),
        expected="The foo bar tool. Foo Bar it.\n",
    )


def test_preserves_crlf_bom_and_mode(tmp_path: Path) -> None:
    """Line endings, a BOM, and the executable bit survive the rewrite.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(
        tmp_path=tmp_path,
        files={"a.txt": b"\xef\xbb\xbfabc_cde\r\nabc_cde\r\n"},
    )
    path: Path = root / "a.txt"
    path.chmod(mode=493)
    expect_equal(actual=_rename(root=root), expected=0)
    moved: Path = tmp_path / Constants.new / "a.txt"
    expect_equal(
        actual=moved.read_bytes(),
        expected=b"\xef\xbb\xbffoo_bar\r\nfoo_bar\r\n",
    )
    expect_equal(actual=moved.stat().st_mode & 511, expected=493)


def test_absolute_paths(tmp_path: Path) -> None:
    """In-project paths become relative; external ones are shielded.

    Args:
        tmp_path: Per-test temporary directory.

    """
    external: Path = tmp_path / "elsewhere" / Constants.old
    external.mkdir(parents=True)
    root: Path = _project(tmp_path=tmp_path, files={"keep": ""})
    inside: str = f"{root}/src/x.py"
    _ = (root / "notes.cfg").write_text(
        data=f"inside={inside}\nouter={external}\n",
        encoding="utf-8",
    )
    expect_equal(actual=_rename(root=root), expected=0)
    text: str = (tmp_path / Constants.new / "notes.cfg").read_text(
        encoding="utf-8",
    )
    expect_in(member="inside=src/x.py", container=text)
    expect_in(member=f"outer={external}", container=text)


def test_shebang_binary_and_symlink_untouched(tmp_path: Path) -> None:
    """Shebangs, binary payloads, and symlinks are never rewritten.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(
        tmp_path=tmp_path,
        files={
            "run": "#!/usr/bin/env abc_cde\nprint('abc_cde')\n",
            "blob.bin": b"\x00abc_cde\x00",
        },
    )
    (root / "link.txt").symlink_to(target="run")
    expect_equal(actual=_rename(root=root), expected=0)
    moved: Path = tmp_path / Constants.new
    expect_equal(
        actual=(moved / "run").read_text(encoding="utf-8"),
        expected="#!/usr/bin/env abc_cde\nprint('foo_bar')\n",
    )
    expect_equal(
        actual=(moved / "blob.bin").read_bytes(),
        expected=b"\x00abc_cde\x00",
    )
    expect_true(condition=(moved / "link.txt").is_symlink())


def test_renames_files_and_directories(tmp_path: Path) -> None:
    """Names carrying the old name are restyled, deepest first.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(
        tmp_path=tmp_path,
        files={
            "abc_cde/abc_cde.py": "x = 1\n",
            "exactus/docs/AbcCde.md": "y\n",
        },
    )
    expect_equal(actual=_rename(root=root), expected=0)
    moved: Path = tmp_path / Constants.new
    expect_true(condition=(moved / "foo_bar" / "foo_bar.py").is_file())
    expect_true(condition=(moved / "exactus" / "docs" / "FooBar.md").is_file())


def test_pyproject_name_is_detected(tmp_path: Path) -> None:
    """The distribution name is an old name even if the directory differs.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "checkout"
    root.mkdir()
    _ = (root / "pyproject.toml").write_text(
        data='[project]\nname = "abc-cde"\n',
        encoding="utf-8",
    )
    _ = (root / "a.py").write_text(data="import abc_cde\n", encoding="utf-8")
    status: int = main(
        arguments=[str(object=root), "--name", Constants.new, "--yes"],
    )
    expect_equal(actual=status, expected=0)
    expect_equal(
        actual=(tmp_path / Constants.new / "a.py").read_text(encoding="utf-8"),
        expected="import foo_bar\n",
    )
    expect_in(
        member='name = "foo-bar"',
        container=(tmp_path / Constants.new / "pyproject.toml").read_text(
            encoding="utf-8",
        ),
    )


def test_dry_run_and_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--dry-run`` changes nothing and writing needs ``--yes``.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    root: Path = _project(tmp_path=tmp_path, files={"a.py": "abc_cde\n"})
    expect_equal(actual=_rename(root=root, extra=("--dry-run",)), expected=0)
    expect_equal(
        actual=(root / "a.py").read_text(encoding="utf-8"),
        expected="abc_cde\n",
    )
    monkeypatch.setattr(target=stdin, name="isatty", value=lambda: False)
    status: int = main(arguments=[str(object=root), "--name", Constants.new])
    expect_equal(actual=status, expected=1)
    expect_true(condition=root.exists())


def test_collisions_stop_before_any_change(tmp_path: Path) -> None:
    """Two paths mapping to one destination abort the whole rename.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(
        tmp_path=tmp_path,
        files={
            "abc_cde.txt": "a\n",
            "foo_bar.txt": "b\n",
            "m.py": "abc_cde\n",
        },
    )
    expect_equal(actual=_rename(root=root), expected=1)
    expect_equal(
        actual=(root / "m.py").read_text(encoding="utf-8"),
        expected="abc_cde\n",
    )
    (tmp_path / Constants.new).mkdir()
    clash: int = _rename(
        root=_project(tmp_path=tmp_path / "x", files={"b.py": "abc_cde\n"}),
    )
    expect_equal(actual=clash, expected=0)


def test_existing_root_target_is_refused(tmp_path: Path) -> None:
    """A target directory that already exists aborts the rename.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path, files={"a.py": "abc_cde\n"})
    (tmp_path / Constants.new).mkdir()
    expect_equal(actual=_rename(root=root), expected=1)
    expect_equal(
        actual=(root / "a.py").read_text(encoding="utf-8"),
        expected="abc_cde\n",
    )


def test_rolls_back_when_a_step_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing rename restores contents and names.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    root: Path = _project(
        tmp_path=tmp_path,
        files={"a.py": "abc_cde\n", "abc_cde.txt": "x\n"},
    )
    real: Callable[..., None] = move

    def flaky(*, source: Path, destination: Path) -> None:
        """Fail on the root rename only.

        Args:
            source: Existing path.
            destination: New path.

        Raises:
            OSError: When renaming the project root.

        """
        if source == root:
            msg: str = "disk full"
            raise OSError(msg)
        real(source=source, destination=destination)

    monkeypatch.setattr(target=Constants.rp, name="move", value=flaky)
    expect_equal(actual=_rename(root=root), expected=1)
    expect_equal(
        actual=(root / "a.py").read_text(encoding="utf-8"),
        expected="abc_cde\n",
    )
    expect_true(condition=(root / "abc_cde.txt").is_file())


def test_invalid_and_identical_names(tmp_path: Path) -> None:
    """Bad targets are refused with a non-zero status.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path, files={"a.py": "abc_cde\n"})
    for name in ("9lives", "a/b", "", Constants.old, "AbcCde"):
        status: int = main(
            arguments=[str(object=root), "--name", name, "--yes"],
        )
        expect_equal(actual=status, expected=1)
    expect_true(condition=root.exists())


def test_loose_boundary_reaches_inside_identifiers(tmp_path: Path) -> None:
    """``--boundary loose`` renames compounds such as ``abc_cde_core``.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path, files={"a.py": "abc_cde_core\n"})
    expect_equal(actual=_rename(root=root), expected=0)
    expect_equal(
        actual=(tmp_path / Constants.new / "a.py").read_text(encoding="utf-8"),
        expected="abc_cde_core\n",
    )
    second: Path = _project(
        tmp_path=tmp_path / "two",
        files={"a.py": "abc_cde_core\n"},
    )
    expect_equal(
        actual=_rename(root=second, extra=("--boundary", "loose")),
        expected=0,
    )
    expect_equal(
        actual=(tmp_path / "two" / Constants.new / "a.py").read_text(
            encoding="utf-8",
        ),
        expected="foo_bar_core\n",
    )


@pytest.mark.skipif(which(cmd="git") is None, reason="git is not installed")
def test_gitignored_files_are_left_alone(tmp_path: Path) -> None:
    """Inside a repository only tracked and unignored files are rewritten.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(
        tmp_path=tmp_path,
        files={
            ".gitignore": "ignored.txt\n",
            "kept.txt": "abc_cde\n",
            "ignored.txt": "abc_cde\n",
        },
    )
    _ = run(args=["git", "init", "-q", str(object=root)], check=True)
    expect_equal(actual=_rename(root=root), expected=0)
    moved: Path = tmp_path / Constants.new
    expect_equal(
        actual=(moved / "kept.txt").read_text(encoding="utf-8"),
        expected="foo_bar\n",
    )
    expect_equal(
        actual=(moved / "ignored.txt").read_text(encoding="utf-8"),
        expected="abc_cde\n",
    )


def test_mixed_case_spellings_are_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spellings the matcher cannot restyle are left alone and reported.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    out: StringIO = StringIO()
    err: StringIO = StringIO()
    monkeypatch.setattr(target=Constants.rp, name="stdout", value=out)
    monkeypatch.setattr(target=Constants.rp, name="stderr", value=err)
    root: Path = _project(
        tmp_path=tmp_path,
        files={"a.py": "abc_cde = 1\nclass Abc_Cde: ...\n"},
    )
    expect_equal(actual=_dry(root=root), expected=0)
    expect_in(member="a.py:2", container=err.getvalue())
    expect_in(member="1 unrecognized", container=out.getvalue())


def test_abbreviations_are_exact_and_opt_in(tmp_path: Path) -> None:
    """``AT`` is renamed only when asked, case-sensitively and standalone.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(
        tmp_path=tmp_path,
        files={
            "a.txt": (
                dedent(
                    text=(
                        "    AT = 1\n    started_at = 2\n    look at this"
                        "\n    AT_HOME = 3\n    exactus-tools exactus_tool"
                        "s EXACTUS_TOOLS\n    "
                    ),
                )
            ),
        },
    )
    status: int = main(
        arguments=[
            str(object=root),
            "--name",
            Constants.new,
            "--yes",
            "--from",
            "exactus-tools",
            "--abbrev",
            "AT",
        ],
    )
    expect_equal(actual=status, expected=0)
    expect_equal(
        actual=(tmp_path / Constants.new / "a.txt").read_text(
            encoding="utf-8",
        ),
        expected=(
            dedent(
                text=(
                    "    FB = 1\n    started_at = 2\n    look at this\n   "
                    " AT_HOME = 3\n    foo-bar foo_bar FOO_BAR\n    "
                ),
            )
        ),
    )


def test_short_lowercase_abbreviation_needs_consent(tmp_path: Path) -> None:
    """A lowercase ``at`` is refused unless explicitly allowed.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path, files={"a.py": "x_at = at\n"})
    refused: int = main(
        arguments=[
            str(object=root),
            "--name",
            Constants.new,
            "--yes",
            "--abbrev",
            "at",
        ],
    )
    expect_equal(actual=refused, expected=1)
    expect_equal(
        actual=(root / "a.py").read_text(encoding="utf-8"),
        expected="x_at = at\n",
    )
    allowed: int = main(
        arguments=[
            str(object=root),
            "--name",
            Constants.new,
            "--yes",
            "--abbrev",
            "at=fb",
            "--allow-short-lowercase",
        ],
    )
    expect_equal(actual=allowed, expected=0)
    expect_equal(
        actual=(tmp_path / Constants.new / "a.py").read_text(encoding="utf-8"),
        expected="x_at = fb\n",
    )


class FakeGitHub:
    """Record GitHub CLI calls instead of contacting GitHub.

    Attributes:
        calls: Every ``gh`` argument list received.
        fail: Whether ``repo rename`` should fail.

    """

    def __init__(self, *, fail: bool = False) -> None:
        """Create the recorder.

        Args:
            fail: Make ``repo rename`` raise.

        """
        self.calls: list[list[str]] = []
        self.fail: bool = fail

    def __call__(self, *, arguments: list[str]) -> CompletedProcess[bytes]:
        """Record one call.

        Args:
            arguments: Arguments after ``gh``.

        Returns:
            A successful empty result.

        Raises:
            CalledProcessError: For ``repo rename`` when configured to fail.

        """
        self.calls.append(arguments)
        if self.fail and arguments[:2] == ["repo", "rename"]:
            raise CalledProcessError(returncode=1, cmd=["gh", *arguments])
        return CompletedProcess(args=arguments, returncode=0, stdout=b"")


def _github_project(*, tmp_path: Path) -> Path:
    """Create a git project whose origin is ``github.com/me/abc_cde``.

    Args:
        tmp_path: Per-test temporary directory.

    Returns:
        The project root.

    """
    root: Path = _project(
        tmp_path=tmp_path,
        files={"README.md": "Clone https://github.com/me/abc_cde.git\n"},
    )
    _ = run(args=["git", "init", "-q", str(object=root)], check=True)
    _ = run(
        args=[
            "git",
            "-C",
            str(object=root),
            "remote",
            "add",
            "origin",
            "https://github.com/me/abc_cde.git",
        ],
        check=True,
    )
    return root


def _origin(*, root: Path) -> str:
    """Read the ``origin`` URL.

    Args:
        root: Repository working tree.

    Returns:
        The configured URL.

    """
    return (
        run(
            args=[
                "git",
                "-C",
                str(object=root),
                "remote",
                "get-url",
                "origin",
            ],
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )


@pytest.mark.skipif(which(cmd="git") is None, reason="git is not installed")
def test_github_rename_updates_repo_remote_and_urls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--github`` renames the repository, the remote, and file URLs.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    fake: FakeGitHub = FakeGitHub()
    monkeypatch.setattr(target=Constants.rp, name="_gh", value=fake)
    root: Path = _github_project(tmp_path=tmp_path)
    dry: int = _rename(root=root, extra=("--github", "--dry-run"))
    expect_equal(actual=dry, expected=0)
    expect_equal(actual=fake.calls, expected=[["auth", "status"]])
    expect_equal(actual=_rename(root=root, extra=("--github",)), expected=0)
    moved: Path = tmp_path / Constants.new
    expect_in(
        member=[
            "repo",
            "rename",
            Constants.new,
            "--repo",
            "me/abc_cde",
            "--yes",
        ],
        container=fake.calls,
    )
    expect_equal(
        actual=_origin(root=moved),
        expected="https://github.com/me/foo_bar.git",
    )
    expect_equal(
        actual=(moved / "README.md").read_text(encoding="utf-8"),
        expected="Clone https://github.com/me/foo_bar.git\n",
    )


@pytest.mark.skipif(which(cmd="git") is None, reason="git is not installed")
def test_github_failure_rolls_back_local_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed repository rename leaves files, folder, and remote intact.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=Constants.rp,
        name="_gh",
        value=FakeGitHub(fail=True),
    )
    root: Path = _github_project(tmp_path=tmp_path)
    expect_equal(actual=_rename(root=root, extra=("--github",)), expected=1)
    expect_true(condition=root.is_dir())
    expect_equal(
        actual=(root / "README.md").read_text(encoding="utf-8"),
        expected="Clone https://github.com/me/abc_cde.git\n",
    )
    expect_equal(
        actual=_origin(root=root),
        expected="https://github.com/me/abc_cde.git",
    )


def test_github_needs_a_github_remote(tmp_path: Path) -> None:
    """A project without a GitHub remote is refused before any change.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path, files={"a.py": "abc_cde\n"})
    expect_equal(actual=_rename(root=root, extra=("--github",)), expected=1)
    expect_equal(
        actual=(root / "a.py").read_text(encoding="utf-8"),
        expected="abc_cde\n",
    )


@pytest.mark.skipif(which(cmd="git") is None, reason="git is not installed")
def test_github_rename_is_undone_when_repointing_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the remote cannot be repointed, the GitHub rename is reversed.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    fake: FakeGitHub = FakeGitHub()
    monkeypatch.setattr(target=Constants.rp, name="_gh", value=fake)

    def broken(*, change: object, directory: Path, undo: bool) -> None:
        """Fail only when repointing forward.

        Args:
            change: Planned rename.
            directory: Working tree.
            undo: Whether the call undoes a previous repoint.

        Raises:
            CalledProcessError: When not undoing.

        """
        del change, directory
        if not undo:
            raise CalledProcessError(returncode=1, cmd=["git"])

    monkeypatch.setattr(
        target=Constants.rp,
        name="_repoint_remote",
        value=broken,
    )
    root: Path = _github_project(tmp_path=tmp_path)
    expect_equal(actual=_rename(root=root, extra=("--github",)), expected=1)
    renames: list[list[str]] = [
        call for call in fake.calls if call[:2] == ["repo", "rename"]
    ]
    expect_equal(
        actual=[call[2] for call in renames],
        expected=[Constants.new, "abc_cde"],
    )
    expect_true(condition=root.is_dir())


class FakeTerminal:
    """Scripted standard input that claims to be a terminal.

    Attributes:
        answers: Lines the user "types", consumed in order.
        asked: How many lines were read.

    """

    def __init__(self, *, answers: list[str]) -> None:
        """Create the terminal.

        Args:
            answers: Lines to return from ``readline``.

        """
        self.answers: list[str] = answers
        self.asked: int = 0

    @staticmethod
    def isatty() -> bool:
        """Report terminal attachment.

        Returns:
            Always true.

        """
        return True

    def readline(self) -> str:
        """Return the next scripted answer.

        Returns:
            The answer with a newline, or an empty string at end of input.

        """
        self.asked += 1
        return self.answers.pop(0) + "\n" if self.answers else ""


def _interactive(
    *,
    monkeypatch: pytest.MonkeyPatch,
    answers: list[str],
) -> tuple[FakeTerminal, StringIO]:
    """Attach a scripted terminal and capture the script's output.

    Args:
        monkeypatch: Pytest patching helper.
        answers: Lines the user "types".

    Returns:
        The terminal and the captured standard output.

    """
    terminal: FakeTerminal = FakeTerminal(answers=answers)
    out: StringIO = StringIO()
    monkeypatch.setattr(target=Constants.rp, name="stdin", value=terminal)
    monkeypatch.setattr(target=Constants.rp, name="stdout", value=out)
    return (terminal, out)


@pytest.mark.skipif(which(cmd="git") is None, reason="git is not installed")
def test_discovered_repository_is_offered_and_renamed_on_yes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without ``--github`` a found repository is offered; "y" renames it.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    fake: FakeGitHub = FakeGitHub()
    monkeypatch.setattr(target=Constants.rp, name="_gh", value=fake)
    _, out = _interactive(monkeypatch=monkeypatch, answers=["y", "y"])
    root: Path = _github_project(tmp_path=tmp_path)
    status: int = main(arguments=[str(object=root), "--name", Constants.new])
    expect_equal(actual=status, expected=0)
    expect_in(
        member="Rename GitHub repository me/abc_cde to me/foo_bar?",
        container=out.getvalue(),
    )
    expect_equal(
        actual=_origin(root=tmp_path / Constants.new),
        expected="https://github.com/me/foo_bar.git",
    )


@pytest.mark.skipif(which(cmd="git") is None, reason="git is not installed")
def test_declining_the_github_question_keeps_the_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Answering "n" renames locally but leaves GitHub untouched.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    fake: FakeGitHub = FakeGitHub()
    monkeypatch.setattr(target=Constants.rp, name="_gh", value=fake)
    _interactive(monkeypatch=monkeypatch, answers=["y", "n"])
    root: Path = _github_project(tmp_path=tmp_path)
    status: int = main(arguments=[str(object=root), "--name", Constants.new])
    expect_equal(actual=status, expected=0)
    expect_equal(actual=fake.calls, expected=[])
    expect_equal(
        actual=_origin(root=tmp_path / Constants.new),
        expected="https://github.com/me/abc_cde.git",
    )


@pytest.mark.skipif(which(cmd="git") is None, reason="git is not installed")
def test_yes_flag_never_renames_a_discovered_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a terminal, ``--yes`` leaves a found repository alone.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    fake: FakeGitHub = FakeGitHub()
    monkeypatch.setattr(target=Constants.rp, name="_gh", value=fake)
    root: Path = _github_project(tmp_path=tmp_path)
    expect_equal(actual=_rename(root=root), expected=0)
    expect_equal(actual=fake.calls, expected=[])
    expect_equal(
        actual=_origin(root=tmp_path / Constants.new),
        expected="https://github.com/me/abc_cde.git",
    )


@pytest.mark.skipif(which(cmd="git") is None, reason="git is not installed")
def test_no_github_flag_never_asks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--no-github`` skips both the discovery and the question.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    terminal, out = _interactive(monkeypatch=monkeypatch, answers=["y"])
    root: Path = _github_project(tmp_path=tmp_path)
    status: int = main(
        arguments=[str(object=root), "--name", Constants.new, "--no-github"],
    )
    expect_equal(actual=status, expected=0)
    expect_equal(actual=terminal.asked, expected=1)
    expect_false(condition="GitHub repository" in out.getvalue())


def test_prompt_formatting_and_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """The prompt is ANSI-styled on a terminal and re-asks on bad input.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=Constants.cli_help,
        name="styled",
        value=lambda: True,
    )
    terminal, out = _interactive(
        monkeypatch=monkeypatch,
        answers=["maybe", ""],
    )
    answer: bool = ask(
        question="Proceed?",
        details=("some detail",),
        default=True,
    )
    expect_true(condition=answer)
    text: str = out.getvalue()
    expect_in(member="\x1b[1mProceed?\x1b[0m", container=text)
    expect_in(member="\x1b[2m[Y/n]\x1b[0m", container=text)
    expect_in(member="Please answer y or n.", container=text)
    expect_equal(actual=terminal.asked, expected=2)


def _dotted(*, tmp_path: Path, name: str, content: str) -> str:
    """Rename a one-file project in ``auto`` mode and return the result.

    Args:
        tmp_path: Per-test temporary directory.
        name: Name of the file holding ``content``.
        content: File content.

    Returns:
        The rewritten file content.

    """
    root: Path = _project(tmp_path=tmp_path, files={name: content})
    expect_equal(actual=_rename(root=root, extra=("--dotted",)), expected=0)
    return (tmp_path / Constants.new / name).read_text(encoding="utf-8")


def test_dotted_python_attribute_vs_string(tmp_path: Path) -> None:
    """Python code and f-strings keep ``abc.cde``; plain strings change.

    Args:
        tmp_path: Per-test temporary directory.

    """
    source: str = dedent(
        text=(
            "    value = abc.cde\n    obj.abc.cde = 1\n    # see abc.cde\n    "
            'logger = getLogger("abc.cde")\n    """Docs for abc.cde."""\n    l'
            'abel = f"abc.cde {value}"\n    '
        ),
    )
    expect_equal(
        actual=_dotted(tmp_path=tmp_path, name="a.py", content=source),
        expected=(
            dedent(
                text=(
                    "    value = abc.cde\n    obj.abc.cde = 1\n    # see f"
                    'oo.bar\n    logger = getLogger("foo.bar")\n    """Doc'
                    's for foo.bar."""\n    label = f"abc.cde {value}"\n  '
                    "  "
                ),
            )
        ),
    )


def test_dotted_javascript_and_css(tmp_path: Path) -> None:
    """Property access and CSS selectors are kept; strings are renamed.

    Args:
        tmp_path: Per-test temporary directory.

    """
    script: str = dedent(
        text=(
            "    const v = abc.cde;\n    // abc.cde note\n    const t = 'abc.c"
            "de';\n    const u = `x ${abc.cde} abc.cde`;\n    "
        ),
    )
    expect_equal(
        actual=_dotted(tmp_path=tmp_path, name="a.js", content=script),
        expected=(
            dedent(
                text=(
                    "    const v = abc.cde;\n    // foo.bar note\n    cons"
                    "t t = 'foo.bar';\n    const u = `x ${abc.cde} abc.cde"
                    "`;\n    "
                ),
            )
        ),
    )
    styles: str = "abc.cde { color: red }\n/* abc.cde */\n"
    expect_equal(
        actual=_dotted(
            tmp_path=tmp_path / "css",
            name="a.css",
            content=styles,
        ),
        expected="abc.cde { color: red }\n/* foo.bar */\n",
    )


def test_dotted_markdown_and_chains(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prose is renamed; inline code and longer dotted chains are reported.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    err: StringIO = StringIO()
    monkeypatch.setattr(target=Constants.rp, name="stderr", value=err)
    text: str = "Use abc.cde here, `abc.cde` there, and abc.cde.json too.\n"
    expect_equal(
        actual=_dotted(tmp_path=tmp_path, name="a.md", content=text),
        expected="Use foo.bar here, `abc.cde` there, and foo.bar.json too.\n",
    )
    expect_in(
        member="guarded: dotted code reference",
        container=err.getvalue(),
    )


def test_dotted_import_paths_that_exist_are_kept(tmp_path: Path) -> None:
    """A dotted name that addresses a real package path is never renamed.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(
        tmp_path=tmp_path,
        files={
            "abc/cde/__init__.py": "",
            "m.py": 'import abc.cde\nname = "abc.cde"\n',
        },
    )
    expect_equal(actual=_rename(root=root), expected=0)
    expect_equal(
        actual=(tmp_path / Constants.new / "m.py").read_text(encoding="utf-8"),
        expected='import abc.cde\nname = "abc.cde"\n',
    )


def test_dotted_modes_override_detection(tmp_path: Path) -> None:
    """``--dotted always`` renames code too; ``never`` renames nothing.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path, files={"a.py": "x = abc.cde\n"})
    expect_equal(
        actual=_rename(root=root, extra=("--dotted-code",)),
        expected=0,
    )
    expect_equal(
        actual=(tmp_path / Constants.new / "a.py").read_text(encoding="utf-8"),
        expected="x = foo.bar\n",
    )
    second: Path = _project(
        tmp_path=tmp_path / "two",
        files={"a.py": '"abc.cde"\n'},
    )
    expect_equal(actual=_rename(root=second, extra=()), expected=0)
    expect_equal(
        actual=(tmp_path / "two" / Constants.new / "a.py").read_text(
            encoding="utf-8",
        ),
        expected='"abc.cde"\n',
    )
