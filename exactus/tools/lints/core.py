# Copyright (c) 2026
# Copyright (c) 2026
"""Lint exactus engine: clean, lint, and type-check sources with rollback.

The exactus cleans source files, optionally formats them, runs external
linters through :mod:`exactus.packages.all_lints`, retains project-specific
compliance and shebang checks, and guards
``pyrefly infer`` behind a snapshot/regression/rollback contract. It emits
a normalized ``{version, tools, summary, findings}`` payload consumed by
:mod:`exactus.tools.lints.main` for the standard exactus report bundle.
"""

from __future__ import annotations

from ast import (
    AST,
    AnnAssign,
    Assign,
    AsyncFunctionDef,
    Attribute,
    Call,
    ClassDef,
    Constant,
    Expr,
    FunctionDef,
    Import,
    ImportFrom,
    Load,
    Module,
    Name,
    Pass,
    Raise,
    Store,
    Subscript,
    expr,
    iter_child_nodes,
    iter_fields,
    parse,
    walk,
)
from collections.abc import Callable, Generator, Iterator, Mapping, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field, replace
from datetime import datetime
from fnmatch import fnmatch
from importlib.resources import files as resource_files
from itertools import pairwise
from json import JSONDecodeError, dumps, loads
from os import environ, pathsep
from textwrap import dedent

try:
    from os import geteuid
except ImportError:
    geteuid: Callable[[], int] | None = None
from pathlib import Path
from platform import machine, node, platform, python_version, system
from re import MULTILINE, Match, Pattern
from re import compile as compile_regex
from shutil import copy2, which
from subprocess import CompletedProcess, SubprocessError, run
from sys import executable
from tempfile import TemporaryDirectory
from time import monotonic, perf_counter
from tomllib import loads as toml_loads
from typing import TYPE_CHECKING, ClassVar, Final, Self, cast, final

from exactus.packages.organize import configured_order
from exactus.packages.steps import trace
from exactus.tools.common.cli import (
    ExactusCommonTables,
    exactus_tool_command,
    is_reports_tree,
    resolve_exactus_tool_bundle,
    resolve_linter_toolchain,
)
from exactus.tools.common.runtime import (
    Progress,
    publish_progress,
    release_activities,
    run_source_activity,
)
from exactus.tools.common.sprint import Writer, sprint
from exactus.tools.common.toml import TomlDocument, TomlSerializer, TomlValue
from exactus.tools.lints.compliance import (
    ComplianceInput,
    ComplianceResult,
    scan_compliance,
)
from exactus.tools.lints.css_tokens import (
    CssTokenFinding,
    CssTokenInput,
    scan_css_tokens,
)
from exactus.tools.lints.js_delimiters import (
    DelimiterInput,
    DelimiterResult,
    JavaScriptDelimiterSimplifier,
    scan_delimiters,
)
from exactus.tools.lints.js_function_blocks import (
    FunctionBlocksInput,
    FunctionBlocksResult,
    scan_function_blocks,
)
from exactus.tools.lints.long_lines import (
    LongLineRepair,
    LongLinesAPI,
    RepairSummary,
)
from exactus.tools.lints.packages_pipeline import (
    AllLintsRequest,
    issue_baselines,
    legacy_tools,
    run_all_lints,
    run_group_final,
    run_organize,
)
from exactus.tools.lints.shebang import (
    ShebangInput,
    ShebangResult,
    ShebangSettings,
    scan_shebang,
)
from exactus.tools.lints.string_transform import (
    TransformOptions,
    TransformResult,
    transform_strings,
)

if TYPE_CHECKING:
    from importlib.resources.abc import Traversable

    from exactus.packages.all_lints import ToolResult
type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
type IssueKey = tuple[str, int, int, str, str]
type ToolCommands = Mapping[str, tuple[str, ...] | None]
type ToolArguments = Mapping[str, Sequence[str]]
type ExceptionMessageCandidate = tuple[Name, Name, AST]
type ExceptionMessageFixCandidate = tuple[Name, Name, AST, Assign | AnnAssign]


def template_resource(*, name: str) -> Traversable:
    """Locate a bundled linter template.

    Templates live in ``exactus/tools/lints/templates`` and
    are anchored on the ``exactus.tools.lints`` package rather
    than on
    this module, so they resolve identically wherever the lint engine
    lives inside the package tree.

    Args:
        name: Template file name; empty selects the directory itself.

    Returns:
        The resource for the template (or the templates directory).

    """
    templates: Traversable = resource_files("exactus.tools.lints").joinpath(
        "templates",
    )
    return templates.joinpath(name) if name else templates


@final
class Constants:
    """Hold the report schema and tool-matching defaults.

    Attributes:
        report_version: Report schema version.
        python_suffixes: Python source suffixes.
        eslint_suffixes: JavaScript source suffixes.
        stylelint_suffixes: CSS source suffixes.
        htmlhint_suffixes: HTML source suffixes.
        tool_names: Report section names in report order.
        default_bare_import_exceptions: Modules allowed as bare imports.
        python_packages: ``(command, package)`` Python tool installs.
        node_packages: ``(command, package)`` Node.js tool installs.
        node_path_extras: Extra PATH entries searched for Node.js.
        ruff_extend_ignores: Ruff rule exclusions applied everywhere.
        ruff_config_names: Standalone Ruff configuration filenames.
        upper_global_pattern: Uppercase module-global pattern.
        upper_global_exempt_calls: Calls exempt from the global rule.
        js_class_pattern: JavaScript class-body pattern.
        js_method_pattern: JavaScript method pattern.
        js_arrow_field_pattern: JavaScript arrow-field pattern.
        js_function_pattern: JavaScript function-declaration pattern.
        css_measure_pattern: CSS measurement-unit pattern.
        css_numeric_literal_pattern: CSS numeric-literal pattern.
        css_gradient_pattern: CSS gradient-function pattern.
        css_color_pattern: CSS color-literal pattern.
        css_time_pattern: CSS time-unit pattern.
        css_easing_pattern: CSS easing-function pattern.
        css_font_text_properties: Font/text property names.
        css_allowed_literals: Direct numeric literals allowed in CSS.
        js_style_assignment_pattern: ``.style.property =`` pattern.
        js_style_set_property_pattern: ``style.setProperty()`` pattern.
        js_object_assign_style_pattern: ``Object.assign(...style)`` pattern.
        js_object_property_pattern: Object-literal property pattern.
        js_identifier_pattern: JavaScript identifier token pattern.
        js_masked_region_pattern: JavaScript string and comment pattern.
        js_quoted_value_pattern: Quoted JavaScript literal pattern.
        js_static_value_pattern: Static JavaScript value pattern.
        css_reference_pattern: Variable and URL function starts.
        css_descriptor_pattern: Descriptor blocks outside the element cascade.
        css_declaration_pattern: CSS property declaration pattern.
        comment_body_pattern: Non-newline comment-character pattern.
        css_comment_pattern: CSS ``/* ... */`` comment pattern.
        css_priority_pattern: Trailing declaration priority marker.
        html_comment_pattern: HTML ``<!-- ... -->`` comment pattern.
        html_style_tag_pattern: HTML ``<style>`` open-tag pattern.
        html_style_block_pattern: HTML ``<style>...</style>`` pattern.
        html_inline_script_pattern: HTML ``<script>...</script>`` pattern.
        html_script_src_pattern: ``<script>`` ``src`` attribute pattern.
        html_type_attribute_pattern: ``type`` attribute pattern.
        html_style_attribute_pattern: Inline ``style`` attribute pattern.
        html_event_attribute_pattern: Inline ``on*`` handler pattern.
        html_javascript_url_pattern: ``javascript:`` URL pattern.
        html_data_script_types: Non-JavaScript ``<script>`` type values.
        stylelint_default_config: Fallback stylelint configuration.
        eslint_config_names: Recognized ESLint configuration filenames.
        jsconfig_names: Recognized JSConfig configuration filenames.
        stylelint_config_names: Recognized stylelint config filenames.
        empty_methods: Empty default for optional method sets.
        version_commands: Command key whose ``--version`` names the
            version of each external linter.
        version_pattern: Version number inside ``--version`` output.
        version_timeout: Seconds one ``--version`` probe may take.
        stage_spans: Overall-progress bounds of each full-run stage.
        simple_stage_spans: Overall-progress bounds of each all-lints-only
            stage.
        total_stages: Planned stage count of a full run.
        simple_total_stages: Planned stage count of an all-lints-only run.

    """

    report_version: ClassVar[int] = 1
    python_suffixes: ClassVar[frozenset[str]] = frozenset({".py", ".pyi"})
    eslint_suffixes: ClassVar[frozenset[str]] = frozenset(
        {".js", ".jsx", ".mjs", ".cjs"},
    )
    stylelint_suffixes: ClassVar[frozenset[str]] = frozenset({".css"})
    htmlhint_suffixes: ClassVar[frozenset[str]] = frozenset({".htm", ".html"})
    tool_names: ClassVar[tuple[str, ...]] = (
        "custom_compliance",
        "custom_shebang",
        "custom_python",
        "custom_python_long_lines",
        "custom_javascript",
        "custom_javascript_delimiters",
        "custom_javascript_notation",
        "custom_css",
        "custom_html",
        "ruff",
        "ruff_docs",
        "basedpyright",
        "pyrefly",
        "eslint",
        "typescript",
        "stylelint",
        "htmlhint",
    )
    default_bare_import_exceptions: ClassVar[tuple[str, ...]] = (
        "pytest",
        "sys",
    )
    python_packages: ClassVar[tuple[tuple[str, str], ...]] = (
        ("ruff", "ruff"),
        ("basedpyright", "basedpyright"),
        ("pyrefly", "pyrefly"),
    )
    node_packages: ClassVar[tuple[tuple[str, str], ...]] = (
        ("eslint", "eslint"),
        ("tsc", "typescript"),
        ("stylelint", "stylelint"),
        ("htmlhint", "htmlhint"),
        ("prettier", "prettier"),
    )
    node_path_extras: ClassVar[tuple[str, ...]] = (
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
    )
    ruff_extend_ignores: ClassVar[tuple[str, ...]] = (
        "--extend-ignore",
        "D203",
        "--extend-ignore",
        "D213",
    )
    ruff_config_names: ClassVar[tuple[str, ...]] = ("ruff.toml", ".ruff.toml")

    @classmethod
    def ruff_config_text(cls, *, cwd: Path) -> str:
        """Return the project's own Ruff configuration text, if any.

        Args:
            cwd: Project working directory.

        Returns:
            ``ruff.toml``/``.ruff.toml`` text, the ``pyproject.toml``
            text when it carries a ``[tool.ruff`` table, or ``""``.

        """
        for name in cls.ruff_config_names:
            if (cwd / name).is_file():
                return (cwd / name).read_text(encoding="utf-8")
        pyproject: Path = cwd / "pyproject.toml"
        if pyproject.is_file():
            text: str = pyproject.read_text(encoding="utf-8")
            if "[tool.ruff" in text:
                return text
        return ""

    @classmethod
    def ruff_policy(cls, *, cwd: Path) -> tuple[str, ...]:
        """Return Ruff rule-selection flags for the exactused project.

        A project that configures Ruff keeps its own rule selection;
        unconfigured projects get the exactus's strict ``ALL`` default.

        Args:
            cwd: Project working directory.

        Returns:
            Ruff CLI flags.

        """
        if cls.ruff_config_text(cwd=cwd):
            return cls.ruff_extend_ignores
        return ("--select", "ALL", *cls.ruff_extend_ignores)

    eslint_config_names: ClassVar[tuple[str, ...]] = (
        "eslint.config.js",
        "eslint.config.mjs",
        "eslint.config.cjs",
    )
    jsconfig_names: ClassVar[tuple[str, ...]] = (
        "jsconfig.json",
        "tsconfig.json",
    )
    stylelint_config_names: ClassVar[tuple[str, ...]] = (
        ".stylelintrc",
        ".stylelintrc.json",
        ".stylelintrc.yaml",
        ".stylelintrc.yml",
        ".stylelintrc.js",
        ".stylelintrc.cjs",
        "stylelint.config.js",
        "stylelint.config.mjs",
        "stylelint.config.cjs",
    )
    upper_global_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"^_*[A-Z][A-Z0-9_]*$",
    )
    upper_global_exempt_calls: ClassVar[frozenset[str]] = frozenset(
        ("TypeVar", "ParamSpec", "TypeVarTuple", "TypeAliasType", "NewType"),
    )
    js_class_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"^[ \t]*(?:export\s+(?:default\s+)?)?"
        r"class\s+(?P<name>[A-Za-z_$][\w$]*)"
        r"(?:\s+extends\s+(?P<base>[A-Za-z_$][\w.$]*))?"
        r"[^\{]*\{(?P<body>[\s\S]*?)^\}",
        flags=MULTILINE,
    )
    js_method_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?m)^[ \t]*(?P<static>static\s+)?(?:async\s+)?"
        r"(?P<name>(?!(?:if|elif|for|while|switch|catch|with|return|"
        r"typeof|instanceof|new|delete|void|in|of|await|yield|throw|"
        r"do|else|try|finally|case|default|break|continue|debugger|"
        r"extends|function|class|const|let|var|import|export|super|"
        r"this)\b)[A-Za-z_$][\w$]*)\s*"
        r"\((?P<params>[^)]*)\)\s*\{",
    )
    js_arrow_field_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?m)^[ \t]*(?P<static>static\s+)?(?:async\s+)?"
        r"(?P<name>[A-Za-z_$][\w$]*)\s*=\s*"
        r"(?:async\s+)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>",
    )
    js_function_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?m)^[ \t]*(?:async\s+)?function\s+"
        r"(?P<name>[A-Za-z_$][\w$]*)\s*\(",
    )
    css_measure_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?i)(?<![-\w.])(?:\d+(?:\.\d+)?|\.\d+)"
        r"(?:px|cm|mm|q|in|pc|pt|em|rem|ex|rex|cap|rcap|ch|rch|ic|ric|"
        r"lh|rlh|vw|vh|vi|vb|vmin|vmax|svw|svh|svi|svb|svmin|svmax|"
        r"lvw|lvh|lvi|lvb|lvmin|lvmax|dvw|dvh|dvi|dvb|dvmin|dvmax|"
        r"cqw|cqh|cqi|cqb|cqmin|cqmax|fr|deg|grad|rad|turn|ms|s|hz|khz|"
        r"dpi|dpcm|dppx|x|%)\b",
    )
    css_numeric_literal_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?i)(?<![#\w.-])(?P<number>[-+]?(?:\d+(?:\.\d+)?|\.\d+))"
        r"(?P<unit>%|[a-z]+)?(?![\w.-])",
    )
    css_gradient_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?i)\b(?:repeating-)?(?:linear|radial|conic)-gradient\s*\(",
    )
    css_color_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?i)(?:#[0-9a-f]{3,8}\b|"
        r"\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color|"
        r"color-mix|light-dark)\s*\(|"
        r"\b(?:transparent|currentcolor|aliceblue|antiquewhite|aqua|"
        r"aquamarine|azure|beige|bisque|black|blanchedalmond|blue|"
        r"blueviolet|brown|burlywood|cadetblue|chartreuse|chocolate|"
        r"coral|cornflowerblue|cornsilk|crimson|cyan|darkblue|darkcyan|"
        r"darkgoldenrod|darkgray|darkgreen|darkgrey|darkkhaki|"
        r"darkmagenta|darkolivegreen|darkorange|darkorchid|darkred|"
        r"darksalmon|darkseagreen|darkslateblue|darkslategray|"
        r"darkslategrey|darkturquoise|darkviolet|deeppink|deepskyblue|"
        r"dimgray|dimgrey|dodgerblue|firebrick|floralwhite|forestgreen|"
        r"fuchsia|gainsboro|ghostwhite|gold|goldenrod|gray|green|"
        r"greenyellow|grey|honeydew|hotpink|indianred|indigo|ivory|"
        r"khaki|lavender|lavenderblush|lawngreen|lemonchiffon|lightblue|"
        r"lightcoral|lightcyan|lightgoldenrodyellow|lightgray|lightgreen|"
        r"lightgrey|lightpink|lightsalmon|lightseagreen|lightskyblue|"
        r"lightslategray|lightslategrey|lightsteelblue|lightyellow|lime|"
        r"limegreen|linen|magenta|maroon|mediumaquamarine|mediumblue|"
        r"mediumorchid|mediumpurple|mediumseagreen|mediumslateblue|"
        r"mediumspringgreen|mediumturquoise|mediumvioletred|midnightblue|"
        r"mintcream|mistyrose|moccasin|navajowhite|navy|oldlace|olive|"
        r"olivedrab|orange|orangered|orchid|palegoldenrod|palegreen|"
        r"paleturquoise|palevioletred|papayawhip|peachpuff|peru|pink|"
        r"plum|powderblue|purple|rebeccapurple|red|rosybrown|royalblue|"
        r"saddlebrown|salmon|sandybrown|seagreen|seashell|sienna|silver|"
        r"skyblue|slateblue|slategray|slategrey|snow|springgreen|"
        r"steelblue|tan|teal|thistle|tomato|turquoise|violet|wheat|"
        r"white|whitesmoke|yellow|yellowgreen)\b)",
    )
    css_time_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?<![-\w.])(?:\d+(?:\.\d+)?|\.\d+)(?:ms|s)\b",
    )
    css_easing_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=(
            "(?i)\\b(?:linear|ease|ease-in|ease-out|ease-in-out|step-start|ste"
            "p-end)\\b|(?:cubic-bezier|steps|linear)\\s*\\("
        ),
    )
    css_font_text_properties: ClassVar[frozenset[str]] = frozenset(
        {
            "font",
            "font-family",
            "font-size",
            "font-size-adjust",
            "font-stretch",
            "font-style",
            "font-weight",
            "font-kerning",
            "font-feature-settings",
            "font-language-override",
            "font-optical-sizing",
            "font-palette",
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
            "font-variation-settings",
            "text-align",
            "text-align-last",
            "text-indent",
            "text-justify",
            "text-transform",
            "text-orientation",
            "text-combine-upright",
            "text-wrap",
            "text-wrap-mode",
            "text-wrap-style",
            "letter-spacing",
            "word-spacing",
            "line-height",
            "tab-size",
            "white-space",
            "white-space-collapse",
            "word-break",
            "overflow-wrap",
            "word-wrap",
            "hyphens",
            "hyphenate-character",
            "hyphenate-limit-chars",
            "text-decoration",
            "text-decoration-color",
            "text-decoration-line",
            "text-decoration-style",
            "text-decoration-thickness",
            "text-underline-offset",
            "text-underline-position",
            "text-decoration-skip-ink",
            "text-decoration-skip",
            "text-emphasis",
            "text-emphasis-color",
            "text-emphasis-position",
            "text-emphasis-style",
            "text-overflow",
            "text-shadow",
            "direction",
            "writing-mode",
            "unicode-bidi",
            "text-rendering",
            "text-size-adjust",
            "text-spacing-trim",
        },
    )
    css_allowed_literals: ClassVar[frozenset[str]] = frozenset(
        {"0", "1", "0%", "100%"},
    )
    js_style_assignment_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=(
            "(?m)(?P<target>[A-Za-z_$][\\w$]*(?:\\.[A-Za-z_$][\\w$]*|\\[[^\\]]"
            "+\\])*)\\.style\\.(?P<property>[A-Za-z_$][\\w$]*)\\s*=\\s*(?P<val"
            "ue>[^;\\n]+)"
        ),
    )
    js_style_set_property_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=(
            "(?m)(?P<target>[A-Za-z_$][\\w$]*(?:\\.[A-Za-z_$][\\w$]*|\\[[^\\]]"
            "+\\])*)\\.style\\.setProperty\\(\\s*(?P<property>['\\\"][^'\\\"]+"
            "['\\\"])\\s*,\\s*(?P<value>[^,\\n)]+)"
        ),
    )
    js_object_assign_style_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?s)Object\.assign\(\s*"
        r"(?P<target>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*|\[[^\]]+\])*)"
        r"\.style\s*,\s*\{(?P<body>.*?)\}\s*\)",
    )
    js_object_property_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?m)(?P<property>[A-Za-z_$][\w$]*|['\"][^'\"]+['\"])\s*:\s*"
        r"(?P<value>(?:['\"][^'\"]*['\"]|`[^`]*`|[^,\n}]+))",
    )
    js_identifier_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"[A-Za-z_$][\w$]*",
    )
    js_masked_region_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"'(?:\\.|[^'\\])*'"
        r'|"(?:\\.|[^"\\])*"'
        r"|`(?:\\.|[^`\\])*`"
        r"|//[^\n]*"
        r"|(?s:/\*.*?\*/)",
    )
    js_quoted_value_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"^(['\"])(?:\\.|(?!\1).)*\1$",
    )
    js_static_value_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"^(?:[-+]?(?:\d+(?:\.\d+)?|\.\d+)|true|false|null)$",
    )
    css_reference_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?i)\b(?:var|url)\s*\(",
    )
    css_descriptor_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?i)@(?:font-face|property|counter-style)\b[^{}]*\{",
    )
    css_priority_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?i)\s*!\s*important\s*$",
    )
    css_comment_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?s)/\*.*?\*/",
    )
    comment_body_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"[^\n]",
    )
    css_declaration_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?m)(?:^|[{;])\s*(?P<property>-{0,2}[\w][\w-]*)\s*:\s*"
        r"(?P<value>[^;{}]+)",
    )
    html_comment_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?s)<!--.*?-->",
    )
    html_style_tag_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?is)<style(?:\s[^>]*)?>",
    )
    html_style_block_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?is)<style\b[^>]*>.*?</style\s*>",
    )
    html_inline_script_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?is)<script\b(?P<attrs>[^>]*)>(?P<body>.*?)</script\s*>",
    )
    html_script_src_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?i)(?<![\w-])src\s*=",
    )
    html_type_attribute_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?i)(?<![\w-])type\s*=\s*[\"']?(?P<type>[\w./+-]+)",
    )
    html_style_attribute_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?i)(?<![\w-])style\s*=\s*"
        r"(?P<value>\"[^\"]+\"|'[^']+'|[^\s>\"']+)",
    )
    html_event_attribute_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?i)(?<![\w-])(?P<name>on[a-z]+)\s*=",
    )
    html_javascript_url_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"(?i)(?<![\w-])(?:href|src|action|formaction|xlink:href)\s*="
        r"\s*[\"']?\s*javascript:",
    )
    html_data_script_types: ClassVar[frozenset[str]] = frozenset(
        {
            "application/json",
            "application/ld+json",
            "importmap",
            "speculationrules",
            "text/plain",
            "text/template",
            "text/x-template",
        },
    )
    stylelint_default_config: ClassVar[dict[str, JsonValue]] = {
        "ignoreFiles": [
            "**/node_modules/**",
            "**/*.min.css",
            "**/dist/**",
            "**/build/**",
            ".bkp/**",
            ".history/**",
            ".venv/**",
            "venv/**",
        ],
        "rules": {
            "annotation-no-unknown": True,
            "at-rule-no-unknown": True,
            "block-no-empty": True,
            "color-no-invalid-hex": True,
            "comment-no-empty": True,
            "custom-property-no-missing-var-function": True,
            "declaration-block-no-duplicate-custom-properties": True,
            "declaration-block-no-duplicate-properties": [
                True,
                {"ignore": ["consecutive-duplicates-with-different-values"]},
            ],
            "declaration-block-no-shorthand-property-overrides": True,
            "font-family-no-duplicate-names": True,
            "font-family-no-missing-generic-family-keyword": True,
            "function-calc-no-unspaced-operator": True,
            "function-linear-gradient-no-nonstandard-direction": True,
            "function-no-unknown": True,
            "keyframe-block-no-duplicate-selectors": True,
            "keyframe-declaration-no-important": True,
            "media-feature-name-no-unknown": True,
            "media-query-no-invalid": True,
            "named-grid-areas-no-invalid": True,
            "no-descending-specificity": True,
            "no-duplicate-selectors": True,
            "no-empty-source": True,
            "no-invalid-double-slash-comments": True,
            "no-invalid-position-at-import-rule": True,
            "no-irregular-whitespace": True,
            "property-no-unknown": True,
            "selector-anb-no-unmatchable": True,
            "selector-pseudo-class-no-unknown": True,
            "selector-pseudo-element-no-unknown": True,
            "selector-type-no-unknown": [
                True,
                {"ignore": ["custom-elements"]},
            ],
            "string-no-newline": True,
            "unit-no-unknown": True,
        },
    }
    empty_methods: ClassVar[frozenset[tuple[Path, int]]] = frozenset()
    version_commands: ClassVar[dict[str, str]] = {
        "ruff": "ruff",
        "ruff_docs": "ruff",
        "basedpyright": "basedpyright",
        "pyrefly": "pyrefly",
        "eslint": "eslint",
        "typescript": "tsc",
        "stylelint": "stylelint",
        "htmlhint": "htmlhint",
    }
    version_pattern: ClassVar[Pattern[str]] = compile_regex(
        pattern=r"\d+(?:\.\d+)+[\w.+-]*",
    )
    version_timeout: ClassVar[float] = 30.0
    stage_spans: ClassVar[dict[str, tuple[float, float]]] = {
        "toolchain": (0.02, 0.06),
        "clean": (0.06, 0.12),
        "conventions": (0.12, 0.25),
        "all lints": (0.25, 0.85),
        "infer": (0.85, 0.95),
        "pyrefly": (0.85, 0.95),
        "compliance and report": (0.95, 1.0),
    }
    simple_stage_spans: ClassVar[dict[str, tuple[float, float]]] = {
        "toolchain": (0.02, 0.08),
        "all lints": (0.08, 0.95),
        "compliance and report": (0.95, 1.0),
    }
    total_stages: ClassVar[int] = 8
    simple_total_stages: ClassVar[int] = 4


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Store one subprocess result.

    Attributes:
        command: Executed command.
        returncode: Process exit code.
        stdout: Standard output.
        stderr: Standard error.
        duration_seconds: Wall-clock seconds the command ran.

    """

    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Describe the pre-inference Python source snapshot.

    Attributes:
        root: Temporary backup root.
        files: Mapping from source files to backup files.
        existing: Python files present before inference.

    """

    root: Path
    files: Mapping[Path, Path]
    existing: frozenset[Path]


@dataclass(frozen=True, slots=True)
class SummaryInput:
    """Carry report-summary construction inputs.

    Attributes:
        started_at: Run start timestamp.
        finished_at: Run completion timestamp.
        duration_seconds: Elapsed run duration.
        cwd: Project working directory.
        report_path: Combined JSON report destination, or ``None`` when
            the report is written to standard output.
        targets: Files, directories, or glob patterns.
        ignores: Glob patterns excluded from all tools.
        tools: Per-tool report mapping.
        all_findings: Concatenated normalized findings.
        python_args: Relative Python file arguments.
        eslint_args: Relative JavaScript file arguments.
        stylelint_args: Relative CSS file arguments.
        htmlhint_args: Relative HTML file arguments.

    """

    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    cwd: Path
    report_path: Path | None
    targets: Sequence[str]
    ignores: Sequence[str]
    tools: Mapping[str, JsonValue]
    all_findings: Sequence[JsonValue]
    python_args: Sequence[str]
    eslint_args: Sequence[str]
    stylelint_args: Sequence[str]
    htmlhint_args: Sequence[str]


_COLLECT_PROGRESS_INTERVAL: Final[float] = 0.2
_COLLECT_PROGRESS_ESTIMATE: Final[int] = 500


def _ignore_file(_file: Path) -> None:
    """Accept a visited file when no progress callback is supplied.

    Args:
        _file: Ignored file.

    """


