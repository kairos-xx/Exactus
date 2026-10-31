# Copyright (c) 2026 João Lopes.
"""Behavioral tests for the JavaScript delimiter simplifier."""

from pathlib import Path
from textwrap import dedent
from typing import Final, final

import pytest

from exactus.tools.common import runtime as runtime_module
from exactus.tools.lints.js_delimiters import (
    DelimiterFinding,
    DelimiterHeal,
    DelimiterInput,
    DelimiterResult,
    ExecutionMetrics,
    FileResult,
    JavaScriptDelimiterSimplifier,
    JavaScriptFiles,
    SourceMetrics,
    TextResult,
    TransformationMetrics,
    scan_delimiters,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        min_multiple_transformations: Grouped module constant.

    """

    min_multiple_transformations: Final[int] = 2


def expect(*, condition: bool, message: str) -> None:
    """Expect.

    Args:
        condition: Condition.
        message: Message.

    """
    if not condition:
        pytest.fail(reason=message)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("const f = (x) => { return x; };", "const f = x => x;"),
        (
            "const f = (x) => { return { value: x }; };",
            "const f = x => ({ value: x });",
        ),
        (
            "const f = async (x) => { return await g(x); };",
            "const f = async x => await g(x);",
        ),
        ("const x = (((value)));", "const x = value;"),
        ("const x = (a * b) + c;", "const x = a * b + c;"),
        ("const x = a + (b * c);", "const x = a + b * c;"),
        ("const x = foo((value));", "const x = foo(value);"),
        ("const x = array[(index)];", "const x = array[index];"),
        ("if ((ready)) { run(); }", "if (ready) run();"),
        ("while ((ready)) { run(); }", "while (ready) run();"),
        ("else { run(); }", "else run();"),
        ("do { run(); } while (ready);", "do run(); while (ready);"),
        ("if (ready) { return; }", "if (ready) return;"),
        ("if (ready) { throw error; }", "if (ready) throw error;"),
        ("const x = (foo.bar);", "const x = foo.bar;"),
        ("return (value);", "return value;"),
        ("throw (error);", "throw error;"),
    ],
)
def test_simplifies_supported_constructs(source: str, expected: str) -> None:
    """Simplify supported constructs and remain idempotent.

    Args:
        source: Source.
        expected: Expected.

    """
    simplifier: JavaScriptDelimiterSimplifier = JavaScriptDelimiterSimplifier(
        validate=False,
    )
    result: TextResult = simplifier.simplify_text(source=source)
    expect(
        condition=result.source == expected,
        message="Unexpected simplification.",
    )
    expect(
        condition=result.transformations.total > 0,
        message="Expected at least one transformation.",
    )
    expect(
        condition=simplifier.simplify_text(source=result.source).source
        == result.source,
        message="Simplification must be idempotent.",
    )


@pytest.mark.parametrize(
    "source",
    [
        "const x = (a + b) * c;",
        "const x = a - (b - c);",
        "const x = a / (b / c);",
        "const x = (obj?.a).b;",
        "const x = (a ?? b) || c;",
        "const x = a ?? (b || c);",
        "if (ready) { const x = 1; }",
        "if (ready) { let x = 1; }",
        "if (ready) { class X {} }",
        "const f = ({x}) => x;",
        "const f = (x = 1) => x;",
        "const f = (...args) => args;",
        "const x = (a ** b) ** c;",
        "const x = a ** (b ** c);",
        "const e = /** @type {Error} */ (err).message;",
        "const s = /** @type {Element} */ (byId(i)).root;",
        "register('bad', /** @type {any} */ (null));",
        "const n = (await ids(page)).length;",
        "const z = (await value)?.id;",
        "const t = (await value)`tpl`;",
        "const l = (typeof v).length;",
        "const d = (-n).toFixed();",
        "const b = (!flag).value;",
        "this.pending.delete(msg.id);",
        "const t = x.typeof(a);",
        "const w = obj.await(task);",
        "if (!(search instanceof HTMLInputElement) || !groups) return;",
        "const u = !(option.value in this.view.cells) || x;",
        "const v = !('disabled' in element) || !element.disabled;",
        "const q = !(a && b);",
        "const r = ~(a | b);",
        "const y = typeof (a + b);",
        "const aw = await (a + b);",
        "const dl = delete (a ? b : c);",
        "return (\n  a !== undefined &&\n  items.every(x => x === null)\n);",
        "throw (\n  new Error('bad')\n);",
        "function* g() { yield (\n  a + b\n); }",
        "if ((found = next())) run(found);",
        "while ((found = next())) run(found);",
        "for (let i = 0; (x = step(i)); i++) use(x);",
        "if (!(found = next())) stop();",
        "target.onmessage = event => listener?.(event.data);",
        "listener?.(a + b);",
    ],
)
def test_preserves_required_delimiters(source: str) -> None:
    """Preserve delimiters required by grammar, precedence, or scope.

    Args:
        source: Source.

    """
    result: TextResult = JavaScriptDelimiterSimplifier(
        validate=False,
    ).simplify_text(source=source)
    expect(
        condition=result.source == source,
        message="Required delimiter removed.",
    )


def test_preserves_object_expression_arrow_inside_call() -> None:
    """Keep object-expression parentheses while simplifying its parameter."""
    source: str = dedent(
        text=(
            "    const values = items.map((index) => ({\n      index,\n      v"
            "alue: null,\n    }));\n    "
        ),
    )
    expected: str = source.replace("(index) =>", "index =>")
    result: TextResult = JavaScriptDelimiterSimplifier(
        validate=False,
    ).simplify_text(source=source)
    expect(
        condition=result.source == expected,
        message="Object arrow changed meaning.",
    )


def test_file_processing_write_backup_and_unchanged(tmp_path: Path) -> None:
    """Support dry runs, writes, backups, and stable unchanged files.

    Args:
        tmp_path: Tmp path.

    """
    path: Path = tmp_path / "a.js"
    _ = path.write_text(
        data="const f = (x) => { return x; };",
        encoding="utf-8",
    )
    simplifier: JavaScriptDelimiterSimplifier = JavaScriptDelimiterSimplifier(
        validate=False,
    )
    checked: FileResult = simplifier.simplify_file(path=path, write=False)
    expect(
        condition=checked.changed,
        message="Dry run should detect a change.",
    )
    expect(
        condition="(x)" in path.read_text(encoding="utf-8"),
        message="Dry run wrote the file.",
    )
    written: FileResult = simplifier.simplify_file(path=path, backup=True)
    expect(
        condition=written.changed and written.written,
        message="Write was not recorded.",
    )
    expect(
        condition=(tmp_path / "a.js.bak").exists(),
        message="Backup was not created.",
    )
    stable: FileResult = simplifier.simplify_file(path=path)
    expect(
        condition=not stable.changed,
        message="Second run should be stable.",
    )


def test_file_discovery_and_exclusions(tmp_path: Path) -> None:
    """Discover supported files respecting default and custom exclusions.

    Args:
        tmp_path: Tmp path.

    """
    for name in ("a.js", "b.mjs", "c.txt"):
        _ = (tmp_path / name).write_text(data="x", encoding="utf-8")
    ignored: Path = tmp_path / "node_modules"
    ignored.mkdir()
    _ = (ignored / "d.js").write_text(data="x", encoding="utf-8")
    generated: Path = tmp_path / "generated"
    generated.mkdir()
    _ = (generated / "e.cjs").write_text(data="x", encoding="utf-8")
    files: tuple[Path, ...] = JavaScriptFiles(
        roots=(tmp_path,),
        excludes=("node_modules", "generated"),
    ).collect()
    expect(
        condition={path.name for path in files} == {"a.js", "b.mjs"},
        message="Discovery returned unexpected files.",
    )
    direct: tuple[Path, ...] = JavaScriptFiles(
        roots=(tmp_path / "a.js",),
        excludes=(),
    ).collect()
    expect(
        condition=direct == ((tmp_path / "a.js").resolve(),),
        message="Direct file discovery failed.",
    )
    missing: tuple[Path, ...] = JavaScriptFiles(
        roots=(tmp_path / "missing",),
        excludes=(),
    ).collect()
    expect(
        condition=not missing,
        message="Missing roots should yield no files.",
    )


def test_rich_metrics_and_execution(tmp_path: Path) -> None:
    """Expose immutable transformation, source, file, and execution metrics.

    Args:
        tmp_path: Tmp path.

    """
    path: Path = tmp_path / "sample.js"
    _ = path.write_text(
        data="const fn = (x) => {\n\n    return { value: x };\n\n};\n",
        encoding="utf-8",
    )
    execution: ExecutionMetrics = JavaScriptDelimiterSimplifier(
        validate=False,
    ).simplify_paths(roots=(tmp_path,), write=True, backup=True)
    file_result: FileResult = execution.files[0]
    expectations: tuple[bool, ...] = (
        execution.files_total == 1,
        execution.files_changed == 1,
        execution.files_written == 1,
        execution.transformations >= Constants.min_multiple_transformations,
        execution.bytes_removed > 0,
        execution.characters_removed > 0,
        execution.lines_removed > 0,
        execution.blank_lines_removed > 0,
        execution.elapsed_seconds >= 0.0,
        bool(execution.transformations_by_kind),
        file_result.backup_path is not None,
        file_result.validation.requested is False,
        file_result.validation.performed is False,
        file_result.validation.passed is None,
        file_result.source_metrics.bytes_removed == execution.bytes_removed,
        file_result.transformations.count(kind="arrow-parameter-parentheses")
        == 1,
        file_result.transformations.parentheses_removed
        >= Constants.min_multiple_transformations,
        file_result.transformations.braces_removed
        >= Constants.min_multiple_transformations,
    )
    expect(
        condition=all(expectations),
        message="Execution metrics are inconsistent.",
    )
    expect(
        condition=file_result.backup_path is not None
        and file_result.backup_path.exists(),
        message="Metrics backup path is invalid.",
    )


def test_source_and_empty_transformation_metrics() -> None:
    """Derive source deltas and empty transformation metadata."""
    source_metrics: SourceMetrics = SourceMetrics.compare(
        before="a\n\n",
        after="a\n",
    )
    transformations: TransformationMetrics = (
        TransformationMetrics.from_replacements(replacements=())
    )
    expect(
        condition=source_metrics.lines_removed == 1
        and source_metrics.blank_lines_removed == 1
        and (source_metrics.bytes_removed == 1)
        and (source_metrics.characters_removed == 1)
        and (transformations.total == 0)
        and (transformations.count(kind="missing") == 0),
        message="Metric derivation failed.",
    )


def test_real_node_validation_when_available(tmp_path: Path) -> None:
    """Validate transformed source with Node when the runtime is available.

    Args:
        tmp_path: Tmp path.

    """
    path: Path = tmp_path / "validated.js"
    _ = path.write_text(
        data="const f = (x) => { return x; };",
        encoding="utf-8",
    )
    result: FileResult = JavaScriptDelimiterSimplifier(
        validate=True,
    ).simplify_file(path=path, write=False)
    if result.validation.available:
        expect(
            condition=result.validation.performed,
            message="Node validation was skipped.",
        )
        expect(
            condition=result.validation.passed is True,
            message="Node validation failed.",
        )


@pytest.mark.parametrize(
    "source",
    [
        "const s = 'a\\'b'; const x = ((value));",
        'const s = "a\\"b"; const x = ((value));',
        "const t = `value ${x}`; const y = ((value));",
        "const r = /a[b\\/]c/gi; const x = ((value));",
        "const r = /unterminated\nconst x = ((value));",
        "// comment\nconst x = ((value));",
        "/* block */ const x = ((value));",
        "const x = (a && b) || c;",
        "const x = (a || b) && c;",
        "const x = (a & b) | c;",
        "const x = (a << b) + c;",
        "const x = (a < b) === c;",
        "const x = (a instanceof B) && c;",
        "const x = (a in b) && c;",
        "const x = (a ? b : c);",
        "const x = (typeof value);",
        "const x = (!value);",
        "const x = (~value);",
        "if (ready) { break; }",
        "if (ready) { continue; }",
        "if (ready) { a(); b(); }",
        "if (ready) { /* keep */ run(); }",
        "if (ready) { function f() {} }",
        "if (ready) { async function f() {} }",
        "if (ready) { if (other) run(); } else stop();",
        "const f = (x) => { return\nx; };",
        "const f = (x) => { /* keep */ return x; };",
        "const f = (x) => { return x; extra(); };",
        "const x = ((foo?.bar));",
        "const x = ((foo.bar));",
        "const x = new Foo((value));",
        "const x = foo?.((value));",
    ],
)
def test_public_stability_corpus(source: str) -> None:
    """Exercise lexical and precedence paths through the public API.

    Args:
        source: Source.

    """
    simplifier: JavaScriptDelimiterSimplifier = JavaScriptDelimiterSimplifier(
        validate=False,
    )
    first: TextResult = simplifier.simplify_text(source=source)
    second: TextResult = simplifier.simplify_text(source=first.source)
    expect(
        condition=second.source == first.source,
        message="Corpus case is not stable.",
    )


def test_scan_reports_findings_without_writing(tmp_path: Path) -> None:
    """Without ``fix`` each simplifiable file is a positioned finding.

    Args:
        tmp_path: Tmp path.

    """
    dirty: Path = tmp_path / "dirty.js"
    _ = dirty.write_text(
        data="const f = (x) => { return x; };\n",
        encoding="utf-8",
    )
    clean: Path = tmp_path / "clean.js"
    _ = clean.write_text(data="const f = x => x;\n", encoding="utf-8")
    files: tuple[Path, ...] = (dirty, clean)
    result: DelimiterResult = scan_delimiters(
        inputs=DelimiterInput(root=tmp_path, files=files, fix=False),
    )
    expect(
        condition=result.files == len(files),
        message="Scan did not cover both files.",
    )
    expect(
        condition=len(result.findings) == 1,
        message="Expected exactly one finding.",
    )
    finding: DelimiterFinding = result.findings[0]
    expect(
        condition=finding.rule == "DEL001",
        message="Finding carries the wrong rule.",
    )
    expect(
        condition=finding.file == "dirty.js",
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
        condition="(x)" in dirty.read_text(encoding="utf-8"),
        message="A dry scan rewrote the file.",
    )


def test_scan_heals_files_with_fix(tmp_path: Path) -> None:
    """With ``fix`` files are rewritten, reported as heals, then stable.

    Args:
        tmp_path: Tmp path.

    """
    path: Path = tmp_path / "app.js"
    _ = path.write_text(
        data="const f = (x) => { return x; };\n",
        encoding="utf-8",
    )
    result: DelimiterResult = scan_delimiters(
        inputs=DelimiterInput(root=tmp_path, files=(path,), fix=True),
    )
    expect(
        condition=not result.findings,
        message="A successful heal left findings.",
    )
    expect(
        condition=len(result.healed) == 1,
        message="Expected exactly one heal.",
    )
    heal: DelimiterHeal = result.healed[0]
    expect(
        condition=heal.rule == "DEL001" and heal.action == "simplify",
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
        condition="const f = x => x;" in path.read_text(encoding="utf-8"),
        message="File was not simplified.",
    )
    again: DelimiterResult = scan_delimiters(
        inputs=DelimiterInput(root=tmp_path, files=(path,), fix=True),
    )
    expect(
        condition=not again.healed and (not again.findings),
        message="A healed file did not stabilize.",
    )


def test_scan_reports_unreadable_files(tmp_path: Path) -> None:
    """Non-UTF-8 sources produce ``DEL002`` error findings in both modes.

    Args:
        tmp_path: Tmp path.

    """
    path: Path = tmp_path / "bad.js"
    path.write_bytes(data=b"const f = (x) => x;\xff\xfe")
    for fix in (False, True):
        result: DelimiterResult = scan_delimiters(
            inputs=DelimiterInput(root=tmp_path, files=(path,), fix=fix),
        )
        expect(
            condition=len(result.findings) == 1,
            message="Unreadable file produced no finding.",
        )
        expect(
            condition=result.findings[0].rule == "DEL002",
            message="Unreadable file used the wrong rule.",
        )
        expect(
            condition=result.findings[0].severity == "error",
            message="Unreadable file is not an error.",
        )
        expect(
            condition=not result.healed,
            message="Unreadable file reported a heal.",
        )


def test_embedded_delimiters_progress_stays_in_its_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delimiter completion must not mark the whole lint run complete.

    Args:
        tmp_path: Per-test project directory.
        monkeypatch: Pytest patching helper.

    """
    path: Path = tmp_path / "file.js"
    _ = path.write_text(data="const f = x => x;\n", encoding="utf-8")
    snapshots: list[runtime_module.Progress] = []

    def publish(*, progress: runtime_module.Progress) -> None:
        """Capture delimiter progress.

        Args:
            progress: Published phase snapshot.

        """
        snapshots.append(progress)

    monkeypatch.setattr(
        target=runtime_module,
        name="publish_progress",
        value=publish,
    )
    _ = scan_delimiters(
        inputs=DelimiterInput(root=tmp_path, files=(path,), fix=False),
        progress_span=(0.12, 0.146),
    )
    expect(
        condition=bool(snapshots),
        message="The scan published no progress.",
    )
    expect(
        condition=snapshots[-1].span == (0.12, 0.146),
        message="Delimiter progress escaped its phase slice.",
    )
    expect(
        condition=snapshots[-1].fraction == 1.0,
        message="Delimiter progress did not reach its slice end.",
    )
