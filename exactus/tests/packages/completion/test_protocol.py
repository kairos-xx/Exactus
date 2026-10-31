# Copyright (c) 2026
"""Wire-protocol coverage for ``__complete`` parsing and records."""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

from exactus.packages.completion.catalog import (
    CommandSpec,
    CompletionCatalog,
    OptionSpec,
)
from exactus.packages.completion.engine import CompletionEngine
from exactus.packages.completion.model import (
    CompletionCandidate,
    CompletionKind,
)
from exactus.packages.completion.model import (
    Constants as _GroupFinalConstants_2,
)
from exactus.packages.completion.protocol import (
    Constants,
    ParsedRequest,
    parse_request,
    render_record,
    run_completion,
)
from exactus.packages.completion.protocol import (
    Constants as _GroupFinalConstants,
)
from exactus.packages.completion.protocol import (
    Constants as _GroupFinalConstants_3,
)
from exactus.packages.completion.protocol import (
    Constants as _GroupFinalConstants_4,
)
from exactus.packages.completion.protocol import (
    Constants as _GroupFinalConstants_5,
)
from exactus.packages.completion.protocol import (
    Constants as _GroupFinalConstants_6,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_none,
    expect_true,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _catalog() -> CompletionCatalog:
    """Build a minimal catalog for protocol tests.

    Returns:
        Catalog with one value-taking option.

    """
    return CompletionCatalog(
        root=CommandSpec(
            name="check",
            description="",
            options=(
                OptionSpec(
                    names=("--format",),
                    dest="format",
                    cardinality=_GroupFinalConstants_2.one_value,
                    static_values=("json", "text"),
                ),
            ),
        ),
        contexts=(),
    )


def _request(*, words: tuple[str, ...] = ("check", "")) -> tuple[str, ...]:
    """Build minimal valid protocol arguments.

    Args:
        words: Logical words including the active word.

    Returns:
        ``--name=value`` protocol arguments.

    """
    return (
        f"--protocol-version={_GroupFinalConstants_3.protocol_version}",
        "--shell=bash",
        "--active-word-index=1",
        "--prefix=",
        *(f"--word={word}" for word in words),
    )


def test_parse_valid_request() -> None:
    """A well-formed request parses into a normalized value."""
    parsed: ParsedRequest = parse_request(
        arguments=_request(words=("exactus", "--f")),
    )
    expect_true(condition=parsed.request is not None)
    expect_equal(actual=parsed.status, expected=Constants.exit_ok)
    expect_equal(
        actual=parsed.request.words if parsed.request else (),
        expected=("exactus", "--f"),
    )


def test_parse_rejects_bare_argument() -> None:
    """Arguments must use ``--name=value`` form."""
    parsed: ParsedRequest = parse_request(arguments=("--shell=bash", "oops"))
    expect_none(value=parsed.request)
    expect_equal(actual=parsed.status, expected=Constants.exit_malformed)


def test_parse_rejects_unknown_argument() -> None:
    """Unknown protocol names are malformed."""
    parsed: ParsedRequest = parse_request(arguments=(*_request(), "--bogus=x"))
    expect_equal(actual=parsed.status, expected=Constants.exit_malformed)


def test_parse_rejects_missing_shell() -> None:
    """``--shell`` is required."""
    parsed: ParsedRequest = parse_request(
        arguments=("--active-word-index=0", "--word=check"),
    )
    expect_equal(actual=parsed.status, expected=Constants.exit_malformed)


def test_parse_rejects_unknown_shell() -> None:
    """Unsupported shell names exit ``3``."""
    parsed: ParsedRequest = parse_request(
        arguments=("--shell=tcsh", "--active-word-index=0", "--word=check"),
    )
    expect_equal(
        actual=parsed.status,
        expected=Constants.exit_unsupported_shell,
    )


def test_parse_rejects_protocol_mismatch() -> None:
    """A foreign protocol version yields no candidates."""
    parsed: ParsedRequest = parse_request(
        arguments=(
            "--protocol-version=99",
            "--shell=bash",
            "--active-word-index=0",
            "--word=check",
        ),
    )
    expect_none(value=parsed.request)
    expect_equal(actual=parsed.status, expected=Constants.exit_malformed)


def test_parse_rejects_bad_index() -> None:
    """Non-numeric and out-of-range active indices are malformed."""
    for index in ("x", "-1", "5"):
        parsed: ParsedRequest = parse_request(
            arguments=(
                "--shell=bash",
                f"--active-word-index={index}",
                "--word=check",
            ),
        )
        expect_equal(actual=parsed.status, expected=Constants.exit_malformed)


def test_parse_accepts_empty_and_dash_words() -> None:
    """Empty words and ``-``-leading words survive ``--word=``."""
    parsed: ParsedRequest = parse_request(
        arguments=(
            "--shell=bash",
            "--active-word-index=2",
            "--word=check",
            "--word=--format",
            "--word=",
        ),
    )
    expect_true(condition=parsed.request is not None)
    expect_equal(
        actual=parsed.request.words if parsed.request else (),
        expected=("check", "--format", ""),
    )


def test_parse_enforces_word_limit() -> None:
    """More than ``MAX_WORDS`` words is malformed."""
    parsed: ParsedRequest = parse_request(
        arguments=(
            "--shell=bash",
            "--active-word-index=0",
            *(
                f"--word=w{index}"
                for index in range(_GroupFinalConstants_4.max_words + 1)
            ),
        ),
    )
    expect_equal(actual=parsed.status, expected=Constants.exit_malformed)


def test_parse_enforces_input_limit() -> None:
    """Requests above ``MAX_INPUT`` bytes are malformed."""
    parsed: ParsedRequest = parse_request(
        arguments=(
            "--shell=bash",
            "--active-word-index=1",
            "--word=check",
            f"--word={'x' * _GroupFinalConstants_5.max_input}",
        ),
    )
    expect_equal(actual=parsed.status, expected=Constants.exit_malformed)


def test_render_record_fields() -> None:
    """Records are ``value US display US description US kind US flags``."""
    record: str | None = render_record(
        candidate=CompletionCandidate(
            value="--format",
            display="--format",
            description="Output format",
            kind=CompletionKind.OPTION,
            append_space=True,
        ),
    )
    expect_equal(
        actual=record,
        expected="--format\x1f--format\x1fOutput format\x1foption\x1f1",
    )


def test_render_record_rejects_control_characters() -> None:
    """Fields containing separators or newlines are dropped."""
    for field_value in ("a\x1fb", "a\nb", "a\rb", "a\x00b"):
        expect_none(
            value=render_record(
                candidate=CompletionCandidate(
                    value="v",
                    display="v",
                    description=field_value,
                    kind=CompletionKind.VALUE,
                    append_space=True,
                ),
            ),
        )


def test_render_record_enforces_size_limit() -> None:
    """Records above ``MAX_RECORD`` are dropped."""
    expect_none(
        value=render_record(
            candidate=CompletionCandidate(
                value="v",
                display="v",
                description="x" * _GroupFinalConstants_6.max_record,
                kind=CompletionKind.VALUE,
                append_space=True,
            ),
        ),
    )


def test_run_completion_writes_only_records() -> None:
    """Stdout carries records only, with a ``0`` exit."""
    stream: StringIO = StringIO()
    status: int = run_completion(
        catalog=_catalog(),
        arguments=(
            "--shell=bash",
            "--active-word-index=1",
            "--prefix=--",
            "--word=check",
            "--word=--",
        ),
        out=stream,
    )
    expect_equal(actual=status, expected=Constants.exit_ok)
    lines: tuple[str, ...] = tuple(stream.getvalue().splitlines())
    expect_true(condition=len(lines) > 0, message="expected candidates")
    for line in lines:
        expect_in(member="\x1f", container=line)
        expect_true(
            condition=line.startswith("--"),
            message=f"unexpected record: {line!r}",
        )


def test_run_completion_malformed_writes_nothing() -> None:
    """Rejections emit no stdout records and a non-zero status."""
    stream: StringIO = StringIO()
    status: int = run_completion(
        catalog=_catalog(),
        arguments=("--shell=bogus",),
        out=stream,
    )
    expect_equal(actual=status, expected=Constants.exit_unsupported_shell)
    expect_equal(actual=stream.getvalue(), expected="")


def test_run_completion_engine_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Provider explosions surface as exit ``5`` with empty stdout.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Per-test scratch directory.

    """

    def _explode(**_kwargs: object) -> None:
        """Raise an unexpected engine failure.

        Args:
            _kwargs: Ignored.

        Raises:
            RuntimeError: Always.

        """
        msg: str = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(
        target=CompletionEngine,
        name="complete",
        value=_explode,
    )
    monkeypatch.chdir(path=tmp_path)
    stream: StringIO = StringIO()
    status: int = run_completion(
        catalog=_catalog(),
        arguments=(
            "--shell=bash",
            "--active-word-index=2",
            "--prefix=",
            "--word=check",
            "--word=--config",
            "--word=",
        ),
        out=stream,
    )
    expect_equal(
        actual=status,
        expected=_GroupFinalConstants.exit_engine_failure,
    )
    expect_equal(actual=stream.getvalue(), expected="")


def test_protocol_limits_count_utf8_bytes() -> None:
    """Multibyte requests and records obey byte limits."""
    parsed: ParsedRequest = parse_request(
        arguments=_request(
            words=("exactus", "界" * (_GroupFinalConstants_5.max_input // 3)),
        ),
    )
    expect_equal(actual=parsed.status, expected=Constants.exit_malformed)
    expect_none(
        value=render_record(
            candidate=CompletionCandidate(
                value="v",
                display="v",
                description="界" * (_GroupFinalConstants_6.max_record // 3),
                kind=CompletionKind.VALUE,
                append_space=True,
            ),
        ),
    )


def test_protocol_rejects_invalid_text() -> None:
    """Controls and unpaired surrogates cannot cross the wire."""
    for text in ("a\t", "a\x1f", "a\x7f", "a\ud800"):
        parsed: ParsedRequest = parse_request(
            arguments=_request(words=("exactus", text)),
        )
        expect_equal(actual=parsed.status, expected=Constants.exit_malformed)
        expect_none(
            value=render_record(
                candidate=CompletionCandidate(
                    value=text,
                    display="v",
                    description="",
                    kind=CompletionKind.VALUE,
                    append_space=True,
                ),
            ),
        )
