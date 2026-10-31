# pmanager API

`pmanager` is a Python 3.13 process manager with a symmetric typed
configuration model, object-reference process graph API, detached
cross-platform workers, lifecycle hooks, structured Python arguments,
live status enrichment, and context/global broadcasts.

## Configuration

Use `Specification` for a serializable mutable data model or `Spec` for the
object-first graph builder. `Spec.process()` returns a `Process` object that
can be passed directly to `Dependency` and child collections. Direct object
references are retained in memory; names are produced only at the
serialization/runtime boundary.

## Runtime

`Orchestrator` owns runtime access. `Context` binds operations to one context.
`ProcessHandle` provides status, pause, resume, reset, restart, cancel, kill,
wait, watch, and subscription operations.

## Python workers

Subclass `ProcessClass`, use `PythonClassExecutor`, and optionally implement
decorated `@pause`, `@resume`, `@reset`, `@cancel`, `@kill`, `@status`, and
`@receive(topic)` methods. The kill hook is a bounded pre-kill hook and cannot
prevent mandatory termination.

## Broadcasts

Workers and orchestrators may publish context or global live events. Events
carry source identity, context, generation, topic, payload, sequence, and
timestamp. Delivery is live and bounded rather than durable.

## Examples

See `examples/api/run.py` and `examples/cli/run.py`.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Public Python API for the process orchestrator. |
| `__main__.py` | Run the pmanager command-line interface. |
| `_platform.py` | Cross-platform process primitives used by the orchestrator. |
| `api.py` | Stable Python-first API for the context-aware process orchestrator. |
| `builder.py` | Object-first orchestration graph builder. |
| `class_runner.py` | Detached runner for Python ProcessClass executors. |
| `examples/` | Runnable demonstration for `exactus/packages/pmanager/`. |
| `lifecycle.py` | Python process classes and lifecycle-hook decorators. |
| `model.py` | Validated mutable configuration model for orchestration specifications. |
| `processes.json` | Configuration file. |
| `py.typed` | PEP 561 marker declaring that the package ships inline type annotations. |
| `runtime.py` | Context-aware process orchestrator. |

Run it as a module: `python -m exactus.packages.pmanager`.

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Public Python API for the process orchestrator.


### `__main__.py`

Run the pmanager command-line interface.


### `_platform.py`

Cross-platform process primitives used by the orchestrator.

- `class PlatformError` — Platformerror.
- `class ProcessBackend` — Define platform-specific process operations.
  - `command_lines(self) -> tuple[tuple[int, str], ...]` — Return visible process command lines.
  - `detached_kwargs(self) -> dict[str, bool | int]` — Return detached-spawn metadata for diagnostics.
  - `spawn(self, command: list[str]) -> Popen[bytes]` — Spawn one detached process.
  - `pause(self, pid: int) -> None` — Pause a process.
  - `resume(self, pid: int) -> None` — Resume a process.
  - `terminate(self, pid: int) -> None` — Terminate a process.
- `class PosixBackend` — Posixbackend.
  - `command_lines(self) -> tuple[tuple[int, str], ...]` — Command lines.
  - `detached_kwargs(self) -> dict[str, bool | int]` — Detached kwargs.
  - `spawn(self, command: list[str]) -> Popen[bytes]` — Spawn one detached POSIX process.
  - `pause(self, pid: int) -> None` — Pause.
  - `resume(self, pid: int) -> None` — Resume.
  - `terminate(self, pid: int) -> None` — Terminate.
- `class WindowsBackend` — Windowsbackend.
  - `powershell_process_action(pid: int, method: str) -> None` — Powershell process action.
  - `command_lines(self) -> tuple[tuple[int, str], ...]` — Command lines.
  - `detached_kwargs(self) -> dict[str, bool | int]` — Detached kwargs.
  - `spawn(self, command: list[str]) -> Popen[bytes]` — Spawn one detached Windows process.
  - `pause(self, pid: int) -> None` — Pause.
  - `resume(self, pid: int) -> None` — Resume.
  - `terminate(self, pid: int) -> None` — Terminate.
- `backend() -> ProcessBackend` — Backend.

### `api.py`

Stable Python-first API for the context-aware process orchestrator.

- `class Constants` — Group module-level constants.
  - `structured_argument_parts` = `2`
