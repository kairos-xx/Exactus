# Copyright (c) 2026 João Lopes.
"""Behavior tests for the orchestration engine."""

from importlib import import_module
from json import dumps
from os import getpid
from pathlib import Path
from socket import AF_INET, SOCK_STREAM, socket
from threading import Thread
from time import sleep
from types import ModuleType
from typing import TYPE_CHECKING, Final, NoReturn, cast

import pytest

from exactus.packages.pmanager.runtime import (
    Cli,
    Client,
    Constants,
    Descriptor,
    Discovery,
    JsonValue,
    Launcher,
    Runtime,
    Spec,
    SpecError,
    State,
    Worker,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_not_equal,
    expect_true,
    fail,
    private,
    private_call,
    private_result,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from subprocess import Popen
MODULE: Final[ModuleType] = import_module(
    name="exactus.packages.pmanager.runtime",
)
ROOT: Final[Path] = (
    Path(__file__).resolve().parents[4] / "exactus" / "packages" / "pmanager"
)
SPEC: Final[Path] = ROOT / "processes.json"
AUTH_TAG: Final[str] = "secret"
POLL_ATTEMPTS: Final[int] = 20
LIVE_RESULTS: Final[int] = 2
ERROR_STATUS: Final[int] = 2


def _returns_none(**_kwargs: object) -> None:
    """Return None for any stub call.

    Args:
        **_kwargs: Ignored stub arguments.

    """
    return


class _NullBackend:
    """Backend that suppresses real process spawns."""

    def spawn(self, command: list[str]) -> None:
        """Ignore spawn requests.

        Args:
            command: Command and arguments to execute.

        """


def _request_completed(**_kwargs: object) -> dict[str, JsonValue]:
    """Return a completed IPC snapshot.

    Args:
        **_kwargs: Ignored request arguments.

    Returns:
        Constructed test value.

    """
    return {"state": "completed", "progress": 100}


def test_spec_errors_and_helpers(tmp_path: Path) -> None:
    """Handle test spec errors and helpers.

    Args:
        tmp_path: Tmp path.

    """
    spec: Spec = Spec(path=SPEC)
    merged: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=private_call(
            owner=Spec,
            name="_merge",
            base={"a": {"b": 1}},
            override={"a": {"c": 2}, "d": 3},
        ),
    )
    if merged != {"a": {"b": 1, "c": 2}, "d": 3}:
        fail(message="Deep merge failed.")
    if Spec.refs(config={"depends_on": ["A", {"process": "B"}]}) != ("A", "B"):
        fail(message="Reference extraction failed.")
    if spec.process(name="A").get("executor") != {"type": "counter"}:
        fail(message="Template normalization failed.")
    cases: tuple[JsonValue, ...] = (
        [],
        {"version": 2, "global": [], "processes": {}},
        {"version": 2, "global": {"defaults": []}, "processes": {}},
        {"version": 2, "processes": {"A": []}},
        {"version": 2, "templates": {}, "processes": {"A": {"extends": "x"}}},
        {"version": 2, "processes": {"A": {"depends_on": ["B"]}}},
        {"version": 2, "processes": {"A": {"depends_on": ["A"]}}},
        {
            "version": 2,
            "processes": {
                "A": {"depends_on": ["B"]},
                "B": {"depends_on": ["A"]},
            },
        },
    )
    for index, value in enumerate(iterable=cases):
        path: Path = tmp_path / f"bad-{index}.json"
        path.write_text(data=dumps(obj=value), encoding="utf-8")
        with pytest.raises(expected_exception=SpecError):
            Spec(path=path)
    with pytest.raises(expected_exception=SpecError):
        spec.process(name="missing")


def test_discovery_and_find(monkeypatch: pytest.MonkeyPatch) -> None:
    """Discover logical workers through the platform backend.

    Args:
        monkeypatch: Test input.

    """
    rows: tuple[tuple[int, str], ...] = (
        (
            11,
            "python x --orchestrator-worker=v2 --worker-port=99 "
            "--worker-name=A --worker-context=ctx --worker-args="
            '["--x"]',
        ),
        (12, "unrelated"),
    )

    class Backend:
        """Minimal discovery backend."""

        @staticmethod
        def command_lines() -> tuple[tuple[int, str], ...]:
            """Return deterministic process rows.

            Returns:
                Deterministic process rows.

            """
            return rows

    monkeypatch.setattr(target=MODULE, name="backend", value=Backend)
    descriptors: tuple[Descriptor, ...] = Discovery.all()
    expect_equal(actual=len(descriptors), expected=1)
    expect_equal(actual=descriptors[0].pid, expected=11)
    expect_equal(actual=descriptors[0].args, expected=("--x",))
    expect_equal(
        actual=Discovery.find(name="A", context="ctx"),
        expected=descriptors[0],
    )


