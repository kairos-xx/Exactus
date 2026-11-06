# Copyright (c) 2026
"""Exercise parser failure modes and uncovered merge reconciliation paths."""

from __future__ import annotations

from json import dumps
from subprocess import CompletedProcess, TimeoutExpired
from typing import TYPE_CHECKING

import pytest

from exactus.packages.source_merger import (
    DeltaPolicy,
    MergeResult,
    SourceMerger,
)
from exactus.packages.source_merger import engine as engine_module
from exactus.packages.source_merger import foreign_parser as foreign_module
from exactus.packages.source_merger.foreign_parser import (
    HtmlCollector,
    HtmlParser,
    NodeParser,
)
from exactus.packages.source_merger.model import Language, Snapshot, Unit
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_true,
    private_call,
    require,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def _process(
    *,
    returncode: int = 0,
    stdout: bytes = b"",
    stderr: bytes = b"",
) -> CompletedProcess[bytes]:
    """Fabricate a completed subprocess result.

    Args:
        returncode: Exit status to report.
        stdout: Captured standard output bytes.
        stderr: Captured standard error bytes.

    Returns:
        Completed process record for the Node bridge.

    """
    return CompletedProcess(
        args=["node", "parse_node.cjs"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _stub_run(
    *,
    process: CompletedProcess[bytes] | None = None,
    error: BaseException | None = None,
) -> Callable[..., CompletedProcess[bytes]]:
    """Build a fake ``subprocess.run`` for ``monkeypatch.setattr``.

    Args:
        process: Completed process to return on success.
        error: Failure to raise instead of returning.

    Returns:
        Callable compatible with keyword-style ``run`` invocations.

    """

    def fake(*args: object, **kwargs: object) -> CompletedProcess[bytes]:
        """Simulate a subprocess invocation.

        Args:
            args: Launch command tokens.
            kwargs: Launch keyword arguments.

        Returns:
            The fabricated completed process.

        Raises:
            BaseException: The configured failure, when given.
            ValueError: The stub lacked both result and failure.

        """
        del args, kwargs
        if error is not None:
            raise error
        if process is None:
            msg: str = "stub requires a process or an error"
            raise ValueError(msg)
        return process

    return fake


def _stub(
    *,
    result: object = None,
    error: BaseException | None = None,
) -> Callable[..., object]:
    """Build a fake returning ``result`` or raising ``error``.

    Args:
        result: Value to return on success.
        error: Failure to raise instead of returning.

    Returns:
        Callable compatible with any keyword invocation.

    """

    def fake(*args: object, **kwargs: object) -> object:
        """Simulate a helper invocation.

        Args:
            args: Positional arguments supplied by the caller.
            kwargs: Keyword arguments supplied by the caller.

        Returns:
            The configured result.

        Raises:
            BaseException: The configured failure, when given.

        """
        del args, kwargs
        if error is not None:
            raise error
        return result

    return fake


def reconcile(
    *,
    language: Language,
    original: str,
    user: str,
    tool: str,
    delta_policy: DeltaPolicy | None = None,
) -> MergeResult:
    """Merge three source versions using the public Python API.

    Args:
        language: Parser language.
        original: Common ancestor.
        user: User-edited fork.
        tool: Tool-refactored fork.
        delta_policy: Optional mutation budget policy.

    Returns:
        Merge result with explicit conflict reporting.

    """
    return SourceMerger(
        original=original,
        user_edited=user,
        tool_refactored=tool,
        language=language,
        delta_policy=delta_policy,
    ).merge()


def test_parse_many_empty_returns_nothing() -> None:
    """An empty batch short-circuits without spawning Node."""
    expect_equal(
        actual=NodeParser().parse_many(sources=(), language="css"),
        expected=(),
    )


def test_parse_many_spawn_failure_returns_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing Node runtime degrades every snapshot to invalid.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=foreign_module,
        name="run",
        value=_stub_run(error=OSError("node is not installed")),
    )
    snapshots: tuple[Snapshot, ...] = NodeParser().parse_many(
        sources=(".a { color: red; }",),
        language="css",
    )
    expect_equal(actual=len(snapshots), expected=1)
    expect_false(condition=snapshots[0].valid)
    expect_in(member="Node parser unavailable", container=snapshots[0].error)


def test_parse_many_timeout_returns_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Node timeout degrades every snapshot to invalid.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=foreign_module,
        name="run",
        value=_stub_run(error=TimeoutExpired(cmd="node", timeout=15)),
    )
    snapshots: tuple[Snapshot, ...] = NodeParser().parse_many(
        sources=(".a { color: red; }",),
        language="css",
    )
    expect_false(condition=snapshots[0].valid)
    expect_in(member="Node parser unavailable", container=snapshots[0].error)


