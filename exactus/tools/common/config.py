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
from os import environ
from pathlib import Path
from sys import argv as sys_argv
from tomllib import TOMLDecodeError, loads
from typing import TYPE_CHECKING, Final, cast, final

from exactus.packages.argument_parser import normalized_option
from exactus.tools.common.collect_files import mark

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
        ("-h", "--help", "--list-tools", "--list-pipelines", "--show-config"),
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
    project's configuration.

    Args:
        start: Directory the upward walk begins in.

    Returns:
        Loaded files, nearest first.

    """
    value: str = environ.get(Constants.environment_variable, "")
    if value == Constants.disabled:
        return ()
    root: str | None = environ.get("EXACTUS_ROOT")
    return discover(
        start=start,
        explicit=Path(value) if value else None,
        boundary=Path(root) if root else None,
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
