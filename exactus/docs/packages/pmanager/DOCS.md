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
| `examples/` | Run the comprehensive API example with any of: ```bash python -m exactus.packages.pmanager.examples |
| `lifecycle.py` | Python process classes and lifecycle-hook decorators. |
| `model.py` | Validated mutable configuration model for orchestration specifications. |
| `processes.json` | — |
| `py.typed` | — |
| `runtime.py` | Context-aware process orchestrator. |

Run it as a module: `python -m exactus.packages.pmanager`.

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `_platform.py`

Cross-platform process primitives used by the orchestrator.

- `class PlatformError(RuntimeError)` — Platformerror.
- `class ProcessBackend(ABC)` — Define platform-specific process operations.
  - `command_lines() -> tuple[tuple[int, str], ...]` — Return visible process command lines.
  - `detached_kwargs() -> dict[str, bool | int]` — Return detached-spawn metadata for diagnostics.
  - `spawn(command: list[str]) -> Popen[bytes]` — Spawn one detached process.
  - `pause(pid: int) -> None` — Pause a process.
  - `resume(pid: int) -> None` — Resume a process.
  - `terminate(pid: int) -> None` — Terminate a process.
- `class PosixBackend(ProcessBackend)` — Posixbackend.
  - `command_lines() -> tuple[tuple[int, str], ...]` — Command lines.
  - `detached_kwargs() -> dict[str, bool | int]` — Detached kwargs.
  - `spawn(command: list[str]) -> Popen[bytes]` — Spawn one detached POSIX process.
  - `pause(pid: int) -> None` — Pause.
  - `resume(pid: int) -> None` — Resume.
  - `terminate(pid: int) -> None` — Terminate.
- `class WindowsBackend(ProcessBackend)` — Windowsbackend.
  - `powershell_process_action(pid: int, method: str) -> None` — Powershell process action.
  - `command_lines() -> tuple[tuple[int, str], ...]` — Command lines.
  - `detached_kwargs() -> dict[str, bool | int]` — Detached kwargs.
  - `spawn(command: list[str]) -> Popen[bytes]` — Spawn one detached Windows process.
  - `pause(pid: int) -> None` — Pause.
  - `resume(pid: int) -> None` — Resume.
  - `terminate(pid: int) -> None` — Terminate.
- `backend() -> ProcessBackend` — Backend.

### `api.py`

Stable Python-first API for the context-aware process orchestrator.

- `class Constants` — Group module-level constants.
  - `structured_argument_parts` = `2`
- `class OrchestratorError(RuntimeError)` — Orchestratorerror.
- `class ProcessNotFoundError(OrchestratorError)` — Processnotfounderror.
- `class WaitTimeoutError(OrchestratorError)` — Waittimeouterror.
- `class ProcessAction(Enum)` — Processaction.
- `class BroadcastEvent` — Broadcastevent.
  - Fields: `id: int`, `topic: str`, `payload: JsonValue`, `source: str`, `context: str`, `generation: int`, `timestamp: float`
- `class ProcessKey` — Processkey.
  - Fields: `name: str`, `context: str`, `arguments: tuple[str, ...]`
- `class ProcessStatus` — Processstatus.
  - Fields: `key: ProcessKey`, `state: State`, `progress: int`, `pid: int | None`, `reason: str`, `exit_code: int | None`, `attempts: int`, `generation: int`, `children: Mapping[str, JsonValue]`, `custom_status: JsonValue`
  - `terminal() -> bool` — Terminal.
  - `successful() -> bool` — Successful.
  - `live() -> bool` — Live.
- `class ProcessEvent` — Processevent.
  - Fields: `status: ProcessStatus`, `previous_state: State | None`
- `class PlanEntry` — Planentry.
  - Fields: `key: ProcessKey`, `action: str`, `pid: int | None`
- `class ExecutionPlan` — Executionplan.
  - Fields: `root: ProcessKey`, `entries: tuple[PlanEntry, ...]`
- `class ProcessHandle` — Processhandle.
  - `status() -> ProcessStatus` — Status.
  - `pause(*, recursive: bool=False) -> ProcessStatus` — Pause.
  - `resume(*, recursive: bool=False) -> ProcessStatus` — Resume.
  - `reset(*, recursive: bool=False) -> ProcessStatus` — Reset.
  - `restart(*, recursive: bool=False) -> ProcessStatus` — Restart.
  - `kill(*, recursive: bool=False) -> ProcessStatus` — Kill.
  - `cancel(*, recursive: bool=False) -> ProcessStatus` — Cancel.
  - `wait(*, timeout: float | None=None, poll_interval: float=0.1) -> ProcessStatus` — Wait.
  - `watch(*, poll_interval: float=0.25, changes_only: bool=True) -> Iterator[ProcessEvent]` — Watch.
  - `subscribe(callback: Callable[[ProcessEvent], None], *, poll_interval: float=0.25, changes_only: bool=True) -> ProcessStatus` — Subscribe.
- `class Context` — Context.
  - `create(process: str | Process | type[ProcessClass], *, arguments: tuple[tuple[JsonValue, ...], dict[str, JsonValue]] | Sequence[str]=(), restart: bool=False) -> ProcessHandle` — Create.
  - `get(process: str) -> ProcessHandle` — Get.
  - `status(process: str) -> ProcessStatus` — Status.
  - `list() -> tuple[ProcessStatus, ...]` — List.
  - `broadcast(topic: str, payload: JsonValue=None, *, scope: str='context') -> int` — Publish a live event from this context.
  - `broadcasts(*, after: int=0, process: str | None=None) -> tuple[BroadcastEvent, ...]` — Broadcasts.
  - `watch_broadcasts(*, after: int=0, process: str | None=None, poll_interval: float=0.1) -> Iterator[BroadcastEvent]` — Watch broadcasts.
  - `plan(process: str, *, arguments: Sequence[str]=()) -> ExecutionPlan` — Plan.
- `class Orchestrator` — Orchestrator.
  - `from_file(path: str | Path) -> Orchestrator` — From file.
  - `from_object_spec(specification: ObjectSpec) -> Orchestrator` — From object spec.
  - `from_specification(specification: Specification) -> Orchestrator` — From specification.
  - `from_mapping(specification: Mapping[str, JsonValue]) -> Orchestrator` — From mapping.
  - `broadcast(topic: str, payload: JsonValue=None, *, context: str, scope: str='context') -> int` — Broadcast.
  - `broadcasts(*, context: str, after: int=0, process: str | None=None) -> tuple[BroadcastEvent, ...]` — Broadcasts.
  - `close(*, kill_owned: bool=True) -> None` — Close.
  - `detach(name: str, context: str) -> None` — Detach.
  - `validate() -> None` — Validate.
  - `context(name: str) -> Context` — Context.
  - `create(name: str, context: str, *, arguments: Sequence[str]=(), restart: bool=False) -> ProcessHandle` — Create.
  - `get(name: str, context: str) -> ProcessHandle` — Get.
  - `status(name: str, context: str) -> ProcessStatus` — Status.
  - `watch_broadcasts(*, context: str, after: int=0, process: str | None=None, poll_interval: float=0.1) -> Iterator[BroadcastEvent]` — Watch broadcasts.
  - `list(*, context: str | None=None, name: str | None=None) -> tuple[ProcessStatus, ...]` — List.
  - `pause(name: str, context: str, *, recursive: bool=False) -> ProcessStatus` — Pause.
  - `resume(name: str, context: str, *, recursive: bool=False) -> ProcessStatus` — Resume.
  - `reset(name: str, context: str, *, recursive: bool=False) -> ProcessStatus` — Reset.
  - `restart(name: str, context: str, *, recursive: bool=False) -> ProcessStatus` — Restart.
  - `kill(name: str, context: str, *, recursive: bool=False) -> ProcessStatus` — Kill.
  - `cancel(name: str, context: str, *, recursive: bool=False) -> ProcessStatus` — Cancel.
  - `wait(name: str, context: str, *, timeout: float | None=None, poll_interval: float=0.1) -> ProcessStatus` — Wait.
  - `watch(name: str, context: str, *, poll_interval: float=0.25, changes_only: bool=True) -> Iterator[ProcessEvent]` — Watch.
  - `subscribe(name: str, context: str, callback: Callable[[ProcessEvent], None], *, poll_interval: float=0.25, changes_only: bool=True) -> ProcessStatus` — Subscribe.
  - `plan(name: str, context: str, *, arguments: Sequence[str]=()) -> ExecutionPlan` — Plan.

### `builder.py`

Object-first orchestration graph builder.

- `class ProcessPolicy` — Processpolicy.
  - Fields: `values: dict[str, ModelValue]`
- `class CounterExecutor` — Counterexecutor.
  - Fields: `duration_seconds: float | None`, `tick_seconds: float | None`
  - `to_executor() -> Executor` — To executor.
- `class PythonClassExecutor` — Pythonclassexecutor.
  - Fields: `process_class: type[ProcessClass]`
  - `to_executor() -> Executor` — To executor.
- `class Process` — Process.
  - Fields: `name: str`, `executor: CounterExecutor | PythonClassExecutor | Executor | None`, `policy: ProcessPolicy | None`, `dependencies: list[Dependency]`, `children: list[Process | str]`, `concurrency: Concurrency | None`
  - `dependency(target: Process | str, *, policy: ProcessPolicy | None=None) -> Dependency` — Dependency.
- `class Dependency` — Dependency.
  - Fields: `target: Process | str`, `policy: ProcessPolicy | None`
  - `name() -> str` — Name.
  - `process() -> Process | None` — Process.
- `class ProcessOptions(TypedDict)` — Processoptions.
- `class Spec` — Spec.
  - `processes() -> tuple[Process, ...]` — Processes.
  - `process(name: str, *, executor: CounterExecutor | PythonClassExecutor | Executor | None=None, policy: ProcessPolicy | None=None, dependencies: Iterable[Dependency | Process | str]=(), **options: Unpack[ProcessOptions]) -> Process` — Process.
  - `get(name: str) -> Process` — Get.
  - `to_specification() -> Specification` — To specification.

### `class_runner.py`

Detached runner for Python ProcessClass executors.

- `main() -> int` — Run the command-line entry point.

### `lifecycle.py`

Python process classes and lifecycle-hook decorators.

- `class Lifecycle(StrEnum)` — Lifecycle.
- `pause(function: Callable[P, R]) -> Callable[P, R]` — Mark a method as the pause hook.
- `resume(function: Callable[P, R]) -> Callable[P, R]` — Mark a method as the resume hook.
- `reset(function: Callable[P, R]) -> Callable[P, R]` — Mark a method as the reset hook.
- `cancel(function: Callable[P, R]) -> Callable[P, R]` — Mark a method as the cancel hook.
- `kill(function: Callable[P, R]) -> Callable[P, R]` — Mark a method as the bounded pre-kill hook.
- `status(function: Callable[P, R]) -> Callable[P, R]` — Mark a method as the live status hook.
- `receive(topic: str) -> Callable[[Callable[P, R]], Callable[P, R]]` — Build a typed broadcast-receiver decorator.
- `class CallArguments` — Callarguments.
  - Fields: `args: tuple[ModelValue, ...]`, `kwargs: dict[str, ModelValue] | None`
- `class ProcessClass` — Processclass.
  - `name() -> str` — Name.
  - `configure_broadcast(sender: Callable[[str, ModelValue, str], int]) -> None` — Configure broadcast.
  - `broadcast(topic: str, payload: ModelValue=None, *, scope: str='context') -> int` — Broadcast.
  - `receive_broadcast(topic: str, payload: ModelValue) -> None` — Receive broadcast.
  - `lifecycle_hook(lifecycle: Lifecycle) -> Callable[[], ModelValue] | None` — Lifecycle hook.
  - `invoke_lifecycle(lifecycle: Lifecycle, timeout: float | None=None) -> bool` — Invoke lifecycle.
- `process_name(name: str) -> Callable[[type[ProcessT]], type[ProcessT]]` — Process name.

### `model.py`

Validated mutable configuration model for orchestration specifications.

- `class ModelValidationError(ValueError)` — Modelvalidationerror.
- `class ArgumentPolicy` — Argumentpolicy.
  - `from_mapping(data: Mapping[str, ModelValue]) -> Self` — From mapping.
  - `policy() -> str` — Policy.
  - `policy(value: str) -> None` — Policy.
  - `values() -> tuple[str, ...]` — Values.
  - `values(value: Iterable[ModelValue]) -> None` — Values.
  - `to_mapping() -> dict[str, ModelValue]` — To mapping.
- `class Identity` — Identity.
  - `include_arguments() -> bool` — Include arguments.
  - `include_arguments(value: ModelValue) -> None` — Include arguments.
  - `to_mapping() -> dict[str, ModelValue]` — To mapping.
- `class Timeouts` — Timeouts.
  - `run_seconds() -> float | None` — Run seconds.
  - `run_seconds(value: float | None) -> None` — Run seconds.
  - `dependency_seconds() -> float | None` — Dependency seconds.
  - `dependency_seconds(value: float | None) -> None` — Dependency seconds.
  - `waiting_seconds() -> float | None` — Set waiting seconds.
  - `waiting_seconds(value: float | None) -> None` — Set waiting seconds.
  - `on_timeout() -> str` — On timeout.
  - `on_timeout(value: str) -> None` — On timeout.
  - `to_mapping() -> dict[str, ModelValue]` — To mapping.
- `class Retry` — Retry.
  - `max_attempts() -> int` — Max attempts.
  - `max_attempts(value: ModelValue) -> None` — Max attempts.
  - `delay_seconds() -> float` — Delay seconds.
  - `delay_seconds(value: ModelValue) -> None` — Delay seconds.
  - `backoff() -> float` — Backoff.
  - `backoff(value: ModelValue) -> None` — Backoff.
  - `max_delay_seconds() -> float` — Max delay seconds.
  - `max_delay_seconds(value: ModelValue) -> None` — Max delay seconds.
  - `to_mapping() -> dict[str, ModelValue]` — To mapping.
- `class Executor` — Executor.
  - `type_() -> str` — Type.
  - `type_(value: str) -> None` — Type.
  - `command() -> tuple[str, ...]` — Command.
  - `command(value: Iterable[ModelValue]) -> None` — Command.
  - `cwd() -> str | None` — Cwd.
  - `cwd(value: str | None) -> None` — Cwd.
  - `to_mapping() -> dict[str, ModelValue]` — To mapping.
- `class ProcessReference` — Processreference.
  - Fields: `arguments: ArgumentPolicy`
  - `process() -> str` — Process.
  - `process(value: str) -> None` — Process.
  - `scope() -> str` — Scope.
  - `scope(value: str) -> None` — Scope.
  - `completion() -> str` — Completion.
  - `completion(value: str) -> None` — Completion.
  - `to_mapping() -> dict[str, ModelValue]` — To mapping.
- `class Concurrency` — Concurrency.
  - `group() -> str` — Group.
  - `group(value: str) -> None` — Group.
  - `scope() -> str` — Scope.
  - `scope(value: str) -> None` — Scope.
  - `max_running() -> int` — Max running.
  - `max_running(value: ModelValue) -> None` — Max running.
  - `on_conflict() -> str` — On conflict.
  - `on_conflict(value: str) -> None` — On conflict.
  - `queue() -> str` — Queue.
  - `queue(value: str) -> None` — Queue.
  - `to_mapping() -> dict[str, ModelValue]` — To mapping.
- `class Resource` — Resource.
  - `capacity() -> int` — Capacity.
  - `capacity(value: ModelValue) -> None` — Capacity.
  - `to_mapping() -> dict[str, ModelValue]` — To mapping.
- `class GlobalConfig` — Store validated global defaults, queues, resources, and rules.
  - Fields: `defaults: dict[str, ModelValue]`, `rules: list[ModelValue]`
  - `queue_strategy() -> str` — Return the queue strategy.
  - `queue_strategy(value: str) -> None` — Set and validate the queue strategy.
  - `resources() -> dict[str, Resource]` — Return configured resources.
  - `resources(value: dict[str, Resource] | dict[ModelValue, ModelValue]) -> None` — Set and validate configured resources.
  - `to_mapping() -> dict[str, ModelValue]` — Serialize global configuration.
- `class ProcessDefinitionFields(TypedDict)` — Process definition fields.
- `class Constants` — Group module-level constants.
  - `definition_field_names` = `frozenset({'extends', 'executor', 'depends_on', 'children', 'mode',...`
- `class ProcessDefinition` — Processdefinition.
  - Fields: `executor: Executor | None`, `concurrency: Concurrency | None`, `extra: dict[str, ModelValue]`
  - `extends() -> str | None` — Set the inherited template.
  - `extends(value: str | None) -> None` — Set the inherited template.
  - `mode() -> str | None` — Mode.
  - `mode(value: str | None) -> None` — Mode.
  - `launch() -> str` — Launch.
  - `launch(value: str) -> None` — Launch.
  - `duration_seconds() -> float | None` — Duration seconds.
  - `duration_seconds(value: float | None) -> None` — Duration seconds.
  - `tick_seconds() -> float | None` — Tick seconds.
  - `tick_seconds(value: float | None) -> None` — Tick seconds.
  - `depends_on() -> list[ProcessReference]` — Depends on.
  - `depends_on(value: Iterable[ProcessReference | ModelValue]) -> None` — Depends on.
  - `children() -> list[ProcessReference]` — Children.
  - `children(value: Iterable[ProcessReference | ModelValue]) -> None` — Children.
  - `to_mapping() -> dict[str, ModelValue]` — To mapping.
- `class Specification` — Specification.
  - `from_json(value: str) -> Self` — From json.
  - `from_file(path: str | Path) -> Self` — From file.
  - `from_mapping(data: Mapping[str, ModelValue]) -> Self` — From mapping.
  - `version() -> int` — Version.
  - `version(value: ModelValue) -> None` — Version.
  - `global_config() -> GlobalConfig` — Global config.
  - `global_config(value: GlobalConfig | ModelValue) -> None` — Global config.
  - `templates() -> dict[str, ProcessDefinition]` — Templates.
  - `templates(value: dict[str, ProcessDefinition]) -> None` — Templates.
  - `processes() -> dict[str, ProcessDefinition]` — Set process definitions.
  - `processes(value: dict[str, ProcessDefinition]) -> None` — Set process definitions.
  - `validate_graph() -> None` — Validate graph.
  - `to_mapping() -> dict[str, ModelValue]` — To mapping.
  - `to_json(*, indent: int | None=2) -> str` — To json.
  - `write(path: str | Path) -> Path` — Write.

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
- `class State(Enum)` — State.
- `class Descriptor` — Descriptor.
  - Fields: `pid: int`, `port: int`, `name: str`, `context: str`, `args: tuple[str, ...]`, `token: str`
- `class Runtime` — Runtime.
  - Fields: `name: str`, `context: str`, `args: tuple[str, ...]`, `progress: int`, `state: State`, `reason: str`, `exit_code: int | None`, `attempts: int`, `generation: int`, `children: dict[str, JsonValue]`
- `class SpecError(RuntimeError)` — Specerror.
- `class Spec` — Spec.
  - `refs(config: dict[str, JsonValue]) -> tuple[str, ...]` — Refs.
  - `validate() -> None` — Validate.
  - `process(name: str) -> dict[str, JsonValue]` — Process.
- `class Discovery` — Discovery.
  - `find(name: str, context: str) -> Descriptor | None` — Find.
  - `all() -> tuple[Descriptor, ...]` — All.
- `class Client` — Client.
  - `request(descriptor: Descriptor, command: str, *, payload: dict[str, JsonValue] | None=None) -> dict[str, JsonValue]` — Request.
- `class Launcher` — Launcher.
  - `create(name: str, context: str, process_args: tuple[str, ...], *, restart: bool=False, policy_key: str='on_create') -> Descriptor` — Create.
- `class Worker` — Worker.
  - `snapshot() -> dict[str, JsonValue]` — Snapshot.
  - `refs(key: str) -> tuple[str, ...]` — Refs.
  - `execute() -> None` — Execute.
  - `serve() -> None` — Serve.
- `class Cli` — Cli.
  - `split_args(values: list[str]) -> tuple[list[str], tuple[str, ...]]` — Split args.
  - `main(values: list[str]) -> int` — Run the command-line entry point.
  - `render(info: dict[str, JsonValue]) -> str` — Render.
  - `tree(spec: Spec, context: str) -> str` — Tree.
- `main() -> int` — Run the command-line entry point.

## Examples

Run the comprehensive API example with any of:

```bash
python -m exactus.packages.pmanager.examples
python -m exactus.packages.pmanager.examples.api
```

Run the JSON-specification CLI example with:

```bash
python -m exactus.packages.pmanager.examples.cli
```

Files: `__init__.py`, `__main__.py`, `api/__init__.py`, `api/__main__.py`, `api/run.py`, `cli/__init__.py`, `cli/__main__.py`, `cli/processes.json`, `cli/run.py`, `run.py`

## Dependencies and consumers

- No dependencies outside the standard library.
- Used by: `__main__.py`, `tests/common/check/test_check_extra.py`, `tests/common/package/test_package_independence.py`, `tests/tools/common/test_common_package.py`, `tests/tools/common/test_execution.py`, `tests/tools/common/test_pipeline_output.py`, `tests/tools/common/test_tool_worker.py`, `tools/common/api.py`, `tools/common/execution.py`, `tools/common/tool_worker.py`

## Tests

Tests live in `exactus/tests/packages/pmanager/`.

- `test_api.py` — Public API contract tests. (3 tests)
  - `test_public_api_plan_and_context`
  - `test_public_api_missing_status`
  - `test_public_state_contract_includes_paused`
- `test_api_extended.py` — Extended public API tests. (10 tests)
  - `test_mapping_validate_get_and_properties`
  - `test_list_filters_and_status_conversion`
  - `test_controls_context_and_recursive`
  - `test_create_plan_and_launcher_error`
  - `test_wait_watch_subscribe_and_timeout`
  - `test_missing_and_transport_errors`
  - `test_context_manager_ownership_and_detach`
  - `test_generation_is_exposed_in_public_status`
  - `test_handle_forwarders_and_context_status`
  - `test_closed_scope_and_close_cleanup`
- `test_broadcast.py` — Live worker broadcast integration tests. (1 tests)
  - `test_context_broadcast_reaches_other_worker_and_api`
- `test_class_runner.py` — Unit tests for the detached class-runner entry module. (17 tests)
  - `test_resolve_returns_process_class`
  - `test_resolve_rejects_non_process_class`
  - `test_call_arguments_plain_values`
  - `test_call_arguments_parses_orchestrator_call`
  - `test_call_arguments_ignores_non_mapping`
  - `test_call_arguments_rejects_bad_members`
  - `test_control_value`
  - `test_run_status_hook_returns_result`
  - `test_run_status_hook_translates_errors`
  - `test_status_server_answers_requests`
  - `test_status_server_reports_non_serializable`
  - `test_broadcast_sender_delivers`
  - `test_broadcast_sender_fails_closed`
  - `test_event_receiver_dispatches`
  - `test_main_requires_module_and_class`
  - `test_main_runs_class_with_orchestrator_arguments`
  - `test_signal_handlers_invoke_lifecycle`
- `test_core.py` — Behavior tests for the orchestration engine. (20 tests)
  - `test_spec_errors_and_helpers`
  - `test_discovery_and_find`
  - `test_client_request`
  - `test_worker_state_counter_and_wait`
  - `test_worker_ensure_command_fanout_execute`
  - `test_cli_helpers_and_main`
  - `test_cli_loads_a_json_spec_file`
  - `test_launcher_real_worker`
  - `test_worker_concurrency_and_fanout`
  - `test_worker_command_and_failure`
  - `test_cli_observe_create_and_errors`
  - `test_worker_serve_protocol`
  - `test_cli_worker_tree_status_and_live`
  - `test_module_main_success_and_error`
  - `test_launcher_timeout`
  - `test_wait_for_disappeared_dependency`
  - `test_fanout_disappearance_is_failure`
  - `test_obsolete_generation_cannot_publish_completion`
  - `test_authenticated_serve_controls_executor`
  - `test_launcher_honors_existing_state_policy`
- `test_example_run.py` — Cover the bundled ``pmanager`` example entry point. (1 tests)
  - `test_example_module_runs_as_a_script`
- `test_examples.py` — Exercise the bundled pmanager examples as user-facing documentation. (5 tests)
  - `test_example_entrypoint_delegates_to_api`
  - `test_build_spec_defines_the_pipeline_graph`
  - `test_cli_example_loads_a_json_specification`
  - `test_api_example_runs_end_to_end`
  - `test_application_worker_run_records_invocation`
- `test_model.py` — Typed specification model contract tests. (7 tests)
  - `test_mutable_validated_properties`
  - `test_round_trip_existing_specification`
  - `test_programmatic_graph_and_orchestrator`
  - `test_graph_validation_rejects_unknown_reference`
  - `test_validation_branches_and_serializers`
  - `test_reference_concurrency_resource_validation`
  - `test_global_and_process_definition_validation`
- `test_object_api.py` — Object-first API tests. (6 tests)
  - `test_object_references_are_retained`
  - `test_policy_is_compiled`
  - `test_lifecycle_hooks_and_kill_timeout`
  - `test_status_decorator_marks_status_hook`
  - `test_lifecycle_hook_and_broadcast_dispatch`
  - `test_builder_validation_and_reference_edges`
- `test_platform.py` — Cross-platform backend contract tests. (4 tests)
  - `test_posix_backend`
  - `test_windows_discovery_and_detach`
  - `test_windows_pause_resume`
  - `test_windows_terminate`
- `test_spec.py` — Specification smoke tests. (3 tests)
  - `test_spec_has_all_examples`
  - `test_e_is_parallel_join`
  - `test_c_is_global_singleton_runner`

<!-- exactus:reference:end -->
