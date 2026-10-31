"""Test read-only unified diff rendering and patcher diff CLI modes.

The suite verifies textual syntax-highlighted unified diffs, builder-level
read-only diff execution, generated update-PYZ diff inspection, preservation
of configured project state during inspection, and safe summaries for binary
content that cannot be represented as textual unified diffs.
"""

from pathlib import Path
from subprocess import CompletedProcess, run
from sys import executable

import pytest

from exactus.packages.patcher import (
    DiffRenderer,
    ProjectSource,
    PyzProjectPatch,
)
from exactus.packages.patcher.cli import PatcherCli


def _expect(*, condition: bool, message: str) -> None:
    """Validate a test condition and raise when it is not satisfied.

    The helper provides explicit test validation without using Python's
    ``assert`` statement. This keeps the tests compatible with Ruff's S101
    security rule without requiring file-level or inline suppressions.

    Args:
        condition: Boolean condition that must evaluate to ``True``.
        message: Human-readable explanation included in the raised exception
            when the condition evaluates to ``False``.

    Raises:
        AssertionError: If ``condition`` evaluates to ``False``.

    """
    if not condition:
        raise AssertionError(message)


@pytest.mark.parametrize(
    ("suffix", "old", "new", "token"),
    [
        (".py", "value = 1\n", "value = 2\n", "\033["),
        (".js", "const x = 1;\n", "const x = 2;\n", "\033["),
        (".css", "a { color: #fff; }\n", "a { color: #000; }\n", "\033["),
        (".html", "<p>old</p>\n", "<p>new</p>\n", "\033["),
        (".json", '{"a": 1}\n', '{"a": 2}\n', "\033["),
        (".toml", 'a = "old"\n', 'a = "new"\n', "\033["),
        (".xml", "<a>old</a>\n", "<a>new</a>\n", "\033["),
    ],
)
def test_highlighted_text_diff(
    tmp_path: Path,
    suffix: str,
    old: str,
    new: str,
    token: str,
) -> None:
    """Verify supported textual formats receive highlighted unified diffs.

    A before and after project are created with a single changed file using
    the parameterized extension. Rendering with color enabled must retain
    conventional unified-diff headers and hunks while also introducing ANSI
    formatting for supported textual formats.

    Args:
        tmp_path: Temporary pytest directory containing the before and after
            project snapshots.
        suffix: File extension identifying the textual syntax to render.
        old: Original textual content written to the before-state file.
        new: Replacement textual content written to the after-state file.
        token: Expected ANSI control-sequence prefix proving that colored
            syntax highlighting was emitted.

    """
    before: Path = tmp_path / "before"
    after: Path = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    filename: str = f"file{suffix}"
    (before / filename).write_text(data=old, encoding="utf-8")
    (after / filename).write_text(data=new, encoding="utf-8")
    rendered: str = DiffRenderer.render(
        before=ProjectSource.from_path(path=before),
        after=ProjectSource.from_path(path=after),
        color=True,
    )
    _expect(
        condition="diff --git" in rendered,
        message=f"Unified diff header is missing for {suffix}.",
    )
    _expect(
        condition="@@" in rendered,
        message=f"Unified diff hunk marker is missing for {suffix}.",
    )
    _expect(
        condition=token in rendered,
        message=f"Expected highlighting is missing for {suffix}.",
    )


def test_builder_diff_is_read_only(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Verify builder diff mode reports changes without creating an output.

    The builder CLI receives valid A and B sources together with ``--diff``.
    It must render the textual difference to standard output while leaving
    the configured patch-output path absent, proving that diff mode is a
    read-only inspection operation.

    Args:
        tmp_path: Temporary pytest directory containing the before and after
            project states and the intentionally unused output path.
        capfd: Pytest capture fixture used to inspect text written to the
            process standard-output file descriptor.

    """
    before: Path = tmp_path / "before"
    after: Path = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    (before / "a.py").write_text(data="x = 1\n", encoding="utf-8")
    (after / "a.py").write_text(data="x = 2\n", encoding="utf-8")
    output: Path = tmp_path / "must-not-exist.pyz"
    status: int = PatcherCli.run(
        arguments=(
            "--a",
            str(object=before),
            "--b",
            str(object=after),
            "--diff",
            "--no-color",
            "--output",
            str(object=output),
        ),
    )
    captured: str = capfd.readouterr().out
    _expect(
        condition=status == 0,
        message="Builder diff mode returned a nonzero status.",
    )
    _expect(
        condition="-x = 1" in captured,
        message="Builder diff omitted the removed source line.",
    )
    _expect(
        condition="+x = 2" in captured,
        message="Builder diff omitted the added source line.",
    )
    _expect(
        condition=not output.exists(),
        message="Read-only builder diff unexpectedly created an output.",
    )


def test_generated_update_diff_is_read_only(tmp_path: Path) -> None:
    """Verify generated update diff mode does not mutate its target project.

    A real executable update is built from two project states and configured
    for a third target directory containing the original content. Invoking
    the generated PYZ with ``--diff`` must report the embedded change while
    preserving the target file exactly as it existed before inspection.

    Args:
        tmp_path: Temporary pytest directory containing the before, after,
            target, and generated update-PYZ paths.

    """
    before: Path = tmp_path / "before"
    after: Path = tmp_path / "after"
    target: Path = tmp_path / "target"
    paths: tuple[Path, ...] = (before, after, target)
    for path in paths:
        path.mkdir()
    (before / "a.py").write_text(data="x = 1\n", encoding="utf-8")
    (after / "a.py").write_text(data="x = 2\n", encoding="utf-8")
    (target / "a.py").write_text(data="x = 1\n", encoding="utf-8")
    update: Path = tmp_path / "update.pyz"
    patch: PyzProjectPatch = PyzProjectPatch.delta(
        a=before,
        b=after,
        project_root=target,
    )
    patch.build(output=update)
    result: CompletedProcess[str] = run(
        args=(executable, str(object=update), "--diff", "--no-color"),
        check=False,
        capture_output=True,
        text=True,
    )
    target_content: str = (target / "a.py").read_text(encoding="utf-8")
    _expect(condition=result.returncode == 0, message=result.stderr)
    _expect(
        condition="-x = 1" in result.stdout,
        message="Generated update diff omitted the removed line.",
    )
    _expect(
        condition="+x = 2" in result.stdout,
        message="Generated update diff omitted the added line.",
    )
    _expect(
        condition=target_content == "x = 1\n",
        message="Generated update diff mutated the configured target.",
    )


def test_binary_diff_summary(tmp_path: Path) -> None:
    """Verify changed binary files are summarized without text decoding.

    Before and after project states are populated with binary files
    containing null bytes and different payloads. Rendering the delta must
    report that the binary files differ rather than attempting to interpret
    arbitrary bytes as source text.

    Args:
        tmp_path: Temporary pytest directory containing the binary before and
            after project states.

    """
    before: Path = tmp_path / "before"
    after: Path = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    (before / "blob.bin").write_bytes(data=b"\0old")
    (after / "blob.bin").write_bytes(data=b"\0new")
    rendered: str = DiffRenderer.render(
        before=ProjectSource.from_path(path=before),
        after=ProjectSource.from_path(path=after),
        color=False,
    )
    _expect(
        condition="Binary files differ" in rendered,
        message="Binary difference summary was not rendered.",
    )
