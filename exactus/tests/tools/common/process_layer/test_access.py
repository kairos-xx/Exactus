# Copyright (c) 2026
"""Shared-secret provisioning and responder lifecycle."""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from exactus.tests.common.support import expect_equal, expect_none, expect_true
from exactus.tools.common.process_layer import access
from exactus.tools.common.process_layer.access import (
    Constants,
    authkey,
    runtime_dir,
    start_responder,
    stop_responder,
)

if TYPE_CHECKING:
    from exactus.tools.common.process_layer.process_control import (
        IdentityResponder,
    )


def test_runtime_dir_prefers_reports_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``EXACTUS_REPORTS_ROOT`` wins over every other base directory.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    monkeypatch.setenv(name=Constants.reports, value=str(object=tmp_path))
    expect_equal(
        actual=runtime_dir(output=tmp_path / "other"),
        expected=tmp_path / Constants.directory,
    )


def test_runtime_dir_uses_output_parent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Without the env override the output parent hosts ``.runtime``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    monkeypatch.delenv(name=Constants.reports, raising=False)
    output: Path = tmp_path / "report" / "result.md"
    expect_equal(
        actual=runtime_dir(output=output),
        expected=output.parent / Constants.directory,
    )


def test_runtime_dir_defaults_to_cwd_reports(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """No env and no output resolve under the working directory.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    monkeypatch.delenv(name=Constants.reports, raising=False)
    monkeypatch.chdir(path=tmp_path)
    expect_equal(
        actual=runtime_dir(),
        expected=tmp_path / Constants.default_reports / Constants.directory,
    )


def test_authkey_env_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A sufficiently long ``EXACTUS_AUTHKEY`` returns as bytes.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    secret: str = "s" * Constants.secret_bytes
    monkeypatch.setenv(name=Constants.environment, value=secret)
    expect_equal(
        actual=authkey(runtime=tmp_path / "runtime"),
        expected=secret.encode(encoding="utf-8"),
    )


def test_authkey_env_override_rejects_short_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Short ``EXACTUS_AUTHKEY`` values raise ``ValueError``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    monkeypatch.setenv(name=Constants.environment, value="short")
    with pytest.raises(expected_exception=ValueError, match="32 bytes"):
        _ = authkey(runtime=tmp_path / "runtime")


def test_authkey_generates_and_reuses_file(tmp_path: Path) -> None:
    """The file secret is generated once then reused byte-for-byte.

    Args:
        tmp_path: Isolated filesystem root.

    """
    runtime: Path = tmp_path / "runtime"
    first: bytes = authkey(runtime=runtime)
    expect_equal(actual=len(first), expected=Constants.secret_bytes)
    expect_true(
        condition=(runtime / Constants.filename).is_file(),
        message="authkey file missing",
    )
    second: bytes = authkey(runtime=runtime)
    expect_equal(actual=second, expected=first)


def test_authkey_regenerates_short_files(tmp_path: Path) -> None:
    """A truncated on-disk secret is replaced with a full key.

    Args:
        tmp_path: Isolated filesystem root.

    """
    runtime: Path = tmp_path / "runtime"
    runtime.mkdir(parents=True)
    _ = (runtime / Constants.filename).write_bytes(data=b"tiny")
    key: bytes = authkey(runtime=runtime)
    expect_equal(actual=len(key), expected=Constants.secret_bytes)


def test_start_responder_starts_or_degrades(tmp_path: Path) -> None:
    """Startup either yields a responder or degrades to ``None``.

    Args:
        tmp_path: Isolated filesystem root.

    """
    responder: IdentityResponder | None = start_responder(
        run_id="test-run",
        runtime=tmp_path / "runtime",
    )
    try:
        expect_true(
            condition=responder is None or responder.running,
            message="returned responder is not serving",
        )
    finally:
        stop_responder(responder=responder)


def test_stop_responder_accepts_none() -> None:
    """Stopping a missing responder is a silent no-op."""
    expect_none(value=stop_responder(responder=None))


def test_authkey_honours_access_module(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The module re-export keeps ``access.authkey`` in sync.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    monkeypatch.setenv(name=Constants.environment, value="k" * 40)
    expect_equal(actual=access.authkey(runtime=tmp_path), expected=b"k" * 40)
