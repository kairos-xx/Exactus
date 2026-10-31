# Copyright (c) 2026 João Lopes.
"""Cross-platform process primitives used by the orchestrator."""

from __future__ import annotations

from abc import ABC, abstractmethod
from json import loads
from os import kill
from os import name as os_name
from pathlib import Path
from signal import SIGCONT, SIGSTOP, SIGTERM
from subprocess import DEVNULL, CompletedProcess, Popen, run
from typing import ClassVar, Final, final


class PlatformError(RuntimeError):
    """Platformerror."""


class ProcessBackend(ABC):
    """Define platform-specific process operations."""

    @abstractmethod
    def command_lines(self) -> tuple[tuple[int, str], ...]:
        """Return visible process command lines.

        Returns:
            Process identifiers paired with command lines.

        """

    @abstractmethod
    def detached_kwargs(self) -> dict[str, bool | int]:
        """Return detached-spawn metadata for diagnostics.

        Returns:
            Platform-specific subprocess keyword metadata.

        """

    @abstractmethod
    def spawn(self, command: list[str]) -> Popen[bytes]:
        """Spawn one detached process.

        Args:
            command: Command and arguments to execute.

        Returns:
            Spawned process handle.

        """

    @abstractmethod
    def pause(self, pid: int) -> None:
        """Pause a process.

        Args:
            pid: Process identifier.

        """

    @abstractmethod
    def resume(self, pid: int) -> None:
        """Resume a process.

        Args:
            pid: Process identifier.

        """

    @abstractmethod
    def terminate(self, pid: int) -> None:
        """Terminate a process.

        Args:
            pid: Process identifier.

        """


@final
class PosixBackend(ProcessBackend):
    """Posixbackend."""

    _proc_root: ClassVar[Path] = Path("/proc")

    def command_lines(self) -> tuple[tuple[int, str], ...]:
        """Command lines.

        Returns:
            The resulting value.

        """
        if self._proc_root.is_dir():
            rows: list[tuple[int, str]] = []
            try:
                processes: list[Path] = sorted(
                    self._proc_root.iterdir(),
                    key=lambda item: item.name,
                )
            except OSError:
                return ()
            for process in processes:
                if not process.name.isdigit():
                    continue
                try:
                    values: list[bytes] = [
                        value
                        for value in (process / "cmdline")
                        .read_bytes()
                        .split(sep=b"\0")
                        if value
                    ]
                except OSError:
                    continue
                command: str = " ".join(
                    value.decode(encoding="utf-8", errors="replace")
                    for value in values
                )
                if command:
                    rows.append((int(process.name), command))
            return tuple(rows)
        result: CompletedProcess[str] = run(
            args=["/bin/ps", "-ww", "-axo", "pid=,command="],
            capture_output=True,
            text=True,
            check=False,
        )
        rows = []
        for line in result.stdout.splitlines():
            stripped: str = line.strip()
            if not stripped:
                continue
            pid_text, separator, command = stripped.partition(" ")
            if separator and pid_text.isdigit():
                rows.append((int(pid_text), command.strip()))
        return tuple(rows)

    def detached_kwargs(self) -> dict[str, bool | int]:
        """Detached kwargs.

        Returns:
            The resulting value.

        """
        return {"start_new_session": True, "close_fds": True}

    def spawn(self, command: list[str]) -> Popen[bytes]:
        """Spawn one detached POSIX process.

        Args:
            command: Command and arguments to execute.

        Returns:
            Spawned process handle.

        """
        return Popen(
            args=command,
            stdin=DEVNULL,
            stdout=DEVNULL,
            stderr=DEVNULL,
            start_new_session=True,
            close_fds=True,
        )

    def pause(self, pid: int) -> None:
        """Pause.

        Args:
            pid: Pid.

        """
        kill(pid, SIGSTOP)

    def resume(self, pid: int) -> None:
        """Resume.

        Args:
            pid: Pid.

        """
        kill(pid, SIGCONT)

    def terminate(self, pid: int) -> None:
        """Terminate.

        Args:
            pid: Pid.

        """
        kill(pid, SIGTERM)


