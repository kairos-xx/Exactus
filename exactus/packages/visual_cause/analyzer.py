# Copyright (c) 2026
"""Find CSS rules that causally change a page's rendered pixels."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.resources import files as resource_files
from io import BytesIO
from json import dumps, loads
from pathlib import Path
from shutil import which
from sys import stdout
from time import monotonic
from typing import TYPE_CHECKING, Final, Literal, Protocol, cast, final
from urllib.parse import SplitResult, urlsplit

from PIL import Image, ImageChops, ImageDraw
from playwright.sync_api import (
    Browser,
    BrowserContext,
    CDPSession,
    Error,
    Page,
    sync_playwright,
)

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.visual_cause.causal import (
    CausalMinimizer,
    CauseSet,
    CssValueParser,
    LayoutEvidence,
    ValueNode,
)

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from importlib.resources.abc import Traversable
type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]


@final
class Constants:
    """Group module-level constants.

    Attributes:
        default_width: Grouped module constant.
        default_height: Grouped module constant.
        default_threshold: Grouped module constant.
        default_max_candidates: Grouped module constant.
        max_threshold: Grouped module constant.
        max_relation_elements: Grouped module constant.
        min_region_pixels: Grouped module constant.
        geometry_delta_epsilon: Grouped module constant.

    """

    default_width: Final[int] = 1440
    default_height: Final[int] = 900
    default_threshold: Final[int] = 12
    default_max_candidates: Final[int] = 80
    max_threshold: Final[int] = 255
    max_relation_elements: Final[int] = 8
    min_region_pixels: Final[int] = 2
    geometry_delta_epsilon: Final[float] = 0.005


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration.

    Attributes:
    url: Stored url value.
    css_a: Stored css a value.
    css_b: Stored css b value.
    output: Stored output value.
    width: Stored width value.
    height: Stored height value.
    threshold: Stored threshold value.
    max_candidates: Stored max candidates value.
    timeout_ms: Stored timeout ms value.
    url_b: Stored url b value.
    use_native_styles_a: Stored use native styles a value.
    use_native_styles_b: Stored use native styles b value.
    parallel_workers: Stored parallel workers value.
    recycle_after: Stored recycle after value.
    analysis_budget_seconds: Maximum wall-clock budget for causal expansion.
    screenshot_scale: Device-pixel density used for saved screenshot evidence.
    advanced_analysis: Whether to run higher-order causal analysis phases.
    extended_selectors: Whether to install the packaged extended-selector
        engine when it exists on disk; ``False`` restricts selector queries
        to native ``querySelectorAll``.

    """

    url: str
    css_a: Path | str | None
    css_b: Path | str | None
    output: Path
    width: int
    height: int
    threshold: int
    max_candidates: int
    timeout_ms: int
    url_b: str | None = None
    use_native_styles_a: bool = False
    use_native_styles_b: bool = False
    parallel_workers: int = 4
    recycle_after: int = 24
    analysis_budget_seconds: float = 45.0
    screenshot_scale: float = 2.0
    advanced_analysis: bool = True
    extended_selectors: bool = True


@dataclass(frozen=True, slots=True)
class CssTarget:
    """Normalized CSS comparison target.

    Attributes:
    source: Stored source value.
    files: Stored files value.
    css: Stored css value.

    """

    source: Path | None
    files: tuple[Path, ...]
    css: str

    @classmethod
    def load(cls, source: Path | str | None) -> CssTarget:
        """Load one CSS file or recursively combine a directory of CSS files.

        Args:
        source: Value for source.

        Returns:
        Result produced by load.

        Raises:
        FileNotFoundError: If the operation cannot be completed.
        ValueError: If the operation cannot be completed.

        """
        if source is None:
            return cls(source=None, files=(), css="")
        path: Path = Path(source).expanduser().resolve()
        if path.is_file():
            if path.suffix.lower() != ".css":
                msg: str = f"CSS target file must end in .css: {path}"
                raise ValueError(msg)
            files: tuple[Path, ...] = (path,)
        elif path.is_dir():
            files = tuple(
                sorted(
                    (
                        candidate
                        for candidate in path.rglob(pattern="*")
                        if candidate.is_file()
                        and candidate.suffix.lower() == ".css"
                    ),
                    key=lambda candidate: candidate.relative_to(
                        path,
                    ).as_posix(),
                ),
            )
            if not files:
                msg = f"CSS target directory contains no .css files: {path}"
                raise FileNotFoundError(msg)
        else:
            msg = f"CSS target does not exist: {path}"
            raise FileNotFoundError(msg)
        chunks: list[str] = []
        for css_file in files:
            relative: str = (
                css_file.name
                if path.is_file()
                else css_file.relative_to(path).as_posix()
            )
            chunks.append(
                f"/* css-visual-cause source: {relative} */\n"
                f"{css_file.read_text(encoding='utf-8')}",
            )
        return cls(source=path, files=files, css="\n\n".join(chunks))

    def manifest(self) -> dict[str, JsonValue]:
        """Return report metadata for this target.

        Returns:
        Result produced by manifest.

        """
        return {
            "source": None if self.source is None else str(object=self.source),
            "kind": "native"
            if self.source is None
            else "file"
            if self.source.is_file()
            else "directory",
            "files": [str(object=path) for path in self.files],
            "file_count": len(self.files),
        }


@dataclass(frozen=True, slots=True)
class Rect:
    """Document-space rectangle.

    Attributes:
    x: Stored x value.
    y: Stored y value.
    width: Stored width value.
    height: Stored height value.

    """

    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        """Return the right edge.

        Returns:
        Result produced by right.

        """
        return self.x + self.width

    @property
    def bottom(self) -> float:
        """Return the bottom edge.

        Returns:
        Result produced by bottom.

        """
        return self.y + self.height

    @property
    def area(self) -> float:
        """Return the rectangle area.

        Returns:
            Area in square CSS pixels.

        """
        return self.width * self.height

    def intersection_area(self, other: Rect) -> float:
        """Return the area shared with another rectangle.

        Args:
            other: Rectangle to compare against.

        Returns:
            Shared area in square CSS pixels.

        """
        horizontal: float = max(
            0.0,
            min(self.right, other.right) - max(self.x, other.x),
        )
        vertical: float = max(
            0.0,
            min(self.bottom, other.bottom) - max(self.y, other.y),
        )
        return horizontal * vertical

    def intersects(self, other: Rect) -> bool:
        """Return whether two rectangles overlap.

        Args:
        other: Value for other.

        Returns:
        Result produced by intersects.

        """
        return (
            self.x < other.right
            and self.right > other.x
            and (self.y < other.bottom)
            and (self.bottom > other.y)
        )


@dataclass(frozen=True, slots=True)
class ElementInfo:
    """DOM element relevant to a visual change.

    Attributes:
    selector: Stored selector value.
    dom_path: Stored dom path value.
    parent_path: Stored parent path value.
    tag: Stored tag value.
    text: Stored text value.
    own_text: Stored own text value.
    rect: Stored rect value.
    position: Stored position value.
    z_index: Stored z index value.
    computed: Stored computed value.
    typed_computed: Stored typed computed value.
    before_content: Stored before content value.
    after_content: Stored after content value.
    child_count: Stored child count value.
    scroll_width: Stored scroll width value.
    scroll_height: Stored scroll height value.
    client_width: Stored client width value.
    client_height: Stored client height value.
    overflow_x: Stored overflow x value.
    overflow_y: Stored overflow y value.

    """

    selector: str
    dom_path: str
    parent_path: str
    tag: str
    text: str
    own_text: str
    rect: Rect
    position: str
    z_index: str
    computed: dict[str, str]
    typed_computed: dict[str, JsonValue]
    before_content: str
    after_content: str
    child_count: int
    scroll_width: float
    scroll_height: float
    client_width: float
    client_height: float
    overflow_x: str
    overflow_y: str


@dataclass(frozen=True, slots=True)
class StyleChange:
    """One computed-style before/after change.

    Attributes:
    a: Stored a value.
    b: Stored b value.

    """

    a: str
    b: str


@dataclass(frozen=True, slots=True)
class ChangeNode:
    """One changed DOM element before tree serialization.

    Attributes:
    selector: Stored selector value.
    categories: Stored categories value.
    origins: Stored origins value.
    mechanisms: Stored mechanisms value.
    geometry: Stored geometry value.
    computed_style_changes: Stored computed style changes value.
    changed_pixels: Stored changed pixels value.

    """

    selector: str
    categories: tuple[str, ...]
    origins: tuple[str, ...]
    mechanisms: tuple[str, ...]
    geometry: dict[str, dict[str, float]]
    computed_style_changes: dict[str, dict[str, StyleChange]]
    changed_pixels: int


@dataclass(frozen=True, slots=True)
class RuleInfo:
    """Browser-parsed CSS style rule.

    Attributes:
    index: Stored index value.
    selector: Stored selector value.
    css_text: Stored css text value.
    declarations: Stored declarations value.
    matched: Stored matched value.

    """

    index: int
    selector: str
    css_text: str
    declarations: tuple[str, ...]
    matched: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Cause:
    """Counterfactual evidence for one CSS rule.

    Attributes:
    index: Stored index value.
    selector: Stored selector value.
    css_text: Stored css text value.
    declarations: Stored declarations value.
    matched: Stored matched value.
    relations: Stored relations value.
    changed_pixels_without_rule: Stored changed pixels without rule value.
    pixels_explained: Stored pixels explained value.
    explanation_ratio: Stored explanation ratio value.

    """

    index: int
    selector: str
    css_text: str
    declarations: tuple[str, ...]
    matched: tuple[str, ...]
    relations: tuple[str, ...]
    changed_pixels_without_rule: int
    pixels_explained: int
    explanation_ratio: float


class InvalidBrowserPayloadError(TypeError):
    """Raised when browser JSON does not match the expected schema."""


class JsonPage(Protocol):
    """Typed boundary for JavaScript evaluation."""

    def evaluate(self, expression: str, arg: str | None = None) -> str:
        """Evaluate JavaScript and return serialized JSON.

        Args:
        expression: Value for expression.
        arg: Value for arg.

        Returns:
        Result produced by evaluate.

        """
        ...


class CdpSender(Protocol):
    """Typed boundary for Chrome DevTools Protocol commands."""

    def __call__(
        self,
        method: str,
        params: dict[str, JsonValue] | None = None,
    ) -> dict[str, JsonValue]:
        """Send one CDP command and return its result dictionary.

        Args:
        method: CDP method name.
        params: Optional command parameters.

        Returns:
        Result produced by the CDP command.

        """
        ...


class ProgressObserver(Protocol):
    """Receive bounded analyzer progress updates."""

    def __call__(self, phase: str, completed: int, total: int) -> None:
        """Receive one progress update.

        Args:
            phase: Analyzer phase being reported.
            completed: Work items finished so far.
            total: Work items expected for the phase.

        """


type RenderSide = Literal["a", "b"]


