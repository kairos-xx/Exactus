# Copyright (c) 2026
"""Repair Python lines that remain too long after Ruff formatting.

Ruff's formatter leaves a physical line over the configured width when no
layout of the statement fits. This module repairs those residual lines
conservatively: every candidate rewrite is validated against the Python
AST, scored against Ruff's own E501 diagnostics and accepted only when it
strictly improves the file, so a repair can never change behavior.

:class:`LongLinesAPI` is the stable in-memory and batch facade;
:class:`LongLineRepair` plugs the repair into the Ruff stabilization loop of
the lints tool.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from io import BytesIO
from json import JSONDecodeError, loads
from pathlib import Path
from re import IGNORECASE, Match, search
from subprocess import CalledProcessError, CompletedProcess, run
from threading import Lock
from tokenize import detect_encoding
from tomllib import load as tload
from typing import cast

from exactus.tools.lints.long_lines_engine import (
    BatchResult,
    Constants,
    Edit,
    LongLineFixer,
    Result,
    Settings,
    TextResult,
)

__all__: list[str] = [
    "BatchResult",
    "Constants",
    "Edit",
    "LongLineFixer",
    "LongLineRepair",
    "LongLinesAPI",
    "RepairSummary",
    "Result",
    "Settings",
    "TextResult",
]


class LongLinesAPI:
    """Stable Python API for long-line repair integration.

    Every operation returns immutable structured results and accepts
    explicit configuration, so callers never depend on console output.
    """

    @classmethod
    def resolve_line_length(
        cls,
        file_path: Path,
        ruff_command: tuple[str, ...] = ("ruff",),
    ) -> int:
        """Resolve effective Ruff line length for one Python file.

        Ruff's resolved settings win; the nearest ``pyproject.toml`` is the
        fallback when Ruff is unavailable.

        Args:
            file_path: Python source path.
            ruff_command: Executable prefix used to invoke Ruff.

        Returns:
            Ruff/project line length with the canonical fallback.

        """
        try:
            completed: CompletedProcess[str] = run(
                args=[
                    *ruff_command,
                    "check",
                    "--show-settings",
                    str(object=file_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        except (CalledProcessError, FileNotFoundError):
            return cls._pyproject_line_length(file_path=file_path)
        match: Match[str] | None = search(
            pattern="(?m)^\\s*linter\\.line_length\\s*=\\s*(\\d+)\\s*$",
            string=completed.stdout,
            flags=IGNORECASE,
        )
        if match is None:
            return cls._pyproject_line_length(file_path=file_path)
        return int(match.group(1))

    @classmethod
    def fix(
        cls,
        paths: tuple[Path, ...],
        settings: Settings | None = None,
        ruff_report: Path | None = None,
        *,
        resolve_line_length: bool = False,
    ) -> BatchResult:
        """Process a deterministic batch for pipeline integration.

        Args:
            paths: Python files and/or directories.
            settings: Base repair settings.
            ruff_report: Optional broad Ruff JSON report.
            resolve_line_length: Resolve Ruff line length per project
                configuration instead of using ``settings.line_length``.

        Returns:
            Immutable aggregate batch result.

        """
        base: Settings = settings if settings is not None else Settings()
        report: dict[Path, frozenset[int]] = (
            cls.parse_ruff_report(path=ruff_report)
            if ruff_report is not None
            else {}
        )
        lengths: dict[Path | None, int] = {}

        def width(file_path: Path) -> int:
            """Resolve and memoize the width of one file's configuration.

            Args:
                file_path: Python source path.

            Returns:
                Effective line length for the file.

            """
            if not resolve_line_length:
                return base.line_length
            key: Path | None = cls.find_pyproject(file_path=file_path)
            if key not in lengths:
                lengths[key] = cls.resolve_line_length(
                    file_path=file_path,
                    ruff_command=base.ruff_command,
                )
            return lengths[key]

        return BatchResult(
            results=tuple(
                LongLineFixer(
                    settings=replace(
                        base,
                        line_length=width(file_path=path),
                        reported_e501_lines=report.get(
                            path.resolve(),
                            base.reported_e501_lines,
                        ),
                    ),
                ).fix_path(path=path)
                for path in cls.discover(paths=paths)
            ),
        )

    @staticmethod
    def parse_ruff_report(path: Path) -> dict[Path, frozenset[int]]:
        """Load E501 rows from a broad Ruff JSON report.

        Args:
            path: Ruff JSON report path.

        Returns:
            Absolute Python paths mapped to E501 row numbers.

        Raises:
            ValueError: If the report is not valid JSON.
            TypeError: If the JSON value is not a diagnostic array.

        """
        try:
            payload: object = loads(s=path.read_text(encoding="utf-8"))
        except JSONDecodeError as error:
            msg: str = f"Invalid Ruff JSON report: {path}"
            raise ValueError(msg) from error
        if not isinstance(payload, list):
            msg = f"Ruff JSON report must contain a diagnostic array: {path}"
            raise TypeError(msg)
        rows: dict[Path, set[int]] = {}
        for item in cast(typ="list[object]", val=payload):
            if not isinstance(item, dict):
                continue
            entry: dict[str, object] = cast(typ="dict[str, object]", val=item)
            if entry.get("code") != "E501":
                continue
            filename: object = entry.get("filename")
            location: object = entry.get("location")
            if not isinstance(filename, str) or not isinstance(location, dict):
                continue
            where: dict[str, object] = cast(
                typ="dict[str, object]",
                val=location,
            )
            row: object = where.get("row")
            if not isinstance(row, int) or row < 1:
                continue
            source_path: Path = Path(filename)
            if not source_path.is_absolute():
                source_path = Path.cwd() / source_path
            rows.setdefault(source_path.resolve(), set()).add(row)
        return {
            source_path: frozenset(source_rows)
            for source_path, source_rows in rows.items()
        }

    @staticmethod
    def find_pyproject(file_path: Path) -> Path | None:
        """Find the nearest applicable ``pyproject.toml``.

        Args:
            file_path: Python source path.

        Returns:
            Nearest configuration path, if present.

        """
        directory: Path = file_path.resolve().parent
        for candidate_directory in (directory, *directory.parents):
            candidate: Path = candidate_directory / Constants.pyproject_name
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def discover(paths: tuple[Path, ...]) -> tuple[Path, ...]:
        """Expand file/directory inputs into deterministic Python paths.

        Args:
            paths: Files and directories to inspect.

        Returns:
            Sorted unique Python files after canonical exclusions.

        """
        files: set[Path] = set()
        for path in paths:
            if path.is_file() and path.suffix == ".py":
                files.add(path)
            elif path.is_dir():
                files.update(
                    candidate
                    for candidate in path.rglob(pattern="*.py")
                    if not any(
                        part.startswith(".") for part in candidate.parts
                    )
                    and (
                        not Constants.excluded_parts.intersection(
                            candidate.parts,
                        )
                    )
                    and (
                        not (
                            "exactus" in candidate.parts
                            and "bundle" in candidate.parts
                        )
                    )
                )
        return tuple(sorted(files))

    @staticmethod
    def ruff_e501_rows(
        path: Path,
        ruff_command: tuple[str, ...] = ("ruff",),
    ) -> frozenset[int]:
        """Collect the rows Ruff reports as E501 for one file.

        Ruff, not a width heuristic, decides which rows are over-long, so
        these rows seed the first repair pass.

        Args:
            path: Python source path.
            ruff_command: Executable prefix used to invoke Ruff.

        Returns:
            One-based E501 rows; empty when Ruff is unavailable.

        """
        try:
            completed: CompletedProcess[str] = run(
                args=[
                    *ruff_command,
                    "check",
                    "--select",
                    "E501",
                    "--output-format",
                    "json",
                    "--no-fix",
                    str(object=path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            payload: object = loads(s=completed.stdout or "[]")
        except (FileNotFoundError, JSONDecodeError):
            return frozenset()
        if not isinstance(payload, list):
            return frozenset()
        rows: set[int] = set()
        for item in cast(typ="list[object]", val=payload):
            if not isinstance(item, dict):
                continue
            entry: dict[str, object] = cast(typ="dict[str, object]", val=item)
            location: object = entry.get("location")
            if entry.get("code") != "E501" or not isinstance(location, dict):
                continue
            row: object = cast(typ="dict[str, object]", val=location).get(
                "row",
            )
            if isinstance(row, int) and row >= 1:
                rows.add(row)
        return frozenset(rows)

    @staticmethod
    def ruff_e501_rows_many(
        paths: tuple[Path, ...],
        ruff_command: tuple[str, ...] = ("ruff",),
    ) -> dict[Path, frozenset[int]]:
        """Collect Ruff E501 rows for many files with one subprocess.

        Args:
            paths: Python source paths.
            ruff_command: Executable prefix used to invoke Ruff.

        Returns:
            Absolute paths mapped to their one-based E501 rows. Files with
            no E501 diagnostics are omitted.

        """
        if not paths:
            return {}
        try:
            completed: CompletedProcess[str] = run(
                args=[
                    *ruff_command,
                    "check",
                    "--select",
                    "E501",
                    "--output-format",
                    "json",
                    "--no-fix",
                    *(str(object=path) for path in paths),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            payload: object = loads(s=completed.stdout or "[]")
        except (FileNotFoundError, JSONDecodeError):
            return {}
        if not isinstance(payload, list):
            return {}
        rows: dict[Path, set[int]] = {}
        for item in cast(typ="list[object]", val=payload):
            if not isinstance(item, dict):
                continue
            entry: dict[str, object] = cast(typ="dict[str, object]", val=item)
            filename: object = entry.get("filename")
            location: object = entry.get("location")
            if (
                entry.get("code") != "E501"
                or not isinstance(filename, str)
                or not isinstance(location, dict)
            ):
                continue
            row: object = cast(typ="dict[str, object]", val=location).get(
                "row",
            )
            if not isinstance(row, int) or row < 1:
                continue
            source_path: Path = Path(filename)
            if not source_path.is_absolute():
                source_path = Path.cwd() / source_path
            rows.setdefault(source_path.resolve(), set()).add(row)
        return {
            source_path: frozenset(source_rows)
            for source_path, source_rows in rows.items()
        }

    @staticmethod
    def has_long_lines(path: Path, line_length: int) -> bool:
        """Cheaply test whether a file has a physical line over the width.

        Args:
            path: Python source path.
            line_length: Maximum physical line width.

        Returns:
            ``True`` when any line exceeds the width after tab expansion.

        """
        data: bytes = path.read_bytes()
        encoding: str = detect_encoding(
            readline=BytesIO(initial_bytes=data).readline,
        )[0]
        return any(
            len(line.expandtabs(tabsize=Constants.tab_size)) > line_length
            for line in data.decode(encoding=encoding).splitlines()
        )

    @staticmethod
    def transform(
        source: str,
        settings: Settings | None = None,
        path: Path | None = None,
    ) -> TextResult:
        """Transform source without filesystem mutation.

        Args:
            source: Python source.
            settings: Explicit repair settings.
            path: Optional Ruff configuration identity.

        Returns:
            In-memory transformation result.

        """
        return LongLineFixer(
            settings=settings if settings is not None else Settings(),
        ).transform_text(source=source, path=path)

    @staticmethod
    def fix_file(path: Path, settings: Settings | None = None) -> Result:
        """Process one Python file.

        Args:
            path: Python file.
            settings: Explicit repair settings.

        Returns:
            File transformation result.

        """
        return LongLineFixer(
            settings=settings if settings is not None else Settings(),
        ).fix_path(path=path)

    @classmethod
    def _pyproject_line_length(cls, file_path: Path) -> int:
        """Read the line length from the nearest ``pyproject.toml``.

        Args:
            file_path: Python source path.

        Returns:
            Configured ``[tool.ruff]`` width or the canonical default.

        """
        toml_path: Path | None = cls.find_pyproject(file_path=file_path)
        if toml_path is None:
            return Constants.default_line_length
        with toml_path.open(mode="rb") as file:
            tool: object = tload(file).get("tool", {})
        ruff: object = (
            cast(typ="dict[str, object]", val=tool).get("ruff", {})
            if isinstance(tool, dict)
            else {}
        )
        if not isinstance(ruff, dict):
            return Constants.default_line_length
        settings: dict[str, object] = cast(typ="dict[str, object]", val=ruff)
        width: object = settings.get("line-length")
        if isinstance(width, (int, str)):
            return int(width)
        format_settings: object = settings.get("format")
        if isinstance(format_settings, dict):
            line_width: object = cast(
                typ="dict[str, object]",
                val=format_settings,
            ).get("line-width")
            if isinstance(line_width, (int, str)):
                return int(line_width)
        return Constants.default_line_length


@dataclass(frozen=True, slots=True)
class RepairSummary:
    """Totals gathered by one :class:`LongLineRepair` over a lint run.

    Attributes:
        repaired: Files changed by the repair.
        unresolved: Files that still have lines Ruff reports, by path.
        skipped: Files that could not be read or decoded.

    """

    repaired: tuple[Path, ...]
    unresolved: tuple[Path, ...]
    skipped: tuple[Path, ...]


class LongLineRepair:
    """Repair residual long lines inside the Ruff stabilization loop.

    The instance is a ``exactus.packages.all_lints`` ``FileRepair``: the
    stabilizer
    calls it for every file after Ruff formatted and fixed it, and runs
    another Ruff cycle when the file changed. It is safe to call from
    worker threads; the per-configuration width cache and the totals are
    guarded by one lock, and each call owns its fixer.
    """

    def __init__(self, *, ruff_command: tuple[str, ...] = ("ruff",)) -> None:
        """Create a repair bound to one Ruff launcher.

        Args:
            ruff_command: Executable prefix used to invoke Ruff.

        """
        self._ruff_command: tuple[str, ...] = ruff_command
        self._lock: Lock = Lock()
        self._lengths: dict[Path | None, int] = {}
        self._repaired: set[Path] = set()
        self._unresolved: set[Path] = set()
        self._skipped: set[Path] = set()

    def repair_many(self, *, paths: tuple[Path, ...]) -> None:
        """Repair Ruff-reported E501 rows across a batch.

        One Ruff invocation discovers all candidate rows. Only files Ruff
        actually reports are passed through the repair engine, avoiding one
        subprocess per physical long-line candidate.

        Args:
            paths: Python files Ruff just formatted and fixed.

        """
        reported_by_path: dict[Path, frozenset[int]] = (
            LongLinesAPI.ruff_e501_rows_many(
                paths=paths,
                ruff_command=self._ruff_command,
            )
        )
        for path in paths:
            reported: frozenset[int] | None = reported_by_path.get(
                path.resolve(),
            )
            if not reported:
                continue
            try:
                result: Result = LongLinesAPI.fix_file(
                    path=path,
                    settings=Settings(
                        line_length=self._line_length(path=path),
                        ruff_command=self._ruff_command,
                        reported_e501_lines=reported,
                    ),
                )
            except (OSError, SyntaxError, UnicodeError):
                with self._lock:
                    self._skipped.add(path)
                continue
            with self._lock:
                if result.changed:
                    self._repaired.add(path)
                if result.unresolved_lines:
                    self._unresolved.add(path)

    def summary(self) -> RepairSummary:
        """Return the totals gathered so far.

        Returns:
            Sorted repaired, unresolved and skipped file paths.

        """
        with self._lock:
            return RepairSummary(
                repaired=tuple(sorted(self._repaired)),
                unresolved=tuple(sorted(self._unresolved)),
                skipped=tuple(sorted(self._skipped)),
            )

    def __call__(self, *, path: Path) -> None:
        """Repair one stabilized file in place.

        Files that cannot be read or decoded are skipped and recorded;
        the lint report surfaces their syntax diagnostics.

        Args:
            path: Python file Ruff just formatted and fixed.

        """
        try:
            line_length: int = self._line_length(path=path)
            if not LongLinesAPI.has_long_lines(
                path=path,
                line_length=line_length,
            ):
                return
            reported: frozenset[int] = LongLinesAPI.ruff_e501_rows(
                path=path,
                ruff_command=self._ruff_command,
            )
            result: Result = LongLinesAPI.fix_file(
                path=path,
                settings=Settings(
                    line_length=line_length,
                    ruff_command=self._ruff_command,
                    reported_e501_lines=reported,
                ),
            )
        except (OSError, SyntaxError, UnicodeError):
            with self._lock:
                self._skipped.add(path)
            return
        with self._lock:
            if result.changed:
                self._repaired.add(path)
            if result.unresolved_lines:
                self._unresolved.add(path)

    def _line_length(self, *, path: Path) -> int:
        """Resolve the line length of one file's Ruff configuration.

        Args:
            path: Python source path.

        Returns:
            Effective line length, resolved once per configuration file.

        """
        key: Path | None = LongLinesAPI.find_pyproject(file_path=path)
        with self._lock:
            known: int | None = self._lengths.get(key)
        if known is not None:
            return known
        resolved: int = LongLinesAPI.resolve_line_length(
            file_path=path,
            ruff_command=self._ruff_command,
        )
        with self._lock:
            self._lengths[key] = resolved
        return resolved
