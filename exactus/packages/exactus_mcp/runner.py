# Copyright (c) 2026
"""Run a constrained Exactus report command for an MCP caller."""

from __future__ import annotations

from asyncio import Lock, create_subprocess_exec, to_thread, wait_for
from asyncio.subprocess import PIPE, STDOUT, Process
from dataclasses import dataclass
from json import JSONDecodeError, loads
from os import environ, pathsep
from pathlib import Path, PurePath
from sys import executable
from typing import TYPE_CHECKING, Final, Literal, Protocol, cast, final

from exactus.tools.common.catalog import Constants as CatalogConstants
from exactus.tools.common.catalog import ToolSpec
from exactus.tools.common.config import (
    discovery_from_environment,
    reports_anchor,
    reports_directory,
)

if TYPE_CHECKING:
    from exactus.packages.server.json_types import JsonValue
    from exactus.tools.common.config import ConfigFile
type RemoteTool = Literal["docs", "kwargs_typehints", "lints", "readme"]
type ReportFormat = Literal["json", "markdown"]


@final
class Constants:
    """Group runner constants.

    Attributes:
        output_tail: Maximum captured command output returned to a caller.
        maximum_includes: Maximum include globs accepted per remote run.
        maximum_include_length: Maximum characters in one include glob.
        remote_tools: Exactus tools admitted through the public service.

    """

    output_tail: Final[int] = 16_000
    maximum_includes: Final[int] = 64
    maximum_include_length: Final[int] = 512
    remote_tools: Final[tuple[RemoteTool, ...]] = (
        "docs",
        "kwargs_typehints",
        "lints",
        "readme",
    )


@final
@dataclass(frozen=True, slots=True)
class CheckResult:
    """Summarize one completed Exactus check.

    Attributes:
        tool: Exactus tool that ran.
        exit_code: Exactus process exit status.
        status: Status read from the generated JSON report.
        findings: Total findings recorded by the report.
        report_path: Generated machine-readable report path.
        output: Tail of the captured Exactus process output.
        report: Complete parsed machine-readable Exactus report.

    """

    tool: RemoteTool
    exit_code: int
    status: str
    findings: int
    report_path: Path
    output: str
    report: JsonValue

    def to_json(self) -> dict[str, JsonValue]:
        """Return a JSON-compatible representation.

        Returns:
            Structured MCP tool result.

        """
        return {
            "tool": self.tool,
            "exit_code": self.exit_code,
            "status": self.status,
            "findings": self.findings,
            "report_path": str(object=self.report_path),
            "output": self.output,
            "report": self.report,
        }


class Runner(Protocol):
    """Contract used by the MCP service to run Exactus."""

    @staticmethod
    def list_tools() -> tuple[str, ...]:
        """Return the complete Exactus catalog.

        Returns:
            Canonical tool identifiers.

        """
        ...

    async def run(
        self,
        *,
        tool: RemoteTool,
        includes: tuple[str, ...],
    ) -> CheckResult:
        """Run one protected Exactus check.

        Args:
            tool: Safe report-oriented tool identifier.
            includes: Repository-relative include globs.

        Returns:
            Completed check result.

        """
        ...

    def read_report(
        self,
        *,
        tool: RemoteTool,
        report_format: ReportFormat,
    ) -> str:
        """Read one generated Exactus report.

        Args:
            tool: Safe report-oriented tool identifier.
            report_format: Markdown or JSON representation.

        Returns:
            Report text, or an explanatory missing-report message.

        """
        ...


