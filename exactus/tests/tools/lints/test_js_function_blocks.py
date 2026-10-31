# Copyright (c) 2026 João Lopes.
"""Behavioral tests for the Python JavaScript block analyzer API."""

from json import dumps
from pathlib import Path
from subprocess import CompletedProcess
from textwrap import dedent
from unittest.mock import patch

import pytest

from exactus.tools.common import runtime as runtime_module
from exactus.tools.lints.js_function_blocks import (
    ConversionResult,
    FunctionBlock,
    FunctionBlocksFinding,
    FunctionBlocksHeal,
    FunctionBlocksInput,
    FunctionBlocksResult,
    JavaScriptBlockAnalyzer,
    JsonValue,
    scan_function_blocks,
)


def expect(*, condition: bool, message: str) -> None:
    """Expect.

    Args:
        condition: Condition.
        message: Message.

    """
    if not condition:
        pytest.fail(reason=message)


def executable_for(
    command: str,
    /,
    *,
    available: frozenset[str],
) -> str | None:
    """Return an executable for the command.

    Args:
        command: Command.
        available: Available.

    Returns:
        The resulting value.

    """
    return f"/{command}" if command in available else None


def source_file(*, tmp_path: Path, suffix: str = ".js") -> Path:
    """Source file.

    Args:
        tmp_path: Tmp path.
        suffix: Suffix.

    Returns:
        The resulting value.

    """
    path: Path = tmp_path / f"sample{suffix}"
    path.write_text(data="const x = value => value;\n", encoding="utf-8")
    return path


def completed(
    *,
    stdout: str = "",
    stderr: str = "",
    code: int = 0,
) -> CompletedProcess[str]:
    """Completed.

    Args:
        stdout: Stdout.
        stderr: Stderr.
        code: Code.

    Returns:
        The resulting value.

    """
    return CompletedProcess(
        args=["node"],
        returncode=code,
        stdout=stdout,
        stderr=stderr,
    )


def block_payload() -> dict[str, JsonValue]:
    """Block payload.

    Returns:
        The resulting value.

    """
    return {
        "name": "double",
        "kind": "function_declaration",
        "class_name": None,
        "method_kind": None,
        "line_start": 1,
        "column_start": 1,
        "line_end": 1,
        "column_end": 34,
        "static_current": False,
        "static_eligible": False,
        "arrow_current": False,
        "arrow_eligible": True,
        "uses_this_or_super": False,
        "uses_arguments": False,
        "uses_new_target": False,
        "async": False,
        "arrow_blockers": [],
        "recommendation": "use arrow",
        "source": "function double(x) { return x * 2; }",
    }


def test_constructor_validation(*, tmp_path: Path) -> None:
    """Test constructor validation.

    Args:
        tmp_path: Tmp path.

    """
    with pytest.raises(
        expected_exception=FileNotFoundError,
        match="JavaScript file does not exist",
    ):
        JavaScriptBlockAnalyzer(path=tmp_path / "missing.js")
    path: Path = source_file(tmp_path=tmp_path, suffix=".txt")
    with pytest.raises(
        expected_exception=ValueError,
        match="Expected a JavaScript file",
    ):
        JavaScriptBlockAnalyzer(path=path)


def test_analyze_public_contract(*, tmp_path: Path) -> None:
    """Test analyze public contract.

    Args:
        tmp_path: Tmp path.

    """
    analyzer: JavaScriptBlockAnalyzer = JavaScriptBlockAnalyzer(
        path=source_file(tmp_path=tmp_path),
    )
    with (
        patch.object(
            target=analyzer,
            attribute="resolve_espree",
            return_value="espree",
        ),
        patch.object(
            target=analyzer,
            attribute="_run_analyzer",
            return_value=completed(stdout=dumps(obj=[block_payload()])),
        ),
    ):
        blocks: tuple[FunctionBlock, ...] = analyzer.analyze()
    expect(condition=len(blocks) == 1, message="Expected one block.")
    expect(condition=blocks[0].name == "double", message="Wrong block name.")
    expect(
        condition=blocks[0].recommendation == "use arrow",
        message="Wrong recommendation.",
    )


