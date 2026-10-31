# Copyright (c) 2026
"""Validate Exactus MCP project configuration loading."""

from __future__ import annotations

from io import StringIO
from os import name as os_name
from pathlib import Path
from textwrap import dedent

import pytest

from exactus.packages.exactus_mcp import wakeup_cli
from exactus.packages.exactus_mcp.project_config import (
    ConfigSelection,
    select_config,
    service_defaults,
    service_json_defaults,
    wake_defaults,
    wake_json_defaults,
)
from exactus.tests.common.support import expect_equal, expect_in, expect_not_in


def test_service_and_wake_defaults_are_typed(tmp_path: Path) -> None:
    """Supported TOML settings become normalized parser defaults.

    Args:
        tmp_path: Temporary project root.

    """
    configuration: str = dedent(
        text=(
            '    \n    [tool.exactus.mcp]\n    host = "127.0.0.1"\n    port = '
            "6100\n    ngrok = true\n    tunnel-timeout = 12\n    \n    [tool."
            "exactus.mcp.wakeup]\n    keep-service-running = true\n    state ="
            ' ".state/last-id"\n    service-command = ["python", "-m", "servic'
            'e"]\n    '
        ),
    )
    _ = (tmp_path / "pyproject.toml").write_text(
        data=configuration,
        encoding="utf-8",
    )
    expect_equal(
        actual=service_defaults(root=tmp_path),
        expected={
            "host": "127.0.0.1",
            "ngrok": True,
            "port": 6100,
            "tunnel_timeout": 12.0,
        },
    )
    expect_equal(
        actual=wake_defaults(root=tmp_path),
        expected={
            "keep_service_running": True,
            "service_command": ("python", "-m", "service"),
            "state": tmp_path / ".state" / "last-id",
        },
    )


def test_unknown_setting_is_rejected(tmp_path: Path) -> None:
    """A misspelled setting fails instead of silently doing nothing.

    Args:
        tmp_path: Temporary project root.

    """
    _ = (tmp_path / "pyproject.toml").write_text(
        data="[tool.exactus.mcp]\nunknown = true\n",
        encoding="utf-8",
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="unknown Exactus MCP setting",
    ):
        _ = service_defaults(root=tmp_path)


