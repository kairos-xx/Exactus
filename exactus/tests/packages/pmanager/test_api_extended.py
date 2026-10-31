# Copyright (c) 2026 João Lopes.
"""Extended public API tests."""

from json import loads
from pathlib import Path
from typing import TYPE_CHECKING, Final, NoReturn, cast
from typing import final as _group_final_final

import pytest

from exactus.packages.pmanager import (
    Context,
    ExecutionPlan,
    Orchestrator,
    OrchestratorError,
    ProcessEvent,
    ProcessHandle,
    ProcessNotFoundError,
    ProcessStatus,
    WaitTimeoutError,
)
from exactus.packages.pmanager.api import Client, Discovery
from exactus.packages.pmanager.runtime import Descriptor, JsonValue, State
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
    private,
    private_as,
    private_result,
    require,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


@_group_final_final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.
        spec: Grouped module constant.

    """

    root: Final = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "packages"
        / "pmanager"
    )
    spec: Final = root / "processes.json"


def descriptor(name: str = "A", context: str = "ctx") -> Descriptor:
    """Build a descriptor.

    Args:
        name: Test input.
        context: Test input.

    Returns:
        Constructed test value.

    """
    return Descriptor(
        pid=42,
        port=1234,
        name=name,
        context=context,
        args=("--x",),
    )


def snapshot(
    state: str = "running",
    progress: int = 10,
) -> dict[str, JsonValue]:
    """Build an IPC snapshot.

    Args:
        state: Test input.
        progress: Test input.

    Returns:
        Constructed test value.

    """
    return {
        "state": state,
        "progress": progress,
        "reason": "why",
        "exit_code": None,
        "attempts": 2,
        "children": {},
    }


def _find_descriptor(**_kwargs: object) -> Descriptor:
    """Return a stub descriptor for discovery.

    Args:
        **_kwargs: Ignored discovery arguments.

    Returns:
        Constructed test value.

    """
    return descriptor()


def _find_none(**_kwargs: object) -> None:
    """Report a missing process.

    Args:
        **_kwargs: Ignored discovery arguments.

    """
    return


def _request_snapshot(**_kwargs: object) -> dict[str, JsonValue]:
    """Return a stub snapshot for IPC requests.

    Args:
        **_kwargs: Ignored request arguments.

    Returns:
        Constructed test value.

    """
    return snapshot()


def _request_completed(**_kwargs: object) -> dict[str, JsonValue]:
    """Return a completed stub snapshot.

    Args:
        **_kwargs: Ignored request arguments.

    Returns:
        Constructed test value.

    """
    return snapshot(state="completed", progress=100)


def _request_killed(**_kwargs: object) -> dict[str, JsonValue]:
    """Return a killed stub snapshot.

    Args:
        **_kwargs: Ignored request arguments.

    Returns:
        Constructed test value.

    """
    return {"state": "killed", "progress": 0}


def _raise_down(**_kwargs: object) -> NoReturn:
    """Raise a stub transport failure.

    Args:
        **_kwargs: Ignored request arguments.

    Raises:
        OSError: Always.

    """
    msg: str = "down"
    raise OSError(msg)


def test_mapping_validate_get_and_properties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover mapping construction, handles, and status properties.

    Args:
        monkeypatch: Test input.

    """
    api: Orchestrator = Orchestrator.from_mapping(
        specification=cast(
            typ="dict[str, JsonValue]",
            val=loads(s=Constants.spec.read_text()),
        ),
    )
    api.validate()
    monkeypatch.setattr(
        target=Discovery,
        name="find",
        value=staticmethod(_find_descriptor),
    )
    monkeypatch.setattr(
        target=Client,
        name="request",
        value=staticmethod(_request_snapshot),
    )
    handle: ProcessHandle = api.get(name="A", context="ctx")
    status: ProcessStatus = handle.status()
    expect_true(condition=status.live)
    expect_false(condition=status.terminal)
    expect_false(condition=status.successful)
    expect_equal(actual=handle.key.arguments, expected=("--x",))