def test_parse_many_nonzero_exit_returns_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A crashing Node bridge returns its stderr as the error.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=foreign_module,
        name="run",
        value=_stub_run(
            process=_process(returncode=2, stderr=b"bridge exploded"),
        ),
    )
    snapshots: tuple[Snapshot, ...] = NodeParser().parse_many(
        sources=(".a { color: red; }",),
        language="css",
    )
    expect_false(condition=snapshots[0].valid)
    expect_in(member="bridge exploded", container=snapshots[0].error)


def test_parse_many_bad_json_returns_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unreadable bridge output is a protocol failure, not a crash.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=foreign_module,
        name="run",
        value=_stub_run(process=_process(stdout=b"not json")),
    )
    snapshots: tuple[Snapshot, ...] = NodeParser().parse_many(
        sources=(".a { color: red; }",),
        language="css",
    )
    expect_false(condition=snapshots[0].valid)
    expect_in(member="Invalid parser protocol", container=snapshots[0].error)


def test_parse_many_count_mismatch_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A batch response of the wrong arity is rejected.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=foreign_module,
        name="run",
        value=_stub_run(
            process=_process(
                stdout=dumps(
                    obj=[{"valid": True, "units": [], "statements": []}] * 2,
                ).encode(encoding="utf-8"),
            ),
        ),
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="invalid number of batch responses",
    ):
        NodeParser().parse_many(
            sources=(".a { color: red; }",),
            language="css",
        )


def test_parse_many_invalid_response_returns_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A parser-rejected input surfaces its reported error.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=foreign_module,
        name="run",
        value=_stub_run(
            process=_process(
                stdout=dumps(
                    obj=[{"valid": False, "error": "unclosed rule"}],
                ).encode(encoding="utf-8"),
            ),
        ),
    )
    snapshots: tuple[Snapshot, ...] = NodeParser().parse_many(
        sources=(".a { color: red; }",),
        language="css",
    )
    expect_false(condition=snapshots[0].valid)
    expect_equal(actual=snapshots[0].error, expected="unclosed rule")


def test_parse_many_missing_keys_returns_protocol_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed unit records degrade to protocol failures.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=foreign_module,
        name="run",
        value=_stub_run(
            process=_process(
                stdout=dumps(
                    obj=[
                        {
                            "valid": True,
                            "units": [{"kind": "rule"}],
                            "statements": [],
                        },
                    ],
                ).encode(encoding="utf-8"),
            ),
        ),
    )
    snapshots: tuple[Snapshot, ...] = NodeParser().parse_many(
        sources=(".a { color: red; }",),
        language="css",
    )
    expect_false(condition=snapshots[0].valid)
    expect_in(member="Invalid parser protocol", container=snapshots[0].error)


def test_parse_many_decode_raise_returns_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A decoding failure degrades the whole batch to invalid.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=foreign_module,
        name="run",
        value=_stub_run(
            process=_process(
                stdout=dumps(
                    obj=[{"valid": True, "units": [], "statements": []}],
                ).encode(encoding="utf-8"),
            ),
        ),
    )
    monkeypatch.setattr(
        target=NodeParser,
        name="_decode",
        value=staticmethod(_stub(error=TypeError("bad wire record"))),
    )
    snapshots: tuple[Snapshot, ...] = NodeParser().parse_many(
        sources=(".a { color: red; }",),
        language="css",
    )
    expect_false(condition=snapshots[0].valid)
    expect_in(member="Invalid parser protocol", container=snapshots[0].error)