@final
@dataclass(slots=True)
class LintProgress:
    """Publish ordered lint-exactus stages to the shared progress channel.

    Attributes:
        completed: Finished stage count.
        total: Planned stage count.
        span: Weighted bounds of the active stage in overall progress.
        share: Monotonic completion fraction within the active stage.
        simple: Whether the run is all-lints-only, shrinking the stage
            budget and remapping the stage spans.

    """

    completed: int = 0
    total: int = Constants.total_stages
    span: tuple[float, float] = (0.0, 0.02)
    share: float = 0.0
    simple: bool = False

    def stage(self, *, name: str) -> None:
        """Mark the previous stage finished and publish ``name``.

        Args:
            name: Stage now starting.

        """
        self.completed += 1
        spans: dict[str, tuple[float, float]] = (
            Constants.simple_stage_spans
            if self.simple
            else (Constants.stage_spans)
        )
        self.span = spans.get(name, self.span)
        self.share = 0.0
        self.note(step=name, share=0.0)

    def note(
        self,
        *,
        step: str,
        detail: str = "",
        share: float | None = None,
        completed: int | None = None,
        total: int | None = None,
    ) -> None:
        """Publish a progress snapshot without advancing the stage.

        Args:
            step: Current logical step label.
            detail: Optional finer-grained detail label.
            share: Optional intra-stage completion fraction in ``[0, 1]``.
            completed: Actual completed checks when known.
            total: Actual discovered checks when known.

        """
        if share is not None:
            self.share = max(self.share, 0.0, min(1.0, share))
        publish_progress(
            progress=Progress(
                state="RUNNING",
                completed=self.completed if completed is None else completed,
                total=self.total if total is None else total,
                step=step,
                detail=detail,
                span=self.span,
                share=self.share,
            ),
        )

    def __post_init__(self) -> None:
        """Budget only the stages an all-lints-only run performs."""
        if self.simple:
            self.total = Constants.simple_total_stages