@pytest.mark.parametrize(
    ("result", "error_type", "message"),
    [
        (
            completed(stderr="parse failed", code=1),
            RuntimeError,
            "parse failed",
        ),
        (completed(code=1), RuntimeError, "JavaScript parsing failed"),
        (completed(stdout="{"), ValueError, "invalid JSON"),
        (completed(stdout="{}"), TypeError, "JSON array"),
        (completed(stdout="[1]"), TypeError, "non-object"),
    ],
)
def test_analyze_failures(
    *,
    tmp_path: Path,
    result: CompletedProcess[str],
    error_type: type[Exception],
    message: str,
) -> None:
    """Test analyze failures.

    Args:
        tmp_path: Tmp path.
        result: Result.
        error_type: Error type.
        message: Message.

    """
    analyzer: JavaScriptBlockAnalyzer = JavaScriptBlockAnalyzer(
        path=source_file(tmp_path=tmp_path),
    )
    with (
        patch.object(
            target=analyzer,
            attribute="resolve_espree",
            return_value="espree",
        ),
        patch.object(
            target=analyzer,
            attribute="_run_analyzer",
            return_value=result,
        ),
        pytest.raises(expected_exception=error_type, match=message),
    ):
        analyzer.analyze()


def test_conversion_public_wrappers(*, tmp_path: Path) -> None:
    """Test conversion public wrappers.

    Args:
        tmp_path: Tmp path.

    """
    analyzer: JavaScriptBlockAnalyzer = JavaScriptBlockAnalyzer(
        path=source_file(tmp_path=tmp_path),
    )
    payload: str = dumps(
        obj={
            "source": "const x = x => x;",
            "changed": True,
            "transformations": 1,
        },
    )
    with (
        patch.object(
            target=analyzer,
            attribute="resolve_espree",
            return_value="espree",
        ),
        patch.object(
            target=analyzer,
            attribute="_run_analyzer",
            return_value=completed(stdout=payload),
        ),
    ):
        expect(
            condition=analyzer.to_arrow().transformations == 1,
            message="Expected one to-arrow transformation.",
        )
        expect(
            condition=analyzer.from_arrow().changed,
            message="Expected from-arrow conversion to report a change.",
        )


@pytest.mark.parametrize(
    ("result", "error_type", "message"),
    [
        (
            completed(stderr="conversion failed", code=1),
            RuntimeError,
            "conversion failed",
        ),
        (completed(code=1), RuntimeError, "JavaScript conversion failed"),
        (completed(stdout="{"), ValueError, "invalid JSON"),
        (completed(stdout="[]"), TypeError, "JSON object"),
        (
            completed(
                stdout=dumps(
                    obj={"source": 1, "changed": True, "transformations": 1},
                ),
            ),
            ValueError,
            "string field",
        ),
    ],
)
def test_conversion_failures(
    *,
    tmp_path: Path,
    result: CompletedProcess[str],
    error_type: type[Exception],
    message: str,
) -> None:
    """Test conversion failures.

    Args:
        tmp_path: Tmp path.
        result: Result.
        error_type: Error type.
        message: Message.

    """
    analyzer: JavaScriptBlockAnalyzer = JavaScriptBlockAnalyzer(
        path=source_file(tmp_path=tmp_path),
    )
    with (
        patch.object(
            target=analyzer,
            attribute="resolve_espree",
            return_value="espree",
        ),
        patch.object(
            target=analyzer,
            attribute="_run_analyzer",
            return_value=result,
        ),
        pytest.raises(expected_exception=error_type, match=message),
    ):
        analyzer.convert(direction="to_arrow")


def scenario_file(*, tmp_path: Path, marker: str) -> Path:
    """Scenario file.

    Args:
        tmp_path: Tmp path.
        marker: Marker.

    Returns:
        The resulting value.

    """
    path: Path = tmp_path / "scenario.js"
    contents: dict[str, str] = {
        "SCENARIO_ANALYZE": (
            dedent(
                text=(
                    "    /*SCENARIO_ANALYZE*/\n    function free(x) { retu"
                    "rn x; }\n    class Demo { method(y) { return y; } }\n"
                    "    const arrow = z => z;"
                ),
            )
        ),
        "SCENARIO_TO_ARROW": (
            dedent(
                text=(
                    "    /*SCENARIO_TO_ARROW*/\n    function double(x) { r"
                    "eturn x * 2; }\n    function make(x) { return { value"
                    ": x }; }\n    class Demo { method(a, b) { return a + "
                    "b; } }"
                ),
            )
        ),
        "SCENARIO_FROM_ARROW": (
            dedent(
                text=(
                    "    /*SCENARIO_FROM_ARROW*/\n    const inc = x => x +"
                    " 1;\n    class Demo { static twice = x => x * 2; }"
                ),
            )
        ),
        "SCENARIO_SCRIPT_FALLBACK": "/*SCENARIO_SCRIPT_FALLBACK*/",
        "SCENARIO_PARSE_FAIL": "/*SCENARIO_PARSE_FAIL*/",
    }
    path.write_text(data=contents[marker], encoding="utf-8")
    package: Path = tmp_path / "node_modules" / "espree"
    package.mkdir(parents=True, exist_ok=True)
    (package / "package.json").write_text(
        data='{"name":"espree","main":"index.cjs"}',
        encoding="utf-8",
    )
    (package / "index.cjs").write_text(
        data=(Path(__file__).parent / "js" / "fake_espree.cjs").read_text(
            encoding="utf-8",
        ),
        encoding="utf-8",
    )
    return path