def test_list_filters_and_status_conversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover discovery filtering and defensive snapshot conversion.

    Args:
        monkeypatch: Test input.

    """
    api: Orchestrator = Orchestrator.from_file(path=Constants.spec)
    values: tuple[Descriptor, ...] = (
        descriptor(),
        descriptor(name="D", context="other"),
    )
    monkeypatch.setattr(
        target=Discovery,
        name="all",
        value=staticmethod(lambda: values),
    )
    monkeypatch.setattr(
        target=Client,
        name="request",
        value=staticmethod(_request_completed),
    )
    rows: tuple[ProcessStatus, ...] = api.list(context="ctx", name="A")
    expect_equal(actual=len(rows), expected=1)
    expect_true(condition=rows[0].terminal)
    expect_true(condition=rows[0].successful)
    weird: ProcessStatus = private_result(
        owner=api,
        name="_status",
        kind=ProcessStatus,
        descriptor=descriptor(),
        data={
            "state": "bad",
            "progress": "bad",
            "exit_code": "bad",
            "attempts": "bad",
            "children": [],
        },
    )
    expect_true(condition=weird.state is State.STARTING)
    expect_equal(actual=weird.progress, expected=0)


def test_controls_context_and_recursive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover lifecycle controls and the context facade.

    Args:
        monkeypatch: Test input.

    """
    api: Orchestrator = Orchestrator.from_file(path=Constants.spec)

    def _find(**kwargs: object) -> Descriptor:
        """Build a descriptor from forwarded discovery arguments.

        Args:
            **kwargs: Forwarded discovery arguments.

        Returns:
            Constructed test value.

        """
        return descriptor(
            name=str(object=kwargs["name"]),
            context=str(object=kwargs["context"]),
        )

    monkeypatch.setattr(
        target=Discovery,
        name="find",
        value=staticmethod(_find),
    )
    monkeypatch.setattr(
        target=Client,
        name="request",
        value=staticmethod(_request_snapshot),
    )
    ctx: Context = api.context(name="ctx")
    expect_true(condition=ctx.get(process="A").pause().state is State.RUNNING)
    expect_true(condition=ctx.get(process="A").resume().state is State.RUNNING)
    expect_true(condition=ctx.get(process="A").reset().state is State.RUNNING)
    expect_true(
        condition=ctx.get(process="A").restart().state is State.RUNNING,
    )
    expect_true(condition=ctx.get(process="A").kill().state is State.RUNNING)
    expect_true(condition=ctx.get(process="A").cancel().state is State.RUNNING)
    expect_true(
        condition=api.pause(recursive=True, name="B", context="ctx").state
        is State.RUNNING,
    )
    expect_true(condition=len(ctx.list()) >= 0)