@dataclass(frozen=True, slots=True)
class Intervention:
    """Counterfactual render interventions applied to one page.

    Attributes:
    disabled_rule: Flattened rule index to disable, when any.
    element_override: Element selector plus computed-style overrides.
    disabled_declarations: Rule-index/property pairs to disable.

    """

    disabled_rule: int | None = None
    element_override: tuple[str, dict[str, str]] | None = None
    disabled_declarations: tuple[tuple[int, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ProvenanceMaps:
    """Per-selector causal provenance produced by the analysis phases.

    Attributes:
    causal_edges: Element-to-element causal edge evidence.
    declaration_provenance: Declaration-level counterfactual evidence.
    function_provenance: CSS value-fragment counterfactual evidence.
    cascade_provenance: Chromium cascade/matched-style provenance.
    interaction_provenance: Non-additive declaration-combination evidence.
    minimal_sets: Minimal causal declaration sets.

    """

    causal_edges: dict[str, list[dict[str, JsonValue]]]
    declaration_provenance: dict[str, list[dict[str, JsonValue]]]
    function_provenance: dict[str, list[dict[str, JsonValue]]]
    cascade_provenance: dict[str, JsonValue]
    interaction_provenance: dict[str, list[dict[str, JsonValue]]]
    minimal_sets: dict[str, list[dict[str, JsonValue]]]


@dataclass(frozen=True, slots=True)
class AnalysisResults:
    """Complete analyzer output bundle used for report generation.

    Attributes:
    baseline: Baseline changed-pixel count.
    regions: Connected visual-difference rectangles.
    affected: Rendered elements intersecting visual changes.
    nodes: Classified changed DOM nodes.
    causes: Rules proven causal by whole-rule ablation.
    elements_a: Side-A element snapshots.
    rules_b: Side-B flattened CSS rules.
    evidence_image_a: High-resolution side-A screenshot.
    evidence_image_b: High-resolution side-B screenshot.
    analysis_image_a: CSS-pixel side-A screenshot.
    analysis_image_b: CSS-pixel side-B screenshot.
    provenance: Causal provenance maps by selector.

    """

    baseline: int
    regions: tuple[Rect, ...]
    affected: tuple[ElementInfo, ...]
    nodes: tuple[ChangeNode, ...]
    causes: tuple[Cause, ...]
    elements_a: tuple[ElementInfo, ...]
    rules_b: tuple[RuleInfo, ...]
    evidence_image_a: Image.Image
    evidence_image_b: Image.Image
    analysis_image_a: Image.Image
    analysis_image_b: Image.Image
    provenance: ProvenanceMaps


@dataclass(slots=True)
class ReportState:
    """Mutable per-report caches used while writing report.md.

    Attributes:
    evidence: Evidence output directory.
    crop_cache: Saved crop paths by element selector.
    nodes_by_selector: Changed nodes keyed by generated selector.
    elements_b: Side-B element snapshots keyed by selector.

    """

    evidence: Path
    crop_cache: dict[str, tuple[str, str, str]]
    nodes_by_selector: dict[str, ChangeNode]
    elements_b: dict[str, ElementInfo]


@dataclass(frozen=True, slots=True)
class ProvenanceTrial:
    """Per-node counterfactual context for provenance experiments.

    Attributes:
    browser: Browser used for counterfactual renders.
    reference: Side-A element snapshot used as reference.
    baseline: Reference-to-B distance that improvements are measured against.

    """

    browser: Browser
    reference: ElementInfo
    baseline: float


@dataclass(frozen=True, slots=True)
class DeclarationContext:
    """Shared lookups for declaration-level counterfactual trials.

    Attributes:
    selectors: Changed-element selectors to evaluate per trial.
    a_by_selector: Side-A element snapshots keyed by selector.
    b_by_selector: Side-B element snapshots keyed by selector.
    causes_by_index: Proven causal rules keyed by flattened index.

    """

    selectors: tuple[str, ...]
    a_by_selector: dict[str, ElementInfo]
    b_by_selector: dict[str, ElementInfo]
    causes_by_index: dict[int, Cause]


def browser_script(*, name: str) -> str:
    """Return one packaged browser script's source text.

    Resolved through ``importlib.resources`` so browser programs keep
    working when the package executes from a pyz archive, where
    ``Path(__file__)`` does not address real files.

    Args:
        name: Script filename inside ``js/`` of the
            ``exactus.packages.visual_cause`` package.

    Returns:
        JavaScript source text.

    """
    return (
        resource_files("exactus.packages.visual_cause")
        .joinpath("js", name)
        .read_text(encoding="utf-8")
    )


def _script(*, name: str) -> str:
    """Return one packaged browser script's source text.

    Args:
        name: Script filename inside ``js/`` of the
            ``exactus.packages.visual_cause`` package.

    Returns:
        JavaScript source text.

    """
    return browser_script(name=name)


def _extended_selector_source() -> str | None:
    """Return the packaged ExtendedSelector engine as a page program.

    The engine ships as an ES module; replacing its two ``export``
    statements lets it run inside a plain ``page.evaluate`` program and
    publish the constructor as ``window.ExtendedSelector``.

    Returns:
        Browser program source, or ``None`` when the packaged
        ``extended_selector`` package is not on disk.

    """
    try:
        candidate: Traversable = resource_files(
            "exactus.packages.extended_selector",
        ).joinpath("editor", "extended-selector.js")
    except ModuleNotFoundError:
        return None
    try:
        if not candidate.is_file():
            return None
        source: str = candidate.read_text(encoding="utf-8")
    except OSError:
        return None
    body: str = source.replace(
        "export class ExtendedSelector",
        "class ExtendedSelector",
    ).replace(
        "export default ExtendedSelector;",
        "window.ExtendedSelector = ExtendedSelector;",
    )
    return "() => {\n" + body + '\n  return "ok";\n};\n'


class CssVisualCause:
    """Compare two stylesheets and experimentally identify visual causes."""

    _STYLE_GROUPS: Final[dict[str, frozenset[str]]] = {
        "layout": frozenset(
            {
                "display",
                "position",
                "top",
                "right",
                "bottom",
                "left",
                "float",
                "clear",
                "overflow",
                "overflow-x",
                "overflow-y",
                "grid-template-columns",
                "grid-template-rows",
                "grid-column",
                "grid-row",
                "grid-auto-flow",
                "gap",
                "row-gap",
                "column-gap",
                "align-content",
                "align-items",
                "align-self",
                "justify-content",
                "justify-items",
                "justify-self",
                "flex",
                "flex-basis",
                "flex-direction",
                "flex-grow",
                "flex-shrink",
                "flex-wrap",
                "order",
            },
        ),
        "box_model": frozenset(
            {
                "width",
                "height",
                "min-width",
                "min-height",
                "max-width",
                "max-height",
                "margin-top",
                "margin-right",
                "margin-bottom",
                "margin-left",
                "padding-top",
                "padding-right",
                "padding-bottom",
                "padding-left",
                "box-sizing",
                "border-top-width",
                "border-right-width",
                "border-bottom-width",
                "border-left-width",
                "border-top-left-radius",
                "border-top-right-radius",
                "border-bottom-right-radius",
                "border-bottom-left-radius",
            },
        ),
        "typography": frozenset(
            {
                "font-family",
                "font-size",
                "font-style",
                "font-weight",
                "font-stretch",
                "line-height",
                "letter-spacing",
                "word-spacing",
                "text-align",
                "text-indent",
                "text-transform",
                "white-space",
                "word-break",
                "overflow-wrap",
                "text-overflow",
            },
        ),
        "transform": frozenset(
            {
                "transform",
                "transform-origin",
                "transform-style",
                "perspective",
                "perspective-origin",
                "translate",
                "rotate",
                "scale",
            },
        ),
        "visibility": frozenset(
            {
                "visibility",
                "opacity",
                "clip",
                "clip-path",
                "content-visibility",
            },
        ),
        "stacking": frozenset({"z-index", "isolation", "mix-blend-mode"}),
        "paint": frozenset(
            {
                "background",
                "background-image",
                "background-position",
                "background-size",
                "box-shadow",
                "text-shadow",
                "outline",
                "filter",
                "backdrop-filter",
            },
        ),
    }
    _COLOR_NAMES: Final[frozenset[str]] = frozenset(
        {
            "color",
            "background-color",
            "border-top-color",
            "border-right-color",
            "border-bottom-color",
            "border-left-color",
            "outline-color",
            "text-decoration-color",
            "column-rule-color",
            "caret-color",
            "fill",
            "stroke",
            "flood-color",
            "lighting-color",
            "stop-color",
        },
    )
    _PREPARE_JS: Final[str] = _script(name="prepare.js")
    _CONTAINER_RULES_JS: Final[str] = _script(name="container_rules.js")
    _CSS_VARIABLES_JS: Final[str] = _script(name="css_variables.js")
    _RULES_JS: Final[str] = _script(name="rules.js")
    _INSTALL_HELPERS_JS: Final[str] = _script(name="install_helpers.js")
    _DISABLE_DECLARATIONS_JS: Final[str] = _script(
        name="disable_declarations.js",
    )
    _DISABLE_DECLARATION_JS: Final[str] = _script(
        name="disable_declaration.js",
    )
    _OVERRIDE_ELEMENT_JS: Final[str] = _script(name="override_element.js")
    _ELEMENTS_JS: Final[str] = _script(name="elements.js")
    _DISABLE_RULE_JS: Final[str] = _script(name="disable_rule.js")
    _EXTENDED_SELECTOR_JS: Final[str | None] = _extended_selector_source()
    _NEXT_FRAME_JS: Final[str] = (
        "() => new Promise((resolve) => requestAnimationFrame(resolve))"
    )
    _SETTLE_FRAME_JS: Final[str] = (
        "() => new Promise((resolve) => requestAnimationFrame("
        "() => requestAnimationFrame(resolve)))"
    )

    def __init__(
        self,
        settings: Settings,
        progress: ProgressObserver | None = None,
    ) -> None:
        """Initialize the analyzer.

        Args:
        settings: Value for settings.
        progress: Optional observer receiving analyzer phase updates.

        """
        self.settings: Settings = settings
        self._observer: ProgressObserver | None = progress
        self.target_a: CssTarget = CssTarget.load(source=settings.css_a)
        self.target_b: CssTarget = CssTarget.load(source=settings.css_b)
        self.css_a: str = self.target_a.css
        self.css_b: str = self.target_b.css
        self._last_elements_b: tuple[ElementInfo, ...] = ()
        self._last_container_queries: list[JsonValue] = []
        self._last_variable_graph: dict[str, list[dict[str, JsonValue]]] = {}
        self._deadline: float | None = None
        self._highres_a: Image.Image | None = None
        self._highres_b: Image.Image | None = None
        settings.output.mkdir(parents=True, exist_ok=True)

    def run(self) -> AnalysisResults:
        """Run analysis and return the result used to write the artifacts.

        Returns:
            Analysis results also written to the output directory.

        """
        self._deadline = monotonic() + self.settings.analysis_budget_seconds
        self._progress(phase="starting", completed=0, total=1)
        try:
            return self._run_analysis()
        except Exception as error:
            self._write_failure(error=error)
            raise

    @classmethod
    def _disable_rule(cls, page: Page, rule_index: int) -> None:
        """Disable a flattened CSS style rule by clearing its declarations.

        Args:
        page: Value for page.
        rule_index: Value for rule index.

        """
        page.evaluate(expression=cls._DISABLE_RULE_JS, arg=rule_index)

    @classmethod
    def _style_group(cls, name: str) -> str:
        """Classify a computed CSS property by rendering concern.

        Args:
        name: Value for name.

        Returns:
        Result produced by  style group.

        """
        if name in cls._COLOR_NAMES or "color" in name:
            return "color"
        for group, properties in cls._STYLE_GROUPS.items():
            if name in properties:
                return group
        return "other"

    @classmethod
    def _strongest_root_cause(
        cls,
        singles: list[dict[str, JsonValue]],
        interactions: list[dict[str, JsonValue]],
        fallback: list[dict[str, JsonValue]],
    ) -> JsonValue:
        """Choose the strongest single or synergistic root-cause explanation.

        Args:
        singles: Value for singles.
        interactions: Value for interactions.
        fallback: Value for fallback.

        Returns:
        Result produced by  strongest root cause.

        """
        single: dict[str, JsonValue] | None = singles[0] if singles else None
        interaction: dict[str, JsonValue] | None = (
            interactions[0] if interactions else None
        )
        single_confidence: float = (
            cls._json_float(value=single.get("confidence", 0.0))
            if single is not None
            else 0.0
        )
        interaction_confidence: float = (
            cls._json_float(value=interaction.get("confidence", 0.0))
            if interaction is not None
            else 0.0
        )
        if interaction is not None and (
            interaction_confidence > single_confidence
            or single_confidence == 0.0
        ):
            return interaction
        if single is not None:
            return single
        return fallback[0] if fallback else None

    @classmethod
    def _contributors_for(
        cls,
        selector: str,
        rule_index: int,
        property_name: str,
        interactions: dict[str, list[dict[str, JsonValue]]],
        minimal_sets: dict[str, list[dict[str, JsonValue]]],
    ) -> list[str]:
        """Collect properties experimentally interacting with one declaration.

        Args:
        selector: Value for selector.
        rule_index: Value for rule index.
        property_name: Value for property name.
        interactions: Value for interactions.
        minimal_sets: Value for minimal sets.

        Returns:
        Result produced by  contributors for.

        """
        output: set[str] = set()
        for source in (interactions, minimal_sets):
            for entry in source.get(selector, []):
                cls._collect_contributors(
                    entry=entry,
                    rule_index=rule_index,
                    property_name=property_name,
                    output=output,
                )
        return sorted(output)

    @staticmethod
    def _changed_rule_candidates(
        rules_a: tuple[RuleInfo, ...],
        ranked: tuple[RuleInfo, ...],
    ) -> tuple[RuleInfo, ...]:
        """Put B rules absent from A first while preserving causal rank.

        Args:
            rules_a: Rules captured from side A.
            ranked: Candidate rules ordered by causal relevance.

        Returns:
            Candidate rules with changed B rules prioritized.

        """
        signatures_a: set[tuple[str, str]] = {
            (rule.selector, rule.css_text) for rule in rules_a
        }
        changed: list[RuleInfo] = [
            rule
            for rule in ranked
            if (rule.selector, rule.css_text) not in signatures_a
        ]
        return tuple(changed) if changed else ranked

    @staticmethod
    def _parse_elements(raw: str) -> tuple[ElementInfo, ...]:
        """Validate and convert browser DOM geometry.

        Args:
        raw: Value for raw.

        Returns:
        Result produced by  parse elements.

        Raises:
        InvalidBrowserPayloadError: If the operation cannot be completed.

        """
        decoded: JsonValue = cast(typ="JsonValue", val=loads(s=raw))
        if not isinstance(decoded, list):
            raise InvalidBrowserPayloadError
        output: list[ElementInfo] = []
        for entry_value in decoded:
            if not isinstance(entry_value, dict):
                raise InvalidBrowserPayloadError
            entry: dict[str, JsonValue] = entry_value
            selector: JsonValue = entry.get("selector")
            dom_path: JsonValue = entry.get("domPath")
            parent_path: JsonValue = entry.get("parentPath")
            tag: JsonValue = entry.get("tag")
            text: JsonValue = entry.get("text")
            own_text: JsonValue = entry.get("ownText")
            position: JsonValue = entry.get("position")
            z_index: JsonValue = entry.get("zIndex")
            computed: JsonValue = entry.get("computed")
            typed_computed: JsonValue = entry.get("typedComputed")
            before_content: JsonValue = entry.get("beforeContent")
            after_content: JsonValue = entry.get("afterContent")
            child_count: JsonValue = entry.get("childCount")
            overflow_x: JsonValue = entry.get("overflowX")
            overflow_y: JsonValue = entry.get("overflowY")
            number_names: tuple[str, ...] = (
                "x",
                "y",
                "width",
                "height",
                "scrollWidth",
                "scrollHeight",
                "clientWidth",
                "clientHeight",
            )
            numbers: tuple[JsonValue, ...] = tuple(
                entry.get(name) for name in number_names
            )
            if (
                not isinstance(selector, str)
                or not isinstance(dom_path, str)
                or (not isinstance(parent_path, str))
                or (not isinstance(tag, str))
                or (not isinstance(text, str))
                or (not isinstance(own_text, str))
                or (not isinstance(position, str))
                or (not isinstance(z_index, str))
                or (not isinstance(computed, dict))
                or (not isinstance(typed_computed, dict))
                or (not isinstance(before_content, str))
                or (not isinstance(after_content, str))
                or (not isinstance(child_count, int))
                or (not isinstance(overflow_x, str))
                or (not isinstance(overflow_y, str))
                or (
                    not all(
                        isinstance(value, str) for value in computed.values()
                    )
                )
                or (
                    not all(
                        isinstance(value, int | float)
                        and (not isinstance(value, bool))
                        for value in numbers
                    )
                )
            ):
                raise InvalidBrowserPayloadError
            numeric_values: tuple[float, ...] = tuple(
                float(value)
                for value in numbers
                if isinstance(value, int | float)
            )
            output.append(
                ElementInfo(
                    selector=selector,
                    dom_path=dom_path,
                    parent_path=parent_path,
                    tag=tag,
                    text=text,
                    own_text=own_text,
                    rect=Rect(
                        x=numeric_values[0],
                        y=numeric_values[1],
                        width=numeric_values[2],
                        height=numeric_values[3],
                    ),
                    position=position,
                    z_index=z_index,
                    computed={
                        str(object=key): str(object=value)
                        for key, value in computed.items()
                    },
                    typed_computed={
                        str(object=key): cast(typ="JsonValue", val=value)
                        for key, value in typed_computed.items()
                    },
                    before_content=before_content,
                    after_content=after_content,
                    child_count=child_count,
                    scroll_width=numeric_values[4],
                    scroll_height=numeric_values[5],
                    client_width=numeric_values[6],
                    client_height=numeric_values[7],
                    overflow_x=overflow_x,
                    overflow_y=overflow_y,
                ),
            )
        return tuple(output)

    @staticmethod
    def _pixels_in_rect(mask: Image.Image, rect: Rect) -> int:
        """Count changed mask pixels inside a document rectangle.

        Args:
        mask: Value for mask.
        rect: Value for rect.

        Returns:
        Result produced by  pixels in rect.

        """
        left: int = max(0, int(rect.x))
        top: int = max(0, int(rect.y))
        right: int = min(mask.width, int(rect.right + 1))
        bottom: int = min(mask.height, int(rect.bottom + 1))
        if left >= right or top >= bottom:
            return 0
        crop: Image.Image = mask.crop(box=(left, top, right, bottom))
        return sum(1 for value in crop.tobytes() if value)

    @staticmethod
    def _parent_selector(selector: str) -> str:
        """Return the generated selector's direct parent selector.

        Args:
        selector: Value for selector.

        Returns:
        Result produced by  parent selector.

        """
        return (
            selector.rsplit(sep=" > ", maxsplit=1)[0]
            if " > " in selector
            else ""
        )

    @staticmethod
    def _declaration_parts(declaration: str) -> tuple[str, str]:
        """Split a normalized CSS declaration into property and value.

        Args:
        declaration: Value for declaration.

        Returns:
        Result produced by  declaration parts.

        """
        property_name, separator, value = declaration.partition(":")
        if not separator:
            return (declaration.strip(), "")
        return (property_name.strip(), value.strip())

    @staticmethod
    def _variable_chains(
        records: list[dict[str, JsonValue]],
    ) -> list[dict[str, JsonValue]]:
        """Build transitive custom-property dependency chains.

        Args:
        records: Value for records.

        Returns:
        Result produced by  variable chains.

        """
        definitions: dict[str, list[dict[str, JsonValue]]] = {}
        consumers: list[dict[str, JsonValue]] = []
        for record in records:
            defines: JsonValue | None = record.get("defines")
            if isinstance(defines, str):
                definitions.setdefault(defines, []).append(record)
            if record.get("references"):
                consumers.append(record)

        def expand(
            name: str,
            visited: frozenset[str],
        ) -> list[dict[str, JsonValue]]:
            """Run expand.

            Args:
            name: Value for name.
            visited: Value for visited.

            Returns:
            Result produced by expand.

            """
            if name in visited:
                return [{"variable": name, "cycle": True}]
            chain: list[dict[str, JsonValue]] = []
            for definition in definitions.get(name, []):
                references_value: JsonValue | None = definition.get(
                    "references",
                )
                references: list[str] = (
                    [
                        value
                        for value in references_value
                        if isinstance(value, str)
                    ]
                    if isinstance(references_value, list)
                    else []
                )
                chain.append(
                    cast(
                        typ="dict[str, JsonValue]",
                        val={
                            "variable": name,
                            "defined_by": {
                                "selector": definition.get("selector"),
                                "authored_value": definition.get(
                                    "authored_value",
                                ),
                                "resolved_value": definition.get(
                                    "resolved_definition",
                                ),
                                "source_order": definition.get("source_order"),
                                "important": definition.get("important"),
                            },
                            "depends_on": [
                                {
                                    "variable": reference,
                                    "chain": expand(
                                        name=reference,
                                        visited=visited | {name},
                                    ),
                                }
                                for reference in references
                            ],
                        },
                    ),
                )
            return chain

        output: list[dict[str, JsonValue]] = []
        for consumer in consumers:
            references_value: JsonValue | None = consumer.get("references")
            if not isinstance(references_value, list):
                continue
            output.append(
                cast(
                    typ="dict[str, JsonValue]",
                    val={
                        "consumer": {
                            "selector": consumer.get("selector"),
                            "property": consumer.get("property"),
                            "authored_value": consumer.get("authored_value"),
                        },
                        "variables": [
                            {
                                "variable": reference,
                                "chain": expand(
                                    name=reference,
                                    visited=frozenset(),
                                ),
                            }
                            for reference in references_value
                            if isinstance(reference, str)
                        ],
                    },
                ),
            )
        return output

    @staticmethod
    @staticmethod
    def _content_delta(
        before: ElementInfo,
        after: ElementInfo,
    ) -> dict[str, JsonValue] | None:
        """Return DOM/pseudo-content changes independent of CSS geometry.

        Args:
        before: Value for before.
        after: Value for after.

        Returns:
        Result produced by  content delta.

        """
        changes: dict[str, JsonValue] = {}
        if before.text != after.text:
            changes["text"] = {"a": before.text, "b": after.text}
        if before.own_text != after.own_text:
            changes["own_text"] = {"a": before.own_text, "b": after.own_text}
        if before.before_content != after.before_content:
            changes["before"] = {
                "a": before.before_content,
                "b": after.before_content,
            }
        if before.after_content != after.after_content:
            changes["after"] = {
                "a": before.after_content,
                "b": after.after_content,
            }
        if before.child_count != after.child_count:
            changes["child_count"] = {
                "a": before.child_count,
                "b": after.child_count,
            }
        intrinsic: dict[str, JsonValue] = {}
        for name, a_value, b_value in (
            ("scroll_width", before.scroll_width, after.scroll_width),
            ("scroll_height", before.scroll_height, after.scroll_height),
            ("client_width", before.client_width, after.client_width),
            ("client_height", before.client_height, after.client_height),
        ):
            if a_value != b_value:
                intrinsic[name] = {"a": a_value, "b": b_value}
        if intrinsic:
            changes["intrinsic_geometry"] = intrinsic
        if (
            before.overflow_x != after.overflow_x
            or before.overflow_y != after.overflow_y
        ):
            changes["overflow"] = {
                "a": {"x": before.overflow_x, "y": before.overflow_y},
                "b": {"x": after.overflow_x, "y": after.overflow_y},
            }
        return changes or None

    @staticmethod
    def _json_float(value: JsonValue, default: float = 0.0) -> float:
        """Convert a JSON scalar number to float without unsafe unions.

        Args:
        value: Value for value.
        default: Value for default.

        Returns:
        Result produced by  json float.

        """
        return (
            float(value)
            if isinstance(value, int | float) and (not isinstance(value, bool))
            else default
        )

    @staticmethod
    @staticmethod
    def _element_by_selector(
        elements: tuple[ElementInfo, ...],
        selector: str,
    ) -> ElementInfo:
        """Return an element snapshot by generated selector.

        Args:
        elements: Value for elements.
        selector: Value for selector.

        Returns:
        Result produced by  element by selector.

        Raises:
        KeyError: If the operation cannot be completed.

        """
        for element in elements:
            if element.selector == selector:
                return element
        msg: str = f"Element snapshot not found: {selector}"
        raise KeyError(msg)

    @staticmethod
    def _element_distance(
        reference: ElementInfo,
        candidate: ElementInfo,
    ) -> float:
        """Measure geometry plus computed-style distance from a reference.

        Args:
        reference: Value for reference.
        candidate: Value for candidate.

        Returns:
        Result produced by  element distance.

        """
        geometry: float = (
            abs(reference.rect.x - candidate.rect.x)
            + abs(reference.rect.y - candidate.rect.y)
            + abs(reference.rect.width - candidate.rect.width)
            + abs(reference.rect.height - candidate.rect.height)
        )
        style: float = float(
            sum(
                (
                    reference.computed.get(name, "") != value
                    for name, value in candidate.computed.items()
                ),
            ),
        )
        return geometry + style

    @staticmethod
    def _relationship(
        source: str,
        target: str,
        elements: tuple[ElementInfo, ...],
    ) -> str:
        """Classify the structural relation from source to target.

        Args:
        source: Value for source.
        target: Value for target.
        elements: Value for elements.

        Returns:
        Result produced by  relationship.

        """
        by_selector: dict[str, ElementInfo] = {
            element.selector: element for element in elements
        }
        source_element: ElementInfo | None = by_selector.get(source)
        target_element: ElementInfo | None = by_selector.get(target)
        if source_element is not None and target_element is not None:
            if target_element.dom_path.startswith(
                f"{source_element.dom_path}/",
            ):
                return "ancestor"
            if source_element.dom_path.startswith(
                f"{target_element.dom_path}/",
            ):
                return "descendant"
            if (
                source_element.parent_path
                and source_element.parent_path == target_element.parent_path
            ):
                return "sibling"
        if (
            source_element is not None
            and target_element is not None
            and source_element.rect.intersects(other=target_element.rect)
        ):
            return "overlap"
        return "indirect"

    @staticmethod
    def _style_changes_json(node: ChangeNode) -> dict[str, JsonValue]:
        """Serialize grouped computed-style changes as JSON.

        Args:
            node: Changed rendered DOM node.

        Returns:
            Grouped before/after computed-style values.

        """
        return cast(
            typ="dict[str, JsonValue]",
            val={
                group: {
                    name: {"a": change.a, "b": change.b}
                    for name, change in changes.items()
                }
                for group, changes in node.computed_style_changes.items()
                if changes
            },
        )

    @staticmethod
    def _paint_order(current: ElementInfo, other: ElementInfo) -> str:
        """Estimate overlap paint order from z-index when comparable.

        Args:
        current: Value for current.
        other: Value for other.

        Returns:
        Result produced by  paint order.

        """
        try:
            current_z: int = int(current.z_index)
            other_z: int = int(other.z_index)
        except ValueError:
            return "unknown"
        if other_z > current_z:
            return "other-above"
        if other_z < current_z:
            return "other-below"
        return "same-z-index"

    @staticmethod
    def _relations(
        rule: RuleInfo,
        affected: tuple[ElementInfo, ...],
        elements: tuple[ElementInfo, ...],
    ) -> tuple[str, ...]:
        """Describe how rule-matched nodes relate to visually changed nodes.

        Args:
        rule: Value for rule.
        affected: Value for affected.
        elements: Value for elements.

        Returns:
        Result produced by  relations.

        """
        by_selector: dict[str, ElementInfo] = {
            element.selector: element for element in elements
        }
        relations: set[str] = set()
        affected_selectors: set[str] = {
            element.selector for element in affected
        }
        for matched_selector in rule.matched:
            matched: ElementInfo | None = by_selector.get(matched_selector)
            if matched is None:
                continue
            for target in affected[: Constants.max_relation_elements]:
                if matched_selector == target.selector:
                    relations.add(f"self:{target.selector}")
                elif target.selector.startswith(f"{matched_selector} > "):
                    relations.add(f"ancestor:{matched_selector}")
                elif matched_selector.startswith(f"{target.selector} > "):
                    relations.add(f"descendant:{matched_selector}")
                elif matched.rect.intersects(other=target.rect):
                    relations.add(f"overlap:{matched_selector}")
                else:
                    matched_parent: str = (
                        matched_selector.rpartition(" > ")[0]
                        if " > " in matched_selector
                        else ""
                    )
                    target_parent: str = (
                        target.selector.rpartition(" > ")[0]
                        if " > " in target.selector
                        else ""
                    )
                    if matched_parent and matched_parent == target_parent:
                        relations.add(f"sibling:{matched_selector}")
            if matched_selector in affected_selectors:
                relations.add(f"self:{matched_selector}")
        return tuple(sorted(relations))

    @staticmethod
    def _structural_analysis(
        image_a: Image.Image,
        image_b: Image.Image,
        regions: tuple[Rect, ...],
        elements: tuple[ElementInfo, ...],
    ) -> dict[str, JsonValue]:
        """Summarize visual structure and structural A/B disruption.

        Args:
            image_a: CSS-pixel reference image.
            image_b: CSS-pixel changed image.
            regions: Connected visual-difference regions.
            elements: Rendered elements intersecting visual changes.

        Returns:
            JSON-compatible structural image analysis.

        """
        width: int = max(image_a.width, image_b.width)
        height: int = max(image_a.height, image_b.height)
        horizontal: list[JsonValue] = []
        vertical: list[JsonValue] = []
        for region in regions:
            horizontal.append(
                {
                    "start": round(number=region.y, ndigits=2),
                    "end": round(number=region.bottom, ndigits=2),
                    "coverage": round(
                        number=region.width / max(1, width),
                        ndigits=4,
                    ),
                },
            )
            vertical.append(
                {
                    "start": round(number=region.x, ndigits=2),
                    "end": round(number=region.right, ndigits=2),
                    "coverage": round(
                        number=region.height / max(1, height),
                        ndigits=4,
                    ),
                },
            )
        alignments: dict[str, int] = {
            "left": 0,
            "right": 0,
            "top": 0,
            "bottom": 0,
        }
        tolerance: float = 2.0
        for index, first in enumerate(iterable=elements):
            for second in elements[index + 1 :]:
                if abs(first.rect.x - second.rect.x) <= tolerance:
                    alignments["left"] += 1
                if abs(first.rect.right - second.rect.right) <= tolerance:
                    alignments["right"] += 1
                if abs(first.rect.y - second.rect.y) <= tolerance:
                    alignments["top"] += 1
                if abs(first.rect.bottom - second.rect.bottom) <= tolerance:
                    alignments["bottom"] += 1
        areas: list[float] = [
            region.width * region.height for region in regions
        ]
        changed_area: float = sum(areas)
        page_area: float = float(max(1, width * height))
        repeated: dict[str, int] = {}
        for element in elements:
            key: str = (
                f"{round(number=element.rect.width)}x"
                f"{round(number=element.rect.height)}"
            )
            repeated[key] = repeated.get(key, 0) + 1
        repeated_groups: list[JsonValue] = [
            {"size": key, "count": count}
            for key, count in sorted(repeated.items())
            if count > 1
        ]
        return cast(
            typ="dict[str, JsonValue]",
            val={
                "canvas": {"width": width, "height": height},
                "changed_region_count": len(regions),
                "changed_region_area": round(number=changed_area, ndigits=2),
                "changed_region_area_ratio": round(
                    number=changed_area / page_area,
                    ndigits=6,
                ),
                "largest_region_area": round(
                    number=max(areas, default=0.0),
                    ndigits=2,
                ),
                "horizontal_bands": horizontal,
                "vertical_bands": vertical,
                "alignment_pairs": alignments,
                "repeated_geometry_groups": repeated_groups,
                "affected_element_count": len(elements),
            },
        )

    @staticmethod
    def _group_property_evidence(
        provenance: dict[str, list[dict[str, JsonValue]]],
    ) -> dict[int, dict[str, list[dict[str, JsonValue]]]]:
        """Group declaration evidence by rule index and property.

        Args:
            provenance: Declaration evidence keyed by selector.

        Returns:
            Evidence grouped by rule index then property name.

        """
        grouped: dict[int, dict[str, list[dict[str, JsonValue]]]] = {}
        for selector, declarations in provenance.items():
            for declaration in declarations:
                rule_index_value: JsonValue = declaration.get("rule_index")
                property_value: JsonValue = declaration.get("property")
                if not isinstance(rule_index_value, int) or not isinstance(
                    property_value,
                    str,
                ):
                    continue
                grouped.setdefault(rule_index_value, {}).setdefault(
                    property_value,
                    [],
                ).append({**declaration, "selector": selector})
        return grouped

    @staticmethod
    def _evidence_metrics(
        grouped: dict[int, dict[str, list[dict[str, JsonValue]]]],
    ) -> tuple[int, int, int]:
        """Count identified properties, links, and proven properties.

        Args:
            grouped: Evidence grouped by rule index then property.

        Returns:
            Identified-property, affected-pair, and proven-property counts.

        """
        identified: int = sum(
            len(properties) for properties in grouped.values()
        )
        pairs: int = sum(
            len(impacts)
            for properties in grouped.values()
            for impacts in properties.values()
        )
        proven: int = sum(
            1
            for properties in grouped.values()
            for impacts in properties.values()
            if any(item.get("proven") is True for item in impacts)
        )
        return (identified, pairs, proven)

    @staticmethod
    def _report_alignment(alignment_value: JsonValue) -> list[str]:
        """Build the alignment-structure table when data is available.

        Args:
            alignment_value: Alignment pair counts by edge.

        Returns:
            Markdown lines, or an empty list without alignment data.

        """
        if not isinstance(alignment_value, dict):
            return []
        return [
            "### Alignment structure",
            "",
            "Pairs of affected elements that remain aligned within a 2 "
            "CSS-pixel tolerance:",
            "",
            "| Edge | Pair count |",
            "|---|---:|",
            *[
                f"| {name.title()} | {value} |"
                for name, value in alignment_value.items()
            ],
            "",
        ]

    @staticmethod
    def _report_repeated_geometry(repeated_value: JsonValue) -> list[str]:
        """Build the repeated-geometry table when data is available.

        Args:
            repeated_value: Repeated element-size groups.

        Returns:
            Markdown lines, or an empty list without repeated geometry.

        """
        if not isinstance(repeated_value, list) or not repeated_value:
            return []
        lines: list[str] = [
            "### Repeated geometry",
            "",
            "| Approximate size | Count |",
            "|---|---:|",
        ]
        lines.extend(
            f"| `{item.get('size', '')}` | {item.get('count', 0)} |"
            for item in repeated_value
            if isinstance(item, dict)
        )
        lines.append("")
        return lines

    @staticmethod
    def _safe_evidence_name(
        rule_index: int,
        property_name: str,
        selector: str,
    ) -> str:
        """Create a stable filesystem-safe evidence basename.

        Args:
        rule_index: Value for rule index.
        property_name: Value for property name.
        selector: Value for selector.

        Returns:
        Result produced by  safe evidence name.

        """
        raw: str = f"r{rule_index}-{property_name}-{selector}"
        return "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in raw
        )[:120]

    @staticmethod
    def _human_change_summary(node: ChangeNode) -> str:
        """Describe only meaningful geometry and computed-style changes.

        Args:
            node: Changed rendered DOM node.

        Returns:
            Markdown describing non-zero geometry deltas and computed changes.

        """
        geometry: list[str] = []
        for name, values in node.geometry.items():
            a_value: float = values.get("a", 0.0)
            b_value: float = values.get("b", 0.0)
            delta: float = b_value - a_value
            if abs(delta) <= Constants.geometry_delta_epsilon:
                continue
            geometry.append(
                f"| `{name}` | {a_value:.2f} | {b_value:.2f} | {delta:+.2f} |",
            )
        body: list[str] = []
        if geometry:
            body.extend(
                [
                    "**Geometry**",
                    "",
                    "| Measurement | A | B | Δ |",
                    "|---|---:|---:|---:|",
                    *geometry,
                    "",
                ],
            )
        for group, changes in node.computed_style_changes.items():
            rows: list[str] = [
                f"| `{name}` | `{change.a}` | `{change.b}` |"
                for name, change in changes.items()
                if change.a != change.b
            ]
            if rows:
                body.extend(
                    [
                        f"**{group.replace('_', ' ').title()}**",
                        "",
                        "| Property | A | B |",
                        "|---|---|---|",
                        *rows,
                        "",
                    ],
                )
        if not body:
            body.extend(
                [
                    "No captured geometry or computed-style field changed; "
                    "the causal evidence is pixel-level.",
                    "",
                ],
            )
        return "\n".join(["###### What changed", "", *body])

    @staticmethod
    def _collect_contributors(
        entry: dict[str, JsonValue],
        rule_index: int,
        property_name: str,
        output: set[str],
    ) -> None:
        """Add companion properties from one member-list evidence entry.

        Args:
            entry: Interaction or minimal-set evidence entry.
            rule_index: Flattened rule index of the current declaration.
            property_name: Property of the current declaration.
            output: Accumulating contributor property names.

        """
        members: JsonValue = entry.get("members")
        if not isinstance(members, list):
            return
        involved: bool = any(
            isinstance(member, dict)
            and member.get("rule_index") == rule_index
            and (member.get("property") == property_name)
            for member in members
        )
        if not involved:
            return
        for member in members:
            if isinstance(member, dict):
                prop: JsonValue = member.get("property")
                if isinstance(prop, str) and prop != property_name:
                    output.add(prop)

    def _url_for_side(self, side: RenderSide) -> str:
        """Resolve the navigation URL for an explicit A/B side.

        Args:
        side: Render side being prepared.

        Returns:
        Result produced by  url for css.

        """
        return (
            self.settings.url
            if side == "a" or self.settings.url_b is None
            else self.settings.url_b
        )

    def _budget_available(self) -> bool:
        """Return whether the bounded causal-search budget remains.

        Returns:
            True when another causal experiment may start.

        """
        return self._deadline is None or monotonic() < self._deadline

    def _require_budget(self, phase: str) -> bool:
        """Record truncation and return whether a causal phase may continue.

        Args:
            phase: Name of the causal-analysis phase.

        Returns:
            True when the phase may continue within the configured budget.

        """
        if self._budget_available():
            return True
        self._progress(phase=f"{phase}-budget-exhausted", completed=1, total=1)
        return False

    def _navigate(self, page: Page, url: str) -> None:
        """Navigate with bounded readiness and local-file support.

        Args:
            page: Playwright page used for navigation.
            url: Target URL or file URI.

        """
        parsed: SplitResult = urlsplit(url=url)
        if parsed.scheme == "file":
            html_path: Path = Path(parsed.path)
            page.set_content(
                html=html_path.read_text(encoding="utf-8"),
                wait_until="domcontentloaded",
                timeout=self.settings.timeout_ms,
            )
        else:
            page.goto(
                url=url,
                wait_until="domcontentloaded",
                timeout=self.settings.timeout_ms,
            )
        page.wait_for_timeout(timeout=50)

    def _install_extended_selector(self, *, page: Page) -> None:
        """Install the packaged extended-selector engine when enabled.

        Args:
            page: Page that should resolve extended selector queries.

        """
        source: str | None = self._EXTENDED_SELECTOR_JS
        if self.settings.extended_selectors and source is not None:
            page.evaluate(expression=source)

    def _progress(self, phase: str, completed: int, total: int) -> None:
        """Persist lightweight progress so long analyses are visibly alive.

        Args:
            phase: Current analysis phase.
            completed: Number of completed units.
            total: Total units for the phase.

        """
        payload: dict[str, JsonValue] = {
            "status": "running",
            "phase": phase,
            "completed": completed,
            "total": total,
            "updated_monotonic": monotonic(),
        }
        (self.settings.output / "progress.json").write_text(
            data=dumps(obj=payload, indent=2),
            encoding="utf-8",
        )
        stdout.write(f"[css-visual-cause] {phase} {completed}/{total}\n")
        stdout.flush()
        if self._observer is not None:
            self._observer(phase=phase, completed=completed, total=total)

    def _write_failure(self, error: Exception) -> None:
        """Persist a useful report even when analysis cannot complete.

        Args:
            error: Exception that terminated the analysis.

        """
        payload: dict[str, JsonValue] = {
            "status": "failed",
            "error_type": type(error).__name__,
            "error": str(object=error),
            "url_a": self.settings.url,
            "url_b": self.settings.url_b or self.settings.url,
            "target_a": self.target_a.manifest(),
            "target_b": self.target_b.manifest(),
        }
        (self.settings.output / "progress.json").write_text(
            data=dumps(obj=payload, indent=2),
            encoding="utf-8",
        )
        (self.settings.output / "failure.json").write_text(
            data=dumps(obj=payload, indent=2),
            encoding="utf-8",
        )
        (self.settings.output / "report.md").write_text(
            data=(
                "# CSS visual-causality analysis failed\n\n"
                f"- Error: `{type(error).__name__}`\n"
                f"- URL A: `{self.settings.url}`\n"
                f"- URL B: `{self.settings.url_b or self.settings.url}`\n\n"
                f"```text\n{error}\n```\n"
            ),
            encoding="utf-8",
        )

    def _run_analysis(self) -> AnalysisResults:
        """Run baseline renders and causal interventions.

        Returns:
            Analysis results used to write the artifacts.

        """
        with sync_playwright() as playwright:
            try:
                browser: Browser = playwright.chromium.launch(headless=True)
            except Exception:
                executable: str | None = which(cmd="chromium") or which(
                    cmd="google-chrome",
                )
                if executable is None:
                    raise
                browser = playwright.chromium.launch(
                    headless=True,
                    executable_path=executable,
                )
            try:
                self._progress(phase="baseline-a", completed=0, total=2)
                image_a, elements_a, rules_a = self._render(
                    browser=browser,
                    css=self.css_a,
                    intervention=Intervention(),
                    side="a",
                )
                self._progress(phase="baseline-b", completed=1, total=2)
                image_b, elements_b, rules_b = self._render(
                    browser=browser,
                    css=self.css_b,
                    intervention=Intervention(),
                    side="b",
                )
                self._progress(phase="baseline-complete", completed=2, total=2)
                self._last_elements_b = elements_b
                (self._highres_a or image_a).save(
                    fp=self.settings.output / "a.png",
                )
                (self._highres_b or image_b).save(
                    fp=self.settings.output / "b.png",
                )
                self._progress(phase="pixel-diff", completed=0, total=1)
                baseline: int = self._changed_pixels(
                    image_a=image_a,
                    image_b=image_b,
                )
                self._progress(phase="regions", completed=0, total=1)
                regions: tuple[Rect, ...] = self._regions(
                    image_a=image_a,
                    image_b=image_b,
                )
                affected: tuple[ElementInfo, ...] = tuple(
                    element
                    for element in elements_b
                    if any(
                        element.rect.intersects(other=region)
                        for region in regions
                    )
                )
                self._progress(phase="change-nodes", completed=0, total=1)
                nodes: tuple[ChangeNode, ...] = self._change_nodes(
                    image_a=image_a,
                    image_b=image_b,
                    elements_a=elements_a,
                    affected=affected,
                )
                self._progress(phase="rank-rules", completed=0, total=1)
                ranked_raw: tuple[RuleInfo, ...] = self._rank_rules(
                    rules=rules_b,
                    affected=affected,
                    elements=elements_b,
                )
                ranked: tuple[RuleInfo, ...] = self._changed_rule_candidates(
                    rules_a=rules_a,
                    ranked=ranked_raw,
                )
                causes: list[Cause] = []
                deep_analysis: bool = self.settings.advanced_analysis
                for rule, changed, explained in (
                    self._serial_rule_trials(
                        browser=browser,
                        rules=ranked,
                        image_a=image_a,
                        baseline=baseline,
                    )
                    if self._require_budget(phase="rule-trials")
                    else []
                ):
                    if explained == 0:
                        continue
                    causes.append(
                        Cause(
                            index=rule.index,
                            selector=rule.selector,
                            css_text=rule.css_text,
                            declarations=rule.declarations,
                            matched=rule.matched,
                            relations=self._relations(
                                rule=rule,
                                affected=affected,
                                elements=elements_b,
                            ),
                            changed_pixels_without_rule=changed,
                            pixels_explained=explained,
                            explanation_ratio=explained / baseline
                            if baseline
                            else 0.0,
                        ),
                    )
                causes.sort(
                    key=lambda cause: (-cause.pixels_explained, cause.index),
                )
                declaration_provenance: dict[
                    str,
                    list[dict[str, JsonValue]],
                ] = self._declaration_trials(
                    browser=browser,
                    nodes=nodes,
                    rules=ranked,
                    causes=tuple(causes),
                    elements_a=elements_a,
                )
                declaration_provenance = self._complete_property_evidence(
                    rules=ranked,
                    causes=tuple(causes),
                    nodes=nodes,
                    provenance=declaration_provenance,
                )
                causal_edges: dict[str, list[dict[str, JsonValue]]] = (
                    self._causal_edges(
                        browser=browser,
                        nodes=nodes,
                        elements_a=elements_a,
                    )
                    if deep_analysis
                    and self._require_budget(phase="causal-edges")
                    else {}
                )
                function_provenance: dict[str, list[dict[str, JsonValue]]] = (
                    self._function_provenance(
                        browser=browser,
                        nodes=nodes,
                        rules=rules_b,
                        elements_a=elements_a,
                        rules_a=rules_a,
                    )
                    if deep_analysis and self._require_budget(phase="values")
                    else {}
                )
                cascade_provenance: dict[str, JsonValue] = (
                    self._cascade_provenance(browser=browser, nodes=nodes)
                    if deep_analysis and self._require_budget(phase="cascade")
                    else {}
                )
                interaction_provenance: dict[
                    str,
                    list[dict[str, JsonValue]],
                ] = (
                    self._interaction_provenance(
                        browser=browser,
                        nodes=nodes,
                        rules=rules_b,
                        elements_a=elements_a,
                        singles=declaration_provenance,
                    )
                    if deep_analysis
                    and self._require_budget(phase="interactions")
                    else {}
                )
                minimal_sets: dict[str, list[dict[str, JsonValue]]] = (
                    self._minimal_cause_sets(
                        browser=browser,
                        nodes=nodes,
                        rules=rules_b,
                        elements_a=elements_a,
                    )
                    if deep_analysis
                    and self._require_budget(phase="minimal-sets")
                    else {}
                )
                self._progress(phase="writing-report", completed=1, total=1)
                results: AnalysisResults = AnalysisResults(
                    baseline=baseline,
                    regions=regions,
                    affected=affected,
                    nodes=nodes,
                    causes=tuple(causes),
                    elements_a=elements_a,
                    rules_b=rules_b,
                    evidence_image_a=self._highres_a or image_a,
                    evidence_image_b=self._highres_b or image_b,
                    analysis_image_a=image_a,
                    analysis_image_b=image_b,
                    provenance=ProvenanceMaps(
                        causal_edges=causal_edges,
                        declaration_provenance=declaration_provenance,
                        function_provenance=function_provenance,
                        cascade_provenance=cascade_provenance,
                        interaction_provenance=interaction_provenance,
                        minimal_sets=minimal_sets,
                    ),
                )
                self._write_outputs(results=results)
                self._progress(phase="complete", completed=1, total=1)
                return results
            finally:
                browser.close()

    def _single_declaration_provenance(
        self,
        nodes: tuple[ChangeNode, ...],
        causes: tuple[Cause, ...],
        elements_a: tuple[ElementInfo, ...],
    ) -> dict[str, list[dict[str, JsonValue]]]:
        """Promote single-declaration rule ablations to property evidence.

        Args:
            nodes: Changed rendered DOM nodes.
            causes: Proven causal CSS rules.
            elements_a: Side-A element snapshots.

        Returns:
            Property evidence grouped by affected element selector.

        """
        by_a: dict[str, ElementInfo] = {
            element.selector: element for element in elements_a
        }
        by_b: dict[str, ElementInfo] = {
            element.selector: element for element in self._last_elements_b
        }
        output: dict[str, list[dict[str, JsonValue]]] = {
            node.selector: [] for node in nodes
        }
        for cause in causes:
            if len(cause.declarations) != 1:
                continue
            property_name, authored_value = self._declaration_parts(
                declaration=cause.declarations[0],
            )
            for node in nodes:
                if node.selector not in cause.matched:
                    continue
                before: ElementInfo | None = by_a.get(node.selector)
                after: ElementInfo | None = by_b.get(node.selector)
                if before is None or after is None:
                    continue
                output[node.selector].append(
                    cast(
                        typ="dict[str, JsonValue]",
                        val={
                            "rule_index": cause.index,
                            "selector": cause.selector,
                            "property": property_name,
                            "authored_value": authored_value,
                            "computed_b": after.computed.get(
                                property_name,
                                "",
                            ),
                            "improvement": float(cause.pixels_explained),
                            "confidence": cause.explanation_ratio,
                            "role": "single-declaration-rule-ablation",
                            "value_ast": CssValueParser.parse(
                                value=authored_value,
                            ).to_json(),
                        },
                    ),
                )
        return output

    def _declaration_trials(
        self,
        browser: Browser,
        nodes: tuple[ChangeNode, ...],
        rules: tuple[RuleInfo, ...],
        causes: tuple[Cause, ...],
        elements_a: tuple[ElementInfo, ...],
    ) -> dict[str, list[dict[str, JsonValue]]]:
        """Test every changed declaration against every changed rendered node.

        Args:
            browser: Browser used for declaration counterfactual renders.
            nodes: Changed rendered DOM nodes.
            rules: Authored A-to-B changed rules selected for analysis.
            causes: Rules already proven causal by whole-rule ablation.
            elements_a: Side-A element snapshots.

        Returns:
            Declaration evidence grouped by affected element selector.

        """
        output: dict[str, list[dict[str, JsonValue]]] = {
            node.selector: [] for node in nodes
        }
        if not rules:
            return output
        declaration_context: DeclarationContext = DeclarationContext(
            selectors=tuple(node.selector for node in nodes),
            a_by_selector={
                element.selector: element for element in elements_a
            },
            b_by_selector={
                element.selector: element for element in self._last_elements_b
            },
            causes_by_index={cause.index: cause for cause in causes},
        )
        context: BrowserContext = browser.new_context(
            viewport={
                "width": self.settings.width,
                "height": self.settings.height,
            },
            device_scale_factor=1.0,
            reduced_motion="reduce",
        )
        page: Page = context.new_page()
        total: int = sum(len(rule.declarations) for rule in rules)
        completed: int = 0
        try:
            for rule_offset, rule in enumerate(iterable=rules):
                if not self._budget_available():
                    break
                if (
                    rule_offset > 0
                    and rule_offset % self.settings.recycle_after == 0
                ):
                    page.close()
                    page = context.new_page()
                self._navigate(page=page, url=self._url_for_side(side="b"))
                page.evaluate(expression=self._INSTALL_HELPERS_JS)
                self._install_extended_selector(page=page)
                page.evaluate(
                    expression=self._PREPARE_JS,
                    arg=self.settings.use_native_styles_b,
                )
                page.locator(selector="#__css_cause_style__").evaluate(
                    expression="(node, css) => { node.textContent = css; }",
                    arg=self.css_b,
                )
                page.evaluate(expression="() => document.fonts.ready")
                for declaration in rule.declarations:
                    if not self._budget_available():
                        break
                    self._progress(
                        phase="declaration-trials",
                        completed=completed,
                        total=total,
                    )
                    completed += 1
                    self._declaration_trial(
                        page=page,
                        rule=rule,
                        declaration=declaration,
                        context=declaration_context,
                        output=output,
                    )
        finally:
            context.close()
        return output

    def _declaration_trial(
        self,
        page: Page,
        rule: RuleInfo,
        declaration: str,
        context: DeclarationContext,
        output: dict[str, list[dict[str, JsonValue]]],
    ) -> None:
        """Disable one declaration and record per-element improvements.

        Args:
            page: Prepared page rendering side B.
            rule: Flattened rule owning the declaration.
            declaration: Authored declaration to disable.
            context: Shared lookups for declaration trials.
            output: Evidence grouped by affected element selector.

        """
        property_name, authored_value = self._declaration_parts(
            declaration=declaration,
        )
        page.evaluate(
            expression=self._DISABLE_DECLARATION_JS,
            arg=[rule.index, property_name],
        )
        page.evaluate(expression=self._NEXT_FRAME_JS)
        raw_elements: str = cast(typ="JsonPage", val=page).evaluate(
            expression=self._ELEMENTS_JS,
        )
        trial_elements: tuple[ElementInfo, ...] = self._parse_elements(
            raw=raw_elements,
        )
        trial_by_selector: dict[str, ElementInfo] = {
            element.selector: element for element in trial_elements
        }
        cause: Cause | None = context.causes_by_index.get(rule.index)
        for selector in context.selectors:
            before: ElementInfo | None = context.a_by_selector.get(selector)
            after: ElementInfo | None = context.b_by_selector.get(selector)
            trial: ElementInfo | None = trial_by_selector.get(selector)
            if before is None or after is None:
                continue
            distance_before: float = self._element_distance(
                reference=before,
                candidate=after,
            )
            distance_trial: float = (
                self._element_distance(reference=before, candidate=trial)
                if trial is not None
                else distance_before
            )
            local_improvement: float = max(
                0.0,
                distance_before - distance_trial,
            )
            direct: bool = local_improvement > 0.0
            matched: bool = selector in rule.matched
            if not direct and (not matched):
                continue
            global_explained: int = (
                cause.pixels_explained if cause is not None else 0
            )
            confidence: float = (
                cause.explanation_ratio if cause is not None else 0.0
            )
            if direct and matched:
                impact_kind: str = "direct-local"
            elif direct:
                impact_kind = "propagated-structural-or-inherited"
            else:
                impact_kind = "matched-changed-element"
            output[selector].append(
                cast(
                    typ="dict[str, JsonValue]",
                    val={
                        "rule_index": rule.index,
                        "rule_selector": rule.selector,
                        "property": property_name,
                        "authored_value": authored_value,
                        "computed_b": after.computed.get(property_name, ""),
                        "improvement": float(global_explained),
                        "local_improvement": local_improvement,
                        "confidence": confidence,
                        "proven": cause is not None or direct,
                        "direct_local_evidence": direct,
                        "matched_by_rule": matched,
                        "impact_kind": impact_kind,
                        "role": "declaration-ablation",
                        "value_ast": CssValueParser.parse(
                            value=authored_value,
                        ).to_json(),
                    },
                ),
            )
        page.evaluate(
            expression=(
                "\n([ruleIndex, property, value]) => {\n"
                "  const sheet = document.getElementById("
                '"__css_cause_style__").sheet;\n'
                "  const flat = [];\n"
                "  const walk = (rules) => {\n"
                "    for (const item of rules) {\n"
                "      if (item instanceof CSSStyleRule) flat.push(item);\n"
                '      else if ("cssRules" in item) walk(item.cssRules);\n'
                "    }\n"
                "  };\n"
                "  walk(sheet.cssRules);\n"
                "  const target = flat[ruleIndex];\n"
                "  if (target) target.style.setProperty(property, value);\n"
                "}\n"
            ),
            arg=[rule.index, property_name, authored_value],
        )

    def _complete_property_evidence(
        self,
        rules: tuple[RuleInfo, ...],
        causes: tuple[Cause, ...],
        nodes: tuple[ChangeNode, ...],
        provenance: dict[str, list[dict[str, JsonValue]]],
    ) -> dict[str, list[dict[str, JsonValue]]]:
        """Retain all changed authored properties and their changed matches.

        Args:
            rules: Authored A-to-B changed rules selected for analysis.
            causes: Rules with positive counterfactual causal evidence.
            nodes: Changed rendered DOM nodes.
            provenance: Experimentally proven declaration evidence.

        Returns:
            Complete property evidence including unproven changed candidates.

        """
        causal_indexes: set[int] = {cause.index for cause in causes}
        changed_selectors: set[str] = {node.selector for node in nodes}
        output: dict[str, list[dict[str, JsonValue]]] = {
            selector: list(items) for selector, items in provenance.items()
        }
        for rule in rules:
            for declaration in rule.declarations:
                property_name, authored_value = self._declaration_parts(
                    declaration=declaration,
                )
                for selector in rule.matched:
                    if selector not in changed_selectors:
                        continue
                    items: list[dict[str, JsonValue]] = output.setdefault(
                        selector,
                        [],
                    )
                    if any(
                        item.get("rule_index") == rule.index
                        and item.get("property") == property_name
                        for item in items
                    ):
                        continue
                    items.append(
                        cast(
                            typ="dict[str, JsonValue]",
                            val={
                                "rule_index": rule.index,
                                "rule_selector": rule.selector,
                                "property": property_name,
                                "authored_value": authored_value,
                                "computed_b": "",
                                "improvement": 0.0,
                                "local_improvement": 0,
                                "confidence": 0.0,
                                "proven": False,
                                "direct_local_evidence": False,
                                "impact_kind": "matched-changed-element",
                                "role": "causal-rule-property-candidate"
                                if rule.index in causal_indexes
                                else "changed-rule-property-candidate",
                                "value_ast": CssValueParser.parse(
                                    value=authored_value,
                                ).to_json(),
                            },
                        ),
                    )
        return output

    def _serial_rule_trials(
        self,
        browser: Browser,
        rules: tuple[RuleInfo, ...],
        image_a: Image.Image,
        baseline: int,
    ) -> list[tuple[RuleInfo, int, int]]:
        """Evaluate bounded rule interventions on one recyclable page.

        Args:
            browser: Browser used for counterfactual renders.
            rules: Ranked candidate CSS rules.
            image_a: Side-A baseline image.
            baseline: Baseline changed-pixel count.

        Returns:
            Rule, changed-pixel count, and explained-pixel tuples.

        """
        selected: tuple[RuleInfo, ...] = rules[: self.settings.max_candidates]
        results: list[tuple[RuleInfo, int, int]] = []
        context: BrowserContext = browser.new_context(
            viewport={
                "width": self.settings.width,
                "height": self.settings.height,
            },
            device_scale_factor=1.0,
            reduced_motion="reduce",
        )
        page: Page = context.new_page()
        try:
            total: int = len(selected)
            for offset, rule in enumerate(iterable=selected, start=1):
                if not self._budget_available():
                    break
                if (
                    offset > 1
                    and (offset - 1) % self.settings.recycle_after == 0
                ):
                    page.close()
                    page = context.new_page()
                self._progress(
                    phase="rule-trials",
                    completed=offset - 1,
                    total=total,
                )
                trial, _, _ = self._render_page(
                    page=page,
                    css=self.css_b,
                    intervention=Intervention(disabled_rule=rule.index),
                    side="b",
                )
                changed: int = self._changed_pixels(
                    image_a=image_a,
                    image_b=trial,
                )
                results.append((rule, changed, max(0, baseline - changed)))
        finally:
            context.close()
        return results

    def _render(
        self,
        browser: Browser,
        css: str,
        intervention: Intervention,
        side: RenderSide | None = None,
    ) -> tuple[Image.Image, tuple[ElementInfo, ...], tuple[RuleInfo, ...]]:
        """Render the target with one supplied stylesheet.

        Args:
        browser: Value for browser.
        css: Value for css.
        intervention: Counterfactual interventions to apply.
        side: Explicit A/B render identity; legacy calls infer it from CSS.

        Returns:
        Result produced by  render.

        """
        context: BrowserContext = browser.new_context(
            viewport={
                "width": self.settings.width,
                "height": self.settings.height,
            },
            device_scale_factor=self.settings.screenshot_scale,
            reduced_motion="reduce",
        )
        page: Page = context.new_page()
        selected_side: RenderSide = (
            side if side is not None else "a" if css == self.css_a else "b"
        )
        try:
            return self._render_page(
                page=page,
                css=css,
                intervention=intervention,
                side=selected_side,
            )
        finally:
            context.close()

    def _render_page(
        self,
        page: Page,
        css: str,
        intervention: Intervention,
        side: RenderSide | None = None,
    ) -> tuple[Image.Image, tuple[ElementInfo, ...], tuple[RuleInfo, ...]]:
        """Render using a reusable Playwright page.

        Args:
        page: Value for page.
        css: Value for css.
        intervention: Counterfactual interventions to apply.
        side: Explicit A/B render identity; legacy calls infer it from CSS.

        Returns:
        Result produced by  render page.

        """
        selected_side: RenderSide = (
            side if side is not None else "a" if css == self.css_a else "b"
        )
        self._navigate(page=page, url=self._url_for_side(side=selected_side))
        page.evaluate(expression=self._INSTALL_HELPERS_JS)
        self._install_extended_selector(page=page)
        page.evaluate(
            expression=self._PREPARE_JS,
            arg=self.settings.use_native_styles_a
            if selected_side == "a"
            else self.settings.use_native_styles_b,
        )
        page.locator(selector="#__css_cause_style__").evaluate(
            expression="(node, css) => { node.textContent = css; }",
            arg=css,
        )
        page.evaluate(expression="() => document.fonts.ready")
        page.evaluate(expression=self._SETTLE_FRAME_JS)
        rules: tuple[RuleInfo, ...] = self._read_rules(page=page)
        baseline_capture: bool = (
            intervention.disabled_rule is None
            and (not intervention.disabled_declarations)
            and (intervention.element_override is None)
        )
        if selected_side == "b" and baseline_capture:
            parsed_queries: JsonValue = loads(
                s=cast(typ="JsonPage", val=page).evaluate(
                    expression=self._CONTAINER_RULES_JS,
                ),
            )
            if isinstance(parsed_queries, list):
                self._last_container_queries = parsed_queries
        if intervention.disabled_rule is not None:
            self._disable_rule(
                page=page,
                rule_index=intervention.disabled_rule,
            )
        if intervention.disabled_declarations:
            page.evaluate(
                expression=self._DISABLE_DECLARATIONS_JS,
                arg=[
                    [index, name]
                    for index, name in intervention.disabled_declarations
                ],
            )
        if intervention.element_override is not None:
            page.evaluate(
                expression=self._OVERRIDE_ELEMENT_JS,
                arg=[
                    intervention.element_override[0],
                    intervention.element_override[1],
                ],
            )
        if not baseline_capture:
            page.evaluate(expression=self._SETTLE_FRAME_JS)
        raw_elements: str = cast(typ="JsonPage", val=page).evaluate(
            expression=self._ELEMENTS_JS,
        )
        elements: tuple[ElementInfo, ...] = self._parse_elements(
            raw=raw_elements,
        )
        if baseline_capture:
            evidence_png: bytes = page.screenshot(
                full_page=True,
                animations="disabled",
                caret="hide",
                scale="device",
            )
            with Image.open(fp=BytesIO(initial_bytes=evidence_png)) as opened:
                highres: Image.Image = opened.convert(mode="RGBA")
            analysis_png: bytes = page.screenshot(
                full_page=True,
                animations="disabled",
                caret="hide",
                scale="css",
            )
            with Image.open(fp=BytesIO(initial_bytes=analysis_png)) as opened:
                image: Image.Image = opened.convert(mode="RGBA")
            if selected_side == "a":
                self._highres_a = highres.copy()
            if selected_side == "b":
                self._highres_b = highres.copy()
        else:
            analysis_png = page.screenshot(
                full_page=True,
                animations="disabled",
                caret="hide",
                scale="css",
            )
            with Image.open(fp=BytesIO(initial_bytes=analysis_png)) as opened:
                image = opened.convert(mode="RGBA")
        return (image, elements, rules)

    def _read_rules(self, page: Page) -> tuple[RuleInfo, ...]:
        """Read browser-parsed style rules.

        Args:
        page: Value for page.

        Returns:
        Result produced by  read rules.

        Raises:
        InvalidBrowserPayloadError: If the operation cannot be completed.

        """
        raw: str = cast(typ="JsonPage", val=page).evaluate(
            expression=self._RULES_JS,
        )
        decoded: JsonValue = cast(typ="JsonValue", val=loads(s=raw))
        if not isinstance(decoded, list):
            raise InvalidBrowserPayloadError
        rules: list[RuleInfo] = []
        for entry_value in decoded:
            if not isinstance(entry_value, dict):
                raise InvalidBrowserPayloadError
            entry: dict[str, JsonValue] = entry_value
            index: JsonValue = entry.get("index")
            selector: JsonValue = entry.get("selector")
            css_text: JsonValue = entry.get("cssText")
            declarations: JsonValue = entry.get("declarations")
            matched: JsonValue = entry.get("matched")
            if (
                not isinstance(index, int)
                or not isinstance(selector, str)
                or (not isinstance(css_text, str))
                or (not isinstance(declarations, list))
                or (not all(isinstance(item, str) for item in declarations))
                or (not isinstance(matched, list))
                or (not all(isinstance(item, str) for item in matched))
            ):
                raise InvalidBrowserPayloadError
            rules.append(
                RuleInfo(
                    index=index,
                    selector=selector,
                    css_text=css_text,
                    declarations=tuple(
                        item for item in declarations if isinstance(item, str)
                    ),
                    matched=tuple(
                        item for item in matched if isinstance(item, str)
                    ),
                ),
            )
        return tuple(rules)

    def _difference_mask(
        self,
        image_a: Image.Image,
        image_b: Image.Image,
    ) -> Image.Image:
        """Return a thresholded pixel-difference mask.

        Args:
        image_a: Value for image a.
        image_b: Value for image b.

        Returns:
        Result produced by  difference mask.

        """
        width: int = max(image_a.width, image_b.width)
        height: int = max(image_a.height, image_b.height)
        a: Image.Image = Image.new(mode="RGBA", size=(width, height))
        b: Image.Image = Image.new(mode="RGBA", size=(width, height))
        a.paste(im=image_a, box=(0, 0))
        b.paste(im=image_b, box=(0, 0))
        difference: Image.Image = ImageChops.difference(image1=a, image2=b)
        channels: tuple[Image.Image, ...] = difference.split()
        maximum: Image.Image = channels[0]
        for channel in channels[1:]:
            maximum = ImageChops.lighter(image1=maximum, image2=channel)
        return maximum.point(
            lut=lambda value: (
                255
                if cast(typ="int", val=value) > self.settings.threshold
                else 0
            ),
            mode="1",
        )

    def _changed_pixels(
        self,
        image_a: Image.Image,
        image_b: Image.Image,
    ) -> int:
        """Count meaningfully different pixels.

        Args:
        image_a: Value for image a.
        image_b: Value for image b.

        Returns:
        Result produced by  changed pixels.

        """
        mask: Image.Image = self._difference_mask(
            image_a=image_a,
            image_b=image_b,
        )
        return sum(1 for value in mask.tobytes() if value)

    def _regions(
        self,
        image_a: Image.Image,
        image_b: Image.Image,
    ) -> tuple[Rect, ...]:
        """Find connected visual-difference rectangles.

        Args:
        image_a: Value for image a.
        image_b: Value for image b.

        Returns:
        Result produced by  regions.

        """
        mask: Image.Image = self._difference_mask(
            image_a=image_a,
            image_b=image_b,
        ).convert(mode="L")
        width: int = mask.width
        height: int = mask.height
        changed: set[tuple[int, int]] = {
            (index % width, index // width)
            for index, value in enumerate(iterable=mask.tobytes())
            if value
        }
        visited: set[tuple[int, int]] = set()
        regions: list[Rect] = []
        for y in range(height):
            for x in range(width):
                if (x, y) not in changed or (x, y) in visited:
                    continue
                stack: list[tuple[int, int]] = [(x, y)]
                visited.add((x, y))
                min_x: int = x
                max_x: int = x
                min_y: int = y
                max_y: int = y
                count: int = 0
                while stack:
                    px, py = stack.pop()
                    count += 1
                    min_x = min(min_x, px)
                    max_x = max(max_x, px)
                    min_y = min(min_y, py)
                    max_y = max(max_y, py)
                    for nx, ny in (
                        (px - 1, py),
                        (px + 1, py),
                        (px, py - 1),
                        (px, py + 1),
                    ):
                        if (
                            0 <= nx < width
                            and 0 <= ny < height
                            and ((nx, ny) in changed)
                            and ((nx, ny) not in visited)
                        ):
                            visited.add((nx, ny))
                            stack.append((nx, ny))
                if count >= Constants.min_region_pixels:
                    regions.append(
                        Rect(
                            x=float(min_x),
                            y=float(min_y),
                            width=float(max_x - min_x + 1),
                            height=float(max_y - min_y + 1),
                        ),
                    )
        return tuple(regions)

    def _change_nodes(
        self,
        image_a: Image.Image,
        image_b: Image.Image,
        elements_a: tuple[ElementInfo, ...],
        affected: tuple[ElementInfo, ...],
    ) -> tuple[ChangeNode, ...]:
        """Build classified changed-element nodes for graph construction.

        Args:
        image_a: Value for image a.
        image_b: Value for image b.
        elements_a: Value for elements a.
        affected: Value for affected.

        Returns:
        Result produced by  change nodes.

        """
        by_a: dict[str, ElementInfo] = {
            element.selector: element for element in elements_a
        }
        mask: Image.Image = self._difference_mask(
            image_a=image_a,
            image_b=image_b,
        ).convert(mode="L")
        return tuple(
            node
            for after in affected
            for before in (by_a.get(after.selector),)
            if before is not None
            for node in (
                self._change_node(before=before, after=after, mask=mask),
            )
            if node is not None
        )

    def _change_node(
        self,
        before: ElementInfo,
        after: ElementInfo,
        mask: Image.Image,
    ) -> ChangeNode | None:
        """Classify one element's visual and computed-style changes.

        Args:
            before: Side-A element snapshot.
            after: Side-B element snapshot.
            mask: Thresholded pixel-difference mask.

        Returns:
            Classified change node, or None when nothing changed.

        """
        position_changed: bool = (
            after.rect.x != before.rect.x or after.rect.y != before.rect.y
        )
        size_changed: bool = (
            after.rect.width != before.rect.width
            or after.rect.height != before.rect.height
        )
        groups: dict[str, dict[str, StyleChange]] = {
            name: {}
            for name in (
                "layout",
                "box_model",
                "typography",
                "color",
                "paint",
                "transform",
                "visibility",
                "stacking",
                "other",
            )
        }
        for name, value in after.computed.items():
            previous: str = before.computed.get(name, "")
            if previous == value:
                continue
            group: str = self._style_group(name=name)
            groups[group][name] = StyleChange(a=previous, b=value)
        categories: tuple[str, ...] = tuple(
            (
                category
                for category, present in (
                    ("position", position_changed),
                    ("size", size_changed),
                    ("color", bool(groups["color"])),
                    (
                        "style",
                        any(
                            (
                                values
                                for name, values in groups.items()
                                if name != "color"
                            ),
                        ),
                    ),
                )
                if present
            ),
        )
        if not categories:
            return None
        origins: list[str] = []
        mechanisms: list[str] = []
        if groups["layout"] or groups["box_model"]:
            origins.append("computed-style")
            mechanisms.append("layout")
        if groups["typography"]:
            origins.append("computed-style")
            mechanisms.append("text-reflow")
        if groups["color"] or groups["paint"]:
            origins.append("computed-style")
            mechanisms.append("paint")
        if groups["transform"]:
            origins.append("computed-style")
            mechanisms.append("transform")
        if groups["stacking"]:
            origins.append("computed-style")
            mechanisms.append("stacking")
        if position_changed and (
            not (
                groups["layout"] or groups["box_model"] or groups["transform"]
            )
        ):
            origins.append("propagated")
            mechanisms.append("layout-reflow")
        return ChangeNode(
            selector=after.selector,
            categories=categories,
            origins=tuple(dict.fromkeys(origins or ["propagated"])),
            mechanisms=tuple(dict.fromkeys(mechanisms or ["unknown"])),
            geometry={
                "position": {
                    "a_x": before.rect.x,
                    "a_y": before.rect.y,
                    "b_x": after.rect.x,
                    "b_y": after.rect.y,
                    "delta_x": after.rect.x - before.rect.x,
                    "delta_y": after.rect.y - before.rect.y,
                },
                "size": {
                    "a_width": before.rect.width,
                    "a_height": before.rect.height,
                    "b_width": after.rect.width,
                    "b_height": after.rect.height,
                    "delta_width": after.rect.width - before.rect.width,
                    "delta_height": after.rect.height - before.rect.height,
                },
            },
            computed_style_changes=groups,
            changed_pixels=self._pixels_in_rect(mask=mask, rect=after.rect),
        )

    def _function_provenance(
        self,
        browser: Browser,
        nodes: tuple[ChangeNode, ...],
        rules: tuple[RuleInfo, ...],
        elements_a: tuple[ElementInfo, ...],
        rules_a: tuple[RuleInfo, ...],
    ) -> dict[str, list[dict[str, JsonValue]]]:
        """Test exact CSS value nodes with aligned A-side source replacements.

        Args:
        browser: Value for browser.
        nodes: Value for nodes.
        rules: Value for rules.
        elements_a: Value for elements a.
        rules_a: Value for rules a.

        Returns:
        Result produced by  function provenance.

        """
        by_a: dict[str, ElementInfo] = {
            item.selector: item for item in elements_a
        }
        a_rules: dict[int, RuleInfo] = {rule.index: rule for rule in rules_a}
        output: dict[str, list[dict[str, JsonValue]]] = {
            node.selector: [] for node in nodes
        }
        for node in nodes:
            if not self._budget_available():
                break
            reference: ElementInfo | None = by_a.get(node.selector)
            if reference is None:
                continue
            baseline_element: ElementInfo = self._element_by_selector(
                elements=self._last_elements_b,
                selector=node.selector,
            )
            baseline: float = self._element_distance(
                reference=reference,
                candidate=baseline_element,
            )
            if baseline <= 0.0:
                continue
            trial: ProvenanceTrial = ProvenanceTrial(
                browser=browser,
                reference=reference,
                baseline=baseline,
            )
            for rule in rules:
                a_rule: RuleInfo | None = a_rules.get(rule.index)
                if node.selector not in rule.matched or a_rule is None:
                    continue
                output[node.selector].extend(
                    self._function_rule_provenance(
                        trial=trial,
                        node=node,
                        rule=rule,
                        a_rule=a_rule,
                    ),
                )
            output[node.selector].sort(
                key=lambda item: (
                    -self._json_float(value=item.get("confidence", 0.0))
                ),
            )
        return output

    def _function_rule_provenance(
        self,
        trial: ProvenanceTrial,
        node: ChangeNode,
        rule: RuleInfo,
        a_rule: RuleInfo,
    ) -> list[dict[str, JsonValue]]:
        """Test one rule's B declarations against aligned A values.

        Args:
            trial: Per-node counterfactual context.
            node: Changed rendered DOM node.
            rule: Side-B flattened CSS rule.
            a_rule: Aligned side-A rule with the same index.

        Returns:
            Value-fragment evidence for this rule.

        """
        a_declarations: dict[str, str] = {}
        for declaration in a_rule.declarations:
            name, value = self._declaration_parts(declaration=declaration)
            if name:
                a_declarations[name] = value
        results: list[dict[str, JsonValue]] = []
        for declaration in rule.declarations:
            property_name, _ = self._declaration_parts(declaration=declaration)
            a_value: str | None = a_declarations.get(property_name)
            if not property_name or a_value is None:
                continue
            results.extend(
                self._value_fragment_trials(
                    trial=trial,
                    node=node,
                    rule=rule,
                    declaration=declaration,
                    a_value=a_value,
                ),
            )
        return results

    def _value_fragment_trials(
        self,
        trial: ProvenanceTrial,
        node: ChangeNode,
        rule: RuleInfo,
        declaration: str,
        a_value: str,
    ) -> list[dict[str, JsonValue]]:
        """Intervene on each changed CSS value fragment in a declaration.

        Args:
            trial: Per-node counterfactual context.
            node: Changed rendered DOM node.
            rule: Side-B flattened CSS rule.
            declaration: Side-B authored declaration.
            a_value: Aligned side-A authored value.

        Returns:
            Evidence for each token-level counterfactual that improved.

        """
        property_name, b_value = self._declaration_parts(
            declaration=declaration,
        )
        a_nodes: tuple[ValueNode, ...] = CssValueParser.walk(
            node=CssValueParser.parse(value=a_value),
        )
        b_nodes: tuple[ValueNode, ...] = CssValueParser.walk(
            node=CssValueParser.parse(value=b_value),
        )
        results: list[dict[str, JsonValue]] = []
        for index, b_node in enumerate(iterable=b_nodes):
            if (
                b_node.kind == "value"
                or index >= len(a_nodes)
                or a_nodes[index].kind != b_node.kind
                or (a_nodes[index].text == b_node.text)
            ):
                continue
            a_node: ValueNode = a_nodes[index]
            rewritten: str = CssValueParser.replace(
                value=b_value,
                node=b_node,
                replacement=a_node.text,
            )
            trial_css: str = (
                f"{rule.selector} {{ {property_name}: {rewritten} "
                "!important; }"
            )
            _, trial_elements, _ = self._render(
                browser=trial.browser,
                css=self.css_b + "\n" + trial_css,
                intervention=Intervention(),
                side="b",
            )
            try:
                trial_element: ElementInfo = self._element_by_selector(
                    elements=trial_elements,
                    selector=node.selector,
                )
            except KeyError:
                continue
            improvement: float = trial.baseline - self._element_distance(
                reference=trial.reference,
                candidate=trial_element,
            )
            if improvement <= 0.0:
                continue
            results.append(
                {
                    "rule_index": rule.index,
                    "selector": rule.selector,
                    "property": property_name,
                    "kind": b_node.kind,
                    "span": {"start": b_node.start, "end": b_node.end},
                    "a": a_node.text,
                    "b": b_node.text,
                    "authored_a": a_value,
                    "authored_b": b_value,
                    "counterfactual_value": rewritten,
                    "improvement": improvement,
                    "confidence": min(1.0, improvement / trial.baseline),
                    "role": "source-aligned-token-intervention",
                },
            )
        return results

    def _cascade_provenance(
        self,
        browser: Browser,
        nodes: tuple[ChangeNode, ...],
    ) -> dict[str, JsonValue]:
        """Capture Chromium cascade, inheritance, pseudos, and keyframes.

        Args:
        browser: Value for browser.
        nodes: Value for nodes.

        Returns:
        Result produced by  cascade provenance.

        """
        context: BrowserContext = browser.new_context(
            viewport={
                "width": self.settings.width,
                "height": self.settings.height,
            },
            device_scale_factor=self.settings.screenshot_scale,
            reduced_motion="reduce",
        )
        page: Page = context.new_page()
        output: dict[str, JsonValue] = {}
        try:
            self._navigate(
                page=page,
                url=self.settings.url_b or self.settings.url,
            )
            page.evaluate(expression=self._INSTALL_HELPERS_JS)
            self._install_extended_selector(page=page)
            page.evaluate(
                expression=self._PREPARE_JS,
                arg=self.settings.use_native_styles_b,
            )
            page.locator(selector="#__css_cause_style__").evaluate(
                expression="(node, css) => { node.textContent = css; }",
                arg=self.css_b,
            )
            page.evaluate(expression="() => document.fonts.ready")
            session: CDPSession = context.new_cdp_session(page=page)
            send: CdpSender = cast(typ="CdpSender", val=session.send)
            send(method="DOM.enable")
            send(method="CSS.enable")
            document_value: JsonValue = cast(
                typ="JsonValue",
                val=loads(
                    s=dumps(
                        obj=send(
                            method="DOM.getDocument",
                            params={"depth": -1},
                        ),
                    ),
                ),
            )
            if not isinstance(document_value, dict):
                return output
            document: dict[str, JsonValue] = document_value
            root: JsonValue = document.get("root")
            if not isinstance(root, dict):
                return output
            root_id: JsonValue = root.get("nodeId")
            if not isinstance(root_id, int):
                return output
            for node in nodes:
                if "#shadow-root" in node.selector:
                    continue
                try:
                    query_value: JsonValue = cast(
                        typ="JsonValue",
                        val=loads(
                            s=dumps(
                                obj=send(
                                    method="DOM.querySelector",
                                    params={
                                        "nodeId": root_id,
                                        "selector": node.selector,
                                    },
                                ),
                            ),
                        ),
                    )
                    if not isinstance(query_value, dict):
                        continue
                    node_id: JsonValue = query_value.get("nodeId")
                    if not isinstance(node_id, int) or node_id == 0:
                        continue
                    matched: JsonValue = cast(
                        typ="JsonValue",
                        val=loads(
                            s=dumps(
                                obj=send(
                                    method="CSS.getMatchedStylesForNode",
                                    params={"nodeId": node_id},
                                ),
                            ),
                        ),
                    )
                    computed_value: JsonValue = cast(
                        typ="JsonValue",
                        val=loads(
                            s=dumps(
                                obj=send(
                                    method="CSS.getComputedStyleForNode",
                                    params={"nodeId": node_id},
                                ),
                            ),
                        ),
                    )
                    computed: dict[str, JsonValue] = (
                        computed_value
                        if isinstance(computed_value, dict)
                        else {}
                    )
                    output[node.selector] = cast(
                        typ="JsonValue",
                        val=loads(
                            s=dumps(
                                obj={
                                    "source": "chromium-cdp",
                                    "matched": matched,
                                    "computed": computed.get(
                                        "computedStyle",
                                        [],
                                    ),
                                },
                            ),
                        ),
                    )
                except (Error, ValueError, TypeError) as error:
                    output[node.selector] = {
                        "source": "chromium-cdp",
                        "error": str(object=error),
                    }
            return output
        finally:
            context.close()

    def _minimal_cause_sets(
        self,
        browser: Browser,
        nodes: tuple[ChangeNode, ...],
        rules: tuple[RuleInfo, ...],
        elements_a: tuple[ElementInfo, ...],
    ) -> dict[str, list[dict[str, JsonValue]]]:
        """Minimize declaration sets across ancestor/descendant/sibling rules.

        Args:
        browser: Value for browser.
        nodes: Value for nodes.
        rules: Value for rules.
        elements_a: Value for elements a.

        Returns:
        Result produced by  minimal cause sets.

        """
        by_a: dict[str, ElementInfo] = {
            element.dom_path: element for element in elements_a
        }
        result: dict[str, list[dict[str, JsonValue]]] = {}
        for node in nodes[:12]:
            baseline_element: ElementInfo = self._element_by_selector(
                elements=self._last_elements_b,
                selector=node.selector,
            )
            reference: ElementInfo | None = by_a.get(baseline_element.dom_path)
            if reference is None:
                continue
            baseline: float = self._element_distance(
                reference=reference,
                candidate=baseline_element,
            )
            if baseline <= 0.0:
                continue
            reference_element: ElementInfo = reference
            candidates: tuple[tuple[int, str], ...] = tuple(
                (
                    (rule.index, name)
                    for rule in rules
                    for declaration in rule.declarations
                    for name, _ in (
                        self._declaration_parts(declaration=declaration),
                    )
                    if name
                    and (rule.selector in node.selector or rule.matched)
                ),
            )[:18]
            if not candidates:
                continue

            def evaluate(
                items: tuple[tuple[int, str], ...],
                *,
                selector: str = node.selector,
                base: float = baseline,
                reference: ElementInfo = reference_element,
            ) -> float:
                """Measure normalized improvement for a declaration set.

                Args:
                items: Value for items.
                selector: Value for selector.
                base: Value for base.
                reference: Value for reference.

                Returns:
                Result produced by evaluate.

                """
                _, elements, _ = self._render(
                    browser=browser,
                    css=self.css_b,
                    intervention=Intervention(disabled_declarations=items),
                    side="b",
                )
                try:
                    trial: ElementInfo = self._element_by_selector(
                        elements=elements,
                        selector=selector,
                    )
                except KeyError:
                    return 0.0
                return max(
                    0.0,
                    (
                        base
                        - self._element_distance(
                            reference=reference,
                            candidate=trial,
                        )
                    )
                    / base,
                )

            minimizer: CausalMinimizer = CausalMinimizer(
                evaluate=evaluate,
                budget=32,
                threshold=0.6,
            )
            minimum: CauseSet | None = minimizer.minimize(
                candidates=candidates,
            )
            if minimum is not None:
                result[node.selector] = [
                    {
                        "members": [
                            {"rule_index": index, "property": name}
                            for index, name in minimum.members
                        ],
                        "improvement": minimum.improvement,
                        "confidence": minimum.confidence,
                        "evaluations": minimum.evaluations,
                        "minimal_within_budget": minimum.minimal_within_budget,
                    },
                ]
        return result

    def _interaction_provenance(
        self,
        browser: Browser,
        nodes: tuple[ChangeNode, ...],
        rules: tuple[RuleInfo, ...],
        elements_a: tuple[ElementInfo, ...],
        singles: dict[str, list[dict[str, JsonValue]]],
    ) -> dict[str, list[dict[str, JsonValue]]]:
        """Discover declaration combinations with non-additive causal effects.

        Args:
        browser: Value for browser.
        nodes: Value for nodes.
        rules: Value for rules.
        elements_a: Value for elements a.
        singles: Value for singles.

        Returns:
        Result produced by  interaction provenance.

        """
        by_a: dict[str, ElementInfo] = {
            element.selector: element for element in elements_a
        }
        output: dict[str, list[dict[str, JsonValue]]] = {
            node.selector: [] for node in nodes
        }
        for node in nodes:
            if not self._budget_available():
                break
            reference: ElementInfo | None = by_a.get(node.selector)
            if reference is None:
                continue
            baseline_element: ElementInfo = self._element_by_selector(
                elements=self._last_elements_b,
                selector=node.selector,
            )
            baseline: float = self._element_distance(
                reference=reference,
                candidate=baseline_element,
            )
            if baseline <= 0.0:
                continue
            candidates: list[tuple[int, str, str, str]] = (
                self._interaction_candidates(node=node, rules=rules)
            )
            single_score: dict[tuple[int, str], float] = {}
            for result in singles.get(node.selector, []):
                rule_index: JsonValue = result.get("rule_index")
                property_name: JsonValue = result.get("property")
                improvement: JsonValue = result.get("improvement")
                if (
                    isinstance(rule_index, int)
                    and isinstance(property_name, str)
                    and isinstance(improvement, int | float)
                ):
                    single_score[rule_index, property_name] = float(
                        improvement,
                    )
            trial: ProvenanceTrial = ProvenanceTrial(
                browser=browser,
                reference=reference,
                baseline=baseline,
            )
            for left_index in range(len(candidates)):
                for right_index in range(left_index + 1, len(candidates)):
                    evidence: dict[str, JsonValue] | None = (
                        self._interaction_trial(
                            trial=trial,
                            node=node,
                            left=candidates[left_index],
                            right=candidates[right_index],
                            single_score=single_score,
                        )
                    )
                    if evidence is not None:
                        output[node.selector].append(evidence)
            output[node.selector].sort(
                key=lambda item: (
                    self._json_float(value=item["confidence"]),
                    self._json_float(value=item["synergy"]),
                ),
                reverse=True,
            )
        return output

    def _interaction_candidates(
        self,
        node: ChangeNode,
        rules: tuple[RuleInfo, ...],
    ) -> list[tuple[int, str, str, str]]:
        """Collect and prioritize matched declaration candidates.

        Args:
            node: Changed rendered DOM node.
            rules: Side-B flattened CSS rules.

        Returns:
            Bounded candidates as rule-index/selector/property/value tuples.

        """
        candidates: list[tuple[int, str, str, str]] = []
        for rule in rules:
            if node.selector not in rule.matched:
                continue
            for declaration in rule.declarations:
                property_name, value = self._declaration_parts(
                    declaration=declaration,
                )
                if property_name:
                    candidates.append(
                        (rule.index, rule.selector, property_name, value),
                    )
        changed_properties: set[str] = {
            name
            for changes in node.computed_style_changes.values()
            for name in changes
        }
        candidates.sort(
            key=lambda item: (
                item[2] not in changed_properties,
                item[0],
                item[2],
            ),
        )
        return candidates[:12]

    def _interaction_trial(
        self,
        trial: ProvenanceTrial,
        node: ChangeNode,
        left: tuple[int, str, str, str],
        right: tuple[int, str, str, str],
        single_score: dict[tuple[int, str], float],
    ) -> dict[str, JsonValue] | None:
        """Measure synergy from disabling one declaration pair.

        Args:
            trial: Per-node counterfactual context.
            node: Changed rendered DOM node.
            left: First declaration candidate tuple.
            right: Second declaration candidate tuple.
            single_score: Single-declaration improvements by pair key.

        Returns:
            Interaction evidence, or None when no synergy was observed.

        """
        _, trial_elements, _ = self._render(
            browser=trial.browser,
            css=self.css_b,
            intervention=Intervention(
                disabled_declarations=(
                    (left[0], left[2]),
                    (right[0], right[2]),
                ),
            ),
            side="b",
        )
        try:
            trial_element: ElementInfo = self._element_by_selector(
                elements=trial_elements,
                selector=node.selector,
            )
        except KeyError:
            return None
        joint: float = trial.baseline - self._element_distance(
            reference=trial.reference,
            candidate=trial_element,
        )
        if joint <= 0.0:
            return None
        left_score: float = single_score.get((left[0], left[2]), 0.0)
        right_score: float = single_score.get((right[0], right[2]), 0.0)
        synergy: float = joint - max(left_score, right_score)
        if synergy <= 0.0:
            return None
        return {
            "kind": "interaction",
            "members": [
                {
                    "rule_index": left[0],
                    "selector": left[1],
                    "property": left[2],
                    "authored_value": left[3],
                    "individual_improvement": left_score,
                },
                {
                    "rule_index": right[0],
                    "selector": right[1],
                    "property": right[2],
                    "authored_value": right[3],
                    "individual_improvement": right_score,
                },
            ],
            "joint_improvement": joint,
            "synergy": synergy,
            "confidence": min(1.0, joint / trial.baseline),
        }

    def _causal_edges(
        self,
        browser: Browser,
        nodes: tuple[ChangeNode, ...],
        elements_a: tuple[ElementInfo, ...],
    ) -> dict[str, list[dict[str, JsonValue]]]:
        """Infer element-to-element causal edges with interventions.

        Args:
        browser: Value for browser.
        nodes: Value for nodes.
        elements_a: Value for elements a.

        Returns:
        Result produced by  causal edges.

        """
        by_a: dict[str, ElementInfo] = {
            element.selector: element for element in elements_a
        }
        edges: dict[str, list[dict[str, JsonValue]]] = {
            node.selector: [] for node in nodes
        }
        for source in nodes:
            before: ElementInfo | None = by_a.get(source.selector)
            if before is None:
                continue
            restore: dict[str, str] = {}
            for changes in source.computed_style_changes.values():
                restore.update(
                    {name: change.a for name, change in changes.items()},
                )
            if not restore:
                continue
            _, trial_elements, _ = self._render(
                browser=browser,
                css=self.css_b,
                intervention=Intervention(
                    element_override=(source.selector, restore),
                ),
                side="b",
            )
            trial_by_selector: dict[str, ElementInfo] = {
                element.selector: element for element in trial_elements
            }
            for target in nodes:
                if target.selector == source.selector:
                    continue
                target_a: ElementInfo | None = by_a.get(target.selector)
                trial: ElementInfo | None = trial_by_selector.get(
                    target.selector,
                )
                if target_a is None or trial is None:
                    continue
                baseline: float = self._element_distance(
                    reference=target_a,
                    candidate=self._element_by_selector(
                        elements=self._last_elements_b,
                        selector=target.selector,
                    ),
                )
                improved: float = baseline - self._element_distance(
                    reference=target_a,
                    candidate=trial,
                )
                if baseline <= 0.0 or improved <= 0.0:
                    continue
                edges[target.selector].append(
                    cast(
                        typ="dict[str, JsonValue]",
                        val={
                            "selector": source.selector,
                            "relationship": self._relationship(
                                source=source.selector,
                                target=target.selector,
                                elements=self._last_elements_b,
                            ),
                            "mechanisms": list(source.mechanisms),
                            "improvement": improved,
                            "confidence": min(1.0, improved / baseline),
                        },
                    ),
                )
        for values in edges.values():
            values.sort(
                key=lambda edge: self._json_float(value=edge["confidence"]),
                reverse=True,
            )
        return edges

    def _change_forest(
        self,
        nodes: tuple[ChangeNode, ...],
        causes: tuple[Cause, ...],
        elements: tuple[ElementInfo, ...],
        elements_a: tuple[ElementInfo, ...],
        provenance: ProvenanceMaps,
    ) -> list[dict[str, JsonValue]]:
        """Serialize changed nodes as isolated, deduplicated relation trees.

        Args:
        nodes: Value for nodes.
        causes: Value for causes.
        elements: Value for elements.
        elements_a: Value for elements a.
        provenance: Causal provenance maps by selector.

        Returns:
        Result produced by  change forest.

        """
        by_selector: dict[str, ChangeNode] = {
            node.selector: node for node in nodes
        }
        element_by_selector: dict[str, ElementInfo] = {
            element.selector: element for element in elements
        }
        element_a_by_selector: dict[str, ElementInfo] = {
            element.selector: element for element in elements_a
        }
        children: dict[str, list[str]] = {
            selector: [] for selector in by_selector
        }
        parent_of: dict[str, str] = {}
        for selector in by_selector:
            parent: str = self._parent_selector(selector=selector)
            while parent:
                if parent in by_selector:
                    parent_of[selector] = parent
                    children[parent].append(selector)
                    break
                parent = self._parent_selector(selector=parent)
        roots: list[str] = [
            selector for selector in by_selector if selector not in parent_of
        ]
        consumed: set[str] = set()

        def serialize(selector: str) -> dict[str, JsonValue]:
            """Run serialize.

            Args:
            selector: Value for selector.

            Returns:
            Result produced by serialize.

            """
            consumed.add(selector)
            node: ChangeNode = by_selector[selector]
            direct_children: list[dict[str, JsonValue]] = [
                serialize(selector=child)
                for child in children[selector]
                if child not in consumed
            ]
            current: ElementInfo | None = element_by_selector.get(selector)
            sibling_refs, overlap_refs = self._tree_relations(
                selector=selector,
                by_selector=by_selector,
                parent_of=parent_of,
                current=current,
                element_by_selector=element_by_selector,
            )
            relevant_causes: list[dict[str, JsonValue]] = [
                cast(
                    typ="dict[str, JsonValue]",
                    val={
                        "selector": cause.selector,
                        "declarations": list(cause.declarations),
                        "pixels_explained": cause.pixels_explained,
                        "explanation_ratio": cause.explanation_ratio,
                    },
                )
                for cause in causes
                if selector in cause.matched
                or any(
                    relation.endswith(selector) for relation in cause.relations
                )
            ]
            return cast(
                typ="dict[str, JsonValue]",
                val={
                    "selector": selector,
                    "categories": list(node.categories),
                    "change_origin": list(node.origins),
                    "mechanisms": list(node.mechanisms),
                    "geometry": node.geometry,
                    "computed_style_changes": self._style_changes_json(
                        node=node,
                    ),
                    "causes": relevant_causes,
                    "css_provenance": provenance.declaration_provenance.get(
                        selector,
                        [],
                    ),
                    "css_value_provenance": provenance.function_provenance.get(
                        selector,
                        [],
                    ),
                    "cascade_provenance": provenance.cascade_provenance.get(
                        selector,
                    ),
                    "css_variables": {
                        "usage": self._last_variable_graph.get(selector, []),
                        "chains": self._variable_chains(
                            records=self._last_variable_graph.get(
                                selector,
                                [],
                            ),
                        ),
                    },
                    "interaction_causes": (
                        provenance.interaction_provenance.get(selector, [])
                    ),
                    "content_change": self._content_delta(
                        before=element_a_by_selector[selector],
                        after=current,
                    )
                    if current is not None
                    and selector in element_a_by_selector
                    else None,
                    "caused_by": provenance.causal_edges.get(selector, []),
                    "root_cause": self._strongest_root_cause(
                        singles=provenance.declaration_provenance.get(
                            selector,
                            [],
                        ),
                        interactions=provenance.interaction_provenance.get(
                            selector,
                            [],
                        ),
                        fallback=relevant_causes,
                    ),
                    "visual_impact": {"changed_pixels": node.changed_pixels},
                    "relations": {
                        "descendants": direct_children,
                        "siblings": sibling_refs,
                        "overlaps": overlap_refs,
                    },
                },
            )

        forest: list[dict[str, JsonValue]] = [
            serialize(selector=root) for root in roots if root not in consumed
        ]
        forest.extend(
            serialize(selector=selector)
            for selector in by_selector
            if selector not in consumed
        )
        return forest

    def _tree_relations(
        self,
        selector: str,
        by_selector: dict[str, ChangeNode],
        parent_of: dict[str, str],
        current: ElementInfo | None,
        element_by_selector: dict[str, ElementInfo],
    ) -> tuple[list[dict[str, JsonValue]], list[dict[str, JsonValue]]]:
        """Collect sibling and overlap references for one tree node.

        Args:
            selector: Generated selector of the current node.
            by_selector: Changed nodes keyed by selector.
            parent_of: Changed-node parent selector map.
            current: Side-B element for the current selector, when present.
            element_by_selector: Side-B elements keyed by selector.

        Returns:
            Sibling references and overlapping-element references.

        """
        sibling_refs: list[dict[str, JsonValue]] = []
        overlap_refs: list[dict[str, JsonValue]] = []
        parent: str = self._parent_selector(selector=selector)
        for other_selector in by_selector:
            if other_selector == selector:
                continue
            if (
                parent
                and self._parent_selector(selector=other_selector) == parent
                and (parent_of.get(other_selector) != selector)
                and (parent_of.get(selector) != other_selector)
            ):
                sibling_refs.append({"selector": other_selector})
            other_element: ElementInfo | None = element_by_selector.get(
                other_selector,
            )
            if (
                current is not None
                and other_element is not None
                and current.rect.intersects(other=other_element.rect)
                and (not other_selector.startswith(f"{selector} > "))
                and (not selector.startswith(f"{other_selector} > "))
            ):
                overlap_refs.append(
                    {
                        "selector": other_selector,
                        "position": other_element.position,
                        "z_index": other_element.z_index,
                        "paint_order": self._paint_order(
                            current=current,
                            other=other_element,
                        ),
                    },
                )
        return (sibling_refs, overlap_refs)

    def _rank_rules(
        self,
        rules: tuple[RuleInfo, ...],
        affected: tuple[ElementInfo, ...],
        elements: tuple[ElementInfo, ...],
    ) -> tuple[RuleInfo, ...]:
        """Prioritize rules with structural or geometric evidence.

        Args:
        rules: Value for rules.
        affected: Value for affected.
        elements: Value for elements.

        Returns:
        Result produced by  rank rules.

        """
        scored: list[tuple[int, RuleInfo]] = []
        for rule in rules:
            relations: tuple[str, ...] = self._relations(
                rule=rule,
                affected=affected,
                elements=elements,
            )
            score: int = sum(
                {
                    "self": 100,
                    "overlap": 80,
                    "ancestor": 60,
                    "sibling": 40,
                    "descendant": 30,
                }.get(relation.split(sep=":", maxsplit=1)[0], 0)
                for relation in relations
            )
            if score:
                scored.append((score, rule))
        scored.sort(key=lambda item: (-item[0], item[1].index))
        return tuple((rule for _, rule in scored))

    def _write_outputs(self, results: AnalysisResults) -> None:
        """Write JSON and annotated visual output.

        Args:
            results: Complete analyzer output bundle.

        """
        annotated: Image.Image = results.evidence_image_b.copy()
        draw: ImageDraw.ImageDraw = ImageDraw.Draw(im=annotated)
        for index, region in enumerate(iterable=results.regions, start=1):
            scale: float = self.settings.screenshot_scale
            draw.rectangle(
                xy=(
                    region.x * scale,
                    region.y * scale,
                    region.right * scale,
                    region.bottom * scale,
                ),
                outline="red",
                width=max(2, round(number=scale * 2)),
            )
            draw.text(
                xy=(region.x * scale + 3, region.y * scale + 3),
                text=str(object=index),
                fill="red",
            )
        annotated.save(fp=self.settings.output / "diff.png")
        structure: dict[str, JsonValue] = self._structural_analysis(
            image_a=results.analysis_image_a,
            image_b=results.analysis_image_b,
            regions=results.regions,
            elements=results.affected,
        )
        report: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val={
                "url": self.settings.url,
                "url_a": self.settings.url,
                "url_b": self.settings.url_b or self.settings.url,
                "native_styles": {
                    "a": self.settings.use_native_styles_a,
                    "b": self.settings.use_native_styles_b,
                },
                "target_a": self.target_a.manifest(),
                "target_b": self.target_b.manifest(),
                "css_a": str(object=self.target_a.source),
                "css_b": str(object=self.target_b.source),
                "baseline_changed_pixels": results.baseline,
                "screenshot_scale": self.settings.screenshot_scale,
                "structural_analysis": structure,
                "minimal_cause_sets": results.provenance.minimal_sets,
                "container_queries": self._last_container_queries,
                "regions": [asdict(obj=region) for region in results.regions],
                "affected_elements": [
                    {
                        "selector": element.selector,
                        "tag": element.tag,
                        "text": element.text,
                        "rect": asdict(obj=element.rect),
                        "position": element.position,
                        "z_index": element.z_index,
                    }
                    for element in results.affected
                ],
                "layout_evidence": [
                    {
                        "selector": current.selector,
                        "dom_path": current.dom_path,
                        "changes": LayoutEvidence.compare(
                            a=previous.computed,
                            b=current.computed,
                        ),
                        "resolved_grid_tracks": {
                            "columns": current.computed.get(
                                "grid-template-columns",
                                "",
                            ),
                            "rows": current.computed.get(
                                "grid-template-rows",
                                "",
                            ),
                        },
                        "container": {
                            "type": current.computed.get(
                                "container-type",
                                "normal",
                            ),
                            "name": current.computed.get(
                                "container-name",
                                "none",
                            ),
                            "width": current.rect.width,
                            "height": current.rect.height,
                        },
                    }
                    for current in results.affected
                    for previous in results.elements_a
                    if previous.dom_path == current.dom_path
                    and LayoutEvidence.compare(
                        a=previous.computed,
                        b=current.computed,
                    )
                ],
                "change_trees": self._change_forest(
                    nodes=results.nodes,
                    causes=results.causes,
                    elements=results.affected,
                    elements_a=results.elements_a,
                    provenance=results.provenance,
                ),
            },
        )
        (self.settings.output / "report.json").write_text(
            data=dumps(obj=report, indent=2),
            encoding="utf-8",
        )
        self._write_human_report(results=results, structure=structure)
        stdout.write(
            "\n".join(
                [
                    f"Changed pixels: {results.baseline}",
                    f"Visual regions: {len(results.regions)}",
                    f"Affected DOM elements: {len(results.affected)}",
                    f"Changed DOM nodes: {len(results.nodes)}",
                    f"Causal CSS rules: {len(results.causes)}",
                    f"Report: {self.settings.output / 'report.json'}",
                    "",
                ],
            ),
        )

    def _write_human_report(
        self,
        results: AnalysisResults,
        structure: dict[str, JsonValue],
    ) -> None:
        """Write an inverted CSS-first Markdown report with visual evidence.

        Args:
            results: Complete analyzer output bundle.
            structure: Structural image-analysis summary for the report.

        """
        evidence: Path = self.settings.output / "evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        state: ReportState = ReportState(
            evidence=evidence,
            crop_cache={},
            nodes_by_selector={node.selector: node for node in results.nodes},
            elements_b={
                element.selector: element for element in self._last_elements_b
            },
        )
        grouped: dict[int, dict[str, list[dict[str, JsonValue]]]] = (
            self._group_property_evidence(
                provenance=results.provenance.declaration_provenance,
            )
        )
        lines: list[str] = self._report_header()
        lines += self._report_overview(
            results=results,
            grouped=grouped,
            structure=structure,
        )
        lines += self._report_measures(
            grouped=grouped,
            node_count=len(results.nodes),
        )
        lines += self._report_files(
            results=results,
            grouped=grouped,
            state=state,
        )
        (self.settings.output / "report.md").write_text(
            data="\n".join(lines) + "\n",
            encoding="utf-8",
        )

    def _report_header(self) -> list[str]:
        """Build the report title and visual-overview section.

        Returns:
            Markdown lines for the report preamble.

        """
        return [
            "# CSS visual-causality report",
            "",
            "This is the CSS-first view of the same counterfactual evidence "
            "stored in `report.json`.",
            "",
            f"- URL A: `{self.settings.url}`",
            f"- URL B: `{self.settings.url_b or self.settings.url}`",
            f"- CSS target A: `{self.target_a.source}`",
            f"- CSS target B: `{self.target_b.source}`",
            "",
            "## Visual overview",
            "",
            "| Reference A | Changed B | Annotated changed regions |",
            "|---|---|---|",
            "| ![](a.png) | ![](b.png) | ![](diff.png) |",
            "",
        ]

    def _report_overview(
        self,
        results: AnalysisResults,
        grouped: dict[int, dict[str, list[dict[str, JsonValue]]]],
        structure: dict[str, JsonValue],
    ) -> list[str]:
        """Build executive-summary and structural-analysis sections.

        Args:
            results: Complete analyzer output bundle.
            grouped: Evidence grouped by rule index then property.
            structure: Structural image-analysis summary.

        Returns:
            Markdown lines for the overview sections.

        """
        identified, pairs, proven = self._evidence_metrics(grouped=grouped)
        changed_ratio: float = self._json_float(
            value=structure.get("changed_region_area_ratio", 0.0),
        )
        region_count: JsonValue = structure.get("changed_region_count", 0)
        region_area: JsonValue = structure.get("changed_region_area", 0)
        largest_area: JsonValue = structure.get("largest_region_area", 0)
        element_count: JsonValue = structure.get("affected_element_count", 0)
        lines: list[str] = [
            "## Executive summary",
            "",
            f"- **{len(results.nodes)}** rendered nodes changed.",
            f"- **{identified}** changed CSS properties were identified "
            "across "
            f"**{pairs}** changed element/property links.",
            f"- **{proven}** properties have declaration-level "
            "experimental "
            "support; the remainder are retained as changed matched "
            "candidates "
            "rather than hidden.",
            "- Structural change regions cover approximately "
            f"**{changed_ratio * 100.0:.2f}%** of the rendered canvas.",
            "- Evidence screenshots are captured at "
            f"**{self.settings.screenshot_scale:.1f}x device-pixel density** "
            "while causal pixel metrics remain normalized to CSS pixels.",
            "",
            "## Structural image analysis",
            "",
            "| Structural metric | Value |",
            "|---|---:|",
            f"| Changed regions | {region_count} |",
            f"| Changed-region area | {region_area} CSS px² |",
            f"| Changed canvas share | {changed_ratio * 100.0:.2f}% |",
            f"| Largest changed region | {largest_area} CSS px² |",
            f"| Affected rendered elements | {element_count} |",
            "",
        ]
        lines += self._report_alignment(
            alignment_value=structure.get("alignment_pairs", {}),
        )
        lines += self._report_repeated_geometry(
            repeated_value=structure.get("repeated_geometry_groups", []),
        )
        return lines

    def _report_measures(
        self,
        grouped: dict[int, dict[str, list[dict[str, JsonValue]]]],
        node_count: int,
    ) -> list[str]:
        """Build the summary-measures table and reading guide.

        Args:
            grouped: Evidence grouped by rule index then property.
            node_count: Number of changed DOM nodes observed.

        Returns:
            Markdown lines for the summary section.

        """
        identified, pairs, proven = self._evidence_metrics(grouped=grouped)
        supported_rules: int = sum(
            1
            for properties in grouped.values()
            if any(
                item.get("proven") is True
                for impacts in properties.values()
                for item in impacts
            )
        )
        return [
            "## Summary",
            "",
            "| Measure | Count |",
            "|---|---:|",
            f"| CSS files with causal evidence | {len(self.target_b.files)} |",
            f"| Changed rules represented | {len(grouped)} |",
            "| Rules with property-level experimental support | "
            f"{supported_rules} |",
            f"| Identified changed properties | {identified} |",
            "| Properties with declaration-level experimental support | "
            f"{proven} |",
            f"| Property → affected-element links | {pairs} |",
            f"| Changed DOM nodes observed | {node_count} |",
            "",
            "### How to read the evidence",
            "",
            "- **Explained visual delta** is a pixel count, not a percentage.",
            "- **Share of baseline visual delta** is the normalized causal "
            "score.",
            "- Zero/unchanged geometry is omitted instead of reporting "
            "`0 → 0`.",
            "- “Other contributing properties” contains experimentally "
            "observed interaction/minimal-set companions, not merely "
            "correlated styles.",
            "",
        ]

    def _report_files(
        self,
        results: AnalysisResults,
        grouped: dict[int, dict[str, list[dict[str, JsonValue]]]],
        state: ReportState,
    ) -> list[str]:
        """Build per-source-file rule and property sections.

        Args:
            results: Complete analyzer output bundle.
            grouped: Evidence grouped by rule index then property.
            state: Mutable report caches.

        Returns:
            Markdown lines for the per-file sections.

        """
        rules_by_index: dict[int, RuleInfo] = {
            rule.index: rule for rule in results.rules_b
        }
        file_for_rule: dict[int, Path] = self._rule_source_files(
            rules=results.rules_b,
            files=self.target_b.files,
        )
        target_source: Path | None = self.target_b.source
        if target_source is None:
            return []
        lines: list[str] = []
        for source_file in self.target_b.files:
            rule_indexes: list[int] = [
                index
                for index in sorted(grouped)
                if file_for_rule.get(index) == source_file
            ]
            if not rule_indexes:
                continue
            relative: str = (
                source_file.name
                if target_source.is_file()
                else source_file.relative_to(target_source).as_posix()
            )
            lines.extend([f"## `{relative}`", ""])
            for rule_index in rule_indexes:
                rule: RuleInfo | None = rules_by_index.get(rule_index)
                if rule is None:
                    continue
                lines.extend(
                    [
                        f"### Rule {rule_index}: `{rule.selector}`",
                        "",
                        "```css",
                        rule.css_text,
                        "```",
                        "",
                    ],
                )
                for property_name, impacts in grouped[rule_index].items():
                    lines.extend(
                        self._report_property(
                            results=results,
                            state=state,
                            rule_index=rule_index,
                            property_name=property_name,
                            impacts=impacts,
                        ),
                    )
        return lines

    def _report_property(
        self,
        results: AnalysisResults,
        state: ReportState,
        rule_index: int,
        property_name: str,
        impacts: list[dict[str, JsonValue]],
    ) -> list[str]:
        """Build one property section with its affected elements.

        Args:
            results: Complete analyzer output bundle.
            state: Mutable report caches.
            rule_index: Flattened rule index owning the property.
            property_name: Changed CSS property name.
            impacts: Per-element evidence for the property.

        Returns:
            Markdown lines for the property section.

        """
        authored: str = str(object=impacts[0].get("authored_value", ""))
        property_proven: bool = any(
            item.get("proven") is True for item in impacts
        )
        status: str = (
            "counterfactually proven"
            if property_proven
            else (
                "identified changed property; not independently proven "
                "sufficient"
            )
        )
        lines: list[str] = [
            f"#### `{property_name}: {authored}`",
            "",
            f"**Causal status:** {status}",
            "",
        ]
        for impact in impacts:
            lines.extend(
                self._report_impact(
                    results=results,
                    state=state,
                    rule_index=rule_index,
                    property_name=property_name,
                    impact=impact,
                ),
            )
        return lines

    def _report_impact(
        self,
        results: AnalysisResults,
        state: ReportState,
        rule_index: int,
        property_name: str,
        impact: dict[str, JsonValue],
    ) -> list[str]:
        """Build the evidence block for one affected element.

        Args:
            results: Complete analyzer output bundle.
            state: Mutable report caches.
            rule_index: Flattened rule index owning the property.
            property_name: Changed CSS property name.
            impact: Per-element evidence entry.

        Returns:
            Markdown lines for the affected-element block.

        """
        selector: str = str(object=impact["selector"])
        node: ChangeNode | None = state.nodes_by_selector.get(selector)
        element: ElementInfo | None = state.elements_b.get(selector)
        if node is None or element is None:
            return []
        if selector not in state.crop_cache:
            stem: str = self._safe_evidence_name(
                rule_index=0,
                property_name="element",
                selector=selector,
            )
            state.crop_cache[selector] = self._save_element_crops(
                image_a=results.evidence_image_a,
                image_b=results.evidence_image_b,
                element=element,
                evidence=state.evidence,
                stem=stem,
            )
        a_name, b_name, diff_name = state.crop_cache[selector]
        explained_pixels: float = self._json_float(
            value=impact.get("improvement", 0.0),
        )
        confidence: float = self._json_float(
            value=impact.get("confidence", 0.0),
        )
        baseline_pixels: float = (
            explained_pixels / confidence if confidence > 0.0 else 0.0
        )
        impact_percent: float = confidence * 100.0
        bounds: str = (
            f"x={element.rect.x:.1f}, y={element.rect.y:.1f}, "
            f"w={element.rect.width:.1f}, h={element.rect.height:.1f}"
        )
        contributors: list[str] = self._contributors_for(
            selector=selector,
            rule_index=rule_index,
            property_name=property_name,
            interactions=results.provenance.interaction_provenance,
            minimal_sets=results.provenance.minimal_sets,
        )
        contributor_text: str = (
            ", ".join(f"`{item}`" for item in contributors)
            if contributors
            else "none detected by the completed bounded experiments"
        )
        lines: list[str] = [
            f"##### Affected element `{selector}`",
            "",
            "| Metric | Evidence |",
            "|---|---:|",
            "| Explained visual delta | "
            f"**{round(number=explained_pixels):,} changed pixels** |",
            f"| Share of baseline visual delta | **{impact_percent:.1f}%** |",
            "| Baseline visual delta | "
            f"{round(number=baseline_pixels):,} changed pixels |",
            f"| Evidence score | {confidence:.3f} |",
            "| Impact classification | "
            f"{impact.get('impact_kind', 'unknown')} |",
            "",
            "> **Metric meaning:** for counterfactually proven properties, "
            "“explained visual delta” is the number of changed pixels removed "
            "when this declaration is counterfactually disabled. The "
            "percentage is that reduction divided by the original A/B "
            "changed-pixel count.",
            "",
            self._human_change_summary(node=node),
            "",
            f"**Rendered bounds (B):** `{bounds}`",
            "",
            "###### Visual evidence",
            "",
            "| A — reference | B — changed | Absolute pixel difference |",
            "|---|---|---|",
            f"| ![]({a_name}) | ![]({b_name}) | ![]({diff_name}) |",
            "",
            "**Other contributing properties:** " + contributor_text,
            "",
        ]
        tokens: list[dict[str, JsonValue]] = [
            item
            for item in results.provenance.function_provenance.get(
                selector,
                [],
            )
            if item.get("rule_index") == rule_index
            and item.get("property") == property_name
        ]
        if tokens:
            lines.extend(["**Causal value fragments:**", ""])
            lines.extend(
                f"- `{token.get('b', '')}` → `{token.get('a', '')}` "
                "(confidence "
                f"{self._json_float(value=token.get('confidence', 0.0)):.3f})"
                for token in tokens[:8]
            )
            lines.append("")
        return lines

    def _rule_source_files(
        self,
        rules: tuple[RuleInfo, ...],
        files: tuple[Path, ...],
    ) -> dict[int, Path]:
        """Map flattened CSSOM rules back to concatenated target files.

        Args:
        rules: Value for rules.
        files: Value for files.

        Returns:
        Result produced by  rule source files.

        """
        output: dict[int, Path] = {}
        if not files:
            return output
        if self.target_b.source is None:
            return output
        combined: str = self.css_b
        markers: list[tuple[int, Path]] = []
        for file in files:
            relative: str = (
                file.name
                if self.target_b.source.is_file()
                else file.relative_to(self.target_b.source).as_posix()
            )
            marker: str = f"/* css-visual-cause source: {relative} */"
            position: int = combined.find(marker)
            if position >= 0:
                markers.append((position, file))
        markers.sort(key=lambda item: item[0])
        search_from: int = 0
        for rule in rules:
            position = combined.find(rule.css_text, search_from)
            if position < 0:
                position = combined.find(rule.selector, search_from)
            if position < 0:
                continue
            search_from = position + 1
            candidates: list[Path] = [
                file
                for marker_position, file in markers
                if marker_position <= position
            ]
            output[rule.index] = candidates[-1] if candidates else files[0]
        return output

    def _save_element_crops(
        self,
        image_a: Image.Image,
        image_b: Image.Image,
        element: ElementInfo,
        evidence: Path,
        stem: str,
    ) -> tuple[str, str, str]:
        """Save padded A/B/diff crops for one affected rendered element.

        Args:
        image_a: Value for image a.
        image_b: Value for image b.
        element: Value for element.
        evidence: Value for evidence.
        stem: Value for stem.

        Returns:
        Result produced by  save element crops.

        """
        scale: float = self.settings.screenshot_scale
        padding: int = round(number=12 * scale)
        left: int = max(0, round(number=element.rect.x * scale) - padding)
        top: int = max(0, round(number=element.rect.y * scale) - padding)
        right: int = min(
            image_b.width,
            max(left + 1, round(number=element.rect.right * scale) + padding),
        )
        bottom: int = min(
            image_b.height,
            max(top + 1, round(number=element.rect.bottom * scale) + padding),
        )
        box: tuple[int, int, int, int] = (left, top, right, bottom)
        crop_a: Image.Image = image_a.crop(box=box)
        crop_b: Image.Image = image_b.crop(box=box)
        crop_diff: Image.Image = ImageChops.difference(
            image1=crop_a,
            image2=crop_b,
        )
        a_path: Path = evidence / f"{stem}-a.png"
        b_path: Path = evidence / f"{stem}-b.png"
        diff_path: Path = evidence / f"{stem}-diff.png"
        crop_a.save(fp=a_path)
        crop_b.save(fp=b_path)
        crop_diff.save(fp=diff_path)
        return (
            a_path.relative_to(self.settings.output).as_posix(),
            b_path.relative_to(self.settings.output).as_posix(),
            diff_path.relative_to(self.settings.output).as_posix(),
        )


