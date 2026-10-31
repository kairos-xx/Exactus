# Copyright (c) 2026 João Lopes.
"""Report JavaScript function and method blocks and modernization eligibility.

The analyzer parses JavaScript with Espree through Node.js. It reports every
function-like block with its source range, containing class when applicable,
current static/arrow state, whether an instance method can become static, and
whether a callable can safely use arrow notation under conservative semantic
checks.

Espree is resolved from the target JavaScript project's Node resolution path,
from a nearby ESLint installation, or from the global npm module directory.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from importlib.resources import as_file
from importlib.resources import files as resource_files
from json import JSONDecodeError, dumps, loads
from pathlib import Path
from shutil import which
from subprocess import PIPE, CompletedProcess
from typing import Literal, cast

from psutil import Popen, cpu_count

from exactus.packages.steps import trace
from exactus.tools.common.runtime import LaneProgress

type BlockKind = Literal[
    "arrow_function",
    "class_field",
    "function_declaration",
    "function_expression",
    "method",
    "object_method",
]
type ArrowDirection = Literal["from_arrow", "to_arrow"]
type JsonScalar = str | int | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True, slots=True)
class FunctionBlock:
    """Describe FunctionBlock.

    Attributes:
    name: Public value used by this data structure.
    kind: Public value used by this data structure.
    class_name: Public value used by this data structure.
    method_kind: Public value used by this data structure.
    line_start: Public value used by this data structure.
    column_start: Public value used by this data structure.
    line_end: Public value used by this data structure.
    column_end: Public value used by this data structure.
    static_current: Public value used by this data structure.
    static_eligible: Public value used by this data structure.
    arrow_current: Public value used by this data structure.
    arrow_eligible: Public value used by this data structure.
    uses_this_or_super: Public value used by this data structure.
    uses_arguments: Public value used by this data structure.
    uses_new_target: Public value used by this data structure.
    is_async: Public value used by this data structure.
    arrow_blockers: Public value used by this data structure.
    recommendation: Public value used by this data structure.
    source: Public value used by this data structure.

    """

    name: str
    kind: BlockKind
    class_name: str | None
    method_kind: str | None
    line_start: int
    column_start: int
    line_end: int
    column_end: int
    static_current: bool
    static_eligible: bool
    arrow_current: bool
    arrow_eligible: bool
    uses_this_or_super: bool
    uses_arguments: bool
    uses_new_target: bool
    is_async: bool
    arrow_blockers: tuple[str, ...]
    recommendation: str
    source: str


@dataclass(frozen=True, slots=True)
class ConversionResult:
    """Describe ConversionResult.

    Attributes:
    source: Public value used by this data structure.
    changed: Public value used by this data structure.
    transformations: Public value used by this data structure.

    """

    source: str
    changed: bool
    transformations: int


class JavaScriptBlockAnalyzer:
    """Parse and classify function-like blocks in one JavaScript file."""

    def __init__(self, *, path: Path, espree: str | None = None) -> None:
        """Init  .

        Args:
            path: Path.
            espree: Espree.

        Raises:
            FileNotFoundError: Raised when the operation cannot be completed.
            ValueError: Raised when the operation cannot be completed.

        """
        self.path: Path = path.expanduser().resolve()
        if not self.path.is_file():
            msg: str = f"JavaScript file does not exist: {self.path}"
            raise FileNotFoundError(msg)
        if self.path.suffix.lower() not in {".js", ".mjs", ".cjs", ".jsx"}:
            msg = f"Expected a JavaScript file, received: {self.path}"
            raise ValueError(msg)
        self._espree: str | None = espree

    def resolve_espree(self) -> str:
        """Resolve espree.

        Returns:
            The resulting value.

        """
        if self._espree is None:
            self._espree = self._probe_espree()
        return self._espree

    def analyze(self) -> tuple[FunctionBlock, ...]:
        """Analyze.

        Returns:
            The resulting value.

        Raises:
            RuntimeError: Raised when the operation cannot be completed.
            TypeError: Raised when the operation cannot be completed.
            ValueError: Raised when the operation cannot be completed.

        """
        with as_file(
            resource_files("exactus.packages.organize")
            / "js"
            / "class_organizer.js",
        ) as script:
            completed: CompletedProcess[str] = self._run_analyzer(
                args=["node", str(object=script)],
                input_data=dumps(
                    obj={
                        "action": "analyze",
                        "espree": self.resolve_espree(),
                        "file": str(object=self.path),
                    },
                ),
            )
        if completed.returncode != 0:
            msg: str = completed.stderr.strip() or "JavaScript parsing failed."
            raise RuntimeError(msg)
        try:
            payload: JsonValue = cast(
                typ="JsonValue",
                val=loads(s=completed.stdout),
            )
        except JSONDecodeError as error:
            msg = "Analyzer returned invalid JSON."
            raise ValueError(msg) from error
        if not isinstance(payload, list):
            msg = "Analyzer output must be a JSON array."
            raise TypeError(msg)
        return tuple(map(self._raw_block, payload))

    def convert(
        self,
        *,
        direction: ArrowDirection | None = None,
    ) -> ConversionResult:
        """Convert.

        Args:
            direction: Direction.

        Returns:
            The resulting value.

        Raises:
            RuntimeError: Raised when the operation cannot be completed.
            TypeError: Raised when the operation cannot be completed.
            ValueError: Raised when the operation cannot be completed.

        """
        with as_file(
            resource_files("exactus.packages.organize")
            / "js"
            / "class_organizer.js",
        ) as script:
            completed: CompletedProcess[str] = self._run_analyzer(
                args=["node", str(object=script)],
                input_data=dumps(
                    obj={
                        "action": "convert",
                        "direction": direction or "normalize",
                        "espree": self.resolve_espree(),
                        "file": str(object=self.path),
                    },
                ),
            )
        if completed.returncode != 0:
            msg: str = (
                completed.stderr.strip() or "JavaScript conversion failed."
            )
            raise RuntimeError(msg)
        try:
            payload: JsonValue = cast(
                typ="JsonValue",
                val=loads(s=completed.stdout),
            )
        except JSONDecodeError as error:
            msg = "Analyzer returned invalid JSON."
            raise ValueError(msg) from error
        if not isinstance(payload, dict):
            msg = "Conversion output must be a JSON object."
            raise TypeError(msg)
        item: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=payload,
        )
        return ConversionResult(
            source=self._string(item=item, key="source"),
            changed=self._boolean(item=item, key="changed"),
            transformations=self._integer(item=item, key="transformations"),
        )

    def normalize(self) -> ConversionResult:
        """Normalize.

        Returns:
            The resulting value.

        """
        return self.convert()

    def to_arrow(self) -> ConversionResult:
        """To arrow.

        Returns:
            The resulting value.

        """
        return self.convert(direction="to_arrow")

    def from_arrow(self) -> ConversionResult:
        """From arrow.

        Returns:
            The resulting value.

        """
        return self.convert(direction="from_arrow")

    @classmethod
    def _strings(
        cls,
        *,
        item: dict[str, JsonValue],
        key: str,
    ) -> tuple[str, ...]:
        """Strings.

        Args:
            item: Item.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            ValueError: Raised when the operation cannot be completed.

        """
        if isinstance((value := item.get(key)), list) and all(
            map(cls._is_string, value),
        ):
            return tuple(cast(typ="list[str]", val=value))
        msg: str = f"Analyzer returned invalid string-list field: {key}"
        raise ValueError(msg)

    @classmethod
    def _block(cls, *, item: dict[str, JsonValue]) -> FunctionBlock:
        """Block.

        Args:
            item: Item.

        Returns:
            The resulting value.

        Raises:
            ValueError: Raised when the operation cannot be completed.

        """
        kind_text: str = cls._string(item=item, key="kind")
        valid_kinds: tuple[BlockKind, ...] = (
            "arrow_function",
            "class_field",
            "function_declaration",
            "function_expression",
            "method",
            "object_method",
        )
        if "" + kind_text not in valid_kinds:
            msg: str = f"Analyzer returned invalid block kind: {kind_text}"
            raise ValueError(msg)
        kind: BlockKind = cast(typ="BlockKind", val=kind_text)
        return FunctionBlock(
            name=cls._string(item=item, key="name"),
            kind=kind,
            class_name=cls._optional_string(item=item, key="class_name"),
            method_kind=cls._optional_string(item=item, key="method_kind"),
            line_start=cls._integer(item=item, key="line_start"),
            column_start=cls._integer(item=item, key="column_start"),
            line_end=cls._integer(item=item, key="line_end"),
            column_end=cls._integer(item=item, key="column_end"),
            static_current=cls._boolean(item=item, key="static_current"),
            static_eligible=cls._boolean(item=item, key="static_eligible"),
            arrow_current=cls._boolean(item=item, key="arrow_current"),
            arrow_eligible=cls._boolean(item=item, key="arrow_eligible"),
            uses_this_or_super=cls._boolean(
                item=item,
                key="uses_this_or_super",
            ),
            uses_arguments=cls._boolean(item=item, key="uses_arguments"),
            uses_new_target=cls._boolean(item=item, key="uses_new_target"),
            is_async=cls._boolean(item=item, key="async"),
            arrow_blockers=cls._strings(item=item, key="arrow_blockers"),
            recommendation=cls._string(item=item, key="recommendation"),
            source=cls._string(item=item, key="source"),
        )

    @classmethod
    def _raw_block(cls, value: JsonValue, /) -> FunctionBlock:
        """Raw block.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            TypeError: Raised when the operation cannot be completed.

        """
        if not isinstance(value, dict):
            msg: str = "Analyzer returned a non-object block."
            raise TypeError(msg)
        return cls._block(item=value)

    @staticmethod
    def _run_command(*, args: list[str], cwd: Path) -> CompletedProcess[str]:
        """Run command.

        Args:
            args: Args.
            cwd: Cwd.

        Returns:
            The resulting value.

        """
        process: Popen = Popen(
            args=args,
            cwd=cwd,
            stdout=PIPE,
            stderr=PIPE,
            text=True,
        )
        stdout: str
        stderr: str
        stdout, stderr = process.communicate()
        return CompletedProcess(
            args=args,
            returncode=process.returncode or 0,
            stdout=stdout,
            stderr=stderr,
        )

    @staticmethod
    def _run_analyzer(
        *,
        args: list[str],
        input_data: str,
    ) -> CompletedProcess[str]:
        """Run analyzer.

        Args:
            args: Args.
            input_data: Input data.

        Returns:
            The resulting value.

        Raises:
            RuntimeError: Raised when the operation cannot be completed.

        """
        node: str | None = which(cmd=args[0])
        if node is None:
            msg: str = "Node.js is required to parse JavaScript."
            raise RuntimeError(msg)
        process: Popen = Popen(
            args=[node, *args[1:]],
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            text=True,
        )
        stdout: str
        stderr: str
        stdout, stderr = process.communicate(input=input_data)
        return CompletedProcess(
            args=args,
            returncode=process.returncode or 0,
            stdout=stdout,
            stderr=stderr,
        )

    @staticmethod
    def _string(*, item: dict[str, JsonValue], key: str) -> str:
        """Extract a string field.

        Args:
            item: Item.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            ValueError: Raised when the operation cannot be completed.

        """
        if isinstance((value := item.get(key)), str):
            return value
        msg: str = f"Analyzer returned invalid string field: {key}"
        raise ValueError(msg)

    @staticmethod
    def _optional_string(
        *,
        item: dict[str, JsonValue],
        key: str,
    ) -> str | None:
        """Extract an optional string field.

        Args:
            item: Item.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            ValueError: Raised when the operation cannot be completed.

        """
        if (value := item.get(key)) is None or isinstance(value, str):
            return value
        msg: str = f"Analyzer returned invalid optional string field: {key}"
        raise ValueError(msg)

    @staticmethod
    def _integer(*, item: dict[str, JsonValue], key: str) -> int:
        """Integer.

        Args:
            item: Item.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            ValueError: Raised when the operation cannot be completed.

        """
        if isinstance((value := item.get(key)), int) and (
            not isinstance(value, bool)
        ):
            return value
        msg: str = f"Analyzer returned invalid integer field: {key}"
        raise ValueError(msg)

    @staticmethod
    def _boolean(*, item: dict[str, JsonValue], key: str) -> bool:
        """Boolean.

        Args:
            item: Item.
            key: Key.

        Returns:
            The resulting value.

        Raises:
            ValueError: Raised when the operation cannot be completed.

        """
        if isinstance((value := item.get(key)), bool):
            return value
        msg: str = f"Analyzer returned invalid boolean field: {key}"
        raise ValueError(msg)

    @staticmethod
    def _is_string(value: JsonValue, /) -> bool:
        """Is string.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return isinstance(value, str)

    def _probe_espree(self) -> str:
        """Probe espree.

        Returns:
            The resulting value.

        Raises:
            RuntimeError: Raised when the operation cannot be completed.

        """
        if which(cmd="node") is None:
            msg: str = "Node.js is required to parse JavaScript."
            raise RuntimeError(msg)
        local: CompletedProcess[str] = self._run_command(
            args=[
                "node",
                "-e",
                (
                    "const{createRequire}=require('node:module');const "
                    "r=createRequire(process.argv[1]);process.stdout.write(r.r"
                    "esolve('espree'));"
                ),
                str(object=self.path),
            ],
            cwd=self.path.parent,
        )
        if local.returncode == 0 and local.stdout.strip():
            return local.stdout.strip()
        if (eslint := which(cmd="eslint")) is not None:
            bundled: CompletedProcess[str] = self._run_command(
                args=[
                    "node",
                    "-e",
                    (
                        "const{createRequire}=require('node:module');const{rea"
                        "lpathSync}=require('node:fs');const "
                        "r=createRequire(realpathSync(process.argv[1]));proces"
                        "s.stdout.write(r.resolve('espree'));"
                    ),
                    eslint,
                ],
                cwd=self.path.parent,
            )
            if bundled.returncode == 0 and bundled.stdout.strip():
                return bundled.stdout.strip()
        if which(cmd="npm") is not None:
            npm_root: CompletedProcess[str] = self._run_command(
                args=["npm", "root", "-g"],
                cwd=self.path.parent,
            )
            if npm_root.returncode == 0 and npm_root.stdout.strip():
                candidate: Path = (
                    Path(npm_root.stdout.strip())
                    / "espree"
                    / "dist"
                    / "espree.cjs"
                )
                if candidate.is_file():
                    return str(object=candidate)
        msg = (
            "Espree could not be resolved. Install espree or ESLint in "
            "the JavaScript project, or make a global Espree "
            "installation available to Node.js."
        )
        raise RuntimeError(msg)