def test_client_request() -> None:
    """Exercise the local IPC request protocol."""
    server: socket = socket(family=AF_INET, type=SOCK_STREAM)
    server.bind((Constants.host, 0))
    server.listen(1)
    port: int = int(server.getsockname()[1])

    def serve_once() -> None:
        """Serve one test response."""
        connection, _address = server.accept()
        with connection:
            connection.recv(65536)
            connection.sendall(b'{"state":"paused","progress":4}\n')
        server.close()

    thread: Thread = Thread(target=serve_once)
    thread.start()
    info: dict[str, JsonValue] = Client.request(
        descriptor=Descriptor(
            pid=1,
            port=port,
            name="A",
            context="x",
            args=(),
        ),
        command="info",
    )
    thread.join()
    if info.get("state") != State.PAUSED.value:
        fail(message="IPC response parsing failed.")


def test_worker_state_counter_and_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Handle test worker state counter and wait.

    Args:
        monkeypatch: Monkeypatch.

    """
    spec: Spec = Spec(path=SPEC)
    worker: Worker = Worker(
        runtime=Runtime(name="A", context="ctx", args=("--x",)),
        spec=spec,
        port=1,
    )
    private_call(
        owner=worker,
        name="_set",
        state=State.PAUSED,
        reason="manual",
    )
    snap: dict[str, JsonValue] = worker.snapshot()
    expect_equal(actual=snap.get("state"), expected="paused")
    expect_equal(actual=snap.get("reason"), expected="manual")
    expect_equal(actual=worker.refs(key="depends_on"), expected=())
    _ = private_call(
        owner=worker,
        name="_cmd_pause",
        request={"payload": {"owner": "first"}},
    )
    _ = private_call(
        owner=worker,
        name="_cmd_pause",
        request={"payload": {"owner": "second"}},
    )
    first_release: object = private_call(
        owner=worker,
        name="_cmd_start",
        request={"payload": {"owner": "first"}},
    )
    expect_equal(
        actual=cast(typ="dict[str, JsonValue]", val=first_release)["state"],
        expected=State.PAUSED.value,
    )
    second_release: object = private_call(
        owner=worker,
        name="_cmd_start",
        request={"payload": {"owner": "second"}},
    )
    expect_equal(
        actual=cast(typ="dict[str, JsonValue]", val=second_release)["state"],
        expected=State.RUNNING.value,
    )

    def _sleep(_seconds: float) -> None:
        """Accept a synthetic sleep duration.

        Args:
            _seconds: Test input.

        """
        return

    monkeypatch.setattr(target=MODULE, name="sleep", value=_sleep)
    expect_true(
        condition=private_result(owner=worker, name="_run_counter", kind=bool),
    )
    expect_equal(
        actual=worker.runtime.progress,
        expected=Constants.percent_complete,
    )
    descriptor: Descriptor = Descriptor(
        pid=2,
        port=2,
        name="A",
        context="ctx",
        args=(),
    )

    def _find(**_kwargs: object) -> Descriptor:
        """Return the stub descriptor.

        Args:
            **_kwargs: Ignored discovery arguments.

        Returns:
            Constructed test value.

        """
        return descriptor

    monkeypatch.setattr(
        target=Discovery,
        name="find",
        value=staticmethod(_find),
    )

    def _completed_request(**_kwargs: object) -> dict[str, JsonValue]:
        """Return a completed IPC snapshot.

        Args:
            **_kwargs: Ignored request arguments.

        Returns:
            Constructed test value.

        """
        return {"state": "completed"}

    monkeypatch.setattr(
        target=Client,
        name="request",
        value=staticmethod(_completed_request),
    )
    if not private_result(
        owner=worker,
        name="_wait_for",
        kind=bool,
        descriptor=descriptor,
        label="A",
    ):
        fail(message="Completed dependency should release waiter.")

    def _failed_request(**_kwargs: object) -> dict[str, JsonValue]:
        """Return a failed IPC snapshot.

        Args:
            **_kwargs: Ignored request arguments.

        Returns:
            Constructed test value.

        """
        return {"state": "failed"}

    monkeypatch.setattr(
        target=Client,
        name="request",
        value=staticmethod(_failed_request),
    )
    if private_result(
        owner=worker,
        name="_wait_for",
        kind=bool,
        descriptor=descriptor,
        label="A",
    ):
        fail(message="Failed dependency should fail waiter.")


def test_worker_ensure_command_fanout_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Handle test worker ensure command fanout execute.

    Args:
        monkeypatch: Monkeypatch.

    """
    spec: Spec = Spec(path=SPEC)
    worker: Worker = Worker(
        runtime=Runtime(name="E", context="ctx", args=()),
        spec=spec,
        port=1,
    )
    descriptor: Descriptor = Descriptor(
        pid=2,
        port=2,
        name="D",
        context="ctx",
        args=(),
    )

    def _find(**_kwargs: object) -> Descriptor:
        """Return the stub descriptor.

        Args:
            **_kwargs: Ignored discovery arguments.

        Returns:
            Constructed test value.

        """
        return descriptor

    monkeypatch.setattr(
        target=Discovery,
        name="find",
        value=staticmethod(_find),
    )

    def _create(_self: object, **_kwargs: object) -> Descriptor:
        """Return the stub descriptor.

        Args:
            _self: Test input.
            **_kwargs: Ignored launcher arguments.

        Returns:
            Constructed test value.

        """
        return descriptor

    monkeypatch.setattr(target=Launcher, name="create", value=_create)
    ensure: Callable[..., Descriptor] = cast(
        typ="Callable[..., Descriptor]",
        val=private(owner=worker, name="_ensure"),
    )
    if ensure(name="D") != descriptor:
        fail(message="Existing dependency was not reused.")
    if ensure(name="D", restart_live=True) != descriptor:
        fail(message="Restart request failed.")
    monkeypatch.setattr(target=worker, name="_run_fanout", value=lambda: True)
    worker.execute()
    if worker.runtime.state is not State.COMPLETED:
        fail(message="Fan-out success did not complete E.")
    counter: Worker = Worker(
        runtime=Runtime(name="A", context="ctx", args=()),
        spec=spec,
        port=1,
    )
    monkeypatch.setattr(
        target=counter,
        name="_run_counter",
        value=lambda: True,
    )
    monkeypatch.setattr(
        target=counter,
        name="_admit_concurrency",
        value=lambda: None,
    )
    counter.execute()
    if counter.runtime.state is not State.COMPLETED:
        fail(message="Counter execution did not complete.")