def test_create_plan_and_launcher_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover create, context create, plans, and translated errors.

    Args:
        monkeypatch: Test input.

    """
    api: Orchestrator = Orchestrator.from_file(path=Constants.spec)
    monkeypatch.setattr(
        target=private(owner=api, name="_launcher"),
        name="create",
        value=_find_descriptor,
    )
    handle: ProcessHandle = api.create(
        arguments=("--a",),
        name="A",
        context="ctx",
    )
    expect_equal(actual=handle.key.arguments, expected=("--a",))
    expect_equal(
        actual=api.context(name="ctx").create(process="A").key.context,
        expected="ctx",
    )

    def _find_named(**kwargs: object) -> Descriptor | None:
        """Resolve only process B from forwarded discovery arguments.

        Args:
            **kwargs: Forwarded discovery arguments.

        Returns:
            Constructed test value.

        """
        if kwargs["name"] == "B":
            return descriptor(
                name=str(object=kwargs["name"]),
                context=str(object=kwargs["context"]),
            )
        return None

    monkeypatch.setattr(
        target=Discovery,
        name="find",
        value=staticmethod(_find_named),
    )
    plan: ExecutionPlan = api.context(name="ctx").plan(
        arguments=("x",),
        process="C",
    )
    expect_equal(
        actual={entry.action for entry in plan.entries},
        expected={"CREATE", "REUSE"},
    )

    def _raise_boom(**_kwargs: object) -> NoReturn:
        """Raise a stub launcher failure.

        Args:
            **_kwargs: Ignored launcher arguments.

        Raises:
            RuntimeError: Always.

        """
        msg: str = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(
        target=private(owner=api, name="_launcher"),
        name="create",
        value=_raise_boom,
    )
    with pytest.raises(expected_exception=OrchestratorError):
        api.create(name="A", context="ctx")


def test_wait_watch_subscribe_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover terminal waiting and event consumption.

    Args:
        monkeypatch: Test input.

    """
    api: Orchestrator = Orchestrator.from_file(path=Constants.spec)
    states: Iterator[dict[str, JsonValue]] = iter(
        [snapshot(), snapshot(state="completed", progress=100)],
    )

    def _status(**_kwargs: object) -> ProcessStatus:
        """Convert the next scripted snapshot.

        Args:
            **_kwargs: Ignored status arguments.

        Returns:
            Constructed test value.

        """
        return private_result(
            owner=api,
            name="_status",
            kind=ProcessStatus,
            descriptor=descriptor(),
            data=next(states),
        )

    monkeypatch.setattr(target=api, name="status", value=_status)
    expect_true(
        condition=api.wait(
            poll_interval=0.01,
            name="A",
            context="ctx",
        ).successful,
    )
    states2: Iterator[dict[str, JsonValue]] = iter(
        [snapshot(), snapshot(state="completed", progress=100)],
    )

    def _status2(**_kwargs: object) -> ProcessStatus:
        """Convert the next scripted snapshot.

        Args:
            **_kwargs: Ignored status arguments.

        Returns:
            Constructed test value.

        """
        return private_result(
            owner=api,
            name="_status",
            kind=ProcessStatus,
            descriptor=descriptor(),
            data=next(states2),
        )

    monkeypatch.setattr(target=api, name="status", value=_status2)
    events: list[ProcessEvent] = list(
        api.watch(
            poll_interval=0.01,
            changes_only=False,
            name="A",
            context="ctx",
        ),
    )
    expect_equal(actual=len(events), expected=2)
    states3: Iterator[dict[str, JsonValue]] = iter(
        [snapshot(state="completed", progress=100)],
    )

    def _status3(**_kwargs: object) -> ProcessStatus:
        """Convert the next scripted snapshot.

        Args:
            **_kwargs: Ignored status arguments.

        Returns:
            Constructed test value.

        """
        return private_result(
            owner=api,
            name="_status",
            kind=ProcessStatus,
            descriptor=descriptor(),
            data=next(states3),
        )

    monkeypatch.setattr(target=api, name="status", value=_status3)
    seen: list[State] = []
    final: ProcessStatus = api.subscribe(
        poll_interval=0.01,
        name="A",
        context="ctx",
        callback=lambda event: seen.append(event.status.state),
    )
    expect_true(condition=final.successful)
    expect_equal(actual=seen, expected=[State.COMPLETED])

    def _status4(**_kwargs: object) -> ProcessStatus:
        """Convert a running snapshot.

        Args:
            **_kwargs: Ignored status arguments.

        Returns:
            Constructed test value.

        """
        return private_result(
            owner=api,
            name="_status",
            kind=ProcessStatus,
            descriptor=descriptor(),
            data=snapshot(),
        )

    monkeypatch.setattr(target=api, name="status", value=_status4)
    with pytest.raises(expected_exception=WaitTimeoutError):
        api.wait(timeout=0.0, name="A", context="ctx")