@dataclass(frozen=True, slots=True)
class FunctionBlocksFinding:
    """Describe FunctionBlocksFinding.

    Attributes:
    rule: Public value used by this data structure.
    file: Public value used by this data structure.
    line: Public value used by this data structure.
    column: Public value used by this data structure.
    message: Public value used by this data structure.
    severity: Public value used by this data structure.

    """

    rule: str
    file: str
    line: int
    column: int
    message: str
    severity: str = "warning"


@dataclass(frozen=True, slots=True)
class FunctionBlocksHeal:
    """Describe FunctionBlocksHeal.

    Attributes:
    rule: Public value used by this data structure.
    file: Public value used by this data structure.
    action: Public value used by this data structure.
    transformations: Public value used by this data structure.

    """

    rule: str
    file: str
    action: str
    transformations: int


@dataclass(frozen=True, slots=True)
class FunctionBlocksInput:
    """Describe FunctionBlocksInput.

    Attributes:
    root: Public value used by this data structure.
    files: Public value used by this data structure.
    fix: Public value used by this data structure.

    """

    root: Path
    files: tuple[Path, ...]
    fix: bool


@dataclass(frozen=True, slots=True)
class FunctionBlocksResult:
    """Describe FunctionBlocksResult.

    Attributes:
    files: Public value used by this data structure.
    findings: Public value used by this data structure.
    healed: Public value used by this data structure.

    """

    files: int
    findings: tuple[FunctionBlocksFinding, ...]
    healed: tuple[FunctionBlocksHeal, ...]