def test_cli_helpers_and_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """Handle test cli helpers and main.

    Args:
        monkeypatch: Monkeypatch.

    """
    head: list[str]
    payload: tuple[str, ...]
    head, payload = Cli.split_args(
        values=["-c", "A", "x", "--args", "--foo", "v", "--live"],
    )
    if payload != ("--foo", "v") or "--live" not in head:
        fail(message="Argument forwarding split failed.")
    if (
        private_result(
            owner=Cli,
            name="_index",
            kind=int,
            values=["a", "b"],
            target="b",
        )
        != 1
    ):
        fail(message="Index helper failed.")
    with pytest.raises(expected_exception=ValueError, match="x"):
        private_call(owner=Cli, name="_index", values=[], target="x")
    rendered: str = Cli.render(info={"progress": 50, "state": "paused"})
    if "50% paused" not in rendered:
        fail(message="Paused renderer failed.")
    output: list[str] = []
    monkeypatch.setattr(
        target=MODULE.stdout,
        name="write",
        value=output.append,
    )
    if Cli.main(values=[str(object=ROOT / "runtime.py"), "--validate"]) != 0:
        fail(message="Validate command failed.")
    if (
        Cli.main(values=[str(object=ROOT / "runtime.py"), "--tree", "ctx"])
        != 0
    ):
        fail(message="Tree command failed.")
    monkeypatch.setattr(
        target=Discovery,
        name="all",
        value=staticmethod(lambda: ()),
    )
    if (
        Cli.main(
            values=[
                "-m",
                "exactus.packages.pmanager.runtime",
                "--status",
                "--json",
            ],
        )
        != 0
    ):
        fail(message="Status command failed.")
    if (
        Cli.main(
            values=[
                "-m",
                "exactus.packages.pmanager.runtime",
                "-c",
                "E",
                "ctx",
                "--dry-run",
            ],
        )
        != 0
    ):
        fail(message="Dry-run command failed.")


