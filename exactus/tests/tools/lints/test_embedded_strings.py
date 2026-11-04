# Copyright (c) 2026
"""Regression and randomized invariance tests for embedded string rendering."""

from __future__ import annotations

from ast import Constant, Module, dump, parse, walk
from hashlib import sha256
from string import ascii_letters, digits
from subprocess import CalledProcessError, CompletedProcess
from sys import executable
from textwrap import dedent
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.tools.lints import embedded_strings, string_transform
from exactus.tools.lints.embedded_strings import (
    EmbeddedLanguage,
    LiteralOptions,
    format_embedded_source,
    rewrite_multiline_literals,
    run_checked_command,
)
from exactus.tools.lints.string_transform import (
    TransformOptions,
    TransformResult,
    atomic_write,
    transform_strings,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@final
class Constants:
    """Group module-level constants.

    Attributes:
        lf: Grouped module constant.

    """

    lf: Final[str] = chr(10)


def verify(*, predicate: bool) -> None:
    """Fail the active test for a violated invariant.

    Args:
        predicate: Required invariant result.

    Raises:
        AssertionError: If the invariant is not true.

    """
    if not predicate:
        msg: str = "Invariant failed"
        raise AssertionError(msg)


@pytest.mark.parametrize(
    "value",
    [
        Constants.lf.join(
            (
                "    from importlib import import_module",
                "    from types import ModuleType",
                "    ",
            ),
        ),
        Constants.lf.join(
            (
                '            """Embedded Python docstring."""',
                "            from sys import argv",
                '            stdout.write("OK\\n")',
                "            ",
            ),
        ),
        Constants.lf.join(
            (
                "            const value = process.argv[2];",
                "            console.log('OK');",
                "            ",
            ),
        ),
        Constants.lf.join(
            (
                '    <main class="wide"><style>body { color: red }',
                "</style></main>    ",
            ),
        ),
        Constants.lf.join(
            (
                "    .alpha { color: #fff; }",
                "    .beta { display: flex; }",
                "    ",
            ),
        ),
        "    ",
        Constants.lf.join(("a", "b", "")),
        Constants.lf.join(("   ", "", "   ")),
        "a" * 250 + "" + Constants.lf + "b" * 310,
        Constants.lf.join(('x\\n y\\"z', "\r\t\x00\u2028\u2029")),
        Constants.lf.join(('a"""b', " c'''d")),
        Constants.lf.join(("\"'\"'", "\\")),
        Constants.lf.join(("😀 αλφά 🏁", "2")),
    ],
)
def test_exact_value_and_idempotence(value: str) -> None:
    """Retain all original literal bytes after Python evaluation.

    Args:
        value: Input string containing arbitrary escape-sensitive data.

    """
    original: str = f"""\
from textwrap import dedent
template: str = dedent(text={value!r})
"""
    result: embedded_strings.LiteralRewrite = rewrite_multiline_literals(
        source=original,
        options=LiteralOptions(line_length=79),
    )
    verify(
        predicate=dump(node=parse(source=original), include_attributes=False)
        == dump(node=parse(source=result.source), include_attributes=False),
    )
    verify(
        predicate=rewrite_multiline_literals(source=result.source).source
        == result.source,
    )
    verify(predicate="template" in result.source)
    if result.count:
        verify(predicate="\\" + Constants.lf in result.source)
        verify(
            predicate=all(
                len(row) <= LiteralOptions().line_length
                for row in result.source.splitlines()
            ),
        )
    verify(predicate=dedent(text=value) == dedent(text=value))


def test_concatenated_imports() -> None:
    """Rebuild split import strings with correct spacing and trailing LF."""
    chunks: tuple[str, ...] = (
        Constants.lf.join(
            (
                "    from importlib import import_module",
                "    from importlib.machi",
            ),
        ),
        Constants.lf.join(
            (
                "nery import PathFinder",
                "    from importlib.util import module_fro",
            ),
        ),
        Constants.lf.join(
            (
                "m_spec",
                "    from pathlib import Path",
                "    from sys import modules",
            ),
        ),
        Constants.lf.join(
            (
                " as _modules",
                "    from sys import path as _path",
                "    from types i",
            ),
        ),
        Constants.lf.join(("mport ModuleType", "    ")),
    )
    original: str = (
        Constants.lf.join(("base_imports: str = dedent(", "    text=(", ""))
        + "".join(
            (
                f"""\
        {chunk!r}
"""
            )
            for chunk in chunks
        )
        + Constants.lf.join(("    ),", ")", ""))
    )
    result: embedded_strings.LiteralRewrite = rewrite_multiline_literals(
        source=original,
    )
    verify(predicate=result.count == 1)
    verify(
        predicate="from importlib.machinery import PathFinder"
        in result.source,
    )
    verify(
        predicate=dump(node=parse(source=original), include_attributes=False)
        == dump(node=parse(source=result.source), include_attributes=False),
    )
    verify(
        predicate=rewrite_multiline_literals(source=result.source).source
        == result.source,
    )


def test_documented_python_and_node_examples() -> None:
    """Keep nested Python documentation and JS as literal data."""
    examples: dict[str, str] = {
        "python_probe": Constants.lf.join(
            (
                '            """Run functional probes."""',
                "            from __future__ import annotations",
                "",
                "            from sys import stdout",
                '            stdout.write("OK\\n")',
                "            ",
            ),
        ),
        "node_probe": Constants.lf.join(
            (
                "            const name = process.argv[2];",
                "            const m = require(name);",
                "            if (m) { console.log('OK'); }",
                "            ",
            ),
        ),
        "loader_head": Constants.lf.join(
            (
                "    if (",
                "        _existing := _modules.get(",
                "            {name}",
                "        )",
                (
                    "    ) is not None and Path(getattr(_existing, "
                    '"__file__", "")).resolve() != _file:'
                ),
                "        _package: ModuleType = _existing",
                "    ",
            ),
        ),
    }
    for name, value in examples.items():
        original: str = (
            (
                f"""\
{name}: str = dedent(text=(
"""
            )
            + "".join(
                (
                    f"""\
    {value[index : index + 46]!r}
"""
                )
                for index in range(0, len(value), 46)
            )
            + "))"
            + Constants.lf
        )
        result: embedded_strings.LiteralRewrite = rewrite_multiline_literals(
            source=original,
        )
        verify(predicate=result.count == 1)
        verify(
            predicate=dump(
                node=parse(source=original),
                include_attributes=False,
            )
            == dump(
                node=parse(source=result.source),
                include_attributes=False,
            ),
        )
        verify(
            predicate=all(
                len(line) <= LiteralOptions().line_length
                for line in result.source.splitlines()
            ),
        )


def test_unicode_before_source_token() -> None:
    """Preserve literal positioning following multibyte UTF-8 characters."""
    source: str = 'name = "😀"; value = ("abc\\ndef" "ghi")' + Constants.lf
    result: embedded_strings.LiteralRewrite = rewrite_multiline_literals(
        source=source,
    )
    verify(predicate=result.count == 1)
    verify(
        predicate=dump(node=parse(source=source), include_attributes=False)
        == dump(node=parse(source=result.source), include_attributes=False),
    )


def test_protect_docstrings_and_inline_comments() -> None:
    """Avoid replacing executable docstrings or comment-bearing groups."""
    source: str = dedent(
        text=Constants.lf.join(
            (
                '    """An opening docstring\\nwith an escaped newline."""',
                "    def f() -> str:",
                '        """First\\nSecond."""',
                '        return ("hello\\n"  # do not delete me',
                '                "world")',
                "    ",
            ),
        ),
    )
    result: embedded_strings.LiteralRewrite = rewrite_multiline_literals(
        source=source,
    )
    verify(predicate=result.count == 0)
    verify(predicate=result.source == source)
    verify(
        predicate=any(
            issue.reason == "comment-protected" for issue in result.issues
        ),
    )


def test_formatted_values_preserved() -> None:
    """Render multiline f-strings without altering field expressions."""
    source: str = Constants.lf.join(
        ('name = "x"', "value = f\"{name}:\\n{len('more\\nlines')}\"", ""),
    )
    result: embedded_strings.LiteralRewrite = rewrite_multiline_literals(
        source=source,
    )
    verify(
        predicate=result.count == 1
        and 'f"""' in result.source
        and (
            dump(node=parse(source=source), include_attributes=False)
            == dump(node=parse(source=result.source), include_attributes=False)
        ),
    )
    verify(
        predicate=rewrite_multiline_literals(source=result.source).source
        == result.source,
    )


def test_fstring_readme_concatenation() -> None:
    """Turn adjacent literals and f-strings into readable Markdown."""
    source: str = Constants.lf.join(
        (
            "def make_readme(",
            "    name: str,",
            "    files: list[str],",
            "    size: int,",
            "    requested_lines: str,",
            "    discovered: list[str],",
            ") -> str:",
            "    return (",
            "        f\"# `{name.removesuffix('.zip')}/`\\n\"",
            '        "\\n"',
            (
                '        "Source bundle produced by '
                '`exactus.packages.zip_components`.\\n"'
            ),
            '        "\\n"',
            '        "## Contents\\n"',
            '        "\\n"',
            '        f"- `{name}` — the archive ({len(files)} files, "',
            '        f"{_human_size(size=size)})\\n"',
            (
                "        \"- `TREE.txt` — the archive's members as a "
                'size/date tree\\n"'
            ),
            '        "- `README.md` — this file\\n"',
            '        "\\n"',
            '        "## Selection\\n"',
            '        "\\n"',
            '        f"{requested_lines}"',
            '        "\\n"',
            '        f"Discovered transitively: "',
            (
                "        f\"{', '.join(f'`{item}`' for item in discovered) or "
                "'none'}\\n\""
            ),
            '        "\\n"',
            '        "## Usage\\n"',
            '        "\\n"',
            '        "```bash\\n"',
            '        f"unzip -o {name} -d .\\n"',
            '        "```\\n"',
            '        "\\n"',
            (
                '        "Run at a repository root to restore every member in '
                'place.\\n"'
            ),
            "    )",
            "",
        ),
    )
    result: embedded_strings.LiteralRewrite = rewrite_multiline_literals(
        source=source,
        options=LiteralOptions(line_length=79),
    )
    verify(predicate=result.count == 1 and (not result.issues))
    verify(
        predicate=Constants.lf.join(('f"""\\', "# `")) in result.source
        and Constants.lf.join(("", "", "## Contents", "", "")) in result.source
        and (
            Constants.lf.join(("", "", "## Usage", "", "```bash", ""))
            in result.source
        )
        and ("\\n" not in result.source),
    )
    verify(
        predicate=dump(node=parse(source=source), include_attributes=False)
        == dump(node=parse(source=result.source), include_attributes=False),
    )
    verify(
        predicate=all(
            len(line) <= LiteralOptions().line_length
            for line in result.source.splitlines()
            if line.startswith(("#", "-", "Discovered", "Run", 'f"""'))
        ),
    )
    verify(
        predicate=rewrite_multiline_literals(
            source=result.source,
            options=LiteralOptions(line_length=79),
        ).source
        == result.source,
    )


@pytest.mark.parametrize(
    "expression",
    [
        'f"{{escaped}}: {name!r}\\n" "\\n" f"{count:>{width}}\\n"',
        'f"{name=}\\n" "\\n" f"{len(files):04d}\\n"',
        'f"{name.removesuffix(\'.zip\')}\\n" "\\n"',
        "f\"{' / '.join(f'[{item}]' for item in files)}\\n\" \"\\n\"",
        'f"{name} \\\\ backslash \\" quote\\n" "\\n"',
    ],
)
def test_fstring_ast_and_idempotence(expression: str) -> None:
    """Preserve nested format specifications, literal braces, and escapes.

    Args:
        expression: Syntactically valid f-string expression.

    """
    source: str = f"""\
result = ({expression})
"""
    rewritten: embedded_strings.LiteralRewrite = rewrite_multiline_literals(
        source=source,
    )
    verify(predicate=rewritten.count == 1)
    verify(
        predicate=dump(node=parse(source=source), include_attributes=False)
        == dump(node=parse(source=rewritten.source), include_attributes=False),
    )
    verify(
        predicate=rewrite_multiline_literals(source=rewritten.source).source
        == rewritten.source,
    )


def test_embedded_formatter_refuses_interpolations() -> None:
    """Never send dynamic f-strings into embedded-code formatters."""
    result: embedded_strings.LiteralRewrite = rewrite_multiline_literals(
        source='html_source = f"<h1>{title}</h1>\\n"' + Constants.lf,
        options=LiteralOptions(format_embedded=True, allow_value_changes=True),
    )
    verify(predicate=result.count == 0)
    verify(
        predicate=any(
            issue.reason == "embedded-formatter-does-not-support-fstrings"
            for issue in result.issues
        ),
    )


def test_integrated_pipeline_formats_concatenated_fstrings(
    tmp_path: Path,
) -> None:
    """Run the entire Exactus pipeline, including its legacy dedent pass.

    Args:
        tmp_path: Pytest-managed sandbox for the input Python source.

    """
    source: str = dedent(
        text=Constants.lf.join(
            (
                "    def make(name: str) -> str:",
                "        return (",
                '            f"# {name}\\n"',
                '            "\\n"',
                '            "## Contents\\n"',
                '            "\\n"',
                '            f"- `{name}`\\n"',
                '            "\\n"',
                '            "## Usage\\n"',
                "        )",
                "    ",
            ),
        ),
    )
    path: Path = tmp_path / "sample.py"
    path.write_text(data=source, encoding="utf-8")
    result: TransformResult = transform_strings(
        file=path,
        write=False,
        options=TransformOptions(
            line_length=LiteralOptions().line_length,
            format_interpolations=False,
        ),
    )
    verify(predicate=result.changed and result.count >= 1)
    verify(
        predicate=Constants.lf.join(("", "", "## Contents", "", ""))
        in result.source,
    )
    verify(predicate="\\n" not in result.source)
    verify(
        predicate=dump(node=parse(source=source), include_attributes=False)
        == dump(node=parse(source=result.source), include_attributes=False),
    )
    path.write_text(data=result.source, encoding="utf-8")
    verify(
        predicate=not transform_strings(
            file=path,
            write=False,
            options=TransformOptions(
                line_length=LiteralOptions().line_length,
                format_interpolations=False,
            ),
        ).changed,
    )


def test_old_dedent_pass_ignores_fstring_interpolations(
    tmp_path: Path,
) -> None:
    """Never select AST fragments located inside a formatted field.

    Args:
        tmp_path: Temporary source directory.

    """
    source: str = dedent(
        text=Constants.lf.join(
            (
                "    def f(name: str) -> str:",
                '        return f"{name.removesuffix(\'.zip\')}\\n" "\\n"',
                "    ",
            ),
        ),
    )
    path: Path = tmp_path / "nested.py"
    path.write_text(data=source, encoding="utf-8")
    result: TransformResult = transform_strings(
        file=path,
        write=False,
        options=TransformOptions(
            line_length=LiteralOptions().line_length,
            format_interpolations=False,
        ),
    )
    verify(
        predicate=dump(node=parse(source=source), include_attributes=False)
        == dump(node=parse(source=result.source), include_attributes=False),
    )


def test_randomized_fstring_fragments() -> None:
    """Differentially verify varied f-string contents across 300 cases."""
    characters: str = "abc  {}\"'\\\r\t\x00✨😀"
    for sample in range(300):
        literal: str = "".join(
            characters[
                (sample * 131 + index * 137 + index**2) % len(characters)
            ]
            for index in range(sample * 71 % 130)
        )
        source: str = (
            "value = ({prefix} {literal} {suffix})" + Constants.lf
        ).format(
            prefix='f"{name!r}"',
            literal=repr(literal + Constants.lf.join(("", "", ""))),
            suffix='f"{count:>{width}}\\n"',
        )
        result: embedded_strings.LiteralRewrite = rewrite_multiline_literals(
            source=source,
        )
        verify(predicate=result.count == 1)
        verify(
            predicate=dump(node=parse(source=source), include_attributes=False)
            == dump(
                node=parse(source=result.source),
                include_attributes=False,
            ),
        )
        verify(
            predicate=rewrite_multiline_literals(source=result.source).source
            == result.source,
        )


def test_embedded_formatter_explicitly_changes_value() -> None:
    """Require consent before changing embedded HTML source strings."""
    source: str = 'html_source = "<h1>hello</h1>"' + Constants.lf
    with pytest.raises(
        expected_exception=ValueError,
        match="allow_value_changes",
    ):
        rewrite_multiline_literals(
            source=source,
            options=LiteralOptions(format_embedded=True),
        )

    def formatter(*, source: str, language: str, line_length: int) -> str:
        """Format a toy HTML document without running a formatter process.

        Args:
            source: Original document.
            language: Language selected from binding context.
            line_length: Formatter width.

        Returns:
            Formatted test content.

        """
        verify(predicate=language == "html")
        verify(predicate=line_length == LiteralOptions().line_length)
        return source.replace(
            "<h1>",
            Constants.lf.join(("<h1>", "  ")),
        ).replace("</h1>", Constants.lf.join(("", "</h1>")))

    result: embedded_strings.LiteralRewrite = rewrite_multiline_literals(
        source=source,
        options=LiteralOptions(format_embedded=True, allow_value_changes=True),
        formatter=formatter,
    )
    verify(predicate=result.changed_values)
    verify(predicate=result.count == 1)
    verify(predicate="hello" in result.source)


def test_external_formatter_error_is_reported() -> None:
    """Reject unavailable or invalid embedded formatters safely."""
    source: str = 'css_source = "p{color:red}"' + Constants.lf

    def failing_formatter(
        *,
        source: str,
        language: str,
        line_length: int,
    ) -> str:
        """Simulate failed formatting.

        Args:
            source: Unformatted CSS.
            language: Detected language.
            line_length: Formatting width.

        Returns:
            Formatted source (never reached; always raises).

        Raises:
            RuntimeError: Always, for this test.

        """
        verify(
            predicate=source != "" and language == "css" and (line_length > 0),
        )
        msg: str = "formatter failed"
        raise RuntimeError(msg)

    options: LiteralOptions = LiteralOptions(
        format_embedded=True,
        allow_value_changes=True,
    )
    result: embedded_strings.LiteralRewrite = rewrite_multiline_literals(
        source=source,
        options=options,
        formatter=failing_formatter,
    )
    verify(predicate=result.source == source)
    verify(predicate=len(result.issues) == 1)
    with pytest.raises(expected_exception=RuntimeError, match="Unrenderable"):
        rewrite_multiline_literals(
            source=source,
            options=LiteralOptions(
                format_embedded=True,
                allow_value_changes=True,
                strict=True,
            ),
            formatter=failing_formatter,
        )


def test_width_rejected_without_mutation() -> None:
    """Skip literal when opening expression leaves no room for quotes."""
    source: str = 'value = "x\\n"' + Constants.lf
    with pytest.raises(expected_exception=ValueError, match="line_length"):
        rewrite_multiline_literals(
            source=source,
            options=LiteralOptions(line_length=1),
        )
    verify(predicate=rewrite_multiline_literals(source=source).count == 1)


def test_randomized_losslessness() -> None:
    """Fuzz escape boundaries and enforce idempotence on sampled inputs."""
    alphabet: str = (
        ascii_letters
        + digits
        + Constants.lf.join((" \\\"'", "\r\t\x00.,;()[]{}"))
        + "😀€"
    )
    for index in range(550):
        digest: bytes = b"".join(
            sha256(
                data=index.to_bytes(length=4, byteorder="big")
                + block.to_bytes(length=2, byteorder="big"),
            ).digest()
            for block in range(9)
        )
        length: int = 2 + digest[0] % 218
        value: str = "".join(
            alphabet[byte % len(alphabet)] for byte in digest[1 : length + 1]
        )
        source: str = f"""\
script: str = ({value[: len(value) // 2]!r} {value[len(value) // 2 :]!r})
"""
        width: int = 32 + digest[240] % 68
        result: embedded_strings.LiteralRewrite = rewrite_multiline_literals(
            source=source,
            options=LiteralOptions(line_length=width),
        )
        verify(
            predicate=dump(node=parse(source=source), include_attributes=False)
            == dump(
                node=parse(source=result.source),
                include_attributes=False,
            ),
        )
        verify(
            predicate=rewrite_multiline_literals(
                source=result.source,
                options=LiteralOptions(line_length=width),
            ).source
            == result.source,
        )


def test_unknown_or_malformed_formatter_inputs() -> None:
    """Reject oversized formatter payloads before invoking child processes."""
    with pytest.raises(expected_exception=ValueError, match="limit"):
        format_embedded_source(
            source="x" * 1000001,
            language="python",
            line_length=79,
        )


def test_original_ast_literal_values() -> None:
    """Verify exact decoded byte-sensitive values, not just pretty syntax."""
    original: str = 'data: str = ("ab\\t\\r\\x00\\\\\\n" "def")' + Constants.lf
    result: embedded_strings.LiteralRewrite = rewrite_multiline_literals(
        source=original,
    )
    original_values: list[str] = [
        node.value
        for node in walk(node=parse(source=original))
        if isinstance(node, Constant) and isinstance(node.value, str)
    ]
    final_values: list[str] = [
        node.value
        for node in walk(node=parse(source=result.source))
        if isinstance(node, Constant) and isinstance(node.value, str)
    ]
    verify(predicate=original_values == final_values)


def test_subprocess_adapter_success_and_errors() -> None:
    """Verify shell-free process behavior and nonzero exit detection."""
    result: CompletedProcess[str] = run_checked_command(
        args=(executable, "-c", "print('ready')"),
        check=True,
    )
    verify(predicate=result.returncode == 0)
    verify(predicate=result.stdout == "ready" + Constants.lf)
    with pytest.raises(expected_exception=CalledProcessError):
        run_checked_command(
            args=(executable, "-c", "raise SystemExit(5)"),
            check=True,
        )
    result = run_checked_command(
        args=(executable, "-c", "raise SystemExit(5)"),
        check=False,
    )
    verify(predicate=result.returncode != 0)
    with pytest.raises(expected_exception=ValueError, match="command"):
        run_checked_command(args=())
    with pytest.raises(expected_exception=ValueError, match="timeout"):
        run_checked_command(args=(executable,), timeout=0)


def test_subprocess_adapter_timeout() -> None:
    """Kill and reap a child that exceeds its strict execution deadline."""
    with pytest.raises(expected_exception=RuntimeError, match="deadline"):
        run_checked_command(
            args=(executable, "-c", "import time; time.sleep(2)"),
            timeout=0.05,
        )


def test_missing_embedded_formatter_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Report missing formatter executables without mutating input.

    Args:
        monkeypatch: Fixture used to replace executable lookup.

    """

    def unavailable(*, cmd: str) -> None:
        """Simulate missing executables.

        Args:
            cmd: Name of the desired tool.

        """
        verify(predicate=cmd in ("ruff", "prettier"))

    monkeypatch.setattr(
        target=embedded_strings,
        name="which",
        value=unavailable,
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="Missing formatter",
    ):
        format_embedded_source(
            source="const x=1",
            language="javascript",
            line_length=79,
        )


def test_embedded_formatter_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dispatch explicitly permitted languages to safe process arguments.

    Args:
        monkeypatch: Fixture used to replace lookup and runner.

    """

    def available(*, cmd: str) -> str:
        """Pretend all formatters are preinstalled.

        Args:
            cmd: Tool name.

        Returns:
            A known executable for the command runner.

        """
        verify(predicate=cmd in ("ruff", "prettier"))
        return executable

    def execute(
        *,
        args: list[str],
        input_text: str | None = None,
        timeout: float = 30,
        check: bool = False,
    ) -> CompletedProcess[str]:
        """Return deterministic output without starting a subprocess.

        Args:
            args: Formatter executable and arguments.
            input_text: Source written to formatter stdin.
            timeout: Process deadline.
            check: Whether exit code matters.

        Returns:
            Successful completed process.

        """
        assert_input: bool = (
            args[0] == executable
            and ("--parser" in args or "--stdin-filename" in args)
            and (input_text is not None)
            and (timeout > 0)
            and check
        )
        verify(predicate=assert_input)
        return CompletedProcess[str](
            args=args,
            returncode=0,
            stdout="formatted" + Constants.lf,
            stderr="",
        )

    monkeypatch.setattr(target=embedded_strings, name="which", value=available)
    monkeypatch.setattr(
        target=embedded_strings,
        name="run_checked_command",
        value=execute,
    )
    for language in ("python", "javascript", "html", "css"):
        verify(
            predicate=format_embedded_source(
                source="    hello",
                language=language,
                line_length=79,
            )
            == "formatted" + Constants.lf,
        )


def test_atomic_write_rejects_concurrent_edits(tmp_path: Path) -> None:
    """Avoid overwriting a modified source snapshot or symbolic link.

    Args:
        tmp_path: Isolated directory for the target file.

    """
    file: Path = tmp_path / "source.py"
    file.write_bytes(data=b"first")
    with pytest.raises(
        expected_exception=RuntimeError,
        match="Concurrent modification",
    ):
        atomic_write(path=file, content=b"second", expected=b"stale")
    verify(predicate=file.read_bytes() == b"first")
    atomic_write(path=file, content=b"second", expected=b"first")
    verify(predicate=file.read_bytes() == b"second")
    link: Path = tmp_path / "link.py"
    link.symlink_to(target=file)
    with pytest.raises(expected_exception=RuntimeError, match="symbolic link"):
        atomic_write(path=link, content=b"different")
    verify(predicate=file.read_bytes() == b"second")


@pytest.mark.parametrize(
    ("filename", "language"),
    [
        ("page.html", "html"),
        ("page.htm", "html"),
        ("script.js", "javascript"),
        ("server.mjs", "javascript"),
        ("server.cjs", "javascript"),
        ("style.css", "css"),
        ("sample.py", "python"),
    ],
)
def test_static_write_text_detects_language(
    filename: str,
    language: EmbeddedLanguage,
) -> None:
    """Use a literal Path suffix to choose the embedded formatter.

    Args:
        filename: File name whose suffix selects a language.
        language: Expected language for the file name.

    """
    original: str = f"""\
Path("{filename}").write_text(data=("  hello\\n" "  world\\n"))
"""

    def formatter(
        *,
        source: str,
        language: EmbeddedLanguage,
        line_length: int,
    ) -> str:
        """Return deterministic replacement text for the injected language.

        Args:
            source: Incoming value passed to the formatter.
            language: Detected language to format.
            line_length: Configured maximum width.

        Returns:
            Known formatted code.

        """
        verify(predicate="hello" in source)
        verify(predicate=line_length == LiteralOptions().line_length)
        return f"""\
formatted {language}
"""

    result: embedded_strings.LiteralRewrite = rewrite_multiline_literals(
        source=original,
        options=LiteralOptions(format_embedded=True, allow_value_changes=True),
        formatter=formatter,
    )
    verify(predicate=result.changed_values)
    verify(predicate=f"formatted {language}" in result.source)


def test_transform_dry_run_write_and_idempotent(tmp_path: Path) -> None:
    """Exercise dry-run auditing, apply, and idempotent re-runs.

    Args:
        tmp_path: Isolated directory for the rewritten file.

    """
    target: Path = tmp_path / "example.py"
    original: str = dedent(
        text=Constants.lf.join(
            (
                "    from textwrap import dedent",
                "    base_imports: str = dedent(text=(",
                '        "    import something\\n    "',
                '        "import more\\n    "',
                "    ))",
                "    ",
            ),
        ),
    )
    target.write_text(data=original, encoding="utf-8")
    audited: TransformResult = transform_strings(
        file=target,
        write=True,
        dry_run=True,
        options=TransformOptions(line_length=79),
    )
    verify(predicate=audited.changed)
    verify(predicate=target.read_text(encoding="utf-8") == original)
    applied: TransformResult = transform_strings(
        file=target,
        write=True,
        options=TransformOptions(line_length=79),
    )
    verify(predicate=applied.changed)
    verify(predicate='"""' in target.read_text(encoding="utf-8"))
    second: TransformResult = transform_strings(
        file=target,
        write=True,
        options=TransformOptions(line_length=79),
    )
    verify(predicate=not second.changed)


def test_transform_error_paths(tmp_path: Path) -> None:
    """Reject invalid options, paths, and source.

    Args:
        tmp_path: Isolated directory for invalid files.

    """
    invalid: Path = tmp_path / "broken.py"
    invalid.write_text(
        data="not valid python?" + Constants.lf,
        encoding="utf-8",
    )
    with pytest.raises(expected_exception=SyntaxError):
        transform_strings(file=invalid, write=False)
    valid: Path = tmp_path / "valid.py"
    valid.write_text(data="x: int = 1" + Constants.lf, encoding="utf-8")
    with pytest.raises(
        expected_exception=ValueError,
        match="format_embedded requires allow_value_changes",
    ):
        transform_strings(
            file=valid,
            write=False,
            options=TransformOptions(
                format_embedded=True,
                allow_value_changes=False,
            ),
        )
    with pytest.raises(expected_exception=RuntimeError):
        transform_strings(file=tmp_path / "missing.py", write=False)


def test_transform_reuses_supplied_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return the caller's parsed tree untouched when nothing changes.

    Args:
        tmp_path: Isolated directory for the parsed file.
        monkeypatch: Fixture used to count parse calls.

    """
    target: Path = tmp_path / "reuse.py"
    source: str = "x: int = 1" + Constants.lf
    target.write_text(data=source, encoding="utf-8")
    tree: Module = parse(source=source)
    parses: list[str] = []
    real_parse: Callable[..., Module] = parse

    def counted(
        *,
        source: str,
        mode: str = "exec",
        filename: str = "<unknown>",
    ) -> object:
        """Record one parse invocation.

        Args:
            source: Python source forwarded to ``parse``.
            mode: Parse mode forwarded to ``parse``.
            filename: Source filename forwarded to ``parse``.

        Returns:
            The parsed AST node.

        """
        parses.append("parse")
        return real_parse(source=source, mode=mode, filename=filename)

    monkeypatch.setattr(target=embedded_strings, name="parse", value=counted)
    monkeypatch.setattr(target=string_transform, name="parse", value=counted)
    result: TransformResult = transform_strings(
        file=target,
        tree=tree,
        write=False,
        options=TransformOptions(line_length=79),
    )
    verify(predicate=result.tree is tree)
    verify(predicate=not parses)