def test_private_json_supports_service_and_wake_secrets(
    tmp_path: Path,
) -> None:
    """A shared private JSON document supplies both command sections.

    Args:
        tmp_path: Temporary configuration directory.

    """
    path: Path = tmp_path / "exactus-mcp.json"
    _ = path.write_text(
        data=(
            dedent(
                text=(
                    '    \n    {\n      "service": {\n        "root": "wor'
                    'kspace",\n        "access_token": "service-secret",\n'
                    '        "mantledb_namespace": "private-namespace"\n  '
                    '    },\n      "wakeup": {\n        "wake-key": "wake-'
                    'secret",\n        "access-token": "service-secret",\n'
                    '        "mantledb-namespace": "private-namespace",\n '
                    '       "secrets-file": "private/watcher.json",\n     '
                    '   "service-command": ["python", "-m", "service"]\n  '
                    "    }\n    }\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    path.chmod(mode=0o600)
    expect_equal(
        actual=service_json_defaults(path=path),
        expected={
            "access_token": "service-secret",
            "mantledb_namespace": "private-namespace",
            "root": tmp_path / "workspace",
        },
    )
    expect_equal(
        actual=wake_json_defaults(path=path),
        expected={
            "access_token": "service-secret",
            "mantledb_namespace": "private-namespace",
            "secrets_file": tmp_path / "private" / "watcher.json",
            "service_command": ("python", "-m", "service"),
            "wake_key": "wake-secret",
        },
    )


@pytest.mark.skipif(
    condition=os_name != "posix",
    reason="POSIX permission bits are unavailable",
)
def test_secret_json_requires_private_posix_permissions(
    tmp_path: Path,
) -> None:
    """Group-readable secret configuration fails before values are used.

    Args:
        tmp_path: Temporary configuration directory.

    """
    path: Path = tmp_path / "unsafe.json"
    _ = path.write_text(data='{"access-token": "exposed"}', encoding="utf-8")
    path.chmod(mode=0o644)
    with pytest.raises(
        expected_exception=ValueError,
        match="must be mode 0600",
    ):
        _ = service_json_defaults(path=path)


def test_toml_rejects_secret_settings(tmp_path: Path) -> None:
    """Project TOML cannot become an accidental plaintext secret store.

    Args:
        tmp_path: Temporary project root.

    """
    _ = (tmp_path / "pyproject.toml").write_text(
        data=('[tool.exactus.mcp.wakeup]\nwake-key = "must-not-live-here"\n'),
        encoding="utf-8",
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="unknown Exactus MCP setting",
    ):
        _ = wake_defaults(root=tmp_path)


def test_config_selection_supports_listing_and_json_paths(
    tmp_path: Path,
) -> None:
    """The dual-form option is removed before normal argument parsing.

    Args:
        tmp_path: Temporary configuration directory.

    """
    listing: ConfigSelection = select_config(
        values=("--root", str(object=tmp_path), "--config"),
    )
    expect_equal(actual=listing.path, expected=None)
    expect_equal(actual=listing.list_only, expected=True)
    expect_equal(
        actual=listing.arguments,
        expected=("--root", str(object=tmp_path)),
    )
    loaded: ConfigSelection = select_config(
        values=("--config=config.json", "status"),
    )
    expect_equal(
        actual=loaded.path,
        expected=(Path.cwd() / "config.json").resolve(),
    )
    expect_equal(actual=loaded.list_only, expected=False)
    expect_equal(actual=loaded.arguments, expected=("status",))


def test_select_config_rejects_empty_inline_value() -> None:
    """A bare ``--config=`` with no path raises a clear ValueError."""
    with pytest.raises(
        expected_exception=ValueError,
        match="requires a JSON file path",
    ):
        select_config(values=("--config=",))


def test_select_config_rejects_bare_followed_by_flag() -> None:
    """A bare ``--config`` before another flag raises ValueError."""
    with pytest.raises(
        expected_exception=ValueError,
        match="bare --config must be the final argument",
    ):
        select_config(values=("--config", "--root", "."))


def test_select_config_rejects_repeated_path() -> None:
    """Two explicit ``--config`` paths raise a clear ValueError."""
    with pytest.raises(
        expected_exception=ValueError,
        match="only one --config JSON file may be supplied",
    ):
        select_config(values=("--config=a.json", "--config=b.json"))


def test_select_config_allows_bare_after_path() -> None:
    """A path followed by a bare ``--config`` is valid listing syntax."""
    selection: ConfigSelection = select_config(
        values=("--config=cfg.json", "--config"),
    )
    expect_equal(
        actual=selection.path,
        expected=(Path.cwd() / "cfg.json").resolve(),
    )
    expect_equal(actual=selection.list_only, expected=True)


def test_service_defaults_reject_invalid_toml(tmp_path: Path) -> None:
    """An invalid TOML document raises a clear ValueError.

    Args:
        tmp_path: Temporary project root.

    """
    _ = (tmp_path / "pyproject.toml").write_text(
        data="[tool.exactus.mcp\n",
        encoding="utf-8",
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="invalid MCP project configuration",
    ):
        _ = service_defaults(root=tmp_path)


def test_service_defaults_reject_non_table_section(tmp_path: Path) -> None:
    """A non-table ``[tool.exactus.mcp]`` raises a clear TypeError.

    Args:
        tmp_path: Temporary project root.

    """
    _ = (tmp_path / "pyproject.toml").write_text(
        data='[tool.exactus]\nmcp = "not-a-table"\n',
        encoding="utf-8",
    )
    with pytest.raises(
        expected_exception=TypeError,
        match="must be a TOML table",
    ):
        _ = service_defaults(root=tmp_path)


def test_service_json_defaults_reject_invalid_json(tmp_path: Path) -> None:
    """An invalid JSON document raises a clear ValueError.

    Args:
        tmp_path: Temporary project root.

    """
    path: Path = tmp_path / "service.json"
    _ = path.write_text(data="not json", encoding="utf-8")
    path.chmod(mode=0o600)
    with pytest.raises(
        expected_exception=ValueError,
        match="unable to load Exactus MCP JSON config",
    ):
        _ = service_json_defaults(path=path)


def test_service_json_defaults_reject_non_object(tmp_path: Path) -> None:
    """A JSON document that is not an object raises a clear TypeError.

    Args:
        tmp_path: Temporary project root.

    """
    path: Path = tmp_path / "service.json"
    _ = path.write_text(data='["not-an-object"]', encoding="utf-8")
    path.chmod(mode=0o600)
    with pytest.raises(
        expected_exception=TypeError,
        match="must contain an object",
    ):
        _ = service_json_defaults(path=path)


def test_service_json_defaults_reject_non_object_section(
    tmp_path: Path,
) -> None:
    """A named ``service`` section that is not an object raises TypeError.

    Args:
        tmp_path: Temporary configuration directory.

    """
    path: Path = tmp_path / "service.json"
    _ = path.write_text(data='{"service": 1}', encoding="utf-8")
    path.chmod(mode=0o600)
    with pytest.raises(
        expected_exception=TypeError,
        match="section 'service' must be an object",
    ):
        _ = service_json_defaults(path=path)


def test_service_defaults_reject_duplicate_setting(tmp_path: Path) -> None:
    """Two keys that normalise to the same name raise a clear ValueError.

    Args:
        tmp_path: Temporary project root.

    """
    data: str = (
        '[tool.exactus.mcp]\nngrok-endpoint = "a"\nngrok_endpoint = "b"\n'
    )
    _ = (tmp_path / "pyproject.toml").write_text(data=data, encoding="utf-8")
    with pytest.raises(
        expected_exception=ValueError,
        match="duplicate Exactus MCP setting",
    ):
        _ = service_defaults(root=tmp_path)


def test_service_defaults_reject_invalid_value_type(tmp_path: Path) -> None:
    """A setting with an invalid value type raises a clear ValueError.

    Args:
        tmp_path: Temporary project root.

    """
    _ = (tmp_path / "pyproject.toml").write_text(
        data="[tool.exactus.mcp]\nhost = true\n",
        encoding="utf-8",
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="invalid value for Exactus MCP setting",
    ):
        _ = service_defaults(root=tmp_path)


def test_wakeup_cli_lists_json_configuration_with_secrets_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Watcher configuration listing includes no private JSON values.

    Args:
        tmp_path: Temporary configuration directory.
        monkeypatch: Pytest process-state fixture.

    """
    path: Path = tmp_path / "watcher.json"
    _ = path.write_text(
        data=(
            dedent(
                text=(
                    '    \n    {\n      "mantledb-namespace": "private-nam'
                    'espace",\n      "wake-key": "private-wake-key",\n    '
                    '  "access-token": "private-bearer",\n      "service-c'
                    'ommand": ["python", "-m", "service"]\n    }\n    '
                ),
            )
        ),
        encoding="utf-8",
    )
    path.chmod(mode=0o600)
    stream: StringIO = StringIO()
    monkeypatch.setattr(target=wakeup_cli, name="stdout", value=stream)
    result: int = wakeup_cli.main(arguments=(f"--config={path}", "--config"))
    output: str = stream.getvalue()
    expect_equal(actual=result, expected=0)
    expect_in(member='"wake-key": "<redacted>"', container=output)
    expect_in(member='"access-token": "<redacted>"', container=output)
    expect_in(member='"mantledb-namespace": "<redacted>"', container=output)
    expect_in(member='"service-command": [', container=output)
    expect_not_in(member="private-wake-key", container=output)
    expect_not_in(member="private-bearer", container=output)
    expect_not_in(member="private-namespace", container=output)