def test_parse_many_decodes_units_and_statements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Well-formed wire records decode into offset-backed snapshots.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=foreign_module,
        name="run",
        value=_stub_run(
            process=_process(
                stdout=dumps(
                    obj=[
                        {
                            "valid": True,
                            "units": [
                                {
                                    "kind": "rule",
                                    "name": ".a",
                                    "parent": "",
                                    "start": 0,
                                    "end": 18,
                                    "body_start": 5,
                                    "body_end": 17,
                                    "statements": [
                                        {
                                            "kind": "declaration",
                                            "start": 7,
                                            "end": 17,
                                            "shape": "decl",
                                            "exact": "color:red",
                                            "binding": "color",
                                            "annotation": "",
                                            "value_start": 14,
                                            "value_end": "bad",
                                        },
                                    ],
                                    "fingerprint": "fp",
                                    "signature": "rule",
                                    "param_names": [],
                                    "implicit_return": False,
                                    "header_semantic": "{}",
                                },
                            ],
                            "statements": [
                                {
                                    "kind": "declaration",
                                    "start": 7,
                                    "end": 17,
                                    "shape": "decl",
                                    "exact": "color:red",
                                    "binding": "color",
                                    "annotation": "",
                                },
                            ],
                        },
                    ],
                ).encode(encoding="utf-8"),
            ),
        ),
    )
    snapshots: tuple[Snapshot, ...] = NodeParser().parse_many(
        sources=(".a { color: red; }",),
        language="css",
    )
    expect_true(condition=snapshots[0].valid)
    expect_equal(actual=len(snapshots[0].units), expected=1)
    unit: Unit = snapshots[0].units[0]
    expect_equal(actual=unit.name, expected=".a")
    expect_equal(actual=unit.statements[0].value_start, expected=14)
    expect_none(value=unit.statements[0].value_end)


def test_rewrite_identifiers_spawn_failure_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing Node runtime raises a wrapped ValueError.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=foreign_module,
        name="run",
        value=_stub_run(error=OSError("node is not installed")),
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="JavaScript scope parser unavailable",
    ):
        NodeParser.rewrite_identifiers(
            source="x = 1;",
            language="javascript",
            mapping={"x": "y"},
        )


def test_rewrite_identifiers_nonzero_exit_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A crashing bridge surfaces its stderr as the error.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=foreign_module,
        name="run",
        value=_stub_run(
            process=_process(returncode=9, stderr=b"bridge exploded"),
        ),
    )
    with pytest.raises(expected_exception=ValueError, match="bridge exploded"):
        NodeParser.rewrite_identifiers(
            source="x = 1;",
            language="javascript",
            mapping={"x": "y"},
        )


def test_rewrite_identifiers_bad_json_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unreadable bridge output is a protocol failure.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=foreign_module,
        name="run",
        value=_stub_run(process=_process(stdout=b"not json")),
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="Invalid JavaScript rewrite response",
    ):
        NodeParser.rewrite_identifiers(
            source="x = 1;",
            language="javascript",
            mapping={"x": "y"},
        )


def test_rewrite_identifiers_invalid_result_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reported ambiguity surfaces the bridge's error text.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=foreign_module,
        name="run",
        value=_stub_run(
            process=_process(
                stdout=dumps(
                    obj={"valid": False, "error": "binding is ambiguous"},
                ).encode(encoding="utf-8"),
            ),
        ),
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="binding is ambiguous",
    ):
        NodeParser.rewrite_identifiers(
            source="x = 1;",
            language="javascript",
            mapping={"x": "y"},
        )


def test_rewrite_identifiers_missing_text_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid response without rewritten text uses the default error.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=foreign_module,
        name="run",
        value=_stub_run(
            process=_process(
                stdout=dumps(obj={"valid": False}).encode(encoding="utf-8"),
            ),
        ),
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="identifier binding is ambiguous",
    ):
        NodeParser.rewrite_identifiers(
            source="x = 1;",
            language="javascript",
            mapping={"x": "y"},
        )


def test_rewrite_identifiers_returns_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful rewrite returns the bridge's replacement text.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=foreign_module,
        name="run",
        value=_stub_run(
            process=_process(
                stdout=dumps(obj={"valid": True, "text": "y = 1;"}).encode(
                    encoding="utf-8",
                ),
            ),
        ),
    )
    expect_equal(
        actual=NodeParser.rewrite_identifiers(
            source="x = 1;",
            language="javascript",
            mapping={"x": "y"},
        ),
        expected="y = 1;",
    )


