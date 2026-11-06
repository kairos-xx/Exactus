# Copyright (c) 2026
"""Load Exactus MCP command defaults from project configuration."""

from __future__ import annotations

from dataclasses import dataclass
from json import JSONDecodeError
from json import loads as load_json
from os import name as os_name
from pathlib import Path
from tomllib import TOMLDecodeError
from tomllib import loads as load_toml
from typing import TYPE_CHECKING, Final, cast, final

if TYPE_CHECKING:
    from exactus.packages.server.json_types import JsonValue
type ArgumentDefault = bool | float | int | str | Path | tuple[str, ...]
type DefaultSchema = tuple[
    frozenset[str],
    frozenset[str],
    frozenset[str],
    frozenset[str],
    frozenset[str],
    frozenset[str],
]


@final
class Constants:
    """Group module-level constants.

    Attributes:
        service_boolean_keys: Grouped module constant.
        service_float_keys: Grouped module constant.
        service_integer_keys: Grouped module constant.
        service_path_keys: Grouped module constant.
        service_string_keys: Grouped module constant.
        service_toml_string_keys: Grouped module constant.
        wake_boolean_keys: Grouped module constant.
        wake_float_keys: Grouped module constant.
        wake_path_keys: Grouped module constant.
        wake_sequence_keys: Grouped module constant.
        wake_string_keys: Grouped module constant.
        wake_toml_path_keys: Grouped module constant.
        wake_toml_string_keys: Grouped module constant.

    """

    service_boolean_keys: Final[frozenset[str]] = frozenset(
        ("menu-bar", "ngrok"),
    )
    service_float_keys: Final[frozenset[str]] = frozenset(
        ("check-timeout", "mantledb-timeout", "tunnel-timeout"),
    )
    service_integer_keys: Final[frozenset[str]] = frozenset(("port",))
    service_path_keys: Final[frozenset[str]] = frozenset(("root",))
    service_string_keys: Final[frozenset[str]] = frozenset(
        (
            "access-token",
            "host",
            "log-level",
            "mantledb-namespace",
            "mantledb-path",
            "ngrok-command",
            "ngrok-endpoint",
            "ngrok-url",
        ),
    )
    service_toml_string_keys: Final[frozenset[str]] = (
        service_string_keys.difference(("access-token", "mantledb-namespace"))
    )
    wake_boolean_keys: Final[frozenset[str]] = frozenset(
        ("keep-service-running",),
    )
    wake_float_keys: Final[frozenset[str]] = frozenset(
        (
            "discovery-timeout",
            "maximum-age",
            "poll-interval",
            "request-timeout",
            "retry-maximum",
        ),
    )
    wake_path_keys: Final[frozenset[str]] = frozenset(
        ("secrets-file", "state"),
    )
    wake_sequence_keys: Final[frozenset[str]] = frozenset(("service-command",))
    wake_string_keys: Final[frozenset[str]] = frozenset(
        (
            "command-path",
            "label",
            "mantledb-namespace",
            "mcp-path",
            "response-path",
            "url-path",
            "url-pattern",
            "access-token",
            "wake-key",
        ),
    )
    wake_toml_path_keys: Final[frozenset[str]] = frozenset(("state",))
    wake_toml_string_keys: Final[frozenset[str]] = wake_string_keys.difference(
        ("access-token", "mantledb-namespace", "wake-key"),
    )


@dataclass(frozen=True, slots=True)
class ConfigSelection:
    """Describe a removed ``--config`` option.

    Attributes:
        path: Explicit JSON configuration path, when supplied.
        list_only: Whether bare ``--config`` requested effective settings.
        arguments: Remaining command-line arguments.

    """

    path: Path | None
    list_only: bool
    arguments: tuple[str, ...]


def _config_occurrence(
    *,
    values: tuple[str, ...],
    index: int,
) -> tuple[Path | None, bool, int]:
    """Parse one config option occurrence.

    Args:
        values: Complete raw argument vector.
        index: Current configuration-option index.

    Returns:
        Path, list-only flag, and final consumed index.

    Raises:
        ValueError: If the option has an ambiguous or empty value.

    """
    value: str = values[index]
    if value.startswith("--config="):
        path_value: str = value.partition("=")[2]
        if not path_value:
            msg: str = "--config= requires a JSON file path"
            raise ValueError(msg)
        return (Path(path_value).expanduser().resolve(), False, index)
    if index + 1 == len(values):
        return (None, True, index)
    candidate: str = values[index + 1]
    if candidate.startswith("-"):
        msg = (
            "bare --config must be the final argument; "
            "use --config=FILE to load JSON"
        )
        raise ValueError(msg)
    return (Path(candidate).expanduser().resolve(), False, index + 1)