def test_end_to_end_analysis_and_conversion(*, tmp_path: Path) -> None:
    """Test end to end analysis and conversion.

    Args:
        tmp_path: Tmp path.

    """
    source: Path = scenario_file(tmp_path=tmp_path, marker="SCENARIO_ANALYZE")
    analyzer: JavaScriptBlockAnalyzer = JavaScriptBlockAnalyzer(path=source)
    blocks: tuple[FunctionBlock, ...] = analyzer.analyze()
    expect(
        condition=len(blocks) == len(("function", "method", "arrow")),
        message="Expected three analyzed blocks.",
    )
    scenario_file(tmp_path=tmp_path, marker="SCENARIO_TO_ARROW")
    converted: ConversionResult = analyzer.to_arrow()
    expect(condition=converted.changed, message="Expected arrow conversion.")
    expect(
        condition=converted.transformations
        == len(("double", "make", "method")),
        message="Expected three arrow transformations.",
    )


def test_end_to_end_reverse_and_parser_fallback(*, tmp_path: Path) -> None:
    """Test end to end reverse and parser fallback.

    Args:
        tmp_path: Tmp path.

    """
    source: Path = scenario_file(
        tmp_path=tmp_path,
        marker="SCENARIO_FROM_ARROW",
    )
    analyzer: JavaScriptBlockAnalyzer = JavaScriptBlockAnalyzer(path=source)
    reversed_result: ConversionResult = analyzer.from_arrow()
    expect(
        condition=reversed_result.transformations == len(("inc", "twice")),
        message="Expected two reverse transformations.",
    )
    scenario_file(tmp_path=tmp_path, marker="SCENARIO_SCRIPT_FALLBACK")
    expect(
        condition=analyzer.analyze() == (),
        message="Expected empty fallback AST.",
    )


def test_end_to_end_parse_failure(*, tmp_path: Path) -> None:
    """Test end to end parse failure.

    Args:
        tmp_path: Tmp path.

    """
    analyzer: JavaScriptBlockAnalyzer = JavaScriptBlockAnalyzer(
        path=scenario_file(tmp_path=tmp_path, marker="SCENARIO_PARSE_FAIL"),
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match=r"script failure|Unknown fixture scenario",
    ):
        analyzer.analyze()


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("name", 1, "string field"),
        ("class_name", 1, "optional string field"),
        ("line_start", True, "integer field"),
        ("static_current", 1, "boolean field"),
        ("arrow_blockers", ["ok", 2], "string-list field"),
        ("kind", "unknown", "invalid block kind"),
    ],
)
def test_public_block_field_validation(
    *,
    tmp_path: Path,
    key: str,
    value: JsonValue,
    message: str,
) -> None:
    """Test public block field validation.

    Args:
        tmp_path: Tmp path.
        key: Key.
        value: Value.
        message: Message.

    """
    analyzer: JavaScriptBlockAnalyzer = JavaScriptBlockAnalyzer(
        path=source_file(tmp_path=tmp_path),
    )
    payload: dict[str, JsonValue] = block_payload()
    payload[key] = value
    with (
        patch.object(
            target=analyzer,
            attribute="resolve_espree",
            return_value="espree",
        ),
        patch.object(
            target=analyzer,
            attribute="_run_analyzer",
            return_value=completed(stdout=dumps(obj=[payload])),
        ),
        pytest.raises(expected_exception=ValueError, match=message),
    ):
        analyzer.analyze()


def test_public_node_unavailable_for_analyzer(*, tmp_path: Path) -> None:
    """Test public node unavailable for analyzer.

    Args:
        tmp_path: Tmp path.

    """
    analyzer: JavaScriptBlockAnalyzer = JavaScriptBlockAnalyzer(
        path=source_file(tmp_path=tmp_path),
    )
    with (
        patch.object(
            target=analyzer,
            attribute="resolve_espree",
            return_value="espree",
        ),
        patch(
            target="exactus.tools.lints.js_function_blocks.which",
            return_value=None,
        ),
        pytest.raises(
            expected_exception=RuntimeError,
            match=r"Node.js is required",
        ),
    ):
        analyzer.analyze()


