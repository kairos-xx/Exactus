# Copyright (c) 2026
"""Authenticated loopback identity discovery behavior."""

from importlib import import_module
from os import getpid
from pathlib import Path
from socket import socket, socketpair
from typing import TYPE_CHECKING, Final, cast, final

import pytest

if TYPE_CHECKING:
    from types import ModuleType
from exactus.tests.common.support import (
    expect_equal,
    expect_none,
    expect_true,
    private_call,
    private_result,
)
from exactus.tools.common.process_layer.process_control import (
    IdentityResponder,
    ProcessConstants,
    RunIdentity,
    discover,
    identify,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        authkey: Grouped module constant.
        wrong_key: Grouped module constant.

    """

    authkey: Final[bytes] = b"k" * 32
    wrong_key: Final[bytes] = b"w" * 32


def _responder(tmp_path: Path) -> IdentityResponder:
    """Build an unstarted responder bound to a temporary database path.

    Args:
        tmp_path: Directory holding the advertised database path.

    Returns:
        Configured but unstarted identity responder.

    """
    return IdentityResponder(
        run_id="run-control",
        runs_db=tmp_path / "runs.db",
        authkey=Constants.authkey,
    )


def test_responder_rejects_invalid_configuration(tmp_path: Path) -> None:
    """Empty runs, short secrets, and bad timeouts are rejected.

    Args:
        tmp_path: Isolated filesystem root.

    """
    with pytest.raises(expected_exception=ValueError, match="Run"):
        _ = IdentityResponder(
            run_id="",
            runs_db=tmp_path / "r.db",
            authkey=Constants.authkey,
        )
    with pytest.raises(expected_exception=ValueError, match="32"):
        _ = IdentityResponder(
            run_id="r",
            runs_db=tmp_path / "r.db",
            authkey=b"short",
        )
    with pytest.raises(expected_exception=ValueError, match="Timeout"):
        _ = IdentityResponder(
            run_id="r",
            runs_db=tmp_path / "r.db",
            authkey=Constants.authkey,
            timeout=0.0,
        )


def test_identify_verifies_live_responder(tmp_path: Path) -> None:
    """A running responder answers an authenticated handshake.

    Args:
        tmp_path: Isolated filesystem root.

    """
    with _responder(tmp_path=tmp_path) as responder:
        port: int | None = responder.port
        expect_true(condition=responder.running)
        expect_true(condition=port is not None)
        identity: RunIdentity | None = identify(
            pid=getpid(),
            authkey=Constants.authkey,
            port=port,
        )
        if identity is not None:
            expect_equal(actual=identity.root_pid, expected=getpid())
            expect_equal(actual=identity.run_id, expected="run-control")
        expect_true(
            condition=identity is not None,
            message="handshake produced no identity",
        )


def test_identify_rejects_wrong_authkey(tmp_path: Path) -> None:
    """A mismatched secret never yields an identity.

    Args:
        tmp_path: Isolated filesystem root.

    """
    with _responder(tmp_path=tmp_path) as responder:
        identity: RunIdentity | None = identify(
            pid=getpid(),
            authkey=Constants.wrong_key,
            port=responder.port,
        )
        expect_none(value=identity)


def test_identify_rejects_bad_inputs() -> None:
    """Nonpositive pids and bad arguments produce no identity."""
    expect_none(value=identify(pid=-1, authkey=Constants.authkey))
    expect_none(value=identify(pid=0, authkey=Constants.authkey))
    with pytest.raises(expected_exception=ValueError, match="short"):
        _ = identify(pid=getpid(), authkey=b"tiny")
    with pytest.raises(expected_exception=ValueError, match="Timeout"):
        _ = identify(pid=getpid(), authkey=Constants.authkey, timeout=-1.0)


def test_responder_start_close_lifecycle(tmp_path: Path) -> None:
    """A responder starts once and closes idempotently.

    Args:
        tmp_path: Isolated filesystem root.

    """
    responder: IdentityResponder = _responder(tmp_path=tmp_path)
    responder.start()
    with pytest.raises(expected_exception=RuntimeError, match="once"):
        responder.start()
    responder.close()
    expect_true(condition=not responder.running)
    responder.close()
    with pytest.raises(expected_exception=ValueError, match="Timeout"):
        responder.close(timeout=0.0)


def test_discover_finds_responder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Discovery interrogates candidate ports and returns identities.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    module: ModuleType = import_module(
        name="exactus.tools.common.process_layer.process_control",
    )
    with _responder(tmp_path=tmp_path) as responder:
        port: int = cast(typ="int", val=responder.port)

        def _listen_table_stub(
            *,
            constants: ProcessConstants,
        ) -> dict[int, set[int]]:
            """Return the responder listener as the only candidate.

            Args:
                constants: Unused process-control configuration.

            Returns:
                Candidate ports grouped by process identifier.

            """
            del constants
            return {getpid(): {port}}

        monkeypatch.setattr(
            target=module,
            name="_listen_table",
            value=_listen_table_stub,
        )
        identities: list[RunIdentity] = discover(
            authkey=Constants.authkey,
            timeout=0.4,
            workers=8,
        )
        expect_true(
            condition=any(
                identity.root_pid == getpid()
                and identity.run_id == "run-control"
                for identity in identities
            ),
            message="responder not discovered",
        )


def test_discover_validates_workers() -> None:
    """Discovery rejects out-of-range worker counts."""
    with pytest.raises(expected_exception=ValueError, match="Workers"):
        _ = discover(authkey=Constants.authkey, workers=0)
    with pytest.raises(expected_exception=ValueError, match="Workers"):
        _ = discover(
            authkey=Constants.authkey,
            workers=ProcessConstants.max_workers + 1,
        )


def test_receive_reads_exact_bytes() -> None:
    """``_receive`` accumulates fragments into an exact payload."""
    left: socket
    right: socket
    left, right = socketpair()
    try:
        _ = left.sendall(b"partial-message")
        data: bytes = private_result(
            owner=import_module(
                name="exactus.tools.common.process_layer.process_control",
            ),
            name="_receive",
            kind=bytes,
            connection=right,
            size=15,
            limit=4,
        )
        expect_equal(actual=data, expected=b"partial-message")
    finally:
        left.close()
        right.close()


def test_receive_none_on_early_close() -> None:
    """``_receive`` reports truncated streams as ``None``."""
    left: socket
    right: socket
    left, right = socketpair()
    try:
        _ = left.sendall(b"abc")
        left.close()
        data: object = private_call(
            owner=import_module(
                name="exactus.tools.common.process_layer.process_control",
            ),
            name="_receive",
            connection=right,
            size=10,
            limit=4,
        )
        expect_none(value=data)
    finally:
        right.close()


def test_listen_table_reports_own_responder_port(tmp_path: Path) -> None:
    """``_listen_table`` lists this process's private loopback listener.

    Args:
        tmp_path: Isolated filesystem root.

    """
    with _responder(tmp_path=tmp_path) as responder:
        table: dict[int, set[int]] = cast(
            typ="dict[int, set[int]]",
            val=private_call(
                owner=import_module(
                    name="exactus.tools.common.process_layer.process_control",
                ),
                name="_listen_table",
                constants=ProcessConstants,
            ),
        )
        expect_true(condition=responder.port in table.get(getpid(), set()))


def test_exactus_candidates_filters_by_process_identity() -> None:
    """``_exactus_candidates`` keeps interpreters and drops dead pids."""
    missing_pid: int = 2**31 - 2
    filtered: dict[int, set[int]] = cast(
        typ="dict[int, set[int]]",
        val=private_call(
            owner=import_module(
                name="exactus.tools.common.process_layer.process_control",
            ),
            name="_exactus_candidates",
            candidates={getpid(): {1}, missing_pid: {2}},
            constants=ProcessConstants,
        ),
    )
    expect_equal(actual=filtered, expected={getpid(): {1}})
