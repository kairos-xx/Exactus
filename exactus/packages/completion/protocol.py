# Copyright (c) 2026
"""Hidden ``__complete`` wire protocol.

The shell adapter invokes ``exactus __complete --shell=<s>
--active-word-index=<n> --prefix=<p> --word=<w>...``; this module
parses that request without ``argparse`` (protocol values themselves
may begin with ``-``) and renders candidates as one Unit-Separated
record per stdout line:

    value<US>display<US>description<US>kind<US>flags

stdout carries candidate records only — never banners, logging, or
usage text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from os import environ
from pathlib import Path
from sys import stderr, stdout
from typing import TYPE_CHECKING, Final, final

from .engine import CompletionEngine
from .model import CompletionCandidate, CompletionRequest, CompletionShell
from .model import Constants as _GroupFinalConstants
from .providers import default_providers

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import TextIO

    from .catalog import CompletionCatalog, ProviderId
    from .providers import CompletionProvider
"Internal request/record protocol version."
"Maximum logical words accepted in one request."
"Maximum total request payload size in bytes (1 MiB)."
"Maximum encoded record length in UTF-8 bytes."
"Environment variable enabling quiet stderr diagnostics."


@final
class Constants:
    """Group module-level constants.

    Attributes:
        exit_ok: Grouped module constant.
        exit_malformed: Grouped module constant.
        exit_unsupported_shell: Grouped module constant.
        exit_catalog_failure: Grouped module constant.
        exit_engine_failure: Grouped module constant.
        rejected: Grouped module constant.
        protocol_version: Grouped module constant.
        max_words: Grouped module constant.
        max_input: Grouped module constant.
        max_record: Grouped module constant.
        debug_variable: Grouped module constant.
        provider_errors: Grouped module constant.

    """

    exit_ok: Final[int] = 0
    exit_malformed: Final[int] = 2
    exit_unsupported_shell: Final[int] = 3
    exit_catalog_failure: Final[int] = 4
    exit_engine_failure: Final[int] = 5
    rejected: Final[frozenset[str]] = frozenset(
        chr(value) for value in (*range(32), *range(127, 160))
    )
    protocol_version: Final[int] = 1
    max_words: Final[int] = 1024
    max_input: Final[int] = 1 << 20
    max_record: Final[int] = 16 * 1024
    debug_variable: Final[str] = "EXACTUS_COMPLETION_DEBUG"
    provider_errors: Final[tuple[type[BaseException], ...]] = (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RuntimeError,
    )


"Reserved for callers that build the catalog lazily."
"Characters that cannot appear inside a protocol field."


@dataclass(frozen=True, slots=True)
class ParsedRequest:
    """Outcome of parsing the hidden request arguments.

    Attributes:
        request: The validated completion request, or ``None``.
        status: Process exit status when ``request`` is ``None``.
        message: Debug-only explanation of a rejection.

    """

    request: CompletionRequest | None
    status: int
    message: str


@dataclass(slots=True)
class _Fields:
    """Raw protocol fields collected from the argument list.

    Attributes:
        shell: ``--shell`` value.
        index: ``--active-word-index`` value.
        prefix: ``--prefix`` value.
        words: Repeated ``--word`` values in order.
        version: ``--protocol-version`` value.
        error: First malformed argument, if any.

    """

    shell: str | None = None
    index: str | None = None
    prefix: str = ""
    words: list[str] = field(default_factory=list)
    version: str | None = None
    error: str | None = None


def _collect(*, arguments: Sequence[str]) -> _Fields:
    """Collect protocol fields from ``--name=value`` arguments.

    Args:
        arguments: Protocol arguments after ``__complete``.

    Returns:
        Collected fields; ``error`` names the first invalid argument.

    """
    fields: _Fields = _Fields()
    for argument in arguments:
        name, separator, value = argument.partition("=")
        if separator != "=" or not name.startswith("--"):
            return _Fields(error=f"malformed protocol argument: {argument!r}")
        if name == "--shell":
            fields.shell = value
        elif name == "--active-word-index":
            fields.index = value
        elif name == "--prefix":
            fields.prefix = value
        elif name == "--word":
            fields.words.append(value)
        elif name == "--protocol-version":
            fields.version = value
        else:
            return _Fields(error=f"unknown protocol argument: {name}")
    return fields


def _reject(*, status: int, message: str) -> ParsedRequest:
    """Build a rejected parse outcome.

    Args:
        status: Exit status for the rejection.
        message: Debug-only explanation.

    Returns:
        A request-less parse outcome.

    """
    return ParsedRequest(request=None, status=status, message=message)


def _active_index(*, fields: _Fields) -> int | None:
    """Validate ``--active-word-index`` against the word list.

    Args:
        fields: Collected protocol fields.

    Returns:
        The index, or ``None`` when invalid.

    """
    try:
        active: int = int(fields.index) if fields.index is not None else 0
    except ValueError:
        return None
    if active < 0 or active >= max(len(fields.words), 1):
        return None
    return active


def _shell_error(*, fields: _Fields) -> ParsedRequest | None:
    """Validate the ``--shell`` field.

    Args:
        fields: Collected protocol fields.

    Returns:
        A rejection when the shell is missing or unsupported.

    """
    if fields.shell is None:
        return _reject(
            status=Constants.exit_malformed,
            message="missing --shell",
        )
    try:
        CompletionShell(fields.shell)
    except ValueError:
        return _reject(
            status=Constants.exit_unsupported_shell,
            message=f"unsupported shell: {fields.shell!r}",
        )
    return None


def _version_error(*, fields: _Fields) -> ParsedRequest | None:
    """Validate ``--protocol-version`` against this build.

    Args:
        fields: Collected protocol fields.

    Returns:
        A rejection when the version is present but incompatible.

    """
    if fields.version is not None and fields.version != str(
        object=Constants.protocol_version,
    ):
        return _reject(
            status=Constants.exit_malformed,
            message=(
                f"unsupported completion protocol version "
                f"{fields.version!r}"
                f"; regenerate the completion script"
            ),
        )
    return None


def _structural_error(
    *,
    arguments: Sequence[str],
    fields: _Fields,
) -> ParsedRequest | None:
    """Validate request shape: size, syntax and word count.

    Args:
        arguments: Raw protocol arguments.
        fields: Collected protocol fields.

    Returns:
        A rejection, or ``None`` when the shape is valid.

    """
    try:
        size: int = sum(
            len(argument.encode(encoding="utf-8")) + 1
            for argument in arguments
        )
    except UnicodeEncodeError:
        return _reject(
            status=Constants.exit_malformed,
            message="request contains invalid UTF-8 text",
        )
    if any(
        character in Constants.rejected
        for argument in arguments
        for character in argument
    ):
        return _reject(
            status=Constants.exit_malformed,
            message="request contains control characters",
        )
    if size > Constants.max_input:
        return _reject(
            status=Constants.exit_malformed,
            message="request exceeds maximum input size",
        )
    if fields.error is not None:
        return _reject(status=Constants.exit_malformed, message=fields.error)
    if len(fields.words) > Constants.max_words:
        return _reject(
            status=Constants.exit_malformed,
            message="request exceeds maximum word count",
        )
    return None


def _semantic_error(
    *,
    fields: _Fields,
    active: int | None,
) -> ParsedRequest | None:
    """Validate request values: version, shell and active index.

    Args:
        fields: Collected protocol fields.
        active: Validated active index, or ``None``.

    Returns:
        A rejection, or ``None`` when the values are valid.

    """
    version: ParsedRequest | None = _version_error(fields=fields)
    if version is not None:
        return version
    shell: ParsedRequest | None = _shell_error(fields=fields)
    if shell is not None:
        return shell
    if active is None:
        return _reject(
            status=Constants.exit_malformed,
            message=f"invalid --active-word-index: {fields.index!r}",
        )
    return None


def parse_request(*, arguments: Sequence[str]) -> ParsedRequest:
    """Parse hidden-protocol arguments into a request.

    Every argument must use ``--name=value`` form; repeated ``--word=``
    preserves empty values and values beginning with ``-``.

    Args:
        arguments: Protocol arguments after ``__complete``.

    Returns:
        The parsed request or a rejection status and message.

    """
    fields: _Fields = _collect(arguments=arguments)
    active: int | None = _active_index(fields=fields)
    rejected: ParsedRequest | None = _structural_error(
        arguments=arguments,
        fields=fields,
    ) or _semantic_error(fields=fields, active=active)
    if rejected is not None:
        return rejected
    return ParsedRequest(
        request=CompletionRequest(
            shell=CompletionShell(fields.shell or ""),
            words=tuple(fields.words),
            active_word_index=0 if active is None else active,
            prefix=fields.prefix,
            protocol_version=Constants.protocol_version
            if fields.version is None
            else int(fields.version),
        ),
        status=Constants.exit_ok,
        message="",
    )


def render_record(*, candidate: CompletionCandidate) -> str | None:
    """Encode one candidate as a wire-protocol line.

    Args:
        candidate: Candidate to encode.

    Returns:
        The ``value<US>display<US>description<US>kind<US>flags`` record,
        or ``None`` when a field cannot be represented by the line
        protocol or the record would exceed ``MAX_RECORD``.

    """
    fields: tuple[str, ...] = (
        candidate.value,
        candidate.display,
        candidate.description,
        candidate.kind.value,
    )
    if any(
        rejected in field
        for field in fields
        for rejected in Constants.rejected
    ):
        return None
    record: str = (
        _GroupFinalConstants.field_separator.join(fields)
        + _GroupFinalConstants.field_separator
        + str(object=candidate.flags)
    )
    try:
        size: int = len(record.encode(encoding="utf-8"))
    except UnicodeEncodeError:
        return None
    return record if size <= Constants.max_record else None


def _debug(*, message: str, command_name: str = "exactus") -> None:
    """Write one diagnostic line when debug mode is enabled.

    Args:
        message: Diagnostic text; never written to stdout.
        command_name: Command name prefixed to the diagnostic.

    """
    if environ.get(Constants.debug_variable) in ("1", "true", "yes"):
        _ = stderr.write(f"{command_name} __complete: {message}\n")


def run_completion(
    *,
    arguments: Sequence[str],
    catalog: CompletionCatalog,
    providers: dict[ProviderId, CompletionProvider] | None = None,
    out: TextIO | None = None,
    command_name: str = "exactus",
) -> int:
    """Run the hidden completion endpoint.

    Args:
        arguments: Protocol arguments after ``__complete``.
        catalog: Grammar catalog supplied by the dispatcher.
        providers: Dynamic providers; ``default_providers()`` when
            ``None``.
        out: Candidate output stream; ``sys.stdout`` when ``None``.
        command_name: Command name stripped and used in diagnostics.

    Returns:
        ``0`` on success including "no candidates"; ``2`` malformed
        request; ``3`` unsupported shell; ``5`` engine failure.

    """
    stream: TextIO = stdout if out is None else out
    parsed: ParsedRequest = parse_request(arguments=arguments)
    if parsed.request is None:
        _debug(message=parsed.message, command_name=command_name)
        return parsed.status
    request: CompletionRequest = parsed.request
    engine: CompletionEngine = CompletionEngine(
        catalog=catalog,
        providers=default_providers() if providers is None else providers,
        working_directory=Path.cwd(),
        command_name=command_name,
    )
    try:
        candidates: tuple[CompletionCandidate, ...] = engine.complete(
            request=request,
        )
    except Constants.provider_errors as error:
        _debug(
            message=f"completion engine failed: {error}",
            command_name=command_name,
        )
        return Constants.exit_engine_failure
    written: int = 0
    for candidate in candidates:
        record: str | None = render_record(candidate=candidate)
        if record is None:
            _debug(
                message=f"unrepresentable candidate: {candidate.value!r}",
                command_name=command_name,
            )
            continue
        _ = stream.write(f"{record}\n")
        written += 1
    _debug(
        message=f"{written} candidate(s) for {request.prefix!r}",
        command_name=command_name,
    )
    return Constants.exit_ok


"Unexpected engine failure modes reported as exit ``5``."