def eslint_which(*, cmd: str) -> str | None:
    """Eslint which.

    Args:
        cmd: Cmd.

    Returns:
        The resulting value.

    """
    return f"/{cmd}" if cmd in {"node", "eslint"} else None


def npm_which(*, cmd: str) -> str | None:
    """Npm which.

    Args:
        cmd: Cmd.

    Returns:
        The resulting value.

    """
    return f"/{cmd}" if cmd in {"node", "npm"} else None


def node_which(*, cmd: str) -> str | None:
    """Node which.

    Args:
        cmd: Cmd.

    Returns:
        The resulting value.

    """
    return "/node" if cmd == "node" else None


def test_public_espree_resolution_fallbacks(*, tmp_path: Path) -> None:
    """Test public espree resolution fallbacks.

    Args:
        tmp_path: Tmp path.

    """
    source: Path = source_file(tmp_path=tmp_path)

    def analyzer() -> JavaScriptBlockAnalyzer:
        """Return a fresh analyzer with uncached Espree resolution.

        Returns:
            The resulting value.

        """
        return JavaScriptBlockAnalyzer(path=source)

    subject: JavaScriptBlockAnalyzer = analyzer()
    analyzer_result: CompletedProcess[str] = completed(stdout="[]")
    eslint_results: list[CompletedProcess[str]] = [
        completed(code=1),
        completed(stdout="/eslint/espree.cjs\n"),
    ]
    with (
        patch(
            target="exactus.tools.lints.js_function_blocks.which",
            side_effect=eslint_which,
        ),
        patch.object(
            target=subject,
            attribute="_run_command",
            side_effect=eslint_results,
        ),
        patch.object(
            target=subject,
            attribute="_run_analyzer",
            return_value=analyzer_result,
        ),
    ):
        expect(
            condition=subject.analyze() == (),
            message="ESLint fallback failed.",
        )
    subject = analyzer()
    global_root: Path = tmp_path / "global"
    candidate: Path = global_root / "espree" / "dist" / "espree.cjs"
    candidate.parent.mkdir(parents=True)
    candidate.write_text(data="", encoding="utf-8")
    npm_results: list[CompletedProcess[str]] = [
        completed(code=1),
        completed(stdout=f"{global_root}\n"),
    ]
    with (
        patch(
            target="exactus.tools.lints.js_function_blocks.which",
            side_effect=npm_which,
        ),
        patch.object(
            target=subject,
            attribute="_run_command",
            side_effect=npm_results,
        ),
        patch.object(
            target=subject,
            attribute="_run_analyzer",
            return_value=analyzer_result,
        ),
    ):
        expect(
            condition=subject.analyze() == (),
            message="npm fallback failed.",
        )
    subject = analyzer()
    with (
        patch(
            target="exactus.tools.lints.js_function_blocks.which",
            side_effect=node_which,
        ),
        patch.object(
            target=subject,
            attribute="_run_command",
            return_value=completed(code=1),
        ),
        pytest.raises(
            expected_exception=RuntimeError,
            match="Espree could not be resolved",
        ),
    ):
        subject.analyze()


def test_automatic_normalization_public_api(*, tmp_path: Path) -> None:
    """Test automatic normalization public api.

    Args:
        tmp_path: Tmp path.

    """
    analyzer: JavaScriptBlockAnalyzer = JavaScriptBlockAnalyzer(
        path=source_file(tmp_path=tmp_path),
    )
    payload: str = dumps(
        obj={
            "source": "const x = x => x;",
            "changed": True,
            "transformations": 1,
        },
    )
    with (
        patch.object(
            target=analyzer,
            attribute="resolve_espree",
            return_value="espree",
        ),
        patch.object(
            target=analyzer,
            attribute="_run_analyzer",
            return_value=completed(stdout=payload),
        ) as run_analyzer,
    ):
        implicit: ConversionResult = analyzer.convert()
        explicit: ConversionResult = analyzer.normalize()
    expect(
        condition=implicit == explicit,
        message="convert() and normalize() must share convention behavior.",
    )
    expected_calls: int = 2
    calls: list[object] = list(run_analyzer.call_args_list)
    expect(
        condition=len(calls) == expected_calls,
        message="Expected two conversions.",
    )
    for call in run_analyzer.call_args_list:
        input_data: str = call.kwargs["input_data"]
        expect(
            condition='"direction": "normalize"' in input_data,
            message="Automatic conversion must request normalization.",
        )


