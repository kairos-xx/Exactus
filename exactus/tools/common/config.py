# Copyright (c) 2026
"""Discover ``[tool.exactus]`` settings and render them as tool arguments.

Settings live in ``pyproject.toml`` files found by walking upward from the
exactused project. Keys are the long flags of the tool they configure, so a
table is rendered into command-line tokens with the tool's own parser and is
validated by it. Callers place those tokens before the arguments the user
typed, which gives the order: parser defaults, configuration, command line.
"""

from __future__ import annotations

from argparse import Action, ArgumentParser, ArgumentTypeError
from dataclasses import dataclass
from importlib import import_module
from json import dumps
from json import loads as json_loads
from os import environ
from pathlib import Path
from sys import argv as sys_argv
from tomllib import TOMLDecodeError, loads
from typing import TYPE_CHECKING, Final, cast, final

from exactus.packages.argument_parser import normalized_option
from exactus.tools.common.collect_files import mark
from exactus.tools.common.path_filters import (
    PathFilters,
    default_excluded_dirs,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Sequence
    from types import ModuleType

    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        environment_variable: Grouped module constant.
        orchestrated_variable: Grouped module constant.
        orchestrator_keys: Grouped module constant.
        disabled: Grouped module constant.
        file_name: Grouped module constant.
        reserved: Grouped module constant.
        path_keys: Grouped module constant.
        select_flags: Grouped module constant.
        info_flags: Grouped module constant.
        repeat_actions: Grouped module constant.
        multi_actions: Grouped module constant.
        extension_sections: Grouped module constant.

    """

    environment_variable: Final[str] = "EXACTUS_CONFIG"
    orchestrated_variable: Final[str] = "EXACTUS_ORCHESTRATED"
    orchestrator_keys: Final[frozenset[str]] = frozenset(
        (
            "clear",
            "pipeline",
            "exclude-tools",
            "include",
            "exclude",
            "root",
            "reports-dir",
        ),
    )
    disabled: Final[str] = "off"
    file_name: Final[str] = "pyproject.toml"
    reserved: Final[frozenset[str]] = frozenset(("root", "reports-dir"))
    path_keys: Final[tuple[str, ...]] = ("actions", "workspace")
    select_flags: Final[frozenset[str]] = frozenset(
        ("-t", "--tools", "--tool"),
    )
    info_flags: Final[frozenset[str]] = frozenset(
        (
            "-h",
            "--help",
            "--list-tools",
            "--list-pipelines",
            "--show-config",
            "--status",
            "--status-all",
            "--kill",
            "--kill-all",
        ),
    )
    repeat_actions: Final[frozenset[str]] = frozenset(("_AppendAction",))
    multi_actions: Final[frozenset[str]] = frozenset(("_ExtendAction",))
    extension_sections: Final[frozenset[str]] = frozenset(("mcp",))


class ConfigError(ValueError):
    """Report an invalid exactus configuration, naming file and key."""


@dataclass(frozen=True, slots=True)
class ConfigFile:
    """One loaded ``pyproject.toml`` carrying a ``[tool.exactus]`` table.

    Attributes:
        path: File the table came from.
        table: The decoded ``[tool.exactus]`` table.

    """

    path: Path
    table: dict[str, JsonValue]


def reports_directory(*, files: tuple[ConfigFile, ...]) -> Path:
    """Resolve the configured project-relative exactus reports directory.

    Args:
        files: Configuration layers, nearest first.

    Returns:
        Relative reports directory, defaulting to ``EXACTUS_RESULTS``.

    Raises:
        ConfigError: The directory is empty or escapes the project.

    """
    value: JsonValue | None = stacked(files=files, path=()).get(
        "reports-dir",
        "EXACTUS_RESULTS",
    )
    if not isinstance(value, str) or not value.strip():
        msg: str = (
            "[tool.exactus] reports-dir must be a nonempty relative path"
        )
        raise ConfigError(msg)
    directory: Path = Path(value)
    if (
        directory.is_absolute()
        or bool(directory.drive)
        or directory == Path()
        or (".." in directory.parts)
    ):
        msg = "[tool.exactus] reports-dir must stay inside the project"
        raise ConfigError(msg)
    return directory


def reports_root(*, start: Path) -> Path:
    """Return the resolved absolute reports directory for ``start``.

    ``EXACTUS_REPORTS_ROOT`` — exported by the orchestrator and by
    ``resolve_arguments`` — wins; otherwise the configured
    ``reports-dir`` resolves against its anchor, defaulting to
    ``<start>/EXACTUS_RESULTS``.

    Args:
        start: Directory configuration discovery begins at.

    Returns:
        Absolute reports directory.

    """
    if override := environ.get("EXACTUS_REPORTS_ROOT"):
        return Path(override).resolve()
    files: tuple[ConfigFile, ...] = discovery_from_environment(start=start)
    return (
        reports_anchor(files=files, start=start)
        / reports_directory(files=files)
    ).resolve()


def reports_anchor(*, files: tuple[ConfigFile, ...], start: Path) -> Path:
    """Resolve the directory a relative ``reports-dir`` anchors at.

    The directory of the file declaring ``reports-dir`` wins so a run
    started in a subdirectory still reports beside its configuration;
    the ``root = true`` marker's directory follows, then ``start``.

    Args:
        files: Configuration layers, nearest first.
        start: Directory the upward walk began in.

    Returns:
        Absolute directory a relative ``reports-dir`` resolves against.

    """
    for item in files:
        if any(
            (
                _normal(key=key) == "reports-dir"
                for key, value in item.table.items()
                if not isinstance(value, dict)
            ),
        ):
            return item.path.parent.resolve()
    for item in files:
        if item.table.get("root") is True:
            return item.path.parent.resolve()
    return start.resolve()


def _as_table(*, value: JsonValue | None) -> dict[str, JsonValue] | None:
    """Narrow a decoded TOML value to a table.

    Args:
        value: Decoded value.

    Returns:
        The table, or ``None`` when the value is not one.

    """
    if isinstance(value, dict):
        return cast(typ="dict[str, JsonValue]", val=value)
    return None


def _load(*, path: Path) -> ConfigFile | None:
    """Parse one file and return its exactus table, if present.

    Args:
        path: ``pyproject.toml`` to read.

    Returns:
        The loaded table, or ``None`` when the file has no ``[tool.exactus]``.

    Raises:
        ConfigError: If the file is not valid TOML.

    """
    try:
        document: dict[str, JsonValue] = loads(
            path.read_text(encoding="utf-8"),
        )
    except TOMLDecodeError as exc:
        msg: str = f"{path}: invalid TOML: {exc}"
        raise ConfigError(msg) from exc
    exactus: dict[str, JsonValue] | None = _as_table(
        value=_sub_table(table=document, path=("tool",)).get("exactus"),
    )
    if exactus is None:
        return None
    return ConfigFile(path=path, table=exactus)


def discover(
    *,
    start: Path,
    explicit: Path | None = None,
    disabled: bool = False,
    boundary: Path | None = None,
) -> tuple[ConfigFile, ...]:
    """Collect exactus configuration files, nearest first.

    Args:
        start: Directory the upward walk begins in.
        explicit: A single file to load instead of walking.
        disabled: Skip the configuration layer entirely.
        boundary: Directory the upward walk never ascends past. When
            ``start`` lies outside it, the walk begins at the boundary —
            an explicit project root cannot inherit an enclosing
            project's configuration or reports anchor.

    Returns:
        Loaded files, nearest first.

    Raises:
        ConfigError: If an explicit file is missing or any file is invalid.

    """
    if disabled:
        return ()
    if explicit is not None:
        if not explicit.is_file():
            msg: str = f"{explicit}: configuration file not found"
            raise ConfigError(msg)
        loaded: ConfigFile | None = _load(path=explicit)
        return (loaded,) if loaded is not None else ()
    found: list[ConfigFile] = []
    resolved: Path = start.resolve()
    bound: Path | None = boundary.resolve() if boundary is not None else None
    if bound is not None and not resolved.is_relative_to(bound):
        resolved = bound
    for directory in (resolved, *resolved.parents):
        candidate: Path = directory / Constants.file_name
        if candidate.is_file():
            item: ConfigFile | None = _load(path=candidate)
            if item is not None:
                found.append(item)
                if item.table.get("root") is True:
                    break
        if bound is not None and directory == bound:
            break
    return tuple(found)


def discovery_from_environment(*, start: Path) -> tuple[ConfigFile, ...]:
    """Discover files honoring the ``EXACTUS_CONFIG`` variable.

    An explicit ``EXACTUS_ROOT`` bounds the upward walk at the declared
    project root so nested invocations cannot inherit the enclosing
    project's configuration. When it is unset, ``start`` itself bounds
    the walk — an explicit run target, whether it arrives through the
    CLI or the Python API, cannot inherit an enclosing project's
    configuration or reports anchor either.

    Args:
        start: Directory the upward walk begins in.

    Returns:
        Loaded files, nearest first.

    """
    value: str = environ.get(Constants.environment_variable, "")
    if value == Constants.disabled:
        return ()
    root: str | None = environ.get("EXACTUS_ROOT")
    boundary: Path
    if root is not None:
        boundary = Path(root)
    else:
        boundary = start if start.is_dir() else start.parent
    return discover(
        start=start,
        explicit=Path(value) if value else None,
        boundary=boundary,
    )


def _normal(*, key: str) -> str:
    """Normalize a TOML key to the long-flag spelling.

    Args:
        key: Raw key such as ``fail_under``.

    Returns:
        The dash-separated key.

    """
    if key in {"coverage_tests", "kwargs_typehints", "visual_cause"}:
        return key
    return key.replace("_", "-")


def _sub_table(
    *,
    table: dict[str, JsonValue],
    path: tuple[str, ...],
) -> dict[str, JsonValue]:
    """Descend into nested tables.

    Args:
        table: Root ``[tool.exactus]`` table.
        path: Table names to follow.

    Returns:
        The nested table, or an empty one when absent.

    """
    node: dict[str, JsonValue] = table
    for name in path:
        child: dict[str, JsonValue] | None = _as_table(value=node.get(name))
        if child is None:
            return {}
        node = child
    return dict(node)


def stacked(
    *,
    files: tuple[ConfigFile, ...],
    path: tuple[str, ...],
) -> dict[str, JsonValue]:
    """Merge the non-table values of one table across all files.

    Args:
        files: Loaded files, nearest first.
        path: Table names below ``[tool.exactus]``; empty for the root table.

    Returns:
        Merged values; scalars nearest-wins, lists farthest-first.

    """
    merged: dict[str, JsonValue] = {}
    for item in reversed(files):
        for raw, value in _sub_table(table=item.table, path=path).items():
            if isinstance(value, dict) or (
                isinstance(value, list)
                and bool(value)
                and all(isinstance(entry, dict) for entry in value)
            ):
                continue
            key: str = _normal(key=raw)
            previous: JsonValue | None = merged.get(key)
            if isinstance(value, list) and isinstance(previous, list):
                merged[key] = [*previous, *value]
            else:
                merged[key] = value
    return merged


def _actions(*, parser: ArgumentParser) -> list[Action]:
    """List a parser's actions.

    argparse offers no public listing, so this is the module's only
    reflective access.

    Args:
        parser: Parser to inspect.

    Returns:
        The registered actions.

    """
    return vars(parser)["_actions"]


def _action(*, parser: ArgumentParser, key: str) -> Action | None:
    """Find the parser action for a long flag.

    Args:
        parser: Tool parser.
        key: Normalized key without leading dashes.

    Returns:
        The matching action, or ``None``.

    """
    flag: str = f"--{key}"
    for action in _actions(parser=parser):
        if flag in action.option_strings:
            return action
    return None


def _convert(
    *,
    action: Action,
    value: JsonValue,
    source: str,
    key: str,
) -> str:
    """Validate one scalar against the action's type and choices.

    Args:
        action: Matching parser action.
        value: Raw TOML scalar.
        source: Text naming the file and table for errors.
        key: Normalized key for errors.

    Returns:
        The scalar as command-line text.

    Raises:
        ConfigError: If the value is rejected by the action.

    """
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        msg: str = f"{source}: {key}: unsupported value {value!r}"
        raise ConfigError(msg)
    text: str = str(object=value)
    try:
        if callable(action.type):
            _ = cast(typ="Callable[[str], object]", val=action.type)(text)
    except (ValueError, TypeError, ArgumentTypeError) as exc:
        msg = f"{source}: {key}: invalid value {value!r}"
        raise ConfigError(msg) from exc
    if action.choices is not None and text not in {
        str(object=choice) for choice in action.choices
    }:
        msg = f"{source}: {key}: {value!r} is not an allowed choice"
        raise ConfigError(msg)
    return text


def _pair(*, flag: str, text: str) -> list[str]:
    """Join a flag and its value so argparse cannot misread the value.

    Args:
        flag: Long option such as ``--fail-under``.
        text: Value text.

    Returns:
        Two tokens, or one ``--flag=value`` token for dash-led values.

    """
    return [f"{flag}={text}"] if text.startswith("-") else [flag, text]


def _tokens_for(
    *,
    action: Action,
    key: str,
    value: JsonValue,
    source: str,
) -> list[str]:
    """Render one key's value for the action that owns its flag.

    Args:
        action: Parser action owning ``--key``.
        key: Normalized key without leading dashes.
        value: TOML value.
        source: Text naming the file and table for errors.

    Returns:
        Command-line tokens; empty for a false flag.

    Raises:
        ConfigError: If the value does not suit the action.

    """
    flag: str = f"--{key}"
    if action.nargs == 0 or (action.nargs == "*" and value is True):
        if not isinstance(value, bool):
            msg: str = f"{source}: {key}: expected true or false"
            raise ConfigError(msg)
        return [flag] if value else []
    items: list[JsonValue] = (
        cast(typ="list[JsonValue]", val=value)
        if isinstance(value, list)
        else [value]
    )
    texts: list[str] = [
        _convert(action=action, value=item, source=source, key=key)
        for item in items
    ]
    kind: str = type(action).__name__
    if kind in Constants.multi_actions or action.nargs in {"+", "*"}:
        return [flag, *texts]
    if kind in Constants.repeat_actions or isinstance(value, list):
        return [
            token for text in texts for token in _pair(flag=flag, text=text)
        ]
    return _pair(flag=flag, text=texts[-1])


def render(
    *,
    values: dict[str, JsonValue],
    parser: ArgumentParser,
    source: str,
    strict: bool,
) -> list[str]:
    """Render config values into argv tokens for one parser.

    Args:
        values: Merged key/value pairs.
        parser: Parser that owns the flags.
        source: Text naming the file and table for errors.
        strict: Raise on keys the parser lacks instead of skipping them.

    Returns:
        Command-line tokens.

    Raises:
        ConfigError: On an unknown key (strict) or an invalid value.

    """
    tokens: list[str] = []
    for key, value in values.items():
        if key in Constants.reserved:
            continue
        action: Action | None = _action(parser=parser, key=key)
        if action is None:
            if strict:
                msg: str = f"{source}: {key}: unknown option"
                raise ConfigError(msg)
            continue
        tokens.extend(
            _tokens_for(action=action, key=key, value=value, source=source),
        )
    return tokens


def section_tool(*, section: str) -> str:
    """Return the tool a ``[tool.exactus.<section>]`` table configures.

    Args:
        section: Normalized table name, canonical.

    Returns:
        The canonical section name.

    """
    return section


def _section_layers(
    *,
    files: tuple[ConfigFile, ...],
    tool: str,
    prefix: tuple[str, ...],
    label: str,
) -> list[tuple[str, dict[str, JsonValue]]]:
    """Read one canonical tool table under ``prefix``.

    Args:
        files: Loaded files, nearest first.
        tool: Canonical tool identifier.
        prefix: Table names above the tool table (``()`` or
            ``("pipeline", <id>)``).
        label: Text naming the file for error messages.

    Returns:
        ``(source, values)`` pairs, lowest priority first.

    """
    names: tuple[str, ...] = (tool,)
    tables: list[tuple[str, dict[str, JsonValue]]] = [
        (
            f"{label}: [tool.exactus.{'.'.join((*prefix, name))}]",
            _resolved_paths(
                files=files,
                path=(*prefix, name),
                values=stacked(files=files, path=(*prefix, name)),
            ),
        )
        for name in names
    ]
    layers: list[tuple[str, dict[str, JsonValue]]] = []
    index: int
    source: str
    values: dict[str, JsonValue]
    for index, (source, values) in enumerate(iterable=tables):
        newer: set[str] = {
            key for _, later in tables[index + 1 :] for key in later
        }
        layers.append(
            (
                source,
                {
                    key: value
                    for key, value in values.items()
                    if key not in newer
                },
            ),
        )
    return layers


def layered_argv(
    *,
    files: tuple[ConfigFile, ...],
    tool: str,
    parser: ArgumentParser,
    pipeline: str | None = None,
    standalone: bool = False,
) -> list[tuple[str, tuple[str, ...]]]:
    """Render the configured arguments of one tool per layer.

    Args:
        files: Loaded files, nearest first.
        tool: Canonical tool identifier.
        parser: The tool's parser.
        pipeline: Pipeline whose scoped table also applies.
        standalone: Also apply common keys that ``check`` handles itself.

    Returns:
        ``(layer, tokens)`` pairs, lowest priority first. Layers are
        ``common``, ``tool`` and ``pipeline``.

    """
    name: str = str(object=files[0].path) if files else "<config>"
    common: dict[str, JsonValue] = {
        key: value
        for key, value in stacked(files=files, path=()).items()
        if standalone or key not in Constants.orchestrator_keys
    }
    layers: list[tuple[str, str, dict[str, JsonValue], bool]] = [
        ("common", f"{name}: [tool.exactus]", common, False),
        *(
            ("tool", source, values, True)
            for source, values in _section_layers(
                files=files,
                tool=tool,
                prefix=(),
                label=name,
            )
        ),
    ]
    if pipeline is not None:
        layers.extend(
            (
                ("pipeline", source, values, True)
                for source, values in _section_layers(
                    files=files,
                    tool=tool,
                    prefix=("pipeline", pipeline),
                    label=name,
                )
            ),
        )
    return [
        (
            layer,
            tuple(
                render(
                    values=values,
                    parser=parser,
                    source=source,
                    strict=strict,
                ),
            ),
        )
        for layer, source, values, strict in layers
    ]


def argv_for(
    *,
    files: tuple[ConfigFile, ...],
    tool: str,
    parser: ArgumentParser,
    pipeline: str | None = None,
    standalone: bool = False,
) -> tuple[str, ...]:
    """Render the configured arguments of one tool, lowest priority first.

    Args:
        files: Loaded files, nearest first.
        tool: Canonical tool identifier.
        parser: The tool's parser.
        pipeline: Pipeline whose scoped table also applies.
        standalone: Also apply common keys that ``check`` handles itself.

    Returns:
        Tokens to place before the preset and CLI arguments.

    """
    return tuple(
        (
            token
            for _, tokens in layered_argv(
                files=files,
                tool=tool,
                parser=parser,
                pipeline=pipeline,
                standalone=standalone,
            )
            for token in tokens
        ),
    )


def _shown(*, parser: ArgumentParser, tokens: list[str]) -> dict[str, str]:
    """Parse ``tokens`` and return each destination's value as text.

    Args:
        parser: Parser to run.
        tokens: Command-line tokens.

    Returns:
        ``repr`` of every parsed value, keyed by destination.

    """
    return {
        key: repr(value)
        for key, value in vars(parser.parse_args(args=tokens)).items()
    }


@dataclass(frozen=True, slots=True)
class EffectiveRequest:
    """Describe one tool whose effective options are reported.

    Attributes:
        tool: Canonical tool identifier.
        module: Catalog module used to build the tool's parser.
        preset: Catalog pipeline preset tokens.
        cli: Command-line tokens for this tool.
        pipeline: Pipeline whose scoped table also applies.

    """

    tool: str
    module: str
    preset: tuple[str, ...] = ()
    cli: tuple[str, ...] = ()
    pipeline: str | None = None


def effective(
    *,
    files: tuple[ConfigFile, ...],
    request: EffectiveRequest,
) -> list[tuple[str, str, str]]:
    """Report each option's final value and the layer that set it.

    Args:
        files: Loaded files, nearest first.
        request: The tool and its non-config layers.

    Returns:
        ``(option, value, layer)`` rows; layer is one of ``default``,
        ``preset``, ``common``, ``tool``, ``pipeline`` or ``cli``.

    """
    parser: ArgumentParser = tool_parser(module=request.module)
    for action in _actions(parser=parser):
        action.required = False
    steps: list[tuple[str, tuple[str, ...]]] = [
        ("preset", request.preset),
        *layered_argv(
            files=files,
            tool=request.tool,
            parser=parser,
            pipeline=request.pipeline,
        ),
        ("cli", request.cli),
    ]
    try:
        current: dict[str, str] = _shown(parser=parser, tokens=[])
    except SystemExit:
        return []
    source: dict[str, str] = dict.fromkeys(current, "default")
    tokens: list[str] = []
    for layer, added in steps:
        tokens.extend(added)
        try:
            updated: dict[str, str] = _shown(parser=parser, tokens=tokens)
        except SystemExit:
            continue
        named: set[str] = {
            action.dest
            for action in _actions(parser=parser)
            for option in action.option_strings
            for token in added
            if token == option or token.startswith(f"{option}=")
        }
        for key, value in updated.items():
            if key in named or value != current.get(key):
                source[key] = layer
        current = updated
    return [(key, current[key], source[key]) for key in sorted(current)]


def validate(
    *,
    files: tuple[ConfigFile, ...],
    parsers: dict[str, ArgumentParser],
    pipelines: Collection[str],
) -> None:
    """Reject unknown tables and keys before any tool starts.

    Args:
        files: Loaded files, nearest first.
        parsers: Tool parser per canonical tool identifier.
        pipelines: Known pipeline identifiers.

    Raises:
        ConfigError: On an unknown table, pipeline, tool or option.

    """
    _ = reports_directory(files=files)
    for item in files:
        origin: str = str(object=item.path)
        for raw, value in item.table.items():
            key: str = _normal(key=raw)
            if not isinstance(value, dict):
                if key not in Constants.orchestrator_keys and (
                    not any(
                        _action(parser=known, key=key)
                        for known in parsers.values()
                    )
                ):
                    msg: str = f"{origin}: {key}: unknown option"
                    raise ConfigError(msg)
                continue
            if key == "pipeline":
                _validate_pipelines(
                    origin=origin,
                    table=cast(typ="dict[str, JsonValue]", val=value),
                    parsers=parsers,
                    pipelines=pipelines,
                )
            elif section_tool(section=key) in parsers:
                _ = render(
                    values=stacked(files=(item,), path=(raw,)),
                    parser=parsers[section_tool(section=key)],
                    source=f"{origin}: [tool.exactus.{key}]",
                    strict=True,
                )
            elif key in Constants.extension_sections:
                continue
            else:
                msg = f"{origin}: [tool.exactus.{key}]: unknown tool"
                raise ConfigError(msg)


def _validate_pipelines(
    *,
    origin: str,
    table: dict[str, JsonValue],
    parsers: dict[str, ArgumentParser],
    pipelines: Collection[str],
) -> None:
    """Validate the ``[tool.exactus.pipeline]`` subtree of one file.

    Args:
        origin: File path used in messages.
        table: The ``pipeline`` table.
        parsers: Tool parser per canonical tool identifier.
        pipelines: Known pipeline identifiers.

    Raises:
        ConfigError: On an unknown pipeline, tool or option.

    """
    for pipeline, body in table.items():
        if pipeline not in pipelines:
            msg: str = (
                f"{origin}: "
                f"[tool.exactus.pipeline.{pipeline}]: unknown pipeline"
            )
            raise ConfigError(msg)
        if not isinstance(body, dict):
            continue
        for tool, values in cast(typ="dict[str, JsonValue]", val=body).items():
            if not isinstance(values, dict):
                if _normal(key=tool) not in Constants.orchestrator_keys:
                    msg = (
                        f"{origin}: "
                        f"[tool.exactus.pipeline.{pipeline}]: "
                        f"{tool}: unknown option"
                    )
                    raise ConfigError(msg)
                continue
            canonical: str = section_tool(section=tool)
            if canonical not in parsers:
                msg = (
                    f"{origin}: "
                    f"[tool.exactus.pipeline.{pipeline}.{tool}]: unknown tool"
                )
                raise ConfigError(msg)
            _ = render(
                values={
                    _normal(key=name): value
                    for name, value in cast(
                        typ="dict[str, JsonValue]",
                        val=values,
                    ).items()
                    if not isinstance(value, dict)
                },
                parser=parsers[canonical],
                source=f"{origin}: [tool.exactus.pipeline.{pipeline}.{tool}]",
                strict=True,
            )


def _resolved_paths(
    *,
    files: tuple[ConfigFile, ...],
    path: tuple[str, ...],
    values: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    """Resolve path-valued keys against the directory of their file.

    Args:
        files: Loaded files, nearest first.
        path: Table names below ``[tool.exactus]`` the values came from.
        values: Merged values.

    Returns:
        Values with configured file paths made absolute.

    """
    resolved: dict[str, JsonValue] = dict(values)
    for key in Constants.path_keys:
        value: JsonValue | None = resolved.get(key)
        if not isinstance(value, str):
            continue
        for item in files:
            declared: dict[str, JsonValue] = _sub_table(
                table=item.table,
                path=path,
            )
            if any(_normal(key=name) == key for name in declared):
                resolved[key] = str(object=item.path.parent / value)
                break
    return resolved


def orchestrator_arguments(
    *,
    files: tuple[ConfigFile, ...],
    parser: ArgumentParser,
    arguments: Sequence[str],
    pipeline: str | None,
    tool_flags: Collection[str] = (),
) -> tuple[str, ...]:
    """Render ``check``'s own settings for pipeline-style invocations.

    Settings are injected only when the invocation is not a single-tool
    run and not an information request. Server settings are additionally
    skipped when a tool is selected.

    Args:
        files: Loaded files, nearest first.
        parser: Orchestrator parser that owns the flags.
        arguments: Arguments the user typed.
        pipeline: Pipeline whose scoped table also applies.
        tool_flags: Top-level flags that dispatch one tool
            (``--docs``).

    Returns:
        Tokens to place before ``arguments``.

    """
    folded_tool_flags: frozenset[str] = frozenset(
        normalized_option(argument=flag) for flag in tool_flags
    )
    folded_info: frozenset[str] = frozenset(
        normalized_option(argument=flag) for flag in Constants.info_flags
    )
    folded_select: frozenset[str] = frozenset(
        normalized_option(argument=flag) for flag in Constants.select_flags
    )
    first: str = arguments[0] if arguments else "-"
    if not first.startswith("-") or (
        normalized_option(argument=first) in folded_tool_flags
    ):
        return ()
    if any(
        normalized_option(argument=item) in folded_info for item in arguments
    ):
        return ()
    values: dict[str, JsonValue] = {
        key: value
        for key, value in stacked(files=files, path=()).items()
        if key in Constants.orchestrator_keys
    }
    values = _resolved_paths(files=files, path=(), values=values)
    if pipeline is not None:
        scoped: dict[str, JsonValue] = _resolved_paths(
            files=files,
            path=("pipeline", pipeline),
            values=stacked(files=files, path=("pipeline", pipeline)),
        )
        values.update(scoped)
    selected: bool = any(
        normalized_option(argument=item) in folded_select for item in arguments
    )
    if selected:
        for key in ("entrypoint", "server", "url"):
            _ = values.pop(key, None)
    name: str = str(object=files[0].path) if files else "<config>"
    return tuple(
        render(
            values=values,
            parser=parser,
            source=f"{name}: [tool.exactus]",
            strict=False,
        ),
    )


def tool_parser(*, module: str) -> ArgumentParser:
    """Build a tool's parser from its module name.

    Prefers the tool's sibling ``arguments`` module so configuration
    discovery never imports heavyweight runtimes such as browsers or
    packaged analyzers; falls back to the given module when no
    ``arguments`` sibling exports ``create_parser``.

    Args:
        module: Full dotted module name such as
            ``exactus.tools.docs.main``.

    Returns:
        The tool's argument parser.

    Raises:
        ModuleNotFoundError: When the tool module itself cannot be
            imported.

    """
    package: str = module.rpartition(".")[0]
    arguments_module: str = f"{package}.arguments" if package else ""
    loaded: ModuleType
    try:
        loaded = (
            import_module(name=arguments_module)
            if arguments_module
            else import_module(name=module)
        )
    except ModuleNotFoundError as error:
        if error.name != arguments_module:
            raise
        loaded = import_module(name=module)
    if not callable(getattr(loaded, "create_parser", None)):
        loaded = import_module(name=module)
    factory: Callable[[], ArgumentParser] = cast(
        typ="Callable[[], ArgumentParser]",
        val=getattr(loaded, "create_parser", None),
    )
    return factory()


def resolve_arguments(
    *,
    tool: str,
    parser: ArgumentParser,
    arguments: Sequence[str] | None,
) -> tuple[str, ...]:
    """Prefix a standalone tool's arguments with its configuration.

    Under ``check`` (``EXACTUS_ORCHESTRATED=1``) the orchestrator has already
    applied the configuration, so arguments pass through unchanged.

    Args:
        tool: Canonical tool identifier.
        parser: The tool's parser; also reports configuration errors.
        arguments: Tokens to parse, or ``None`` for ``sys.argv``.

    Returns:
        Configuration tokens followed by the given arguments.

    """
    given: tuple[str, ...] = (
        tuple(sys_argv[1:]) if arguments is None else tuple(arguments)
    )
    if environ.get(Constants.orchestrated_variable) == "1":
        return mark(tokens=given)
    environ["EXACTUS_EXPLICIT_ARGUMENTS"] = dumps(obj=given)
    start: Path = Path.cwd()
    for item in given:
        if not item.startswith("-") and Path(item).is_dir():
            start = Path(item)
            break
    try:
        files: tuple[ConfigFile, ...] = discovery_from_environment(start=start)
        directory: Path = reports_directory(files=files)
        anchor: Path = reports_anchor(files=files, start=start)
        environ["EXACTUS_REPORTS_ROOT"] = str(
            object=(anchor / directory).resolve(),
        )
        default_output: Path | None = parser.get_default(dest="output_dir")
        if isinstance(default_output, Path) and default_output.parts[:1] == (
            "EXACTUS_RESULTS",
        ):
            parser.set_defaults(
                output_dir=(anchor / directory).joinpath(
                    *default_output.parts[1:],
                ),
            )
        configured: tuple[str, ...] = argv_for(
            files=files,
            tool=tool,
            parser=parser,
            standalone=True,
        )
        if (
            directory != Path("EXACTUS_RESULTS")
            and _action(parser=parser, key="exclude") is not None
        ):
            configured = (
                *configured,
                "--exclude",
                directory.as_posix(),
                "--exclude",
                f"{directory.as_posix()}/**",
            )
    except ConfigError as exc:
        parser.error(message=str(object=exc))
    return mark(tokens=(*configured, *given))


def validate_nested(
    *,
    root: Path,
    files: tuple[ConfigFile, ...],
    parsers: dict[str, ArgumentParser],
    pipelines: Collection[str],
) -> None:
    """Validate encountered owned nested tables before starting tool workers.

    Args:
        root: Immutable run root.
        files: Already discovered run-level carriers.
        parsers: Known tool grammars.
        pipelines: Known pipeline identifiers.

    """
    validate(files=files, parsers=parsers, pipelines=pipelines)
    if environ.get(Constants.environment_variable):
        return
    raw_excludes: JsonValue = stacked(files=files, path=()).get("exclude", [])
    excludes: tuple[str, ...] = (
        tuple(value for value in raw_excludes if isinstance(value, str))
        if isinstance(raw_excludes, list)
        else (raw_excludes,)
        if isinstance(raw_excludes, str)
        else ()
    )
    patterns: PathFilters = PathFilters(excludes=excludes)
    reports: Path = reports_directory(files=files)
    excluded: frozenset[str] = default_excluded_dirs(
        root=root,
        reports_dir=reports,
    )
    for directory, dirnames, filenames in root.walk():
        dirnames[:] = [
            name
            for name in dirnames
            if not name.startswith(".")
            and name not in excluded
            and patterns.matches(
                relative=f"{(directory / name).relative_to(root).as_posix()}/",
            )
        ]
        if directory == root or Constants.file_name not in filenames:
            continue
        item: ConfigFile | None = _load(path=directory / Constants.file_name)
        if item is not None:
            validate(files=(item,), parsers=parsers, pipelines=pipelines)


def files_for_path(*, path: Path, boundary: Path) -> tuple[ConfigFile, ...]:
    """Discover a path's configuration without crossing the run boundary.

    Args:
        path: Existing file or directory within the run root.
        boundary: Run-global project root.

    Returns:
        Configuration carriers, nearest first.

    Raises:
        ConfigError: If the path is missing or resolves outside the root.

    """
    resolved: Path = path.resolve()
    root: Path = boundary.resolve()
    if not resolved.exists() or not resolved.is_relative_to(root):
        msg: str = f"{path}: expected an existing path inside {root}"
        raise ConfigError(msg)
    return discover(
        start=resolved if resolved.is_dir() else resolved.parent,
        boundary=root,
    )


def stacked_provenance(
    *,
    files: tuple[ConfigFile, ...],
    path: tuple[str, ...],
) -> dict[str, Path]:
    """Identify the nearest declaration contributing each merged option.

    Args:
        files: Configuration carriers, nearest first.
        path: Table path below tool.exactus.

    Returns:
        Normalized option names mapped to their nearest declaring file.

    """
    return {
        key: item.path
        for item in reversed(files)
        for key in stacked(files=(item,), path=path)
    }


class ConfigResolver:
    """Own directory configuration and native-carrier caches for one run."""

    def __init__(self, *, root: Path) -> None:
        """Bind discovery and ownership to an immutable run root.

        Args:
            root: Existing analysis root.

        """
        self.root: Path = root.resolve()
        self._files: dict[Path, tuple[ConfigFile, ...]] = {}
        self._native: dict[tuple[Path, tuple[str, ...]], Path | None] = {}
        self._parsers: dict[str, ArgumentParser] = {}
        self._validated: set[tuple[Path, str]] = set()
        self._documents: dict[Path, dict[str, JsonValue]] = {}
        self._native_filters: dict[tuple[Path, str], PathFilters] = {}

    def files(self, *, path: Path) -> tuple[ConfigFile, ...]:
        """Resolve and memoize a directory's exactus configuration chain.

        Args:
            path: Existing candidate within the run root.

        Returns:
            Carriers in nearest-first order.

        Raises:
            ConfigError: When the path is missing or outside the run root.

        """
        resolved: Path = path.resolve()
        if not resolved.exists() or not resolved.is_relative_to(self.root):
            msg: str = f"{path}: expected an existing path inside {self.root}"
            raise ConfigError(msg)
        directory: Path = resolved if resolved.is_dir() else resolved.parent
        if directory not in self._files:
            override: str = environ.get(Constants.environment_variable, "")
            if override:
                self._files[directory] = discover(
                    start=directory,
                    boundary=self.root,
                    disabled=override == Constants.disabled,
                    explicit=None
                    if override == Constants.disabled
                    else Path(override),
                )
            else:
                carrier: Path = directory / Constants.file_name
                item: ConfigFile | None = (
                    _load(path=carrier) if carrier.is_file() else None
                )
                parents: tuple[ConfigFile, ...] = (
                    self.files(path=directory.parent)
                    if directory != self.root
                    and (item is None or item.table.get("root") is not True)
                    else ()
                )
                self._files[directory] = (
                    *((item,) if item is not None else ()),
                    *parents,
                )
        return self._files[directory]

    def stacked(
        self,
        *,
        path: Path,
        table: tuple[str, ...] = (),
    ) -> dict[str, JsonValue]:
        """Merge the selected path's tool table.

        Args:
            path: Existing candidate within the root.
            table: Table components below tool.exactus.

        Returns:
            Merged non-table options.

        """
        return stacked(files=self.files(path=path), path=table)

    def argv_signature(
        self,
        *,
        tool: str,
        path: Path,
        parser: ArgumentParser | None = None,
    ) -> tuple[str, ...]:
        """Render path-specific options while retaining global ownership.

        Args:
            tool: Canonical tool identifier.
            path: Candidate whose ancestor tables apply.
            parser: Tool parser, or the standard tool module's parser.

        Returns:
            Deterministic per-path option tokens, excluding run controls.

        """
        if parser is None:
            if tool not in self._parsers:
                self._parsers[tool] = tool_parser(
                    module=f"exactus.tools.{tool}.main",
                )
            parser = self._parsers[tool]
        global_keys: frozenset[str] = Constants.orchestrator_keys | {
            "fix",
            "dry",
            "workers",
            "jobs",
            "install-tools",
            "no-install-tools",
            "output-dir",
            "collect-files",
        }
        values: dict[str, JsonValue] = {
            **self.stacked(path=path),
            **self.stacked(path=path, table=(tool,)),
        }
        return tuple(
            render(
                values={
                    k: v for k, v in values.items() if k not in global_keys
                },
                parser=parser,
                source=str(object=path),
                strict=False,
            ),
        )

    def options(self, *, path: Path, tool: str) -> dict[str, JsonValue]:
        """Resolve nested per-file options without overriding explicit CLI.

        Args:
            path: Source candidate.
            tool: Canonical tool identifier.

        Returns:
            Nested common/tool values excluding global ownership controls.

        """
        nested: tuple[ConfigFile, ...] = tuple(
            item
            for item in self.files(path=path)
            if item.path.parent != self.root
        )
        if tool not in self._parsers:
            self._parsers[tool] = tool_parser(
                module=f"exactus.tools.{tool}.main",
            )
        for item in nested:
            identity: tuple[Path, str] = (item.path, tool)
            if identity not in self._validated:
                render(
                    values=stacked(files=(item,), path=(tool,)),
                    parser=self._parsers[tool],
                    source=str(object=item.path),
                    strict=True,
                )
                self._validated.add(identity)
        values: dict[str, JsonValue] = {
            **stacked(files=nested, path=()),
            **stacked(files=nested, path=(tool,)),
        }
        try:
            explicit: JsonValue = json_loads(
                s=environ.get("EXACTUS_EXPLICIT_ARGUMENTS", "[]"),
            )
        except ValueError:
            explicit = []
        protected: set[str] = (
            {
                normalized_option(argument=token)
                .removeprefix("--")
                .replace("_", "-")
                .split(sep="=", maxsplit=1)[0]
                for token in explicit
                if isinstance(token, str) and token.startswith("--")
            }
            if isinstance(explicit, list)
            else set()
        )
        global_keys: frozenset[str] = Constants.orchestrator_keys | {
            "fix",
            "dry",
            "workers",
            "jobs",
            "install-tools",
            "no-install-tools",
            "output-dir",
            "collect-files",
            "no-fix",
            "unsafe-fixes",
        }
        return {
            key: value
            for key, value in values.items()
            if key not in global_keys
            and key not in protected
            and f"no-{key}" not in protected
            and key.removeprefix("no-") not in protected
        }

    def boolean(
        self,
        *,
        path: Path,
        tool: str,
        name: str,
        default: bool,
    ) -> bool:
        """Read a validated per-file boolean option.

        Args:
            path: Source candidate.
            tool: Tool table.
            name: Normalized option key.
            default: Effective run-level fallback.

        Returns:
            Nested boolean or the supplied fallback.

        Raises:
            ConfigError: If a nested declaration is not boolean.

        """
        value: JsonValue = self.options(path=path, tool=tool).get(
            name,
            default,
        )
        if not isinstance(value, bool):
            msg: str = f"{path}: {name}: expected true or false"
            raise ConfigError(msg)
        return value

    def filters(self, *, path: Path, tool: str | None = None) -> PathFilters:
        """Anchor applicable selection patterns at their declaring folders.

        Args:
            path: Existing candidate within the root.
            tool: Optional tool table whose filters also apply.

        Returns:
            Root-relative include/exclude unions for this candidate.

        """
        values: dict[str, list[str]] = {"include": [], "exclude": []}
        for item in reversed(self.files(path=path)):
            prefix: str = (
                item.path.parent.relative_to(self.root).as_posix()
                if item.path.parent.is_relative_to(self.root)
                else "."
            )
            for table in ((), (tool,)) if tool is not None else ((),):
                declared: dict[str, JsonValue] = stacked(
                    files=(item,),
                    path=table,
                )
                for key, collected in values.items():
                    raw: JsonValue | None = declared.get(key)
                    patterns: list[JsonValue] = (
                        raw if isinstance(raw, list) else [raw]
                    )
                    collected.extend(
                        f"{prefix}/{pattern}" if prefix != "." else pattern
                        for pattern in patterns
                        if isinstance(pattern, str)
                    )
        return PathFilters(
            includes=tuple(values["include"]),
            excludes=tuple(values["exclude"]),
        )

    def native_filters(self, *, path: Path, tool: str) -> PathFilters:
        """Resolve native selection tables relative to their declaring carrier.

        Args:
            path: Existing source candidate.
            tool: Analyzer name.

        Returns:
            Scoped native include/exclude unions.

        """
        directory: Path = path.resolve().parent
        key: tuple[Path, str] = (directory, tool)
        if key in self._native_filters:
            return self._native_filters[key]
        patterns: dict[str, list[str]] = {"include": [], "exclude": []}
        native: str = "ruff" if tool in {"ruff", "ruff_docs"} else tool
        for parent in (directory, *directory.parents):
            carrier: Path | None = parent / "pyproject.toml"
            document: dict[str, JsonValue] = {}
            if carrier and carrier.is_file():
                if carrier not in self._documents:
                    self._documents[carrier] = loads(
                        carrier.read_text(encoding="utf-8"),
                    )
                document = self._documents[carrier]
            tables: tuple[dict[str, JsonValue], ...] = (
                _sub_table(
                    table=document,
                    path=("tool", "audit_linters_json"),
                ),
                _sub_table(
                    table=document,
                    path=("tool", "audit_linters_json", tool),
                ),
                _sub_table(table=document, path=("tool", native)),
            )
            prefix: str = parent.relative_to(self.root).as_posix()
            for table in tables:
                self._scope_native_patterns(
                    table=table,
                    prefix=prefix,
                    patterns=patterns,
                )
            if (
                parent == self.root
                or _sub_table(table=document, path=("tool", "exactus")).get(
                    "root",
                )
                is True
            ):
                break
        if native == "ruff":
            carrier = self.nearest_native(path=path, sections=("ruff",))
            if carrier is not None and carrier.name in {
                "ruff.toml",
                ".ruff.toml",
            }:
                if carrier not in self._documents:
                    self._documents[carrier] = loads(
                        carrier.read_text(encoding="utf-8"),
                    )
                self._scope_native_patterns(
                    table=self._documents[carrier],
                    prefix=carrier.parent.relative_to(self.root).as_posix(),
                    patterns=patterns,
                )
        result: PathFilters = PathFilters(
            includes=tuple(patterns["include"]),
            excludes=tuple(patterns["exclude"]),
        )
        self._native_filters[key] = result
        return result

    def nearest_native(
        self,
        *,
        path: Path,
        sections: tuple[str, ...],
    ) -> Path | None:
        """Find the nearest native config containing a requested tool table.

        Args:
            path: Existing source candidate.
            sections: Tool table names or explicit native config filenames.

        Returns:
            Nearest qualifying carrier, or None within this root.

        Raises:
            ConfigError: If a discovered pyproject is invalid TOML.

        """
        _ = self.files(path=path)
        directory: Path = path.resolve()
        if not directory.is_dir():
            directory = directory.parent
        key: tuple[Path, tuple[str, ...]] = (directory, sections)
        if key in self._native:
            return self._native[key]
        names: dict[str, tuple[str, ...]] = {
            "ruff": (".ruff.toml", "ruff.toml"),
            "basedpyright": ("basedpyrightconfig.json", "pyrightconfig.json"),
            "pyright": ("pyrightconfig.json",),
            "pyrefly": ("pyrefly.toml",),
            "typescript": ("jsconfig.json", "tsconfig.json"),
        }
        result: Path | None = None
        for parent in (directory, *directory.parents):
            candidates: tuple[str, ...] = tuple(
                name
                for section in sections
                for name in names.get(section, (section,))
            )
            result = next(
                (
                    parent / name
                    for name in candidates
                    if (parent / name).is_file()
                ),
                None,
            )
            if result is not None:
                break
            result, stopped = self._native_pyproject(
                parent=parent,
                sections=sections,
            )
            if result is not None or stopped or parent == self.root:
                break
        self._native[key] = result
        return result

    @staticmethod
    def _scope_native_patterns(
        *,
        table: dict[str, JsonValue],
        prefix: str,
        patterns: dict[str, list[str]],
    ) -> None:
        """Anchor native selection patterns in the declaring directory.

        Args:
            table: Native analyzer configuration.
            prefix: Root-relative declaring directory.
            patterns: Owned accumulating selection lists.

        """
        for name, values in patterns.items():
            for option in (name, f"extend-{name}", f"project-{name}s"):
                raw: JsonValue = table.get(option, [])
                selected: list[JsonValue] = (
                    [raw]
                    if isinstance(raw, str)
                    else raw
                    if isinstance(raw, list)
                    else []
                )
                values.extend(
                    f"{prefix}/{value}" if prefix != "." else value
                    for value in selected
                    if isinstance(value, str)
                )

    def _native_document(
        self,
        *,
        pyproject: Path,
    ) -> dict[str, JsonValue]:
        """Load and cache one ``pyproject.toml`` document.

        Args:
            pyproject: Configuration file to read.

        Returns:
            Decoded TOML document.

        Raises:
            ConfigError: If the file is invalid TOML.

        """
        if pyproject not in self._documents:
            try:
                self._documents[pyproject] = loads(
                    pyproject.read_text(encoding="utf-8"),
                )
            except TOMLDecodeError as error:
                msg: str = f"{pyproject}: invalid TOML: {error}"
                raise ConfigError(msg) from error
        return self._documents[pyproject]

    def _native_pyproject(
        self,
        *,
        parent: Path,
        sections: tuple[str, ...],
    ) -> tuple[Path | None, bool]:
        """Inspect a cached native table and its optional inheritance boundary.

        Args:
            parent: Current directory inside the run root.
            sections: Requested native tool names.

        Returns:
            Matching carrier and whether nested Exactus inheritance stops.

        Raises:
            ConfigError: When the native carrier is invalid TOML.

        """
        pyproject: Path = parent / "pyproject.toml"
        if not pyproject.is_file():
            return None, False
        try:
            if pyproject not in self._documents:
                self._documents[pyproject] = loads(
                    pyproject.read_text(encoding="utf-8"),
                )
            document: dict[str, JsonValue] = self._documents[pyproject]
        except TOMLDecodeError as error:
            msg: str = f"{pyproject}: invalid TOML: {error}"
            raise ConfigError(msg) from error
        tools: dict[str, JsonValue] = _sub_table(
            table=document,
            path=("tool",),
        )
        matched: bool = any(
            section in tools
            or (section == "basedpyright" and "pyright" in tools)
            for section in sections
        )
        stopped: bool = (
            _sub_table(table=tools, path=("exactus",)).get("root") is True
        )
        return pyproject if matched else None, stopped


@dataclass(frozen=True, slots=True)
class OptionProvenance:
    """Describe one resolved option and its winning declaration.

    Attributes:
        name: Parser destination.
        value: Display-compatible resolved value.
        layer: Winning precedence layer.
        source: Declaring configuration carrier, if any.

    """

    name: str
    value: str
    layer: str
    source: Path | None


@dataclass(frozen=True, slots=True)
class ToolConfigReport:
    """Expose one tool's resolved options.

    Attributes:
        identifier: Canonical tool identifier.
        options: Resolved options with provenance.

    """

    identifier: str
    options: tuple[OptionProvenance, ...]


@dataclass(frozen=True, slots=True)
class ShowConfigReport:
    """Represent the versioned path-scoped configuration contract.

    Attributes:
        path: Selected file or directory.
        anchor: Directory discovery starts at.
        root: Run-global ownership root.
        files: Nearest-first exactus carriers.
        pipeline: Optional selected pipeline.
        tools: Resolved tool option reports.
        reports_dir: Run-global report destination.

    """

    path: Path
    anchor: Path
    root: Path
    files: tuple[Path, ...]
    pipeline: str | None
    tools: tuple[ToolConfigReport, ...]
    reports_dir: Path

    def to_json(self) -> dict[str, JsonValue]:
        """Serialize schema version one without platform-specific objects.

        Returns:
            JSON-compatible report data.

        """
        return {
            "schema_version": 1,
            "path": str(object=self.path),
            "anchor": str(object=self.anchor),
            "root": str(object=self.root),
            "files": [str(object=p) for p in self.files],
            "pipeline": self.pipeline,
            "reports_dir": str(object=self.reports_dir),
            "tools": [
                {
                    "identifier": tool.identifier,
                    "options": [
                        {
                            "name": option.name,
                            "value": option.value,
                            "layer": option.layer,
                            "source": str(object=option.source)
                            if option.source is not None
                            else None,
                        }
                        for option in tool.options
                    ],
                }
                for tool in self.tools
            ],
        }


def show_config(
    *,
    root: Path,
    path: Path | None = None,
    tools: tuple[EffectiveRequest, ...] = (),
    pipeline: str | None = None,
    cli: tuple[str, ...] = (),
) -> ShowConfigReport:
    """Resolve one path through the same model used by the CLI display.

    Args:
        root: Run-global project root.
        path: Selected existing path, defaulting to root.
        tools: Tools and optional presets to report.
        pipeline: Selected pipeline.
        cli: Explicit tool arguments with highest precedence.

    Returns:
        Versioned structured report retaining option provenance.

    """
    selected: Path = (path or root).resolve()
    resolver: ConfigResolver = ConfigResolver(root=root)
    files: tuple[ConfigFile, ...] = resolver.files(path=selected)
    reports: list[ToolConfigReport] = []
    for request in tools:
        paths: dict[str, tuple[str, ...]] = {
            "common": (),
            "tool": (request.tool,),
            "pipeline": ("pipeline", pipeline or "", request.tool),
        }
        options: list[OptionProvenance] = []
        for name, value, layer in effective(
            files=files,
            request=EffectiveRequest(
                tool=request.tool,
                module=request.module,
                preset=request.preset,
                cli=(*request.cli, *cli),
                pipeline=pipeline or request.pipeline,
            ),
        ):
            origins: dict[str, Path] = (
                stacked_provenance(
                    files=files,
                    path=paths.get(layer, ()),
                )
                if layer in paths
                else {}
            )
            parser: ArgumentParser = tool_parser(module=request.module)
            source: Path | None = next(
                (
                    origin
                    for key, origin in origins.items()
                    if (action := _action(parser=parser, key=key)) is not None
                    and action.dest == name
                ),
                None,
            )
            options.append(
                OptionProvenance(
                    name=name,
                    value=value,
                    layer=layer,
                    source=source,
                ),
            )
        reports.append(
            ToolConfigReport(
                identifier=request.tool,
                options=tuple(options),
            ),
        )
    global_files: tuple[ConfigFile, ...] = resolver.files(path=root)
    return ShowConfigReport(
        path=selected,
        anchor=selected if selected.is_dir() else selected.parent,
        root=root.resolve(),
        files=tuple(item.path for item in files),
        pipeline=pipeline,
        tools=tuple(reports),
        reports_dir=reports_anchor(files=global_files, start=root)
        / reports_directory(files=global_files),
    )
