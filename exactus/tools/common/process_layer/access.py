# Copyright (c) 2026
"""Shared-secret provisioning and responder wiring for exactus runs."""

from __future__ import annotations

from contextlib import suppress
from os import environ
from pathlib import Path
from secrets import token_bytes
from typing import Final, final

from exactus.tools.common.process_layer.process_control import (
    IdentityResponder,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        directory: Grouped module constant.
        filename: Grouped module constant.
        environment: Grouped module constant.
        reports: Grouped module constant.
        default_reports: Grouped module constant.
        secret_bytes: Grouped module constant.
        close_timeout: Grouped module constant.

    """

    directory: Final[str] = ".runtime"
    filename: Final[str] = "authkey"
    environment: Final[str] = "EXACTUS_AUTHKEY"
    reports: Final[str] = "EXACTUS_REPORTS_ROOT"
    default_reports: Final[str] = "EXACTUS_RESULTS"
    secret_bytes: Final[int] = 32
    close_timeout: Final[float] = 2.0


def runtime_dir(*, output: Path | None = None) -> Path:
    """Resolve the shared ``.runtime`` directory for this process.

    Args:
        output: Tool output directory used when the reports-root
            environment variable is unset.

    Returns:
        Shared runtime directory holding ``runs.db`` and ``authkey``.

    """
    reports: str | None = environ.get(Constants.reports)
    if reports:
        return Path(reports) / Constants.directory
    base: Path = (
        output.parent
        if output is not None
        else Path.cwd() / Constants.default_reports
    )
    return base / Constants.directory


def authkey(*, runtime: Path) -> bytes:
    """Return the shared process-layer secret, creating it when absent.

    ``EXACTUS_AUTHKEY`` overrides the shared file. The file secret is
    generated once per runtime directory and restricted to the owning
    user so every local exactus process can authenticate.

    Args:
        runtime: Shared runtime directory receiving ``authkey``.

    Returns:
        Shared authentication secret of at least 32 bytes.

    Raises:
        ValueError: If the environment override is too short.

    """
    override: str | None = environ.get(Constants.environment)
    if override:
        key: bytes = override.encode(encoding="utf-8")
        if len(key) < Constants.secret_bytes:
            msg: str = (
                f"{Constants.environment} must contain at least "
                f"{Constants.secret_bytes} bytes"
            )
            raise ValueError(msg)
        return key
    runtime.mkdir(parents=True, exist_ok=True)
    path: Path = runtime / Constants.filename
    try:
        existing: bytes = path.read_bytes()
    except OSError:
        existing = b""
    if len(existing) >= Constants.secret_bytes:
        return existing
    key = token_bytes(nbytes=Constants.secret_bytes)
    temporary: Path = path.with_suffix(suffix=".tmp")
    _ = temporary.write_bytes(data=key)
    temporary.chmod(mode=384)
    _ = temporary.replace(target=path)
    return key


def start_responder(*, run_id: str, runtime: Path) -> IdentityResponder | None:
    """Start a best-effort authenticated responder for the run.

    Responder startup is optional: authentication failures and socket
    errors degrade to no responder rather than aborting the run.

    Args:
        run_id: Unified run identifier advertised to controllers.
        runtime: Shared runtime directory holding ``runs.db`` and
            ``authkey``.

    Returns:
        Started responder, or None when it could not start.

    """
    try:
        responder: IdentityResponder = IdentityResponder(
            run_id=run_id,
            runs_db=runtime / "runs.db",
            authkey=authkey(runtime=runtime),
        )
        responder.start()
    except (OSError, ValueError):
        return None
    return responder


def stop_responder(*, responder: IdentityResponder | None) -> None:
    """Stop a responder started by ``start_responder``.

    Args:
        responder: Responder to stop, or None when none started.

    """
    if responder is None:
        return
    with suppress(OSError, ValueError, TimeoutError):
        responder.close(timeout=Constants.close_timeout)
