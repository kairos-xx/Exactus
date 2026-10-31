# Copyright (c) 2026 João Lopes.
"""Source-preserving JavaScript class-method organization."""

from dataclasses import dataclass
from importlib.resources import as_file
from importlib.resources import files as resource_files
from json import JSONDecodeError, dumps, loads
from pathlib import Path
from shutil import which
from subprocess import PIPE, CompletedProcess
from typing import Final, cast, final

from psutil import Popen

type JsonScalar = str | int | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


@final
class Constants:
    """Group module-level constants.

    Attributes:
        resolve_local: Grouped module constant.
        resolve_eslint: Grouped module constant.

    """

    resolve_local: Final[str] = (
        "const{createRequire}=require('node:module');const "
        "r=createRequire(process.argv[1]);process.stdout.write(r.resolve('"
        "espree'));"
    )
    resolve_eslint: Final[str] = (
        "const{createRequire}=require('node:module');const{realpathSync}=r"
        "equire('node:fs');const "
        "r=createRequire(realpathSync(process.argv[1]));process.stdout.wri"
        "te(r.resolve('espree'));"
    )


@dataclass(frozen=True, slots=True)
class JavaScriptReorderMetrics:
    """Metrics produced by JavaScript class-method organization.

    Attributes:
        classes_reordered: Classes whose method order changed.
        classes_seen: Structural classes inspected.
        lines_moved: Source lines relocated.
        methods_moved: Methods whose position changed.
        methods_seen: Direct methods inspected.

    """

    classes_reordered: int = 0
    classes_seen: int = 0
    lines_moved: int = 0
    methods_moved: int = 0
    methods_seen: int = 0


@dataclass(frozen=True, slots=True)
class JavaScriptReorderResult:
    """Outcome of reordering one JavaScript source file.

    Attributes:
        metrics: Aggregated reorder metrics.
        source: Reordered source text.

    """

    metrics: JavaScriptReorderMetrics
    source: str

    @property
    def changed(self) -> bool:
        """Return whether at least one method moved.

        Returns:
            Whether any method changed position.

        """
        return self.metrics.methods_moved > 0