def test_html_void_element_with_id_is_a_unit() -> None:
    """Void elements become tracked units only when identified."""
    snapshot: Snapshot = HtmlParser.parse(
        source='<br id="hero"><img src="a.png">',
    )
    expect_true(condition=snapshot.valid)
    expect_equal(actual=len(snapshot.units), expected=1)
    expect_equal(actual=snapshot.units[0].name, expected="hero")


def test_html_self_closing_named_element_is_a_unit() -> None:
    """Self-closing named elements are recorded without nesting."""
    snapshot: Snapshot = HtmlParser.parse(source='<div id="a"/>')
    expect_true(condition=snapshot.valid)
    expect_equal(actual=len(snapshot.units), expected=1)
    expect_equal(actual=snapshot.units[0].name, expected="a")


def test_html_stray_close_tag_is_a_failure() -> None:
    """A closing tag with no opener is reported, not raised."""
    snapshot: Snapshot = HtmlParser.parse(source="</p>")
    expect_false(condition=snapshot.valid)
    expect_in(member="Unexpected closing tag p", container=snapshot.error)


def test_html_unbalanced_close_tag_is_a_failure() -> None:
    """A mismatched closing tag is reported, not raised."""
    snapshot: Snapshot = HtmlParser.parse(source="<div></span>")
    expect_false(condition=snapshot.valid)
    expect_in(member="Unbalanced tag div", container=snapshot.error)


def test_html_unclosed_elements_are_a_failure() -> None:
    """Elements left open at EOF are reported, not raised."""
    snapshot: Snapshot = HtmlParser.parse(source="<div><span>x</span>")
    expect_false(condition=snapshot.valid)
    expect_in(member="Unclosed HTML elements", container=snapshot.error)


def test_html_incomplete_close_tag_is_a_failure() -> None:
    """A closing tag truncated before ``>`` is reported."""
    collector: HtmlCollector = HtmlCollector(source="<div>x")
    collector.feed(data="<div>x")
    collector.handle_endtag(tag="div")
    expect_true(
        condition=any(
            "Incomplete closing tag" in failure
            for failure in collector.failures
        ),
    )


def test_html_nested_duplicate_names_select_outermost() -> None:
    """Identically named nested elements keep only the outermost unit."""
    snapshot: Snapshot = HtmlParser.parse(
        source='<div id="a"><div id="a">x</div></div>',
    )
    expect_true(condition=snapshot.valid)
    expect_equal(actual=len(snapshot.units), expected=1)


def test_git_merge_spawn_failure_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing git binary raises a wrapped RuntimeError.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=engine_module,
        name="run",
        value=_stub_run(error=OSError("git is not installed")),
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="Git diff3 unavailable",
    ):
        private_call(
            owner=engine_module,
            name="_git_merge",
            original="a",
            user="b",
            tool="c",
        )


def test_git_merge_unexpected_status_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A crashed merge-file surfaces its stderr as the error.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=engine_module,
        name="run",
        value=_stub_run(
            process=_process(returncode=3, stderr=b"merge-file exploded"),
        ),
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="merge-file exploded",
    ):
        private_call(
            owner=engine_module,
            name="_git_merge",
            original="a",
            user="b",
            tool="c",
        )


def test_deleted_statement_is_removed_from_tool() -> None:
    """A user deletion removes the statement at its tool-side location."""
    result: MergeResult = reconcile(
        language="python",
        original="""\
def f():
    a = 1
    b = 2
    return a
""",
        user="""\
def f():
    a = 1
    return a
""",
        tool="""\
def f() -> int:
    a = 1
    b = 2
    return a
""",
    )
    expect_true(condition=result.success, message=str(object=result.conflicts))
    source: str = require(value=result.source)
    expect_true(condition="b = 2" not in source)
    expect_in(member="def f() -> int:", container=source)


def test_literal_edit_inside_condition_preserves_tool() -> None:
    """A literal change in a non-assignment statement uses leaf patching."""
    result: MergeResult = reconcile(
        language="python",
        original="""\
def f(x):
    if x > 1:
        return x
""",
        user="""\
def f(x):
    if x > 2:
        return x
""",
        tool="""\
def f(x: int) -> int:
    if x > 1:
        return x
""",
    )
    expect_true(condition=result.success, message=str(object=result.conflicts))
    source: str = require(value=result.source)
    expect_in(member="if x > 2:", container=source)
    expect_in(member="x: int", container=source)