- `class OrchestratorError` — Orchestratorerror.
- `class ProcessNotFoundError` — Processnotfounderror.
- `class WaitTimeoutError` — Waittimeouterror.
- `class ProcessAction` — Processaction.
  - `PAUSE` = `'pause'`
  - `RESUME` = `'start'`
  - `RESET` = `'reset'`
  - `RESTART` = `'restart'`
  - `KILL` = `'kill'`
  - `CANCEL` = `'cancel'`
- `class BroadcastEvent` — Broadcastevent.
  - Fields: `id: int`, `topic: str`, `payload: JsonValue`, `source: str`, `context: str`, `generation: int`, `timestamp: float`
- `class ProcessKey` — Processkey.
  - `arguments` = `()`
  - Fields: `name: str`, `context: str`
- `class ProcessStatus` — Processstatus.
  - `custom_status` = `None`
  - Fields: `key: ProcessKey`, `state: State`, `progress: int`, `pid: int | None`, `reason: str`, `exit_code: int | None`, `attempts: int`, `generation: int`, `children: Mapping[str, JsonValue]`
  - `terminal(self) -> bool` — Terminal.
  - `successful(self) -> bool` — Successful.
  - `live(self) -> bool` — Live.
- `class ProcessEvent` — Processevent.
  - Fields: `status: ProcessStatus`, `previous_state: State | None`
- `class PlanEntry` — Planentry.
  - `pid` = `None`
  - Fields: `key: ProcessKey`, `action: str`
- `class ExecutionPlan` — Executionplan.
  - Fields: `root: ProcessKey`, `entries: tuple[PlanEntry, ...]`
- `class ProcessHandle` — Processhandle.
  - `__init__(self, orchestrator: Orchestrator, key: ProcessKey) -> None` — Init.
  - `status(self) -> ProcessStatus` — Status.
  - `pause(self, *, recursive: bool=False) -> ProcessStatus` — Pause.
  - `resume(self, *, recursive: bool=False) -> ProcessStatus` — Resume.
  - `reset(self, *, recursive: bool=False) -> ProcessStatus` — Reset.
  - `restart(self, *, recursive: bool=False) -> ProcessStatus` — Restart.
  - `kill(self, *, recursive: bool=False) -> ProcessStatus` — Kill.
  - `cancel(self, *, recursive: bool=False) -> ProcessStatus` — Cancel.
  - `wait(self, *, timeout: float | None=None, poll_interval: float=0.1) -> ProcessStatus` — Wait.
  - `watch(self, *, poll_interval: float=0.25, changes_only: bool=True) -> Iterator[ProcessEvent]` — Watch.
  - `subscribe(self, callback: Callable[[ProcessEvent], None], *, poll_interval: float=0.25, changes_only: bool=True) -> ProcessStatus` — Subscribe.
- `class Context` — Context.
  - `__init__(self, orchestrator: Orchestrator, name: str) -> None` — Init.
  - `create(self, process: str | Process | type[ProcessClass], *, arguments: tuple[tuple[JsonValue, ...], dict[str, JsonValue]] | Sequence[str]=(), restart: bool=False) -> ProcessHandle` — Create.
  - `get(self, process: str) -> ProcessHandle` — Get.
  - `status(self, process: str) -> ProcessStatus` — Status.
  - `list(self) -> tuple[ProcessStatus, ...]` — List.
  - `broadcast(self, topic: str, payload: JsonValue=None, *, scope: str='context') -> int` — Publish a live event from this context.
  - `broadcasts(self, *, after: int=0, process: str | None=None) -> tuple[BroadcastEvent, ...]` — Broadcasts.
  - `watch_broadcasts(self, *, after: int=0, process: str | None=None, poll_interval: float=0.1) -> Iterator[BroadcastEvent]` — Watch broadcasts.
  - `plan(self, process: str, *, arguments: Sequence[str]=()) -> ExecutionPlan` — Plan.
