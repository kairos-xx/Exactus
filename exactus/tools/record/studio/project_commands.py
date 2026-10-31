# Copyright (c) 2026 Project contributors
"""Editor commands for projects, apart from the large controller."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, cast

from exactus.tools.record.model import TargetMode
from exactus.tools.record.project_info import (
    ProjectInfo,
    ProjectInfoCodec,
    ProjectInfoError,
)
from exactus.tools.record.studio.projects import (
    ProjectError,
    ProjectLibrary,
    ProjectSummary,
    tags_of,
    target_from_address,
)

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.model import Target, Workspace


def project_view(
    *,
    library: ProjectLibrary,
    active: str,
    workspace: Workspace,
) -> dict[str, JsonValue]:
    """Describe the open project and the library for the editor.

    Args:
        library: The Studio's projects.
        active: Identifier of the open project.
        workspace: The open project, with its unsaved changes.

    Returns:
        The ``project`` being edited and the ``library`` of all projects.

    """
    projects: tuple[ProjectSummary, ...] = library.list()
    saved: ProjectSummary | None = next(
        (item for item in projects if item.slug == active),
        None,
    )
    info: ProjectInfo = workspace.project
    target: Target = workspace.target
    return {
        "project": {
            "slug": active,
            "name": info.name
            or (saved.info.name if saved is not None else ""),
            "description": info.description,
            "tags": list(info.tags),
            "author": info.author,
            "version": info.version,
            "created_at": info.created_at
            or (saved.info.created_at if saved is not None else ""),
            "base_url": (
                target.address()
                if target.mode is TargetMode.URL and target.url
                else ""
            ),
            "saved": saved is not None,
        },
        "library": {
            "projects": [item.to_json_value() for item in projects],
            "recents": list(library.recents()),
            "tags": cast(typ="JsonValue", val=tags_of(projects=projects)),
        },
    }


def new_info(*, data: dict[str, JsonValue]) -> ProjectInfo:
    """Read the details of a new project from a form.

    Args:
        data: Form fields; only the name is required.

    Returns:
        The details.

    Raises:
        ProjectError: When the details are not valid.

    """
    try:
        return ProjectInfoCodec.from_form(data=data, base=ProjectInfo())
    except ProjectInfoError as error:
        raise ProjectError(str(object=error)) from error


def updated_workspace(
    *,
    workspace: Workspace,
    library: ProjectLibrary,
    active: str,
    data: dict[str, JsonValue],
) -> Workspace:
    """Apply an edit of the open project's details.

    Args:
        workspace: The open project.
        library: The Studio's projects, which keep names unique.
        active: Identifier of the open project.
        data: Changed fields: name, description, tags, author, version and
            base_url. Fields that are absent stay as they are.

    Returns:
        The project with the new details.

    Raises:
        ProjectError: When a detail is not valid or the name is taken.

    """
    try:
        info: ProjectInfo = ProjectInfoCodec.from_form(
            data=data,
            base=workspace.project,
        )
    except ProjectInfoError as error:
        raise ProjectError(str(object=error)) from error
    if info.name != workspace.project.name:
        if not info.name:
            msg: str = "A project needs a name."
            raise ProjectError(msg)
        if library.name_taken(name=info.name, ignore=active):
            msg = f"A project named {info.name!r} already exists."
            raise ProjectError(msg)
    target: Target = workspace.target
    if "base_url" in data:
        target = target_from_address(
            address=str(object=data["base_url"] or ""),
            base=workspace.target,
        )
    return replace(workspace, project=info, target=target)
