# Copyright (c) 2026 Project contributors
"""Exercise the version-3 fixture regeneration utility."""

from __future__ import annotations

from json import dumps, loads
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast, final

from exactus.tests.common.support import expect_equal
from exactus.tests.tools.record.v3_fixture_builder import (
    build,
    canonical,
    main,
)
from exactus.tools.record.store import WorkspaceCodec

if TYPE_CHECKING:
    import pytest

    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        folder: Grouped module constant.
        names: Grouped module constant.

    """

    folder: Final[Path] = Path(__file__).resolve().parent / "fixtures" / "v3"
    names: Final[tuple[str, ...]] = (
        "guards-and-chain",
        "edges-all-modes",
        "variables-all-scopes",
        "legacy-receive-previous",
    )


def _base() -> dict[str, JsonValue]:
    """Load the demo workspace the fixtures derive from.

    Returns:
        The parsed demo document.

    """
    return cast(
        typ="dict[str, JsonValue]",
        val=loads(
            s=(Constants.folder / "demo.pwflow.json").read_text(
                encoding="utf-8",
            ),
        ),
    )


def test_build_returns_every_fixture() -> None:
    """Derive the four named fixtures from the demo workspace."""
    fixtures: dict[str, dict[str, JsonValue]] = build(base=_base())
    expect_equal(actual=set(fixtures), expected=set(Constants.names))


def test_build_covers_every_edge_mode() -> None:
    """Emit one edge for each transition mode."""
    fixtures: dict[str, dict[str, JsonValue]] = build(base=_base())
    edges: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=fixtures["edges-all-modes"]["edges"],
    )
    modes: set[str] = {cast(typ="str", val=edge["mode"]) for edge in edges}
    expect_equal(
        actual=modes,
        expected={"always", "condition", "fallback", "retry", "finally"},
    )
    expressions: list[JsonValue] = [
        edge["condition_expression"]
        for edge in edges
        if edge["mode"] == "condition"
    ]
    expect_equal(
        actual=expressions,
        expected=["__EXACTUS_FLOW__.vars.Count > 1"],
    )


def test_build_covers_every_variable_scope() -> None:
    """Emit one variable for each persisted scope."""
    fixtures: dict[str, dict[str, JsonValue]] = build(base=_base())
    variables: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=fixtures["variables-all-scopes"]["variables"],
    )
    scopes: set[str] = {
        cast(typ="str", val=variable["scope"]) for variable in variables
    }
    expect_equal(
        actual=scopes,
        expected={"flow", "run", "workspace", "environment", "secret"},
    )


def test_build_chains_guarded_events() -> None:
    """Emit a guarded chain where later events consume earlier results."""
    fixtures: dict[str, dict[str, JsonValue]] = build(base=_base())
    events: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=cast(
            typ="list[dict[str, JsonValue]]",
            val=fixtures["guards-and-chain"]["flows"],
        )[0]["events"],
    )
    expect_equal(actual=len(events), expected=3)
    expect_equal(actual=events[0]["output_variable"], expected="Count")
    expect_equal(
        actual=events[1]["when_expression"],
        expected="__EXACTUS_FLOW__.vars.Count > 1",
    )
    expect_equal(actual=events[1]["sandbox"], expected=True)
    expect_equal(actual=events[2]["output_variable"], expected="Label")


def test_build_keeps_legacy_receive_previous_shape() -> None:
    """Emit the pre-migration receive-previous event pair."""
    fixtures: dict[str, dict[str, JsonValue]] = build(base=_base())
    events: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=cast(
            typ="list[dict[str, JsonValue]]",
            val=fixtures["legacy-receive-previous"]["flows"],
        )[0]["events"],
    )
    expect_equal(actual=len(events), expected=2)
    expect_equal(actual=events[1]["receive_previous"], expected=True)
    expect_equal(actual=events[1]["payload"], expected="{{previous}}")


def test_canonical_round_trips_through_the_codec() -> None:
    """Serialize a built fixture to the codec's canonical keys."""
    fixtures: dict[str, dict[str, JsonValue]] = build(base=_base())
    document: dict[str, JsonValue] = canonical(
        document=fixtures["guards-and-chain"],
    )
    expect_equal(actual=document, expected=loads(s=dumps(obj=document)))
    WorkspaceCodec.from_json_value(value=document)


def test_main_writes_the_committed_fixtures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regenerate fixture files identical to the committed ones.

    Args:
        tmp_path: Isolated output directory supplied by pytest.
        monkeypatch: Argument-vector override supplied by pytest.

    """
    monkeypatch.setattr(
        target="exactus.tests.tools.record.v3_fixture_builder.argv",
        name=[
            "v3_fixture_builder",
            str(object=tmp_path),
            str(object=Constants.folder / "demo.pwflow.json"),
        ],
    )
    main()
    expect_equal(
        actual={path.name for path in tmp_path.iterdir()},
        expected={f"{name}.pwflow.json" for name in Constants.names},
    )
    for name in Constants.names:
        written: Path = tmp_path / f"{name}.pwflow.json"
        committed: Path = Constants.folder / f"{name}.pwflow.json"
        expect_equal(
            actual=written.read_text(encoding="utf-8"),
            expected=committed.read_text(encoding="utf-8"),
        )