- `class Orchestrator` — Orchestrator.
  - `__init__(self, spec_path: Path) -> None` — Init.
  - `from_file(cls, path: str | Path) -> Orchestrator` — From file.
  - `from_object_spec(cls, specification: ObjectSpec) -> Orchestrator` — From object spec.
  - `from_specification(cls, specification: Specification) -> Orchestrator` — From specification.
  - `from_mapping(cls, specification: Mapping[str, JsonValue]) -> Orchestrator` — From mapping.
  - `broadcast(topic: str, payload: JsonValue=None, *, context: str, scope: str='context') -> int` — Broadcast.
  - `broadcasts(*, context: str, after: int=0, process: str | None=None) -> tuple[BroadcastEvent, ...]` — Broadcasts.
  - `close(self, *, kill_owned: bool=True) -> None` — Close.
  - `detach(self, name: str, context: str) -> None` — Detach.
  - `validate(self) -> None` — Validate.
  - `context(self, name: str) -> Context` — Context.
  - `create(self, name: str, context: str, *, arguments: Sequence[str]=(), restart: bool=False) -> ProcessHandle` — Create.
  - `get(self, name: str, context: str) -> ProcessHandle` — Get.
  - `status(self, name: str, context: str) -> ProcessStatus` — Status.
  - `watch_broadcasts(self, *, context: str, after: int=0, process: str | None=None, poll_interval: float=0.1) -> Iterator[BroadcastEvent]` — Watch broadcasts.
  - `list(self, *, context: str | None=None, name: str | None=None) -> tuple[ProcessStatus, ...]` — List.
  - `pause(self, name: str, context: str, *, recursive: bool=False) -> ProcessStatus` — Pause.
  - `resume(self, name: str, context: str, *, recursive: bool=False) -> ProcessStatus` — Resume.
  - `reset(self, name: str, context: str, *, recursive: bool=False) -> ProcessStatus` — Reset.
  - `restart(self, name: str, context: str, *, recursive: bool=False) -> ProcessStatus` — Restart.
  - `kill(self, name: str, context: str, *, recursive: bool=False) -> ProcessStatus` — Kill.
  - `cancel(self, name: str, context: str, *, recursive: bool=False) -> ProcessStatus` — Cancel.
  - `wait(self, name: str, context: str, *, timeout: float | None=None, poll_interval: float=0.1) -> ProcessStatus` — Wait.
  - `watch(self, name: str, context: str, *, poll_interval: float=0.25, changes_only: bool=True) -> Iterator[ProcessEvent]` — Watch.
  - `subscribe(self, name: str, context: str, callback: Callable[[ProcessEvent], None], *, poll_interval: float=0.25, changes_only: bool=True) -> ProcessStatus` — Subscribe.
  - `plan(self, name: str, context: str, *, arguments: Sequence[str]=()) -> ExecutionPlan` — Plan.

### `builder.py`

Object-first orchestration graph builder.

- `class ProcessPolicy` — Processpolicy.
  - `values` = `field(default_factory=dict)`
- `class CounterExecutor` — Counterexecutor.
  - `duration_seconds` = `None`
  - `tick_seconds` = `None`
  - `to_executor() -> Executor` — To executor.
- `class PythonClassExecutor` — Pythonclassexecutor.
  - Fields: `process_class: type[ProcessClass]`
  - `to_executor(self) -> Executor` — To executor.
- `class Process` — Process.
  - `executor` = `None`
  - `policy` = `None`
  - `dependencies` = `field(default_factory=list)`
  - `children` = `field(default_factory=list)`
  - `concurrency` = `None`
  - Fields: `name: str`
  - `dependency(self, target: Process | str, *, policy: ProcessPolicy | None=None) -> Dependency` — Dependency.
- `class Dependency` — Dependency.
  - `policy` = `None`
  - Fields: `target: Process | str`
  - `name(self) -> str` — Name.
  - `process(self) -> Process | None` — Process.
- `class ProcessOptions` — Processoptions.
  - Fields: `children: Iterable[Process | str]`, `concurrency: Concurrency | None`
- `class Spec` — Spec.
  - `__init__(self, *, version: int=2, global_config: GlobalConfig | None=None) -> None` — Init.
  - `processes(self) -> tuple[Process, ...]` — Processes.
  - `process(self, name: str, *, executor: CounterExecutor | PythonClassExecutor | Executor | None=None, policy: ProcessPolicy | None=None, dependencies: Iterable[Dependency | Process | str]=(), **options: Unpack[ProcessOptions]) -> Process` — Process.
  - `get(self, name: str) -> Process` — Get.
  - `to_specification(self) -> Specification` — To specification.

### `class_runner.py`

Detached runner for Python ProcessClass executors.

- `main() -> int` — Run the command-line entry point.

### `examples/__init__.py`

Comprehensive pmanager examples.


### `examples/__main__.py`

Run the pmanager example with the project virtual environment.


### `examples/api/__init__.py`

Python API example package.


### `examples/api/__main__.py`

Run the Python API example.


### `examples/api/run.py`

Comprehensive object-first pmanager API example.