def test_cli_loads_a_json_spec_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Load an explicit JSON specification for informational commands.

    Args:
        tmp_path: Temporary specification directory.
        monkeypatch: Redirects CLI output.

    """
    spec_path: Path = tmp_path / "example-spec.json"
    spec_path.write_text(
        data=dumps(
            obj={
                "version": 2,
                "processes": {"only": {"executor": {"type": "counter"}}},
            },
        ),
        encoding="utf-8",
    )
    output: list[str] = []
    monkeypatch.setattr(
        target=MODULE.stdout,
        name="write",
        value=output.append,
    )
    script: str = str(object=ROOT / "runtime.py")
    for option in (
        ("--spec", str(object=spec_path)),
        (f"--spec={spec_path}",),
    ):
        output.clear()
        expect_equal(
            actual=Cli.main(values=[script, *option, "--validate"]),
            expected=0,
        )
        expect_true(
            condition="valid: 1 processes" in "".join(output),
            message="The CLI did not load the selected JSON spec.",
        )
    with pytest.raises(expected_exception=SpecError, match="requires"):
        Cli.main(values=[script, "--spec"])


def test_launcher_real_worker() -> None:
    """Exercise detached launch, discovery, IPC, and serving together."""
    context: str = f"coverage-launch-{getpid()}"
    launcher: Launcher = Launcher(spec_path=SPEC)
    descriptor: Descriptor = launcher.create(
        name="A",
        context=context,
        process_args=("--sample",),
    )
    info: dict[str, JsonValue] = {}
    attempt: int = 0
    while attempt < POLL_ATTEMPTS:
        try:
            info = Client.request(descriptor=descriptor, command="info")
            break
        except OSError:
            sleep(0.05)
            attempt += 1
    if not info:
        fail(message="Launched worker IPC did not become ready.")
    if info.get("args") != ["--sample"]:
        fail(message="Launched worker lost forwarded arguments.")
    Client.request(descriptor=descriptor, command="pause")
    paused: dict[str, JsonValue] = Client.request(
        descriptor=descriptor,
        command="info",
    )
    if paused.get("state") not in {"paused", "running"}:
        fail(message="Pause command was not accepted.")
    Client.request(descriptor=descriptor, command="start")
    Client.request(descriptor=descriptor, command="reset")
    reused: Descriptor = launcher.create(
        name="A",
        context=context,
        process_args=("--again",),
        restart=True,
    )
    if reused.pid != descriptor.pid:
        fail(message="Existing worker was not reused.")
    Client.request(descriptor=descriptor, command="kill")


def test_worker_concurrency_and_fanout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Handle test worker concurrency and fanout.

    Args:
        monkeypatch: Test input.

    """
    spec: Spec = Spec(path=SPEC)
    worker: Worker = Worker(
        runtime=Runtime(name="C", context="ctx", args=()),
        spec=spec,
        port=1,
    )
    peer: Descriptor = Descriptor(
        pid=999999,
        port=9,
        name="C",
        context="other",
        args=(),
    )
    calls: list[int] = []

    def peers() -> tuple[Descriptor, ...]:
        """Return a peer only on the first scan.

        Returns:
            Current synthetic peer set.

        """
        calls.append(1)
        return (peer,) if len(calls) == 1 else ()

    monkeypatch.setattr(
        target=Discovery,
        name="all",
        value=staticmethod(peers),
    )

    def _running_request(**_kwargs: object) -> dict[str, JsonValue]:
        """Return a running IPC snapshot.

        Args:
            **_kwargs: Ignored request arguments.

        Returns:
            Constructed test value.

        """
        return {"state": "running"}

    monkeypatch.setattr(
        target=Client,
        name="request",
        value=staticmethod(_running_request),
    )

    def _sleep(_seconds: float) -> None:
        """Accept a synthetic sleep duration.

        Args:
            _seconds: Test input.

        """
        return

    monkeypatch.setattr(target=MODULE, name="sleep", value=_sleep)
    private_call(owner=worker, name="_admit_concurrency")
    fanout: Worker = Worker(
        runtime=Runtime(name="E", context="ctx", args=()),
        spec=spec,
        port=1,
    )
    c_desc: Descriptor = Descriptor(
        pid=2,
        port=2,
        name="C",
        context="ctx",
        args=(),
    )
    d_desc: Descriptor = Descriptor(
        pid=3,
        port=3,
        name="D",
        context="ctx",
        args=(),
    )
    descriptors: dict[str, Descriptor] = {"C": c_desc, "D": d_desc}

    def _find(*, name: str, context: str) -> Descriptor | None:
        """Resolve a stub descriptor by name.

        Args:
            name: Test input.
            context: Test input.

        Returns:
            Constructed test value.

        """
        del context
        return descriptors.get(name)

    monkeypatch.setattr(
        target=Discovery,
        name="find",
        value=staticmethod(_find),
    )

    def _ensure(name: str, *, restart_live: bool = False) -> Descriptor:
        """Return the stub descriptor for a name.

        Args:
            name: Test input.
            restart_live: Test input.

        Returns:
            Constructed test value.

        """
        del restart_live
        return descriptors[name]

    monkeypatch.setattr(target=fanout, name="_ensure", value=_ensure)
    monkeypatch.setattr(
        target=Client,
        name="request",
        value=staticmethod(_request_completed),
    )
    if not private_result(owner=fanout, name="_run_fanout", kind=bool):
        fail(message="Completed fan-out should succeed.")


