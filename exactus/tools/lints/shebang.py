# Copyright (c) 2026
"""Exactus Python executable permissions against shebang presence.

Python files starting with a ``#!`` shebang are entry points meant to
run directly, so they must carry executable bits; every other Python
file must not.  The exactus reports both directions, mirroring Ruff's
``EXE001`` and ``EXE002`` rules, and can heal the mismatches: add the
missing executable bit, insert a shebang, strip a shebang, or drop the
executable bits, according to the configured policies.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from re import Pattern
from re import compile as compile_pattern
from stat import S_IRGRP, S_IROTH, S_IRUSR, S_IXGRP, S_IXOTH, S_IXUSR
from typing import TYPE_CHECKING, Final, Literal, cast

from exactus.packages.steps import trace
from exactus.tools.common.cli import (
    ExactusCommonTables,
    is_reports_tree,
    match_path,
)
from exactus.tools.common.runtime import Progress, publish_progress

if TYPE_CHECKING:
    from io import BufferedReader
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue
type ExecWithoutShebang = Literal["add-shebang", "drop-exec"]
"""Heal policy for executable files lacking a shebang."""
type ShebangWithoutExec = Literal["add-exec", "drop-shebang"]
"""Heal policy for shebang files lacking the executable bit."""


class Constants:
    """Executable-permission exactus constants.

    Attributes:
        executable_bits: User, group, and other execute permission bits.
        readable_bits: Read permission bits mirrored by ``chmod +x``.
        skipped_dirs: Directory names excluded from repository
            traversal.
        duplicate_copy: Pattern matching duplicate-copy filename
            suffixes.
        excluded_reason: Reason recorded for glob-filtered files.
        symlink_reason: Reason recorded for symbolic links.
        shebang_limit: Most bytes read from the first line of a file.
        env_program: Name of the ``env`` launcher.
        env_value_options: ``env`` options that consume the next word.
        env_split_option: ``env`` option holding a command string.
        unknown_interpreter: Label of a shebang naming no program.
        no_extension: Label of files without a suffix.
        shebangs: Shebang line inserted for each known suffix.

    """

    executable_bits: Final[int] = S_IXUSR | S_IXGRP | S_IXOTH
    readable_bits: Final[int] = S_IRUSR | S_IRGRP | S_IROTH
    skipped_dirs: Final[frozenset[str]] = (
        ExactusCommonTables.DEFAULT_EXCLUDED_DIRS | frozenset({"bundle"})
    )
    duplicate_copy: Final[Pattern[str]] = compile_pattern(
        pattern=r" \d+(?:\.[^.]+)?$",
    )
    excluded_reason: Final[str] = "excluded by include/exclude rules"
    symlink_reason: Final[str] = "symbolic link"
    shebang_limit: Final[int] = 512
    env_program: Final[str] = "env"
    env_value_options: Final[frozenset[str]] = frozenset(
        {"-u", "--unset", "-C", "--chdir"},
    )
    env_split_option: Final[str] = "-S"
    unknown_interpreter: Final[str] = "unknown"
    no_extension: Final[str] = "(none)"
    shebangs: Final[dict[str, str]] = {
        ".py": "#!/usr/bin/env python3",
        ".sh": "#!/bin/sh",
        ".bash": "#!/usr/bin/env bash",
        ".zsh": "#!/usr/bin/env zsh",
        ".js": "#!/usr/bin/env node",
        ".pl": "#!/usr/bin/env perl",
        ".rb": "#!/usr/bin/env ruby",
    }


@dataclass(frozen=True, slots=True)
class ShebangSettings:
    """Auto-heal toggle and the two mismatch heal policies.

    Attributes:
        heal: Repair permission/shebang mismatches instead of only
            reporting them.
        exec_no_shebang: Action for an executable file without a
            shebang: ``add-shebang`` inserts the interpreter line for
            its suffix, ``drop-exec`` clears its executable bits.
        shebang_no_exec: Action for a shebang file without the
            executable bit: ``add-exec`` marks it executable,
            ``drop-shebang`` removes the shebang line.

    """

    heal: bool = False
    exec_no_shebang: ExecWithoutShebang = "add-shebang"
    shebang_no_exec: ShebangWithoutExec = "add-exec"


@dataclass(frozen=True, slots=True)
class ShebangFinding:
    """One executable-permission violation located in a scanned file.

    Attributes:
        rule: Stable rule identifier (``EXE001``-``EXE003``).
        file: Root-relative file path.
        line: ``1`` for permission findings, ``0`` when inspection
            failed.
        message: Human-readable violation description.
        severity: ``error`` for every enforced requirement.

    """

    rule: str
    file: str
    line: int
    message: str
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class ShebangHeal:
    """One permission/shebang repair applied to a scanned file.

    Attributes:
        rule: Rule whose violation was repaired (``EXE001`` or
            ``EXE002``).
        file: Root-relative file path.
        action: Repair applied: ``add-exec``, ``add-shebang``,
            ``drop-exec`` or ``drop-shebang``.

    """

    rule: str
    file: str
    action: str


@dataclass(frozen=True, slots=True)
class ShebangInput:
    """Carry the inputs of one executable-permission exactus run.

    Attributes:
        root: Project root directory.
        includes: Include globs narrowing scanned files.
        excludes: Exclude globs narrowing scanned files.
        settings: Auto-heal toggle and mismatch policies.
        source_files: Pre-discovered Python sources. When supplied, repository
            discovery is skipped.

    """

    root: Path
    includes: tuple[str, ...]
    excludes: tuple[str, ...]
    settings: ShebangSettings = field(default_factory=ShebangSettings)
    source_files: tuple[Path, ...] | None = None


@dataclass(frozen=True, slots=True)
class ShebangSkip:
    """One Python file found under the root but not audited.

    Attributes:
        target: Root-relative file path.
        reason: Why the file was not audited.

    """

    target: str
    reason: str


@dataclass(frozen=True, slots=True)
class FileFacts:
    """What one inspection learned about a scanned file.

    Attributes:
        file: Root-relative file path.
        extension: Lower-case suffix, or the no-extension label.
        executable: Whether any execute bit is set.
        interpreter: Normalized shebang interpreter, ``None`` without a
            shebang.
        error: Why the file could not be inspected, else ``None``.

    """

    file: str
    extension: str
    executable: bool = False
    interpreter: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ShebangMetrics:
    """Counters gathered from the files the exactus walked.

    Attributes:
        files_scanned: Files inspected (readable or not).
        executable_files: Inspected files with an execute bit.
        files_with_shebang: Inspected files starting with ``#!``.
        interpreters: Interpreter and file count, most used first.
        executable_without_shebang: Executable files lacking a shebang.
        shebang_without_executable: Shebang files lacking execute bits.
        extensions: File extension and count, most used first.

    """

    files_scanned: int = 0
    executable_files: int = 0
    files_with_shebang: int = 0
    interpreters: tuple[tuple[str, int], ...] = ()
    executable_without_shebang: tuple[str, ...] = ()
    shebang_without_executable: tuple[str, ...] = ()
    extensions: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class ShebangResult:
    """Outcome of one executable-permission exactus run.

    Attributes:
        files: Number of Python source files scanned.
        findings: Violations in deterministic order.
        healed: Repairs applied during the run, in scan order.
        includes: Include globs the run applied.
        excludes: Exclude globs the run applied.
        skipped: Files found but not audited, with reasons.
        metrics: Executable and shebang counters of the scanned files.

    """

    files: int
    findings: tuple[ShebangFinding, ...]
    healed: tuple[ShebangHeal, ...] = ()
    includes: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()
    skipped: tuple[ShebangSkip, ...] = ()
    metrics: ShebangMetrics = field(default_factory=ShebangMetrics)


def skipped(*, name: str) -> bool:
    """Report whether a path segment is excluded from the exactus.

    Args:
        name: File or directory name.

    Returns:
        ``True`` for caches, build output, hidden entries, and numbered
        copies.

    """
    return (
        name in Constants.skipped_dirs
        or name.startswith(".")
        or name.endswith((".egg-info", ".dist-info"))
        or Constants.duplicate_copy.search(string=name) is not None
    )


def scan(*, inputs: ShebangInput) -> tuple[list[Path], list[ShebangSkip]]:
    """Collect owned Python sources and the files left out.

    Files under the fixed skip rules (caches, build output, hidden
    entries, numbered copies) are not reported; symbolic links and
    files rejected by the include/exclude globs are.

    Args:
        inputs: Exactus inputs carrying the root and glob filters.

    Returns:
        Sorted audited paths and the sorted skipped files.

    """
    if inputs.source_files is not None:
        return (sorted(inputs.source_files), [])
    files: list[Path] = []
    left_out: list[ShebangSkip] = []
    collected: list[Path] = []
    directory: Path
    dirnames: list[str]
    filenames: list[str]
    for directory, dirnames, filenames in inputs.root.walk(top_down=True):
        dirnames[:] = [
            name
            for name in dirnames
            if not skipped(name=name)
            and not is_reports_tree(directory=directory / name)
        ]
        collected.extend(
            directory / name for name in filenames if name.endswith(".py")
        )
    path: Path
    for path in sorted(collected):
        relative: Path = path.relative_to(inputs.root)
        if any(skipped(name=part) for part in relative.parts):
            continue
        if path.is_symlink():
            left_out.append(
                ShebangSkip(
                    target=relative.as_posix(),
                    reason=Constants.symlink_reason,
                ),
            )
        elif path.is_file():
            if match_path(
                path=path,
                root=inputs.root,
                includes=inputs.includes,
                excludes=inputs.excludes,
            ):
                files.append(path)
            else:
                left_out.append(
                    ShebangSkip(
                        target=relative.as_posix(),
                        reason=Constants.excluded_reason,
                    ),
                )
    return files, left_out


def python_files(*, inputs: ShebangInput) -> list[Path]:
    """Collect owned Python sources under the exactus root.

    Args:
        inputs: Exactus inputs carrying the root and glob filters.

    Returns:
        Sorted source paths surviving skip and include/exclude rules.

    """
    return scan(inputs=inputs)[0]


def first_line(*, path: Path) -> bytes:
    """Read the start of a file's first line.

    Args:
        path: File to inspect.

    Returns:
        At most ``Constants.shebang_limit`` bytes of the first line.

    """
    handle: BufferedReader
    with path.open(mode="rb") as handle:
        return handle.readline(Constants.shebang_limit)


def has_shebang(*, path: Path) -> bool:
    """Report whether a file's first line is a shebang.

    Args:
        path: File to inspect.

    Returns:
        ``True`` when the first line starts with ``#!``.

    """
    return first_line(path=path).startswith(b"#!")


def _env_interpreter(*, words: list[str]) -> str:
    """Find the program an ``env`` shebang launches.

    Args:
        words: Words following ``env`` in the shebang.

    Returns:
        The program's base name, or ``env`` when none is named.

    """
    skip: bool = False
    word: str
    for word in words:
        if skip:
            skip = False
        elif word in Constants.env_value_options:
            skip = True
        elif (
            word.startswith(Constants.env_split_option)
            and word != Constants.env_split_option
        ):
            return PurePosixPath(
                word.removeprefix(Constants.env_split_option),
            ).name
        elif not (word.startswith("-") or "=" in word):
            return PurePosixPath(word).name
    return Constants.env_program


def interpreter_of(*, line: bytes) -> str | None:
    """Normalize the interpreter named by a shebang line.

    ``#!/usr/bin/env python3`` and ``#!/usr/bin/python3`` both give
    ``python3``; ``env`` options and ``NAME=value`` words are skipped, so
    ``#!/usr/bin/env -S node --flag`` gives ``node``.

    Args:
        line: First line of a file.

    Returns:
        The interpreter's base name, the unknown label for an empty
        shebang, or ``None`` when the line is not a shebang.

    """
    if not line.startswith(b"#!"):
        return None
    words: list[str] = (
        line.decode(encoding="utf-8", errors="replace")
        .removeprefix("#!")
        .split()
    )
    if not words:
        return Constants.unknown_interpreter
    program: str = PurePosixPath(words[0]).name
    if program == Constants.env_program:
        return _env_interpreter(words=words[1:])
    return program or Constants.unknown_interpreter


def inspect_file(*, path: Path, root: Path) -> FileFacts:
    """Read one file's permission bits and shebang in a single visit.

    Args:
        path: Python file to inspect.
        root: Project root for relative reporting.

    Returns:
        The file's facts; ``error`` is set when it cannot be read.

    """
    relative: str = path.relative_to(root).as_posix()
    extension: str = path.suffix.lower() or Constants.no_extension
    try:
        executable: bool = bool(
            path.stat().st_mode & Constants.executable_bits,
        )
        interpreter: str | None = interpreter_of(line=first_line(path=path))
    except OSError as error:
        return FileFacts(
            file=relative,
            extension=extension,
            error=f"cannot inspect the file: {error}",
        )
    return FileFacts(
        file=relative,
        extension=extension,
        executable=executable,
        interpreter=interpreter,
    )


def findings_for(*, facts: FileFacts) -> list[ShebangFinding]:
    """Check one file's executable bits against its shebang.

    Args:
        facts: Inspection result of the file.

    Returns:
        Zero or one permission finding for the file.

    """
    if facts.error is not None:
        return [
            ShebangFinding(
                rule="EXE003",
                file=facts.file,
                line=0,
                message=facts.error,
            ),
        ]
    shebang: bool = facts.interpreter is not None
    if shebang and not facts.executable:
        return [
            ShebangFinding(
                rule="EXE001",
                file=facts.file,
                line=1,
                message="shebang is present but the file is not executable",
            ),
        ]
    if facts.executable and not shebang:
        return [
            ShebangFinding(
                rule="EXE002",
                file=facts.file,
                line=1,
                message="file is executable but has no shebang",
            ),
        ]
    return []


def check_file(*, path: Path, root: Path) -> list[ShebangFinding]:
    """Check one file's executable bits against its shebang.

    Args:
        path: Python file to exactus.
        root: Project root for relative reporting.

    Returns:
        Zero or one permission finding for the file.

    """
    return findings_for(facts=inspect_file(path=path, root=root))


def _insert_shebang(*, path: Path, line: str) -> None:
    """Prepend a shebang line to a file's bytes.

    Args:
        path: File to rewrite.
        line: Shebang text without the trailing newline.

    """
    path.write_bytes(data=f"{line}\n".encode() + path.read_bytes())


def _strip_shebang(*, path: Path) -> None:
    """Remove a file's first line, which is a shebang.

    Args:
        path: File to rewrite.

    """
    data: bytes = path.read_bytes()
    end: int = data.find(b"\n")
    path.write_bytes(data=b"" if end == -1 else data[end + 1 :])


def _heal_exec_no_shebang(
    *,
    path: Path,
    facts: FileFacts,
    settings: ShebangSettings,
) -> ShebangHeal | None:
    """Repair an executable file that lacks a shebang.

    Args:
        path: File to repair.
        facts: Inspection result of the file.
        settings: Heal policies selected for the run.

    Returns:
        The applied repair, or ``None`` when the suffix names no known
        interpreter.

    """
    if settings.exec_no_shebang == "drop-exec":
        path.chmod(mode=path.stat().st_mode & ~Constants.executable_bits)
        return ShebangHeal(rule="EXE002", file=facts.file, action="drop-exec")
    line: str | None = Constants.shebangs.get(facts.extension)
    if line is None:
        return None
    _insert_shebang(path=path, line=line)
    return ShebangHeal(rule="EXE002", file=facts.file, action="add-shebang")


def _heal_shebang_no_exec(
    *,
    path: Path,
    facts: FileFacts,
    settings: ShebangSettings,
) -> ShebangHeal:
    """Repair a shebang file that lacks the executable bit.

    Args:
        path: File to repair.
        facts: Inspection result of the file.
        settings: Heal policies selected for the run.

    Returns:
        The applied repair.

    """
    if settings.shebang_no_exec == "drop-shebang":
        _strip_shebang(path=path)
        return ShebangHeal(
            rule="EXE001",
            file=facts.file,
            action="drop-shebang",
        )
    mode: int = path.stat().st_mode
    path.chmod(mode=mode | ((mode & Constants.readable_bits) >> 2))
    return ShebangHeal(rule="EXE001", file=facts.file, action="add-exec")


def heal_file(
    *,
    path: Path,
    facts: FileFacts,
    settings: ShebangSettings,
) -> ShebangHeal | None:
    """Repair one file's permission/shebang mismatch.

    Executable files without a shebang gain the interpreter line for
    their suffix (``add-shebang``) or lose the executable bits
    (``drop-exec``); shebang files without the executable bit gain it
    (``add-exec``) or lose the shebang (``drop-shebang``).  Files whose
    suffix has no known interpreter keep their finding.

    Args:
        path: File to repair.
        facts: Inspection result of the file.
        settings: Heal policies selected for the run.

    Returns:
        The applied repair, or ``None`` when the file is consistent or
        the suffix names no known interpreter.

    """
    if facts.error is not None:
        return None
    if facts.executable and facts.interpreter is None:
        return _heal_exec_no_shebang(path=path, facts=facts, settings=settings)
    if facts.interpreter is not None and not facts.executable:
        return _heal_shebang_no_exec(path=path, facts=facts, settings=settings)
    return None


def _ranked(*, counts: Counter[str]) -> tuple[tuple[str, int], ...]:
    """Order counted values, most frequent first, ties by name.

    Args:
        counts: Occurrences of each value.

    Returns:
        Value and count pairs.

    """
    ordered: list[tuple[int, str]] = sorted(
        (-count, value) for value, count in counts.items()
    )
    return tuple((value, -negative) for negative, value in ordered)


def collect_metrics(*, facts: list[FileFacts]) -> ShebangMetrics:
    """Summarize the facts of every scanned file.

    Args:
        facts: Inspection results in scan order.

    Returns:
        Counters, interpreter and extension tallies and the two
        mismatch path lists.

    """
    readable: list[FileFacts] = [item for item in facts if item.error is None]
    interpreters: Counter[str] = Counter(
        item.interpreter for item in readable if item.interpreter is not None
    )
    return ShebangMetrics(
        files_scanned=len(facts),
        executable_files=sum(item.executable for item in readable),
        files_with_shebang=sum(
            item.interpreter is not None for item in readable
        ),
        interpreters=_ranked(counts=interpreters),
        executable_without_shebang=tuple(
            item.file
            for item in readable
            if item.executable and item.interpreter is None
        ),
        shebang_without_executable=tuple(
            item.file
            for item in readable
            if item.interpreter is not None and not item.executable
        ),
        extensions=_ranked(counts=Counter(item.extension for item in facts)),
    )


def scan_shebang(
    *,
    inputs: ShebangInput,
    progress_span: tuple[float, float] = (0.0, 1.0),
) -> ShebangResult:
    """Exactus executable permissions for every owned Python source.

    Each file is inspected once; findings, heals and metrics share that
    visit.  When healing is enabled a repaired file produces a
    :class:`ShebangHeal` instead of a finding; a repair that fails or
    names an unknown interpreter leaves the finding in place.

    Args:
        inputs: Exactus inputs carrying the root, glob filters and
            heal policies.
        progress_span: Overall progress slice used when embedded in lints.

    Returns:
        Scanned-file count, every permission finding, the applied
        repairs and the metrics.

    """
    files: list[Path]
    left_out: list[ShebangSkip]
    files, left_out = scan(inputs=inputs)
    trace(
        step=(
            f"shebang: {len(files)} files to inspect, {len(left_out)} skipped"
        ),
        depth=3,
    )
    for skip in left_out:
        trace(step=f"shebang: {skip.target} — skipped: {skip.reason}", depth=4)
    findings: list[ShebangFinding] = []
    healed: list[ShebangHeal] = []
    facts: list[FileFacts] = []
    for index, path in enumerate(iterable=files, start=1):
        publish_progress(
            progress=Progress(
                state="RUNNING",
                completed=index,
                total=len(files),
                step="checking permissions",
                detail=path.name,
                span=progress_span,
            ),
        )
        inspected: FileFacts = inspect_file(path=path, root=inputs.root)
        facts.append(inspected)
        repair: ShebangHeal | None = None
        if inputs.settings.heal:
            try:
                repair = heal_file(
                    path=path,
                    facts=inspected,
                    settings=inputs.settings,
                )
            except OSError:
                repair = None
        if repair is not None:
            healed.append(repair)
            trace(step=f"shebang: {path} — healed: {repair.action}", depth=4)
        else:
            found: list[ShebangFinding] = findings_for(facts=inspected)
            findings.extend(found)
            trace(
                step=(
                    f"shebang: {path} — {len(found)} findings"
                    if found
                    else f"shebang: {path} — ok"
                ),
                depth=4,
            )
    return ShebangResult(
        files=len(files),
        findings=tuple(findings),
        healed=tuple(healed),
        includes=inputs.includes,
        excludes=inputs.excludes,
        skipped=tuple(left_out),
        metrics=collect_metrics(facts=facts),
    )


def metrics_data(*, metrics: ShebangMetrics) -> dict[str, JsonValue]:
    """Return the executable/shebang counters as JSON.

    Args:
        metrics: Counters gathered while scanning.

    Returns:
        Counters, interpreter and extension tables and the two path
        lists.

    """
    return cast(
        typ="dict[str, JsonValue]",
        val={
            "files_scanned": metrics.files_scanned,
            "executable_files": metrics.executable_files,
            "files_with_shebang": metrics.files_with_shebang,
            "shebang_interpreters": [
                {"interpreter": name, "count": count}
                for name, count in metrics.interpreters
            ],
            "executable_without_shebang": list(
                metrics.executable_without_shebang,
            ),
            "shebang_without_executable": list(
                metrics.shebang_without_executable,
            ),
            "by_extension": [
                {"extension": name, "count": count}
                for name, count in metrics.extensions
            ],
        },
    )