- `class ApplicationWorker` — Example Python worker with lifecycle and broadcast integration.
  - `current_status() -> dict[str, str | bool]` — Return application-specific live status.
  - `on_pause(self) -> None` — Handle cooperative pause.
  - `on_resume(self) -> None` — Handle cooperative resume.
  - `configuration_changed(self, payload: ModelValue) -> None` — Receive a live event from another worker or orchestrator.
  - `before_kill(self) -> None` — Perform bounded graceful work before the mandatory hard kill.
  - `run(self, count: int=1, *, name: str='example', enabled: bool=True) -> int` — Run the example workload.
- `build_spec() -> Spec` — Build a mixed counter/class process graph with object references.
- `main() -> int` — Exercise creation, monitoring, broadcasts, planning, and cleanup.

### `examples/cli/__init__.py`

JSON-specification CLI example package.


### `examples/cli/__main__.py`

Run the CLI example.


### `examples/cli/run.py`

JSON-specification pmanager CLI example launcher.

- `class Constants` — Group module-level constants.
  - `spec` = `Path(__file__).with_name(name='processes.json')`
- `main() -> int` — Load a JSON process specification through representative CLI calls.

### `examples/run.py`

Run the comprehensive pmanager API example directly or as a package.


### `lifecycle.py`

Python process classes and lifecycle-hook decorators.

- `class Lifecycle` — Lifecycle.
  - `PAUSE` = `'pause'`
  - `RESUME` = `'resume'`
  - `RESET` = `'reset'`
  - `CANCEL` = `'cancel'`
  - `KILL` = `'kill'`
  - `STATUS` = `'status'`
- `pause(function: Callable[P, R]) -> Callable[P, R]` — Mark a method as the pause hook.
- `resume(function: Callable[P, R]) -> Callable[P, R]` — Mark a method as the resume hook.
- `reset(function: Callable[P, R]) -> Callable[P, R]` — Mark a method as the reset hook.
- `cancel(function: Callable[P, R]) -> Callable[P, R]` — Mark a method as the cancel hook.
- `kill(function: Callable[P, R]) -> Callable[P, R]` — Mark a method as the bounded pre-kill hook.
- `status(function: Callable[P, R]) -> Callable[P, R]` — Mark a method as the live status hook.
- `receive(topic: str) -> Callable[[Callable[P, R]], Callable[P, R]]` — Build a typed broadcast-receiver decorator.
- `class CallArguments` — Callarguments.
  - `args` = `()`
  - `kwargs` = `None`
- `class ProcessClass` — Processclass.
  - `process_name` = `None`
  - `kill_timeout` = `5.0`
  - `__init__(self) -> None` — Init.
  - `name(cls) -> str` — Name.
  - `configure_broadcast(self, sender: Callable[[str, ModelValue, str], int]) -> None` — Configure broadcast.
  - `broadcast(self, topic: str, payload: ModelValue=None, *, scope: str='context') -> int` — Broadcast.
  - `receive_broadcast(self, topic: str, payload: ModelValue) -> None` — Receive broadcast.
  - `lifecycle_hook(self, lifecycle: Lifecycle) -> Callable[[], ModelValue] | None` — Lifecycle hook.
  - `invoke_lifecycle(self, lifecycle: Lifecycle, timeout: float | None=None) -> bool` — Invoke lifecycle.
- `process_name(name: str) -> Callable[[type[ProcessT]], type[ProcessT]]` — Process name.

### `model.py`

Validated mutable configuration model for orchestration specifications.

- `class ModelValidationError` — Modelvalidationerror.
- `class ArgumentPolicy` — Argumentpolicy.
  - `__init__(self, policy: str='inherit', values: tuple[str, ...]=()) -> None` — Init.
  - `from_mapping(cls, data: Mapping[str, ModelValue]) -> Self` — From mapping.
  - `policy(self) -> str` — Policy.
  - `policy(self, value: str) -> None` — Policy.
  - `values(self) -> tuple[str, ...]` — Values.
  - `values(self, value: Iterable[ModelValue]) -> None` — Values.
  - `to_mapping(self) -> dict[str, ModelValue]` — To mapping.
- `class Identity` — Identity.
  - `__init__(self, *, include_arguments: bool=False) -> None` — Init.
  - `include_arguments(self) -> bool` — Include arguments.
  - `include_arguments(self, value: ModelValue) -> None` — Include arguments.
  - `to_mapping(self) -> dict[str, ModelValue]` — To mapping.
