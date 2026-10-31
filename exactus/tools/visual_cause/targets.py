"""Normalize and validate configured visual-cause targets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol, cast

from exactus.tools.common.config import ConfigFile, discovery_from_environment

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


class TargetOptions(Protocol):
    """Typed options consumed while resolving targets.

    Attributes:
        root: Project root used to resolve relative paths.
        target: Named configured targets requested on the CLI.
        url: Ad-hoc page URL for the A side.
        html: Ad-hoc local HTML file for the A side.
        landing: Landing document name inside ``html`` folders.
        url_b: Ad-hoc page URL for the B side.
        html_b: Ad-hoc local HTML file for the B side.
        landing_b: Landing document name for the B page.
        css_a: Stylesheet applied to the A side.
        css_b: Stylesheet applied to the B side.
        viewport: ``WIDTHxHEIGHT`` strings for ad-hoc rendering.
        accept: Findings kinds accepted without failing the run.
        warning: Findings kinds reported as warnings.
        fail: Findings kinds that fail the run.
        default_level: Verdict level used when none is configured.
        fail_on: Failure threshold for the tool run.
        threshold: Pixel difference threshold in 0..255.
        max_candidates: Most causal candidates explored per target.
        parallel_workers: Worker processes rendering comparisons.
        timeout_ms: Per-render timeout in milliseconds.
        screenshot_scale: Device-pixel ratio applied to screenshots.
        native_styles_a: Whether the A side keeps native styles.
        native_styles_b: Whether the B side keeps native styles.

    """

    root: Path
    target: list[str]
    url: str | None
    html: Path | None
    landing: str
    url_b: str | None
    html_b: Path | None
    landing_b: str
    css_a: Path | None
    css_b: Path | None
    viewport: list[str]
    accept: list[str]
    warning: list[str]
    fail: list[str]
    default_level: str
    fail_on: str
    threshold: int
    max_candidates: int
    parallel_workers: int
    timeout_ms: int
    screenshot_scale: float
    native_styles_a: bool
    native_styles_b: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceValues:
    """Normalized A/B page and stylesheet sources.

    Attributes:
        url: Page URL for the A side.
        html: Local HTML document for the A side.
        url_b: Page URL for the B side.
        html_b: Local HTML document for the B side.
        css_a: Stylesheet applied to the A side.
        css_b: Stylesheet applied to the B side.

    """

    url: str | None
    html: Path | None
    url_b: str | None
    html_b: Path | None
    css_a: Path | None
    css_b: Path | None


class Constants:
    """Store closed target limits.

    Attributes:
        viewport_parts: Dimension count in one ``WIDTHxHEIGHT`` string.
        max_threshold: Largest accepted pixel difference threshold.

    """

    viewport_parts: Final[int] = 2
    max_threshold: Final[int] = 255


@dataclass(frozen=True, slots=True, kw_only=True)
class Viewport:
    """One CSS-pixel viewport.

    Attributes:
        width: Horizontal extent in CSS pixels.
        height: Vertical extent in CSS pixels.

    """

    width: int
    height: int

    @classmethod
    def parse(cls, *, value: str) -> Viewport:
        """Parse ``WIDTHxHEIGHT`` and reject non-positive dimensions.

        Args:
            value: Viewport string such as ``1440x900``.

        Returns:
            Parsed viewport.

        Raises:
            ValueError: If the shape is not ``WIDTHxHEIGHT`` or a
                dimension is not positive.

        """
        parts: list[str] = value.lower().split(sep="x")
        if len(parts) != Constants.viewport_parts or not all(
            part.isdecimal() for part in parts
        ):
            msg: str = f"Invalid viewport {value!r}; expected WIDTHxHEIGHT."
            raise ValueError(msg)
        width, height = (int(part) for part in parts)
        if width < 1 or height < 1:
            msg = f"Invalid viewport {value!r}; dimensions must be positive."
            raise ValueError(msg)
        return cls(width=width, height=height)

    @property
    def label(self) -> str:
        """Return the stable viewport label.

        Returns:
            ``WIDTHxHEIGHT`` label used in artifact names.

        """
        return f"{self.width}x{self.height}"


@dataclass(frozen=True, slots=True, kw_only=True)
class Target:
    """One validated page comparison across one or more viewports.

    Attributes:
        name: Stable target identifier.
        url: Page URL for the A side.
        html: Local HTML document for the A side.
        landing: Landing document name inside ``html`` folders.
        url_b: Page URL for the B side.
        html_b: Local HTML document for the B side.
        landing_b: Landing document name for the B page.
        css_a: Stylesheet applied to the A side.
        css_b: Stylesheet applied to the B side.
        viewports: Viewports rendered for this target.
        accept: Findings kinds accepted without failing the run.
        warning: Findings kinds reported as warnings.
        fail: Findings kinds that fail the run.
        default_level: Verdict level used when none is configured.
        fail_on: Failure threshold for the tool run.
        threshold: Pixel difference threshold in 0..255.
        max_candidates: Most causal candidates explored per target.
        parallel_workers: Worker processes rendering comparisons.
        timeout_ms: Per-render timeout in milliseconds.
        screenshot_scale: Device-pixel ratio applied to screenshots.
        native_styles_a: Whether the A side keeps native styles.
        native_styles_b: Whether the B side keeps native styles.

    """

    name: str
    url: str | None
    html: Path | None
    landing: str
    url_b: str | None
    html_b: Path | None
    landing_b: str
    css_a: Path | None
    css_b: Path | None
    viewports: tuple[Viewport, ...]
    accept: tuple[str, ...]
    warning: tuple[str, ...]
    fail: tuple[str, ...]
    default_level: str
    fail_on: str
    threshold: int
    max_candidates: int
    parallel_workers: int
    timeout_ms: int
    screenshot_scale: float
    native_styles_a: bool
    native_styles_b: bool

    @property
    def mode(self) -> str:
        """Return the normalized comparison mode.

        Returns:
            ``page`` for two-page diffs, ``stylesheets`` for A/B CSS on
            one page, or ``overlay`` for the single-side comparison.

        """
        if self.url_b is not None or self.html_b is not None:
            return "page"
        return "stylesheets" if self.css_a is not None else "overlay"


def _path(*, value: JsonValue | None, base: Path) -> Path | None:
    """Resolve one configured path against its declaring directory.

    Args:
        value: Raw configured value.
        base: Directory relative paths resolve against.

    Returns:
        Absolute path, or ``None`` when ``value`` is ``None``.

    Raises:
        ValueError: If the value is not a nonempty string.

    """
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        msg: str = f"Expected a nonempty path, got {value!r}."
        raise ValueError(msg)
    candidate: Path = Path(value)
    return (
        candidate if candidate.is_absolute() else (base / candidate).resolve()
    )


def _strings(*, value: JsonValue | None) -> tuple[str, ...]:
    """Coerce a configured list into a string tuple.

    Args:
        value: Raw configured value.

    Returns:
        Strings as a tuple, empty when ``value`` is ``None``.

    Raises:
        ValueError: If the value is not a list of strings.

    """
    if value is None:
        return ()
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        msg: str = f"Expected a list of strings, got {value!r}."
        raise ValueError(msg)
    return tuple(cast(typ="list[str]", val=value))


def configured(*, start: Path) -> tuple[dict[str, JsonValue], ...]:
    """Load named target tables with nearest-file name overrides.

    Args:
        start: Directory the config-file discovery starts from.

    Returns:
        Target tables keyed by name, each carrying ``__base__``.

    Raises:
        TypeError: If a configured entry is not a named table.

    """
    files: tuple[ConfigFile, ...] = discovery_from_environment(start=start)
    selected: dict[str, dict[str, JsonValue]] = {}
    for item in reversed(files):
        tool: JsonValue | None = item.table.get("visual_cause")
        if not isinstance(tool, dict):
            continue
        entries: JsonValue | None = tool.get("targets")
        if not isinstance(entries, list):
            continue
        for raw in entries:
            if not isinstance(raw, dict):
                msg: str = (
                    f"{item.path}: each visual_cause target needs a name."
                )
                raise TypeError(msg)
            target_name: JsonValue | None = raw.get("name")
            if not isinstance(target_name, str):
                msg = f"{item.path}: each visual_cause target needs a name."
                raise TypeError(msg)
            value: dict[str, JsonValue] = dict(raw)
            value["__base__"] = str(object=item.path.parent)
            selected[target_name] = value
    return tuple(selected.values())


def _source_values(
    *,
    raw: dict[str, JsonValue],
    base: Path,
    name: str,
) -> SourceValues:
    """Parse and validate mutually exclusive source fields.

    Args:
        raw: Raw configured target table.
        base: Directory relative paths resolve against.
        name: Target name used in error messages.

    Returns:
        Normalized A/B sources.

    Raises:
        TypeError: If a URL field is not text.
        ValueError: If the source combination is contradictory or
            incomplete.

    """
    url_value: JsonValue | None = raw.get("url")
    url_b_value: JsonValue | None = raw.get("url-b", raw.get("url_b"))
    if url_value is not None and not isinstance(url_value, str):
        msg: str = f"Target {name!r}: url must be text."
        raise TypeError(msg)
    if url_b_value is not None and not isinstance(url_b_value, str):
        msg = f"Target {name!r}: url-b must be text."
        raise TypeError(msg)
    values: SourceValues = SourceValues(
        url=url_value,
        html=_path(value=raw.get("html"), base=base),
        url_b=url_b_value,
        html_b=_path(value=raw.get("html-b", raw.get("html_b")), base=base),
        css_a=_path(value=raw.get("css-a", raw.get("css_a")), base=base),
        css_b=_path(value=raw.get("css-b", raw.get("css_b")), base=base),
    )
    has_b_page: bool = values.url_b is not None or values.html_b is not None
    message: str | None = (
        f"Target {name!r}: provide exactly one of url or html."
        if (values.url is None) == (values.html is None)
        else f"Target {name!r}: url-b and html-b conflict."
        if values.url_b is not None and values.html_b is not None
        else f"Target {name!r}: a B page cannot use CSS sides."
        if has_b_page
        and (values.css_a is not None or values.css_b is not None)
        else f"Target {name!r}: provide a B page or css-b."
        if not has_b_page and values.css_b is None
        else None
    )
    if message is not None:
        raise ValueError(message)
    return values


def _integer(*, value: JsonValue | None, fallback: int, label: str) -> int:
    """Return one integer option without accepting booleans.

    Args:
        value: Raw configured value.
        fallback: Default when ``value`` is ``None``.
        label: Option name used in error messages.

    Returns:
        Configured or fallback integer.

    Raises:
        TypeError: If the value is not an integer.

    """
    selected: JsonValue = fallback if value is None else value
    if isinstance(selected, bool) or not isinstance(selected, int):
        msg: str = f"{label} must be an integer."
        raise TypeError(msg)
    return selected


def _decimal(*, value: JsonValue | None, fallback: float, label: str) -> float:
    """Return one numeric option without accepting booleans.

    Args:
        value: Raw configured value.
        fallback: Default when ``value`` is ``None``.
        label: Option name used in error messages.

    Returns:
        Configured or fallback value as a float.

    Raises:
        TypeError: If the value is not numeric.

    """
    selected: JsonValue = fallback if value is None else value
    if isinstance(selected, bool) or not isinstance(selected, int | float):
        msg: str = f"{label} must be numeric."
        raise TypeError(msg)
    return float(selected)


def _boolean(*, value: JsonValue | None, fallback: bool, label: str) -> bool:
    """Return one boolean option.

    Args:
        value: Raw configured value.
        fallback: Default when ``value`` is ``None``.
        label: Option name used in error messages.

    Returns:
        Configured or fallback boolean.

    Raises:
        TypeError: If the value is not a boolean.

    """
    selected: JsonValue = fallback if value is None else value
    if not isinstance(selected, bool):
        msg: str = f"{label} must be true or false."
        raise TypeError(msg)
    return selected


def _validate_target(*, target: Target) -> Target:
    """Validate closed target settings and return the same target.

    Args:
        target: Constructed target to validate.

    Returns:
        The same target when every closed setting is valid.

    Raises:
        ValueError: If a level, threshold or numeric limit is invalid.

    """
    message: str | None = (
        f"Target {target.name!r}: invalid default-level."
        if target.default_level not in {"accept", "warning", "fail"}
        else f"Target {target.name!r}: invalid fail-on."
        if target.fail_on not in {"findings", "pixels", "never"}
        else f"Target {target.name!r}: threshold must be 0..255."
        if not 0 <= target.threshold <= Constants.max_threshold
        else f"Target {target.name!r}: numeric limits must be positive."
        if min(
            target.max_candidates,
            target.parallel_workers,
            target.timeout_ms,
        )
        < 1
        else f"Target {target.name!r}: screenshot-scale must be positive."
        if target.screenshot_scale <= 0.0
        else None
    )
    if message is not None:
        raise ValueError(message)
    return target


def _target(*, raw: dict[str, JsonValue], options: TargetOptions) -> Target:
    """Build one validated target from a raw configured table.

    Args:
        raw: Raw configured target table carrying ``__base__``.
        options: CLI options supplying fallback values.

    Returns:
        Validated target.

    Raises:
        ValueError: If the name or a nested source field is invalid.

    """
    base: Path = Path(str(object=raw.get("__base__", options.root))).resolve()
    name_value: JsonValue | None = raw.get("name", "adhoc")
    if not isinstance(name_value, str) or not name_value.strip():
        msg: str = "Target name must be nonempty."
        raise ValueError(msg)
    sources: SourceValues = _source_values(raw=raw, base=base, name=name_value)
    viewport_values: tuple[str, ...] = _strings(value=raw.get("viewports"))
    viewports: tuple[Viewport, ...] = tuple(
        Viewport.parse(value=value) for value in viewport_values
    ) or (Viewport(width=1440, height=900),)
    default_level: str = str(
        object=raw.get(
            "default-level",
            raw.get("default_level", options.default_level),
        ),
    )
    fail_on: str = str(
        object=raw.get("fail-on", raw.get("fail_on", options.fail_on)),
    )
    return _validate_target(
        target=Target(
            name=name_value,
            url=sources.url,
            html=sources.html,
            landing=str(object=raw.get("landing", "index.html")),
            url_b=sources.url_b,
            html_b=sources.html_b,
            landing_b=str(
                object=raw.get(
                    "landing-b",
                    raw.get("landing_b", "index.html"),
                ),
            ),
            css_a=sources.css_a,
            css_b=sources.css_b,
            viewports=viewports,
            accept=(
                *_strings(value=raw.get("accept")),
                *tuple(options.accept),
            ),
            warning=(
                *_strings(value=raw.get("warning")),
                *tuple(options.warning),
            ),
            fail=(*_strings(value=raw.get("fail")), *tuple(options.fail)),
            default_level=default_level,
            fail_on=fail_on,
            threshold=_integer(
                value=raw.get("threshold"),
                fallback=options.threshold,
                label="threshold",
            ),
            max_candidates=_integer(
                value=raw.get("max-candidates", raw.get("max_candidates")),
                fallback=options.max_candidates,
                label="max-candidates",
            ),
            parallel_workers=_integer(
                value=raw.get("parallel-workers", raw.get("parallel_workers")),
                fallback=options.parallel_workers,
                label="parallel-workers",
            ),
            timeout_ms=_integer(
                value=raw.get("timeout-ms", raw.get("timeout_ms")),
                fallback=options.timeout_ms,
                label="timeout-ms",
            ),
            screenshot_scale=_decimal(
                value=raw.get("screenshot-scale", raw.get("screenshot_scale")),
                fallback=options.screenshot_scale,
                label="screenshot-scale",
            ),
            native_styles_a=_boolean(
                value=raw.get("native-styles-a", raw.get("native_styles_a")),
                fallback=options.native_styles_a,
                label="native-styles-a",
            ),
            native_styles_b=_boolean(
                value=raw.get("native-styles-b", raw.get("native_styles_b")),
                fallback=options.native_styles_b,
                label="native-styles-b",
            ),
        ),
    )


def resolve(*, options: TargetOptions) -> tuple[Target, ...]:
    """Resolve ad-hoc or named configured targets.

    Args:
        options: CLI options selecting the source mode.

    Returns:
        Validated targets in resolution order.

    Raises:
        ValueError: If ad-hoc flags mix with names, a name is unknown,
            or no source was provided.

    """
    ad_hoc: bool = any(
        value is not None
        for value in (
            options.url,
            options.html,
            options.url_b,
            options.html_b,
            options.css_a,
            options.css_b,
        )
    )
    if ad_hoc and options.target:
        msg: str = "Use --target separately from ad-hoc source flags."
        raise ValueError(msg)
    if ad_hoc:
        raw: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val={
                "name": "adhoc",
                "url": options.url,
                "html": (
                    None if options.html is None else str(object=options.html)
                ),
                "landing": options.landing,
                "url-b": options.url_b,
                "html-b": (
                    None
                    if options.html_b is None
                    else str(object=options.html_b)
                ),
                "landing-b": options.landing_b,
                "css-a": (
                    None
                    if options.css_a is None
                    else str(object=options.css_a)
                ),
                "css-b": (
                    None
                    if options.css_b is None
                    else str(object=options.css_b)
                ),
                "viewports": list(options.viewport),
                "__base__": str(object=Path(options.root).resolve()),
            },
        )
        return (_target(raw=raw, options=options),)
    entries: tuple[dict[str, JsonValue], ...] = configured(
        start=Path(options.root),
    )
    if options.target:
        requested: set[str] = set(options.target)
        known: set[str] = {str(object=item.get("name")) for item in entries}
        if missing := sorted(requested - known):
            msg = "Unknown visual-cause target(s): " + ", ".join(missing)
            raise ValueError(msg)
        entries = tuple(
            item for item in entries if item.get("name") in requested
        )
    if not entries:
        msg = "Provide a target with --url/--html or configure one."
        raise ValueError(msg)
    return tuple(_target(raw=item, options=options) for item in entries)
