# Copyright (c) 2026
"""Validate ngrok public URL discovery."""

from asyncio import StreamReader, run
from asyncio.subprocess import Process
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from exactus.packages.exactus_mcp import ngrok
from exactus.packages.exactus_mcp.ngrok import NgrokTunnel
from exactus.tests.common.support import expect_equal, expect_none


def _process(*, output: bytes, returncode: int | None = None) -> MagicMock:
    """Create a child process with deterministic captured output.

    Args:
        output: Buffered child stdout.
        returncode: Current child exit status.

    Returns:
        Process double with an asynchronous wait operation.

    """
    process: MagicMock = MagicMock(spec=Process)
    process.stdout = StreamReader()
    process.stdout.feed_data(data=output)
    process.stdout.feed_eof()
    process.returncode = returncode
    process.wait = AsyncMock(return_value=0)
    return process


def test_parse_public_url_accepts_started_https_tunnel() -> None:
    """A started-tunnel record yields its HTTPS origin."""
    expect_equal(
        actual=NgrokTunnel.parse_public_url(
            line=(
                '{"msg":"started tunnel",'
                '"url":"https://exactus.ngrok-free.app"}'
            ),
        ),
        expected="https://exactus.ngrok-free.app",
    )


def test_parse_public_url_rejects_unrelated_or_insecure_records() -> None:
    """Malformed, unrelated, and HTTP records never create a public origin."""
    expect_none(value=NgrokTunnel.parse_public_url(line="not JSON"))
    expect_none(
        value=NgrokTunnel.parse_public_url(
            line='{"msg":"started tunnel","url":"http://localhost"}',
        ),
    )
    expect_none(
        value=NgrokTunnel.parse_public_url(line='{"msg":"session started"}'),
    )


@pytest.mark.parametrize(
    "line",
    [
        "[]",
        "null",
        '{"msg":"started tunnel"}',
        '{"msg":"started tunnel","url":3}',
        '{"msg":"started tunnel","url":"https:"}',
    ],
)
def test_parse_public_url_rejects_incomplete_records(line: str) -> None:
    """Reject non-object logs and incomplete HTTPS records.

    Args:
        line: Candidate log record.

    """
    expect_none(value=NgrokTunnel.parse_public_url(line=line))


@pytest.mark.parametrize("endpoint", [None, "configured-endpoint"])
def test_start_wait_and_close_own_the_child(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str | None,
) -> None:
    """Discover a tunnel after unrelated logs and reap it on close.

    Args:
        monkeypatch: Child-process boundary replacement.
        endpoint: Optional named endpoint selection.

    """

    async def exercise() -> None:
        """Run the tunnel lifecycle against the scripted child."""
        process: MagicMock = _process(
            output=(
                b'not JSON\n{"msg":"started tunnel",'
                b'"url":"https://exactus.ngrok-free.app"}\n'
            ),
        )
        spawn: AsyncMock = AsyncMock(return_value=process)
        monkeypatch.setattr(
            target=ngrok,
            name="which",
            value=MagicMock(return_value="ngrok"),
        )
        monkeypatch.setattr(
            target=ngrok,
            name="create_subprocess_exec",
            value=spawn,
        )
        tunnel: NgrokTunnel = await NgrokTunnel.start(
            command="ngrok",
            upstream_url="http://127.0.0.1:6100",
            startup_timeout=1.0,
            requested_url="https://exactus.ngrok-free.app",
            endpoint_name=endpoint,
        )
        expect_equal(
            actual=tunnel.public_url,
            expected="https://exactus.ngrok-free.app",
        )
        expect_equal(actual=await tunnel.wait(), expected=0)
        expect_equal(
            actual=spawn.call_args.args[1],
            expected="http" if endpoint is None else "start",
        )
        if endpoint is None:
            expect_equal(
                actual=spawn.call_args.args[-2:],
                expected=("--url", "https://exactus.ngrok-free.app"),
            )
        else:
            expect_equal(actual=spawn.call_args.args[-1], expected=endpoint)
        await tunnel.close()
        process.terminate.assert_called_once_with()
        process.kill.assert_not_called()

    run(main=exercise())


def test_start_rejects_missing_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing binary fails before any child process is created.

    Args:
        monkeypatch: Executable lookup replacement.

    """
    monkeypatch.setattr(
        target=ngrok,
        name="which",
        value=MagicMock(return_value=None),
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="executable not found",
    ):
        run(
            main=NgrokTunnel.start(
                command="missing",
                upstream_url="http://localhost",
                startup_timeout=1.0,
                requested_url=None,
                endpoint_name=None,
            ),
        )


@pytest.mark.parametrize("missing_stdout", [False, True])
def test_start_failure_reaps_child(
    *,
    monkeypatch: pytest.MonkeyPatch,
    missing_stdout: bool,
) -> None:
    """Missing capture and early exit both clean up the owned process.

    Args:
        monkeypatch: Child-process boundary replacement.
        missing_stdout: Whether capture is unavailable rather than exhausted.

    """

    async def exercise() -> None:
        """Trigger the startup failure and verify cleanup."""
        process: MagicMock = _process(output=b"startup failed\n")
        if missing_stdout:
            process.stdout = None
        monkeypatch.setattr(
            target=ngrok,
            name="which",
            value=MagicMock(return_value="ngrok"),
        )
        monkeypatch.setattr(
            target=ngrok,
            name="create_subprocess_exec",
            value=AsyncMock(return_value=process),
        )
        with pytest.raises(
            expected_exception=RuntimeError,
            match="stdout was not captured"
            if missing_stdout
            else "startup failed",
        ):
            await NgrokTunnel.start(
                command="ngrok",
                upstream_url="http://localhost",
                startup_timeout=1.0,
                requested_url=None,
                endpoint_name=None,
            )
        process.terminate.assert_called_once_with()

    run(main=exercise())


@pytest.mark.parametrize("already_exited", [False, True])
def test_close_handles_exited_and_unresponsive_children(
    *,
    already_exited: bool,
) -> None:
    """Closing is harmless after exit and escalates a failed terminate.

    Args:
        already_exited: Whether the child has already finished.

    """

    async def exercise() -> None:
        """Close the tunnel against the scripted child state."""
        process: MagicMock = _process(
            output=b"",
            returncode=0 if already_exited else None,
        )
        process.wait = AsyncMock(side_effect=[TimeoutError(), 0])
        await NgrokTunnel(
            process=cast(typ="Process", val=process),
            public_url="https://exactus.ngrok-free.app",
        ).close()
        if already_exited:
            process.terminate.assert_not_called()
            process.wait.assert_not_awaited()
        else:
            process.terminate.assert_called_once_with()
            process.kill.assert_called_once_with()
            expect_equal(actual=process.wait.await_count, expected=2)

    run(main=exercise())
