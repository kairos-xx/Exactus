# Copyright (c) 2026 Project contributors
"""Verify that run variables expand with key and index paths."""

from __future__ import annotations

from json import loads
from typing import TYPE_CHECKING, cast

import pytest

from exactus.tests.common.support import expect_equal, private, private_as
from exactus.tools.record.flow_runner import FlowRunner
from exactus.tools.record.selector_sandbox import RunStreams
from exactus.tools.record.store import WorkspaceCodec
from exactus.tools.record.studio import controller as controller_module
from exactus.tools.record.studio.service import StudioService

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.model import Flow, RuntimeVariable, Workspace


def _expanded(*, tmp_path: Path, text: str) -> str | None:
    """Expand a template against two sample variables.

    Args:
        tmp_path: Disposable artifact folder.
        text: Authored text holding variable tokens.

    Returns:
        The expanded text.

    """
    runner: FlowRunner = FlowRunner(output=tmp_path)
    streams: RunStreams = private_as(
        owner=runner,
        name="_streams",
        kind=RunStreams,
    )
    streams.vars["JavaScript Result"] = [{"url": "https://a.test"}]
    streams.vars["Count"] = 3
    expand: Callable[..., str | None] = cast(
        typ="Callable[..., str | None]",
        val=private(owner=runner, name="_template"),
    )
    return expand(value=text)


def test_names_with_spaces_expand_whole(tmp_path: Path) -> None:
    """Expand a whole variable whose name holds a space.

    Args:
        tmp_path: Disposable artifact folder.

    """
    expect_equal(
        actual=_expanded(tmp_path=tmp_path, text="n={{Count}}"),
        expected="n=3",
    )


def test_index_and_key_paths_expand(tmp_path: Path) -> None:
    """Address a nested value by index then key.

    Args:
        tmp_path: Disposable artifact folder.

    """
    expect_equal(
        actual=_expanded(
            tmp_path=tmp_path,
            text="{{JavaScript Result[0].url}}",
        ),
        expected="https://a.test",
    )


def test_unresolved_paths_stay_untouched(tmp_path: Path) -> None:
    """Keep a token whose path does not exist.

    Args:
        tmp_path: Disposable artifact folder.

    """
    expect_equal(
        actual=_expanded(tmp_path=tmp_path, text="{{Count.missing}}"),
        expected="{{Count.missing}}",
    )


def test_getters_read_a_whole_list_or_dictionary(tmp_path: Path) -> None:
    """Count, list keys and list values of structured results.

    Args:
        tmp_path: Disposable artifact folder.

    """
    expect_equal(
        actual=_expanded(
            tmp_path=tmp_path,
            text="{{JavaScript Result|count}}",
        ),
        expected="1",
    )
    expect_equal(
        actual=_expanded(
            tmp_path=tmp_path,
            text="{{JavaScript Result[0]|keys}}",
        ),
        expected='["url"]',
    )
    expect_equal(
        actual=_expanded(
            tmp_path=tmp_path,
            text="{{JavaScript Result[0]|values}}",
        ),
        expected='["https://a.test"]',
    )
    expect_equal(
        actual=_expanded(tmp_path=tmp_path, text="{{Count|keys}}"),
        expected="{{Count|keys}}",
    )


def test_ask_each_time_answers_fill_actions(tmp_path: Path) -> None:
    """Substitute per-run answers without touching the saved flow.

    Args:
        tmp_path: Disposable project folder.

    """
    service: StudioService = StudioService(root=tmp_path, headless=True)
    service.start()
    try:
        _ = service.controller.dispatch(
            command="event.add",
            payload={
                "kind": "javascript",
                "payload": "log('{{ask:Customer}}')",
            },
            revision=cast(typ="int", val=service.snapshot()["revision"]),
        )
        fill: Callable[..., Workspace] = cast(
            typ="Callable[..., Workspace]",
            val=private(owner=controller_module, name="_with_inputs"),
        )
        filled: Workspace = fill(
            workspace=service.controller.workspace,
            inputs={"Customer": "Ana"},
        )
        expect_equal(
            actual=filled.flows[0].events[0].payload,
            expected="log('Ana')",
        )
        expect_equal(
            actual=service.controller.workspace.flows[0].events[0].payload,
            expected="log('{{ask:Customer}}')",
        )
        with pytest.raises(
            expected_exception=ValueError,
            match="Provide a value",
        ):
            _ = fill(workspace=service.controller.workspace, inputs={})
    finally:
        service.stop()


def test_retired_receive_previous_becomes_a_variable(tmp_path: Path) -> None:
    """Name the earlier result and read it by name after loading an old file.

    Args:
        tmp_path: Disposable project folder.

    """
    service: StudioService = StudioService(root=tmp_path, headless=True)
    service.start()
    try:
        for payload in ("1 + 1", "log('{{previous}}')"):
            _ = service.controller.dispatch(
                command="event.add",
                payload={"kind": "javascript", "payload": payload},
                revision=cast(typ="int", val=service.snapshot()["revision"]),
            )
        document: JsonValue = WorkspaceCodec.to_json_value(
            workspace=service.controller.workspace,
        )
        flows: JsonValue = cast(typ="dict[str, JsonValue]", val=document)[
            "flows"
        ]
        events: JsonValue = cast(typ="list[dict[str, JsonValue]]", val=flows)[
            0
        ]["events"]
        cast(typ="list[dict[str, JsonValue]]", val=events)[1][
            "receive_previous"
        ] = True
        loaded: Workspace = WorkspaceCodec.from_json_value(value=document)
        first, second = loaded.flows[0].events
        expect_equal(
            actual=first.output_variable,
            expected=f"{first.label} Result",
        )
        expect_equal(
            actual=second.payload,
            expected=f"log('{{{{{first.output_variable}}}}}')",
        )
    finally:
        service.stop()