def test_scan_reports_findings_without_writing(tmp_path: Path) -> None:
    """Without ``fix`` each modernizable file is a positioned finding.

    Args:
        tmp_path: Tmp path.

    """
    scenario: Path = tmp_path / "scenario.js"
    _ = scenario.write_text(
        data="function double(x) { return x * 2; }\n",
        encoding="utf-8",
    )
    clean: Path = tmp_path / "clean.js"
    _ = clean.write_text(data="const double = x => x * 2;\n", encoding="utf-8")
    files: tuple[Path, ...] = (scenario, clean)
    result: FunctionBlocksResult = scan_function_blocks(
        inputs=FunctionBlocksInput(root=tmp_path, files=files, fix=False),
    )
    expect(
        condition=result.files == len(files),
        message="Scan did not cover both files.",
    )
    expect(
        condition=len(result.findings) == 1,
        message="Expected exactly one finding.",
    )
    finding: FunctionBlocksFinding = result.findings[0]
    expect(
        condition=finding.rule == "JSN001",
        message="Finding carries the wrong rule.",
    )
    expect(
        condition=finding.file == "scenario.js",
        message="Finding names the wrong file.",
    )
    expect(
        condition=finding.severity == "warning",
        message="Finding is not a warning.",
    )
    expect(
        condition=finding.line == 1 and finding.column > 0,
        message="Finding position was not resolved.",
    )
    expect(condition=not result.healed, message="A dry scan reported heals.")
    expect(
        condition="function double" in scenario.read_text(encoding="utf-8"),
        message="A dry scan rewrote the file.",
    )


def test_scan_heals_files_with_fix(tmp_path: Path) -> None:
    """With ``fix`` files are rewritten, reported as heals, then stable.

    Args:
        tmp_path: Tmp path.

    """
    path: Path = tmp_path / "app.js"
    _ = path.write_text(
        data="function double(x) { return x * 2; }\n",
        encoding="utf-8",
    )
    result: FunctionBlocksResult = scan_function_blocks(
        inputs=FunctionBlocksInput(root=tmp_path, files=(path,), fix=True),
    )
    expect(
        condition=not result.findings,
        message="A successful heal left findings.",
    )
    expect(
        condition=len(result.healed) == 1,
        message="Expected exactly one heal.",
    )
    heal: FunctionBlocksHeal = result.healed[0]
    expect(
        condition=heal.rule == "JSN001" and heal.action == "normalize",
        message="Heal metadata is wrong.",
    )
    expect(
        condition=heal.file == "app.js",
        message="Heal names the wrong file.",
    )
    expect(
        condition=heal.transformations > 0,
        message="Heal counted no transformations.",
    )
    expect(
        condition="=> x * 2" in path.read_text(encoding="utf-8"),
        message="File was not modernized.",
    )
    again: FunctionBlocksResult = scan_function_blocks(
        inputs=FunctionBlocksInput(root=tmp_path, files=(path,), fix=True),
    )
    expect(
        condition=not again.healed and (not again.findings),
        message="A healed file did not stabilize.",
    )


def test_embedded_function_blocks_progress_stays_in_its_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Function-block completion must not mark the whole lint run complete.

    Args:
        tmp_path: Per-test project directory.
        monkeypatch: Pytest patching helper.

    """
    path: Path = tmp_path / "file.js"
    _ = path.write_text(data="const f = x => x;\n", encoding="utf-8")
    snapshots: list[runtime_module.Progress] = []

    def publish(*, progress: runtime_module.Progress) -> None:
        """Capture function-block progress.

        Args:
            progress: Published phase snapshot.

        """
        snapshots.append(progress)

    monkeypatch.setattr(
        target=runtime_module,
        name="publish_progress",
        value=publish,
    )
    _ = scan_function_blocks(
        inputs=FunctionBlocksInput(root=tmp_path, files=(path,), fix=False),
        progress_span=(0.12, 0.146),
    )
    if not snapshots:
        pytest.skip(reason="Function-block scan requires espree.")
    expect(
        condition=snapshots[-1].span == (0.12, 0.146),
        message="Function-block progress escaped its phase slice.",
    )
    expect(
        condition=snapshots[-1].fraction == 1.0,
        message="Function-block progress did not reach its slice end.",
    )