- `class Timeouts` — Timeouts.
  - `__init__(self, run_seconds: float | None=None, dependency_seconds: float | None=None, waiting_seconds: float | None=None, on_timeout: str='fail') -> None` — Init.
  - `run_seconds(self) -> float | None` — Run seconds.
  - `run_seconds(self, value: float | None) -> None` — Run seconds.
  - `dependency_seconds(self) -> float | None` — Dependency seconds.
  - `dependency_seconds(self, value: float | None) -> None` — Dependency seconds.
  - `waiting_seconds(self) -> float | None` — Set waiting seconds.
  - `waiting_seconds(self, value: float | None) -> None` — Set waiting seconds.
  - `on_timeout(self) -> str` — On timeout.
  - `on_timeout(self, value: str) -> None` — On timeout.
  - `to_mapping(self) -> dict[str, ModelValue]` — To mapping.
- `class Retry` — Retry.
  - `__init__(self, max_attempts: int=1, delay_seconds: float=1.0, backoff: float=2.0, max_delay_seconds: float=30.0) -> None` — Init.
  - `max_attempts(self) -> int` — Max attempts.
  - `max_attempts(self, value: ModelValue) -> None` — Max attempts.
  - `delay_seconds(self) -> float` — Delay seconds.
  - `delay_seconds(self, value: ModelValue) -> None` — Delay seconds.
  - `backoff(self) -> float` — Backoff.
  - `backoff(self, value: ModelValue) -> None` — Backoff.
  - `max_delay_seconds(self) -> float` — Max delay seconds.
  - `max_delay_seconds(self, value: ModelValue) -> None` — Max delay seconds.
  - `to_mapping(self) -> dict[str, ModelValue]` — To mapping.
- `class Executor` — Executor.
  - `__init__(self, type_: str='counter', command: tuple[str, ...]=(), cwd: str | None=None) -> None` — Init.
  - `type_(self) -> str` — Type.
  - `type_(self, value: str) -> None` — Type.
  - `command(self) -> tuple[str, ...]` — Command.
  - `command(self, value: Iterable[ModelValue]) -> None` — Command.
  - `cwd(self) -> str | None` — Cwd.
  - `cwd(self, value: str | None) -> None` — Cwd.
  - `to_mapping(self) -> dict[str, ModelValue]` — To mapping.
- `class ProcessReference` — Processreference.
  - Fields: `arguments: ArgumentPolicy`
  - `__init__(self, process: str, scope: str='context', completion: str='success', arguments: ArgumentPolicy | None=None) -> None` — Init.
  - `process(self) -> str` — Process.
  - `process(self, value: str) -> None` — Process.
  - `scope(self) -> str` — Scope.
  - `scope(self, value: str) -> None` — Scope.
  - `completion(self) -> str` — Completion.
  - `completion(self, value: str) -> None` — Completion.
  - `to_mapping(self) -> dict[str, ModelValue]` — To mapping.
- `class Concurrency` — Concurrency.
  - `__init__(self, group: str, scope: str='context', max_running: int=1, on_conflict: str='wait', queue: str='fifo') -> None` — Init.
  - `group(self) -> str` — Group.
  - `group(self, value: str) -> None` — Group.
  - `scope(self) -> str` — Scope.
  - `scope(self, value: str) -> None` — Scope.
  - `max_running(self) -> int` — Max running.
  - `max_running(self, value: ModelValue) -> None` — Max running.
  - `on_conflict(self) -> str` — On conflict.
  - `on_conflict(self, value: str) -> None` — On conflict.
  - `queue(self) -> str` — Queue.
  - `queue(self, value: str) -> None` — Queue.
  - `to_mapping(self) -> dict[str, ModelValue]` — To mapping.
- `class Resource` — Resource.
  - `__init__(self, capacity: int=1) -> None` — Init.
  - `capacity(self) -> int` — Capacity.
  - `capacity(self, value: ModelValue) -> None` — Capacity.
  - `to_mapping(self) -> dict[str, ModelValue]` — To mapping.
- `class GlobalConfig` — Store validated global defaults, queues, resources, and rules.
  - Fields: `defaults: dict[str, ModelValue]`, `rules: list[ModelValue]`
  - `__init__(self, defaults: dict[str, ModelValue] | None=None, queue_strategy: str='priority_fifo', resources: dict[str, Resource] | None=None, rules: list[ModelValue] | None=None) -> None` — Initialize validated global configuration.
  - `queue_strategy(self) -> str` — Return the queue strategy.
  - `queue_strategy(self, value: str) -> None` — Set and validate the queue strategy.
  - `resources(self) -> dict[str, Resource]` — Return configured resources.
  - `resources(self, value: dict[str, Resource] | dict[ModelValue, ModelValue]) -> None` — Set and validate configured resources.
  - `to_mapping(self) -> dict[str, ModelValue]` — Serialize global configuration.