@final
class ExactusCommandRunner:
    """Execute Exactus with a fixed root, dry mode, and timeout."""

    def __init__(self, *, root: Path, timeout: float) -> None:
        """Create a constrained runner.

        Args:
            root: Project root Exactus may inspect.
            timeout: Maximum seconds permitted for one check.

        """
        self._root: Path = root
        self._timeout: float = timeout
        self._lock: Lock = Lock()

    @staticmethod
    def list_tools() -> tuple[str, ...]:
        """Return the complete canonical Exactus tool catalog.

        Returns:
            Sorted canonical tool identifiers.

        """
        catalog_tools: tuple[ToolSpec, ...] = (
            CatalogConstants.exactus_catalog.tools()
        )
        identifiers: list[str] = []
        tool_index: int = 0
        while tool_index < len(catalog_tools):
            identifiers.append(catalog_tools[tool_index].identifier)
            tool_index += 1
        return tuple(sorted(identifiers))

    async def run(
        self,
        *,
        tool: RemoteTool,
        includes: tuple[str, ...],
    ) -> CheckResult:
        """Run one Exactus check without permitting source mutation.

        Args:
            tool: Safe report-oriented tool identifier.
            includes: Repository-relative include globs.

        Returns:
            Completed check result and generated-report summary.

        """
        self._validate_includes(includes=includes)
        command: list[str] = [
            executable,
            "-m",
            "exactus",
            "--root",
            str(object=self._root),
            f"--{tool}",
            str(object=self._root),
            "--dry",
        ]
        include: str
        for include in includes:
            command.extend(("--include", include))
        async with self._lock:
            return await self._execute(tool=tool, command=tuple(command))

    def read_report(
        self,
        *,
        tool: RemoteTool,
        report_format: ReportFormat,
    ) -> str:
        """Read a generated report from the configured report tree.

        Args:
            tool: Safe report-oriented tool identifier.
            report_format: Markdown or JSON representation.

        Returns:
            Report text, or an explanatory missing-report message.

        """
        suffix: str = "json" if report_format == "json" else "md"
        report: Path = self._report_path(tool=tool).with_suffix(
            suffix=f".{suffix}",
        )
        if not report.is_file():
            return f"No {report_format} report exists for {tool}."
        return report.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _report_summary(*, path: Path) -> tuple[str, int]:
        """Read status and finding count from a report.

        Args:
            path: Machine-readable Exactus report.

        Returns:
            Status and total finding count.

        """
        try:
            payload: JsonValue = cast(
                typ="JsonValue",
                val=loads(s=path.read_text(encoding="utf-8")),
            )
        except (JSONDecodeError, OSError):
            return ("INVALID", 0)
        if not isinstance(payload, dict):
            return ("INVALID", 0)
        raw_status: JsonValue = payload.get("status")
        summary: JsonValue = payload.get("summary")
        raw_findings: JsonValue = (
            summary.get("findings_total")
            if isinstance(summary, dict)
            else None
        )
        status: str = raw_status if isinstance(raw_status, str) else "UNKNOWN"
        findings: int = (
            raw_findings
            if isinstance(raw_findings, int)
            and not isinstance(raw_findings, bool)
            else 0
        )
        return (status, findings)

    @staticmethod
    def _validate_includes(*, includes: tuple[str, ...]) -> None:
        """Reject include patterns that can escape the configured root.

        Args:
            includes: Repository-relative include globs.

        Raises:
            ValueError: If a pattern is absolute, traverses upward, or is too
                large for the remote boundary.

        """
        if len(includes) > Constants.maximum_includes:
            msg: str = (
                f"at most {Constants.maximum_includes} include patterns "
                "are accepted"
            )
            raise ValueError(msg)
        include: str
        for include in includes:
            path: PurePath = PurePath(include)
            if (
                path.is_absolute()
                or ".." in path.parts
                or len(include) > Constants.maximum_include_length
            ):
                msg = f"unsafe include pattern: {include!r}"
                raise ValueError(msg)

    async def _execute(
        self,
        *,
        tool: RemoteTool,
        command: tuple[str, ...],
    ) -> CheckResult:
        """Execute one validated command and parse its report.

        Args:
            tool: Safe report-oriented tool identifier.
            command: Fully constructed Exactus command.

        Returns:
            Completed check result.

        """
        process_environment: dict[str, str] = dict(environ)
        process_environment["PATH"] = (
            f"{Path(executable).parent}{pathsep}"
            f"{process_environment.get('PATH', '')}"
        )
        process: Process = await create_subprocess_exec(
            *command,
            cwd=self._root,
            env=process_environment,
            stdout=PIPE,
            stderr=STDOUT,
        )
        output: bytes
        try:
            output, _ = await wait_for(
                fut=process.communicate(),
                timeout=self._timeout,
            )
        except TimeoutError:
            process.terminate()
            try:
                _ = await wait_for(fut=process.wait(), timeout=5.0)
            except TimeoutError:
                process.kill()
                _ = await process.wait()
            return CheckResult(
                tool=tool,
                exit_code=124,
                status="TIMEOUT",
                findings=0,
                report_path=self._report_path(tool=tool),
                output=f"Exactus exceeded {self._timeout:g} seconds.",
                report=None,
            )
        report: Path = self._report_path(tool=tool)
        status: str = "MISSING"
        findings: int = 0
        report_exists: bool = await to_thread(report.is_file)
        report_payload: JsonValue = None
        if report_exists:
            status, findings = await to_thread(
                self._report_summary,
                path=report,
            )
            try:
                report_payload = cast(
                    typ="JsonValue",
                    val=loads(
                        s=await to_thread(report.read_text, encoding="utf-8"),
                    ),
                )
            except (JSONDecodeError, OSError):
                report_payload = None
        decoded: str = output.decode(errors="replace")
        return CheckResult(
            tool=tool,
            exit_code=process.returncode or 0,
            status=status,
            findings=findings,
            report_path=report,
            output=decoded[-Constants.output_tail :],
            report=report_payload,
        )

    def _report_path(self, *, tool: RemoteTool) -> Path:
        """Return the JSON report path for one tool.

        Args:
            tool: Canonical safe tool identifier.

        Returns:
            Expected ``result.json`` path.

        Raises:
            ValueError: If the catalog no longer contains the tool.

        """
        spec: ToolSpec | None = CatalogConstants.exactus_catalog.tool(
            identifier=tool,
        )
        if spec is None:
            msg: str = f"unknown Exactus tool: {tool}"
            raise ValueError(msg)
        files: tuple[ConfigFile, ...] = discovery_from_environment(
            start=self._root,
        )
        anchor: Path = reports_anchor(files=files, start=self._root)
        reports: Path = reports_directory(files=files)
        return anchor / reports / spec.output / "result.json"
