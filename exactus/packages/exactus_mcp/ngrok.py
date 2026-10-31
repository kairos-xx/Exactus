# Copyright (c) 2026
"""Own an ngrok child process and discover its public HTTPS origin."""

from __future__ import annotations

from asyncio import create_subprocess_exec, wait_for
from asyncio.subprocess import PIPE, STDOUT, Process
from dataclasses import dataclass
from json import JSONDecodeError, loads
from shutil import which
from typing import TYPE_CHECKING, Final, cast, final
from urllib.parse import ParseResult, urlparse

if TYPE_CHECKING:
    from exactus.packages.server.json_types import JsonValue


@final
class Constants:
    """Group ngrok lifecycle constants.

    Attributes:
        log_tail: Maximum startup log lines retained in an error.

    """

    log_tail: Final[int] = 24


@final
@dataclass(slots=True)
class NgrokTunnel:
    """A running ngrok process and its allocated public origin.

    Attributes:
        process: Owned ngrok child process.
        public_url: Allocated public HTTPS origin.

    """

    process: Process
    public_url: str

    @classmethod
    async def start(
        cls,
        *,
        command: str,
        upstream_url: str,
        startup_timeout: float,
        requested_url: str | None,
        endpoint_name: str | None,
    ) -> NgrokTunnel:
        """Start ngrok and wait for its public URL.

        Args:
            command: Ngrok executable name or path.
            upstream_url: Local Exactus MCP HTTP origin.
            startup_timeout: Maximum startup wait in seconds.
            requested_url: Optional reserved ngrok URL.
            endpoint_name: Optional endpoint defined in ngrok configuration.

        Returns:
            Running tunnel descriptor.

        Raises:
            RuntimeError: If ngrok is missing, exits, or does not allocate an
                HTTPS URL before the timeout.

        """
        executable: str | None = which(cmd=command)
        if executable is None:
            msg: str = f"ngrok executable not found: {command}"
            raise RuntimeError(msg)
        if endpoint_name is None:
            arguments: list[str] = [
                "http",
                upstream_url,
                "--log",
                "stdout",
                "--log-format",
                "json",
                "--log-level",
                "info",
                "--name",
                "exactus-mcp",
            ]
            if requested_url is not None:
                arguments.extend(("--url", requested_url))
        else:
            arguments = [
                "start",
                "--log",
                "stdout",
                "--log-format",
                "json",
                "--log-level",
                "info",
                endpoint_name,
            ]
        process: Process = await create_subprocess_exec(
            executable,
            *arguments,
            stdout=PIPE,
            stderr=STDOUT,
        )
        try:
            public_url: str = await wait_for(
                fut=cls._public_url(process=process),
                timeout=startup_timeout,
            )
        except (RuntimeError, TimeoutError):
            await cls._stop(process=process)
            raise
        return cls(process=process, public_url=public_url)

    @staticmethod
    def parse_public_url(*, line: str) -> str | None:
        """Extract a valid public URL from one ngrok JSON log line.

        Args:
            line: Candidate ngrok log record.

        Returns:
            HTTPS origin, or ``None`` when the record is unrelated.

        """
        try:
            payload: JsonValue = cast(typ="JsonValue", val=loads(s=line))
        except JSONDecodeError:
            return None
        if (
            not isinstance(payload, dict)
            or payload.get("msg") != "started tunnel"
        ):
            return None
        raw_url: JsonValue = payload.get("url")
        if not isinstance(raw_url, str):
            return None
        parsed: ParseResult = urlparse(url=raw_url)
        return raw_url if parsed.scheme == "https" and parsed.netloc else None

    async def wait(self) -> int:
        """Wait for ngrok to exit.

        Returns:
            Ngrok process exit status.

        """
        return await self.process.wait()

    async def close(self) -> None:
        """Stop the owned ngrok process and wait for cleanup."""
        await self._stop(process=self.process)

    @classmethod
    async def _public_url(cls, *, process: Process) -> str:
        """Read ngrok JSON logs until a public HTTPS URL appears.

        Args:
            process: Running ngrok process.

        Returns:
            Public HTTPS origin.

        Raises:
            RuntimeError: If ngrok exits before advertising a URL.

        """
        if process.stdout is None:
            msg: str = "ngrok stdout was not captured"
            raise RuntimeError(msg)
        logs: list[str] = []
        while True:
            line_bytes: bytes = await process.stdout.readline()
            if not line_bytes:
                exit_code: int = await process.wait()
                tail: str = "\n".join(logs[-Constants.log_tail :])
                msg = f"ngrok exited with status {exit_code}\n{tail}"
                raise RuntimeError(msg)
            line: str = line_bytes.decode(errors="replace").strip()
            logs.append(line)
            candidate: str | None = cls.parse_public_url(line=line)
            if candidate is not None:
                return candidate

    @staticmethod
    async def _stop(*, process: Process) -> None:
        """Stop one owned ngrok child process.

        Args:
            process: Ngrok child to stop.

        """
        if process.returncode is not None:
            return
        process.terminate()
        try:
            _ = await wait_for(fut=process.wait(), timeout=5.0)
        except TimeoutError:
            process.kill()
            _ = await process.wait()