def _line_column(*, source: str, offset: int) -> tuple[int, int]:
    """Line column.

    Args:
        source: Source.
        offset: Offset.

    Returns:
        The resulting value.

    """
    line: int = source.count("\n", 0, offset) + 1
    line_start: int = source.rfind("\n", 0, offset)
    return (line, offset - line_start)


def _first_change_offset(*, before: str, after: str) -> int:
    """First change offset.

    Args:
        before: Before.
        after: After.

    Returns:
        The resulting value.

    """
    offset: int = 0
    limit: int = min(len(before), len(after))
    while offset < limit and before[offset] == after[offset]:
        offset += 1
    return offset


def _audit_function_blocks(
    path: Path,
    *,
    root: Path,
    fix: bool,
    espree: str | None,
) -> FunctionBlocksFinding | FunctionBlocksHeal | None:
    """Audit function blocks.

    Args:
        path: Path.
        root: Root.
        fix: Fix.
        espree: Espree.

    Returns:
        The resulting value.

    """

    def error(*, rule: str, message: str) -> FunctionBlocksFinding:
        """Error.

        Args:
            rule: Rule.
            message: Message.

        Returns:
            The resulting value.

        """
        return FunctionBlocksFinding(
            rule=rule,
            file=relative,
            line=0,
            column=0,
            message=message,
            severity="error",
        )

    try:
        relative: str = path.relative_to(root).as_posix()
    except ValueError:
        relative = path.as_posix()
    try:
        original: str = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return error(
            rule="JSN002",
            message="JavaScript file could not be read.",
        )
    try:
        analyzer: JavaScriptBlockAnalyzer = JavaScriptBlockAnalyzer(
            path=path,
            espree=espree,
        )
        result: ConversionResult = analyzer.normalize()
    except (OSError, UnicodeDecodeError):
        return error(
            rule="JSN002",
            message="JavaScript file could not be read.",
        )
    except (RuntimeError, ValueError, TypeError) as exception:
        return error(
            rule="JSN003",
            message=f"Function-block analysis failed: {exception}",
        )
    outcome: FunctionBlocksFinding | FunctionBlocksHeal | None = None
    if result.changed:
        if fix:
            if result.source != original:
                try:
                    path.write_text(data=result.source, encoding="utf-8")
                except OSError:
                    return error(
                        rule="JSN003",
                        message=(
                            "Function-block repair refused: the file "
                            "could not be rewritten."
                        ),
                    )
                outcome = FunctionBlocksHeal(
                    rule="JSN001",
                    file=relative,
                    action="normalize",
                    transformations=result.transformations,
                )
        else:
            line, column = _line_column(
                source=original,
                offset=_first_change_offset(
                    before=original,
                    after=result.source,
                ),
            )
            outcome = FunctionBlocksFinding(
                rule="JSN001",
                file=relative,
                line=line,
                column=column,
                message=(
                    f"{result.transformations} function block(s) can "
                    "be modernized."
                ),
            )
    return outcome