@final
class WindowsBackend(ProcessBackend):
    """Windowsbackend."""

    _PROCESS_SUSPEND_RESUME: Final[int] = 2048
    _PROCESS_TERMINATE: Final[int] = 1

    @staticmethod
    def powershell_process_action(pid: int, method: str) -> None:
        """Powershell process action.

        Args:
            pid: Pid.
            method: Method.

        Raises:
            PlatformError: When the operation cannot complete.

        """
        if method not in {"Suspend", "Resume"}:
            msg: str = f"Unsupported Windows action {method}."
            raise PlatformError(msg)
        script: str = (
            f"$p=Get-Process -Id {pid} -ErrorAction Stop;"
            f'$sig=\'[DllImport("ntdll.dll")]public static extern int '
            f"Nt{method}Process(IntPtr h);';"
            "$t=Add-Type -MemberDefinition $sig -Name N -Namespace O "
            "-PassThru;"
            f"$r=$t::Nt{method}Process($p.Handle);exit $r"
        )
        result: CompletedProcess[str] = run(
            args=[
                (
                    "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershel"
                    "l.exe"
                ),
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            msg = f"Unable to {method.lower()} Windows process {pid}."
            raise PlatformError(msg)

    def command_lines(self) -> tuple[tuple[int, str], ...]:
        """Command lines.

        Returns:
            The resulting value.

        """
        script: str = (
            "Get-CimInstance Win32_Process | "
            "Select-Object ProcessId,CommandLine | "
            "ConvertTo-Json -Compress"
        )
        result: CompletedProcess[str] = run(
            args=[
                (
                    "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershel"
                    "l.exe"
                ),
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return ()
        value: (
            list[dict[str, int | str | None]] | dict[str, int | str | None]
        ) = loads(s=result.stdout)
        items: list[dict[str, int | str | None]] = (
            value if isinstance(value, list) else [value]
        )
        rows: list[tuple[int, str]] = []
        for item in items:
            pid_value: int | str | None = item.get("ProcessId")
            if isinstance(pid_value, int):
                rows.append(
                    (pid_value, str(object=item.get("CommandLine") or "")),
                )
        return tuple(rows)

    def detached_kwargs(self) -> dict[str, bool | int]:
        """Detached kwargs.

        Returns:
            The resulting value.

        """
        return {"creationflags": 8 | 512, "close_fds": True}

    def spawn(self, command: list[str]) -> Popen[bytes]:
        """Spawn one detached Windows process.

        Args:
            command: Command and arguments to execute.

        Returns:
            Spawned process handle.

        """
        return Popen(
            args=command,
            stdin=DEVNULL,
            stdout=DEVNULL,
            stderr=DEVNULL,
            creationflags=8 | 512,
            close_fds=True,
        )

    def pause(self, pid: int) -> None:
        """Pause.

        Args:
            pid: Pid.

        """
        self.powershell_process_action(pid=pid, method="Suspend")

    def resume(self, pid: int) -> None:
        """Resume.

        Args:
            pid: Pid.

        """
        self.powershell_process_action(pid=pid, method="Resume")

    def terminate(self, pid: int) -> None:
        """Terminate.

        Args:
            pid: Pid.

        Raises:
            PlatformError: When the operation cannot complete.

        """
        process: Popen[bytes] = Popen(
            args=[
                "C:\\Windows\\System32\\taskkill.exe",
                "/PID",
                str(object=pid),
                "/T",
                "/F",
            ],
            stdin=DEVNULL,
            stdout=DEVNULL,
            stderr=DEVNULL,
        )
        if process.wait() != 0:
            msg: str = f"Unable to terminate Windows process {pid}."
            raise PlatformError(msg)


def backend() -> ProcessBackend:
    """Backend.

    Returns:
        The resulting value.

    """
    return WindowsBackend() if os_name == "nt" else PosixBackend()
