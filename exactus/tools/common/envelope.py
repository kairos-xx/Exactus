# Copyright (c) 2026
"""Build the normalized report envelope from facts the runner knows.

The envelope is the part of a normalized ``result.json`` that every tool
shares: ``tool``, ``run``, ``invocation``, ``environment``, ``gate`` and
``artifacts``. A tool's own ``report_data`` supplies ``summary``,
``scope``, ``findings`` and ``extension``.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from os import cpu_count, environ
from platform import python_version, release, system
from re import IGNORECASE, Match, Pattern
from re import compile as compile_pattern
from shutil import which
from subprocess import (
    CalledProcessError,
    CompletedProcess,
    TimeoutExpired,
    run,
)
from typing import TYPE_CHECKING, Final

from exactus.tools.common.report_time import readable_time

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


class Constants:
    """Envelope constants.

    Attributes:
        distribution: Installed distribution whose version names the tool.
        variables: Exact environment variable names reported when set;
            no other variable's value is ever reported.
        sensitive_keys: Pattern fragment of key names carrying a secret.
        url: Pattern of a URL with a scheme, up to the next whitespace.
        assignment: Pattern of a ``key=value``/``key: value`` secret.
        flag: Pattern of a ``--secret-flag value`` pair.
        flag_only: Pattern of an argument that is a secret flag alone.
        scheme_secret: Pattern of ``Bearer``/``Basic`` credentials.
        authority_end: Characters that end a URL authority.
        redacted: Replacement text of a hidden value.
        node_timeout: Seconds allowed for ``node --version``.
        minute: Seconds in one minute.
        blocks: Envelope block names, in report order.

    """

    distribution: Final[str] = "exactus"
    variables: Final[frozenset[str]] = frozenset(
        {
            "EXACTUS_COLLECT_FILES",
            "EXACTUS_CONFIG",
            "EXACTUS_HOST",
            "EXACTUS_LINTER_TOOLCHAIN",
            "EXACTUS_ORCHESTRATED",
            "EXACTUS_PIPELINE_RUN_ID",
            "EXACTUS_PORT",
            "EXACTUS_PROJECT_PYTHON",
            "EXACTUS_RECORD_ROOT",
            "EXACTUS_REGISTRY",
            "EXACTUS_ROOT",
            "EXACTUS_RUN_ID",
            "EXACTUS_TOOL",
            "CI",
            "GITHUB_ACTIONS",
            "LANG",
            "LC_ALL",
            "NODE_ENV",
            "TERM",
            "TZ",
            "VIRTUAL_ENV",
        },
    )
    sensitive_keys: Final[str] = (
        r"(?:passw(?:or)?d|passphrase|pass(?![a-z])|pwd|secret|token"
        r"|api[_-]?key|access[_-]?key|private[_-]?key|credential"
        r"|auth(?!or)|bearer|cookie|session)"
    )
    url: Final[Pattern[str]] = compile_pattern(
        pattern=r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)(?P<rest>\S+)",
    )
    assignment: Final[Pattern[str]] = compile_pattern(
        pattern=(
            rf"(?P<key>[\w.-]*{sensitive_keys}[\w.-]*)(?P<sep>\s*[=:]\s*)"
            r"(?P<value>\"[^\"]*\"|'[^']*'|[^\s\"',;&]+)"
        ),
        flags=IGNORECASE,
    )
    flag: Final[Pattern[str]] = compile_pattern(
        pattern=(
            rf"(?P<key>(?<![\w-])--?[\w.-]*{sensitive_keys}[\w.-]*)"
            r"(?P<sep>\s+)(?P<value>(?!-)\S+)"
        ),
        flags=IGNORECASE,
    )
    flag_only: Final[Pattern[str]] = compile_pattern(
        pattern=rf"--?[\w.-]*{sensitive_keys}[\w.-]*",
        flags=IGNORECASE,
    )
    scheme_secret: Final[Pattern[str]] = compile_pattern(
        pattern=r"\b(?P<key>bearer|basic)(?P<sep>\s+)(?P<value>\S+)",
        flags=IGNORECASE,
    )
    authority_end: Final[str] = "/?#"
    redacted: Final[str] = "[redacted]"
    node_timeout: Final[float] = 5.0
    minute: Final[float] = 60.0
    blocks: Final[tuple[str, ...]] = (
        "tool",
        "run",
        "invocation",
        "environment",
        "gate",
        "artifacts",
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class RunFacts:
    """Facts about one tool run known to the runner, not the tool.

    Attributes:
        analyzer: Stable tool identifier.
        title: Fallback human-readable tool name.
        status: Run status (``PASS``, ``FAIL`` or ``ERROR``).
        exit_code: Tool exit code, when known.
        error: Unhandled error text, when the tool crashed or raised,
            even after writing its report.
        started_at: ISO start time, when known.
        finished_at: ISO finish time.
        duration_seconds: Wall-clock duration.
        run_id: Run identifier.
        pipeline_run_id: Owning pipeline run identifier.
        command: Command line that started the run.
        cwd: Working directory of the run.
        arguments: Arguments passed to the tool.
        output: Report directory holding ``ARTIFACTS/``.

    """

    analyzer: str
    title: str
    status: str
    exit_code: int | None
    error: str | None
    started_at: str | None
    finished_at: str
    duration_seconds: float
    run_id: str | None
    pipeline_run_id: str | None
    command: str
    cwd: str
    arguments: tuple[str, ...]
    output: Path


class Redaction:
    """Hide credentials in text a report shows."""

    @classmethod
    def text(cls, *, value: str) -> str:
        """Hide every credential found in one text.

        Args:
            value: Text such as an environment value or command line.

        Returns:
            The text with URL userinfo, ``Bearer``/``Basic`` credentials,
            ``key=value`` secrets and ``--secret-flag value`` pairs hidden.

        """
        hidden: str = Constants.url.sub(repl=cls.userinfo, string=value)
        pattern: Pattern[str]
        for pattern in (
            Constants.scheme_secret,
            Constants.assignment,
            Constants.flag,
        ):
            hidden = pattern.sub(repl=cls.keyed, string=hidden)
        return hidden

    @classmethod
    def arguments(cls, *, values: Sequence[str]) -> list[str]:
        """Hide credentials in an argument vector.

        Args:
            values: Arguments in order.

        Returns:
            The arguments with each one redacted as text, and the value
            following a bare secret flag such as ``--token`` hidden.

        """
        shown: list[str] = []
        previous: str = ""
        value: str
        for value in values:
            secret: bool = bool(
                Constants.flag_only.fullmatch(string=previous),
            ) and not value.startswith("-")
            shown.append(
                Constants.redacted if secret else cls.text(value=value),
            )
            previous = value
        return shown

    @staticmethod
    def userinfo(found: Match[str]) -> str:
        """Hide the userinfo of one matched URL.

        The userinfo runs to the last ``@`` of the URL token, so passwords
        holding ``@`` or ``/`` hide whole. An ``@`` that only appears after
        the authority (a path such as ``/@scope/pkg``) is kept.

        Args:
            found: :attr:`Constants.url` match.

        Returns:
            The URL with any userinfo replaced by ``[redacted]``.

        """
        scheme: str = found["scheme"]
        rest: str = found["rest"]
        at: int = rest.rfind("@")
        if at < 0:
            return found[0]
        userinfo: str = rest[:at]
        cut: int = min(
            (
                index
                for index in (
                    userinfo.find(mark) for mark in Constants.authority_end
                )
                if index >= 0
            ),
            default=-1,
        )
        if cut >= 0 and ":" not in userinfo[:cut]:
            return found[0]
        return f"{scheme}{Constants.redacted}@{rest[at + 1 :]}"

    @staticmethod
    def keyed(found: Match[str]) -> str:
        """Hide the value of one matched ``key``/``value`` secret.

        Args:
            found: Match with ``key``, ``sep`` and ``value`` groups.

        Returns:
            The key and separator followed by ``[redacted]``.

        """
        return f"{found['key']}{found['sep']}{Constants.redacted}"


class EnvironmentProbe:
    """Collect allowlisted, redacted facts about the host."""

    @classmethod
    def facts(cls, *, source: Mapping[str, str]) -> dict[str, JsonValue]:
        """Return the ``environment`` block.

        Args:
            source: Environment mapping to read variables from.

        Returns:
            OS, Python, Node, CPU count and allowlisted variables.

        """
        return {
            "os": f"{system()} {release()}".strip() or None,
            "python": python_version(),
            "node": cls.node_version(),
            "cpu_count": cpu_count(),
            "variables": cls.variables(source=source),
        }

    @staticmethod
    def node_version() -> str | None:
        """Return the installed Node.js version.

        Returns:
            ``node --version`` output, or ``None`` when Node is absent or
            fails.

        """
        program: str | None = which(cmd="node")
        if program is None:
            return None
        try:
            completed: CompletedProcess[str] = run(
                args=(program, "--version"),
                check=True,
                capture_output=True,
                text=True,
                timeout=Constants.node_timeout,
            )
        except (OSError, CalledProcessError, TimeoutExpired):
            return None
        text: str = completed.stdout.strip()
        return text or None

    @staticmethod
    def variables(*, source: Mapping[str, str]) -> list[JsonValue]:
        """Select and redact the reported environment variables.

        Args:
            source: Environment mapping to read.

        Returns:
            Sorted ``{"name", "value"}`` rows of the allowlisted variables
            that are set, each value passed through :class:`Redaction`.

        """
        names: list[str] = sorted(
            name for name in source if name in Constants.variables
        )
        return [
            {"name": name, "value": Redaction.text(value=source[name])}
            for name in names
        ]


class Envelope:
    """Assemble the runner-owned blocks of a normalized result."""

    @classmethod
    def gate(
        cls,
        *,
        facts: RunFacts,
        payload: Mapping[str, JsonValue],
    ) -> dict[str, JsonValue]:
        """Return the ``gate`` block.

        Args:
            facts: Run facts.
            payload: Tool payload supplying findings.

        Returns:
            Gate status and the reason for it. A tool whose payload
            already holds a ``gate`` composed of part gates (``parts``,
            name to ``{status, reason}``) keeps those parts unless the run
            ended in ``ERROR``, and keeps its reason when its status agrees
            with the run status.

        """
        supplied: JsonValue | None = payload.get("gate")
        tool_gate: dict[str, JsonValue] = (
            supplied if isinstance(supplied, dict) else {}
        )
        parts: JsonValue | None = tool_gate.get("parts")
        extra: dict[str, JsonValue] = (
            {"parts": parts} if isinstance(parts, dict) else {}
        )
        if facts.status == "ERROR":
            lines: list[str] = (facts.error or "").strip().splitlines()
            return {
                "status": "ERROR",
                "reason": Redaction.text(value=lines[0])
                if lines
                else "the tool ended early",
            }
        reason: JsonValue | None = tool_gate.get("reason")
        if extra and tool_gate.get("status") == facts.status and reason:
            return {"status": facts.status, "reason": reason, **extra}
        blocking: int | None = cls.blocking(payload=payload)
        if facts.status == "PASS":
            return {
                "status": "PASS",
                "reason": "No blocking findings",
                **extra,
            }
        if blocking:
            noun: str = "finding" if blocking == 1 else "findings"
            return {
                "status": "FAIL",
                "reason": f"{blocking} blocking {noun}",
                **extra,
            }
        return {
            "status": "FAIL",
            "reason": f"the tool exited with status {facts.exit_code}",
            **extra,
        }

    @classmethod
    def build(
        cls,
        *,
        facts: RunFacts,
        payload: Mapping[str, JsonValue],
    ) -> dict[str, JsonValue]:
        """Return every runner-owned block.

        Args:
            facts: Run facts.
            payload: Tool payload; its ``title`` names the tool and its
                ``findings`` drive the gate.

        Returns:
            The ``tool``, ``run``, ``invocation``, ``environment``,
            ``gate`` and ``artifacts`` blocks.

        """
        title: JsonValue | None = payload.get("title")
        duration: float = round(number=facts.duration_seconds, ndigits=3)
        return {
            "tool": {
                "name": facts.analyzer,
                "display_name": title
                if isinstance(title, str) and title
                else facts.title,
                "version": cls.tool_version(),
            },
            "run": {
                "id": facts.run_id,
                "pipeline_id": facts.pipeline_run_id,
                "status": facts.status,
                "exit_code": facts.exit_code,
                "started_at": facts.started_at,
                "finished_at": facts.finished_at,
                "at_human": readable_time(
                    value=facts.started_at or facts.finished_at,
                ),
                "started_at_human": readable_time(value=facts.started_at),
                "finished_at_human": readable_time(value=facts.finished_at),
                "duration_seconds": duration,
                "duration_human": cls.duration_human(seconds=duration),
                "error": Redaction.text(value=facts.error)
                if facts.error
                else None,
            },
            "invocation": {
                "command": Redaction.text(value=facts.command),
                "cwd": facts.cwd,
                "arguments": [*Redaction.arguments(values=facts.arguments)],
            },
            "environment": EnvironmentProbe.facts(source=environ),
            "gate": cls.gate(facts=facts, payload=payload),
            "artifacts": cls.artifacts(output=facts.output),
        }

    @staticmethod
    def duration_human(*, seconds: float) -> str:
        """Format a duration for people.

        Args:
            seconds: Duration in seconds.

        Returns:
            ``"12.3 s"`` below a minute, else ``"2 min 5 s"``.

        """
        if seconds < Constants.minute:
            return f"{seconds:.1f} s"
        minutes: int = int(seconds // Constants.minute)
        rest: int = int(seconds - minutes * Constants.minute)
        return f"{minutes} min {rest} s"

    @staticmethod
    def tool_version() -> str | None:
        """Return the installed toolkit version.

        Returns:
            The distribution version, or ``None`` when not installed.

        """
        try:
            return version(distribution_name=Constants.distribution)
        except PackageNotFoundError:
            return None

    @staticmethod
    def blocking(*, payload: Mapping[str, JsonValue]) -> int | None:
        """Count blocking findings in a tool payload.

        Args:
            payload: Tool payload, possibly without findings.

        Returns:
            Blocking finding count, or ``None`` when no findings list
            exists.

        """
        findings: JsonValue | None = payload.get("findings")
        if not isinstance(findings, list):
            return None
        return sum(
            1
            for item in findings
            if isinstance(item, dict) and item.get("blocking") is True
        )

    @staticmethod
    def artifacts(*, output: Path) -> list[JsonValue]:
        """Return the ``artifacts`` block.

        Args:
            output: Report directory holding ``ARTIFACTS/``.

        Returns:
            One ``{"name", "path", "bytes"}`` row per visible file under
            ``ARTIFACTS/``, sorted by path.

        """
        root: Path = output / "ARTIFACTS"
        rows: list[JsonValue] = []
        try:
            candidates: list[Path] = sorted(root.rglob(pattern="*"))
        except OSError:
            return rows
        path: Path
        for path in candidates:
            relative: Path = path.relative_to(output)
            if (
                path.is_symlink()
                or not path.is_file()
                or any(part.startswith(".") for part in relative.parts)
            ):
                continue
            try:
                size: int = path.stat().st_size
            except OSError:
                continue
            rows.append(
                {
                    "name": path.name,
                    "path": relative.as_posix(),
                    "bytes": size,
                },
            )
        return rows