def test_concurrent_skeleton_edits_are_textual_conflict() -> None:
    """Both forks editing untracked module text is a textual conflict."""
    result: MergeResult = reconcile(
        language="python",
        original="""\
x = 1
# note
""",
        user="""\
x = 1
# user
""",
        tool="""\
x = 1
# tool
""",
    )
    expect_false(condition=result.success)
    expect_none(value=result.source)
    expect_true(
        condition=any(
            item.kind == "textual_conflict" for item in result.conflicts
        ),
        message=str(object=result.conflicts),
    )


def test_one_statement_split_into_two_is_replaced() -> None:
    """Replacing one statement with two patches the tool-side anchor."""
    result: MergeResult = reconcile(
        language="python",
        original="""\
def f(x):
    return g(x)
""",
        user="""\
def f(x):
    y = g(x)
    return y
""",
        tool="""\
def f(x: int) -> int:
    return g(x)
""",
    )
    expect_true(condition=result.success, message=str(object=result.conflicts))
    source: str = require(value=result.source)
    expect_in(member="y = g(x)", container=source)
    expect_in(member="return y", container=source)


def test_insert_before_duplicate_statements_needs_anchor() -> None:
    """An insert without a uniquely tracked neighbor is a conflict."""
    result: MergeResult = reconcile(
        language="python",
        original="""\
def f():
    x = 1
    x = 1
""",
        user="""\
def f():
    y = 9
    x = 1
    x = 1
""",
        tool="""\
def f() -> None:
    x = 1
    x = 1
""",
    )
    expect_false(condition=result.success)
    expect_true(
        condition=any(
            item.kind == "missing_anchor" for item in result.conflicts
        ),
        message=str(object=result.conflicts),
    )


def test_many_to_many_block_surgery_is_a_conflict() -> None:
    """Multi-statement asymmetric rewrites require manual reconciliation."""
    result: MergeResult = reconcile(
        language="python",
        original="""\
def f():
    a = 1
    b = 2
    return a
""",
        user="""\
def f():
    x = 7
    y = 8
    z = 9
    return a
""",
        tool="""\
def f() -> int:
    a = 1
    b = 2
    return a
""",
    )
    expect_false(condition=result.success)
    expect_true(
        condition=any(
            item.kind == "unsupported_transformation"
            for item in result.conflicts
        ),
        message=str(object=result.conflicts),
    )


def test_user_annotation_change_is_a_conflict() -> None:
    """User annotation rewrites on tracked assignments are rejected."""
    result: MergeResult = reconcile(
        language="python",
        original="""\
X: int = 1
Y = 0
""",
        user="""\
X: str = 1
Y = 0
""",
        tool="""\
X: int = 1
Y = 1
""",
    )
    expect_false(condition=result.success)
    expect_true(
        condition=any(
            item.kind == "concurrent_change" for item in result.conflicts
        ),
        message=str(object=result.conflicts),
    )


def test_missing_target_value_span_is_a_conflict() -> None:
    """Assignments without a tool-side value span are rejected."""
    result: MergeResult = reconcile(
        language="python",
        original="""\
X = 1
""",
        user="""\
X = 2
""",
        tool="""\
X: int
""",
    )
    expect_false(condition=result.success)
    expect_true(
        condition=any(
            item.kind == "unsupported_transformation"
            for item in result.conflicts
        ),
        message=str(object=result.conflicts),
    )


def test_matching_assignment_value_additions_merge() -> None:
    """Both forks adding the same value is a no-op projection."""
    result: MergeResult = reconcile(
        language="python",
        original="""\
X: int
""",
        user="""\
X: int = 1
""",
        tool="""\
X: int = 1
""",
    )
    expect_true(condition=result.success, message=str(object=result.conflicts))
    expect_in(member="X: int = 1", container=require(value=result.source))


def test_divergent_assignment_value_additions_conflict() -> None:
    """Both forks adding different values is a concurrent change."""
    result: MergeResult = reconcile(
        language="python",
        original="""\
X: int
""",
        user="""\
X: int = 1
""",
        tool="""\
X: int = 2
""",
    )
    expect_false(condition=result.success)
    expect_true(
        condition=any(
            item.kind == "concurrent_change" for item in result.conflicts
        ),
        message=str(object=result.conflicts),
    )