def scan_function_blocks(
    *,
    inputs: FunctionBlocksInput,
    progress_span: tuple[float, float] = (0.0, 1.0),
) -> FunctionBlocksResult:
    """Scan function blocks.

    Args:
        inputs: Inputs.
        progress_span: Overall progress slice used when embedded in lints.

    Returns:
        The resulting value.

    """
    espree: str | None = None
    if inputs.files:
        try:
            probe: JavaScriptBlockAnalyzer = JavaScriptBlockAnalyzer(
                path=inputs.files[0],
            )
            espree = probe.resolve_espree()
        except (RuntimeError, FileNotFoundError, ValueError) as error:
            trace(
                step=f"notation: espree resolution failed — {error}",
                depth=3,
            )
            return FunctionBlocksResult(
                files=0,
                findings=(
                    FunctionBlocksFinding(
                        rule="JSN003",
                        file=".",
                        line=0,
                        column=0,
                        message=f"Function-block scan skipped: {error}",
                        severity="error",
                    ),
                ),
                healed=(),
            )
    workers: int = max(1, min(16, cpu_count() or 4, len(inputs.files)))
    audit: partial[FunctionBlocksFinding | FunctionBlocksHeal | None] = (
        partial(
            _audit_function_blocks,
            root=inputs.root,
            fix=inputs.fix,
            espree=espree,
        )
    )
    lanes: LaneProgress = LaneProgress(
        total=len(inputs.files),
        step="JavaScript function blocks",
        span=progress_span,
    )

    def tracked(
        path: Path,
    ) -> FunctionBlocksFinding | FunctionBlocksHeal | None:
        """Audit one file while publishing its thread activity.

        Args:
            path: JavaScript file assigned to this thread.

        Returns:
            Finding, heal record, or ``None``.

        """
        label: str = str(object=path)
        lanes.begin(item=label)
        try:
            outcome: FunctionBlocksFinding | FunctionBlocksHeal | None = audit(
                path,
            )
        except Exception as error:
            _ = lanes.finish(item=label, error=str(object=error))
            raise
        _ = lanes.finish(
            item=label,
            error=(
                outcome.message
                if isinstance(outcome, FunctionBlocksFinding)
                and outcome.severity == "error"
                else None
            ),
        )
        trace(
            step=(
                f"notation: {label} — "
                + (
                    f"finding: {outcome.message}"
                    if isinstance(outcome, FunctionBlocksFinding)
                    else (
                        f"healed: {outcome.action}"
                        if isinstance(outcome, FunctionBlocksHeal)
                        else "ok"
                    )
                )
            ),
            depth=4,
        )
        return outcome

    pool: ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes: tuple[
            FunctionBlocksFinding | FunctionBlocksHeal | None,
            ...,
        ] = tuple(pool.map(tracked, inputs.files))
    return FunctionBlocksResult(
        files=len(inputs.files),
        findings=tuple(
            outcome
            for outcome in outcomes
            if isinstance(outcome, FunctionBlocksFinding)
        ),
        healed=tuple(
            outcome
            for outcome in outcomes
            if isinstance(outcome, FunctionBlocksHeal)
        ),
    )