def _validated_url(value: str) -> str:
    """Validate a browser target URL.

    Args:
    value: Value for value.

    Returns:
    Result produced by  validated url.

    Raises:
    ValueError: If the operation cannot be completed.

    """
    parsed: SplitResult = urlsplit(url=value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        msg: str = "URL must use http:// or https://."
        raise ValueError(msg)
    return value


def _settings() -> Settings:
    """Parse command-line settings.

    Returns:
    Result produced by  settings.

    Raises:
    ValueError: If the operation cannot be completed.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        description=(
            "Render one URL with two CSS targets (files or directories) and "
            "experimentally identify which CSS rules cause the visual "
            "differences."
        ),
    )
    parser.add_argument("url")
    parser.add_argument("css_a", type=Path)
    parser.add_argument("css_b", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("css-cause"))
    parser.add_argument("--width", type=int, default=Constants.default_width)
    parser.add_argument("--height", type=int, default=Constants.default_height)
    parser.add_argument(
        "--threshold",
        type=int,
        default=Constants.default_threshold,
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=Constants.default_max_candidates,
    )
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument(
        "--url-b",
        default=None,
        help=(
            "Optional B URL. Omit to compare both CSS targets on the same URL."
        ),
    )
    parser.add_argument(
        "--native-styles-a",
        action="store_true",
        help="Keep URL A's native author styles before applying target A.",
    )
    parser.add_argument(
        "--native-styles-b",
        action="store_true",
        help="Keep URL B's native author styles before applying target B.",
    )
    parser.add_argument("--parallel-workers", type=int, default=4)
    parser.add_argument("--recycle-after", type=int, default=24)
    parser.add_argument("--screenshot-scale", type=float, default=2.0)
    parser.add_argument(
        "--no-extended-selectors",
        action="store_false",
        dest="extended_selectors",
        help=(
            "Do not install the packaged extended-selector engine; use only "
            "native querySelectorAll for selector queries."
        ),
    )
    arguments: Namespace = parser.parse_args()
    url: str = _validated_url(value=cast(typ="str", val=arguments.url))
    css_a: Path = cast(typ="Path", val=arguments.css_a)
    css_b: Path = cast(typ="Path", val=arguments.css_b)
    output: Path = cast(typ="Path", val=arguments.output)
    width: int = cast(typ="int", val=arguments.width)
    height: int = cast(typ="int", val=arguments.height)
    threshold: int = cast(typ="int", val=arguments.threshold)
    max_candidates: int = cast(typ="int", val=arguments.max_candidates)
    timeout_ms: int = cast(typ="int", val=arguments.timeout_ms)
    screenshot_scale: float = cast(typ="float", val=arguments.screenshot_scale)
    CssTarget.load(source=css_a)
    CssTarget.load(source=css_b)
    invalid_message: str | None = (
        "Width, height, timeout, and screenshot scale must be positive."
        if width < 1
        or height < 1
        or timeout_ms < 1
        or (screenshot_scale <= 0.0)
        else "Threshold must be 0..255 and max-candidates must be positive."
        if not 0 <= threshold <= Constants.max_threshold or max_candidates < 1
        else None
    )
    if invalid_message is not None:
        msg: str = invalid_message
        raise ValueError(msg)
    url_b: str | None = cast(typ="str | None", val=arguments.url_b)
    return Settings(
        url=url,
        css_a=css_a,
        css_b=css_b,
        output=output,
        width=width,
        height=height,
        threshold=threshold,
        max_candidates=max_candidates,
        timeout_ms=timeout_ms,
        url_b=None if url_b is None else _validated_url(value=url_b),
        use_native_styles_a=cast(typ="bool", val=arguments.native_styles_a),
        use_native_styles_b=cast(typ="bool", val=arguments.native_styles_b),
        parallel_workers=cast(typ="int", val=arguments.parallel_workers),
        recycle_after=cast(typ="int", val=arguments.recycle_after),
        screenshot_scale=screenshot_scale,
        extended_selectors=cast(typ="bool", val=arguments.extended_selectors),
    )


def analyze(
    *,
    settings: Settings,
    progress: ProgressObserver | None = None,
) -> AnalysisResults:
    """Run one visual-cause analysis and return its structured result.

    Args:
        settings: Validated engine configuration.
        progress: Optional observer called for every progress update.

    Returns:
        The same analysis result used to write the engine report.

    """
    return CssVisualCause(settings=settings, progress=progress).run()


def main() -> None:
    """Run the command-line analyzer."""
    CssVisualCause(settings=_settings()).run()


if __name__ == "__main__":
    main()
