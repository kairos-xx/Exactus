# Copyright (c) 2026 Project contributors
"""Exercise ownership checks and safe fixed-port replacement failures."""

from __future__ import annotations

from os import getpid
from subprocess import CompletedProcess

import pytest

from exactus.packages.server import ports
from exactus.tests.common.support import expect_equal


@pytest.mark.parametrize(
    ("output", "command", "expected"),
    [
        ("", "", None),
        ("123\n456\n", "", None),
        ("123\n", "node -m exactus.tools.record.studio", None),
        ("123\n", "", None),
        ("123\n", "python -m unrelated.studio", None),
        ("123\n", "python -m exactus.tools.record.studio", 123),
        (
            "123\n123\n",
            "python /app/exactus/tools/record/studio/__main__.py",
            123,
        ),
        ("123\n", "python 'broken", None),
        (
            "123\n",
            "python -u -c from exactus.tools.record.studio.service "
            "import StudioService as S; s=S()",
            123,
        ),
    ],
)
def test_listener_identity(
    monkeypatch: pytest.MonkeyPatch,
    output: str,
    command: str,
    expected: int | None,
) -> None:
    """Only the requested package or factory may own a replaceable listener.

    Args:
        monkeypatch: Process-query substitution.
        output: Listener PID output.
        command: Process command line.
        expected: Expected verified PID.

    """

    def query(
        *,
        args: tuple[str, ...],
        **_options: object,
    ) -> CompletedProcess[str]:
        """Return deterministic process metadata.

        Args:
            args: Process query arguments.
            _options: Subprocess options.

        Returns:
            Captured process metadata.

        """
        return CompletedProcess(
            args=args,
            returncode=0,
            stdout=output if args[0] == "lsof" else command,
        )

    monkeypatch.setattr(target=ports, name="subprocess_run", value=query)
    expect_equal(
        actual=ports.listener_owner(
            port=8877,
            module="exactus.tools.record.studio",
            factory="exactus.tools.record.studio.service.StudioService",
        ),
        expected=expected,
    )


@pytest.mark.parametrize(
    "command",
    [
        "python -m other",
        "python -c invalid!!",
        "python -c from exactus.tools.record.studio.service "
        "import StudioService",
        "python -c from other import StudioService; StudioService()",
    ],
)
def test_inline_factory_requires_import_and_call(command: str) -> None:
    """A mention, malformed snippet or unrelated factory is insufficient.

    Args:
        command: Untrusted process command line.

    """
    expect_equal(
        actual=ports.inline_factory(
            command=command,
            factory="exactus.tools.record.studio.service.StudioService",
        ),
        expected=False,
    )


def test_owner_query_failure_and_current_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unavailable process tools and our own PID fail closed.

    Args:
        monkeypatch: Process-query substitution.

    """

    def unavailable(**_options: object) -> CompletedProcess[str]:
        """Simulate unavailable process inspection.

        Args:
            _options: Subprocess options.

        Returns:
            Never reached; the function always raises.

        Raises:
            OSError: Process tools are unavailable.

        """
        raise OSError

    monkeypatch.setattr(target=ports, name="subprocess_run", value=unavailable)
    expect_equal(
        actual=ports.listener_owner(port=8877, module="studio"),
        expected=None,
    )

    def current_process(**_options: object) -> CompletedProcess[str]:
        """Return the current process as an unsafe candidate.

        Args:
            _options: Process-query options.

        Returns:
            Current process identity.

        """
        return CompletedProcess(
            args=[],
            returncode=0,
            stdout=str(object=getpid()),
        )

    monkeypatch.setattr(
        target=ports,
        name="subprocess_run",
        value=current_process,
    )
    expect_equal(
        actual=ports.listener_owner(port=8877, module="studio"),
        expected=None,
    )


@pytest.mark.parametrize(
    "mode",
    ["free", "auto", "graceful", "forced", "changed", "vanished", "unknown"],
)
def test_replacement_paths(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    """Replace only verified owners, escalating only while ownership persists.

    Args:
        monkeypatch: Process and clock substitution.
        mode: Shutdown outcome to exercise.

    """
    state: dict[str, bool] = {"busy": mode not in {"free", "auto"}}
    signals: list[int] = []
    forced: list[int] = []
    ticks: list[float] = [0.0, 6.0]
    owners: list[int | None] = [
        None if mode == "unknown" else 123,
        456 if mode == "changed" else 123,
    ]

    def interrupt(pid: int, _signal: int) -> None:
        """Simulate graceful interruption.

        Args:
            pid: Verified process ID.
            _signal: Requested signal.

        Raises:
            ProcessLookupError: Owner already exited.

        """
        signals.append(pid)
        if mode == "vanished":
            raise ProcessLookupError
        if mode == "graceful":
            state["busy"] = False

    def terminate(*, pid: int) -> None:
        """Simulate forced cleanup.

        Args:
            pid: Verified process ID.

        """
        forced.append(pid)
        state["busy"] = False

    def busy(**_options: object) -> bool:
        """Read simulated listener state.

        Args:
            _options: TCP probe options.

        Returns:
            Whether the simulated port is occupied.

        """
        return state["busy"]

    def owner(**_options: object) -> int | None:
        """Read the next simulated port owner.

        Args:
            _options: Ownership query options.

        Returns:
            Simulated listening PID.

        """
        return owners.pop(0)

    monkeypatch.setattr(target=ports, name="listening", value=busy)
    monkeypatch.setattr(target=ports, name="listener_owner", value=owner)
    monkeypatch.setattr(target=ports, name="kill", value=interrupt)
    monkeypatch.setattr(target=ports, name="terminate_tree", value=terminate)
    monkeypatch.setattr(
        target=ports,
        name="monotonic",
        value=lambda: ticks.pop(0),
    )
    if mode in {"changed", "unknown"}:
        with pytest.raises(expected_exception=OSError, match="Port 8877"):
            ports.replace_listener(port=8877, module="studio")
    else:
        expect_equal(
            actual=ports.replace_listener(
                port=0 if mode == "auto" else 8877,
                module="studio",
            ),
            expected=None if mode in {"auto", "free"} else 123,
        )
    expect_equal(actual=forced, expected=[123] if mode == "forced" else [])
    expect_equal(
        actual=signals,
        expected=[] if mode in {"auto", "free", "unknown"} else [123],
    )