- `class ProcessDefinitionFields` — Process definition fields.
  - Fields: `extends: str | None`, `executor: Executor | None`, `depends_on: list[ProcessReference] | None`, `children: list[ProcessReference] | None`, `mode: str | None`, `launch: str`, `concurrency: Concurrency | None`, `duration_seconds: float | None`, `tick_seconds: float | None`, `extra: dict[str, ModelValue] | None`
- `class Constants` — Group module-level constants.
  - `definition_field_names` = `frozenset({'extends', 'executor', 'depends_on', 'children', 'mode', 'laun...`
- `class ProcessDefinition` — Processdefinition.
  - Fields: `executor: Executor | None`, `concurrency: Concurrency | None`, `extra: dict[str, ModelValue]`
  - `__init__(self, **fields: Unpack[ProcessDefinitionFields]) -> None` — Init.
  - `extends(self) -> str | None` — Set the inherited template.
  - `extends(self, value: str | None) -> None` — Set the inherited template.
  - `mode(self) -> str | None` — Mode.
  - `mode(self, value: str | None) -> None` — Mode.
  - `launch(self) -> str` — Launch.
  - `launch(self, value: str) -> None` — Launch.
  - `duration_seconds(self) -> float | None` — Duration seconds.
  - `duration_seconds(self, value: float | None) -> None` — Duration seconds.
  - `tick_seconds(self) -> float | None` — Tick seconds.
  - `tick_seconds(self, value: float | None) -> None` — Tick seconds.
  - `depends_on(self) -> list[ProcessReference]` — Depends on.
  - `depends_on(self, value: Iterable[ProcessReference | ModelValue]) -> None` — Depends on.
  - `children(self) -> list[ProcessReference]` — Children.
  - `children(self, value: Iterable[ProcessReference | ModelValue]) -> None` — Children.
  - `to_mapping(self) -> dict[str, ModelValue]` — To mapping.
- `class Specification` — Specification.
  - `__init__(self, version: int=2, global_config: GlobalConfig | None=None, templates: dict[str, ProcessDefinition] | None=None, processes: dict[str, ProcessDefinition] | None=None) -> None` — Init.
  - `from_json(cls, value: str) -> Self` — From json.
  - `from_file(cls, path: str | Path) -> Self` — From file.
  - `from_mapping(cls, data: Mapping[str, ModelValue]) -> Self` — From mapping.
  - `version(self) -> int` — Version.
  - `version(self, value: ModelValue) -> None` — Version.
  - `global_config(self) -> GlobalConfig` — Global config.
  - `global_config(self, value: GlobalConfig | ModelValue) -> None` — Global config.
  - `templates(self) -> dict[str, ProcessDefinition]` — Templates.
  - `templates(self, value: dict[str, ProcessDefinition]) -> None` — Templates.
  - `processes(self) -> dict[str, ProcessDefinition]` — Set process definitions.
  - `processes(self, value: dict[str, ProcessDefinition]) -> None` — Set process definitions.
  - `validate_graph(self) -> None` — Validate graph.
  - `to_mapping(self) -> dict[str, ModelValue]` — To mapping.
  - `to_json(self, *, indent: int | None=2) -> str` — To json.
  - `write(self, path: str | Path) -> Path` — Write.

### `runtime.py`

Context-aware process orchestrator.

- `class Constants` — Constants.
  - `host` = `'127.0.0.1'`
  - `marker` = `'--orchestrator-worker=v2'`
  - `poll` = `0.1`
  - `bar_width` = `36`
  - `spec_name` = `'processes.json'`
  - `spec_version` = `2`
  - `percent_complete` = `100`
  - `ipc_max_bytes` = `1048576`
  - `protocol_version` = `2`
  - `kill_grace` = `5.0`
- `class State` — State.
  - `STARTING` = `'starting'`
  - `RUNNING` = `'running'`
  - `PAUSED` = `'paused'`
  - `WAITING_DEPENDENCY` = `'waiting_dependency'`
  - `WAITING_CONCURRENCY` = `'waiting_concurrency'`
  - `WAITING_RESOURCE` = `'waiting_resource'`
  - `WAITING_CHILDREN` = `'waiting_children'`
  - `COMPLETED` = `'completed'`
  - `FAILED` = `'failed'`
  - `STOPPING` = `'stopping'`
  - `KILLED` = `'killed'`
  - `CANCELLED` = `'cancelled'`