def select_config(*, values: tuple[str, ...]) -> ConfigSelection:
    """Remove and classify the optional ``--config`` argument.

    Bare ``--config`` is intentionally accepted only as the final argument.
    This keeps JSON paths unambiguous while reserving the bare form for the
    requested read-only effective-configuration listing.

    Args:
        values: Raw command-line arguments.

    Returns:
        Selected path/list operation and all non-configuration arguments.

    Raises:
        ValueError: If the option is repeated or lacks an unambiguous value.

    """
    selected_path: Path | None = None
    list_only: bool = False
    remaining: list[str] = []
    index: int = 0
    while index < len(values):
        value: str = values[index]
        if value == "--":
            remaining.extend(values[index:])
            break
        if value != "--config" and (not value.startswith("--config=")):
            remaining.append(value)
            index += 1
            continue
        candidate_path: Path | None
        candidate_list: bool
        candidate_path, candidate_list, index = _config_occurrence(
            values=values,
            index=index,
        )
        if candidate_path is not None:
            if selected_path is not None:
                msg: str = "only one --config JSON file may be supplied"
                raise ValueError(msg)
            selected_path = candidate_path
        if candidate_list:
            if list_only:
                msg = "bare --config may be supplied only once"
                raise ValueError(msg)
            list_only = True
        index += 1
    return ConfigSelection(
        path=selected_path,
        list_only=list_only,
        arguments=tuple(remaining),
    )


def service_defaults(*, root: Path) -> dict[str, ArgumentDefault]:
    """Return validated `[tool.exactus.mcp]` argument defaults.

    Args:
        root: Project root containing the optional ``pyproject.toml``.

    Returns:
        Parser-default mapping with command-line spelling normalized.

    """
    section: dict[str, JsonValue] = _section(root=root, nested=False)
    return _validated_defaults(
        section=section,
        root=root,
        schema=(
            Constants.service_boolean_keys,
            Constants.service_float_keys,
            Constants.service_integer_keys,
            Constants.service_path_keys,
            frozenset(),
            Constants.service_toml_string_keys,
        ),
    )


def service_json_defaults(*, path: Path) -> dict[str, ArgumentDefault]:
    """Return service defaults from a private JSON configuration file.

    Args:
        path: JSON file containing a flat object or ``service`` object.

    Returns:
        Validated parser defaults, including explicitly supplied secrets.

    """
    section: dict[str, JsonValue] = _json_section(path=path, name="service")
    _require_private_secret_file(path=path, section=section)
    return _validated_defaults(
        section=section,
        root=path.parent,
        schema=(
            Constants.service_boolean_keys,
            Constants.service_float_keys,
            Constants.service_integer_keys,
            Constants.service_path_keys,
            frozenset(),
            Constants.service_string_keys,
        ),
    )


def wake_json_defaults(*, path: Path) -> dict[str, ArgumentDefault]:
    """Return watcher defaults from a private JSON configuration file.

    Args:
        path: JSON file containing a flat object or ``wakeup`` object.

    Returns:
        Validated parser defaults, including explicitly supplied secrets.

    """
    section: dict[str, JsonValue] = _json_section(path=path, name="wakeup")
    _require_private_secret_file(path=path, section=section)
    return _validated_defaults(
        section=section,
        root=path.parent,
        schema=(
            Constants.wake_boolean_keys,
            Constants.wake_float_keys,
            frozenset(),
            Constants.wake_path_keys,
            Constants.wake_sequence_keys,
            Constants.wake_string_keys,
        ),
    )


def wake_defaults(*, root: Path) -> dict[str, ArgumentDefault]:
    """Return validated `[tool.exactus.mcp.wakeup]` argument defaults.

    Args:
        root: Project root containing the optional ``pyproject.toml``.

    Returns:
        Parser-default mapping with command-line spelling normalized.

    """
    section: dict[str, JsonValue] = _section(root=root, nested=True)
    return _validated_defaults(
        section=section,
        root=root,
        schema=(
            Constants.wake_boolean_keys,
            Constants.wake_float_keys,
            frozenset(),
            Constants.wake_toml_path_keys,
            Constants.wake_sequence_keys,
            Constants.wake_toml_string_keys,
        ),
    )


def _section(*, root: Path, nested: bool) -> dict[str, JsonValue]:
    """Read one Exactus MCP configuration table.

    Args:
        root: Project root containing the optional TOML document.
        nested: Whether to select the nested watcher table.

    Returns:
        Selected table, or an empty mapping when the file/table is absent.

    Raises:
        TypeError: If the selected table has the wrong shape.
        ValueError: If the TOML document is invalid.

    """
    path: Path = root / "pyproject.toml"
    if not path.is_file():
        return {}
    try:
        document: JsonValue = cast(
            typ="JsonValue",
            val=load_toml(path.read_text(encoding="utf-8")),
        )
    except TOMLDecodeError as exc:
        msg: str = f"invalid MCP project configuration: {exc}"
        raise ValueError(msg) from exc
    value: JsonValue | None = document
    key: str
    keys: tuple[str, ...] = (
        ("tool", "exactus", "mcp", "wakeup")
        if nested
        else ("tool", "exactus", "mcp")
    )
    for key in keys:
        if not isinstance(value, dict):
            return {}
        value = value.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        msg = f"[{'/'.join(keys)}] must be a TOML table"
        raise TypeError(msg)
    return value