def test_missing_and_transport_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover missing-process and transport exception translation.

    Args:
        monkeypatch: Test input.

    """
    api: Orchestrator = Orchestrator.from_file(path=Constants.spec)
    monkeypatch.setattr(
        target=Discovery,
        name="find",
        value=staticmethod(_find_none),
    )
    with pytest.raises(expected_exception=ProcessNotFoundError):
        api.status(name="A", context="ctx")
    monkeypatch.setattr(
        target=Discovery,
        name="find",
        value=staticmethod(_find_descriptor),
    )
    monkeypatch.setattr(
        target=Client,
        name="request",
        value=staticmethod(_raise_down),
    )
    with pytest.raises(expected_exception=OrchestratorError):
        api.status(name="A", context="ctx")


def test_context_manager_ownership_and_detach(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise API ownership cleanup and explicit detach.

    Args:
        monkeypatch: Test input.

    """
    api: Orchestrator = Orchestrator.from_file(
        path=Constants.root / "processes.json",
    )
    descriptor: Descriptor = Descriptor(
        pid=91,
        port=92,
        name="A",
        context="owned",
        args=(),
    )

    def _owned(**_kwargs: object) -> Descriptor:
        """Return the prebuilt owned descriptor.

        Args:
            **_kwargs: Ignored launcher arguments.

        Returns:
            Constructed test value.

        """
        return descriptor

    monkeypatch.setattr(
        target=private(owner=api, name="_launcher"),
        name="create",
        value=_owned,
    )
    monkeypatch.setattr(
        target=Discovery,
        name="find",
        value=staticmethod(_owned),
    )
    monkeypatch.setattr(
        target=Client,
        name="request",
        value=staticmethod(_request_killed),
    )
    handle: ProcessHandle = api.create(name="A", context="owned")
    expect_equal(actual=handle.key.name, expected="A")
    api.detach(name="A", context="owned")
    api.create(name="A", context="owned")
    api.close()
    api.close()
    expect_true(condition=private_as(owner=api, name="_closed", kind=bool))


def test_generation_is_exposed_in_public_status() -> None:
    """Preserve execution generation in public snapshots."""
    descriptor: Descriptor = Descriptor(
        pid=1,
        port=2,
        name="A",
        context="ctx",
        args=(),
    )
    status: ProcessStatus = private_result(
        owner=Orchestrator,
        name="_status",
        kind=ProcessStatus,
        descriptor=descriptor,
        data={"state": "running", "progress": 3, "generation": 7},
    )
    expect_equal(actual=status.generation, expected=7)


def test_handle_forwarders_and_context_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover the remaining convenience facade forwarding methods.

    Args:
        monkeypatch: Test input.

    """
    api: Orchestrator = Orchestrator.from_file(path=Constants.spec)
    done: ProcessStatus = private_result(
        owner=api,
        name="_status",
        kind=ProcessStatus,
        descriptor=descriptor(),
        data=snapshot(state="completed", progress=100),
    )

    def _done(**_kwargs: object) -> ProcessStatus:
        """Return the completed status.

        Args:
            **_kwargs: Ignored status arguments.

        Returns:
            Constructed test value.

        """
        return done

    monkeypatch.setattr(target=api, name="status", value=_done)
    handle: ProcessHandle = api.get(name="A", context="ctx")
    expect_true(condition=handle.wait(timeout=0.1).successful)
    expect_true(
        condition=list(handle.watch(poll_interval=0.01))[-1].status.successful,
    )
    seen: list[State] = []
    expect_true(
        condition=handle.subscribe(
            callback=lambda event: seen.append(event.status.state),
        ).successful,
    )
    expect_equal(actual=seen, expected=[State.COMPLETED])
    expect_true(
        condition=api.context(name="ctx").status(process="A").successful,
    )


def test_closed_scope_and_close_cleanup() -> None:
    """Cover closed-scope protection and idempotent cleanup branches."""
    api: Orchestrator = Orchestrator.from_mapping(
        specification={
            "version": 2,
            "global": {"defaults": {}},
            "templates": {},
            "processes": {"A": {"executor": {"type": "counter"}}},
        },
    )
    temporary: Path | None = cast(
        typ="Path | None",
        val=private(owner=api, name="_temporary_spec"),
    )
    api.close(kill_owned=False)
    temporary = require(value=temporary)
    expect_false(condition=temporary.exists())
    api.close()
    with pytest.raises(expected_exception=OrchestratorError):
        api.__enter__()