class JavaScriptClassMethodReorderer:
    """Reorder safe JavaScript class-method runs without regenerating code."""

    def __init__(self, *, path: Path) -> None:
        """Initialize a file-backed JavaScript reorderer.

        Args:
            path: JavaScript source file.

        """
        self.path: Path = path

    def measure(self) -> JavaScriptReorderResult:
        """Return reordered source and metrics without writing the file.

        Returns:
            Reordered source text with aggregated metrics.

        """
        return self._reorder(path=self.path)

    def reorder(self) -> str:
        """Return reordered source without writing the file.

        Returns:
            Reordered JavaScript source.

        """
        return self.measure().source

    def write(self) -> bool:
        """Reorder the file in place and return whether it changed.

        Returns:
            Whether the file content changed.

        """
        result: JavaScriptReorderResult = self.measure()
        if not result.changed:
            return False
        _bytes_written: int = self.path.write_text(
            data=result.source,
            encoding="utf-8",
        )
        return True

    @classmethod
    def _reorder(cls, *, path: Path) -> JavaScriptReorderResult:
        """Run the bundled JavaScript organizer for one source file.

        Args:
            path: JavaScript source file to reorder.

        Returns:
            Reordered source text with aggregated metrics.

        Raises:
            RuntimeError: If the organizer exits with a failure status.
            TypeError: If the organizer emits malformed JSON or an
                incomplete payload.

        """
        node: str = cls._executable(name="node")
        with as_file(
            resource_files("exactus.packages.organize")
            / "js"
            / "class_organizer.js",
        ) as script:
            completed: CompletedProcess[str] = cls._run(
                arguments=[node, str(object=script)],
                cwd=path.parent,
                stdin=dumps(
                    obj={
                        "action": "organize",
                        "espree": cls._resolve_espree(path=path),
                        "file": str(object=path),
                    },
                ),
            )
        if completed.returncode != 0:
            msg: str = (
                completed.stderr.strip() or "JavaScript organization failed."
            )
            raise RuntimeError(msg)
        try:
            payload: JsonValue = cast(
                typ="JsonValue",
                val=loads(s=completed.stdout),
            )
        except JSONDecodeError as error:
            msg = "JavaScript organizer returned invalid JSON."
            raise TypeError(msg) from error
        return cls._result(payload=payload)

    @classmethod
    def _resolve_espree(cls, *, path: Path) -> str:
        """Resolve Espree from the project, ESLint, or global npm modules.

        Args:
            path: JavaScript source file whose project anchors the
                module lookup.

        Returns:
            Absolute path of the resolved Espree module.

        Raises:
            RuntimeError: If ``node`` is missing or Espree cannot be
                resolved from any probe.

        """
        node: str = cls._executable(name="node")
        probes: list[list[str]] = [
            [node, "-e", Constants.resolve_local, str(object=path.resolve())],
        ]
        eslint: str | None = which(cmd="eslint")
        if eslint is not None:
            probes.append([node, "-e", Constants.resolve_eslint, eslint])
        arguments: list[str]
        for arguments in probes:
            completed: CompletedProcess[str] = cls._run(
                arguments=arguments,
                cwd=path.parent,
            )
            if completed.returncode == 0 and completed.stdout.strip():
                return completed.stdout.strip()
        npm: str | None = which(cmd="npm")
        if npm is not None:
            completed = cls._run(
                arguments=[npm, "root", "-g"],
                cwd=path.parent,
            )
            candidate: Path = (
                Path(completed.stdout.strip())
                / "espree"
                / "dist"
                / "espree.cjs"
            )
            if completed.returncode == 0 and candidate.is_file():
                return str(object=candidate)
        msg: str = (
            "Espree could not be resolved. Install espree or ESLint "
            "in the JavaScript project, or make a global Espree "
            "installation available."
        )
        raise RuntimeError(msg)

    @classmethod
    def _result(cls, *, payload: JsonValue) -> JavaScriptReorderResult:
        """Validate organizer JSON and construct its typed result.

        Args:
            payload: Decoded organizer output.

        Returns:
            Typed reorder result.

        Raises:
            TypeError: If the payload is not an object or lacks the
                ``source`` text and ``metrics`` mapping.

        """
        if not isinstance(payload, dict):
            msg: str = "JavaScript organizer output must be an object."
            raise TypeError(msg)
        source: JsonValue = payload.get("source")
        metrics: JsonValue = payload.get("metrics")
        if not isinstance(source, str) or not isinstance(metrics, dict):
            msg = "JavaScript organizer output is incomplete."
            raise TypeError(msg)
        return JavaScriptReorderResult(
            metrics=JavaScriptReorderMetrics(
                classes_reordered=cls._integer(
                    payload=metrics,
                    key="classes_reordered",
                ),
                classes_seen=cls._integer(payload=metrics, key="classes_seen"),
                lines_moved=cls._integer(payload=metrics, key="lines_moved"),
                methods_moved=cls._integer(
                    payload=metrics,
                    key="methods_moved",
                ),
                methods_seen=cls._integer(payload=metrics, key="methods_seen"),
            ),
            source=source,
        )

    @staticmethod
    def _executable(*, name: str) -> str:
        """Resolve a required executable to an absolute path.

        Args:
            name: Executable name resolved through ``PATH``.

        Returns:
            Absolute executable path.

        Raises:
            RuntimeError: If the executable is not on ``PATH``.

        """
        executable: str | None = which(cmd=name)
        if executable is not None:
            return executable
        msg: str = f"{name} is required to organize JavaScript."
        raise RuntimeError(msg)

    @staticmethod
    def _run(
        *,
        arguments: list[str],
        cwd: Path,
        stdin: str | None = None,
    ) -> CompletedProcess[str]:
        """Run one trusted organizer support command.

        Args:
            arguments: Command line executed without a shell.
            cwd: Working directory for the process.
            stdin: Optional text piped to the process's standard input.

        Returns:
            Completed process carrying captured output.

        """
        process: Popen = Popen(
            args=arguments,
            cwd=cwd,
            stdin=PIPE if stdin is not None else None,
            stdout=PIPE,
            stderr=PIPE,
            text=True,
        )
        output: str
        error: str
        output, error = process.communicate(input=stdin)
        return CompletedProcess(
            args=arguments,
            returncode=process.returncode or 0,
            stdout=output,
            stderr=error,
        )

    @staticmethod
    def _integer(*, payload: dict[str, JsonValue], key: str) -> int:
        """Read one integer metric from a JSON object.

        Args:
            payload: Decoded metrics mapping.
            key: Metric name to read.

        Returns:
            The integer metric value.

        Raises:
            TypeError: If the metric is absent or not an integer.

        """
        value: JsonValue = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            msg: str = (
                f"JavaScript organizer metric {key!r} must be an integer."
            )
            raise TypeError(msg)
        return value