def test_worker_command_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Handle test worker command and failure.

    Args:
        monkeypatch: Test input.

    """
    spec: Spec = Spec(path=SPEC)
    worker: Worker = Worker(
        runtime=Runtime(name="A", context="ctx", args=("x",)),
        spec=spec,
        port=1,
    )

    class Process:
        """Minimal completed process facade."""

        @staticmethod
        def poll() -> int:
            """Return successful completion.

            Returns:
                Successful exit status.

            """
            return 0

        @staticmethod
        def wait() -> int:
            """Return the exit status.

            Returns:
                Process exit status.

            """
            return 0

        def terminate(self) -> None:
            """Accept termination."""

    def _popen(**_kwargs: object) -> Process:
        """Return the completed process stub.

        Args:
            **_kwargs: Ignored spawn arguments.

        Returns:
            Constructed test value.

        """
        return Process()

    monkeypatch.setattr(target=MODULE, name="Popen", value=_popen)
    if not private_result(
        owner=worker,
        name="_run_command",
        kind=bool,
        executor_config={"command": ["echo"]},
    ):
        fail(message="Successful command should succeed.")
    if private_result(
        owner=worker,
        name="_run_command",
        kind=bool,
        executor_config={"command": "bad"},
    ):
        fail(message="Invalid command should fail.")


def test_cli_observe_create_and_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Handle test cli observe create and errors.

    Args:
        monkeypatch: Monkeypatch.

    """
    descriptor: Descriptor = Descriptor(
        pid=7,
        port=8,
        name="A",
        context="ctx",
        args=(),
    )

    def _find(**_kwargs: object) -> Descriptor:
        """Return the stub descriptor.

        Args:
            **_kwargs: Ignored discovery arguments.

        Returns:
            Constructed test value.

        """
        return descriptor

    monkeypatch.setattr(
        target=Discovery,
        name="find",
        value=staticmethod(_find),
    )

    def _paused_request(**_kwargs: object) -> dict[str, JsonValue]:
        """Return a paused IPC snapshot.

        Args:
            **_kwargs: Ignored request arguments.

        Returns:
            Constructed test value.

        """
        return {"state": "paused", "progress": 25}

    monkeypatch.setattr(
        target=Client,
        name="request",
        value=staticmethod(_paused_request),
    )
    output: list[str] = []
    monkeypatch.setattr(
        target=MODULE.stdout,
        name="write",
        value=output.append,
    )
    script: str = str(object=ROOT / "runtime.py")
    if Cli.main(values=[script, "-o", "A", "ctx", "--info", "--json"]) != 0:
        fail(message="Observe info failed.")

    def _create(_self: object, **_kwargs: object) -> Descriptor:
        """Return the stub descriptor.

        Args:
            _self: Test input.
            **_kwargs: Ignored launcher arguments.

        Returns:
            Constructed test value.

        """
        return descriptor

    monkeypatch.setattr(target=Launcher, name="create", value=_create)
    if Cli.main(values=[script, "-c", "A", "ctx", "--args", "--x"]) != 0:
        fail(message="Create routing failed.")
    if Cli.main(values=[str(object=ROOT / "A.py"), "ctx"]) != 0:
        fail(message="Wrapper routing failed.")
    with pytest.raises(expected_exception=SpecError):
        Cli.main(values=[script])
    with pytest.raises(expected_exception=SpecError):
        Cli.main(values=[script, "-o", "A"])