- `class Descriptor` — Descriptor.
  - `token` = `''`
  - Fields: `pid: int`, `port: int`, `name: str`, `context: str`, `args: tuple[str, ...]`
- `class Runtime` — Runtime.
  - `progress` = `0`
  - `state` = `State.STARTING`
  - `reason` = `''`
  - `exit_code` = `None`
  - `attempts` = `0`
  - `generation` = `1`
  - `children` = `field(default_factory=dict)`
  - Fields: `name: str`, `context: str`, `args: tuple[str, ...]`
- `class SpecError` — Specerror.
- `class Spec` — Spec.
  - `__init__(self, path: Path) -> None` — Init.
  - `refs(config: dict[str, JsonValue]) -> tuple[str, ...]` — Refs.
  - `validate(self) -> None` — Validate.
  - `process(self, name: str) -> dict[str, JsonValue]` — Process.
- `class Discovery` — Discovery.
  - `find(cls, name: str, context: str) -> Descriptor | None` — Find.
  - `all() -> tuple[Descriptor, ...]` — All.
- `class Client` — Client.
  - `request(descriptor: Descriptor, command: str, *, payload: dict[str, JsonValue] | None=None) -> dict[str, JsonValue]` — Request.
- `class Launcher` — Launcher.
  - `__init__(self, spec_path: Path) -> None` — Init.
  - `create(self, name: str, context: str, process_args: tuple[str, ...], *, restart: bool=False, policy_key: str='on_create') -> Descriptor` — Create.
- `class Worker` — Worker.
  - `__init__(self, runtime: Runtime, spec: Spec, port: int, token: str='') -> None` — Init.
  - `snapshot(self) -> dict[str, JsonValue]` — Snapshot.
  - `refs(self, key: str) -> tuple[str, ...]` — Refs.
  - `execute(self) -> None` — Execute.
  - `serve(self) -> None` — Serve.
- `class Cli` — Cli.
  - `CONTROL` = `{'--kill', '-k', '--pause', '-p', '--start', '-s', '--reset', '-r', '--in...`
  - `OBSERVE_COMMANDS` = `{'-k': 'kill', '--kill': 'kill', '-p': 'pause', '--pause': 'pause', '-s':...`
  - `split_args(cls, values: list[str]) -> tuple[list[str], tuple[str, ...]]` — Split args.
  - `main(cls, values: list[str]) -> int` — Run the command-line entry point.
  - `render(info: dict[str, JsonValue]) -> str` — Render.
  - `tree(spec: Spec, context: str) -> str` — Tree.
- `main() -> int` — Run the command-line entry point.

## Examples

Runnable demonstration for `exactus/packages/pmanager/`.

Run the comprehensive pmanager API example directly or as a package.

```bash
python -m exactus.packages.pmanager.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/api/README.md`, `examples/api/__init__.py`, `examples/api/__main__.py`, `examples/api/run.py`, `examples/cli/README.md`, `examples/cli/__init__.py`, `examples/cli/__main__.py`, `examples/cli/processes.json`, `examples/cli/run.py`, `examples/run.py`

## Dependencies and consumers

- Used by: `__main__.py`, `tests/common/check/test_check_extra.py`, `tests/packages/pmanager/test_api.py`, `tests/packages/pmanager/test_api_extended.py`, `tests/packages/pmanager/test_broadcast.py`, `tests/packages/pmanager/test_class_runner.py`, `tests/packages/pmanager/test_core.py`, `tests/packages/pmanager/test_example_run.py`, `tests/packages/pmanager/test_examples.py`, `tests/packages/pmanager/test_model.py`, `tests/packages/pmanager/test_object_api.py`, `tests/packages/pmanager/test_platform.py`, `tests/packages/pmanager/test_spec.py`, `tests/tools/common/test_execution.py`, `tests/tools/common/test_pipeline_output.py`, `tests/tools/common/test_tool_worker.py`, `tools/common/api.py`, `tools/common/execution.py`, `tools/common/tool_worker.py`

## Tests

Tests live in `exactus/tests/packages/pmanager/`.

- `test_api.py` — Public API contract tests. (3 tests)
  - `test_public_api_missing_status`
  - `test_public_api_plan_and_context`
  - `test_public_state_contract_includes_paused`