def test_patch_application_failure_is_a_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Overlapping patch failures surface as concurrent-change conflicts.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=engine_module,
        name="apply",
        value=_stub(error=ValueError("overlapping replacements")),
    )
    result: MergeResult = reconcile(
        language="python",
        original="""\
def f():
    return 1
""",
        user="""\
def f():
    return 2
""",
        tool="""\
def f() -> int:
    return 1
""",
    )
    expect_false(condition=result.success)
    expect_true(
        condition=any(
            item.kind == "concurrent_change" and item.scope == "patches"
            for item in result.conflicts
        ),
        message=str(object=result.conflicts),
    )


def test_invalid_patched_source_is_a_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A patched tool fork that no longer parses is rejected.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=engine_module,
        name="apply",
        value=_stub(
            result="""\
def broken(:
""",
        ),
    )
    result: MergeResult = reconcile(
        language="python",
        original="""\
def f():
    return 1
""",
        user="""\
def f():
    return 2
""",
        tool="""\
def f() -> int:
    return 1
""",
    )
    expect_false(condition=result.success)
    expect_true(
        condition=any(
            item.kind == "validation_error" for item in result.conflicts
        ),
        message=str(object=result.conflicts),
    )


def test_inline_body_failure_is_a_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inline-body normalization failures are reported, not raised.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=engine_module,
        name="_prepare_inline_bodies",
        value=_stub(error=ValueError("cannot expand")),
    )
    result: MergeResult = reconcile(
        language="python",
        original="""\
def f():
    return 1
""",
        user="""\
def f():
    return 2
""",
        tool="""\
def f() -> int:
    return 1
""",
    )
    expect_false(condition=result.success)
    expect_true(
        condition=any(
            item.kind == "unsupported_transformation"
            and item.scope == "inline bodies"
            for item in result.conflicts
        ),
        message=str(object=result.conflicts),
    )


def test_invalid_normalized_tool_is_a_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A normalized tool fork that cannot parse is rejected.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=engine_module,
        name="_prepare_inline_bodies",
        value=_stub(
            result=Snapshot(
                source="""\
def broken(:
""",
                units=(),
                statements=(),
                valid=False,
                error="synthetic parse failure",
            ),
        ),
    )
    result: MergeResult = reconcile(
        language="python",
        original="""\
def f():
    return 1
""",
        user="""\
def f():
    return 2
""",
        tool="""\
def f() -> int:
    return 1
""",
    )
    expect_false(condition=result.success)
    expect_true(
        condition=any(
            item.kind == "parse_error" and item.scope == "normalized refactor"
            for item in result.conflicts
        ),
        message=str(object=result.conflicts),
    )


def test_skeleton_merge_failure_is_a_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A crashing textual merge produces a textual-conflict result.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=engine_module,
        name="_git_merge",
        value=_stub(error=RuntimeError("merge-file exploded")),
    )
    result: MergeResult = reconcile(
        language="python",
        original="""\
def f():
    return 1
""",
        user="""\
def f():
    return 2
""",
        tool="""\
def f() -> int:
    return 1
""",
    )
    expect_false(condition=result.success)
    expect_true(
        condition=any(
            item.kind == "textual_conflict" for item in result.conflicts
        ),
        message=str(object=result.conflicts),
    )


def test_element_merge_failure_is_a_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A crashing subtree merge inside an element is a textual conflict.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=engine_module,
        name="_git_merge",
        value=_stub(error=RuntimeError("merge-file exploded")),
    )
    result: MergeResult = reconcile(
        language="html",
        original="""\
<div id="a"><span>One</span></div>
""",
        user="""\
<div id="a"><span>Two</span></div>
""",
        tool="""\
<main><div id="a"><span>One</span></div></main>
""",
    )
    expect_false(condition=result.success)
    expect_true(
        condition=any(
            item.kind == "textual_conflict" for item in result.conflicts
        ),
        message=str(object=result.conflicts),
    )


def test_delta_policy_without_violations_continues() -> None:
    """A configured budget that is respected does not block the merge."""
    result: MergeResult = reconcile(
        language="python",
        original="""\
def f():
    return 1
""",
        user="""\
def f():
    return 2
""",
        tool="""\
def f() -> int:
    return 1
""",
        delta_policy=DeltaPolicy(),
    )
    expect_true(condition=result.success, message=str(object=result.conflicts))
    expect_in(member="return 2", container=require(value=result.source))