def test_worker_serve_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    """Handle test worker serve protocol.

    Args:
        monkeypatch: Monkeypatch.

    """
    probe: socket = socket(family=AF_INET, type=SOCK_STREAM)
    probe.bind((Constants.host, 0))
    port: int = int(probe.getsockname()[1])
    probe.close()
    worker: Worker = Worker(
        runtime=Runtime(name="A", context="serve", args=()),
        spec=Spec(path=SPEC),
        port=port,
    )
    monkeypatch.setattr(target=worker, name="execute", value=lambda: None)
    thread: Thread = Thread(target=worker.serve)
    thread.start()
    sleep(0.05)
    descriptor: Descriptor = Descriptor(
        pid=1,
        port=port,
        name="A",
        context="serve",
        args=(),
    )
    for command in ("info", "pause", "start", "reset", "create", "unknown"):
        Client.request(descriptor=descriptor, command=command)
    Client.request(descriptor=descriptor, command="kill")
    thread.join(timeout=2.0)
    if thread.is_alive():
        fail(message="Worker server did not stop.")


def test_cli_worker_tree_status_and_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Handle test cli worker tree status and live.

    Args:
        monkeypatch: Test input.

    """
    descriptor: Descriptor = Descriptor(
        pid=4,
        port=4,
        name="A",
        context="ctx",
        args=(),
    )
    output: list[str] = []
    monkeypatch.setattr(
        target=MODULE.stdout,
        name="write",
        value=output.append,
    )
    monkeypatch.setattr(target=MODULE.stdout, name="flush", value=lambda: None)

    def _serve(_self: Worker) -> None:
        """Skip the worker serve loop.

        Args:
            _self: Test input.

        """
        return

    monkeypatch.setattr(target=Worker, name="serve", value=_serve)
    script: str = str(object=ROOT / "runtime.py")
    internal: list[str] = [
        script,
        Constants.marker,
        "--worker-port=1",
        "--worker-name=A",
        "--worker-context=ctx",
        "--worker-args=[]",
        f"--spec={SPEC}",
    ]
    if Cli.main(values=internal) != 0:
        fail(message="Internal worker routing failed.")

    def _find(**_kwargs: object) -> Descriptor:
        """Return the stub descriptor.

        Args:
            **_kwargs: Ignored discovery arguments.

        Returns:
            Constructed test value.

        """
        return descriptor

    monkeypatch.setattr(
        target=Discovery,
        name="find",
        value=staticmethod(_find),
    )

    def _paused_request(**_kwargs: object) -> dict[str, JsonValue]:
        """Return a paused IPC snapshot.

        Args:
            **_kwargs: Ignored request arguments.

        Returns:
            Constructed test value.

        """
        return {"state": "paused", "progress": 30}

    monkeypatch.setattr(
        target=Client,
        name="request",
        value=staticmethod(_paused_request),
    )
    tree: str = Cli.tree(spec=Spec(path=SPEC), context="ctx")
    if "paused" not in tree:
        fail(message="Tree did not render a live paused process.")
    monkeypatch.setattr(
        target=Discovery,
        name="all",
        value=staticmethod(lambda: (descriptor,)),
    )
    if Cli.main(values=[script, "--status"]) != 0:
        fail(message="Populated status failed.")
    find_calls: list[int] = []

    def find_once(**_kwargs: JsonValue) -> Descriptor | None:
        """Return one live result followed by process disappearance.

        Args:
            **_kwargs: Ignored discovery arguments.

        Returns:
            Descriptor while live, otherwise None.

        """
        find_calls.append(1)
        return descriptor if len(find_calls) <= LIVE_RESULTS else None

    monkeypatch.setattr(
        target=Discovery,
        name="find",
        value=staticmethod(find_once),
    )
    monkeypatch.setattr(
        target=Client,
        name="request",
        value=staticmethod(_request_completed),
    )
    if Cli.main(values=[script, "-o", "A", "ctx", "--live"]) != 0:
        fail(message="Live observation failed.")


def test_module_main_success_and_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Handle test module main success and error.

    Args:
        monkeypatch: Monkeypatch.

    """
    output: list[str] = []
    monkeypatch.setattr(
        target=MODULE.stdout,
        name="write",
        value=output.append,
    )
    monkeypatch.setattr(
        target=MODULE,
        name="argv",
        value=["-m", "exactus.packages.pmanager.runtime", "--validate"],
    )
    if MODULE.main() != 0:
        fail(message="Top-level success status was incorrect.")

    def _raise_spec(**_kwargs: object) -> NoReturn:
        """Raise a stub spec failure.

        Args:
            **_kwargs: Ignored CLI arguments.

        Raises:
            SpecError: Always.

        """
        msg: str = "x"
        raise SpecError(msg)

    monkeypatch.setattr(
        target=Cli,
        name="main",
        value=staticmethod(_raise_spec),
    )
    monkeypatch.setattr(
        target=MODULE.stderr,
        name="write",
        value=output.append,
    )
    if MODULE.main() != ERROR_STATUS:
        fail(message="Top-level error status was incorrect.")


