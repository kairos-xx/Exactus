# Copyright (c) 2026 João Lopes.
"""Resolve performance settings from defaults, pyproject, and overrides."""

from dataclasses import dataclass
from pathlib import Path
from tomllib import load
from typing import Final, Self, TypedDict, Unpack, cast, final


@final
class Constants:
    """Group module-level constants.

    Attributes:
        default_sources: Grouped module constant.
        default_output: Grouped module constant.

    """

    default_sources: Final[tuple[str, ...]] = (".",)
    default_output: Final[str] = "performance"


type ConfigValue = bool | float | int | str | list[str]
type ConfigTable = dict[str, ConfigValue]


class PerformanceConfigOverrides(TypedDict, total=False):
    """Explicit overrides accepted by ``PerformanceConfig.load``.

    Attributes:
        sources: Explicit source expressions replacing configured sources.
        output: Explicit dashboard output directory.
        serve: Explicit server behavior.
        open_browser: Explicit managed-browser behavior.
        chrome: Explicit Chrome or Chromium executable.
        gap_threshold: Explicit silent-gap threshold in seconds.
        repetition_threshold: Explicit repeated-event threshold.
        server_timeout: Explicit server readiness timeout in seconds.

    """

    sources: tuple[str, ...] | None
    output: Path | None
    serve: bool | None
    open_browser: bool | None
    chrome: Path | None
    gap_threshold: float | None
    repetition_threshold: int | None
    server_timeout: float | None


