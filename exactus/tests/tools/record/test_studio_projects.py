# Copyright (c) 2026 Project contributors
"""Drive the project commands through a real Studio service."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from exactus.tests.common.support import (
    dig,
    dig_list,
    expect_equal,
    expect_true,
)
from exactus.tools.record.studio.service import StudioService

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


@pytest.fixture
def service(tmp_path: Path) -> Iterator[StudioService]:
    """Run an isolated Studio service over an empty library.

    Args:
        tmp_path: Disposable Studio root.

    Yields:
        The running service.

    """
    application: StudioService = StudioService(root=tmp_path, headless=True)
    application.start()
    try:
        yield application
    finally:
        application.stop()


def _send(
    *,
    service: StudioService,
    command: str,
    payload: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    """Send one editor command at the current revision.

    Args:
        service: The running service.
        command: Editor command name.
        payload: Command fields.

    Returns:
        The snapshot the command returns.

    """
    reply: JsonValue = service.controller.dispatch(
        command=command,
        payload=payload,
        revision=cast(typ="int", val=service.snapshot()["revision"]),
    )
    return cast(typ="dict[str, JsonValue]", val=reply)


def _names(*, snapshot: dict[str, JsonValue]) -> list[str]:
    """List the names of the projects in a snapshot's library.

    Args:
        snapshot: A Studio snapshot.

    Returns:
        Project names, newest change first.

    """
    return [
        str(object=dig(document=item, path=("name",)))
        for item in dig_list(document=snapshot, path=("library", "projects"))
    ]


def test_creating_a_project_opens_it_with_unique_names(
    service: StudioService,
    tmp_path: Path,
) -> None:
    """Create a project in its own folder; refuse a name already in use.

    Args:
        service: The running service.
        tmp_path: The Studio root.

    """
    snapshot: dict[str, JsonValue] = _send(
        service=service,
        command="project.create",
        payload={
            "name": "Checkout",
            "tags": "web, Smoke, web",
            "base_url": "http://localhost:3000/app",
        },
    )
    expect_equal(
        actual=dig(document=snapshot, path=("project", "name")),
        expected="Checkout",
    )
    expect_equal(
        actual=dig(document=snapshot, path=("project", "slug")),
        expected="checkout",
    )
    expect_equal(
        actual=dig_list(document=snapshot, path=("project", "tags")),
        expected=["web", "Smoke"],
    )
    expect_equal(
        actual=dig(document=snapshot, path=("project", "base_url")),
        expected="http://localhost:3000/app",
    )
    expect_true(condition=(tmp_path / "projects/checkout").is_dir())
    expect_equal(
        actual=service.persistence.root,
        expected=(tmp_path / "projects/checkout").resolve(),
    )
    with pytest.raises(expected_exception=ValueError, match="already exists"):
        _ = _send(
            service=service,
            command="project.create",
            payload={"name": " checkout ", "replace": True},
        )


def test_switching_projects_guards_unsaved_edits(
    service: StudioService,
) -> None:
    """Keep edits safe until the person confirms leaving them.

    Args:
        service: The running service.

    """
    _ = _send(
        service=service,
        command="project.create",
        payload={"name": "One"},
    )
    _ = _send(
        service=service,
        command="project.update",
        payload={"description": "edited"},
    )
    with pytest.raises(expected_exception=ValueError, match="discarding"):
        _ = _send(
            service=service,
            command="project.create",
            payload={"name": "Two"},
        )
    snapshot: dict[str, JsonValue] = _send(
        service=service,
        command="project.create",
        payload={"name": "Two", "replace": True},
    )
    expect_equal(
        actual=dig(document=snapshot, path=("project", "slug")),
        expected="two",
    )
    reopened: dict[str, JsonValue] = _send(
        service=service,
        command="project.open",
        payload={"slug": "one"},
    )
    expect_equal(
        actual=dig(document=reopened, path=("project", "description")),
        expected="",
    )
    expect_equal(
        actual=dig_list(document=reopened, path=("library", "recents")),
        expected=["one", "two"],
    )


def test_details_can_be_edited_and_names_stay_unique(
    service: StudioService,
) -> None:
    """Edit details, split a base address's port, and refuse a taken name.

    Args:
        service: The running service.

    """
    _ = _send(service=service, command="project.create", payload={"name": "A"})
    _ = _send(service=service, command="project.update", payload={})
    saved: dict[str, JsonValue] = _send(
        service=service,
        command="project.update",
        payload={
            "author": "Ana",
            "version": "1.2",
            "base_url": "https://example.test:8443/start",
        },
    )
    expect_equal(
        actual=dig(document=saved, path=("project", "base_url")),
        expected="https://example.test:8443/start",
    )
    target: object = dig(document=saved, path=("workspace", "target"))
    expect_equal(actual=dig(document=target, path=("port",)), expected=8443)
    _ = _send(service=service, command="workspace.save", payload={})
    _ = _send(
        service=service,
        command="project.create",
        payload={"name": "B", "replace": True},
    )
    with pytest.raises(expected_exception=ValueError, match="already exists"):
        _ = _send(
            service=service,
            command="project.update",
            payload={"name": "a"},
        )


def test_duplicate_delete_and_import(service: StudioService) -> None:
    """Copy, remove and bring in projects; never delete the open one.

    Args:
        service: The running service.

    """
    _ = _send(service=service, command="project.create", payload={"name": "A"})
    _ = _send(service=service, command="workspace.save", payload={})
    _ = _send(
        service=service,
        command="project.duplicate",
        payload={"slug": "a", "name": "A copy"},
    )
    snapshot: dict[str, JsonValue] = service.snapshot()
    expect_equal(
        actual=sorted(_names(snapshot=snapshot)),
        expected=["A", "A copy"],
    )
    with pytest.raises(expected_exception=ValueError, match="Open another"):
        _ = _send(
            service=service,
            command="project.delete",
            payload={"slug": "a"},
        )
    document: JsonValue = service.export_document()
    imported: dict[str, JsonValue] = _send(
        service=service,
        command="project.import",
        payload={"workspace": document},
    )
    expect_equal(
        actual=sorted(_names(snapshot=imported)),
        expected=["A", "A (2)", "A copy"],
    )
    gone: dict[str, JsonValue] = _send(
        service=service,
        command="project.delete",
        payload={"slug": "a-copy"},
    )
    expect_equal(actual=sorted(_names(snapshot=gone)), expected=["A", "A (2)"])