def test_launcher_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise launch timeout when a worker never becomes discoverable.

    Args:
        monkeypatch: Test input.

    """
    ticks: list[float] = [0.0, 16.0]

    def clock() -> float:
        """Return deterministic monotonic timestamps.

        Returns:
            Next synthetic timestamp.

        """
        return ticks.pop(0) if ticks else 16.0

    monkeypatch.setattr(
        target=Discovery,
        name="find",
        value=staticmethod(_returns_none),
    )
    monkeypatch.setattr(target=MODULE, name="backend", value=_NullBackend)
    monkeypatch.setattr(target=MODULE, name="monotonic", value=clock)
    with pytest.raises(
        expected_exception=RuntimeError,
        match="did not become",
    ):
        Launcher(spec_path=SPEC).create(
            name="A",
            context="timeout",
            process_args=(),
        )


def test_wait_for_disappeared_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Treat a disappeared dependency as failure.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    worker: Worker = Worker(
        runtime=Runtime(name="B", context="ctx", args=()),
        spec=Spec(path=SPEC),
        port=1,
    )
    monkeypatch.setattr(
        target=Discovery,
        name="find",
        value=staticmethod(_returns_none),
    )
    descriptor: Descriptor = Descriptor(
        pid=1,
        port=1,
        name="A",
        context="ctx",
        args=(),
    )
    if private_result(
        owner=worker,
        name="_wait_for",
        kind=bool,
        descriptor=descriptor,
        label="A",
    ):
        fail(message="Disappeared dependency must not imply success.")


def test_fanout_disappearance_is_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail a fan-out when a child disappears before completion.

    Args:
        monkeypatch: Test input.

    """
    worker: Worker = Worker(
        runtime=Runtime(name="E", context="missing-child", args=()),
        spec=Spec(path=SPEC),
        port=1,
    )
    child: Descriptor = Descriptor(
        pid=1,
        port=2,
        name="C",
        context="missing-child",
        args=(),
    )

    def _ensure_child(**_kwargs: object) -> Descriptor:
        """Return the stub child descriptor.

        Args:
            **_kwargs: Ignored ensure arguments.

        Returns:
            Constructed test value.

        """
        return child

    monkeypatch.setattr(target=worker, name="_ensure", value=_ensure_child)
    monkeypatch.setattr(
        target=Discovery,
        name="find",
        value=staticmethod(_returns_none),
    )
    expect_false(
        condition=private_result(owner=worker, name="_run_fanout", kind=bool),
    )
    expect_not_equal(actual=worker.runtime.children["C"], expected={})