def _json_section(*, path: Path, name: str) -> dict[str, JsonValue]:
    """Read a flat or named JSON configuration section.

    Args:
        path: JSON configuration path.
        name: Named top-level section accepted for shared files.

    Returns:
        Selected configuration object.

    Raises:
        TypeError: If the JSON document or section has the wrong shape.
        ValueError: If the file is missing or invalid.

    """
    try:
        document: JsonValue = cast(
            typ="JsonValue",
            val=load_json(s=path.read_text(encoding="utf-8")),
        )
    except (JSONDecodeError, OSError) as exc:
        msg: str = f"unable to load Exactus MCP JSON config {path}: {exc}"
        raise ValueError(msg) from exc
    if not isinstance(document, dict):
        msg = "Exactus MCP JSON config must contain an object"
        raise TypeError(msg)
    named: JsonValue | None = document.get(name)
    if named is None:
        return document
    if not isinstance(named, dict):
        msg = f"Exactus MCP JSON config section '{name}' must be an object"
        raise TypeError(msg)
    return named


def _require_private_secret_file(
    *,
    path: Path,
    section: dict[str, JsonValue],
) -> None:
    """Reject POSIX JSON files that expose included secrets.

    Args:
        path: Loaded JSON configuration path.
        section: Selected configuration object.

    Raises:
        ValueError: If a secret-bearing POSIX file has group/world bits.

    """
    carries_secret: bool = any(
        isinstance(section.get(key), str) and bool(section.get(key))
        for key in ("access-token", "access_token", "wake-key", "wake_key")
    )
    if os_name == "posix" and carries_secret and path.stat().st_mode & 63:
        msg: str = f"secret-bearing JSON config must be mode 0600: {path}"
        raise ValueError(msg)


def _validated_defaults(
    *,
    section: dict[str, JsonValue],
    root: Path,
    schema: DefaultSchema,
) -> dict[str, ArgumentDefault]:
    """Validate one table and normalize its keys for ``argparse``.

    Args:
        section: Raw TOML table.
        root: Project root used to resolve relative paths.
        schema: Boolean, float, integer, path, sequence, and string keys.

    Returns:
        Validated defaults keyed by underscore-form destination names.

    Raises:
        ValueError: If a supported key has an invalid value or a key is
            unknown.

    """
    boolean_keys: frozenset[str]
    float_keys: frozenset[str]
    integer_keys: frozenset[str]
    path_keys: frozenset[str]
    sequence_keys: frozenset[str]
    string_keys: frozenset[str]
    (
        boolean_keys,
        float_keys,
        integer_keys,
        path_keys,
        sequence_keys,
        string_keys,
    ) = schema
    allowed: frozenset[str] = frozenset(
        member for group in schema for member in group
    )
    defaults: dict[str, ArgumentDefault] = {}
    raw_key: str
    value: JsonValue
    for raw_key, value in section.items():
        key: str = raw_key.replace("_", "-")
        if key == "wakeup" and isinstance(value, dict):
            continue
        if key not in allowed:
            msg: str = f"unknown Exactus MCP setting: {raw_key}"
            raise ValueError(msg)
        normalized: str = key.replace("-", "_")
        if normalized in defaults:
            msg = f"duplicate Exactus MCP setting: {raw_key}"
            raise ValueError(msg)
        if (key in boolean_keys and isinstance(value, bool)) or (
            key in integer_keys
            and isinstance(value, int)
            and (not isinstance(value, bool))
        ):
            defaults[normalized] = value
        elif (
            key in float_keys
            and isinstance(value, (int, float))
            and (not isinstance(value, bool))
        ):
            defaults[normalized] = float(value)
        elif key in string_keys and isinstance(value, str):
            defaults[normalized] = value
        elif key in path_keys and isinstance(value, str):
            path: Path = Path(value)
            defaults[normalized] = path if path.is_absolute() else root / path
        elif (
            key in sequence_keys
            and isinstance(value, list)
            and all(isinstance(item, str) for item in value)
        ):
            defaults[normalized] = tuple(
                item for item in value if isinstance(item, str)
            )
        else:
            msg = f"invalid value for Exactus MCP setting: {key}"
            raise ValueError(msg)
    return defaults
