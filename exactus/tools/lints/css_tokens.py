# Copyright (c) 2026
"""Audit the CSS custom-property architecture and terminal-layer policy.

Stylesheets are expected to form a five-layer token graph and to consume it
only at the last layer:

``PRIMARY``
    ``--primary-*``: literal inputs, no references and no functions.
``DYNAMIC``
    ``--dynamic-*``: literal inputs supplied at run time, same rules.
``BASE``
    ``--base-*``: derived from ``PRIMARY`` and ``DYNAMIC`` only.
``CATALOG``
    ``--catalog-<component>-<domain>-<rule>``: derived from ``BASE`` only.
``SEMANTIC``
    every other custom property: exactly one plain ``CATALOG`` reference.

Ordinary declarations (the terminal layer) may consume ``SEMANTIC``
variables only, and design-bearing properties must be exactly one
``var()`` reference. The scan is cross-file: definitions and references
are resolved over the whole audited stylesheet set, so one file's token
may be defined in another.

Findings carry stable ``CSS1xx`` identifiers (see ``Constants.rules``); the
``CSS0xx`` identifiers belong to the per-file value conventions in
``core.py``.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from enum import StrEnum
from re import IGNORECASE, Match, Pattern, fullmatch, search
from re import compile as compile_pattern
from re import sub as substitute
from typing import TYPE_CHECKING, Final

from exactus.packages.steps import trace

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path


class Layer(StrEnum):
    """Custom-property architecture layers.

    Attributes:
        PRIMARY: Primitive literal values.
        DYNAMIC: Runtime-provided values.
        BASE: Reusable values derived from primitives.
        CATALOG: Generic component specifications consuming ``BASE``.
        SEMANTIC: Component-facing aliases consuming ``CATALOG``.

    """

    PRIMARY = "primary"
    DYNAMIC = "dynamic"
    BASE = "base"
    CATALOG = "catalog"
    SEMANTIC = "semantic"


class Constants:
    """CSS token audit constants.

    Attributes:
        rules: Short name of each ``CSS1xx`` rule.
        var_reference: ``var(--name`` reference pattern.
        design_function: Functions barred from terminal declarations.
        design_literal: Hardcoded measure, color and function literals.
        provenance: Token names that encode generation provenance.
        numeric_suffix: Numeric collision suffix of a token name.
        special: Start of a comment, string, escape or ``url(``.
        important: Trailing ``!important`` marker.
        property_name: Shape of a declaration's property name.
        var_open: Start of a ``var(`` call.
        analysis_limit: Longest value text the patterns examine.
        message_limit: Longest value text echoed in a finding.
        blanks: Whitespace that may precede a ``url(`` argument.
        function_call: Any CSS function start.
        color_mix: ``color-mix(`` function start.
        identity_calc: ``calc()`` multiplying by BASE zero or one.
        noncanonical_scale: Scale abbreviations outside the BASE vocabulary.
        plain_reference: One plain ``var()`` reference.
        catalog_reference: One plain ``var(--catalog-*)`` reference.
        bare_number: Bare numeric literal.
        design_properties: Properties whose value is a design specification
            and must be exactly one SEMANTIC reference.
        grammar_properties: Structural and behavioral grammar properties.
            Their keywords may stay literal; their operands are still
            checked for design literals and functions.
        configurable_numeric: Numeric-valued properties that must be tokens.
        catalog_domains: Known second segments of a CATALOG name.
        allowed_base_references: Layers a BASE token may reference.
        min_catalog_segments: Fewest dash-separated CATALOG name segments.
        css_wide_keywords: Keywords every property accepts. A custom property
            cannot carry one (it would apply to the custom property itself), so
            a declaration may hold one directly.

    """

    rules: Final[dict[str, str]] = {
        "CSS100": "unreadable-stylesheet",
        "CSS101": "duplicate-definition",
        "CSS102": "undefined-variable",
        "CSS103": "non-semantic-token-name",
        "CSS104": "primary-keyword-token",
        "CSS105": "primary-percent-scale",
        "CSS106": "primary-duration-scale",
        "CSS107": "primary-font-weight-scale",
        "CSS108": "literal-layer-reference",
        "CSS109": "literal-layer-function",
        "CSS110": "invalid-base-dependency",
        "CSS111": "invalid-catalog-dependency",
        "CSS112": "catalog-color-derivation",
        "CSS113": "catalog-identity-calculation",
        "CSS114": "catalog-name-shape",
        "CSS115": "catalog-domain-first",
        "CSS116": "catalog-domain-missing",
        "CSS117": "catalog-noncanonical-scale",
        "CSS118": "catalog-context-leak",
        "CSS119": "invalid-semantic-dependency",
        "CSS120": "semantic-composition",
        "CSS121": "terminal-layer-bypass",
        "CSS122": "terminal-design-function",
        "CSS123": "terminal-token-required",
        "CSS124": "terminal-design-literal",
        "CSS125": "terminal-configurable-number",
    }
    var_reference: Final[Pattern[str]] = compile_pattern(
        pattern=r"var\(\s*(--[^\s,)]+)",
        flags=IGNORECASE,
    )
    design_function: Final[Pattern[str]] = compile_pattern(
        pattern=(
            r"(?<![-\w])(calc|min|max|clamp|minmax|color-mix|repeat)\s*\("
        ),
        flags=IGNORECASE,
    )
    design_literal: Final[Pattern[str]] = compile_pattern(
        pattern=(
            r"(?<![\w.-])[+-]?(?:\d*\.\d+|\d+)(?:e[+-]?\d+)?"
            r"(?:px|rem|em|ch|ex|cap|ic|lh|rlh|"
            r"vw|vh|vi|vb|vmin|vmax|svw|svh|lvw|lvh|dvw|dvh|cm|mm|q|in|pt|pc|"
            r"deg|grad|rad|turn|ms|s|%)\b|"
            r"#[0-9a-f]{3,8}\b|"
            r"\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch)\s*\("
        ),
        flags=IGNORECASE,
    )
    provenance: Final[Pattern[str]] = compile_pattern(
        pattern=(
            r"(?:^|-)(?:derived|generated|autogenerated|auto-generated)"
            r"(?:-|$)|(?:^|-)\b[0-9a-f]{8,}\b(?:-|$)"
        ),
        flags=IGNORECASE,
    )
    numeric_suffix: Final[Pattern[str]] = compile_pattern(pattern=r"-\d+$")
    special: Final[Pattern[str]] = compile_pattern(
        pattern=r"/\*|[\"'\\]|(?<![\w-])url\(",
        flags=IGNORECASE,
    )
    important: Final[Pattern[str]] = compile_pattern(
        pattern=r"\s*!\s*important\s*$",
        flags=IGNORECASE,
    )
    property_name: Final[Pattern[str]] = compile_pattern(
        pattern=r"[*_]?[^\s{};()\"'@:,<>=!/&#.\[\]+~]+",
    )
    var_open: Final[Pattern[str]] = compile_pattern(
        pattern=r"(?<![\w-])var\(",
        flags=IGNORECASE,
    )
    analysis_limit: Final[int] = 16384
    message_limit: Final[int] = 120
    blanks: Final[str] = " \t\r\n\f"
    function_call: Final[Pattern[str]] = compile_pattern(
        pattern=r"[A-Za-z_-][A-Za-z0-9_-]*\s*\(",
    )
    color_mix: Final[Pattern[str]] = compile_pattern(
        pattern=r"\bcolor-mix\s*\(",
        flags=IGNORECASE,
    )
    identity_calc: Final[Pattern[str]] = compile_pattern(
        pattern=(
            r"calc\([^)]*(?:\*\s*var\(\s*--base-number-(?:one|zero)\s*\)|"
            r"var\(\s*--base-number-(?:one|zero)\s*\)\s*\*)"
        ),
        flags=IGNORECASE,
    )
    noncanonical_scale: Final[Pattern[str]] = compile_pattern(
        pattern=r"(?:^|-)(?:[2-9]xl|[2-9]xs|sm|md|lg)(?:-|$)",
        flags=IGNORECASE,
    )
    plain_reference: Final[Pattern[str]] = compile_pattern(
        pattern=r"var\(\s*(--[^\s,)]+)\s*\)",
        flags=IGNORECASE,
    )
    catalog_reference: Final[Pattern[str]] = compile_pattern(
        pattern=r"var\(\s*--catalog-[^\s,)]+\s*\)",
        flags=IGNORECASE,
    )
    bare_number: Final[Pattern[str]] = compile_pattern(
        pattern=r"(?<![\w.-])[+-]?(?:\d*\.\d+|\d+)(?![\w.%-])",
    )
    design_properties: Final[frozenset[str]] = frozenset(
        {
            "-webkit-border-before",
            "-webkit-box-reflect",
            "-webkit-mask-box-image",
            "-webkit-mask-position-x",
            "-webkit-mask-position-y",
            "-webkit-tap-highlight-color",
            "-webkit-text-fill-color",
            "-webkit-text-stroke",
            "-webkit-text-stroke-color",
            "-webkit-text-stroke-width",
            "accent-color",
            "animation",
            "animation-delay",
            "animation-duration",
            "animation-iteration-count",
            "animation-timing-function",
            "aspect-ratio",
            "backdrop-filter",
            "background",
            "background-color",
            "background-image",
            "background-position",
            "background-position-x",
            "background-position-y",
            "background-size",
            "baseline-shift",
            "block-size",
            "border",
            "border-block",
            "border-block-color",
            "border-block-end",
            "border-block-end-color",
            "border-block-end-width",
            "border-block-start",
            "border-block-start-color",
            "border-block-start-width",
            "border-block-width",
            "border-bottom",
            "border-bottom-color",
            "border-bottom-left-radius",
            "border-bottom-right-radius",
            "border-bottom-width",
            "border-color",
            "border-end-end-radius",
            "border-end-start-radius",
            "border-image",
            "border-image-outset",
            "border-image-slice",
            "border-image-source",
            "border-image-width",
            "border-inline",
            "border-inline-color",
            "border-inline-end",
            "border-inline-end-color",
            "border-inline-end-width",
            "border-inline-start",
            "border-inline-start-color",
            "border-inline-start-width",
            "border-inline-width",
            "border-left",
            "border-left-color",
            "border-left-width",
            "border-radius",
            "border-right",
            "border-right-color",
            "border-right-width",
            "border-spacing",
            "border-start-end-radius",
            "border-start-start-radius",
            "border-top",
            "border-top-color",
            "border-top-left-radius",
            "border-top-right-radius",
            "border-top-width",
            "border-width",
            "bottom",
            "box-shadow",
            "caret",
            "caret-color",
            "clip",
            "clip-path",
            "color",
            "column-count",
            "column-gap",
            "column-height",
            "column-rule",
            "column-rule-color",
            "column-rule-width",
            "column-width",
            "columns",
            "contain-intrinsic-block-size",
            "contain-intrinsic-height",
            "contain-intrinsic-inline-size",
            "contain-intrinsic-size",
            "contain-intrinsic-width",
            "content",
            "corner-block-end-shape",
            "corner-block-start-shape",
            "corner-bottom-left-shape",
            "corner-bottom-right-shape",
            "corner-bottom-shape",
            "corner-end-end-shape",
            "corner-end-start-shape",
            "corner-inline-end-shape",
            "corner-inline-start-shape",
            "corner-left-shape",
            "corner-right-shape",
            "corner-shape",
            "corner-start-end-shape",
            "corner-start-start-shape",
            "corner-top-left-shape",
            "corner-top-right-shape",
            "corner-top-shape",
            "cursor",
            "cx",
            "cy",
            "d",
            "dynamic-range-limit",
            "fill",
            "fill-opacity",
            "filter",
            "flex",
            "flex-basis",
            "flex-grow",
            "flex-shrink",
            "flood-color",
            "flood-opacity",
            "font",
            "font-family",
            "font-feature-settings",
            "font-optical-sizing",
            "font-palette",
            "font-size",
            "font-size-adjust",
            "font-stretch",
            "font-style",
            "font-variation-settings",
            "font-weight",
            "font-width",
            "gap",
            "grid",
            "grid-area",
            "grid-auto-columns",
            "grid-auto-rows",
            "grid-column",
            "grid-column-end",
            "grid-column-start",
            "grid-row",
            "grid-row-end",
            "grid-row-start",
            "grid-template",
            "grid-template-areas",
            "grid-template-columns",
            "grid-template-rows",
            "height",
            "hyphenate-character",
            "inline-size",
            "inset",
            "inset-block",
            "inset-block-end",
            "inset-block-start",
            "inset-inline",
            "inset-inline-end",
            "inset-inline-start",
            "interest-delay",
            "interest-delay-end",
            "interest-delay-start",
            "left",
            "letter-spacing",
            "lighting-color",
            "line-clamp",
            "line-height",
            "line-height-step",
            "list-style",
            "list-style-image",
            "margin",
            "margin-block",
            "margin-block-end",
            "margin-block-start",
            "margin-bottom",
            "margin-inline",
            "margin-inline-end",
            "margin-inline-start",
            "margin-left",
            "margin-right",
            "margin-top",
            "marker",
            "marker-end",
            "marker-mid",
            "marker-start",
            "mask",
            "mask-border",
            "mask-border-outset",
            "mask-border-slice",
            "mask-border-source",
            "mask-border-width",
            "mask-image",
            "mask-position",
            "mask-size",
            "math-depth",
            "max-block-size",
            "max-height",
            "max-inline-size",
            "max-width",
            "min-block-size",
            "min-height",
            "min-inline-size",
            "min-width",
            "object-position",
            "object-view-box",
            "offset",
            "offset-anchor",
            "offset-distance",
            "offset-path",
            "offset-position",
            "offset-rotate",
            "opacity",
            "order",
            "outline",
            "outline-color",
            "outline-offset",
            "outline-width",
            "overflow-clip-margin",
            "padding",
            "padding-block",
            "padding-block-end",
            "padding-block-start",
            "padding-bottom",
            "padding-inline",
            "padding-inline-end",
            "padding-inline-start",
            "padding-left",
            "padding-right",
            "padding-top",
            "path-length",
            "perspective",
            "perspective-origin",
            "position-area",
            "quotes",
            "r",
            "reading-order",
            "right",
            "rotate",
            "row-gap",
            "rx",
            "ry",
            "scale",
            "scroll-margin",
            "scroll-margin-block",
            "scroll-margin-block-end",
            "scroll-margin-block-start",
            "scroll-margin-bottom",
            "scroll-margin-inline",
            "scroll-margin-inline-end",
            "scroll-margin-inline-start",
            "scroll-margin-left",
            "scroll-margin-right",
            "scroll-margin-top",
            "scroll-padding",
            "scroll-padding-block",
            "scroll-padding-block-end",
            "scroll-padding-block-start",
            "scroll-padding-bottom",
            "scroll-padding-inline",
            "scroll-padding-inline-end",
            "scroll-padding-inline-start",
            "scroll-padding-left",
            "scroll-padding-right",
            "scroll-padding-top",
            "scrollbar-color",
            "scrollbar-gutter",
            "scrollbar-width",
            "shape-image-threshold",
            "shape-margin",
            "shape-outside",
            "stop-color",
            "stop-opacity",
            "stroke",
            "stroke-dasharray",
            "stroke-dashoffset",
            "stroke-miterlimit",
            "stroke-opacity",
            "stroke-width",
            "tab-size",
            "text-decoration",
            "text-decoration-color",
            "text-decoration-inset",
            "text-decoration-style",
            "text-decoration-thickness",
            "text-emphasis",
            "text-emphasis-color",
            "text-emphasis-position",
            "text-emphasis-style",
            "text-indent",
            "text-overflow",
            "text-shadow",
            "text-size-adjust",
            "text-underline-offset",
            "top",
            "transform",
            "transform-origin",
            "transition",
            "transition-delay",
            "transition-duration",
            "transition-timing-function",
            "translate",
            "vertical-align",
            "view-timeline-inset",
            "width",
            "word-spacing",
            "x",
            "y",
            "z-index",
            "zoom",
        },
    )
    grammar_properties: Final[frozenset[str]] = frozenset(
        {
            "-moz-float-edge",
            "-moz-force-broken-image-icon",
            "-moz-orient",
            "-moz-user-focus",
            "-moz-user-input",
            "-webkit-mask-composite",
            "-webkit-mask-repeat-x",
            "-webkit-mask-repeat-y",
            "-webkit-text-security",
            "-webkit-touch-callout",
            "alignment-baseline",
            "all",
            "anchor-name",
            "anchor-scope",
            "animation-composition",
            "animation-direction",
            "animation-fill-mode",
            "animation-name",
            "animation-play-state",
            "animation-range",
            "animation-range-end",
            "animation-range-start",
            "animation-timeline",
            "appearance",
            "backface-visibility",
            "background-attachment",
            "background-blend-mode",
            "background-clip",
            "background-origin",
            "background-repeat",
            "background-repeat-x",
            "background-repeat-y",
            "baseline-source",
            "border-block-end-style",
            "border-block-start-style",
            "border-block-style",
            "border-bottom-style",
            "border-image-repeat",
            "border-inline-end-style",
            "border-inline-start-style",
            "border-inline-style",
            "border-left-style",
            "border-right-style",
            "border-style",
            "border-top-style",
            "box-decoration-break",
            "break-after",
            "break-before",
            "break-inside",
            "caption-side",
            "caret-animation",
            "caret-shape",
            "clear",
            "clip-rule",
            "color-interpolation",
            "color-interpolation-filters",
            "color-scheme",
            "column-fill",
            "column-rule-style",
            "column-span",
            "column-wrap",
            "contain",
            "container",
            "container-name",
            "container-type",
            "counter-increment",
            "counter-reset",
            "counter-set",
            "direction",
            "dominant-baseline",
            "empty-cells",
            "field-sizing",
            "fill-rule",
            "flex-flow",
            "float",
            "font-kerning",
            "font-language-override",
            "font-smooth",
            "font-synthesis",
            "font-synthesis-position",
            "font-synthesis-small-caps",
            "font-synthesis-style",
            "font-synthesis-weight",
            "font-variant",
            "font-variant-alternates",
            "font-variant-caps",
            "font-variant-east-asian",
            "font-variant-emoji",
            "font-variant-ligatures",
            "font-variant-numeric",
            "font-variant-position",
            "forced-color-adjust",
            "grid-auto-flow",
            "hanging-punctuation",
            "hyphenate-limit-chars",
            "hyphens",
            "image-orientation",
            "image-rendering",
            "image-resolution",
            "initial-letter",
            "interactivity",
            "interpolate-size",
            "line-break",
            "list-style-position",
            "list-style-type",
            "margin-trim",
            "mask-border-mode",
            "mask-border-repeat",
            "mask-clip",
            "mask-composite",
            "mask-mode",
            "mask-origin",
            "mask-repeat",
            "mask-type",
            "math-shift",
            "math-style",
            "mix-blend-mode",
            "object-fit",
            "orphans",
            "outline-style",
            "overflow-anchor",
            "overflow-block",
            "overflow-inline",
            "overflow-wrap",
            "overlay",
            "overscroll-behavior",
            "overscroll-behavior-block",
            "overscroll-behavior-inline",
            "overscroll-behavior-x",
            "overscroll-behavior-y",
            "page",
            "page-break-after",
            "page-break-before",
            "page-break-inside",
            "paint-order",
            "place-content",
            "place-items",
            "place-self",
            "position-anchor",
            "position-try",
            "position-try-fallbacks",
            "position-try-order",
            "position-visibility",
            "print-color-adjust",
            "reading-flow",
            "resize",
            "ruby-align",
            "ruby-overhang",
            "ruby-position",
            "scroll-behavior",
            "scroll-initial-target",
            "scroll-marker-group",
            "scroll-snap-align",
            "scroll-snap-stop",
            "scroll-snap-type",
            "scroll-target-group",
            "scroll-timeline",
            "scroll-timeline-axis",
            "scroll-timeline-name",
            "scrollbar-gutter",
            "scrollbar-width",
            "shape-rendering",
            "speak-as",
            "stroke-linecap",
            "stroke-linejoin",
            "table-layout",
            "text-align-last",
            "text-anchor",
            "text-autospace",
            "text-box",
            "text-box-edge",
            "text-box-trim",
            "text-combine-upright",
            "text-decoration-line",
            "text-decoration-skip",
            "text-decoration-skip-ink",
            "text-decoration-style",
            "text-emphasis-position",
            "text-justify",
            "text-orientation",
            "text-overflow",
            "text-rendering",
            "text-spacing-trim",
            "text-transform",
            "text-underline-position",
            "text-wrap",
            "text-wrap-mode",
            "text-wrap-style",
            "timeline-scope",
            "touch-action",
            "transform-box",
            "transform-style",
            "transition-behavior",
            "transition-property",
            "unicode-bidi",
            "user-modify",
            "vector-effect",
            "view-timeline",
            "view-timeline-axis",
            "view-timeline-name",
            "view-transition-class",
            "view-transition-name",
            "white-space-collapse",
            "widows",
            "will-change",
            "word-break",
            "writing-mode",
        },
    )
    configurable_numeric: Final[frozenset[str]] = frozenset(
        {
            "column-count",
            "columns",
            "fill-opacity",
            "flex-grow",
            "flex-shrink",
            "grid-area",
            "grid-column",
            "grid-column-end",
            "grid-column-start",
            "grid-row",
            "grid-row-end",
            "grid-row-start",
            "opacity",
            "order",
            "orphans",
            "stroke-opacity",
            "stroke-width",
            "widows",
            "z-index",
        },
    )
    catalog_domains: Final[frozenset[str]] = frozenset(
        {
            "measure",
            "typography",
            "color",
            "border",
            "cursor",
            "effect",
            "motion",
        },
    )
    allowed_base_references: Final[frozenset[Layer]] = frozenset(
        {Layer.PRIMARY, Layer.DYNAMIC},
    )
    min_catalog_segments: Final[int] = 3
    css_wide_keywords: Final[frozenset[str]] = frozenset(
        {"inherit", "initial", "unset", "revert", "revert-layer"},
    )


@dataclass(frozen=True, slots=True)
class CssTokenInput:
    """Carry the inputs of one CSS token audit.

    Attributes:
        root: Project root the file paths are reported against.
        files: Stylesheets to audit, as one set.
        context_words: Concrete application or component words that must
            not appear in CATALOG names.

    """

    root: Path
    files: Sequence[Path]
    context_words: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class CssTokenFinding:
    """One token-architecture violation.

    Attributes:
        rule: Stable ``CSS1xx`` identifier.
        file: Stylesheet the declaration is in.
        line: One-based line of the declaration.
        message: Human-readable violation description.

    """

    rule: str
    file: Path
    line: int
    message: str


@dataclass(frozen=True, slots=True)
class CssDeclaration:
    """One parsed CSS declaration.

    Attributes:
        name: Property name as written.
        value: Declaration value as written, comments removed.
        masked: Value with strings and unquoted ``url()`` bodies blanked,
            cut to ``Constants.analysis_limit``; the text every check reads.
        file: Stylesheet the declaration is in.
        line: One-based line of the declaration.
        scope: The selectors and at-rules the declaration is nested in,
            outermost first, whitespace normalized.

    """

    name: str
    value: str
    masked: str
    file: Path
    line: int
    scope: str = ""

    @property
    def is_custom(self) -> bool:
        """Report whether the declaration defines a custom property.

        Returns:
            ``True`` for a ``--name`` property.

        """
        return self.name.startswith("--")


@dataclass(frozen=True, slots=True)
class CssSource:
    """One stylesheet after lexing.

    Attributes:
        clean: The text with comments blanked, line structure intact.
        masked: ``clean`` with strings and unquoted ``url()`` bodies
            blanked and escape sequences neutralized, so no delimiter
            inside them can be taken for structure.
        newlines: Offset of every line break.

    """

    clean: str
    masked: str
    newlines: tuple[int, ...]

    def line(self, *, offset: int) -> int:
        """Return the one-based line holding an offset.

        Args:
            offset: Character offset into the text.

        Returns:
            The line number, found by bisection.

        """
        return bisect_right(a=self.newlines, x=offset) + 1


def layer_of(*, name: str) -> Layer:
    """Return the architecture layer a custom-property name belongs to.

    Args:
        name: Custom-property name, including the leading dashes.

    Returns:
        The layer named by the property prefix; every unprefixed name is
        ``SEMANTIC``.

    """
    if name.startswith("--primary-"):
        return Layer.PRIMARY
    if name.startswith("--dynamic-"):
        return Layer.DYNAMIC
    if name.startswith("--base-"):
        return Layer.BASE
    if name.startswith("--catalog-"):
        return Layer.CATALOG
    return Layer.SEMANTIC


def _contains_run(*, parts: list[str], run: tuple[str, ...]) -> bool:
    """Report whether a name holds a run of words contiguously.

    Args:
        parts: Words of a token name.
        run: Words that must appear next to each other, in order.

    Returns:
        ``True`` when ``run`` is a contiguous slice of ``parts``.

    """
    width: int = len(run)
    return any(
        tuple(parts[start : start + width]) == run
        for start in range(len(parts) - width + 1)
    )


def _clip(*, value: str) -> str:
    """Shorten a value for display in a finding message.

    Args:
        value: Declaration value.

    Returns:
        ``value``, or its first ``Constants.message_limit`` characters
        followed by an ellipsis.

    """
    if len(value) <= Constants.message_limit:
        return value
    return value[: Constants.message_limit] + "…"


def _unimportant(*, value: str) -> str:
    """Drop a trailing ``!important`` so a plain reference stays plain.

    Args:
        value: Declaration value.

    Returns:
        ``value`` without the priority marker, surrounding blanks trimmed.

    """
    return Constants.important.sub(repl="", string=value).strip()


def _without_var_calls(*, value: str) -> str:
    """Remove every ``var()`` call, whatever it nests.

    Args:
        value: Declaration value.

    Returns:
        The remaining text, pieces separated by one space. An unclosed call
        removes the rest of the value.

    """
    pieces: list[str] = []
    position: int = 0
    size: int = len(value)
    while True:
        match: Match[str] | None = Constants.var_open.search(
            string=value,
            pos=position,
        )
        if match is None:
            pieces.append(value[position:])
            return " ".join(pieces)
        pieces.append(value[position : match.start()])
        depth: int = 1
        position = match.end()
        while position < size and depth:
            depth += (value[position] == "(") - (value[position] == ")")
            position += 1


def _blank(*, text: str, fill: str = " ") -> str:
    """Replace every character by a filler, keeping the line breaks.

    Args:
        text: Text to blank.
        fill: Replacement for each character that is not a line break.

    Returns:
        A string of the same length and line structure.

    """
    return "".join("\n" if char == "\n" else fill for char in text)


def _string_end(*, text: str, start: int) -> int:
    """Return where a quoted string ends.

    A backslash escapes the next character, an unescaped line break ends
    an unterminated string (CSS strings do not span lines), and the end of
    the text ends one that is never closed.

    Args:
        text: Stylesheet text.
        start: Offset of the opening quote.

    Returns:
        The offset just past the string.

    """
    quote: str = text[start]
    size: int = len(text)
    index: int = start + 1
    while index < size:
        char: str = text[index]
        if char == "\\":
            index += 2
        elif char == quote:
            return index + 1
        elif char == "\n":
            return index
        else:
            index += 1
    return size


def _url_end(*, text: str, start: int) -> int:
    """Return where the body of an unquoted ``url()`` ends.

    Args:
        text: Stylesheet text.
        start: Offset just past the opening parenthesis.

    Returns:
        The offset of the closing parenthesis, or the end of the text.

    """
    size: int = len(text)
    index: int = start
    while index < size:
        char: str = text[index]
        if char == "\\":
            index += 2
        elif char == ")":
            return index
        else:
            index += 1
    return size


def lex(*, text: str) -> CssSource:
    """Separate a stylesheet's structure from its comments and strings.

    One linear pass. Comments (an unterminated one runs to the end of the
    text), quoted strings and the bodies of unquoted ``url()`` are blanked
    in the structural view, and an escape sequence is neutralized, so a
    ``;``, brace or parenthesis inside any of them never splits a
    declaration. The structural view always has the length and line
    structure of ``text``.

    Args:
        text: Stylesheet text.

    Returns:
        The cleaned and masked views with the line-break offsets.

    """
    clean: list[str] = []
    masked: list[str] = []
    size: int = len(text)
    position: int = 0
    while position < size:
        match: Match[str] | None = Constants.special.search(
            string=text,
            pos=position,
        )
        if match is None:
            clean.append(text[position:])
            masked.append(text[position:])
            break
        plain: str = text[position : match.start()]
        clean.append(plain)
        masked.append(plain)
        opener: str = match.group()
        if opener == "/*":
            close: int = text.find("*/", match.end())
            end: int = size if close < 0 else close + 2
            clean.append(_blank(text=text[match.start() : end]))
            masked.append(_blank(text=text[match.start() : end]))
        elif opener == "\\":
            end = min(match.end() + 1, size)
            clean.append(text[match.start() : end])
            masked.append(_blank(text=text[match.start() : end], fill="_"))
        elif opener[0] in "\"'":
            end = _string_end(text=text, start=match.start())
            clean.append(text[match.start() : end])
            masked.append(_blank(text=text[match.start() : end]))
        else:
            end = match.end()
            ahead: int = end
            while ahead < size and text[ahead] in Constants.blanks:
                ahead += 1
            quoted: bool = ahead < size and text[ahead] in "\"'"
            clean.append(opener)
            masked.append(opener)
            if not quoted:
                end = _url_end(text=text, start=match.end())
                clean.append(text[match.end() : end])
                masked.append(_blank(text=text[match.end() : end]))
        position = end
    offsets: list[int] = []
    found: int = text.find("\n")
    while found >= 0:
        offsets.append(found)
        found = text.find("\n", found + 1)
    return CssSource(
        clean="".join(clean),
        masked="".join(masked),
        newlines=tuple(offsets),
    )


def _segment(
    *,
    source: CssSource,
    start: int,
    end: int,
    file: Path,
    scope: str = "",
) -> tuple[CssDeclaration, ...]:
    """Parse one declaration-sized source segment.

    Args:
        source: The lexed stylesheet.
        start: Offset of the segment start.
        end: Offset of the segment end.
        file: Stylesheet the text was read from.
        scope: Enclosing selectors and at-rules.

    Returns:
        The declaration, located at its first character rather than at the
        end of the previous statement, or nothing for a segment that is
        not one: an at-rule, a segment without a colon, or a name that
        cannot be a property.

    """
    chunk: str = source.clean[start:end]
    shadow: str = source.masked[start:end]
    colon: int = shadow.find(":")
    if colon < 0 or shadow.lstrip().startswith("@"):
        return ()
    name: str = chunk[:colon].strip()
    value: str = chunk[colon + 1 :].strip()
    if (
        not value
        or fullmatch(pattern=Constants.property_name, string=name) is None
    ):
        return ()
    return (
        CssDeclaration(
            name=name,
            value=value,
            masked=shadow[colon + 1 :].strip()[: Constants.analysis_limit],
            file=file,
            line=source.line(offset=start + len(chunk) - len(chunk.lstrip())),
            scope=scope,
        ),
    )


def _separators(*, masked: str) -> Iterator[tuple[int, str]]:
    """Yield the characters that structure a stylesheet.

    Braces and semicolons inside parentheses belong to a value, so they are
    not structural there. Malformed input degrades locally: a stray ``)``
    is ignored, and a ``}`` that closes no brace opened inside the
    parentheses ends a value left open by an unbalanced ``(``, so one typo
    cannot hide the rest of the file.

    Args:
        masked: Structural view of the stylesheet.

    Yields:
        ``(offset, character)`` for each ``{``, ``}`` and ``;`` that
        structures the stylesheet.

    """
    parens: int = 0
    inner: int = 0
    index: int
    char: str
    for index, char in enumerate(iterable=masked):
        if char == "(":
            parens += 1
        elif not parens:
            if char in "{};":
                yield index, char
        elif char == ")":
            parens -= 1
            inner = inner if parens else 0
        elif char == "{":
            inner += 1
        elif char == "}":
            if inner:
                inner -= 1
            else:
                parens = 0
                yield index, char


def parse_declarations(*, text: str, file: Path) -> list[CssDeclaration]:
    """Parse the declarations of one stylesheet.

    A statement ends at the ``}`` closing its block, or at a ``;`` inside
    one; a final statement missing its terminator is kept. Each
    declaration records the chain of selectors and at-rules around it.

    Args:
        text: Stylesheet text.
        file: Stylesheet the text was read from.

    Returns:
        Declarations in source order.

    """
    source: CssSource = lex(text=text)
    declarations: list[CssDeclaration] = []
    scopes: list[str] = []
    statement_start: int = 0
    index: int
    char: str
    for index, char in _separators(masked=source.masked):
        if char == "{":
            scopes.append(
                " ".join(source.clean[statement_start:index].split()),
            )
        elif scopes:
            declarations.extend(
                _segment(
                    source=source,
                    start=statement_start,
                    end=index,
                    file=file,
                    scope=" | ".join(scopes),
                ),
            )
            if char == "}":
                scopes.pop()
        statement_start = index + 1
    if scopes:
        declarations.extend(
            _segment(
                source=source,
                start=statement_start,
                end=len(source.masked),
                file=file,
                scope=" | ".join(scopes),
            ),
        )
    return declarations


class CssTokenAudit:
    """Audit a stylesheet set against the token architecture.

    Attributes:
        inputs: The audited set and its configuration.
        declarations: Every declaration of every file.
        definitions: Custom-property definitions by name.
        findings: Violations in discovery order.
        context_words: CATALOG name words that are forbidden.
        component_names: Component directory names, as word runs, that
            CATALOG names must not contain.

    """

    def __init__(self, *, inputs: CssTokenInput) -> None:
        """Parse the stylesheet set and audit it immediately.

        Args:
            inputs: The audited set and its configuration.

        """
        self.inputs: CssTokenInput = inputs
        self.findings: list[CssTokenFinding] = []
        self.declarations: list[CssDeclaration] = []
        trace(
            step=f"css tokens: parsing {len(set(inputs.files))} files",
            depth=3,
        )
        for file in sorted(set(inputs.files)):
            declarations: list[CssDeclaration] = self._read(file=file)
            self.declarations.extend(declarations)
            trace(
                step=(
                    f"css tokens: {file} — {len(declarations)} declarations"
                ),
                depth=4,
            )
        self.definitions: dict[str, list[CssDeclaration]] = {}
        for declaration in self.declarations:
            if declaration.is_custom:
                self.definitions.setdefault(declaration.name, []).append(
                    declaration,
                )
        self.context_words: frozenset[str] = frozenset(
            word.lower() for word in inputs.context_words
        )
        self.component_names: frozenset[tuple[str, ...]] = (
            self._component_names()
        )
        trace(
            step=(
                f"css tokens: {len(self.definitions)} definitions, "
                f"{len(self.component_names)} component names"
            ),
            depth=3,
        )
        self._duplicate_definitions()
        trace(step="css tokens: references check", depth=3)
        self._references()
        trace(step="css tokens: custom-property layers check", depth=3)
        self._custom_properties()
        trace(step="css tokens: terminal declarations check", depth=3)
        self._terminal_declarations()

    @staticmethod
    def _plain_semantic_reference(*, value: str) -> bool:
        """Report whether a value is one plain SEMANTIC reference.

        Args:
            value: Declaration value.

        Returns:
            ``True`` for exactly one ``var(--name)`` of the SEMANTIC layer.

        """
        match: Match[str] | None = fullmatch(
            pattern=Constants.plain_reference,
            string=value,
        )
        return (
            match is not None
            and layer_of(name=match.group(1)) is Layer.SEMANTIC
        )

    @staticmethod
    def _has_bare_number(*, value: str) -> bool:
        """Report whether a value holds a bare numeric literal.

        Args:
            value: Declaration value with strings masked.

        Returns:
            ``True`` when a number outside ``var()`` has no unit.

        """
        return (
            search(
                pattern=Constants.bare_number,
                string=_without_var_calls(value=value),
            )
            is not None
        )

    def _read(self, file: Path) -> list[CssDeclaration]:
        """Read and parse one stylesheet, reporting one that cannot be read.

        A byte-order mark is dropped. A file that is missing, unreadable or
        not UTF-8 becomes a ``CSS100`` finding and contributes nothing
        else, so one bad file never stops the audit of the rest.

        Args:
            file: Stylesheet to read.

        Returns:
            Its declarations, or none when it could not be read.

        """
        try:
            text: str = file.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            self.findings.append(
                CssTokenFinding(
                    rule="CSS100",
                    file=file,
                    line=0,
                    message=f"Stylesheet could not be read: {error}",
                ),
            )
            return []
        return parse_declarations(text=text, file=file)

    def _component_names(self) -> frozenset[tuple[str, ...]]:
        """Infer component names from ``components/<name>/`` paths.

        A name is kept whole, as its run of words: ``condition-field`` is
        the run ``("condition", "field")``, so a CATALOG name is flagged
        for naming that component, not for using the ordinary word
        ``field`` that happens to be part of it.

        Returns:
            The lowercase word run of every component directory name.

        """
        names: set[tuple[str, ...]] = set()
        for file in self.inputs.files:
            try:
                parts: tuple[str, ...] = file.relative_to(
                    self.inputs.root,
                ).parts
            except ValueError:
                continue
            if "components" not in parts:
                continue
            index: int = parts.index("components")
            if index + 1 < len(parts):
                words: tuple[str, ...] = tuple(
                    substitute(
                        pattern=r"[-_]",
                        repl=" ",
                        string=parts[index + 1].lower(),
                    ).split(),
                )
                if words:
                    names.add(words)
        return frozenset(names)

    def _add(
        self,
        declaration: CssDeclaration,
        rule: str,
        message: str,
    ) -> None:
        """Record one finding for a declaration.

        Args:
            declaration: The offending declaration.
            rule: Stable ``CSS1xx`` identifier.
            message: Human-readable violation description.

        """
        self.findings.append(
            CssTokenFinding(
                rule=rule,
                file=declaration.file,
                line=declaration.line,
                message=(
                    f"{message} ({declaration.name}: "
                    f"{_clip(value=declaration.value)})"
                ),
            ),
        )

    def _duplicate_definitions(self) -> None:
        """Report one custom property given two values in the same scope.

        A property set under different selectors or at-rules is the
        cascade doing its job, so only definitions that share a scope and
        disagree are ambiguous.
        """
        for name, definitions in self.definitions.items():
            scopes: dict[str, list[CssDeclaration]] = {}
            for declaration in definitions:
                scopes.setdefault(declaration.scope, []).append(declaration)
            for group in scopes.values():
                if len({item.value for item in group}) <= 1:
                    continue
                for declaration in group:
                    self._add(
                        declaration=declaration,
                        rule="CSS101",
                        message=(
                            f"{name} has conflicting definitions in one scope."
                        ),
                    )

    def _references(self) -> None:
        """Require every non-dynamic custom-property reference to exist."""
        for declaration in self.declarations:
            for reference in Constants.var_reference.findall(
                string=declaration.masked,
            ):
                if (
                    reference.startswith("--dynamic-")
                    or reference in self.definitions
                ):
                    continue
                self._add(
                    declaration=declaration,
                    rule="CSS102",
                    message=f"Referenced custom property {reference} is not "
                    "defined in the scanned CSS tree.",
                )

    def _custom_properties(self) -> None:
        """Validate token names and the rules of each layer."""
        for declaration in self.declarations:
            if not declaration.is_custom:
                continue
            layer: Layer = layer_of(name=declaration.name)
            if Constants.provenance.search(string=declaration.name) or (
                layer is Layer.BASE
                and Constants.numeric_suffix.search(string=declaration.name)
            ):
                self._add(
                    declaration=declaration,
                    rule="CSS103",
                    message=(
                        "Token names may not encode generation provenance, "
                        "hashes, variants, or numeric collision suffixes."
                    ),
                )
            self._layer_rules(declaration=declaration, layer=layer)

    def _layer_rules(self, declaration: CssDeclaration, layer: Layer) -> None:
        """Validate one custom property against its layer's rules.

        Args:
            declaration: The custom-property definition.
            layer: The layer its name belongs to.

        """
        references: tuple[str, ...] = tuple(
            Constants.var_reference.findall(string=declaration.masked),
        )
        masked: str = declaration.masked
        if layer is Layer.PRIMARY:
            self._primary_name(declaration=declaration)
        if layer in {Layer.PRIMARY, Layer.DYNAMIC}:
            self._literal_layer(
                declaration=declaration,
                layer=layer,
                references=references,
                masked=masked,
            )
        elif layer is Layer.BASE:
            self._base_dependencies(
                declaration=declaration,
                references=references,
            )
        elif layer is Layer.CATALOG:
            self._catalog_value(
                declaration=declaration,
                references=references,
                masked=masked,
            )
        else:
            self._semantic(declaration=declaration, references=references)

    def _primary_name(self, declaration: CssDeclaration) -> None:
        """Validate PRIMARY names against the reserved scale tokens.

        Args:
            declaration: A ``--primary-*`` definition.

        """
        name: str = declaration.name
        if name.startswith("--primary-keyword-"):
            self._add(
                declaration=declaration,
                rule="CSS104",
                message=(
                    "PRIMARY may not be an arbitrary CSS-keyword storage "
                    "layer."
                ),
            )
        if (
            name.startswith("--primary-percent-")
            and name != "--primary-percent-base"
        ):
            self._add(
                declaration=declaration,
                rule="CSS105",
                message="PRIMARY percentage scale must expose only "
                "--primary-percent-base; named percentages belong in BASE.",
            )
        if (
            name.startswith("--primary-duration-")
            and name != "--primary-duration-unit"
        ):
            self._add(
                declaration=declaration,
                rule="CSS106",
                message="PRIMARY duration scale must expose only "
                "--primary-duration-unit; derived durations belong in BASE.",
            )
        if (
            name.startswith("--primary-font-weight-")
            and name != "--primary-font-weight-unit"
        ):
            self._add(
                declaration=declaration,
                rule="CSS107",
                message="PRIMARY font weights must derive from "
                "--primary-font-weight-unit in BASE.",
            )

    def _literal_layer(
        self,
        declaration: CssDeclaration,
        layer: Layer,
        references: tuple[str, ...],
        masked: str,
    ) -> None:
        """Require literal-only values in the literal input layers.

        Args:
            declaration: A PRIMARY or DYNAMIC definition.
            layer: The layer of the definition.
            references: Custom properties the value references.
            masked: The value with strings masked.

        """
        if references:
            self._add(
                declaration=declaration,
                rule="CSS108",
                message=f"{layer.value.upper()} must contain literal inputs "
                "and cannot reference other custom properties.",
            )
        if Constants.function_call.search(string=masked):
            self._add(
                declaration=declaration,
                rule="CSS109",
                message=f"{layer.value.upper()} cannot contain CSS functions.",
            )

    def _base_dependencies(
        self,
        declaration: CssDeclaration,
        references: tuple[str, ...],
    ) -> None:
        """Restrict BASE references to PRIMARY and DYNAMIC tokens.

        Args:
            declaration: A ``--base-*`` definition.
            references: Custom properties the value references.

        """
        for reference in references:
            if (
                layer_of(name=reference)
                not in Constants.allowed_base_references
            ):
                self._add(
                    declaration=declaration,
                    rule="CSS110",
                    message="BASE may reference only PRIMARY or DYNAMIC, "
                    f"not {reference}.",
                )

    def _catalog_value(
        self,
        declaration: CssDeclaration,
        references: tuple[str, ...],
        masked: str,
    ) -> None:
        """Restrict CATALOG references, functions, and naming.

        Args:
            declaration: A ``--catalog-*`` definition.
            references: Custom properties the value references.
            masked: The value with strings masked.

        """
        for reference in references:
            if layer_of(name=reference) is not Layer.BASE:
                self._add(
                    declaration=declaration,
                    rule="CSS111",
                    message=(
                        f"CATALOG may reference only BASE, not {reference}."
                    ),
                )
        if Constants.color_mix.search(string=masked):
            self._add(
                declaration=declaration,
                rule="CSS112",
                message="color-mix() belongs in BASE; CATALOG should consume "
                "an already-derived BASE color.",
            )
        if Constants.identity_calc.search(string=masked):
            self._add(
                declaration=declaration,
                rule="CSS113",
                message="CATALOG contains a no-op multiplication by BASE "
                "zero/one; reuse the appropriate BASE value instead.",
            )
        self._catalog_name(declaration=declaration)

    def _semantic(
        self,
        declaration: CssDeclaration,
        references: tuple[str, ...],
    ) -> None:
        """Require SEMANTIC tokens to be one plain CATALOG reference.

        Args:
            declaration: An unprefixed custom-property definition.
            references: Custom properties the value references.

        """
        if (
            len(references) != 1
            or layer_of(name=references[0]) is not Layer.CATALOG
        ):
            self._add(
                declaration=declaration,
                rule="CSS119",
                message="SEMANTIC must be a single reference to exactly one "
                "CATALOG custom property.",
            )
        if (
            fullmatch(
                pattern=Constants.catalog_reference,
                string=_unimportant(value=declaration.masked),
            )
            is None
        ):
            self._add(
                declaration=declaration,
                rule="CSS120",
                message="SEMANTIC may only reference a CATALOG token; "
                "literals, fallbacks, and composition are forbidden.",
            )

    def _catalog_name(self, declaration: CssDeclaration) -> None:
        """Validate generic-component-first CATALOG naming.

        Args:
            declaration: A ``--catalog-*`` definition.

        """
        body: str = declaration.name.removeprefix("--catalog-")
        parts: list[str] = body.split(sep="-")
        if len(parts) < Constants.min_catalog_segments:
            self._add(
                declaration=declaration,
                rule="CSS114",
                message="CATALOG names should be "
                "--catalog-<generic-component>-<domain>-<rule>.",
            )
            return
        family: str = parts[0]
        domain: str = parts[1]
        if family in Constants.catalog_domains:
            self._add(
                declaration=declaration,
                rule="CSS115",
                message=(
                    "CATALOG must be organized by generic component first, "
                    "then domain."
                ),
            )
        if domain not in Constants.catalog_domains:
            self._add(
                declaration=declaration,
                rule="CSS116",
                message="Expected a known CATALOG domain in the second "
                f"segment; got {domain!r}.",
            )
        if Constants.noncanonical_scale.search(string=body):
            self._add(
                declaration=declaration,
                rule="CSS117",
                message="CATALOG uses a noncanonical scale abbreviation such "
                "as 3xl/5xl/sm/md/lg; use the BASE scale vocabulary.",
            )
        lowered: list[str] = [part.lower() for part in parts]
        if any(part in self.context_words for part in lowered) or any(
            _contains_run(parts=lowered, run=name)
            for name in self.component_names
        ):
            self._add(
                declaration=declaration,
                rule="CSS118",
                message="CATALOG contains a configured concrete application "
                "or component context word.",
            )

    def _terminal_declarations(self) -> None:
        """Validate ordinary declarations at the consumption layer."""
        for declaration in self.declarations:
            if declaration.is_custom:
                continue
            masked: str = declaration.masked
            self._terminal_references(declaration=declaration)
            if Constants.design_function.search(string=masked):
                self._add(
                    declaration=declaration,
                    rule="CSS122",
                    message="Component CSS may not contain calc/min/max/clamp/"
                    "minmax/color-mix/repeat; compose the value upstream.",
                )
            if (
                declaration.name.lower() in Constants.design_properties
                and _unimportant(value=masked).lower()
                not in Constants.css_wide_keywords
                and not self._plain_semantic_reference(
                    value=_unimportant(value=masked),
                )
            ):
                self._add(
                    declaration=declaration,
                    rule="CSS123",
                    message=f"{declaration.name} is a design/configuration "
                    "property and must be exactly one SEMANTIC var() "
                    "reference.",
                )
            elif Constants.design_literal.search(string=masked):
                self._add(
                    declaration=declaration,
                    rule="CSS124",
                    message="This declaration contains an embedded hardcoded "
                    "design literal; move the design operand upstream.",
                )
            if (
                declaration.name in Constants.configurable_numeric
                and self._has_bare_number(value=masked)
            ):
                self._add(
                    declaration=declaration,
                    rule="CSS125",
                    message=f"{declaration.name} contains a configurable "
                    "numeric value that must flow through the token "
                    "graph.",
                )

    def _terminal_references(self, declaration: CssDeclaration) -> None:
        """Require terminal declarations to read SEMANTIC variables only.

        Args:
            declaration: An ordinary (non-custom) declaration.

        """
        for reference in Constants.var_reference.findall(
            string=declaration.masked,
        ):
            if layer_of(name=reference) is not Layer.SEMANTIC:
                self._add(
                    declaration=declaration,
                    rule="CSS121",
                    message="Component CSS may consume SEMANTIC variables "
                    f"only; found {reference}.",
                )


def scan_css_tokens(*, inputs: CssTokenInput) -> tuple[CssTokenFinding, ...]:
    """Audit a stylesheet set against the token architecture.

    Args:
        inputs: The audited set and its configuration.

    Returns:
        Every violation, in file then source order per check.

    """
    return tuple(CssTokenAudit(inputs=inputs).findings)