def test_flow_inputs_are_saved_and_typed_per_run(tmp_path: Path) -> None:
    """Save the flow's inputs, then type the answers for one run.

    Args:
        tmp_path: Disposable project folder.

    """
    service: StudioService = StudioService(root=tmp_path, headless=True)
    service.start()
    try:
        flow: Flow = service.controller.workspace.flows[0]
        _ = service.controller.dispatch(
            command="flow.update",
            payload={
                "name": flow.name,
                "parameters": [
                    {"name": "Customer", "value_type": "string"},
                    {"name": "Count", "value_type": "integer"},
                    {"name": "Rate", "value_type": "float"},
                    {"name": "Flag", "value_type": "boolean"},
                    {
                        "name": "Mode",
                        "value_type": "string",
                        "required": False,
                        "default_value": "fast",
                    },
                ],
            },
            revision=cast(typ="int", val=service.snapshot()["revision"]),
        )
        saved: Flow = service.controller.workspace.flows[0]
        expect_equal(
            actual=[item.name for item in saved.parameters],
            expected=["Customer", "Count", "Rate", "Flag", "Mode"],
        )
        supply: Callable[..., tuple[RuntimeVariable, ...]] = cast(
            typ="Callable[..., tuple[RuntimeVariable, ...]]",
            val=private(owner=controller_module, name="_supplied"),
        )
        variables: tuple[RuntimeVariable, ...] = supply(
            flow=saved,
            answers={
                "Customer": "Ana",
                "Count": "3",
                "Rate": "1.5",
                "Flag": "true",
            },
        )
        expect_equal(
            actual={item.name: item.value for item in variables},
            expected={
                "Customer": "Ana",
                "Count": 3,
                "Rate": 1.5,
                "Flag": True,
            },
        )
        with pytest.raises(
            expected_exception=ValueError,
            match="expects a integer",
        ):
            _ = supply(flow=saved, answers={"Customer": "a", "Count": "x"})
        with pytest.raises(
            expected_exception=ValueError,
            match="expects a boolean",
        ):
            _ = supply(
                flow=saved,
                answers={
                    "Customer": "Ana",
                    "Count": "3",
                    "Rate": "1",
                    "Flag": "yes",
                },
            )
        with pytest.raises(
            expected_exception=ValueError,
            match="Provide a value for",
        ):
            _ = supply(flow=saved, answers={"Customer": "Ana"})
    finally:
        service.stop()


def _published(
    *,
    tmp_path: Path,
    capture: dict[str, JsonValue],
    body: str,
) -> dict[str, JsonValue]:
    """Publish one response capture and return the run variables.

    Args:
        tmp_path: Disposable artifact folder.
        capture: Authored capture mapping.
        body: Response body text; JSON bodies are also parsed.

    Returns:
        The run variables after publishing.

    """
    runner: FlowRunner = FlowRunner(output=tmp_path)
    publish: Callable[..., None] = cast(
        typ="Callable[..., None]",
        val=private(owner=runner, name="_publish_response_captures"),
    )
    parsed: JsonValue = body
    if body.startswith("{"):
        parsed = cast(typ="JsonValue", val=loads(s=body))
    publish(
        config={"captures": [cast(typ="JsonValue", val=capture)]},
        response={
            "status": 200,
            "url": "https://api.test/",
            "headers": {},
            "body": body,
            "json": parsed,
        },
    )
    return private_as(owner=runner, name="_streams", kind=RunStreams).vars


def test_fixed_capture_ignores_response(tmp_path: Path) -> None:
    """A fixed capture publishes its stored value, not the response's.

    Args:
        tmp_path: Disposable artifact folder.

    """
    variables: dict[str, JsonValue] = _published(
        tmp_path=tmp_path,
        capture={
            "name": "Token",
            "mode": "fixed",
            "value": "abc",
            "value_type": "string",
            "path": "x",
        },
        body="{}",
    )
    expect_equal(actual=variables["Token"], expected="abc")


def test_xml_capture_reads_path(tmp_path: Path) -> None:
    """An xml capture reads an attribute and converts its type.

    Args:
        tmp_path: Disposable artifact folder.

    """
    variables: dict[str, JsonValue] = _published(
        tmp_path=tmp_path,
        capture={
            "name": "Id",
            "source": "xml",
            "path": "/user/@id",
            "value_type": "integer",
        },
        body='<user id="5"/>',
    )
    expect_equal(actual=variables["Id"], expected=5)


def test_required_path_missing_names_variable(tmp_path: Path) -> None:
    """A required capture whose path is absent fails with its name.

    Args:
        tmp_path: Disposable artifact folder.

    """
    with pytest.raises(expected_exception=ValueError, match=r"'Id'.*user\.id"):
        _ = _published(
            tmp_path=tmp_path,
            capture={"name": "Id", "source": "json", "path": "user.id"},
            body="{}",
        )


def test_optional_path_missing_is_null(tmp_path: Path) -> None:
    """An optional capture whose path is absent publishes null.

    Args:
        tmp_path: Disposable artifact folder.

    """
    variables: dict[str, JsonValue] = _published(
        tmp_path=tmp_path,
        capture={
            "name": "Id",
            "source": "json",
            "path": "user.id",
            "required": False,
        },
        body="{}",
    )
    expect_equal(actual=variables["Id"], expected=None)