- `test_api_extended.py` — Extended public API tests. (10 tests)
  - `test_closed_scope_and_close_cleanup`
  - `test_context_manager_ownership_and_detach`
  - `test_controls_context_and_recursive`
  - `test_create_plan_and_launcher_error`
  - `test_generation_is_exposed_in_public_status`
  - `test_handle_forwarders_and_context_status`
  - `test_list_filters_and_status_conversion`
  - `test_mapping_validate_get_and_properties`
  - `test_missing_and_transport_errors`
  - `test_wait_watch_subscribe_and_timeout`
- `test_broadcast.py` — Live worker broadcast integration tests. (1 tests)
  - `test_context_broadcast_reaches_other_worker_and_api`
- `test_class_runner.py` — Unit tests for the detached class-runner entry module. (17 tests)
  - `test_broadcast_sender_delivers`
  - `test_broadcast_sender_fails_closed`
  - `test_call_arguments_ignores_non_mapping`
  - `test_call_arguments_parses_orchestrator_call`
  - `test_call_arguments_plain_values`
  - `test_call_arguments_rejects_bad_members`
  - `test_control_value`
  - `test_event_receiver_dispatches`
  - `test_main_requires_module_and_class`
  - `test_main_runs_class_with_orchestrator_arguments`
  - `test_resolve_rejects_non_process_class`
  - `test_resolve_returns_process_class`
  - `test_run_status_hook_returns_result`
  - `test_run_status_hook_translates_errors`
  - `test_signal_handlers_invoke_lifecycle`
  - `test_status_server_answers_requests`
  - `test_status_server_reports_non_serializable`
- `test_core.py` — Behavior tests for the orchestration engine. (20 tests)
  - `test_authenticated_serve_controls_executor`
  - `test_cli_helpers_and_main`
  - `test_cli_loads_a_json_spec_file`
  - `test_cli_observe_create_and_errors`
  - `test_cli_worker_tree_status_and_live`
  - `test_client_request`
  - `test_discovery_and_find`
  - `test_fanout_disappearance_is_failure`
  - `test_launcher_honors_existing_state_policy`
  - `test_launcher_real_worker`
  - `test_launcher_timeout`
  - `test_module_main_success_and_error`
  - `test_obsolete_generation_cannot_publish_completion`
  - `test_spec_errors_and_helpers`
  - `test_wait_for_disappeared_dependency`
  - `test_worker_command_and_failure`
  - `test_worker_concurrency_and_fanout`
  - `test_worker_ensure_command_fanout_execute`
  - `test_worker_serve_protocol`
  - `test_worker_state_counter_and_wait`
- `test_example_run.py` — Cover the bundled ``pmanager`` example entry point. (1 tests)
  - `test_example_module_runs_as_a_script`
- `test_examples.py` — Exercise the bundled pmanager examples as user-facing documentation. (5 tests)
  - `test_api_example_runs_end_to_end`
  - `test_application_worker_run_records_invocation`
  - `test_build_spec_defines_the_pipeline_graph`
  - `test_cli_example_loads_a_json_specification`
  - `test_example_entrypoint_delegates_to_api`
- `test_model.py` — Typed specification model contract tests. (7 tests)
  - `test_global_and_process_definition_validation`
  - `test_graph_validation_rejects_unknown_reference`
  - `test_mutable_validated_properties`
  - `test_programmatic_graph_and_orchestrator`
  - `test_reference_concurrency_resource_validation`
  - `test_round_trip_existing_specification`
  - `test_validation_branches_and_serializers`
- `test_object_api.py` — Object-first API tests. (6 tests)
  - `test_builder_validation_and_reference_edges`
  - `test_lifecycle_hook_and_broadcast_dispatch`
  - `test_lifecycle_hooks_and_kill_timeout`
  - `test_object_references_are_retained`
  - `test_policy_is_compiled`
  - `test_status_decorator_marks_status_hook`
- `test_platform.py` — Cross-platform backend contract tests. (5 tests)
  - `test_posix_backend`
  - `test_posix_proc_discovery`
  - `test_windows_discovery_and_detach`
  - `test_windows_pause_resume`
  - `test_windows_terminate`
- `test_spec.py` — Specification smoke tests. (3 tests)
  - `test_c_is_global_singleton_runner`
  - `test_e_is_parallel_join`
  - `test_spec_has_all_examples`

<!-- exactus:reference:end -->