def test_obsolete_generation_cannot_publish_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prevent an obsolete execution generation from publishing state.

    Args:
        monkeypatch: Test input.

    """
    worker: Worker = Worker(
        runtime=Runtime(name="A", context="generation", args=()),
        spec=Spec(path=SPEC),
        port=1,
    )

    def supersede() -> bool:
        """Exercise supersede.

        Returns:
            Constructed test value.

        """
        worker.runtime.generation += 1
        return True

    monkeypatch.setattr(target=worker, name="_run_counter", value=supersede)
    worker.execute()
    expect_true(condition=worker.runtime.state is State.STARTING)


def test_authenticated_serve_controls_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Authenticate IPC and control a live command executor.

    Args:
        monkeypatch: Test input.

    """
    probe: socket = socket(family=AF_INET, type=SOCK_STREAM)
    probe.bind((Constants.host, 0))
    port: int = int(probe.getsockname()[1])
    probe.close()
    worker: Worker = Worker(
        runtime=Runtime(name="A", context="secure", args=()),
        spec=Spec(path=SPEC),
        port=port,
        token=AUTH_TAG,
    )

    class Process:
        pid: int = 123
        terminated: bool = False

        @staticmethod
        def poll() -> int | None:
            """Exercise poll.

            Returns:
                Constructed test value.

            """
            return None

        def terminate(self) -> None:
            """Exercise terminate."""
            self.terminated = True

    process: Process = Process()
    worker.executor_process = cast(typ="Popen[bytes]", val=process)
    signals: list[str] = []

    class ControlBackend:
        """Capture portable pause and resume operations."""

        @staticmethod
        def pause(*, pid: int) -> None:
            """Exercise pause.

            Args:
                pid: Test input.

            """
            signals.append(f"pause:{pid}")

        @staticmethod
        def resume(*, pid: int) -> None:
            """Exercise resume.

            Args:
                pid: Test input.

            """
            signals.append(f"resume:{pid}")

    monkeypatch.setattr(target=MODULE, name="backend", value=ControlBackend)
    monkeypatch.setattr(target=worker, name="execute", value=lambda: None)
    thread: Thread = Thread(target=worker.serve)
    thread.start()
    sleep(0.05)
    descriptor: Descriptor = Descriptor(
        pid=1,
        port=port,
        name="A",
        context="secure",
        args=(),
        token=AUTH_TAG,
    )
    expect_true(
        condition=Client.request(
            descriptor=descriptor,
            command="pause",
            payload={"owner": "first"},
        )["state"]
        == "paused",
    )
    expect_true(
        condition=Client.request(
            descriptor=descriptor,
            command="pause",
            payload={"owner": "second"},
        )["state"]
        == "paused",
    )
    expect_true(
        condition=Client.request(
            descriptor=descriptor,
            command="start",
            payload={"owner": "first"},
        )["state"]
        == "paused",
    )
    expect_true(
        condition=Client.request(
            descriptor=descriptor,
            command="start",
            payload={"owner": "second"},
        )["state"]
        == "running",
    )
    restarted: dict[str, JsonValue] = Client.request(
        descriptor=descriptor,
        command="restart",
        payload={"args": ["--new"]},
    )
    expect_equal(actual=restarted["generation"], expected=2)
    expect_equal(actual=worker.runtime.args, expected=("--new",))
    Client.request(descriptor=descriptor, command="kill")
    thread.join(timeout=1.0)
    expect_equal(actual=signals, expected=["pause:123", "resume:123"])
    expect_true(condition=process.terminated)


def test_launcher_honors_existing_state_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reuse live dependencies while restarting direct reset-policy creates.

    Args:
        monkeypatch: Test input.

    """
    descriptor: Descriptor = Descriptor(
        pid=4242,
        port=1234,
        name="A",
        context="policy",
        args=(),
        token=AUTH_TAG,
    )

    def _find(**_kwargs: object) -> Descriptor:
        """Return the stub descriptor.

        Args:
            **_kwargs: Ignored discovery arguments.

        Returns:
            Constructed test value.

        """
        return descriptor

    monkeypatch.setattr(
        target=Discovery,
        name="find",
        value=staticmethod(_find),
    )
    commands: list[str] = []

    def request(**kwargs: JsonValue) -> dict[str, JsonValue]:
        """Exercise request.

        Args:
            kwargs: Request keyword arguments.

        Returns:
            Constructed test value.

        """
        command: str = str(object=kwargs["command"])
        commands.append(command)
        return {"state": State.RUNNING.value, "progress": 10}

    monkeypatch.setattr(
        target=Client,
        name="request",
        value=staticmethod(request),
    )
    launcher: Launcher = Launcher(spec_path=SPEC)
    launcher.create(
        name="A",
        context="policy",
        process_args=(),
        policy_key="on_dependency_request",
    )
    expect_equal(actual=commands, expected=["info", "info"])
    commands.clear()
    launcher.create(name="B", context="policy", process_args=())
    expect_equal(actual=commands, expected=["info", "restart"])