@dataclass(frozen=True, slots=True)
class PerformanceConfig:
    """Store resolved performance analyzer settings.

    Attributes:
        project: Project root containing ``pyproject.toml``.
        sources: Files, directories, or glob expressions to inspect.
        output: Directory receiving the exported dashboard.
        serve: Whether to serve the exported dashboard.
        open: Whether to open the dashboard in the managed browser.
        chrome: Optional Chrome or Chromium executable override.
        gap_threshold: Minimum silent interval reported as a bottleneck.
        repetition_threshold: Minimum repeated events reported as a hotspot.
        server_timeout: Maximum seconds to wait for server readiness.

    """

    project: Path
    sources: tuple[str, ...]
    output: Path
    serve: bool
    open: bool
    chrome: Path | None
    gap_threshold: float
    repetition_threshold: int
    server_timeout: float

    @classmethod
    def load(
        cls,
        *,
        project: Path | None = None,
        **overrides: Unpack[PerformanceConfigOverrides],
    ) -> Self:
        """Resolve settings with explicit values taking highest precedence.

        Args:
            project: Explicit project root or a path below it.
            overrides: Explicit per-setting override values.

        Returns:
            Fully resolved immutable configuration.

        """
        root: Path = cls._project_root(start=project or Path.cwd())
        table: ConfigTable = cls._table(project=root)
        configured_sources: tuple[str, ...] = cls._strings(
            value=table.get("sources"),
            default=Constants.default_sources,
        )
        resolved_sources: tuple[str, ...] = (
            overrides.get("sources") or configured_sources
        )
        configured_output: str = cls._string(
            value=table.get("output"),
            default=Constants.default_output,
        )
        configured_chrome: str | None = cls._optional_string(
            value=table.get("chrome"),
        )
        serve: bool | None = overrides.get("serve")
        open_browser: bool | None = overrides.get("open_browser")
        chrome: Path | None = overrides.get("chrome")
        gap_threshold: float | None = overrides.get("gap_threshold")
        repetition_threshold: int | None = overrides.get(
            "repetition_threshold",
        )
        server_timeout: float | None = overrides.get("server_timeout")
        resolved: Self = cls(
            project=root,
            sources=resolved_sources,
            output=cls._path(
                project=root,
                value=overrides.get("output") or Path(configured_output),
            ),
            serve=serve
            if serve is not None
            else cls._boolean(value=table.get("serve"), default=True),
            open=open_browser
            if open_browser is not None
            else cls._boolean(value=table.get("open"), default=True),
            chrome=chrome
            if chrome is not None
            else cls._path(project=root, value=Path(configured_chrome))
            if configured_chrome is not None
            else None,
            gap_threshold=gap_threshold
            if gap_threshold is not None
            else cls._number(value=table.get("gap-threshold"), default=0.25),
            repetition_threshold=repetition_threshold
            if repetition_threshold is not None
            else cls._integer(
                value=table.get("repetition-threshold"),
                default=10,
            ),
            server_timeout=server_timeout
            if server_timeout is not None
            else cls._number(value=table.get("server-timeout"), default=10.0),
        )
        resolved.validate()
        return resolved

    def paths(self) -> tuple[Path, ...]:
        """Expand configured source expressions relative to the project.

        Returns:
            Deterministically ordered source paths and glob matches.

        """
        found: dict[str, Path] = {}
        for source in self.sources:
            candidate: Path = Path(source)
            if not candidate.is_absolute():
                candidate = self.project / candidate
            if any(token in source for token in ("*", "?", "[")):
                for match in self.project.glob(pattern=source):
                    found[str(object=match.resolve())] = match.resolve()
            else:
                found[str(object=candidate.resolve())] = candidate.resolve()
        return tuple(found[key] for key in sorted(found))

    def validate(self) -> None:
        """Validate resolved settings.

        Raises:
            ValueError: When a resolved setting is outside its valid range.

        """
        msg: str
        if self.gap_threshold < 0.0:
            msg = "Performance gap threshold cannot be negative."
            raise ValueError(msg)
        if self.repetition_threshold < 1:
            msg = "Performance repetition threshold must be positive."
            raise ValueError(msg)
        if self.server_timeout <= 0.0:
            msg = "Performance server timeout must be positive."
            raise ValueError(msg)

    @staticmethod
    def _project_root(*, start: Path) -> Path:
        """Find the nearest project root.

        Args:
            start: Candidate project path or child path.

        Returns:
            Nearest directory containing ``pyproject.toml``, or the starting
            directory when no project file exists.

        """
        current: Path = start.resolve()
        if current.is_file():
            current = current.parent
        for candidate in (current, *current.parents):
            if (candidate / "pyproject.toml").is_file():
                return candidate
        return current

    @staticmethod
    def _table(*, project: Path) -> ConfigTable:
        """Read ``tool.performance`` from the project configuration.

        Args:
            project: Resolved project root.

        Returns:
            Performance configuration table, or an empty table.

        """
        path: Path = project / "pyproject.toml"
        if not path.is_file():
            return {}
        with path.open(mode="rb") as stream:
            document: dict[str, ConfigValue | dict[str, ConfigValue]] = cast(
                typ="dict[str, ConfigValue | dict[str, ConfigValue]]",
                val=load(stream),
            )
        tool: ConfigValue | dict[str, ConfigValue] | None = document.get(
            "tool",
        )
        if not isinstance(tool, dict):
            return {}
        performance: ConfigValue | None = tool.get("performance")
        return performance if isinstance(performance, dict) else {}

    @staticmethod
    def _path(*, project: Path, value: Path) -> Path:
        """Resolve one path against the project.

        Args:
            project: Project root.
            value: Absolute or project-relative path.

        Returns:
            Absolute normalized path.

        """
        return (value if value.is_absolute() else project / value).resolve()

    @staticmethod
    def _boolean(*, value: ConfigValue | None, default: bool) -> bool:
        """Read a boolean configuration value.

        Args:
            value: Raw value.
            default: Fallback value.

        Returns:
            Resolved boolean.

        Raises:
            ValueError: When the configured value is not boolean.

        """
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        msg: str = "Performance boolean setting must be true or false."
        raise ValueError(msg)

    @staticmethod
    def _integer(*, value: ConfigValue | None, default: int) -> int:
        """Read an integer configuration value.

        Args:
            value: Raw value.
            default: Fallback value.

        Returns:
            Resolved integer.

        Raises:
            ValueError: When the configured value is not an integer.

        """
        if value is None:
            return default
        if isinstance(value, int) and (not isinstance(value, bool)):
            return value
        msg: str = "Performance integer setting must be an integer."
        raise ValueError(msg)

    @staticmethod
    def _number(*, value: ConfigValue | None, default: float) -> float:
        """Read a numeric configuration value.

        Args:
            value: Raw value.
            default: Fallback value.

        Returns:
            Resolved floating-point value.

        Raises:
            ValueError: When the configured value is not numeric.

        """
        if value is None:
            return default
        if isinstance(value, (int, float)) and (not isinstance(value, bool)):
            return float(value)
        msg: str = "Performance numeric setting must be numeric."
        raise ValueError(msg)

    @staticmethod
    def _string(*, value: ConfigValue | None, default: str) -> str:
        """Read a string configuration value.

        Args:
            value: Raw value.
            default: Fallback value.

        Returns:
            Resolved string.

        Raises:
            ValueError: When the configured value is not a string.

        """
        if value is None:
            return default
        if isinstance(value, str):
            return value
        msg: str = "Performance string setting must be a string."
        raise ValueError(msg)

    @staticmethod
    def _optional_string(*, value: ConfigValue | None) -> str | None:
        """Read an optional string configuration value.

        Args:
            value: Raw value.

        Returns:
            String value or ``None``.

        Raises:
            ValueError: When the configured value is not a string.

        """
        if value is None or isinstance(value, str):
            return value
        msg: str = "Performance optional setting must be a string."
        raise ValueError(msg)

    @staticmethod
    def _strings(
        *,
        value: ConfigValue | None,
        default: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Read a list-of-strings configuration value.

        Args:
            value: Raw value.
            default: Fallback sequence.

        Returns:
            Resolved immutable string sequence.

        Raises:
            ValueError: When the configured value is not a string list.

        """
        if value is None:
            return default
        if isinstance(value, list) and all(
            isinstance(item, str)
            for item in cast(typ="list[object]", val=value)
        ):
            return tuple(value)
        msg: str = "Performance sources must be an array of strings."
        raise ValueError(msg)