@final
@dataclass(slots=True)
class _StageSlicer:
    """Divide one stage span into contiguous weighted sub-step slices.

    Attributes:
        progress: Stage tracker receiving boundary publications.
        step: Step label used on every published note.
        weights: Work units owned by each sub-step in run order.
        cursor: Work units already claimed by earlier sub-steps.
        start: Overall progress bound where the stage starts.
        end: Overall progress bound where the stage ends.
        units: Total work units across every sub-step.

    """

    progress: LintProgress
    step: str
    weights: Sequence[int]
    cursor: int = 0
    start: float = field(init=False)
    end: float = field(init=False)
    units: int = field(init=False)

    def span(self, *, weight: int) -> tuple[float, float]:
        """Slice off the next ``weight`` units of the stage span.

        Args:
            weight: Work units owned by the sub-step.

        Returns:
            Progress span covering those units.

        """
        low: float = self.start + (self.end - self.start) * (
            self.cursor / self.units
        )
        self.cursor += weight
        return low, self.start + (self.end - self.start) * (
            self.cursor / self.units
        )

    def ticks(self, *, weight: int, label: str) -> Callable[[Path], None]:
        """Publish per-file progress over the next ``weight`` units.

        Args:
            weight: Work units owned by the sub-step.
            label: Detail prefix naming the active sub-step.

        Returns:
            ``on_file`` callback advancing the stage share per file.

        """
        base: int = self.cursor
        self.cursor += weight
        ticks: int = 0
        progress: LintProgress = self.progress
        step: str = self.step
        units: int = self.units
        interval: int = max(1, (weight + 63) // 64)

        def report(file: Path) -> None:
            """Advance the stage share by one visited file.

            Args:
                file: File just processed.

            """
            nonlocal ticks
            ticks += 1
            if ticks % interval != 0 and ticks < weight:
                return
            progress.note(
                step=step,
                detail=f"{label}: {file.name}",
                share=(base + min(ticks, weight)) / units,
            )

        return report

    def mark(self, *, weight: int, detail: str) -> None:
        """Consume ``weight`` units and publish the new boundary.

        Args:
            weight: Work units the sub-step owns.
            detail: Label describing the current sub-step.

        """
        self.cursor += weight
        self.progress.note(
            step=self.step,
            detail=detail,
            share=self.cursor / self.units,
        )

    def __post_init__(self) -> None:
        """Capture the active stage span and total work units."""
        self.start, self.end = self.progress.span
        self.units = max(sum(self.weights), 1)


@dataclass(frozen=True, slots=True)
class LintExactusInput:
    """Carry guarded-inference inputs.

    Attributes:
        cwd: Project working directory.
        targets: Files, directories, or glob patterns.
        ignores: Glob patterns excluded from all tools.
        python_args: Relative Python file arguments.
        python_files: Discovered Python files for the refresh pass.
        bare_import_exceptions: Allowed Python bare imports.
        baselines: Pre-inference Ruff and BasedPyright issue keys.
        tools: Per-tool report mapping updated with final findings.
        commands: Resolved executable prefixes keyed by tool name.
        arguments: Extra CLI arguments appended per tool.
        writer: Status-message writer.
        progress: Shared stage tracker for progress publication.

    """

    cwd: Path
    targets: Sequence[str]
    ignores: Sequence[str]
    python_args: Sequence[str]
    python_files: frozenset[Path]
    bare_import_exceptions: Sequence[str]
    baselines: tuple[frozenset[IssueKey], frozenset[IssueKey]]
    tools: dict[str, JsonValue]
    commands: ToolCommands
    arguments: ToolArguments
    writer: Writer
    progress: LintProgress = field(default_factory=LintProgress)


@dataclass(slots=True)
class CleanStats:
    """Accumulated metrics from a cleaning run.

    Attributes:
        scanned: Files inspected.
        changed: Files rewritten.
        lines_removed: Blank lines removed.
        bytes_delta: Net byte-size change.

    """

    scanned: int = 0
    changed: int = 0
    lines_removed: int = 0
    bytes_delta: int = 0


@dataclass(frozen=True, slots=True)
class LintExactusConfig:
    """Toggle the mutating and tool-management stages of the exactus.

    Attributes:
        clean: Normalize whitespace and run formatters on sources;
            requires ``fix``, since cleaning is a healing pass.
        fix: Master healing switch — the Ruff format/check ``--fix``
            convergence loop plus every rewriting stage (cleaning,
            convention rewrites, refactors, shebang repair and guarded
            inference). When off the run is audit-only.
        long_lines: Repair lines left over-long by Ruff inside that loop;
            has no effect when ``fix`` is off.
        delimiters: Scan JavaScript for removable delimiters and
            simplify them when ``fix`` is on.
        notation: Scan JavaScript for modernizable callables and
            normalize them when ``fix`` is on.
        infer: Run guarded ``pyrefly infer`` with rollback.
        install_tools: Install missing external tools on demand.
        group_final: Run the package Final-constant refactor first.
        organize: Reorder Python class methods in the resolved scope
            before linting.
        unsafe_fixes: Allow Ruff unsafe fixes in all-lints stabilization.
        workers: Maximum independent external lint processes.
        shebang: Shebang executable/shebang healing settings.
        simple: Run only the all-lints package audit: the report carries
            its findings alone while cleaning, convention scans,
            refactors, compliance and guarded inference are skipped.

    """

    clean: bool = True
    fix: bool = True
    long_lines: bool = True
    delimiters: bool = True
    notation: bool = True
    infer: bool = True
    install_tools: bool = True
    group_final: bool = True
    organize: bool = True
    unsafe_fixes: bool = False
    workers: int | None = None
    shebang: ShebangSettings = field(default_factory=ShebangSettings)
    simple: bool = False


@dataclass(frozen=True, slots=True)
class LintExactusRequest:
    """Carry the inputs of one guarded lint-exactus run.

    Attributes:
        cwd: Project working directory.
        targets: Files, directories, or glob patterns.
        report_path: JSON report destination recorded in the summary,
            or ``None`` when the report is consumed in memory only.
        ignores: Glob patterns excluded from all tools.
        bare_import_exceptions: Allowed Python bare imports.
        config: Stage toggles controlling mutating behavior.
        writer: Status-message writer.
        toolchain: Explicit bundled toolchain path, when provided.
        tool_args: Extra CLI arguments appended per tool.
        css_context_words: Application or component words that CATALOG
            custom-property names must not contain.

    """

    cwd: Path
    targets: Sequence[str]
    report_path: Path | None
    ignores: Sequence[str]
    bare_import_exceptions: Sequence[str]
    config: LintExactusConfig
    writer: Writer
    toolchain: Path | None
    tool_args: ToolArguments
    css_context_words: Sequence[str] = ()


@dataclass(frozen=True, slots=True)
class PythonReportInput:
    """Carry inputs for the Python analyzer stage.

    Attributes:
        tools: Per-tool report mapping updated in place.
        cwd: Project working directory.
        python_args: Relative Python file arguments.
        commands: Resolved executable prefixes keyed by tool name.
        arguments: Extra CLI arguments appended per tool.
        fix: Whether to run the Ruff format/check ``--fix`` loop.
        progress: Shared stage tracker for progress publication.

    """

    tools: dict[str, JsonValue]
    cwd: Path
    python_args: Sequence[str]
    commands: ToolCommands
    arguments: ToolArguments
    fix: bool
    progress: LintProgress = field(default_factory=LintProgress)


@dataclass(frozen=True, slots=True)
class CustomToolsInput:
    """Carry inputs for the built-in convention scans.

    Attributes:
        cwd: Project working directory.
        python_files: Discovered Python source files.
        eslint_args: Relative JavaScript file arguments.
        stylelint_args: Relative CSS file arguments.
        htmlhint_args: Relative HTML file arguments.
        bare_import_exceptions: Allowed Python bare imports.
        targets: Included source paths for owned-file scans.
        ignores: Excluded path globs for owned-file scans.
        css_context_words: Words forbidden in CATALOG token names.
        shebang: Executable/shebang healing settings.
        progress: Shared stage tracker for progress publication.
        fix: Whether safe custom convention fixes are applied.
        ruff_command: Resolved Ruff executable prefix for transforms.
        delimiters: Whether the JavaScript delimiter scan runs.
        notation: Whether the JavaScript function-block scan runs.

    """

    cwd: Path
    python_files: frozenset[Path]
    eslint_args: Sequence[str]
    stylelint_args: Sequence[str]
    htmlhint_args: Sequence[str]
    bare_import_exceptions: Sequence[str]
    targets: Sequence[str]
    ignores: Sequence[str]
    css_context_words: Sequence[str] = ()
    shebang: ShebangSettings = field(default_factory=ShebangSettings)
    progress: LintProgress = field(default_factory=LintProgress)
    fix: bool = True
    ruff_command: tuple[str, ...] | None = None
    delimiters: bool = True
    notation: bool = True


@dataclass(frozen=True, slots=True)
class _ConventionScopes:
    """File lists covered by each conventions sub-step.

    Attributes:
        python_files: Python sources scanned by the custom conventions;
            also the shebang scan's weight estimate.
        delimiter_files: JavaScript sources covered by the delimiter scan.
        notation_files: JavaScript sources covered by the function-block
            notation scan.
        javascript_files: JavaScript/JSX sources covered by the custom
            class and inline-style conventions.
        css_files: Stylesheets covered by the custom CSS conventions.
        html_files: HTML documents covered by the custom conventions.

    """

    python_files: list[Path]
    delimiter_files: list[Path]
    notation_files: list[Path]
    javascript_files: list[Path]
    css_files: list[Path]
    html_files: list[Path]


@dataclass(frozen=True, slots=True)
class _TransformRuntime:
    """Ruff runtime shared by string transforms and stabilization.

    Attributes:
        cwd: Project working directory used to stabilize transformed
            files with Ruff.
        ruff_command: Resolved Ruff executable prefix for transforms.

    """

    cwd: Path
    ruff_command: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AllLintsStageInput:
    """Carry inputs for the all-lints package stage.

    Attributes:
        cwd: Project working directory.
        targets: Files, directories, or glob patterns in scope.
        ignores: Glob patterns excluded from linting.
        commands: Resolved executable prefixes keyed by tool name.
        tool_args: Extra CLI arguments appended per tool.
        config: Stage configuration for the run.
        tools: Per-tool report mapping extended with findings.
        progress: Shared stage tracker for progress publication.
        repair: Long-line repair applied inside the Ruff stabilization
            loop, or ``None`` when it is not requested.

    """

    cwd: Path
    targets: Sequence[str]
    ignores: Sequence[str]
    commands: ToolCommands
    tool_args: ToolArguments
    config: LintExactusConfig
    tools: dict[str, JsonValue]
    progress: LintProgress = field(default_factory=LintProgress)
    repair: LongLineRepair | None = None


@dataclass(frozen=True, slots=True)
class FinishToolsInput:
    """Carry inputs for the compliance and report stage.

    Attributes:
        cwd: Project root.
        targets: Included paths.
        ignores: Excluded path globs.
        python_files: Pre-discovered owned Python sources.
        tools: Collected linter entries, updated in place.
        commands: Resolved external linter commands.
        simple: Skip the built-in compliance report; the run carries
            all-lints findings alone.

    """

    cwd: Path
    targets: Sequence[str]
    ignores: Sequence[str]
    python_files: frozenset[Path]
    tools: dict[str, JsonValue]
    commands: Mapping[str, tuple[str, ...] | None]
    simple: bool = False


@dataclass(frozen=True, slots=True)
class FrontendReportInput:
    """Carry inputs for the frontend analyzer stage.

    Attributes:
        tools: Per-tool report mapping updated in place.
        cwd: Project working directory.
        eslint_args: Relative JavaScript file arguments.
        stylelint_args: Relative CSS file arguments.
        htmlhint_args: Relative HTML file arguments.
        commands: Resolved executable prefixes keyed by tool name.
        arguments: Extra CLI arguments appended per tool.
        progress: Shared stage tracker for progress publication.

    """

    tools: dict[str, JsonValue]
    cwd: Path
    eslint_args: Sequence[str]
    stylelint_args: Sequence[str]
    htmlhint_args: Sequence[str]
    commands: ToolCommands
    arguments: ToolArguments
    progress: LintProgress = field(default_factory=LintProgress)


class NodeVisitorWalk:
    """Provide compact AST traversal helpers."""

    @staticmethod
    def walk(tree: AST) -> list[AST]:
        """Return descendants including the supplied AST node.

        Args:
            tree: Root AST node to traverse.

        Returns:
            All nodes in traversal order, including the root.

        """
        return list(walk(node=tree))

    @staticmethod
    def children(node: AST) -> list[AST]:
        """Return direct AST children.

        Args:
            node: AST node whose immediate children are needed.

        Returns:
            Immediate children in source order.

        """
        return list(iter_child_nodes(node=node))


class JavaScriptScanner:
    """Provide lightweight lexical JavaScript helpers."""

    @staticmethod
    def block_end(
        source: str,
        start: int,
        opening: str = "{",
        closing: str = "}",
    ) -> int:
        """Find the matching delimiter while respecting quoted strings.

        Args:
            source: JavaScript or CSS source text.
            start: Index of the opening delimiter.
            opening: Opening delimiter to count.
            closing: Matching closing delimiter.

        Returns:
            Index of the matching delimiter, or source length if incomplete.

        """
        depth: int = 0
        quote: str | None = None
        escaped: bool = False
        index: int = start
        while index < len(source):
            character: str = source[index]
            if quote is not None:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == quote:
                    quote = None
            elif character in {"'", '"', "`"}:
                quote = character
            elif character == opening:
                depth += 1
            elif character == closing:
                depth -= 1
                if depth == 0:
                    return index
            index += 1
        return len(source)

    @staticmethod
    def tokens(source: str) -> frozenset[str]:
        """Return identifier-like tokens outside strings and comments.

        Args:
            source: JavaScript source text to tokenize.

        Returns:
            Identifier tokens outside quoted strings.

        """
        return frozenset(
            Constants.js_identifier_pattern.findall(
                string=Constants.js_masked_region_pattern.sub(
                    repl=" ",
                    string=source,
                ),
            ),
        )


@dataclass(frozen=True, slots=True)
class _CleanCollectScope:
    """Shared inputs for clean-source collection.

    Attributes:
        cwd: Working directory for relative paths.
        excludes: User-supplied glob exclusion patterns.
        git_root: Git repository root, if known.
        git_files: Set of tracked Git files, if known.
        on_file: Optional callback invoked for every retained file.

    """

    cwd: Path
    excludes: Sequence[str]
    git_root: Path | None
    git_files: frozenset[Path] | None
    on_file: Callable[[Path], None] | None


@final
class SourceCleaner:
    """Normalize safe whitespace and format without formatter conflicts.

    Attributes:
        css: CSS file suffixes handled by the cleaner.
        default_excludes: Directories omitted from source cleanup.
        html: HTML file suffixes handled by the cleaner.
        js: JavaScript file suffixes handled by the cleaner.
        markup_raw_tags: HTML elements whose bodies keep verbatim
            whitespace.
        prettier: Source suffixes supported by Prettier.
        py: Python file suffixes handled by the cleaner.
        suffixes: All source suffixes handled by the cleaner.

    """

    py: ClassVar[frozenset[str]] = frozenset({".py", ".pyi"})
    js: ClassVar[frozenset[str]] = frozenset({".js", ".jsx", ".mjs", ".cjs"})
    css: ClassVar[frozenset[str]] = frozenset({".css"})
    html: ClassVar[frozenset[str]] = frozenset({".html", ".htm"})
    prettier: ClassVar[frozenset[str]] = css | html
    suffixes: ClassVar[frozenset[str]] = py | js | prettier
    markup_raw_tags: ClassVar[tuple[str, ...]] = (
        "pre",
        "textarea",
        "script",
        "xmp",
        "listing",
    )
    default_excludes: ClassVar[frozenset[str]] = (
        ExactusCommonTables.DEFAULT_EXCLUDED_DIRS | frozenset({"exec"})
    )

    @classmethod
    def normalize(cls: type[Self], path: Path, source: str) -> str:
        """Clean source and ensure exactly one final newline.

        Args:
            path: Source file path selecting the cleaner.
            source: Raw source contents.

        Returns:
            Cleaned source with a single trailing newline.

        """
        cleaned: str
        if path.suffix in cls.py:
            cleaned = cls._python(source=source)
        elif path.suffix in cls.js:
            cleaned = cls._javascript(source=source)
        elif path.suffix in cls.css:
            cleaned = cls._stylesheet(source=source)
        elif path.suffix in cls.html:
            cleaned = cls._markup(source=source)
        else:
            cleaned = source
        return f"{cleaned.rstrip(chr(10))}\n" if cleaned else ""

    @classmethod
    def collect(
        cls: type[Self],
        cwd: Path,
        targets: Sequence[str],
        excludes: Sequence[str],
        on_file: Callable[[Path], None] | None = None,
    ) -> list[Path]:
        """Expand and filter source paths for cleaning.

        Args:
            cwd: Project working directory.
            targets: Paths, directories, or glob patterns.
            excludes: Glob patterns excluded from cleaning.
            on_file: Optional callback invoked for every retained file.

        Returns:
            Sorted, deduplicated source paths to clean.

        """
        git_root: Path | None = cls._git_root(cwd=cwd)
        git_files: frozenset[Path] | None = (
            cls._git_files(root=git_root) if git_root is not None else None
        )
        return cls._collect(
            paths=targets,
            scope=_CleanCollectScope(
                cwd=cwd,
                excludes=excludes,
                git_root=git_root,
                git_files=git_files,
                on_file=on_file,
            ),
        )

    @classmethod
    def run(
        cls: type[Self],
        files: Sequence[Path],
        cwd: Path,
        writer: Writer,
        commands: ToolCommands,
    ) -> CleanStats:
        """Clean source files and run formatters.

        Args:
            files: Source files to clean.
            cwd: Project working directory.
            writer: Status-message writer.
            commands: Resolved executable prefixes keyed by tool name.

        Returns:
            Accumulated cleaning statistics.

        """
        stats: CleanStats = CleanStats()
        existing: list[Path] = [file for file in files if file.is_file()]
        trace(step=f"clean: normalize {len(existing)} files", depth=3)
        for file in existing:
            cls._clean(path=file, stats=stats, writer=writer)
        trace(
            step=(
                f"clean: normalized — {stats.changed} changed, "
                f"{stats.lines_removed} lines removed"
            ),
            depth=3,
        )
        cls._format(files=existing, cwd=cwd, commands=commands, writer=writer)
        cls._report(stats=stats, writer=writer)
        return stats

    @classmethod
    def _python_line(
        cls: type[Self],
        line: str,
        quote: str | None,
        *,
        escaped: bool,
    ) -> tuple[str, str | None, bool, bool]:
        """Process one Python line and return its text plus lexer state.

        Args:
            line: Source line with its line ending.
            quote: Active quote marker, or ``None`` outside strings.
            escaped: Whether the previous character escaped the next.

        Returns:
            ``(processed, quote, escaped, protected)`` for the line.

        """
        protected: bool = quote is not None
        index: int = 0
        while index < len(line):
            if quote is not None:
                quote, escaped, index = cls._string_step(
                    line=line,
                    index=index,
                    quote=quote,
                    escaped=escaped,
                )
                continue
            if line[index] == "#":
                protected = True
                break
            if line.startswith('"""', index) or line.startswith("'''", index):
                quote, protected, index = (
                    line[index : index + 3],
                    True,
                    index + 3,
                )
                continue
            quote = line[index] if line[index] in {'"', "'"} else None
            protected = protected or quote is not None
            escaped = False
            index += 1
        processed: str = line if quote is not None else cls._rstrip(line=line)
        return processed, quote, escaped, protected

    @classmethod
    def _python(cls: type[Self], source: str) -> str:
        """Strip trailing whitespace and drop blank lines outside strings.

        Lines inside string literals stay verbatim so docstring and
        literal content is preserved; every other empty line is removed.
        Ruff format, which runs next in the fix loop, owns the blank
        separators the Python style requires.

        Args:
            source: Python source to clean.

        Returns:
            Python source without unprotected blank lines.

        """
        output: list[str] = []
        quote: str | None = None
        escaped: bool = False
        for line in source.splitlines(keepends=True):
            processed, quote, escaped, protected = cls._python_line(
                line=line,
                quote=quote,
                escaped=escaped,
            )
            if processed.strip() or protected:
                output.append(processed)
        return "".join(output)

    @classmethod
    def _javascript_line(
        cls: type[Self],
        line: str,
        quote: str | None,
        *,
        block: bool,
        escaped: bool,
    ) -> tuple[str, str | None, bool, bool, bool]:
        """Process one JavaScript line and return text plus lexer state.

        Args:
            line: Source line with its line ending.
            quote: Active quote marker, or ``None`` outside strings.
            block: Whether a block comment is open.
            escaped: Whether the previous character escaped the next.

        Returns:
            ``(processed, quote, block, escaped, protected)`` for the
            line.

        """
        protected: bool = quote is not None or block
        index: int = 0
        while index < len(line):
            if block:
                if line.startswith("*/", index):
                    block, index = False, index + 2
                else:
                    index += 1
                continue
            if quote is not None:
                if not escaped and line[index] == quote:
                    quote = None
                escaped = line[index] == "\\" and not escaped
                index += 1
                continue
            if line.startswith("//", index):
                protected = True
                break
            if line.startswith("/*", index):
                block, protected, index = True, True, index + 2
                continue
            quote = line[index] if line[index] in {'"', "'", "`"} else None
            protected = protected or quote is not None
            escaped = False
            index += 1
        processed: str = (
            line if quote is not None or block else cls._rstrip(line=line)
        )
        return processed, quote, block, escaped, protected

    @classmethod
    def _javascript(cls: type[Self], source: str) -> str:
        """Strip trailing whitespace and drop blank lines outside strings.

        Lines inside strings, template literals, and block comments stay
        verbatim; every other empty line is removed. JavaScript layout
        and delimiter syntax remain owned by the convention passes.

        Args:
            source: JavaScript source to clean.

        Returns:
            JavaScript source without unprotected blank lines.

        """
        output: list[str] = []
        quote: str | None = None
        block: bool = False
        escaped: bool = False
        for line in source.splitlines(keepends=True):
            processed, quote, block, escaped, protected = cls._javascript_line(
                line=line,
                quote=quote,
                block=block,
                escaped=escaped,
            )
            if processed.strip() or protected:
                output.append(processed)
        return "".join(output)

    @classmethod
    def _stylesheet_line(
        cls: type[Self],
        line: str,
        quote: str | None,
        *,
        block: bool,
        escaped: bool,
    ) -> tuple[str, str | None, bool, bool, bool]:
        """Process one stylesheet line and return text plus lexer state.

        Args:
            line: Source line with its line ending.
            quote: Active quote marker, or ``None`` outside strings.
            block: Whether a block comment is open.
            escaped: Whether the previous character escaped the next.

        Returns:
            ``(processed, quote, block, escaped, protected)`` for the
            line.

        """
        protected: bool = quote is not None or block
        index: int = 0
        while index < len(line):
            if block:
                if line.startswith("*/", index):
                    block, index = False, index + 2
                else:
                    index += 1
                continue
            if quote is not None:
                if not escaped and line[index] == quote:
                    quote = None
                escaped = line[index] == "\\" and not escaped
                index += 1
                continue
            if line.startswith("/*", index):
                block, protected, index = True, True, index + 2
                continue
            quote = line[index] if line[index] in {'"', "'"} else None
            protected = protected or quote is not None
            escaped = False
            index += 1
        processed: str = (
            line if quote is not None or block else cls._rstrip(line=line)
        )
        return processed, quote, block, escaped, protected

    @classmethod
    def _stylesheet(cls: type[Self], source: str) -> str:
        """Strip trailing whitespace and drop blank lines outside comments.

        Lines inside ``/* ... */`` comments and string literals stay
        verbatim; every other empty line is removed.

        Args:
            source: Stylesheet source to clean.

        Returns:
            Stylesheet source without unprotected blank lines.

        """
        output: list[str] = []
        quote: str | None = None
        block: bool = False
        escaped: bool = False
        for line in source.splitlines(keepends=True):
            (processed, quote, block, escaped, protected) = (
                cls._stylesheet_line(
                    line=line,
                    quote=quote,
                    block=block,
                    escaped=escaped,
                )
            )
            if processed.strip() or protected:
                output.append(processed)
        return "".join(output)

    @classmethod
    def _markup_text_step(
        cls: type[Self],
        lowered: str,
        index: int,
    ) -> tuple[str, str, int]:
        """Advance one character in markup text mode.

        Args:
            lowered: Lowercased source line being scanned.
            index: Cursor position inside the line.

        Returns:
            ``(mode, tag, index)`` after consuming the character or
            opening marker at ``index``.

        """
        if lowered.startswith("<!--", index):
            return "comment", "", index + 4
        if lowered.startswith("<style", index) and cls._markup_boundary(
            lowered=lowered,
            index=index + 6,
        ):
            return "style", "", index + 6
        for name in cls.markup_raw_tags:
            if lowered.startswith(f"<{name}", index) and cls._markup_boundary(
                lowered=lowered,
                index=index + 1 + len(name),
            ):
                return "raw", name, index + 1 + len(name)
        return "text", "", index + 1

    @classmethod
    def _markup_style_step(
        cls: type[Self],
        lowered: str,
        index: int,
    ) -> tuple[str, int]:
        """Advance one character inside a ``<style>`` body.

        Args:
            lowered: Lowercased source line being scanned.
            index: Cursor position inside the line.

        Returns:
            ``(mode, index)`` after consuming the character or marker.

        """
        if lowered.startswith("/*", index):
            return "css_comment", index + 2
        if lowered.startswith("</style", index) and cls._markup_boundary(
            lowered=lowered,
            index=index + 7,
        ):
            return "text", index + 7
        return "style", index + 1

    @classmethod
    def _markup_step(
        cls: type[Self],
        lowered: str,
        index: int,
        mode: str,
        tag: str,
    ) -> tuple[str, str, int]:
        """Advance the markup lexer over one character or marker.

        Args:
            lowered: Lowercased source line being scanned.
            index: Cursor position inside the line.
            mode: Active region — ``text``, ``comment``, ``raw``,
                ``style``, or ``css_comment``.
            tag: Raw-text element whose close tag ends ``raw`` mode.

        Returns:
            ``(mode, tag, index)`` after the step.

        """
        if mode == "comment":
            if lowered.startswith("-->", index):
                mode, tag, index = "text", "", index + 3
            else:
                index += 1
        elif mode == "css_comment":
            if lowered.startswith("*/", index):
                mode, index = "style", index + 2
            else:
                index += 1
        elif mode == "raw":
            if lowered.startswith(f"</{tag}", index) and cls._markup_boundary(
                lowered=lowered,
                index=index + 2 + len(tag),
            ):
                mode, tag, index = "text", "", index + 2 + len(tag)
            else:
                index += 1
        elif mode == "style":
            mode, index = cls._markup_style_step(lowered=lowered, index=index)
        else:
            mode, tag, index = cls._markup_text_step(
                lowered=lowered,
                index=index,
            )
        return mode, tag, index

    @classmethod
    def _markup_line(
        cls: type[Self],
        line: str,
        mode: str,
        tag: str,
    ) -> tuple[str, str, str, bool]:
        """Process one markup line and return its text plus lexer state.

        Args:
            line: Source line with its line ending.
            mode: Active region — ``text``, ``comment``, ``raw``,
                ``style``, or ``css_comment``.
            tag: Raw-text element whose close tag ends ``raw`` mode.

        Returns:
            ``(processed, mode, tag, protected)`` for the line.

        """
        protected: bool = mode in {"comment", "raw", "css_comment"}
        lowered: str = line.lower()
        index: int = 0
        while index < len(line):
            mode, tag, index = cls._markup_step(
                lowered=lowered,
                index=index,
                mode=mode,
                tag=tag,
            )
        processed: str = (
            line
            if mode in {"comment", "raw", "css_comment"}
            else cls._rstrip(line=line)
        )
        return processed, mode, tag, protected

    @classmethod
    def _markup(cls: type[Self], source: str) -> str:
        """Strip trailing whitespace and drop blank lines outside markup.

        ``<pre>``, ``<textarea>``, ``<script>``, ``<xmp>`` and
        ``<listing>`` bodies carry significant whitespace, and HTML or
        embedded-CSS comments may contain blank lines, so lines inside
        those regions stay verbatim; every other empty line is removed.

        Args:
            source: HTML source to clean.

        Returns:
            HTML source without unprotected blank lines.

        """
        output: list[str] = []
        mode: str = "text"
        tag: str = ""
        for line in source.splitlines(keepends=True):
            processed, mode, tag, protected = cls._markup_line(
                line=line,
                mode=mode,
                tag=tag,
            )
            if processed.strip() or protected:
                output.append(processed)
        return "".join(output)

    @classmethod
    def _clean(
        cls: type[Self],
        path: Path,
        stats: CleanStats,
        writer: Writer,
    ) -> None:
        """Clean one source file.

        Args:
            path: Source file to clean.
            stats: Accumulated statistics to update.
            writer: Status-message writer.

        """
        try:
            source: str = path.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            trace(step=f"clean: {path} — missing", depth=4)
            return
        stats.scanned += 1
        cleaned: str = cls.normalize(path=path, source=source)
        if cleaned == source:
            trace(step=f"clean: {path} — unchanged", depth=4)
            return
        stats.changed += 1
        stats.lines_removed += max(0, source.count("\n") - cleaned.count("\n"))
        stats.bytes_delta += len(cleaned.encode(encoding="utf-8")) - len(
            source.encode(encoding="utf-8"),
        )
        _ = path.write_text(data=cleaned, encoding="utf-8")
        trace(step=f"clean: {path} — normalized", depth=4)
        sprint(f"Cleaned: {path}", file=writer)

    @classmethod
    def _excluded_dir(
        cls: type[Self],
        *,
        directory: Path,
        name: str,
        cwd: Path,
        excludes: Sequence[str],
    ) -> bool:
        """Return whether a directory entry is excluded from collection.

        Files and directories that match an exclude pattern are skipped
        during the walk; directories are additionally pruned by name so
        large excluded trees are never descended into.

        Args:
            directory: Parent directory of the candidate entry.
            name: Immediate file or directory name.
            cwd: Working directory used for relative paths.
            excludes: Glob patterns excluded from cleaning.

        Returns:
            ``True`` when the entry should be skipped.

        """
        if name in cls.default_excludes:
            return True
        if name.startswith(".") and name != ".":
            return True
        path: Path = directory / name
        if is_reports_tree(directory=path):
            return True
        try:
            relative: str = path.relative_to(cwd).as_posix()
        except ValueError:
            return True
        return any(
            fnmatch(name=f"{relative}/**", pat=pattern)
            or fnmatch(name=relative, pat=pattern)
            for pattern in excludes
        )

    @classmethod
    def _walk(
        cls: type[Self],
        directory: Path,
        *,
        cwd: Path,
        excludes: Sequence[str],
    ) -> list[Path]:
        """Walk a directory tree, pruning excluded subdirectories.

        Args:
            directory: Directory to walk.
            cwd: Working directory used for relative paths.
            excludes: Glob patterns excluded from cleaning.

        Returns:
            Matching file paths under ``directory``.

        """
        result: list[Path] = []
        for root, dirnames, filenames in directory.walk(top_down=True):
            root_path: Path = Path(root)
            dirnames[:] = [
                name
                for name in dirnames
                if not cls._excluded_dir(
                    directory=root_path,
                    name=name,
                    cwd=cwd,
                    excludes=excludes,
                )
            ]
            for name in filenames:
                if cls._excluded_dir(
                    directory=root_path,
                    name=name,
                    cwd=cwd,
                    excludes=excludes,
                ):
                    continue
                result.append(root_path / name)
        return result

    @classmethod
    def _expand(
        cls: type[Self],
        *,
        pattern: str,
        cwd: Path,
        excludes: Sequence[str],
    ) -> list[Path]:
        """Resolve a path or glob pattern.

        Excluded directories are pruned during the walk so large excluded
        trees do not slow down collection.

        Args:
            pattern: Path, directory, or glob pattern.
            cwd: Working directory used for relative patterns.
            excludes: Glob patterns excluded from cleaning.

        Returns:
            Matching paths.

        """
        path: Path = Path(pattern)
        path = path if path.is_absolute() else cwd / path
        if not any(char in pattern for char in "*?["):
            if path.is_file():
                return [path]
            if not path.is_dir():
                return []
            return cls._walk(directory=path, cwd=cwd, excludes=excludes)
        base_parts: list[str] = []
        glob_parts: list[str] = []
        found: bool = False
        for part in Path(pattern).parts:
            if found or any(char in part for char in "*?["):
                found = True
                glob_parts.append(part)
            else:
                base_parts.append(part)
        result: list[Path] = []
        glob_base: Path = cwd / Path(*base_parts) if base_parts else cwd
        for candidate in glob_base.glob(pattern="/".join(glob_parts)):
            if candidate.is_dir():
                result.extend(
                    cls._walk(directory=candidate, cwd=cwd, excludes=excludes),
                )
            elif candidate.is_file() and not cls._excluded_dir(
                directory=candidate.parent,
                name=candidate.name,
                cwd=cwd,
                excludes=excludes,
            ):
                result.append(candidate)
        return result

    @classmethod
    def _is_excluded(
        cls: type[Self],
        path: Path,
        resolved: Path,
        scope: _CleanCollectScope,
    ) -> bool:
        """Return whether a source path should be excluded.

        Args:
            path: Original path to check.
            resolved: Resolved absolute path.
            scope: Collection scope supplying the working directory,
                glob exclusion patterns, and Git filters.

        Returns:
            ``True`` when the path should be skipped.

        """
        try:
            relative: str = resolved.relative_to(scope.cwd).as_posix()
        except ValueError:
            relative = path.name
        return (
            any(part in cls.default_excludes for part in path.parts)
            or any(
                fnmatch(name=relative, pat=pattern)
                or fnmatch(name=str(object=path), pat=pattern)
                or fnmatch(name=path.name, pat=pattern)
                for pattern in scope.excludes
            )
            or (
                scope.git_files is not None
                and scope.git_root is not None
                and resolved.is_relative_to(scope.git_root)
                and resolved.relative_to(scope.git_root) not in scope.git_files
            )
        )

    @classmethod
    def _collect(
        cls: type[Self],
        *,
        paths: Sequence[str],
        scope: _CleanCollectScope,
    ) -> list[Path]:
        """Expand and filter source paths.

        Args:
            paths: Paths, directories, or globs to collect.
            scope: Collection scope with filters and optional callback.

        Returns:
            Sorted, deduplicated source paths to clean.

        """
        seen: set[Path] = set()
        files: list[Path] = []
        for pattern in paths:
            for file in cls._expand(
                pattern=pattern,
                cwd=scope.cwd,
                excludes=scope.excludes,
            ):
                if not file.is_file() or file.suffix not in cls.suffixes:
                    continue
                try:
                    resolved: Path = file.resolve()
                except OSError:
                    continue
                if resolved in seen or cls._is_excluded(
                    path=file,
                    resolved=resolved,
                    scope=scope,
                ):
                    continue
                seen.add(resolved)
                files.append(file)
                if scope.on_file is not None:
                    scope.on_file(file)
        files.sort(key=str)
        return files

    @classmethod
    def _format(
        cls: type[Self],
        files: Sequence[Path],
        cwd: Path,
        commands: ToolCommands,
        writer: Writer,
    ) -> None:
        """Format Python plus CSS/HTML sources.

        JavaScript is intentionally excluded from Prettier here because the
        delimiter convention pass owns JavaScript syntax and deliberately
        produces forms that Prettier can canonicalize back on the next run.

        Args:
            files: Source files to format.
            cwd: Project working directory.
            commands: Resolved executable prefixes keyed by tool name.
            writer: Status-message writer.

        Raises:
            RuntimeError: If a formatter exits with a failure status.

        """
        formatter_commands: list[tuple[str, ...]] = []
        py_files: list[str] = [
            str(object=file) for file in files if file.suffix in cls.py
        ]
        ruff: tuple[str, ...] | None = commands.get("ruff")
        if py_files and ruff is not None:
            trace(
                step=(
                    f"clean: format — ruff check --fix on "
                    f"{len(py_files)} python files"
                ),
                depth=3,
            )
            formatter_commands.append(
                (
                    *ruff,
                    "check",
                    *Constants.ruff_policy(cwd=cwd),
                    "--fix",
                    "--exit-zero",
                    *py_files,
                ),
            )
        prettier_files: list[str] = [
            str(object=file) for file in files if file.suffix in cls.prettier
        ]
        prettier: tuple[str, ...] | None = commands.get("prettier")
        if prettier_files and prettier is not None:
            trace(
                step=(
                    f"clean: format — prettier --write on "
                    f"{len(prettier_files)} web files"
                ),
                depth=3,
            )
            formatter_commands.append((*prettier, "--write", *prettier_files))
        skipped: list[str] = [
            tool
            for tool, needed in (
                ("ruff", py_files),
                ("prettier", prettier_files),
            )
            if needed and commands.get(tool) is None
        ]
        if skipped:
            sprint(
                f"Skipping formatters not installed: {', '.join(skipped)}.",
                file=writer,
            )
        for command in formatter_commands:
            result: CommandResult = LintExactus.run_command(
                command=command,
                cwd=cwd,
            )
            trace(
                step=(
                    f"clean: formatter {command[0]} — exit {result.returncode}"
                ),
                depth=3,
            )
            if result.returncode:
                msg: str = dedent(
                    text=f"""\
    Formatter failed: {" ".join(command)}
    {result.stderr}""",
                )
                raise RuntimeError(msg)

    @staticmethod
    def _markup_boundary(lowered: str, index: int) -> bool:
        """Return whether ``index`` sits at a tag-name boundary.

        Args:
            lowered: Lowercased source line being scanned.
            index: Position just after a candidate tag name.

        Returns:
            ``True`` when the tag name ends at ``index``.

        """
        return index >= len(lowered) or lowered[index] in " \t\r\n/>"

    @staticmethod
    def _rstrip(line: str) -> str:
        """Remove horizontal trailing whitespace preserving line endings.

        Args:
            line: A single source line.

        Returns:
            The line with trailing spaces and tabs removed.

        """
        return (
            f"{body.rstrip(' \t')}{line[len(body) :]}"
            if (body := line.rstrip("\r\n")) != line
            else line.rstrip(" \t")
        )

    @staticmethod
    def _string_step(
        line: str,
        index: int,
        quote: str,
        *,
        escaped: bool,
    ) -> tuple[str | None, bool, int]:
        """Advance the lexer over one character inside a string.

        Args:
            line: Source line being scanned.
            index: Current character index.
            quote: Active quote marker.
            escaped: Whether the previous character escaped the next.

        Returns:
            ``(quote, escaped, index)`` after consuming the character.

        """
        if quote in {'"""', "'''"}:
            if not escaped and line.startswith(quote, index):
                return None, escaped, index + 3
            return quote, line[index] == "\\" and not escaped, index + 1
        next_quote: str | None = (
            None if not escaped and line[index] == quote else quote
        )
        return next_quote, line[index] == "\\" and not escaped, index + 1

    @staticmethod
    def _git_root(cwd: Path) -> Path | None:
        """Return the current Git repository root.

        Args:
            cwd: Working directory to probe.

        Returns:
            Repository root, or ``None`` outside a Git repository.

        """
        with suppress(FileNotFoundError):
            result: CommandResult = LintExactus.run_command(
                command=("git", "rev-parse", "--show-toplevel"),
                cwd=cwd,
            )
            if result.returncode == 0:
                return Path(result.stdout.strip()).resolve()
        return None

    @staticmethod
    def _git_files(root: Path) -> frozenset[Path] | None:
        """Return files not ignored by Git.

        Args:
            root: Repository root to list files for.

        Returns:
            Tracked and unignored files, or ``None`` on failure.

        """
        with suppress(FileNotFoundError):
            result: CommandResult = LintExactus.run_command(
                command=(
                    "git",
                    "ls-files",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                ),
                cwd=root,
            )
            if result.returncode == 0:
                return frozenset(
                    Path(line) for line in result.stdout.splitlines() if line
                )
        return None

    @staticmethod
    def _report(stats: CleanStats, writer: Writer) -> None:
        """Print accumulated cleaning statistics.

        Args:
            stats: Statistics to report.
            writer: Status-message writer.

        """
        sprint(
            f"{stats.scanned} scanned, "
            f"{stats.changed} changed, "
            f"{stats.lines_removed} lines removed, "
            f"{abs(stats.bytes_delta)} bytes "
            f"{'added' if stats.bytes_delta > 0 else 'removed'}",
            file=writer,
        )


def _lint_path_excluded(path: Path, cwd: Path, ignores: Sequence[str]) -> bool:
    """Return whether ``path`` matches an ignore pattern.

    Args:
        path: File path to check.
        cwd: Project working directory.
        ignores: Glob patterns to exclude.

    Returns:
        ``True`` when the path should be skipped.

    """
    try:
        relative: str = path.relative_to(cwd).as_posix()
    except ValueError:
        return True
    return any(
        fnmatch(name=relative, pat=pattern)
        or fnmatch(name=path.name, pat=pattern)
        for pattern in ignores
    )


def _lint_dir_pruned(
    directory: Path,
    cwd: Path,
    ignores: Sequence[str],
) -> bool:
    """Return whether ``directory`` should be skipped during collection.

    Args:
        directory: Directory path to check.
        cwd: Project working directory.
        ignores: Glob patterns to exclude.

    Returns:
        ``True`` when the directory should not be descended into.

    """
    name: str = directory.name
    if name.startswith(".") and name != ".":
        return True
    if is_reports_tree(directory=directory):
        return True
    try:
        relative: str = directory.relative_to(cwd).as_posix()
    except ValueError:
        return True
    return any(
        fnmatch(name=f"{relative}/**", pat=pattern)
        or fnmatch(name=relative, pat=pattern)
        for pattern in ignores
    )


@dataclass(frozen=True, slots=True)
class _LintCollectScope:
    """Shared inputs for lint-source collection helpers.

    Attributes:
        cwd: Project working directory.
        suffixes: Accepted lowercase file suffixes.
        ignores: Glob patterns to exclude.
        files: Accumulator for resolved matching paths.
        on_file: Optional callback invoked for every retained file.

    """

    cwd: Path
    suffixes: frozenset[str]
    ignores: Sequence[str]
    files: set[Path]
    on_file: Callable[[Path], None] | None


def _lint_maybe_add_file(candidate: Path, *, scope: _LintCollectScope) -> None:
    """Add ``candidate`` to ``files`` if it matches the requested suffixes.

    Args:
        candidate: Path to evaluate.
        scope: Collection scope with filters, accumulator, and callback.

    """
    if candidate.suffix.lower() not in scope.suffixes:
        return
    if not candidate.is_file():
        return
    try:
        resolved: Path = candidate.resolve()
    except OSError:
        return
    if resolved in scope.files or _lint_path_excluded(
        path=resolved,
        cwd=scope.cwd,
        ignores=scope.ignores,
    ):
        return
    scope.files.add(resolved)
    if scope.on_file is not None:
        scope.on_file(candidate)


def _lint_walk_directory(directory: Path, *, scope: _LintCollectScope) -> None:
    """Walk ``directory`` while pruning excluded subdirectories.

    Args:
        directory: Directory to walk.
        scope: Collection scope with filters, accumulator, and callback.

    """
    for root, dirnames, filenames in directory.walk(top_down=True):
        root_path: Path = Path(root)
        dirnames[:] = [
            name
            for name in dirnames
            if not _lint_dir_pruned(
                directory=root_path / name,
                cwd=scope.cwd,
                ignores=scope.ignores,
            )
        ]
        for name in filenames:
            _lint_maybe_add_file(candidate=root_path / name, scope=scope)


@dataclass(frozen=True, slots=True)
class _RunScope:
    """Files collected for one lint run, grouped by pipeline stage.

    Attributes:
        python_files: Python files that participate in guarded inference.
        python_args: Relative Python file arguments for linter commands.
        eslint_args: Relative JavaScript/TypeScript file arguments.
        stylelint_args: Relative stylesheet file arguments.
        htmlhint_args: Relative HTML file arguments.
        clean_files: Files eligible for whitespace cleanup.

    """

    python_files: frozenset[Path]
    python_args: list[str]
    eslint_args: list[str]
    stylelint_args: list[str]
    htmlhint_args: list[str]
    clean_files: list[Path]


@dataclass(frozen=True, slots=True)
class _ToolPhasesInput:
    """Carry inputs for the mutating lint stages.

    Attributes:
        cwd: Project working directory.
        targets: Files, directories, or glob patterns in scope.
        ignores: Glob patterns excluded from linting.
        bare_import_exceptions: Modules allowed as bare imports.
        css_context_words: Application or component words that CATALOG
            custom-property names must not contain.
        config: Stage toggles controlling mutating behavior.
        scope: Collected file groups feeding every stage.
        commands: Resolved executable prefixes keyed by tool name.
        tool_args: Extra CLI arguments appended per tool.
        group_final_report: Payload produced by the group-final stage.
        organize_report: Payload produced by the organize stage.
        writer: Status-message writer.
        progress: Shared stage tracker for progress publication.

    """

    cwd: Path
    targets: Sequence[str]
    ignores: Sequence[str]
    bare_import_exceptions: Sequence[str]
    css_context_words: Sequence[str]
    config: LintExactusConfig
    scope: _RunScope
    commands: ToolCommands
    tool_args: ToolArguments
    group_final_report: JsonValue
    organize_report: JsonValue
    writer: Writer
    progress: LintProgress


class LintExactus:
    """Lint, type-check, and guard ``pyrefly infer`` against regressions."""

    @classmethod
    def run(
        cls: type[Self],
        request: LintExactusRequest,
    ) -> tuple[dict[str, JsonValue], int]:
        """Run the complete guarded lint workflow.

        Args:
            request: Run inputs: file scope, report destination, stage
                toggles, toolchain resolution, and status writer.

        Returns:
            The normalized report payload and an exit status — zero when
            guarded inference is retained, one when it is rolled back.

        """
        started_at: datetime = datetime.now().astimezone()
        started_counter: float = perf_counter()
        cwd: Path = request.cwd
        targets: Sequence[str] = request.targets
        report_path: Path | None = request.report_path
        ignores: Sequence[str] = request.ignores
        bare_import_exceptions: Sequence[str] = request.bare_import_exceptions
        config: LintExactusConfig = request.config
        status_writer: Writer = request.writer
        progress: LintProgress = LintProgress(simple=config.simple)
        trace(step="lints: run start", depth=0)
        trace(step="stage: group final", depth=1)
        group_final_report: JsonValue = run_source_activity(
            mode="write",
            identity="lints:group-final",
            enabled=config.group_final and not config.simple,
            action=lambda: cls._group_final_stage(
                cwd=cwd,
                config=config,
                progress=progress,
            ),
        )
        trace(step="stage: collect", depth=1)
        scope: _RunScope = cls._collect_scope(
            cwd=cwd,
            targets=targets,
            ignores=ignores,
            config=config,
            progress=progress,
        )
        python_files: frozenset[Path] = scope.python_files
        python_args: list[str] = scope.python_args
        eslint_args: list[str] = scope.eslint_args
        stylelint_args: list[str] = scope.stylelint_args
        htmlhint_args: list[str] = scope.htmlhint_args
        clean_files: list[Path] = scope.clean_files
        trace(
            step=(
                f"collect: {len(python_files)} python, "
                f"{len(eslint_args)} javascript, "
                f"{len(stylelint_args)} css, {len(htmlhint_args)} html, "
                f"{len(clean_files)} files to clean"
            ),
            depth=2,
        )
        trace(step="stage: organize", depth=1)
        organize_report: JsonValue = run_source_activity(
            mode="write",
            identity="lints:organize",
            enabled=config.organize and not config.simple,
            action=lambda: cls._organize_stage(
                cwd=cwd,
                python_files=python_files,
                javascript_args=eslint_args,
                config=config,
                progress=progress,
            ),
        )
        progress.stage(name="toolchain")
        trace(step="stage: toolchain", depth=1)
        if config.install_tools:
            required: frozenset[str] = cls._required_tools(
                python_args=python_args,
                eslint_args=eslint_args,
                stylelint_args=stylelint_args,
                htmlhint_args=htmlhint_args,
                clean_files=clean_files,
            )
            trace(step=f"toolchain: required — {sorted(required)}", depth=2)
            cls._ensure_tools(cwd=cwd, writer=status_writer, required=required)
        commands: dict[str, tuple[str, ...] | None] = cls._resolve_commands(
            cwd=cwd,
            toolchain=request.toolchain,
        )
        resolved_tools: list[str] = sorted(
            name for name, command in commands.items() if command is not None
        )
        missing_tools: list[str] = sorted(
            name for name, command in commands.items() if command is None
        )
        trace(
            step=(
                f"toolchain: resolved — {resolved_tools}; "
                f"missing — {missing_tools}"
            ),
            depth=2,
        )
        if not config.simple:
            progress.stage(name="clean")
            trace(step="stage: clean", depth=1)
        with cls._temporary_configs(
            cwd=cwd,
            python_args=python_args,
            eslint_args=eslint_args,
            stylelint_args=stylelint_args,
        ):
            report, status = cls._tool_phases(
                inputs=_ToolPhasesInput(
                    cwd=cwd,
                    targets=targets,
                    ignores=ignores,
                    bare_import_exceptions=bare_import_exceptions,
                    css_context_words=request.css_context_words,
                    config=config,
                    scope=scope,
                    commands=commands,
                    tool_args=request.tool_args,
                    group_final_report=group_final_report,
                    organize_report=organize_report,
                    writer=status_writer,
                    progress=progress,
                ),
            )
        tools: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=report["tools"],
        )
        progress.stage(name="compliance and report")
        trace(step="stage: compliance and report", depth=1)
        cls._finish_tools(
            inputs=FinishToolsInput(
                cwd=cwd,
                targets=targets,
                ignores=ignores,
                python_files=scope.python_files,
                tools=tools,
                commands=commands,
                simple=config.simple,
            ),
        )
        all_findings: list[JsonValue] = cls._all_findings(tools=tools)
        trace(step=f"report: {len(all_findings)} findings collected", depth=2)
        finished_at: datetime = datetime.now().astimezone()
        report["summary"] = cls._summary(
            inputs=SummaryInput(
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=perf_counter() - started_counter,
                cwd=cwd,
                report_path=report_path,
                targets=targets,
                ignores=ignores,
                tools=tools,
                all_findings=all_findings,
                python_args=python_args,
                eslint_args=eslint_args,
                stylelint_args=stylelint_args,
                htmlhint_args=htmlhint_args,
            ),
        )
        report["findings"] = all_findings
        trace(step=f"lints: run finished — status {status}", depth=0)
        return report, status

    @staticmethod
    def run_command(command: Sequence[str], cwd: Path) -> CommandResult:
        """Run one command without raising for diagnostics.

        Args:
            command: Command and arguments.
            cwd: Project working directory.

        Returns:
            Captured subprocess result.

        """
        started: float = perf_counter()
        completed: CompletedProcess[str] = run(
            args=list(command),
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
        return CommandResult(
            command=tuple(command),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_seconds=round(number=perf_counter() - started, ndigits=3),
        )

    @staticmethod
    def parse_json_output(result: CommandResult) -> JsonValue:
        """Parse JSON output from a command.

        Args:
            result: Completed command.

        Returns:
            Parsed JSON value.

        Raises:
            RuntimeError: If stdout is not valid JSON.

        """
        try:
            value: JsonValue = cast(
                typ="JsonValue",
                val=loads(s=result.stdout),
            )
        except JSONDecodeError as error:
            msg: str = dedent(
                text=f"""\
    Invalid JSON from {" ".join(result.command)}: {error}
    stderr:
    {result.stderr}""",
            )
            raise RuntimeError(msg) from error
        return value

    @classmethod
    def _ensure_node(cls: type[Self], cwd: Path, writer: Writer) -> None:
        """Install Node.js when npm is unavailable.

        Args:
            cwd: Project working directory.
            writer: Status-message writer.

        Raises:
            RuntimeError: If no supported package manager is available or
                installation does not expose npm.

        """
        if which(cmd="npm") is not None:
            return
        host: str = system()
        if host == "Darwin":
            cls._install_node_macos(cwd=cwd, writer=writer)
        elif host == "Windows":
            cls._install_node_windows(cwd=cwd, writer=writer)
        elif host == "Linux":
            cls._install_node_linux(cwd=cwd, writer=writer)
        else:
            msg: str = f"Unsupported operating system: {host}"
            raise RuntimeError(msg)
        cls._refresh_path()
        if which(cmd="npm") is None:
            msg = (
                "Node.js installation completed, but npm is not visible in "
                "PATH. Restart the shell and rerun the script."
            )
            raise RuntimeError(msg)

    @classmethod
    def _install_node_macos(
        cls: type[Self],
        cwd: Path,
        writer: Writer,
    ) -> None:
        """Install Node.js with Homebrew.

        Args:
            cwd: Project working directory.
            writer: Status-message writer.

        Raises:
            RuntimeError: If Homebrew is unavailable.

        """
        if which(cmd="brew") is None:
            msg: str = (
                "Node.js is missing and Homebrew is unavailable. "
                "Install Homebrew or Node.js, then rerun the script."
            )
            raise RuntimeError(msg)
        sprint("Installing missing runtime: Node.js via Homebrew", file=writer)
        cls._install(command=("brew", "install", "node"), cwd=cwd)

    @classmethod
    def _install_node_windows(
        cls: type[Self],
        cwd: Path,
        writer: Writer,
    ) -> None:
        """Install Node.js with winget or Chocolatey.

        Args:
            cwd: Project working directory.
            writer: Status-message writer.

        Raises:
            RuntimeError: If neither installer is available.

        """
        if which(cmd="winget") is not None:
            sprint(
                "Installing missing runtime: Node.js via winget",
                file=writer,
            )
            cls._install(
                command=(
                    "winget",
                    "install",
                    "--id",
                    "OpenJS.NodeJS.LTS",
                    "--exact",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ),
                cwd=cwd,
            )
            return
        if which(cmd="choco") is not None:
            sprint(
                "Installing missing runtime: Node.js via Chocolatey",
                file=writer,
            )
            cls._install(
                command=("choco", "install", "nodejs-lts", "-y"),
                cwd=cwd,
            )
            return
        msg: str = (
            "Node.js is missing and neither winget "
            "nor Chocolatey is available."
        )
        raise RuntimeError(msg)

    @classmethod
    def _install_node_linux(
        cls: type[Self],
        cwd: Path,
        writer: Writer,
    ) -> None:
        """Install Node.js with a supported Linux package manager.

        Args:
            cwd: Project working directory.
            writer: Status-message writer.

        Raises:
            RuntimeError: If no supported package manager is found.

        """
        prefix: tuple[str, ...] = cls._sudo_prefix()
        managers: tuple[tuple[str, str, tuple[tuple[str, ...], ...]], ...] = (
            (
                "apt-get",
                "apt",
                (
                    ("apt-get", "update"),
                    ("apt-get", "install", "-y", "nodejs", "npm"),
                ),
            ),
            ("dnf", "dnf", (("dnf", "install", "-y", "nodejs", "npm"),)),
            (
                "pacman",
                "pacman",
                (("pacman", "-S", "--noconfirm", "nodejs", "npm"),),
            ),
            (
                "zypper",
                "zypper",
                (("zypper", "--non-interactive", "install", "nodejs", "npm"),),
            ),
        )
        for probe, label, commands in managers:
            if which(cmd=probe) is None:
                continue
            sprint(
                f"Installing missing runtime: Node.js via {label}",
                file=writer,
            )
            for command in commands:
                cls._install(command=(*prefix, *command), cwd=cwd)
            return
        msg: str = (
            "Node.js is missing and no supported Linux package "
            "manager was found (apt, dnf, pacman, or zypper)."
        )
        raise RuntimeError(msg)

    @classmethod
    def _ensure_tools(
        cls: type[Self],
        cwd: Path,
        writer: Writer,
        required: frozenset[str],
    ) -> None:
        """Install required Python and Node.js analysis tools when absent.

        Args:
            cwd: Project working directory.
            writer: Status-message writer.
            required: Tool commands needed for the matched files.

        """
        if resolve_exactus_tool_bundle(root=cwd) is not None:
            trace(
                step="toolchain: exactus bundle — nothing to install",
                depth=3,
            )
            return
        for command, package in Constants.python_packages:
            if command in required and which(cmd=command) is None:
                trace(step=f"toolchain: install {package}", depth=3)
                sprint(f"Installing missing tool: {package}", file=writer)
                cls._install(
                    command=(
                        executable,
                        "-m",
                        "pip",
                        "install",
                        "--upgrade",
                        package,
                    ),
                    cwd=cwd,
                )
        missing_node_packages: list[str] = [
            package
            for command, package in Constants.node_packages
            if command in required and which(cmd=command) is None
        ]
        eslint_needed: bool = "eslint" in required
        if not missing_node_packages and not eslint_needed:
            return
        cls._ensure_node(cwd=cwd, writer=writer)
        if eslint_needed:
            jsdoc_probe: CompletedProcess[str] = run(
                args=("npm", "list", "-g", "eslint-plugin-jsdoc", "--depth=0"),
                cwd=cwd,
                check=False,
                capture_output=True,
                text=True,
            )
            if jsdoc_probe.returncode:
                missing_node_packages.append("eslint-plugin-jsdoc")
        for package in missing_node_packages:
            trace(step=f"toolchain: install {package}", depth=3)
            sprint(f"Installing missing tool: {package}", file=writer)
            cls._install(command=("npm", "install", "-g", package), cwd=cwd)

    @classmethod
    def _python_files(
        cls: type[Self],
        cwd: Path,
        targets: Sequence[str],
        ignores: Sequence[str],
        on_file: Callable[[Path], None] | None = None,
    ) -> frozenset[Path]:
        """Collect Python files covered by the requested targets.

        Args:
            cwd: Project working directory.
            targets: Files, directories, or glob patterns to include.
            ignores: Glob patterns to exclude.
            on_file: Optional callback invoked for every retained file.

        Returns:
            Resolved Python source paths.

        """
        return cls._matching_files(
            cwd=cwd,
            targets=targets,
            ignores=ignores,
            suffixes=Constants.python_suffixes,
            on_file=on_file,
        )

    @classmethod
    def _snapshot(
        cls: type[Self],
        cwd: Path,
        targets: Sequence[str],
        backup_root: Path,
        ignores: Sequence[str],
    ) -> Snapshot:
        """Back up every existing Python file under the targets.

        Args:
            cwd: Project working directory.
            targets: Files or directories covered by inference.
            backup_root: Temporary backup directory.
            ignores: Glob patterns excluded from inference.

        Returns:
            Snapshot metadata.

        """
        existing: frozenset[Path] = cls._python_files(
            cwd=cwd,
            targets=targets,
            ignores=ignores,
        )
        files: dict[Path, Path] = {}
        for index, source in enumerate(iterable=sorted(existing)):
            backup: Path = backup_root / f"{index:08d}{source.suffix}"
            backup.parent.mkdir(parents=True, exist_ok=True)
            _ = copy2(src=source, dst=backup)
            files[source] = backup
        return Snapshot(root=backup_root, files=files, existing=existing)

    @classmethod
    def _restore(
        cls: type[Self],
        snapshot: Snapshot,
        cwd: Path,
        targets: Sequence[str],
        ignores: Sequence[str],
    ) -> None:
        """Restore sources and remove Python files created by inference.

        Args:
            snapshot: Pre-inference snapshot.
            cwd: Project working directory.
            targets: Files or directories covered by inference.
            ignores: Glob patterns excluded from inference.

        """
        for source, backup in snapshot.files.items():
            source.parent.mkdir(parents=True, exist_ok=True)
            _ = copy2(src=backup, dst=source)
        for created in (
            cls._python_files(cwd=cwd, targets=targets, ignores=ignores)
            - snapshot.existing
        ):
            created.unlink()

    @classmethod
    def _sources_changed(
        cls: type[Self],
        snapshot: Snapshot,
        cwd: Path,
        targets: Sequence[str],
        ignores: Sequence[str],
    ) -> bool:
        """Return whether sources differ from the snapshot.

        Args:
            snapshot: Pre-inference snapshot.
            cwd: Project working directory.
            targets: Files or directories covered by inference.
            ignores: Glob patterns excluded from inference.

        Returns:
            True when files were added, removed, or modified.

        """
        if (
            cls._python_files(cwd=cwd, targets=targets, ignores=ignores)
            != snapshot.existing
        ):
            return True
        return any(
            source.read_bytes() != backup.read_bytes()
            for source, backup in snapshot.files.items()
        )

    @classmethod
    def _ruff_keys(cls: type[Self], payload: JsonValue) -> frozenset[IssueKey]:
        """Normalize Ruff diagnostics for regression comparison.

        Args:
            payload: Ruff JSON payload.

        Returns:
            Stable diagnostic identities.

        Raises:
            TypeError: If the payload has an unexpected shape.

        """
        if not isinstance(payload, list):
            msg: str = "Unexpected Ruff JSON structure."
            raise TypeError(msg)
        keys: set[IssueKey] = set()
        for item in payload:
            if not isinstance(item, dict):
                msg = "Unexpected Ruff diagnostic structure."
                raise TypeError(msg)
            location: JsonValue = item.get("location")
            if not isinstance(location, dict):
                msg = "Ruff diagnostic has no location."
                raise TypeError(msg)
            keys.add(
                (
                    str(object=item.get("filename", "")),
                    cls._json_int(value=location.get("row", 0)),
                    cls._json_int(value=location.get("column", 0)),
                    str(object=item.get("code", "")),
                    str(object=item.get("message", "")),
                ),
            )
        return frozenset(keys)

    @classmethod
    def _basedpyright_keys(
        cls: type[Self],
        payload: JsonValue,
    ) -> frozenset[IssueKey]:
        """Normalize BasedPyright diagnostics for regression comparison.

        Args:
            payload: BasedPyright JSON payload.

        Returns:
            Stable diagnostic identities.

        Raises:
            TypeError: If the payload has an unexpected shape.

        """
        if not isinstance(payload, dict):
            msg: str = "Unexpected BasedPyright JSON structure."
            raise TypeError(msg)
        diagnostics: JsonValue = payload.get("generalDiagnostics", [])
        if not isinstance(diagnostics, list):
            msg = "Unexpected BasedPyright diagnostics structure."
            raise TypeError(msg)
        keys: set[IssueKey] = set()
        for item in diagnostics:
            if not isinstance(item, dict):
                msg = "Unexpected BasedPyright diagnostic."
                raise TypeError(msg)
            range_value: JsonValue = item.get("range")
            start: JsonValue = (
                range_value.get("start")
                if isinstance(range_value, dict)
                else None
            )
            if not isinstance(start, dict):
                msg = "BasedPyright diagnostic has no start range."
                raise TypeError(msg)
            keys.add(
                (
                    str(object=item.get("file", "")),
                    cls._json_int(value=start.get("line", 0)),
                    cls._json_int(value=start.get("character", 0)),
                    str(object=item.get("rule", "")),
                    str(object=item.get("message", "")),
                ),
            )
        return frozenset(keys)

    @classmethod
    def _position(
        cls: type[Self],
        line: JsonValue = 0,
        column: JsonValue = 0,
        end_line: JsonValue = 0,
        end_column: JsonValue = 0,
        *,
        zero_based: bool = False,
    ) -> dict[str, JsonValue]:
        """Normalize a source range to one-based coordinates.

        Args:
            line: Start line.
            column: Start column.
            end_line: End line.
            end_column: End column.
            zero_based: Whether incoming coordinates are zero-based.

        Returns:
            Normalized source range.

        """
        offset: int = 1 if zero_based else 0
        start_line: int = cls._json_int(value=line) + offset
        start_column: int = cls._json_int(value=column) + offset
        finish_line: int = cls._json_int(value=end_line or line) + offset
        finish_column: int = cls._json_int(value=end_column or column) + offset
        return {
            "line": start_line,
            "column": start_column,
            "end_line": finish_line,
            "end_column": finish_column,
        }

    @classmethod
    def _normalize(
        cls: type[Self],
        tool: str,
        payload: JsonValue,
    ) -> list[JsonValue]:
        """Dispatch to the per-tool diagnostic normalizer.

        Args:
            tool: Producing tool name.
            payload: Native JSON payload.

        Returns:
            Diagnostics sharing one schema.

        """
        if tool in {"ruff", "ruff_docs"}:
            return cls._normalize_ruff(tool=tool, payload=payload)
        dispatch: dict[str, Callable[..., list[JsonValue]]] = {
            "basedpyright": cls._normalize_basedpyright,
            "pyrefly": cls._normalize_pyrefly,
            "eslint": cls._normalize_eslint,
            "stylelint": cls._normalize_stylelint,
            "htmlhint": cls._normalize_htmlhint,
        }
        normalizer: Callable[..., list[JsonValue]] | None = dispatch.get(tool)
        return normalizer(payload=payload) if normalizer is not None else []

    @classmethod
    def _normalize_ruff(
        cls: type[Self],
        tool: str,
        payload: JsonValue,
    ) -> list[JsonValue]:
        """Normalize Ruff diagnostics.

        Args:
            tool: Producing tool name.
            payload: Native JSON payload.

        Returns:
            Diagnostics sharing one schema.

        Raises:
            TypeError: If the native payload has an unexpected shape.

        """
        if not isinstance(payload, list):
            msg: str = f"Unexpected {tool} JSON structure."
            raise TypeError(msg)
        findings: list[JsonValue] = []
        for item in payload:
            if not isinstance(item, dict):
                msg = f"Unexpected {tool} diagnostic."
                raise TypeError(msg)
            location: JsonValue = item.get("location")
            end_location: JsonValue = item.get("end_location", location)
            if not isinstance(location, dict) or not isinstance(
                end_location,
                dict,
            ):
                msg = f"{tool} diagnostic has no location."
                raise TypeError(msg)
            findings.append(
                {
                    "tool": tool,
                    "file": str(object=item.get("filename", "")),
                    "rule": str(object=item.get("code", "")),
                    "severity": "warning",
                    "message": str(object=item.get("message", "")),
                    **cls._position(
                        line=location.get("row", 0),
                        column=location.get("column", 0),
                        end_line=end_location.get("row", 0),
                        end_column=end_location.get("column", 0),
                    ),
                },
            )
        return findings

    @classmethod
    def _normalize_basedpyright(
        cls: type[Self],
        payload: JsonValue,
    ) -> list[JsonValue]:
        """Normalize BasedPyright diagnostics.

        Args:
            payload: Native JSON payload.

        Returns:
            Diagnostics sharing one schema.

        Raises:
            TypeError: If the native payload has an unexpected shape.

        """
        if not isinstance(payload, dict):
            msg: str = "Unexpected BasedPyright JSON structure."
            raise TypeError(msg)
        diagnostics: JsonValue = payload.get("generalDiagnostics", [])
        if not isinstance(diagnostics, list):
            msg = "Unexpected BasedPyright diagnostics."
            raise TypeError(msg)
        findings: list[JsonValue] = []
        for item in diagnostics:
            if not isinstance(item, dict):
                msg = "Unexpected BasedPyright diagnostic."
                raise TypeError(msg)
            range_value: JsonValue = item.get("range")
            if not isinstance(range_value, dict):
                msg = "BasedPyright diagnostic has no range."
                raise TypeError(msg)
            start: JsonValue = range_value.get("start")
            end: JsonValue = range_value.get("end", start)
            if not isinstance(start, dict) or not isinstance(end, dict):
                msg = "Invalid BasedPyright source range."
                raise TypeError(msg)
            findings.append(
                {
                    "tool": "basedpyright",
                    "file": str(object=item.get("file", "")),
                    "rule": str(object=item.get("rule", "")),
                    "severity": cls._severity(value=item.get("severity")),
                    "message": str(object=item.get("message", "")),
                    **cls._position(
                        line=start.get("line", 0),
                        column=start.get("character", 0),
                        end_line=end.get("line", 0),
                        end_column=end.get("character", 0),
                        zero_based=True,
                    ),
                },
            )
        return findings

    @classmethod
    def _normalize_pyrefly(
        cls: type[Self],
        payload: JsonValue,
    ) -> list[JsonValue]:
        """Normalize Pyrefly diagnostics.

        Args:
            payload: Native JSON payload.

        Returns:
            Diagnostics sharing one schema.

        Raises:
            TypeError: If the native payload has an unexpected shape.

        """
        items: JsonValue = (
            payload.get("errors", payload.get("diagnostics", []))
            if isinstance(payload, dict)
            else payload
        )
        if not isinstance(items, list):
            msg: str = "Unexpected Pyrefly JSON structure."
            raise TypeError(msg)
        findings: list[JsonValue] = []
        for item in items:
            if not isinstance(item, dict):
                msg = "Unexpected Pyrefly diagnostic."
                raise TypeError(msg)
            range_value: JsonValue = item.get("range", item.get("location"))
            position: dict[str, JsonValue]
            if isinstance(range_value, dict):
                start: JsonValue = range_value.get("start", range_value)
                end: JsonValue = range_value.get("end", start)
                if not isinstance(start, dict) or not isinstance(end, dict):
                    msg = "Invalid Pyrefly source range."
                    raise TypeError(msg)
                position = cls._position(
                    line=start.get("line", 0),
                    column=start.get("column", start.get("character", 0)),
                    end_line=end.get("line", 0),
                    end_column=end.get("column", end.get("character", 0)),
                    zero_based=(
                        start.get("character") is not None
                        and start.get("column") is None
                    ),
                )
            else:
                position = cls._position(
                    line=item.get("line", 0),
                    column=item.get("column", 0),
                    end_line=item.get("stop_line", item.get("line", 0)),
                    end_column=item.get("stop_column", item.get("column", 0)),
                )
            findings.append(
                {
                    "tool": "pyrefly",
                    "file": str(object=item.get("file", item.get("path", ""))),
                    "rule": str(object=item.get("name", item.get("code", ""))),
                    "severity": cls._severity(
                        value=item.get("severity", "warning"),
                    ),
                    "message": str(
                        object=item.get(
                            "message",
                            item.get(
                                "description",
                                item.get("concise_description", ""),
                            ),
                        ),
                    ),
                    **position,
                },
            )
        return findings

    @classmethod
    def _normalize_eslint(
        cls: type[Self],
        payload: JsonValue,
    ) -> list[JsonValue]:
        """Normalize ESLint diagnostics.

        Args:
            payload: Native JSON payload.

        Returns:
            Diagnostics sharing one schema.

        Raises:
            TypeError: If the native payload has an unexpected shape.

        """
        if not isinstance(payload, list):
            msg: str = "Unexpected ESLint JSON structure."
            raise TypeError(msg)
        findings: list[JsonValue] = []
        for file_result in payload:
            if not isinstance(file_result, dict):
                msg = "Unexpected ESLint file result."
                raise TypeError(msg)
            messages: JsonValue = file_result.get("messages", [])
            if not isinstance(messages, list):
                msg = "Unexpected ESLint messages."
                raise TypeError(msg)
            for item in messages:
                if not isinstance(item, dict):
                    msg = "Unexpected ESLint diagnostic."
                    raise TypeError(msg)
                if cls._eslint_ignored(item=item):
                    continue
                findings.append(
                    {
                        "tool": "eslint",
                        "file": str(object=file_result.get("filePath", "")),
                        "rule": str(object=item.get("ruleId", "")),
                        "severity": cls._severity(value=item.get("severity")),
                        "message": str(object=item.get("message", "")),
                        **cls._position(
                            line=item.get("line", 0),
                            column=item.get("column", 0),
                            end_line=item.get("endLine", item.get("line", 0)),
                            end_column=item.get(
                                "endColumn",
                                item.get("column", 0),
                            ),
                        ),
                    },
                )
        return findings

    @classmethod
    def _normalize_stylelint(
        cls: type[Self],
        payload: JsonValue,
    ) -> list[JsonValue]:
        """Normalize Stylelint diagnostics.

        Args:
            payload: Native JSON payload.

        Returns:
            Diagnostics sharing one schema.

        Raises:
            TypeError: If the native payload has an unexpected shape.

        """
        if not isinstance(payload, list):
            msg: str = "Unexpected Stylelint JSON structure."
            raise TypeError(msg)
        findings: list[JsonValue] = []
        for file_result in payload:
            if not isinstance(file_result, dict):
                msg = "Unexpected Stylelint file result."
                raise TypeError(msg)
            warnings: JsonValue = file_result.get("warnings", [])
            if not isinstance(warnings, list):
                msg = "Unexpected Stylelint warnings."
                raise TypeError(msg)
            for item in warnings:
                if not isinstance(item, dict):
                    msg = "Unexpected Stylelint diagnostic."
                    raise TypeError(msg)
                findings.append(
                    {
                        "tool": "stylelint",
                        "file": str(
                            object=file_result.get(
                                "source",
                                file_result.get("filePath", ""),
                            ),
                        ),
                        "rule": str(object=item.get("rule", "")),
                        "severity": cls._severity(
                            value=item.get("severity", "warning"),
                        ),
                        "message": str(object=item.get("text", "")),
                        **cls._position(
                            line=item.get("line", 0),
                            column=item.get("column", 0),
                            end_line=item.get("endLine", item.get("line", 0)),
                            end_column=item.get(
                                "endColumn",
                                item.get("column", 0),
                            ),
                        ),
                    },
                )
        return findings

    @classmethod
    def _normalize_htmlhint(
        cls: type[Self],
        payload: JsonValue,
    ) -> list[JsonValue]:
        """Normalize HTMLHint diagnostics.

        Args:
            payload: Native JSON payload.

        Returns:
            Diagnostics sharing one schema.

        Raises:
            TypeError: If the native payload has an unexpected shape.

        """
        items: JsonValue = (
            payload.get("messages", payload.get("results", []))
            if isinstance(payload, dict)
            else payload
        )
        if not isinstance(items, list):
            msg: str = "Unexpected HTMLHint JSON structure."
            raise TypeError(msg)
        findings: list[JsonValue] = []
        for file_result in items:
            if not isinstance(file_result, dict):
                msg = "Unexpected HTMLHint result."
                raise TypeError(msg)
            default: list[JsonValue] = (
                [file_result] if "message" in file_result else []
            )
            messages: JsonValue = file_result.get("messages", default)
            if not isinstance(messages, list):
                msg = "Unexpected HTMLHint messages."
                raise TypeError(msg)
            for item in messages:
                if not isinstance(item, dict):
                    msg = "Unexpected HTMLHint diagnostic."
                    raise TypeError(msg)
                findings.append(
                    {
                        "tool": "htmlhint",
                        "file": str(
                            object=file_result.get(
                                "file",
                                file_result.get("filePath", ""),
                            ),
                        ),
                        "rule": cls._rule_name(
                            value=item.get("rule", item.get("ruleId", "")),
                        ),
                        "severity": cls._severity(
                            value=item.get("severity", "warning"),
                        ),
                        "message": str(object=item.get("message", "")),
                        **cls._position(
                            line=item.get("line", 0),
                            column=item.get("col", item.get("column", 0)),
                            end_line=item.get("line", 0),
                            end_column=item.get("col", item.get("column", 0)),
                        ),
                    },
                )
        return findings

    @classmethod
    def _exception_message_fix_candidates(
        cls: type[Self],
        *,
        tree: Module,
        parents: Mapping[AST, AST],
    ) -> list[ExceptionMessageFixCandidate]:
        """Return exception-message candidates with their assignments.

        Args:
            tree: Parsed module.
            parents: Child-to-parent AST mapping.

        Returns:
            Candidates ordered by source position.

        """
        return sorted(
            (
                (
                    name,
                    raised_name,
                    assigned_value,
                    cls._exception_message_assignment(
                        name=name,
                        parents=parents,
                    ),
                )
                for name, raised_name, assigned_value in (
                    cls._exception_message_candidates(tree=tree)
                )
            ),
            key=lambda candidate: (
                candidate[0].lineno,
                candidate[0].col_offset,
            ),
        )

    @classmethod
    def _msg_binding_blocks_candidate(
        cls: type[Self],
        *,
        binding: Name,
        candidate: Name,
        terminating_msg_names: frozenset[Name],
        parents: Mapping[AST, AST],
    ) -> bool:
        """Return whether a prior ``msg`` binding can reach a candidate.

        A ``msg`` used by the canonical ``assignment; raise ... (msg)``
        pattern does not reach later code because that path terminates at the
        raise. Other prior bindings conservatively block the rename.

        Args:
            binding: Earlier ``msg`` store.
            candidate: Candidate assignment target.
            terminating_msg_names: ``msg`` stores immediately consumed by a
                raise.
            parents: Child-to-parent AST mapping.

        Returns:
            Whether renaming the candidate could overwrite a live binding.

        """
        return (
            binding.lineno < candidate.lineno
            and binding not in terminating_msg_names
            and cls._lexical_scope(node=binding, parents=parents)
            is cls._lexical_scope(node=candidate, parents=parents)
        )

    @classmethod
    def _fix_exception_messages(
        cls: type[Self],
        *,
        file: Path,
        source: bytes | None = None,
        tree: Module | None = None,
    ) -> bool:
        """Rename control-flow-safe ``PY003`` message locals to ``msg``.

        Earlier ``msg`` bindings block a rename when they can reach the
        candidate. A canonical exception-message binding followed immediately
        by its raise is terminating and therefore does not block a later
        candidate. Existing or newly established ``msg`` annotations are
        reused: a renamed annotated assignment drops its duplicate annotation
        once ``msg`` has already been annotated in the lexical scope.

        Args:
            file: Python source file to rewrite in place.
            source: Pre-read source bytes, when already available.
            tree: Pre-parsed source tree matching ``source``.

        Returns:
            Whether the file was changed.

        """
        loaded: tuple[bytes, Module] | None = cls._exception_fix_source(
            file=file,
            source=source,
            tree=tree,
        )
        if loaded is None:
            return False
        source_bytes, parsed_tree = loaded
        parents: dict[AST, AST] = {
            child: parent
            for parent in walk(node=parsed_tree)
            for child in iter_child_nodes(node=parent)
        }
        candidates: list[ExceptionMessageFixCandidate] = (
            cls._exception_message_fix_candidates(
                tree=parsed_tree,
                parents=parents,
            )
        )
        terminating_msg_names: frozenset[Name] = frozenset(
            name
            for name, _raised_name, _value, _assignment in candidates
            if name.id == "msg"
        )
        msg_bindings: list[Name] = sorted(
            (
                item
                for item in walk(node=parsed_tree)
                if isinstance(item, Name)
                and item.id == "msg"
                and isinstance(item.ctx, Store)
            ),
            key=lambda item: (item.lineno, item.col_offset),
        )
        annotated_scopes: set[AST] = {
            cls._lexical_scope(node=item.target, parents=parents)
            for item in walk(node=parsed_tree)
            if isinstance(item, AnnAssign)
            and isinstance(item.target, Name)
            and item.target.id == "msg"
        }
        replacements: list[tuple[int, int, bytes]] = []
        lines: list[bytes] = source_bytes.splitlines(keepends=True)
        offsets: list[int] = []
        offset: int = 0
        for line in lines:
            offsets.append(offset)
            offset += len(line)
        for name, raised_name, assigned_value, assignment in candidates:
            if name.id == "msg":
                continue
            scope: AST = cls._lexical_scope(node=name, parents=parents)
            if any(
                isinstance(item, Name) and item.id == name.id
                for item in walk(node=assigned_value)
            ) or any(
                cls._msg_binding_blocks_candidate(
                    binding=binding,
                    candidate=name,
                    terminating_msg_names=terminating_msg_names,
                    parents=parents,
                )
                for binding in msg_bindings
            ):
                continue
            name_end_line: int | None = name.end_lineno
            name_end_column: int | None = name.end_col_offset
            raised_end_line: int | None = raised_name.end_lineno
            raised_end_column: int | None = raised_name.end_col_offset
            annotation_end_line: int | None = (
                assignment.annotation.end_lineno
                if isinstance(assignment, AnnAssign)
                else None
            )
            annotation_end_column: int | None = (
                assignment.annotation.end_col_offset
                if isinstance(assignment, AnnAssign)
                else None
            )
            if (
                name_end_line is None
                or name_end_column is None
                or raised_end_line is None
                or raised_end_column is None
                or (
                    isinstance(assignment, AnnAssign)
                    and scope in annotated_scopes
                    and (
                        annotation_end_line is None
                        or annotation_end_column is None
                    )
                )
            ):
                continue
            replacements.append(
                (
                    offsets[name.lineno - 1] + name.col_offset,
                    (
                        offsets[annotation_end_line - 1]
                        + annotation_end_column
                        if isinstance(assignment, AnnAssign)
                        and scope in annotated_scopes
                        and annotation_end_line is not None
                        and annotation_end_column is not None
                        else offsets[name_end_line - 1] + name_end_column
                    ),
                    b"msg",
                ),
            )
            if (
                isinstance(assignment, AnnAssign)
                and scope not in annotated_scopes
            ):
                annotated_scopes.add(scope)
            replacements.append(
                (
                    offsets[raised_name.lineno - 1] + raised_name.col_offset,
                    offsets[raised_end_line - 1] + raised_end_column,
                    b"msg",
                ),
            )
            msg_bindings.append(name)
            terminating_msg_names = terminating_msg_names.union((name,))
        if not replacements:
            return False
        for start, end, replacement in sorted(
            replacements,
            key=lambda item: item[0],
            reverse=True,
        ):
            source_bytes: bytes = (
                source_bytes[:start] + replacement + source_bytes[end:]
            )
        file.write_bytes(data=source_bytes)
        return True

    @classmethod
    def _exception_message_findings(
        cls: type[Self],
        file: Path,
        tree: Module,
    ) -> list[JsonValue]:
        """Detect exception-message locals that are not named ``msg``.

        Args:
            file: Python source file.
            tree: Parsed module.

        Returns:
            Normalized diagnostics.

        """
        return [
            cls._finding(
                tool="custom_python",
                file=file,
                rule="PY003",
                message=(
                    f"Exception message variable `{name.id}` should be named "
                    "`msg`."
                ),
                position=(name.lineno, name.col_offset + 1),
            )
            for name, _raised_name, _assigned_value in (
                cls._exception_message_candidates(tree=tree)
            )
            if name.id != "msg"
        ]

    @classmethod
    def _method_kind_findings(
        cls: type[Self],
        file: Path,
        tree: Module,
        virtual_methods: frozenset[tuple[Path, int]] = Constants.empty_methods,
    ) -> list[JsonValue]:
        """Detect Python methods whose binding kind can be improved.

        Args:
            file: Python source file.
            tree: Parsed module.
            virtual_methods: Methods participating in inheritance contracts.

        Returns:
            Normalized diagnostics.

        """
        findings: list[JsonValue] = []
        for class_node in (
            item for item in walk(node=tree) if isinstance(item, ClassDef)
        ):
            for method in (
                item
                for item in class_node.body
                if isinstance(item, (FunctionDef, AsyncFunctionDef))
            ):
                if (
                    method.name.startswith("__") and method.name.endswith("__")
                ) or (file, method.lineno) in virtual_methods:
                    continue
                if all(
                    (
                        isinstance(statement, Expr)
                        and isinstance(statement.value, Constant)
                        and (
                            isinstance(statement.value.value, str)
                            or statement.value.value is Ellipsis
                        )
                    )
                    or isinstance(statement, Pass)
                    for statement in method.body
                ):
                    continue
                decorators: frozenset[str] = frozenset(
                    decorator.id
                    for decorator in method.decorator_list
                    if isinstance(decorator, Name)
                )
                if "override" in decorators or any(
                    isinstance(item, Call)
                    and isinstance(item.func, Name)
                    and item.func.id == "super"
                    and not item.args
                    and not item.keywords
                    for item in walk(node=method)
                ):
                    continue
                names: frozenset[str] = frozenset(
                    item.id
                    for item in walk(node=method)
                    if isinstance(item, Name) and isinstance(item.ctx, Load)
                )
                diagnostic: tuple[str, str] | None = cls._method_kind(
                    decorators=decorators,
                    names=names,
                    method_name=method.name,
                    class_name=class_node.name,
                )
                if diagnostic is None:
                    continue
                rule, message = diagnostic
                findings.append(
                    cls._finding(
                        tool="custom_python",
                        file=file,
                        rule=rule,
                        message=message,
                        position=(method.lineno, method.col_offset + 1),
                    ),
                )
        return findings

    @classmethod
    def _virtual_methods(
        cls: type[Self],
        *,
        trees: Mapping[Path, Module],
    ) -> frozenset[tuple[Path, int]]:
        """Find methods whose binding is shared by a base and an override.

        Only uniquely resolved local classes participate. Imported aliases
        are resolved by their declared symbol; ambiguous names do not prove
        an inheritance relationship. External overrides remain verifiable
        through ``typing.override`` and the type checker.

        Args:
            trees: Parsed Python modules being exactused.

        Returns:
            Source positions of base methods and their matching overrides.

        """
        classes: dict[str, list[tuple[Path, ClassDef]]] = (
            cls._class_definitions(trees=trees)
        )
        aliases: dict[Path, dict[str, str]] = {
            file: {
                alias.asname or alias.name: alias.name
                for statement in tree.body
                if isinstance(statement, ImportFrom)
                for alias in statement.names
            }
            for file, tree in trees.items()
        }
        virtual: set[tuple[Path, int]] = set()
        for definitions in classes.values():
            for file, child in definitions:
                methods: dict[str, int] = {
                    method.name: method.lineno
                    for method in child.body
                    if isinstance(method, (FunctionDef, AsyncFunctionDef))
                }
                pending: list[tuple[Path, ClassDef]] = [(file, child)]
                visited: set[tuple[Path, int]] = set()
                while pending:
                    owner_file: Path
                    owner: ClassDef
                    owner_file, owner = pending.pop()
                    if (owner_file, owner.lineno) in visited:
                        continue
                    visited.add((owner_file, owner.lineno))
                    for base in owner.bases:
                        name: str = (
                            aliases[owner_file].get(base.id, base.id)
                            if isinstance(base, Name)
                            else base.attr
                            if isinstance(base, Attribute)
                            else ""
                        )
                        candidates: list[tuple[Path, ClassDef]] = classes.get(
                            name,
                            [],
                        )
                        local: list[tuple[Path, ClassDef]] = [
                            candidate
                            for candidate in candidates
                            if candidate[0] == owner_file
                        ]
                        matches: list[tuple[Path, ClassDef]] = (
                            local or candidates
                        )
                        if len(matches) != 1:
                            continue
                        parent_file: Path
                        parent: ClassDef
                        parent_file, parent = matches[0]
                        pending.append((parent_file, parent))
                        for method in parent.body:
                            if (
                                isinstance(
                                    method,
                                    (FunctionDef, AsyncFunctionDef),
                                )
                                and method.name in methods
                            ):
                                virtual.update(
                                    (
                                        (file, methods[method.name]),
                                        (parent_file, method.lineno),
                                    ),
                                )
        return frozenset(virtual)

    @classmethod
    def _python_conventions(
        cls: type[Self],
        files: Sequence[Path],
        bare_import_exceptions: Sequence[str],
        *,
        fix: bool = False,
        transform_runtime: _TransformRuntime | None = None,
        on_file: Callable[[Path], None] = _ignore_file,
    ) -> list[JsonValue]:
        """Exactus project-specific Python conventions.

        Args:
            files: Python source files.
            bare_import_exceptions: Module names allowed as bare imports.
            fix: Whether safe custom convention fixes are applied.
            transform_runtime: Ruff runtime for string transforms and
                the stabilization pass over rewritten files.
            on_file: Callback invoked for every visited file.

        Returns:
            Normalized custom diagnostics.

        """
        findings: list[JsonValue] = []
        exceptions: frozenset[str] = frozenset(bare_import_exceptions)
        trees: dict[Path, Module] = {}
        transformed: list[Path] = []
        transform_widths: dict[Path | None, int] = {}
        trace(
            step=(f"conventions: python — parse pass ({len(files)} files)"),
            depth=3,
        )
        for file in files:
            try:
                source: bytes = file.read_bytes()
                tree: Module = parse(
                    source=source.decode(encoding="utf-8"),
                    filename=str(object=file),
                )
                changed: bool = fix and cls._fix_exception_messages(
                    file=file,
                    source=source,
                    tree=tree,
                )
                if changed:
                    tree = parse(
                        source=file.read_text(encoding="utf-8"),
                        filename=str(object=file),
                    )
                converted: TransformResult | None = (
                    cls._fix_string_transforms(
                        file=file,
                        tree=tree,
                        ruff_command=(
                            transform_runtime.ruff_command
                            if transform_runtime is not None
                            else None
                        ),
                        widths=transform_widths,
                    )
                    if fix
                    else None
                )
                changed = changed or (
                    converted is not None and converted.changed
                )
                if converted is not None and converted.changed:
                    transformed.append(file)
                    trees[file] = converted.tree
                else:
                    trees[file] = (
                        parse(
                            source=file.read_text(encoding="utf-8"),
                            filename=str(object=file),
                        )
                        if changed
                        else tree
                    )
            except (SyntaxError, UnicodeDecodeError):
                continue  # Ruff reports the syntax error itself.
            finally:
                on_file(file)
        if fix and transform_runtime is not None:
            cls._stabilize_transforms(
                files=transformed,
                cwd=transform_runtime.cwd,
                ruff_command=transform_runtime.ruff_command,
                trees=trees,
            )
        virtual_methods: frozenset[tuple[Path, int]] = cls._virtual_methods(
            trees=trees,
        )
        trace(step="conventions: python — findings pass", depth=3)
        for file, tree in trees.items():
            findings.extend(
                cls._exception_message_findings(file=file, tree=tree),
            )
            findings.extend(
                cls._method_kind_findings(
                    file=file,
                    tree=tree,
                    virtual_methods=virtual_methods,
                ),
            )
            findings.extend(
                cls._bare_import_findings(
                    file=file,
                    tree=tree,
                    exceptions=exceptions,
                ),
            )
            findings.extend(
                cls._uppercase_global_findings(file=file, tree=tree),
            )
            on_file(file)
        return findings

    @classmethod
    def _stabilize_transforms(
        cls: type[Self],
        *,
        files: Sequence[Path],
        cwd: Path | None,
        ruff_command: tuple[str, ...] | None,
        trees: dict[Path, Module],
    ) -> None:
        """Re-run Ruff over string-transformed files and refresh trees.

        Args:
            files: Files rewritten by the string transformer.
            cwd: Project working directory; ``None`` skips stabilization.
            ruff_command: Resolved Ruff executable prefix; ``None`` skips
                stabilization.
            trees: Parsed modules refreshed in place for rewritten files.

        """
        if not files or cwd is None or ruff_command is None:
            return
        arguments: list[str] = [str(object=file) for file in files]
        for command in (
            (*ruff_command, "format", *arguments),
            (
                *ruff_command,
                "check",
                *Constants.ruff_policy(cwd=cwd),
                "--fix",
                *arguments,
            ),
            (*ruff_command, "format", *arguments),
        ):
            _ = cls.run_command(command=command, cwd=cwd)
        for file in files:
            try:
                trees[file] = parse(
                    source=file.read_text(encoding="utf-8"),
                    filename=str(object=file),
                )
            except (SyntaxError, UnicodeDecodeError):
                _ = trees.pop(file, None)

    @classmethod
    def _bare_import_findings(
        cls: type[Self],
        file: Path,
        tree: Module,
        exceptions: frozenset[str],
    ) -> list[JsonValue]:
        """Detect bare imports used only through attribute access.

        Args:
            file: Python source file.
            tree: Parsed module.
            exceptions: Module names allowed as bare imports.

        Returns:
            Normalized diagnostics.

        """
        findings: list[JsonValue] = []
        parents: dict[int, AST] = {}
        for parent in NodeVisitorWalk.walk(tree=tree):
            for child in NodeVisitorWalk.children(node=parent):
                parents[id(child)] = parent
        for statement in tree.body:
            if not isinstance(statement, Import):
                continue
            for alias in statement.names:
                bound: str = alias.asname or alias.name.split(sep=".")[0]
                if alias.name.split(sep=".")[0] in exceptions:
                    continue
                uses: list[Name] = [
                    candidate
                    for candidate in NodeVisitorWalk.walk(tree=tree)
                    if isinstance(candidate, Name)
                    and isinstance(candidate.ctx, Load)
                    and candidate.id == bound
                ]
                if not uses:
                    continue
                attributes: list[str] = []
                for use in uses:
                    parent_node: AST | None = parents.get(id(use))
                    if not (
                        isinstance(parent_node, Attribute)
                        and parent_node.value is use
                    ):
                        break
                    attributes.append(parent_node.attr)
                else:
                    findings.append(
                        cls._finding(
                            tool="custom_python",
                            file=file,
                            rule="PY001",
                            message=(
                                f"Bare import `{alias.name}` is only "
                                "used through attributes "
                                f"({', '.join(sorted(set(attributes)))}); "
                                "prefer `from ... import ...`."
                            ),
                            position=(
                                statement.lineno,
                                statement.col_offset + 1,
                            ),
                        ),
                    )
        return findings

    @classmethod
    def _uppercase_global_findings(
        cls: type[Self],
        file: Path,
        tree: Module,
    ) -> list[JsonValue]:
        """Detect uppercase variables without a Final declaration.

        Args:
            file: Python source file.
            tree: Parsed module.

        Returns:
            Normalized diagnostics.

        """
        findings: list[JsonValue] = []
        for statement in tree.body:
            names: list[Name] = []
            if isinstance(statement, Assign) and not cls._generic_binder_call(
                statement=statement,
            ):
                names.extend(
                    target
                    for target in statement.targets
                    if isinstance(target, Name)
                )
            # PY-NAM-0001 requires uppercase names for Final constants.
            elif (
                isinstance(statement, AnnAssign)
                and isinstance(statement.target, Name)
                and not (
                    isinstance(statement.annotation, Subscript)
                    and isinstance(statement.annotation.value, Name)
                    and statement.annotation.value.id == "Final"
                )
            ):
                names.append(statement.target)
            findings.extend(
                cls._finding(
                    tool="custom_python",
                    file=file,
                    rule="PY002",
                    message=(
                        f"Module global `{name.id}` is uppercase but is not "
                        "declared Final. Use an immutable constant or "
                        "move mutable state to an explicit instance "
                        "dependency."
                    ),
                    position=(name.lineno, name.col_offset + 1),
                )
                for name in names
                if Constants.upper_global_pattern.fullmatch(string=name.id)
            )
        return findings

    @classmethod
    def _javascript_conventions(
        cls: type[Self],
        files: Sequence[Path],
        *,
        on_file: Callable[[Path], None] = _ignore_file,
    ) -> list[JsonValue]:
        """Exactus project-specific JavaScript class/function conventions.

        Args:
            files: JavaScript and JSX files.
            on_file: Callback invoked for every visited file.

        Returns:
            Normalized custom diagnostics.

        """
        findings: list[JsonValue] = []
        sources: dict[Path, str] = {
            file: file.read_text(encoding="utf-8") for file in files
        }
        virtual: dict[str, frozenset[str]] = cls._javascript_virtual_methods(
            sources=sources,
        )
        for file, source in sources.items():
            class_ranges: list[tuple[int, int]] = []
            for class_match in Constants.js_class_pattern.finditer(
                string=source,
            ):
                class_ranges.append(
                    (class_match.start("body"), class_match.end("body")),
                )
                findings.extend(
                    cls._javascript_class_conventions(
                        source=source,
                        file=file,
                        class_match=class_match,
                        virtual_methods=virtual.get(
                            class_match.group("name"),
                            frozenset(),
                        ),
                    ),
                )
            for match in Constants.js_function_pattern.finditer(string=source):
                position: int = match.start()
                if any(
                    start <= position <= end for start, end in class_ranges
                ):
                    continue
                line, column = cls._line_column(text=source, offset=position)
                findings.append(
                    cls._finding(
                        tool="custom_javascript",
                        file=file,
                        rule="JS004",
                        message=(
                            f"Function `{match.group('name')}` uses function "
                            "declaration syntax; prefer arrow notation."
                        ),
                        position=(line, column),
                    ),
                )
            on_file(file)
        return findings

    @classmethod
    def _javascript_class_conventions(
        cls: type[Self],
        *,
        source: str,
        file: Path,
        class_match: Match[str],
        virtual_methods: frozenset[str],
    ) -> list[JsonValue]:
        """Exactus methods and arrow fields inside one class body.

        Args:
            source: JavaScript source containing the class.
            file: Source file being scanned.
            class_match: Match produced by ``js_class_pattern``.
            virtual_methods: Methods preserving an inheritance contract.

        Returns:
            Normalized custom diagnostics for the class body.

        """
        findings: list[JsonValue] = []
        body: str = class_match.group("body")
        body_start: int = class_match.start("body")
        method_ranges: list[tuple[int, int]] = []
        for match in Constants.js_method_pattern.finditer(string=body):
            absolute: int = body_start + match.start()
            name: str = match.group("name")
            is_static: bool = match.group("static") is not None
            brace: int = body_start + match.end() - 1
            end: int = JavaScriptScanner.block_end(source=source, start=brace)
            method_ranges.append((brace, end))
            method_body: str = source[brace + 1 : end]
            line, column = cls._line_column(text=source, offset=absolute)
            if (
                not is_static
                and name not in virtual_methods
                and "this" not in JavaScriptScanner.tokens(source=method_body)
            ):
                findings.append(
                    cls._finding(
                        tool="custom_javascript",
                        file=file,
                        rule="JS001",
                        message=(
                            f"Class method `{name}` does not use "
                            "`this`; make it a static arrow method."
                        ),
                        position=(line, column),
                    ),
                )
            elif is_static:
                findings.append(
                    cls._finding(
                        tool="custom_javascript",
                        file=file,
                        rule="JS002",
                        message=(
                            f"Static method `{name}` uses method "
                            "syntax; static methods should use arrow "
                            "notation."
                        ),
                        position=(line, column),
                    ),
                )
        for match in Constants.js_arrow_field_pattern.finditer(string=body):
            if match.group("static") is not None:
                continue
            absolute = body_start + match.start()
            if any(start <= absolute <= end for start, end in method_ranges):
                continue
            # `x = (v) => v` following a comma continues a `const`
            # declaration; it is a local, not a class field.
            if body[: match.start()].rstrip().endswith(","):
                continue
            line, column = cls._line_column(text=source, offset=absolute)
            findings.append(
                cls._finding(
                    tool="custom_javascript",
                    file=file,
                    rule="JS003",
                    message=(
                        f"Instance method `{match.group('name')}` "
                        "uses arrow notation; only static methods "
                        "and standalone functions should be arrows."
                    ),
                    position=(line, column),
                ),
            )
        return findings

    @classmethod
    def _javascript_inline_styles(
        cls: type[Self],
        files: Sequence[Path],
        *,
        on_file: Callable[[Path], None] = _ignore_file,
    ) -> list[JsonValue]:
        """Detect static JavaScript inline-style mutations.

        Static ``element.style.property = value``, ``style.setProperty()``,
        and ``Object.assign(element.style, {...})`` declarations should be
        represented by CSS classes. Values derived from JavaScript variables
        or other runtime expressions are intentionally not reported.

        Args:
            files: JavaScript and JSX source files.
            on_file: Callback invoked for every visited file.

        Returns:
            Normalized custom diagnostics.

        """
        checks: tuple[tuple[Pattern[str], str], ...] = (
            (
                Constants.js_style_assignment_pattern,
                (
                    "is assigned directly through `.style`; replace the "
                    "styling with a CSS class and toggle/apply that class "
                    "from JavaScript."
                ),
            ),
            (
                Constants.js_style_set_property_pattern,
                (
                    "is set through `style.setProperty()`; replace the "
                    "styling with a CSS class."
                ),
            ),
        )
        findings: list[JsonValue] = []
        for file in files:
            text: str = file.read_text(encoding="utf-8")
            protected: tuple[tuple[int, int], ...] = (
                JavaScriptDelimiterSimplifier.protected_spans(source=text)
            )
            for pattern, detail in checks:
                for match in pattern.finditer(string=text):
                    if JavaScriptDelimiterSimplifier.inside_protected(
                        index=match.start(),
                        protected=protected,
                    ):
                        continue
                    if not cls._js_static_style_value(
                        value=match.group("value"),
                    ):
                        continue
                    findings.append(
                        cls._finding(
                            tool="custom_javascript",
                            file=file,
                            rule="JS005",
                            message=(
                                "Static inline style "
                                f"`{match.group('property')}` {detail}"
                            ),
                            position=cls._line_column(
                                text=text,
                                offset=match.start(),
                            ),
                        ),
                    )
            for (
                assign_match
            ) in Constants.js_object_assign_style_pattern.finditer(
                string=text,
            ):
                if JavaScriptDelimiterSimplifier.inside_protected(
                    index=assign_match.start(),
                    protected=protected,
                ):
                    continue
                body: str = assign_match.group("body")
                for (
                    property_match
                ) in Constants.js_object_property_pattern.finditer(
                    string=body,
                ):
                    if not cls._js_static_style_value(
                        value=property_match.group("value"),
                    ):
                        continue
                    findings.append(
                        cls._finding(
                            tool="custom_javascript",
                            file=file,
                            rule="JS006",
                            message=(
                                "Static inline style "
                                f"`{property_match.group('property')}` is "
                                "assigned through `Object.assign(...style, "
                                "{...})`; move it to a CSS class."
                            ),
                            position=cls._line_column(
                                text=text,
                                offset=(
                                    assign_match.start("body")
                                    + property_match.start()
                                ),
                            ),
                        ),
                    )
            on_file(file)
        return findings

    @classmethod
    def _css_violation_reasons(
        cls: type[Self],
        property_name: str,
        remaining: str,
        *,
        allowed: bool,
    ) -> list[str]:
        """Return violation categories for one CSS declaration.

        Args:
            property_name: Lowercased CSS property name.
            remaining: Declaration value without ``var(...)`` references.
            allowed: Whether the compact value is a permitted literal.

        Returns:
            Ordered violation categories, possibly empty.

        """
        if allowed or remaining.strip().lower() in {
            "currentcolor",
            "inherit",
            "initial",
            "unset",
            "revert",
            "revert-layer",
        }:
            return []
        reasons: list[str] = []
        if Constants.css_measure_pattern.search(string=remaining):
            reasons.append("measure")
        if cls._css_has_disallowed_number(value=remaining):
            reasons.append("numeric value")
        if (
            property_name in Constants.css_font_text_properties
            and remaining.strip(" /,")
        ):
            reasons.append("font/text value")
        if Constants.css_color_pattern.search(string=remaining):
            reasons.append("color")
        if Constants.css_gradient_pattern.search(string=remaining):
            reasons.append("gradient")
        if property_name.startswith(("transition", "animation")) and (
            Constants.css_time_pattern.search(string=remaining)
        ):
            reasons.append("transition/animation time")
        if property_name in {
            "transition",
            "transition-timing-function",
            "animation",
            "animation-timing-function",
        } and Constants.css_easing_pattern.search(string=remaining):
            reasons.append("easing")
        return reasons

    @classmethod
    def _css_conventions(
        cls: type[Self],
        files: Sequence[Path],
        *,
        on_file: Callable[[Path], None] = _ignore_file,
    ) -> list[JsonValue]:
        """Detect CSS values that bypass project CSS variables.

        Measures, font/text values, colors, transition durations, and
        transition easings must be supplied through CSS custom properties.
        Only the literal values ``0``, ``1``, ``0%``, and ``100%`` are
        permitted directly.

        Args:
            files: CSS source files.
            on_file: Callback invoked for every visited file.

        Returns:
            Normalized custom diagnostics.

        """
        findings: list[JsonValue] = []
        for file in files:
            text: str = file.read_text(encoding="utf-8")
            text = Constants.css_comment_pattern.sub(
                repl=lambda match: Constants.comment_body_pattern.sub(
                    repl=" ",
                    string=match.group(0),
                ),
                string=text,
            )
            for descriptor in reversed(
                tuple(Constants.css_descriptor_pattern.finditer(string=text)),
            ):
                end: int = (
                    JavaScriptScanner.block_end(
                        source=text,
                        start=descriptor.end() - 1,
                    )
                    + 1
                )
                text = (
                    text[: descriptor.start()]
                    + Constants.comment_body_pattern.sub(
                        repl=" ",
                        string=text[descriptor.start() : end],
                    )
                    + text[end:]
                )
            for match in Constants.css_declaration_pattern.finditer(
                string=text,
            ):
                property_name: str = match.group("property").lower()
                if property_name.startswith("--"):
                    continue
                value: str = match.group("value").strip()
                remaining: str = cls._css_unvariable_parts(value=value)
                if not remaining:
                    continue
                reasons: list[str] = cls._css_violation_reasons(
                    property_name=property_name,
                    remaining=remaining,
                    allowed=(
                        remaining.strip().lower()
                        in Constants.css_allowed_literals
                    ),
                )
                if not reasons:
                    continue
                findings.append(
                    cls._finding(
                        tool="custom_css",
                        file=file,
                        rule="CSS001",
                        message=(
                            f"`{property_name}` contains a hardcoded "
                            f"{', '.join(dict.fromkeys(reasons))}; the value "
                            "must come from a CSS variable. This includes "
                            "gradient definitions/components and all numeric "
                            "measurements. Only 0, 1, 0%, and 100% are "
                            "allowed directly."
                        ),
                        position=cls._line_column(
                            text=text,
                            offset=match.start("value"),
                        ),
                    ),
                )
            on_file(file)
        return findings

    @classmethod
    def _css_token_findings(
        cls: type[Self],
        *,
        root: Path,
        files: Sequence[Path],
        context_words: Sequence[str],
    ) -> list[JsonValue]:
        """Audit the stylesheets against the custom-property architecture.

        The audit is cross-file: every stylesheet in scope is resolved as
        one token graph (see ``css_tokens``).

        Args:
            root: Project root.
            files: CSS source files.
            context_words: Words forbidden in CATALOG token names.

        Returns:
            Normalized custom diagnostics.

        """
        findings: tuple[CssTokenFinding, ...] = scan_css_tokens(
            inputs=CssTokenInput(
                root=root,
                files=files,
                context_words=frozenset(
                    word.strip("-").lower()
                    for word in context_words
                    if word.strip("-")
                ),
            ),
        )
        return [
            cls._finding(
                tool="custom_css",
                file=finding.file,
                rule=finding.rule,
                message=finding.message,
                position=(finding.line, 1),
            )
            for finding in findings
        ]

    @classmethod
    def _html_inline_scripts(
        cls: type[Self],
        *,
        file: Path,
        text: str,
    ) -> list[JsonValue]:
        """Detect inline ``<script>`` bodies in one HTML document.

        Scripts loaded through ``src`` and data-only script types such
        as ``application/json`` or ``importmap`` are not executable
        JavaScript blocks and are not reported.

        Args:
            file: HTML source file being scanned.
            text: Comment-stripped document text.

        Returns:
            Normalized custom diagnostics.

        """
        findings: list[JsonValue] = []
        for match in Constants.html_inline_script_pattern.finditer(
            string=text,
        ):
            attrs: str = match.group("attrs")
            if Constants.html_script_src_pattern.search(string=attrs):
                continue
            type_match: Match[str] | None = (
                Constants.html_type_attribute_pattern.search(string=attrs)
            )
            if (
                type_match is not None
                and type_match.group("type").lower()
                in Constants.html_data_script_types
            ):
                continue
            if not match.group("body").strip():
                continue
            findings.append(
                cls._finding(
                    tool="custom_html",
                    file=file,
                    rule="HTML002",
                    message=(
                        "Inline `<script>` block detected; move JavaScript "
                        "to an external file and load it with `src`."
                    ),
                    position=cls._line_column(text=text, offset=match.start()),
                ),
            )
        return findings

    @classmethod
    def _html_conventions(
        cls: type[Self],
        files: Sequence[Path],
        *,
        on_file: Callable[[Path], None] = _ignore_file,
    ) -> list[JsonValue]:
        """Detect JavaScript and CSS embedded in HTML documents.

        ``<style>`` elements, inline ``<script>`` bodies, ``style``
        attributes, ``on*`` event-handler attributes, and
        ``javascript:`` URLs bypass the convention that all styling and
        behavior live in external stylesheets and scripts.

        Args:
            files: HTML source files.
            on_file: Callback invoked for every visited file.

        Returns:
            Normalized custom diagnostics.

        """
        attribute_checks: tuple[tuple[Pattern[str], str, str], ...] = (
            (
                Constants.html_style_attribute_pattern,
                "HTML003",
                (
                    "Inline `style` attribute detected; move CSS to the "
                    "project stylesheet and apply it through a class."
                ),
            ),
            (
                Constants.html_event_attribute_pattern,
                "HTML004",
                (
                    "Inline event handler `{name}` detected; bind events "
                    "from external JavaScript with `addEventListener`."
                ),
            ),
            (
                Constants.html_javascript_url_pattern,
                "HTML005",
                (
                    "`javascript:` URL detected; move the behavior to "
                    "external JavaScript."
                ),
            ),
        )
        findings: list[JsonValue] = []
        for file in files:
            text: str = file.read_text(encoding="utf-8")
            text = Constants.html_comment_pattern.sub(
                repl=lambda match: Constants.comment_body_pattern.sub(
                    repl=" ",
                    string=match.group(0),
                ),
                string=text,
            )
            embedded_ranges: list[tuple[int, int]] = [
                match.span()
                for match in Constants.html_style_block_pattern.finditer(
                    string=text,
                )
            ]
            embedded_ranges.extend(
                match.span()
                for match in Constants.html_inline_script_pattern.finditer(
                    string=text,
                )
            )
            findings.extend(
                cls._finding(
                    tool="custom_html",
                    file=file,
                    rule="HTML001",
                    message=(
                        "Hardcoded `<style>` element detected; move CSS "
                        "to the project stylesheet."
                    ),
                    position=cls._line_column(text=text, offset=match.start()),
                )
                for match in Constants.html_style_tag_pattern.finditer(
                    string=text,
                )
            )
            findings.extend(cls._html_inline_scripts(file=file, text=text))
            for pattern, rule, template in attribute_checks:
                for match in pattern.finditer(string=text):
                    if any(
                        start <= match.start() <= end
                        for start, end in embedded_ranges
                    ):
                        continue
                    findings.append(
                        cls._finding(
                            tool="custom_html",
                            file=file,
                            rule=rule,
                            message=template.format(
                                name=match.groupdict().get("name") or "",
                            ),
                            position=cls._line_column(
                                text=text,
                                offset=match.start(),
                            ),
                        ),
                    )
            on_file(file)
        return findings

    @classmethod
    def _result_json(
        cls: type[Self],
        tool: str,
        result: CommandResult,
        payload: JsonValue,
    ) -> dict[str, JsonValue]:
        """Build a normalized report entry for one tool.

        Args:
            tool: Producing tool name.
            result: Command execution metadata.
            payload: Parsed native tool output.

        Returns:
            JSON-serializable normalized report entry.

        """
        findings: list[JsonValue] = sorted(
            cls._normalize(tool=tool, payload=payload),
            key=cls._sort_key,
        )
        skipped: list[JsonValue] = []
        if tool == "eslint" and isinstance(payload, list):
            for entry in payload:
                if not isinstance(entry, dict):
                    continue
                messages: JsonValue = entry.get("messages", [])
                if not isinstance(messages, list):
                    continue
                skipped.extend(
                    {
                        "file": entry.get("filePath", ""),
                        "reason": item.get("message", ""),
                    }
                    for item in messages
                    if isinstance(item, dict)
                    and cls._eslint_ignored(item=item)
                )
        return cls._payload(
            entries={
                "tool": tool,
                "command": list(result.command),
                "returncode": result.returncode,
                "stderr": cls._tool_stderr(tool=tool, stderr=result.stderr),
                "count": len(findings),
                "findings": findings,
                "skipped_files": skipped,
                "duration_seconds": result.duration_seconds,
            },
        )

    @classmethod
    def _collect_scope(
        cls: type[Self],
        *,
        cwd: Path,
        targets: Sequence[str],
        ignores: Sequence[str],
        config: LintExactusConfig,
        progress: LintProgress,
    ) -> _RunScope:
        """Collect every file needed by the lint stages.

        Args:
            cwd: Project working directory.
            targets: Paths, directories, or glob patterns.
            ignores: Glob patterns excluded from linting.
            config: Stage configuration for the run.
            progress: Progress reporter updated as files are collected.

        Returns:
            Collected files grouped by pipeline stage.

        """
        progress.note(step="collect")
        collected: int = 0
        last_collect_emit: float = monotonic()

        def _on_file(path: Path) -> None:
            """Count collected files and throttle progress updates.

            Args:
                path: File reported by the scope walk.

            """
            nonlocal collected, last_collect_emit
            collected += 1
            trace(step=f"collect: {path}", depth=4)
            now: float = monotonic()
            if now - last_collect_emit < _COLLECT_PROGRESS_INTERVAL:
                return
            last_collect_emit = now
            progress.note(
                step="collect",
                detail=f"{collected} files",
                share=collected / (collected + _COLLECT_PROGRESS_ESTIMATE),
            )

        source_suffixes: frozenset[str] = (
            Constants.python_suffixes
            | Constants.eslint_suffixes
            | Constants.stylelint_suffixes
            | Constants.htmlhint_suffixes
        )
        source_files: frozenset[Path] = cls._matching_files(
            cwd=cwd,
            targets=targets,
            ignores=ignores,
            suffixes=source_suffixes,
            on_file=_on_file,
        )
        python_files: frozenset[Path] = frozenset(
            path
            for path in source_files
            if path.suffix.lower() in Constants.python_suffixes
        )
        release_activities(items=python_files, stable=False)
        return _RunScope(
            python_files=python_files,
            python_args=cls._relative_args(cwd=cwd, files=python_files),
            eslint_args=cls._relative_args(
                cwd=cwd,
                files=frozenset(
                    path
                    for path in source_files
                    if path.suffix.lower() in Constants.eslint_suffixes
                ),
            ),
            stylelint_args=cls._relative_args(
                cwd=cwd,
                files=frozenset(
                    path
                    for path in source_files
                    if path.suffix.lower() in Constants.stylelint_suffixes
                ),
            ),
            htmlhint_args=cls._relative_args(
                cwd=cwd,
                files=frozenset(
                    path
                    for path in source_files
                    if path.suffix.lower() in Constants.htmlhint_suffixes
                ),
            ),
            clean_files=(
                SourceCleaner.collect(
                    cwd=cwd,
                    targets=targets,
                    excludes=ignores,
                    on_file=_on_file,
                )
                if config.clean and config.fix and not config.simple
                else []
            ),
        )

    @classmethod
    def _tool_phases(
        cls: type[Self],
        inputs: _ToolPhasesInput,
    ) -> tuple[dict[str, JsonValue], int]:
        """Run the mutating stages inside the temporary-config window.

        Args:
            inputs: Stage inputs: file scope, stage toggles, resolved
                toolchain commands, and the shared progress tracker.

        Returns:
            The report payload without ``summary``/``findings`` and the
            guarded-inference exit status.

        Raises:
            RuntimeError: If no supported files matched the targets.

        """
        cwd: Path = inputs.cwd
        targets: Sequence[str] = inputs.targets
        ignores: Sequence[str] = inputs.ignores
        config: LintExactusConfig = inputs.config
        scope: _RunScope = inputs.scope
        commands: ToolCommands = inputs.commands
        status_writer: Writer = inputs.writer
        progress: LintProgress = inputs.progress
        python_files: frozenset[Path] = scope.python_files
        python_args: list[str] = scope.python_args
        eslint_args: list[str] = scope.eslint_args
        stylelint_args: list[str] = scope.stylelint_args
        htmlhint_args: list[str] = scope.htmlhint_args
        clean_files: list[Path] = scope.clean_files
        if config.clean and config.fix and not config.simple:
            trace(step=f"clean: {len(clean_files)} source files", depth=2)
            _ = run_source_activity(
                mode="write",
                identity="lints:clean",
                action=lambda: SourceCleaner.run(
                    files=clean_files,
                    cwd=cwd,
                    writer=status_writer,
                    commands=commands,
                ),
            )
        tools: dict[str, JsonValue] = {}
        if not config.simple:
            progress.stage(name="conventions")
            trace(step="stage: conventions", depth=1)
            tools = run_source_activity(
                mode="write",
                identity="lints:convention-fixes",
                enabled=config.fix,
                action=lambda: cls._custom_tools(
                    inputs=CustomToolsInput(
                        cwd=cwd,
                        python_files=python_files,
                        eslint_args=eslint_args,
                        stylelint_args=stylelint_args,
                        htmlhint_args=htmlhint_args,
                        bare_import_exceptions=inputs.bare_import_exceptions,
                        targets=targets,
                        ignores=ignores,
                        css_context_words=inputs.css_context_words,
                        shebang=config.shebang,
                        progress=progress,
                        fix=config.fix,
                        ruff_command=commands.get("ruff"),
                        delimiters=config.delimiters,
                        notation=config.notation,
                    ),
                ),
            )
        report: dict[str, JsonValue] = {
            "version": Constants.report_version,
            "tools": tools,
            "group_final": inputs.group_final_report,
            "organize": inputs.organize_report,
        }
        repair: LongLineRepair | None = cls._long_line_repair(
            config=config,
            commands=commands,
        )
        trace(
            step=(
                "all lints: long-line repair — "
                f"{'enabled' if repair is not None else 'disabled'}"
            ),
            depth=2,
        )
        trace(step="stage: all lints", depth=1)
        all_lints_report, all_lints_results = run_source_activity(
            mode="write",
            identity="lints:external-fixes",
            enabled=config.fix,
            action=lambda: cls._all_lints_stage(
                inputs=AllLintsStageInput(
                    cwd=cwd,
                    targets=targets,
                    ignores=ignores,
                    commands=commands,
                    tool_args=inputs.tool_args,
                    config=config,
                    tools=tools,
                    progress=progress,
                    repair=repair,
                ),
            ),
        )
        cls._report_long_lines(repair=repair, writer=status_writer)
        if config.long_lines and not config.simple:
            tools["custom_python_long_lines"] = cls._long_lines_report(
                cwd=cwd,
                repair=repair,
                tools=tools,
                file_count=len(python_files),
            )
        report["all_lints"] = cast(typ="JsonValue", val=all_lints_report)
        baselines: tuple[frozenset[IssueKey], frozenset[IssueKey]] | None = (
            issue_baselines(results=all_lints_results)
            if python_args and not config.simple
            else None
        )
        if baselines is not None:
            trace(
                step=(
                    f"infer: baselines — {len(baselines[0])} ruff, "
                    f"{len(baselines[1])} basedpyright issues"
                ),
                depth=2,
            )
        if not any((python_args, eslint_args, stylelint_args, htmlhint_args)):
            trace(step="lints: no supported files matched targets", depth=1)
            msg: str = "No supported files matched the requested targets."
            raise RuntimeError(msg)
        status: int = 0
        if not config.simple:
            inference: bool = config.infer and config.fix
            progress.stage(name="infer" if inference else "pyrefly")
            trace(
                step="stage: infer" if inference else "stage: pyrefly",
                depth=1,
            )
            if baselines is not None:
                status = run_source_activity(
                    mode="write",
                    identity="lints:inference",
                    enabled=inference,
                    action=lambda: cls._infer_stage(
                        inputs=LintExactusInput(
                            cwd=cwd,
                            targets=targets,
                            ignores=ignores,
                            python_args=python_args,
                            python_files=python_files,
                            bare_import_exceptions=(
                                inputs.bare_import_exceptions
                            ),
                            baselines=baselines,
                            tools=tools,
                            commands=commands,
                            arguments=inputs.tool_args,
                            writer=status_writer,
                            progress=progress,
                        ),
                        infer=inference,
                    ),
                )
        return report, status

    @classmethod
    def _finish_tools(cls: type[Self], inputs: FinishToolsInput) -> None:
        """Complete the built-in checks and record external linter versions.

        Args:
            inputs: Report-finalization inputs; ``inputs.tools`` is
                updated in place.

        """
        if not inputs.simple:
            trace(step="report: compliance scan", depth=2)
            inputs.tools["custom_compliance"] = cls._compliance_report(
                cwd=inputs.cwd,
                targets=inputs.targets,
                ignores=inputs.ignores,
                python_files=inputs.python_files,
            )
        cls._record_versions(tools=inputs.tools, commands=inputs.commands)
        trace(step="report: tool versions recorded", depth=2)
        release_activities(items=inputs.python_files)
        trace(step="report: file activities released", depth=2)

    @classmethod
    def _record_versions(
        cls: type[Self],
        tools: dict[str, JsonValue],
        commands: Mapping[str, tuple[str, ...] | None],
    ) -> None:
        """Add the probed ``version`` to every external linter that ran.

        Args:
            tools: Per-tool report entries, updated in place.
            commands: Resolved executable prefixes keyed by command name.

        """
        probed: dict[str, str | None] = {}
        for name, entry in tools.items():
            key: str | None = Constants.version_commands.get(name)
            prefix: tuple[str, ...] | None = (
                commands.get(key) if key is not None else None
            )
            if (
                key is None
                or prefix is None
                or not isinstance(entry, dict)
                or entry.get("skipped")
            ):
                continue
            if key not in probed:
                probed[key] = cls._version(command=prefix)
            entry["version"] = probed[key]

    @classmethod
    @contextmanager
    def _temporary_configs(
        cls: type[Self],
        *,
        cwd: Path,
        python_args: Sequence[str],
        eslint_args: Sequence[str],
        stylelint_args: Sequence[str],
    ) -> Generator[None]:
        """Materialize missing tool configuration files inside `cwd`.

        Projects exactused by this tool may carry no linter configuration
        at all. Bundled templates are copied in — or ``pyproject.toml``
        is generated — only when the project lacks every known config
        filename for that tool, so the external linters always run under
        the exactus's strict defaults without touching existing project
        configuration. Every file created here is removed when the
        context exits.

        Args:
            cwd: Project working directory being exactused.
            python_args: Relative Python file arguments being linted.
            eslint_args: Relative JavaScript file arguments.
            stylelint_args: Relative CSS file arguments.

        Yields:
            Nothing; the context brackets the tool-invocation stages.

        """
        templates: Traversable = template_resource(name="")
        copies: tuple[tuple[Traversable, Sequence[str], str, bool], ...] = (
            (
                templates.joinpath("eslint.config.mjs"),
                Constants.eslint_config_names,
                "eslint.config.mjs",
                bool(eslint_args),
            ),
            (
                templates.joinpath("jsconfig.json"),
                Constants.jsconfig_names,
                "jsconfig.json",
                bool(eslint_args),
            ),
            (
                templates.joinpath("stylelint.config.mjs"),
                Constants.stylelint_config_names,
                "stylelint.config.mjs",
                bool(stylelint_args),
            ),
        )
        written: list[Path] = []
        for source, names, filename, needed in copies:
            if not needed or not source.is_file():
                continue
            if any((cwd / name).exists() for name in names):
                trace(
                    step=f"clean: project config present — skip {filename}",
                    depth=3,
                )
                continue
            destination: Path = cwd / filename
            _ = destination.write_bytes(data=source.read_bytes())
            written.append(destination)
            trace(step=f"clean: materialized {filename}", depth=3)
        if python_args and not (cwd / "pyproject.toml").exists():
            destination = cwd / "pyproject.toml"
            _ = destination.write_text(
                data=cls._generated_pyproject(python_args=python_args),
                encoding="utf-8",
            )
            written.append(destination)
            trace(step="clean: materialized pyproject.toml", depth=3)
        try:
            yield
        finally:
            for path in written:
                with suppress(FileNotFoundError):
                    path.unlink()
                    trace(
                        step=f"clean: removed temporary {path.name}",
                        depth=3,
                    )

    @classmethod
    def _sort_key(
        cls: type[Self],
        finding: JsonValue,
    ) -> tuple[str, int, int, str, str]:
        """Return the canonical ordering key for one finding.

        Args:
            finding: Normalized finding value.

        Returns:
            ``(file, line, column, rule, tool)`` ordering key.

        """
        if isinstance(finding, dict):
            return (
                str(object=finding.get("file", "")),
                cls._json_int(value=finding.get("line")),
                cls._json_int(value=finding.get("column")),
                str(object=finding.get("rule", "")),
                str(object=finding.get("tool", "")),
            )
        return ("", 0, 0, "", "")

    @classmethod
    def _all_findings(
        cls: type[Self],
        tools: Mapping[str, JsonValue],
    ) -> list[JsonValue]:
        """Collect deduplicated normalized findings from every tool.

        Findings are considered duplicates when they share rule code,
        file, and line/column span; the first occurrence in tool order
        wins. Results are ordered by file, position, rule, and tool.

        Args:
            tools: Per-tool report mapping.

        Returns:
            Concatenated findings without duplicates, in file order.

        """
        all_findings: list[JsonValue] = []
        seen: set[tuple[str, str, str, str, str, str]] = set()
        for tool_name in Constants.tool_names:
            entry: JsonValue | None = tools.get(tool_name)
            if not isinstance(entry, dict):
                continue
            findings_value: JsonValue = entry.get("findings", [])
            if not isinstance(findings_value, list):
                continue
            for finding in findings_value:
                if not isinstance(finding, dict):
                    all_findings.append(finding)
                    continue
                key: tuple[str, str, str, str, str, str] = (
                    str(object=finding.get("rule", "")),
                    str(object=finding.get("file", "")),
                    str(object=finding.get("line", "")),
                    str(object=finding.get("column", "")),
                    str(object=finding.get("end_line", "")),
                    str(object=finding.get("end_column", "")),
                )
                if key in seen:
                    continue
                seen.add(key)
                all_findings.append(finding)
        all_findings.sort(key=cls._sort_key)
        return all_findings

    @classmethod
    def _files_with_issues(
        cls: type[Self],
        tools: Mapping[str, JsonValue],
    ) -> list[JsonValue]:
        """Count findings per file and tool, ordered by file.

        Args:
            tools: Per-tool report mapping.

        Returns:
            Per-file rows with a count for every tool.

        """
        per_file: dict[str, dict[str, int]] = {}
        for tool_name in Constants.tool_names:
            entry: JsonValue | None = tools.get(tool_name)
            if not isinstance(entry, dict):
                continue
            tool_findings: JsonValue = entry.get("findings", [])
            if not isinstance(tool_findings, list):
                continue
            for finding in tool_findings:
                if not isinstance(finding, dict):
                    continue
                file_name: str = str(object=finding.get("file", ""))
                if file_name:
                    row: dict[str, int] = per_file.setdefault(
                        file_name,
                        dict.fromkeys(Constants.tool_names, 0),
                    )
                    row[tool_name] += 1
        return [
            cls._payload(entries={"file": file_name, **counts})
            for file_name, counts in sorted(per_file.items())
        ]

    @classmethod
    def _run_check(
        cls: type[Self],
        tool: str,
        command: tuple[str, ...],
        cwd: Path,
    ) -> tuple[dict[str, JsonValue], JsonValue]:
        """Run a JSON-emitting analyzer and normalize its report entry.

        Args:
            tool: Producing tool name.
            command: Analyzer command line.
            cwd: Project working directory.

        Returns:
            Normalized report entry and the parsed native payload.

        """
        result: CommandResult = cls.run_command(command=command, cwd=cwd)
        payload: JsonValue = cls.parse_json_output(result=result)
        entry: dict[str, JsonValue] = cls._result_json(
            tool=tool,
            result=result,
            payload=payload,
        )
        return entry, payload

    @classmethod
    def _ruff_report(
        cls: type[Self],
        cwd: Path,
        python_args: Sequence[str],
        commands: ToolCommands,
        arguments: ToolArguments,
    ) -> tuple[dict[str, JsonValue], JsonValue]:
        """Run the Ruff report pass and normalize its entry.

        Args:
            cwd: Project working directory.
            python_args: Relative Python file arguments.
            commands: Resolved executable prefixes keyed by tool name.
            arguments: Extra CLI arguments appended per tool.

        Returns:
            Normalized report entry and the parsed Ruff payload.

        """
        if (prefix := commands.get("ruff")) is None:
            return (
                cls._skipped_entry(
                    tool="ruff",
                    reason="ruff is not installed.",
                ),
                [],
            )
        return cls._run_check(
            tool="ruff",
            command=(
                *prefix,
                "check",
                *Constants.ruff_policy(cwd=cwd),
                "--output-format=json",
                *python_args,
                *arguments.get("ruff", ()),
            ),
            cwd=cwd,
        )

    @classmethod
    def _basedpyright_report(
        cls: type[Self],
        cwd: Path,
        python_args: Sequence[str],
        commands: ToolCommands,
        arguments: ToolArguments,
    ) -> tuple[dict[str, JsonValue], JsonValue]:
        """Run BasedPyright and normalize its report entry.

        Args:
            cwd: Project working directory.
            python_args: Relative Python file arguments.
            commands: Resolved executable prefixes keyed by tool name.
            arguments: Extra CLI arguments appended per tool.

        Returns:
            Normalized report entry and the parsed BasedPyright payload.

        """
        if (prefix := commands.get("basedpyright")) is None:
            return (
                cls._skipped_entry(
                    tool="basedpyright",
                    reason="basedpyright is not installed.",
                ),
                {},
            )
        return cls._run_check(
            tool="basedpyright",
            command=(
                *prefix,
                "--outputjson",
                *cls._interpreter_flag(tool="basedpyright"),
                *python_args,
                *arguments.get("basedpyright", ()),
            ),
            cwd=cwd,
        )

    @classmethod
    def _ruff_docs_report(
        cls: type[Self],
        cwd: Path,
        python_args: Sequence[str],
        commands: ToolCommands,
        arguments: ToolArguments,
    ) -> dict[str, JsonValue]:
        """Run the docstring Ruff pass and normalize its report entry.

        Args:
            cwd: Project working directory.
            python_args: Relative Python file arguments.
            commands: Resolved executable prefixes keyed by tool name.
            arguments: Extra CLI arguments appended per tool.

        Returns:
            Normalized report entry.

        """
        if (prefix := commands.get("ruff")) is None:
            return cls._skipped_entry(
                tool="ruff_docs",
                reason="ruff is not installed.",
            )
        entry, _ = cls._run_check(
            tool="ruff_docs",
            command=(
                *prefix,
                "check",
                "--preview",
                "--select",
                "D,DOC",
                *Constants.ruff_extend_ignores,
                *(
                    ()
                    if "convention" in Constants.ruff_config_text(cwd=cwd)
                    else ("--config", "lint.pydocstyle.convention='google'")
                ),
                "--output-format=json",
                *python_args,
                *arguments.get("ruff", ()),
            ),
            cwd=cwd,
        )
        return entry

    @classmethod
    def _pyrefly_report(
        cls: type[Self],
        cwd: Path,
        python_args: Sequence[str],
        commands: ToolCommands,
        arguments: ToolArguments,
    ) -> dict[str, JsonValue]:
        """Run Pyrefly on the final sources and normalize its entry.

        Args:
            cwd: Project working directory.
            python_args: Relative Python file arguments.
            commands: Resolved executable prefixes keyed by tool name.
            arguments: Extra CLI arguments appended per tool.

        Returns:
            Normalized report entry.

        """
        if (prefix := commands.get("pyrefly")) is None:
            return cls._skipped_entry(
                tool="pyrefly",
                reason="pyrefly is not installed.",
            )
        entry, _ = cls._run_check(
            tool="pyrefly",
            command=(
                *prefix,
                "check",
                *cls._interpreter_flag(tool="pyrefly"),
                "--min-severity",
                "warn",
                "--output-format=json",
                *python_args,
                *arguments.get("pyrefly", ()),
            ),
            cwd=cwd,
        )
        return entry

    @classmethod
    def _custom_tools(
        cls: type[Self],
        inputs: CustomToolsInput,
    ) -> dict[str, JsonValue]:
        """Run built-in checks that ``all_lints`` does not provide.

        Args:
            inputs: Convention-scan inputs.

        Returns:
            Tool entries for the built-in shebang and convention
            scanners. Compliance runs after inference.

        """
        scopes: _ConventionScopes = cls._convention_scopes(inputs=inputs)
        trace(
            step=(
                f"conventions: scopes — {len(scopes.python_files)} "
                f"python, {len(scopes.delimiter_files)} delimiter, "
                f"{len(scopes.notation_files)} notation, "
                f"{len(scopes.javascript_files)} javascript, "
                f"{len(scopes.css_files)} css, "
                f"{len(scopes.html_files)} html"
            ),
            depth=2,
        )
        slicer: _StageSlicer = _StageSlicer(
            progress=inputs.progress,
            step="conventions",
            weights=(
                len(scopes.python_files),
                2 * len(scopes.python_files),
                len(scopes.delimiter_files) if inputs.delimiters else 0,
                len(scopes.notation_files) if inputs.notation else 0,
                2 * len(scopes.javascript_files),
                len(scopes.css_files) + 1,
                len(scopes.html_files),
            ),
        )
        slicer.mark(weight=0, detail="shebang")
        shebang: dict[str, JsonValue] = cls._shebang_report(
            inputs=inputs,
            progress_span=slicer.span(weight=len(scopes.python_files)),
        )
        entries: dict[str, JsonValue] = {"custom_shebang": shebang}
        trace(
            step=(
                f"conventions: shebang — {shebang.get('count', 0)} findings"
            ),
            depth=2,
        )
        slicer.mark(weight=0, detail="python")
        started: float = perf_counter()
        custom_python_findings: list[JsonValue] = sorted(
            cls._python_conventions(
                files=scopes.python_files,
                bare_import_exceptions=inputs.bare_import_exceptions,
                fix=inputs.fix,
                transform_runtime=(
                    _TransformRuntime(
                        cwd=inputs.cwd,
                        ruff_command=inputs.ruff_command,
                    )
                    if inputs.ruff_command is not None
                    else None
                ),
                on_file=slicer.ticks(
                    weight=2 * len(scopes.python_files),
                    label="python",
                ),
            ),
            key=cls._sort_key,
        )
        entries["custom_python"] = cls._custom_entry(
            tool="custom_python",
            findings=custom_python_findings,
            started=started,
        )
        trace(
            step=(
                f"conventions: python — {len(custom_python_findings)} findings"
            ),
            depth=2,
        )
        if inputs.delimiters:
            slicer.mark(weight=0, detail="delimiters")
            delimiters: dict[str, JsonValue] = cls._delimiter_report(
                inputs=inputs,
                files=scopes.delimiter_files,
                progress_span=slicer.span(weight=len(scopes.delimiter_files)),
            )
            entries["custom_javascript_delimiters"] = delimiters
            trace(
                step=(
                    "conventions: javascript delimiters — "
                    f"{delimiters.get('count', 0)} findings"
                ),
                depth=2,
            )
        if inputs.notation:
            slicer.mark(weight=0, detail="notation")
            notation: dict[str, JsonValue] = cls._notation_report(
                inputs=inputs,
                files=scopes.notation_files,
                progress_span=slicer.span(weight=len(scopes.notation_files)),
            )
            entries["custom_javascript_notation"] = notation
            trace(
                step=(
                    "conventions: javascript notation — "
                    f"{notation.get('count', 0)} findings"
                ),
                depth=2,
            )
        slicer.mark(weight=0, detail="javascript")
        started = perf_counter()
        javascript_report: Callable[[Path], None] = slicer.ticks(
            weight=2 * len(scopes.javascript_files),
            label="javascript",
        )
        custom_javascript_findings: list[JsonValue] = sorted(
            [
                *cls._javascript_conventions(
                    files=scopes.javascript_files,
                    on_file=javascript_report,
                ),
                *cls._javascript_inline_styles(
                    files=scopes.javascript_files,
                    on_file=javascript_report,
                ),
            ],
            key=cls._sort_key,
        )
        entries["custom_javascript"] = cls._custom_entry(
            tool="custom_javascript",
            findings=custom_javascript_findings,
            started=started,
        )
        trace(
            step=(
                f"conventions: javascript — "
                f"{len(custom_javascript_findings)} findings"
            ),
            depth=2,
        )
        slicer.mark(weight=0, detail="css")
        started = perf_counter()
        custom_css_findings: list[JsonValue] = sorted(
            [
                *cls._css_conventions(
                    files=scopes.css_files,
                    on_file=slicer.ticks(
                        weight=len(scopes.css_files),
                        label="css",
                    ),
                ),
                *cls._css_token_findings(
                    root=inputs.cwd,
                    files=scopes.css_files,
                    context_words=inputs.css_context_words,
                ),
            ],
            key=cls._sort_key,
        )
        slicer.mark(weight=1, detail="css tokens")
        entries["custom_css"] = cls._custom_entry(
            tool="custom_css",
            findings=custom_css_findings,
            started=started,
        )
        trace(
            step=(f"conventions: css — {len(custom_css_findings)} findings"),
            depth=2,
        )
        slicer.mark(weight=0, detail="html")
        started = perf_counter()
        custom_html_findings: list[JsonValue] = sorted(
            cls._html_conventions(
                files=scopes.html_files,
                on_file=slicer.ticks(
                    weight=len(scopes.html_files),
                    label="html",
                ),
            ),
            key=cls._sort_key,
        )
        entries["custom_html"] = cls._custom_entry(
            tool="custom_html",
            findings=custom_html_findings,
            started=started,
        )
        trace(
            step=(f"conventions: html — {len(custom_html_findings)} findings"),
            depth=2,
        )
        return entries

    @classmethod
    def _python_reports(
        cls: type[Self],
        inputs: PythonReportInput,
    ) -> tuple[frozenset[IssueKey], frozenset[IssueKey]]:
        """Run the Python analyzers and return baseline issue keys.

        Args:
            inputs: Analyzer inputs; ``inputs.tools`` is updated in
                place with the generated report entries.

        Returns:
            Baseline Ruff and BasedPyright issue keys.

        """
        tools: dict[str, JsonValue] = inputs.tools
        cwd: Path = inputs.cwd
        python_args: Sequence[str] = cls._existing_args(
            cwd=cwd,
            args=inputs.python_args,
        )
        commands: ToolCommands = inputs.commands
        arguments: ToolArguments = inputs.arguments
        fix: bool = inputs.fix
        ruff: tuple[str, ...] | None = commands.get("ruff")
        if fix and ruff is not None:
            inputs.progress.note(step="python", detail="ruff fix")
            for _ in range(2):
                _ = cls.run_command(
                    command=(*ruff, "format", *python_args),
                    cwd=cwd,
                )
                _ = cls.run_command(
                    command=(
                        *ruff,
                        "check",
                        *Constants.ruff_policy(cwd=cwd),
                        "--fix",
                        *python_args,
                    ),
                    cwd=cwd,
                )
            _ = cls.run_command(
                command=(*ruff, "format", *python_args),
                cwd=cwd,
            )
        inputs.progress.note(step="python", detail="ruff")
        tools["ruff"], ruff_payload = cls._ruff_report(
            cwd=cwd,
            python_args=python_args,
            commands=commands,
            arguments=arguments,
        )
        inputs.progress.note(step="python", detail="ruff docs")
        tools["ruff_docs"] = cls._ruff_docs_report(
            cwd=cwd,
            python_args=python_args,
            commands=commands,
            arguments=arguments,
        )
        inputs.progress.note(step="python", detail="basedpyright")
        tools["basedpyright"], basedpyright_payload = cls._basedpyright_report(
            cwd=cwd,
            python_args=python_args,
            commands=commands,
            arguments=arguments,
        )
        return (
            cls._ruff_keys(payload=ruff_payload),
            cls._basedpyright_keys(payload=basedpyright_payload),
        )

    @classmethod
    def _frontend_reports(
        cls: type[Self],
        inputs: FrontendReportInput,
    ) -> None:
        """Run the frontend analyzers and merge their report entries.

        Args:
            inputs: Analyzer inputs; ``inputs.tools`` is updated in
                place with the generated report entries.

        """
        tools: dict[str, JsonValue] = inputs.tools
        cwd: Path = inputs.cwd
        eslint_args: Sequence[str] = cls._existing_args(
            cwd=cwd,
            args=inputs.eslint_args,
        )
        stylelint_args: Sequence[str] = cls._existing_args(
            cwd=cwd,
            args=inputs.stylelint_args,
        )
        htmlhint_args: Sequence[str] = cls._existing_args(
            cwd=cwd,
            args=inputs.htmlhint_args,
        )
        commands: ToolCommands = inputs.commands
        arguments: ToolArguments = inputs.arguments
        inputs.progress.note(step="frontend", detail="eslint")
        if eslint_args:
            if (eslint_prefix := commands.get("eslint")) is None:
                tools["eslint"] = cls._skipped_entry(
                    tool="eslint",
                    reason="eslint is not installed.",
                )
            else:
                eslint: CommandResult = cls.run_command(
                    command=(
                        *eslint_prefix,
                        *eslint_args,
                        *(
                            ()
                            if any(
                                (cwd / name).exists()
                                for name in Constants.eslint_config_names
                            )
                            else (
                                ("--config", str(object=eslint_template))
                                if (
                                    eslint_template := Path(
                                        str(
                                            object=template_resource(
                                                name="eslint.config.mjs",
                                            ),
                                        ),
                                    )
                                ).is_file()
                                else ()
                            )
                        ),
                        "--format",
                        "json",
                        *arguments.get("eslint", ()),
                    ),
                    cwd=cwd,
                )
                tools["eslint"] = cls._result_json(
                    tool="eslint",
                    result=eslint,
                    payload=cls.parse_json_output(result=eslint),
                )
        inputs.progress.note(step="frontend", detail="stylelint")
        if stylelint_args:
            if (stylelint_prefix := commands.get("stylelint")) is None:
                tools["stylelint"] = cls._skipped_entry(
                    tool="stylelint",
                    reason="stylelint is not installed.",
                )
            else:
                stylelint: CommandResult = cls.run_command(
                    command=(
                        *stylelint_prefix,
                        *stylelint_args,
                        *(
                            ()
                            if any(
                                (cwd / name).exists()
                                for name in Constants.stylelint_config_names
                            )
                            else (
                                "--config",
                                dumps(
                                    obj=Constants.stylelint_default_config,
                                    separators=(",", ":"),
                                    sort_keys=True,
                                ),
                            )
                        ),
                        "--formatter",
                        "json",
                        *arguments.get("stylelint", ()),
                    ),
                    cwd=cwd,
                )
                if not stylelint.stdout.strip() and stylelint.stderr.strip():
                    # Stylelint 17 writes the formatted report to stderr.
                    stylelint = replace(
                        stylelint,
                        stdout=stylelint.stderr,
                        stderr="",
                    )
                tools["stylelint"] = cls._result_json(
                    tool="stylelint",
                    result=stylelint,
                    payload=cls.parse_json_output(result=stylelint),
                )
        inputs.progress.note(step="frontend", detail="htmlhint")
        if htmlhint_args:
            if (htmlhint_prefix := commands.get("htmlhint")) is None:
                tools["htmlhint"] = cls._skipped_entry(
                    tool="htmlhint",
                    reason="htmlhint is not installed.",
                )
            else:
                htmlhint: CommandResult = cls.run_command(
                    command=(
                        *htmlhint_prefix,
                        "--format",
                        "json",
                        *(
                            ()
                            if any(
                                (cwd / name).exists()
                                for name in (".htmlhintrc", ".htmlhintrc.json")
                            )
                            else (
                                "--rules",
                                (
                                    "tag-pair,attr-no-duplication,tagname-lowe"
                                    "rcase,attr-lowercase,id-unique"
                                ),
                            )
                        ),
                        *htmlhint_args,
                        *arguments.get("htmlhint", ()),
                    ),
                    cwd=cwd,
                )
                tools["htmlhint"] = cls._result_json(
                    tool="htmlhint",
                    result=htmlhint,
                    payload=cls.parse_json_output(result=htmlhint),
                )

    @classmethod
    def _summary(
        cls: type[Self],
        inputs: SummaryInput,
    ) -> dict[str, JsonValue]:
        """Build the report summary section.

        Args:
            inputs: Summary construction inputs.

        Returns:
            JSON-serializable summary section.

        """
        executed_tools: list[str] = [
            tool_name
            for tool_name in Constants.tool_names
            if isinstance(inputs.tools.get(tool_name), dict)
        ]
        files_with_findings: set[str] = {
            str(object=finding.get("file", ""))
            for finding in inputs.all_findings
            if isinstance(finding, dict) and finding.get("file")
        }
        rules_with_findings: set[str] = {
            str(object=finding.get("rule", ""))
            for finding in inputs.all_findings
            if isinstance(finding, dict) and finding.get("rule")
        }
        return cls._payload(
            entries={
                "timing": cls._payload(
                    entries={
                        "date_time": inputs.started_at.strftime(
                            format="%d/%m/%Y %H:%M:%S",
                        ),
                        "finished_date_time": inputs.finished_at.strftime(
                            format="%d/%m/%Y %H:%M:%S",
                        ),
                        "timezone": str(object=inputs.started_at.tzinfo),
                        "duration_seconds": round(
                            number=inputs.duration_seconds,
                            ndigits=6,
                        ),
                        "duration_human": (
                            f"{int(inputs.duration_seconds // 3600):02d}:"
                            f"{int(inputs.duration_seconds % 3600 // 60):02d}:"
                            f"{inputs.duration_seconds % 60:09.6f}"
                        ),
                    },
                ),
                "host": cls._payload(
                    entries={
                        "hostname": node(),
                        "operating_system": system(),
                        "platform": platform(),
                        "architecture": machine(),
                        "python_version": python_version(),
                    },
                ),
                "analysis": cls._payload(
                    entries={
                        "working_directory": str(object=inputs.cwd),
                        "output_file": (
                            str(object=inputs.report_path)
                            if inputs.report_path is not None
                            else "stdout"
                        ),
                        "targets": list(inputs.targets),
                        "ignore_patterns": list(inputs.ignores),
                        "files": cls._payload(
                            entries={
                                "python": len(inputs.python_args),
                                "javascript_jsx": len(inputs.eslint_args),
                                "css": len(inputs.stylelint_args),
                                "html": len(inputs.htmlhint_args),
                                "unique_analyzed": len(
                                    {
                                        *inputs.python_args,
                                        *inputs.eslint_args,
                                        *inputs.stylelint_args,
                                        *inputs.htmlhint_args,
                                    },
                                ),
                                "with_findings": len(files_with_findings),
                            },
                        ),
                        "files_with_issues": cls._files_with_issues(
                            tools=inputs.tools,
                        ),
                        "findings": cls._payload(
                            entries={
                                "total": len(inputs.all_findings),
                                "errors": sum(
                                    1
                                    for finding in inputs.all_findings
                                    if isinstance(finding, dict)
                                    and finding.get("severity") == "error"
                                ),
                                "warnings": sum(
                                    1
                                    for finding in inputs.all_findings
                                    if isinstance(finding, dict)
                                    and finding.get("severity") == "warning"
                                ),
                                "information": sum(
                                    1
                                    for finding in inputs.all_findings
                                    if isinstance(finding, dict)
                                    and finding.get("severity")
                                    == "information"
                                ),
                                "unique_rules": len(rules_with_findings),
                                "affected_files": len(files_with_findings),
                            },
                        ),
                    },
                ),
                "tools": cls._payload(
                    entries={
                        "configured": len(Constants.tool_names),
                        "executed": len(executed_tools),
                        "names": executed_tools,
                    },
                ),
                "clean": not inputs.all_findings,
            },
        )

    @classmethod
    def _infer_stage(
        cls: type[Self],
        inputs: LintExactusInput,
        *,
        infer: bool,
    ) -> int:
        """Run guarded inference and the Pyrefly report.

        Args:
            inputs: Guarded-inference inputs; ``inputs.tools`` is
                updated in place.
            infer: Whether guarded ``pyrefly infer`` is enabled.

        Returns:
            Exit status from guarded inference, zero otherwise.

        """
        status: int = 0
        if infer and all(
            inputs.commands.get(tool) is not None
            for tool in ("ruff", "basedpyright", "pyrefly")
        ):
            status, rewritten = cls._infer_guard(inputs=inputs)
            if rewritten:
                started: float = perf_counter()
                refreshed: list[JsonValue] = sorted(
                    cls._python_conventions(
                        files=sorted(inputs.python_files),
                        bare_import_exceptions=inputs.bare_import_exceptions,
                    ),
                    key=cls._sort_key,
                )
                inputs.tools["custom_python"] = cls._custom_entry(
                    tool="custom_python",
                    findings=refreshed,
                    started=started,
                )
                trace(
                    step=(
                        f"infer: refreshed python conventions — "
                        f"{len(refreshed)} findings"
                    ),
                    depth=2,
                )
        elif infer:
            trace(step="infer: skipped — required tool missing", depth=2)
            sprint(
                "Skipping pyrefly infer: ruff, basedpyright, or "
                "pyrefly is not installed.",
                file=inputs.writer,
            )
        inputs.progress.note(
            step="infer" if infer else "pyrefly",
            detail="check",
        )
        trace(
            step="infer: pyrefly report" if infer else "pyrefly: report",
            depth=2,
        )
        inputs.tools["pyrefly"] = cls._pyrefly_report(
            cwd=inputs.cwd,
            python_args=inputs.python_args,
            commands=inputs.commands,
            arguments=inputs.arguments,
        )
        return status

    @classmethod
    def _infer_guard(
        cls: type[Self],
        inputs: LintExactusInput,
    ) -> tuple[int, bool]:
        """Run ``pyrefly infer`` and roll back on regressions.

        Post-inference Ruff and BasedPyright passes only run when
        inference rewrote sources; when retained, their findings become
        the reported ones. ``inputs.tools`` is updated in place.

        Args:
            inputs: Guarded-inference inputs.

        Returns:
            Exit status — zero retained, one rolled back — and whether
            retained inference rewrote sources.

        Raises:
            RuntimeError: If a required JSON report cannot be interpreted.
            TypeError: If a required JSON report has an unexpected shape.

        """
        baseline_ruff, baseline_basedpyright = inputs.baselines
        python_args: Sequence[str] = cls._existing_args(
            cwd=inputs.cwd,
            args=inputs.python_args,
        )
        pyrefly: tuple[str, ...] | None = inputs.commands.get("pyrefly")
        if pyrefly is None:
            sprint(
                "Skipping pyrefly infer: pyrefly is not installed.",
                file=inputs.writer,
            )
            return 0, False
        with TemporaryDirectory(prefix="pyrefly-infer-backup-") as temporary:
            trace(step="infer: snapshot sources", depth=2)
            snapshot: Snapshot = cls._snapshot(
                cwd=inputs.cwd,
                targets=inputs.targets,
                backup_root=Path(temporary),
                ignores=inputs.ignores,
            )
            inputs.progress.note(step="infer", detail="pyrefly infer")
            infer: CommandResult = cls.run_command(
                command=(
                    *pyrefly,
                    "infer",
                    *cls._interpreter_flag(tool="pyrefly"),
                    *python_args,
                    *inputs.arguments.get("pyrefly", ()),
                ),
                cwd=inputs.cwd,
            )
            trace(
                step=f"infer: pyrefly infer — exit {infer.returncode}",
                depth=2,
            )
            changed: bool = cls._sources_changed(
                snapshot=snapshot,
                cwd=inputs.cwd,
                targets=inputs.targets,
                ignores=inputs.ignores,
            )
            trace(
                step=(
                    f"infer: sources {'changed' if changed else 'unchanged'}"
                ),
                depth=2,
            )
            if infer.returncode != 0:
                trace(
                    step=(
                        "infer: rolled back — infer exit code "
                        f"{infer.returncode}"
                    ),
                    depth=2,
                )
                cls._restore(
                    snapshot=snapshot,
                    cwd=inputs.cwd,
                    targets=inputs.targets,
                    ignores=inputs.ignores,
                )
                sprint(
                    "pyrefly infer rolled back: "
                    f"infer exit code {infer.returncode}.",
                    file=inputs.writer,
                )
                return 1, False
            if not changed:
                sprint(
                    "pyrefly infer left sources unchanged.",
                    file=inputs.writer,
                )
                return 0, False
            trace(step="infer: recheck ruff and basedpyright", depth=2)
            try:
                inputs.progress.note(step="infer", detail="recheck")
                ruff_entry, ruff_payload = cls._ruff_report(
                    cwd=inputs.cwd,
                    python_args=python_args,
                    commands=inputs.commands,
                    arguments=inputs.arguments,
                )
                basedpyright_entry, basedpyright_payload = (
                    cls._basedpyright_report(
                        cwd=inputs.cwd,
                        python_args=python_args,
                        commands=inputs.commands,
                        arguments=inputs.arguments,
                    )
                )
                new_ruff: frozenset[IssueKey] = (
                    cls._ruff_keys(payload=ruff_payload) - baseline_ruff
                )
                new_basedpyright: frozenset[IssueKey] = (
                    cls._basedpyright_keys(payload=basedpyright_payload)
                    - baseline_basedpyright
                )
            except (RuntimeError, TypeError):
                cls._restore(
                    snapshot=snapshot,
                    cwd=inputs.cwd,
                    targets=inputs.targets,
                    ignores=inputs.ignores,
                )
                raise
            if new_ruff or new_basedpyright:
                trace(
                    step=(
                        f"infer: rolled back — {len(new_ruff)} new "
                        "ruff, "
                        f"{len(new_basedpyright)} new basedpyright "
                        "issues"
                    ),
                    depth=2,
                )
                cls._restore(
                    snapshot=snapshot,
                    cwd=inputs.cwd,
                    targets=inputs.targets,
                    ignores=inputs.ignores,
                )
                sprint(
                    "pyrefly infer rolled back: "
                    f"{len(new_ruff)} new Ruff issue(s), "
                    f"{len(new_basedpyright)} new BasedPyright issue(s).",
                    file=inputs.writer,
                )
                return 1, False
            inputs.tools["ruff"] = ruff_entry
            inputs.tools["ruff_docs"] = cls._ruff_docs_report(
                cwd=inputs.cwd,
                python_args=python_args,
                commands=inputs.commands,
                arguments=inputs.arguments,
            )
            inputs.tools["basedpyright"] = basedpyright_entry
            trace(
                step="infer: retained — no new ruff/basedpyright issues",
                depth=2,
            )
            sprint(
                "pyrefly infer retained: no new Ruff or BasedPyright issues.",
                file=inputs.writer,
            )
            return 0, True

    @staticmethod
    def _fix_string_transforms(
        *,
        file: Path,
        tree: Module,
        ruff_command: tuple[str, ...] | None,
        widths: dict[Path | None, int],
    ) -> TransformResult:
        """Apply source-preserving string transformations to a Python file.

        String dedent conversion, width-limited literal splitting and
        f-string call expansion reuse the caller's parsed tree. Effective
        Ruff line lengths are memoized per project configuration.

        Args:
            file: Python source file to rewrite in place.
            tree: Pre-parsed source tree matching the file.
            ruff_command: Resolved Ruff executable prefix, when available.
            widths: Effective line lengths keyed by project configuration.

        Returns:
            The transformation result; its tree describes the rewritten
            source and is reused for the findings pass.

        """
        key: Path | None = LongLinesAPI.find_pyproject(file_path=file)
        if key not in widths:
            widths[key] = LongLinesAPI.resolve_line_length(
                file_path=file,
                ruff_command=ruff_command or ("ruff",),
            )
        return transform_strings(
            file=file,
            tree=tree,
            write=True,
            options=TransformOptions(
                line_length=widths[key],
                ruff_executable=(
                    ruff_command[0]
                    if ruff_command is not None and len(ruff_command) == 1
                    else None
                ),
            ),
        )

    @staticmethod
    def _generic_binder_call(*, statement: Assign) -> bool:
        """Return whether an assignment binds a generic placeholder.

        ``TypeVar``-family constructors are declared by convention in
        uppercase at module scope; they are type-system placeholders,
        not mutable globals, so ``PY002`` does not apply.

        Args:
            statement: Module-level assignment statement.

        Returns:
            Whether the assigned value calls a generic binder.

        """
        value: expr = statement.value
        if not isinstance(value, Call):
            return False
        function: expr = value.func
        name: str = (
            function.id
            if isinstance(function, Name)
            else function.attr
            if isinstance(function, Attribute)
            else ""
        )
        return name in Constants.upper_global_exempt_calls

    @staticmethod
    def _install(command: Sequence[str], cwd: Path) -> None:
        """Install one missing tool dependency.

        Args:
            command: Installer command and arguments.
            cwd: Project working directory.

        Raises:
            RuntimeError: If installation fails.

        """
        completed: CompletedProcess[str] = run(
            args=list(command),
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode:
            msg: str = dedent(
                text=f"""\
    Installation failed: {" ".join(command)}
    stdout:
    {completed.stdout}
    stderr:
    {completed.stderr}""",
            )
            raise RuntimeError(msg)

    @staticmethod
    def _sudo_prefix() -> tuple[str, ...]:
        """Return the sudo prefix when the process is not already root.

        Returns:
            Command prefix needed for privileged tool installation.

        """
        return () if geteuid is not None and geteuid() == 0 else ("sudo",)

    @staticmethod
    def _refresh_path() -> None:
        """Prepend common Node.js install locations to PATH."""
        path_entries: list[str] = environ.get("PATH", default="").split(
            sep=pathsep,
        )
        extra_paths: tuple[str, ...] = (
            *Constants.node_path_extras,
            str(
                object=Path(
                    environ.get("PROGRAMFILES", default="C:/Program Files"),
                )
                / "nodejs",
            ),
        )
        environ["PATH"] = pathsep.join([*extra_paths, *path_entries])

    @staticmethod
    def _resolve_commands(
        cwd: Path,
        toolchain: Path | None,
    ) -> dict[str, tuple[str, ...] | None]:
        """Resolve executable prefixes for every external tool.

        Ruff and BasedPyright prefer the explicit Linux AMD64 toolchain
        (``--toolchain``, ``EXACTUS_LINTER_TOOLCHAIN``, or a discovered
        ``linters-linux-amd64``-named executable), then ``PATH``, then the
        ``tools_linux_amd64`` bundle; the remaining tools resolve through
        ``PATH`` followed by the same bundle fallback.

        Args:
            cwd: Project working directory.
            toolchain: Explicit bundled toolchain path, when provided.

        Returns:
            Executable prefixes keyed by tool name; ``None`` marks a
            tool that is not available.

        """
        bundled: Path | None = resolve_linter_toolchain(
            root=cwd,
            option=toolchain,
        )
        exactus_bundle: Path | None = resolve_exactus_tool_bundle(root=cwd)
        commands: dict[str, tuple[str, ...] | None] = {}
        for tool in ("ruff", "basedpyright"):
            found: str | None = which(cmd=tool)
            commands[tool] = (
                (str(object=bundled), tool)
                if bundled is not None
                else (found,)
                if found is not None
                else (str(object=exactus_bundle), tool)
                if exactus_bundle is not None
                else None
            )
        for tool in (
            "pyrefly",
            "eslint",
            "tsc",
            "stylelint",
            "htmlhint",
            "prettier",
        ):
            prefix: tuple[str, ...] = exactus_tool_command(tool=tool, root=cwd)
            commands[tool] = (
                prefix
                if len(prefix) > 1 or which(cmd=tool) is not None
                else None
            )
        for name, command in commands.items():
            trace(
                step=(
                    f"toolchain: {name} → "
                    f"{' '.join(command) if command else 'missing'}"
                ),
                depth=3,
            )
        return commands

    @staticmethod
    def _interpreter_flag(tool: str) -> tuple[str, ...]:
        """Return the interpreter-pinning arguments for a type checker.

        ``basedpyright`` and ``pyrefly`` resolve third-party imports
        through ``python3`` on ``PATH`` by default, which is often an
        interpreter unrelated to the one running this exactus. Pin them to
        ``EXACTUS_PROJECT_PYTHON`` — or, failing that, the running
        interpreter — so import resolution reflects the exactused project,
        mirroring the coverage worker's interpreter selection.

        Args:
            tool: ``basedpyright`` or ``pyrefly``.

        Returns:
            Flag and interpreter-path pair, or an empty tuple for tools
            that do not accept an interpreter pin.

        """
        python: str = environ.get("EXACTUS_PROJECT_PYTHON") or executable
        if tool == "basedpyright":
            return ("--pythonpath", python)
        if tool == "pyrefly":
            return ("--python-interpreter-path", python)
        return ()

    @staticmethod
    def _skipped_entry(tool: str, reason: str) -> dict[str, JsonValue]:
        """Build a report entry for a tool that did not run.

        Args:
            tool: Skipped tool name.
            reason: Human-readable explanation recorded in ``stderr``.

        Returns:
            JSON-serializable skipped report entry.

        """
        return {
            "tool": tool,
            "command": [],
            "returncode": 0,
            "stderr": reason,
            "count": 0,
            "findings": [],
            "skipped": True,
        }

    @staticmethod
    def _matching_files(
        cwd: Path,
        targets: Sequence[str],
        ignores: Sequence[str],
        suffixes: frozenset[str],
        on_file: Callable[[Path], None] | None = None,
    ) -> frozenset[Path]:
        """Collect files of selected types from target globs.

        Excluded directories are pruned during the walk so large excluded
        trees (``node_modules``, ``.build-cache``, etc.) do not slow down
        collection.

        Args:
            cwd: Project working directory.
            targets: Files, directories, or glob patterns to include.
            ignores: Glob patterns to exclude.
            suffixes: Accepted lowercase file suffixes.
            on_file: Optional callback invoked for every retained file.

        Returns:
            Resolved matching file paths.

        """
        scope: _LintCollectScope = _LintCollectScope(
            cwd=cwd,
            suffixes=suffixes,
            ignores=ignores,
            files=set(),
            on_file=on_file,
        )
        for target in targets:
            is_glob: bool = any(character in target for character in "*?[")
            candidates: tuple[Path, ...] = (
                tuple(cwd.glob(pattern=target)) if is_glob else (cwd / target,)
            )
            for candidate in candidates:
                if candidate.is_dir():
                    _lint_walk_directory(directory=candidate, scope=scope)
                else:
                    _lint_maybe_add_file(candidate=candidate, scope=scope)
        return frozenset(scope.files)

    @staticmethod
    def _json_int(value: JsonValue) -> int:
        """Convert a scalar JSON coordinate to an integer.

        Args:
            value: JSON value to convert.

        Returns:
            Integer coordinate, or zero for non-scalar values.

        """
        return int(value) if isinstance(value, (bool, int, float, str)) else 0

    @staticmethod
    def _line_column(text: str, offset: int) -> tuple[int, int]:
        """Return the 1-based line and column for a text offset.

        Args:
            text: Source text containing the offset.
            offset: Zero-based character offset.

        Returns:
            ``(line, column)`` locating the offset.

        """
        return (
            text.count("\n", 0, offset) + 1,
            offset - text.rfind("\n", 0, offset),
        )

    @staticmethod
    def _rule_name(value: JsonValue) -> str:
        """Extract a rule identifier from a scalar or descriptor object.

        Args:
            value: Native rule identifier or rule descriptor.

        Returns:
            Rule identifier text.

        """
        if isinstance(value, dict):
            return str(object=value.get("id", value.get("name", "")))
        return str(object=value)

    @staticmethod
    def _severity(value: JsonValue) -> str:
        """Normalize tool-specific severity labels.

        Args:
            value: Native severity value.

        Returns:
            Normalized severity.

        """
        text_value: str = str(object=value or "").lower()
        if text_value in {"1", "error", "fatal"}:
            return "error"
        if text_value in {"2", "warning", "warn"}:
            return "warning"
        if text_value in {"3", "information", "info", "note"}:
            return "information"
        return text_value or "warning"

    @staticmethod
    def _eslint_ignored(item: Mapping[str, JsonValue]) -> bool:
        """Identify ESLint file-selection notices without source diagnostics.

        Args:
            item: Native ESLint message.

        Returns:
            True only for a nonfatal ignored-file notice without a location.

        """
        return (
            item.get("ruleId") is None
            and item.get("line") is None
            and not item.get("fatal", False)
            and str(object=item.get("message", "")).startswith(
                "File ignored because of a matching ignore pattern.",
            )
        )

    @staticmethod
    def _finding(
        tool: str,
        file: Path,
        rule: str,
        message: str,
        position: tuple[int, int],
    ) -> JsonValue:
        """Create one normalized custom finding.

        Args:
            tool: Exactus tool name.
            file: Finding source file.
            rule: Stable rule identifier.
            message: Human-readable diagnostic.
            position: One-based ``(line, column)`` source position.

        Returns:
            Normalized finding.

        """
        line, column = position
        return {
            "tool": tool,
            "file": str(object=file),
            "rule": rule,
            "severity": "warning",
            "message": message,
            "line": line,
            "column": column,
            "end_line": line,
            "end_column": column,
        }

    @staticmethod
    def _exception_message_candidates(
        *,
        tree: Module,
    ) -> list[ExceptionMessageCandidate]:
        """Find adjacent message assignments consumed by ``raise``.

        Args:
            tree: Parsed module.

        Returns:
            Assignment name, matching raise-argument name, and assigned value
            for each exception-message candidate.

        """
        candidates: list[ExceptionMessageCandidate] = []
        for parent in walk(node=tree):
            fields: Iterator[tuple[str, object]] = cast(
                typ="Iterator[tuple[str, object]]",
                val=iter_fields(node=parent),
            )
            for _field, raw_value in fields:
                if not isinstance(raw_value, list):
                    continue
                statements: list[AST] = [
                    item
                    for item in cast(typ="list[object]", val=raw_value)
                    if isinstance(item, AST)
                ]
                for previous, current in pairwise(statements):
                    name: Name | None = None
                    assigned_value: AST | None = None
                    if (
                        isinstance(previous, Assign)
                        and len(previous.targets) == 1
                        and isinstance(previous.targets[0], Name)
                    ):
                        name = previous.targets[0]
                        assigned_value = previous.value
                    elif isinstance(previous, AnnAssign) and isinstance(
                        previous.target,
                        Name,
                    ):
                        name = previous.target
                        assigned_value = previous.value
                    if (
                        name is None
                        or assigned_value is None
                        or not isinstance(current, Raise)
                        or not isinstance(current.exc, Call)
                        or not current.exc.args
                        or not isinstance(current.exc.args[0], Name)
                        or current.exc.args[0].id != name.id
                        or not (
                            isinstance(assigned_value, Constant)
                            or any(
                                isinstance(item, Constant)
                                and isinstance(item.value, str)
                                for item in walk(node=assigned_value)
                            )
                        )
                    ):
                        continue
                    candidates.append(
                        (name, current.exc.args[0], assigned_value),
                    )
        return candidates

    @staticmethod
    def _lexical_scope(*, node: AST, parents: Mapping[AST, AST]) -> AST:
        """Return the lexical binding scope containing ``node``.

        Args:
            node: Node whose binding scope is required.
            parents: Child-to-parent AST mapping.

        Returns:
            Nearest function, class, or module scope.

        """
        current: AST = node
        while not isinstance(
            current,
            (FunctionDef, AsyncFunctionDef, ClassDef, Module),
        ):
            current = parents[current]
        return current

    @staticmethod
    def _exception_message_assignment(
        *,
        name: Name,
        parents: Mapping[AST, AST],
    ) -> Assign | AnnAssign:
        """Return the assignment that binds an exception-message name.

        Args:
            name: Assignment target name.
            parents: Child-to-parent AST mapping.

        Returns:
            Assignment containing ``name``.

        Raises:
            ValueError: If the candidate is not an assignment target.

        """
        parent: AST = parents[name]
        if isinstance(parent, (Assign, AnnAssign)):
            return parent
        msg: str = "Exception-message candidate has no assignment parent."
        raise ValueError(msg)

    @staticmethod
    def _exception_fix_source(
        *,
        file: Path,
        source: bytes | None,
        tree: Module | None,
    ) -> tuple[bytes, Module] | None:
        """Return source bytes and matching AST for one file.

        Args:
            file: Python source file to load when ``source`` is absent.
            source: Pre-read source bytes, when already available.
            tree: Pre-parsed source tree matching ``source``.

        Returns:
            The source bytes paired with its module tree, or ``None``
            when the source cannot be decoded or parsed.

        """
        source_bytes: bytes = (
            source if source is not None else file.read_bytes()
        )
        if tree is not None:
            return source_bytes, tree
        try:
            return source_bytes, parse(
                source=source_bytes.decode(encoding="utf-8"),
                filename=str(object=file),
            )
        except (SyntaxError, UnicodeDecodeError):
            return None

    @staticmethod
    def _method_kind(
        *,
        decorators: frozenset[str],
        names: frozenset[str],
        method_name: str,
        class_name: str,
    ) -> tuple[str, str] | None:
        """Choose a method-kind diagnostic rule and message.

        Args:
            decorators: Simple decorator names applied to the method.
            names: Loaded names referenced by the method body.
            method_name: Method identifier.
            class_name: Enclosing class identifier.

        Returns:
            ``(rule, message)`` when the binding kind should change.

        """
        if decorators.intersection(
            {"property", "cached_property", "override"},
        ):
            return None
        if "staticmethod" in decorators:
            return (
                (
                    "PY007",
                    (
                        f"Static method `{method_name}` uses `{class_name}`; "
                        "make it a classmethod and use `cls`."
                    ),
                )
                if class_name in names
                else None
            )
        if "classmethod" in decorators:
            return (
                (
                    "PY006",
                    (
                        f"Classmethod `{method_name}` does not use `cls`; "
                        "make it static."
                    ),
                )
                if "cls" not in names
                else None
            )
        uses_class: bool = class_name in names
        if "self" not in names and uses_class:
            return "PY004", (
                f"Method `{method_name}` does not use `self` but "
                f"uses `{class_name}`; make it a classmethod."
            )
        if "self" not in names and not uses_class:
            return "PY005", (
                f"Method `{method_name}` uses neither `self` nor "
                "its class; make it static."
            )
        return None

    @staticmethod
    def _class_definitions(
        *,
        trees: Mapping[Path, Module],
    ) -> dict[str, list[tuple[Path, ClassDef]]]:
        """Index class declarations without importing application modules.

        Args:
            trees: Parsed modules being exactused.

        Returns:
            Every declaration for each class name, including ambiguous names.

        """
        classes: dict[str, list[tuple[Path, ClassDef]]] = {}
        for file, tree in trees.items():
            for class_node in walk(node=tree):
                if isinstance(class_node, ClassDef):
                    classes.setdefault(class_node.name, []).append(
                        (file, class_node),
                    )
        return classes

    @staticmethod
    def _javascript_virtual_methods(
        sources: Mapping[Path, str],
    ) -> dict[str, frozenset[str]]:
        """Find instance method contracts shared across inheritance chains.

        Args:
            sources: JavaScript source text indexed by path.

        Returns:
            Virtual method names for each declared class.

        """
        methods: dict[str, set[str]] = {}
        bases: dict[str, set[str]] = {}
        virtual: dict[str, set[str]] = {}
        for source in sources.values():
            for declaration in Constants.js_class_pattern.finditer(
                string=source,
            ):
                name: str = declaration.group("name")
                methods.setdefault(name, set()).update(
                    method.group("name")
                    for method in Constants.js_method_pattern.finditer(
                        string=declaration.group("body"),
                    )
                    if method.group("static") is None
                )
                if base := declaration.group("base"):
                    bases.setdefault(name, set()).add(base)
        for name, declared in methods.items():
            pending: list[str] = list(bases.get(name, set()))
            visited: set[str] = set()
            while pending:
                parent: str = pending.pop()
                if parent in visited:
                    continue
                visited.add(parent)
                shared: set[str] = declared & methods.get(parent, set())
                virtual.setdefault(name, set()).update(shared)
                virtual.setdefault(parent, set()).update(shared)
                pending.extend(bases.get(parent, set()))
        return {name: frozenset(names) for name, names in virtual.items()}

    @staticmethod
    def _css_unvariable_parts(value: str) -> str:
        """Remove CSS variable references before literal-value checks.

        Args:
            value: CSS declaration value.

        Returns:
            Value with complete ``var(...)`` references removed.

        """
        parts: list[str] = []
        end: int = 0
        for match in Constants.css_reference_pattern.finditer(string=value):
            if match.start() < end:
                continue
            parts.append(value[end : match.start()])
            end = (
                JavaScriptScanner.block_end(
                    source=value,
                    start=match.end() - 1,
                    opening="(",
                    closing=")",
                )
                + 1
            )
        parts.append(value[end:])
        return Constants.css_priority_pattern.sub(
            repl="",
            string="".join(parts),
        ).strip()

    @staticmethod
    def _js_static_style_value(value: str) -> bool:
        """Return whether a JavaScript style value is compile-time static.

        Literal strings, template literals without interpolation, numeric
        literals, booleans, and null are static. Expressions containing
        identifiers, property access, calls, or template interpolation are
        treated as dynamic.

        Args:
            value: JavaScript expression assigned to a style property.

        Returns:
            Whether the value should be represented by a CSS class.

        """
        expression: str = value.strip()
        if Constants.js_quoted_value_pattern.fullmatch(string=expression):
            return True
        if (
            expression.startswith("`")
            and expression.endswith("`")
            and "${" not in expression
        ):
            return True
        return (
            Constants.js_static_value_pattern.fullmatch(string=expression)
            is not None
        )

    @staticmethod
    def _css_has_disallowed_number(value: str) -> bool:
        """Return whether a CSS value contains a forbidden numeric literal.

        The only direct numeric literals permitted by the project convention
        are ``0``, ``1``, ``0%``, and ``100%``. Numbers inside CSS variable
        references have already been removed by the caller.

        Args:
            value: CSS declaration value without ``var(...)`` references.

        Returns:
            Whether a forbidden direct numeric literal is present.

        """
        for match in Constants.css_numeric_literal_pattern.finditer(
            string=value,
        ):
            number: str = match.group("number")
            unit: str = (match.group("unit") or "").lower()
            literal: str = f"{number}{unit}"
            if literal not in Constants.css_allowed_literals:
                return True
        return False

    @staticmethod
    def _tool_stderr(tool: str, stderr: str) -> str:
        """Remove informational log noise from captured tool stderr.

        Args:
            tool: Producing tool name.
            stderr: Captured standard error.

        Returns:
            Standard error with ``INFO`` log lines removed.

        """
        return (
            "".join(
                line
                for line in stderr.splitlines(keepends=True)
                if not line.lstrip().startswith("INFO")
            )
            if tool == "pyrefly"
            else stderr
        )

    @staticmethod
    def _group_final_stage(
        *,
        cwd: Path,
        config: LintExactusConfig,
        progress: LintProgress,
    ) -> JsonValue:
        """Run or describe the configurable group-final pre-stage.

        Args:
            config: Config.
            cwd: Cwd.
            progress: Progress.

        Returns:
            The resulting value.

        """
        if not config.group_final or config.simple:
            return {"enabled": False, "dry_run": not config.fix}
        progress.note(step="group final")
        return cast(
            typ="JsonValue",
            val=run_group_final(root=cwd, dry_run=not config.fix),
        )

    @staticmethod
    def _organize_stage(
        *,
        cwd: Path,
        python_files: frozenset[Path],
        javascript_args: list[str],
        config: LintExactusConfig,
        progress: LintProgress,
    ) -> JsonValue:
        """Run or describe the configurable organize pre-stage.

        Args:
            config: Config.
            cwd: Cwd.
            progress: Progress.
            python_files: Python files selected by scope resolution.
            javascript_args: JavaScript files selected by scope resolution.

        Returns:
            The resulting value.

        """
        if not config.organize or config.simple:
            return {"enabled": False, "dry_run": not config.fix}
        progress.note(step="organize")
        return cast(
            typ="JsonValue",
            val=run_organize(
                paths=sorted(
                    python_files
                    | frozenset(cwd / path for path in javascript_args),
                ),
                dry_run=not config.fix,
                order=configured_order(start=cwd),
            ),
        )

    @staticmethod
    def _long_line_repair(
        *,
        config: LintExactusConfig,
        commands: ToolCommands,
    ) -> LongLineRepair | None:
        """Build the long-line repair for the stabilization loop.

        Args:
            config: Stage configuration for the run.
            commands: Resolved executable prefixes keyed by tool name.

        Returns:
            A repair bound to the resolved Ruff launcher, or ``None``
            when fixing, long-line repair, or Ruff is unavailable.

        """
        ruff: tuple[str, ...] | None = commands.get("ruff")
        if not (config.fix and config.long_lines) or ruff is None:
            return None
        return LongLineRepair(ruff_command=ruff)

    @staticmethod
    def _report_long_lines(
        *,
        repair: LongLineRepair | None,
        writer: Writer,
    ) -> None:
        """Print what the long-line repair did during the run.

        Args:
            repair: Repair used by the run, or ``None``.
            writer: Status-message writer.

        """
        if repair is None:
            return
        summary: RepairSummary = repair.summary()
        if summary.repaired:
            sprint(
                f"Repaired long lines in {len(summary.repaired)} file(s).",
                file=writer,
            )
        if summary.skipped:
            sprint(
                "Skipped long-line repair for "
                f"{len(summary.skipped)} unreadable file(s).",
                file=writer,
            )

    @staticmethod
    def _long_lines_report(
        *,
        cwd: Path,
        repair: LongLineRepair | None,
        tools: Mapping[str, JsonValue],
        file_count: int,
    ) -> dict[str, JsonValue]:
        """Build the long-line repair section of the LINTS report.

        Args:
            cwd: Project root used to relativize repaired paths.
            repair: Repair used by the stabilization loop, or ``None``.
            tools: Collected linter entries; the ``ruff`` entry supplies
                the residual E501 diagnostics this pass exists to clear.
            file_count: Python files in scope.

        Returns:
            A built-in linter entry carrying the residual E501 findings
            plus the repairs the stabilization loop applied.

        """
        started: float = perf_counter()
        ruff_entry: JsonValue = tools.get("ruff", {})
        ruff_findings: JsonValue = (
            ruff_entry.get("findings", [])
            if isinstance(ruff_entry, dict)
            else []
        )
        findings: list[JsonValue] = [
            {
                **cast(typ="dict[str, JsonValue]", val=finding),
                "tool": "custom_python_long_lines",
            }
            for finding in (
                ruff_findings if isinstance(ruff_findings, list) else []
            )
            if isinstance(finding, dict)
            and cast(typ="dict[str, JsonValue]", val=finding).get("rule")
            == "E501"
        ]
        summary: RepairSummary = (
            repair.summary()
            if repair is not None
            else RepairSummary(repaired=(), unresolved=(), skipped=())
        )

        def relative(path: Path) -> str:
            """Render a repaired path relative to the project root.

            Args:
                path: Absolute repaired path.

            Returns:
                The project-relative form when possible.

            """
            return str(
                object=path.relative_to(cwd)
                if path.is_relative_to(cwd)
                else path,
            )

        for path in summary.repaired:
            trace(step=f"long lines: repaired {relative(path=path)}", depth=3)
        for path in summary.skipped:
            trace(step=f"long lines: skipped {relative(path=path)}", depth=3)
        trace(
            step=(
                f"long lines: {len(findings)} residual E501, "
                f"{len(summary.repaired)} repaired, "
                f"{len(summary.skipped)} skipped"
            ),
            depth=2,
        )
        return {
            "returncode": int(bool(findings)),
            "count": len(findings),
            "version": "built-in",
            "files": file_count,
            "duration_seconds": perf_counter() - started,
            "findings": findings,
            "healed": [
                {
                    "file": relative(path=path),
                    "rule": "E501",
                    "action": "repair over-width lines",
                }
                for path in summary.repaired
            ],
            "skipped_files": [
                {
                    "file": relative(path=path),
                    "reason": "unreadable or undecodable source",
                }
                for path in summary.skipped
            ],
        }

    @staticmethod
    def _all_lints_stage(
        *,
        inputs: AllLintsStageInput,
    ) -> tuple[dict[str, JsonValue], list[ToolResult]]:
        """Run the package linters while feeding the live stage share.

        Args:
            inputs: Run scope, stage configuration, report mapping, and
                shared progress tracker.

        Returns:
            The all-lints report payload and raw tool results.

        """
        progress: LintProgress = inputs.progress
        progress.stage(name="all lints")
        last_lint_emit: float = monotonic()

        def _on_lint_progress(
            *,
            completed: int,
            total: int,
            detail: str,
        ) -> None:
            """Fold audit progress into the stage's live share.

            Args:
                completed: Completed file/tool checks.
                total: Discovered file/tool checks.
                detail: Label describing the latest audit event.

            """
            nonlocal last_lint_emit
            now: float = monotonic()
            if (
                completed < total
                and now - last_lint_emit < _COLLECT_PROGRESS_INTERVAL
            ):
                return
            last_lint_emit = now
            progress.note(
                step="all lints",
                detail=detail,
                share=completed / max(total, 1),
                completed=completed,
                total=total,
            )

        trace(step="all lints: launch package audit", depth=2)
        all_lints_report, results = run_all_lints(
            request=AllLintsRequest(
                root=inputs.cwd,
                targets=inputs.targets,
                excludes=inputs.ignores,
                commands=inputs.commands,
                arguments=inputs.tool_args,
                stabilize=inputs.config.fix,
                unsafe_fixes=inputs.config.unsafe_fixes,
                workers=inputs.config.workers,
                batch_repair=inputs.repair,
                progress=_on_lint_progress,
            ),
        )
        inputs.tools.update(
            cast(
                typ="dict[str, JsonValue]",
                val=legacy_tools(results=results),
            ),
        )
        trace(step=f"all lints: {len(results)} tool results merged", depth=2)
        return all_lints_report, results

    @staticmethod
    def _compliance_report(
        *,
        cwd: Path,
        targets: Sequence[str],
        ignores: Sequence[str],
        python_files: frozenset[Path],
    ) -> dict[str, JsonValue]:
        """Run the built-in suppression, annotation and configuration checks.

        Args:
            cwd: Project root.
            targets: Included source paths.
            ignores: Excluded path globs.
            python_files: Pre-discovered owned Python sources.

        Returns:
            A built-in linter entry with findings and scan provenance.

        """
        compliance_started: float = perf_counter()
        trace(step="compliance: scanning owned sources", depth=3)
        compliance: ComplianceResult = scan_compliance(
            inputs=ComplianceInput(
                root=cwd,
                includes=tuple(targets) if tuple(targets) != (".",) else (),
                excludes=tuple(ignores),
                source_files=tuple(python_files),
            ),
        )
        trace(
            step=(
                f"compliance: {len(compliance.findings)} findings "
                f"across {compliance.files} files"
            ),
            depth=2,
        )
        return {
            "returncode": int(bool(compliance.findings)),
            "count": len(compliance.findings),
            "version": "built-in",
            "files": compliance.files,
            "duration_seconds": perf_counter() - compliance_started,
            "findings": [
                {
                    "tool": "custom_compliance",
                    "file": finding.file,
                    "rule": finding.rule,
                    "severity": finding.severity,
                    "line": finding.line,
                    "column": 0,
                    "message": finding.message,
                }
                for finding in compliance.findings
            ],
            "skipped_files": [
                {"file": skip.target, "reason": skip.reason}
                for skip in compliance.skipped
            ],
        }

    @staticmethod
    def _delimiter_report(
        *,
        inputs: CustomToolsInput,
        files: Sequence[Path],
        progress_span: tuple[float, float],
    ) -> dict[str, JsonValue]:
        """Scan JavaScript sources for removable delimiters and heal them.

        Args:
            inputs: Convention-scan inputs carrying the JavaScript file
                scope and the fix toggle.
            files: JavaScript sources covered by the delimiter scan.
            progress_span: Conventions-stage slice this scan may fill.

        Returns:
            A built-in linter entry with findings, applied repairs and
            scan provenance.

        """
        started: float = perf_counter()
        trace(
            step=(
                f"delimiters: scanning {len(files)} files — "
                f"heal {'on' if inputs.fix else 'off'}"
            ),
            depth=3,
        )
        result: DelimiterResult = scan_delimiters(
            inputs=DelimiterInput(
                root=inputs.cwd,
                files=tuple(sorted(files)),
                fix=inputs.fix,
            ),
            progress_span=progress_span,
        )
        trace(
            step=(
                f"delimiters: done — {len(result.findings)} findings, "
                f"{len(result.healed)} healed"
            ),
            depth=3,
        )
        return {
            "returncode": int(bool(result.findings)),
            "count": len(result.findings),
            "version": "built-in",
            "files": result.files,
            "duration_seconds": perf_counter() - started,
            "findings": [
                {
                    "tool": "custom_javascript_delimiters",
                    "file": finding.file,
                    "rule": finding.rule,
                    "severity": finding.severity,
                    "line": finding.line,
                    "column": finding.column,
                    "message": finding.message,
                }
                for finding in result.findings
            ],
            "healed": [
                {
                    "file": heal.file,
                    "rule": heal.rule,
                    "action": heal.action,
                    "transformations": heal.transformations,
                    "characters_removed": heal.characters_removed,
                }
                for heal in result.healed
            ],
        }

    @staticmethod
    def _notation_report(
        *,
        inputs: CustomToolsInput,
        files: Sequence[Path],
        progress_span: tuple[float, float],
    ) -> dict[str, JsonValue]:
        """Run the JavaScript function-block notation scan.

        Args:
            inputs: Convention-scan inputs carrying the JavaScript file
                scope and the fix toggle.
            files: JavaScript sources covered by the notation scan.
            progress_span: Conventions-stage slice this scan may fill.

        Returns:
            A built-in linter entry with findings, applied repairs and
            scan provenance.

        """
        started: float = perf_counter()
        trace(
            step=(
                f"notation: scanning {len(files)} files — "
                f"heal {'on' if inputs.fix else 'off'}"
            ),
            depth=3,
        )
        result: FunctionBlocksResult = scan_function_blocks(
            inputs=FunctionBlocksInput(
                root=inputs.cwd,
                files=tuple(sorted(files)),
                fix=inputs.fix,
            ),
            progress_span=progress_span,
        )
        trace(
            step=(
                f"notation: done — {len(result.findings)} findings, "
                f"{len(result.healed)} healed"
            ),
            depth=3,
        )
        return {
            "returncode": int(bool(result.findings)),
            "count": len(result.findings),
            "version": "built-in",
            "files": result.files,
            "duration_seconds": perf_counter() - started,
            "findings": [
                {
                    "tool": "custom_javascript_notation",
                    "file": finding.file,
                    "rule": finding.rule,
                    "severity": finding.severity,
                    "line": finding.line,
                    "column": finding.column,
                    "message": finding.message,
                }
                for finding in result.findings
            ],
            "healed": [
                {
                    "file": heal.file,
                    "rule": heal.rule,
                    "action": heal.action,
                    "transformations": heal.transformations,
                }
                for heal in result.healed
            ],
        }

    @staticmethod
    def _shebang_report(
        *,
        inputs: CustomToolsInput,
        progress_span: tuple[float, float],
    ) -> dict[str, JsonValue]:
        """Run the executable-permission check and heal mismatches.

        Args:
            inputs: Convention-scan inputs carrying the shebang
                settings and include/exclude globs.
            progress_span: Conventions-stage slice this scan may fill.

        Returns:
            A built-in linter entry with findings, applied repairs and
            scan provenance.

        """
        started: float = perf_counter()
        heal: bool = inputs.shebang.heal and inputs.fix
        trace(
            step=(
                f"shebang: scanning sources — heal {'on' if heal else 'off'}"
            ),
            depth=3,
        )
        result: ShebangResult = scan_shebang(
            inputs=ShebangInput(
                root=inputs.cwd,
                includes=(
                    tuple(inputs.targets)
                    if tuple(inputs.targets) != (".",)
                    else ()
                ),
                excludes=tuple(inputs.ignores),
                settings=replace(inputs.shebang, heal=heal),
                source_files=tuple(inputs.python_files),
            ),
            progress_span=progress_span,
        )
        return {
            "returncode": int(bool(result.findings)),
            "count": len(result.findings),
            "version": "built-in",
            "files": result.files,
            "duration_seconds": perf_counter() - started,
            "findings": [
                {
                    "tool": "custom_shebang",
                    "file": finding.file,
                    "rule": finding.rule,
                    "severity": finding.severity,
                    "line": finding.line,
                    "column": 0,
                    "message": finding.message,
                }
                for finding in result.findings
            ],
            "healed": [
                {"file": heal.file, "rule": heal.rule, "action": heal.action}
                for heal in result.healed
            ],
            "skipped_files": [
                {"file": skip.target, "reason": skip.reason}
                for skip in result.skipped
            ],
        }

    @staticmethod
    def _version(command: Sequence[str]) -> str | None:
        """Probe one linter's version through ``--version``.

        Args:
            command: Resolved executable prefix of the linter.

        Returns:
            The first version number the probe prints, or ``None`` when
            the probe fails, times out or prints none.

        """
        try:
            completed: CompletedProcess[str] = run(
                args=[*command, "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=Constants.version_timeout,
            )
        except (OSError, SubprocessError):
            return None
        found: Match[str] | None = Constants.version_pattern.search(
            string=f"{completed.stdout}\n{completed.stderr}",
        )
        return found.group() if found is not None else None

    @staticmethod
    def _payload[T](entries: Mapping[str, T]) -> dict[str, JsonValue]:
        """Cast a JSON-serializable mapping to a mutable payload.

        Args:
            entries: Mapping of JSON-serializable values.

        Returns:
            Mutable JSON payload.

        """
        return cast(typ="dict[str, JsonValue]", val=dict(entries))

    @staticmethod
    def _generated_pyproject(*, python_args: Sequence[str]) -> str:
        """Return a minimal ``pyproject.toml`` for config-less exactuss.

        Args:
            python_args: Relative Python file arguments being linted.

        Returns:
            Generated ``pyproject.toml`` text carrying the exactus's Ruff,
            BasedPyright, and Pyrefly defaults plus explicit includes
            covering every linted file.

        """
        template: Traversable = template_resource(name="pyproject.toml")
        document: TomlDocument = cast(
            typ="TomlDocument",
            val=toml_loads(template.read_text(encoding="utf-8")),
        )
        includes: list[str] = [*python_args] or ["**"]
        tool: dict[str, TomlValue] = cast(
            typ="dict[str, TomlValue]",
            val=document["tool"],
        )
        for section in ("basedpyright", "pyrefly"):
            table: dict[str, TomlValue] = cast(
                typ="dict[str, TomlValue]",
                val=tool[section],
            )
            key: str = (
                "include" if section == "basedpyright" else "project-includes"
            )
            table[key] = cast(typ="TomlValue", val=includes)
        return TomlSerializer.dumps(value=document)

    @staticmethod
    def _required_tools(
        python_args: Sequence[str],
        eslint_args: Sequence[str],
        stylelint_args: Sequence[str],
        htmlhint_args: Sequence[str],
        clean_files: Sequence[Path],
    ) -> frozenset[str]:
        """Return the external tool commands needed for the file set.

        Args:
            python_args: Relative Python file arguments.
            eslint_args: Relative JavaScript file arguments.
            stylelint_args: Relative CSS file arguments.
            htmlhint_args: Relative HTML file arguments.
            clean_files: Source files to clean.

        Returns:
            Tool commands that must be available on ``PATH``.

        """
        required: set[str] = set()
        if python_args:
            required.update(("ruff", "basedpyright", "pyrefly"))
        if eslint_args:
            required.update(("eslint", "tsc"))
        if stylelint_args:
            required.add("stylelint")
        if htmlhint_args:
            required.add("htmlhint")
        if any(file.suffix in SourceCleaner.py for file in clean_files):
            required.add("ruff")
        if any(file.suffix in SourceCleaner.prettier for file in clean_files):
            required.add("prettier")
        return frozenset(required)

    @staticmethod
    def _relative_args(cwd: Path, files: frozenset[Path]) -> list[str]:
        """Return sorted paths relative to the working directory.

        Args:
            cwd: Project working directory.
            files: Absolute file paths.

        Returns:
            Sorted POSIX-relative tool arguments.

        """
        return [file.relative_to(cwd).as_posix() for file in sorted(files)]

    @staticmethod
    def _existing_args(cwd: Path, args: Sequence[str]) -> list[str]:
        """Drop relative arguments whose files no longer exist.

        Args:
            cwd: Project working directory the arguments are relative to.
            args: Relative tool arguments collected before cleaning.

        Returns:
            Arguments that still resolve to files on disk.

        """
        return [arg for arg in args if (cwd / arg).is_file()]

    @staticmethod
    def _custom_entry(
        tool: str,
        findings: Sequence[JsonValue],
        started: float,
    ) -> dict[str, JsonValue]:
        """Build a report entry for a convention checker.

        Args:
            tool: Producing tool name.
            findings: Sorted normalized findings.
            started: ``perf_counter`` value when the checker started.

        Returns:
            JSON-serializable report entry.

        """
        return {
            "tool": tool,
            "command": [],
            "returncode": 0,
            "stderr": "",
            "count": len(findings),
            "findings": list(findings),
            "duration_seconds": round(
                number=perf_counter() - started,
                ndigits=3,
            ),
        }

    @staticmethod
    def _convention_scopes(*, inputs: CustomToolsInput) -> _ConventionScopes:
        """Collect the file lists each conventions sub-step scans.

        Args:
            inputs: Convention-scan inputs.

        Returns:
            Per-sub-step file scopes used for findings and weighting.

        """
        return _ConventionScopes(
            python_files=sorted(
                file for file in inputs.python_files if file.is_file()
            ),
            delimiter_files=[
                inputs.cwd / file
                for file in inputs.eslint_args
                if Path(file).suffix.lower()
                in JavaScriptDelimiterSimplifier.EXTENSIONS
                and not file.endswith(".min.js")
                and (inputs.cwd / file).is_file()
            ],
            notation_files=[
                inputs.cwd / file
                for file in inputs.eslint_args
                if Path(file).suffix.lower() in {".js", ".mjs", ".cjs", ".jsx"}
                and not file.endswith(".min.js")
                and (inputs.cwd / file).is_file()
            ],
            javascript_files=[
                inputs.cwd / file
                for file in inputs.eslint_args
                if Path(file).suffix.lower() in {".js", ".jsx"}
                and not file.endswith(".min.js")
                and (inputs.cwd / file).is_file()
            ],
            css_files=[
                inputs.cwd / file
                for file in inputs.stylelint_args
                if (inputs.cwd / file).is_file()
            ],
            html_files=[
                inputs.cwd / file
                for file in inputs.htmlhint_args
                if (inputs.cwd / file).is_file()
            ],
        )
