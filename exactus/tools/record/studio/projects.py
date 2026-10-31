# Copyright (c) 2026 Project contributors
"""Keep a library of projects, one folder each, under the Studio root.

The Studio root holds ``projects/<slug>/`` folders. Each folder is a complete
project with its own file, selectors and evidence. The root folder's own
project file, if it has one (the layout before the library existed), stays
usable as the project ``@root``, so nothing needs migrating.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from json import dumps, loads
from re import compile as re_compile
from re import sub
from shutil import rmtree
from typing import TYPE_CHECKING, Final, cast, final
from urllib.parse import urlsplit, urlunsplit

from exactus.tools.record.model import Flow, Target, TargetMode, Workspace
from exactus.tools.record.store import WorkspaceCodec, WorkspaceError
from exactus.tools.record.studio.persistence import WorkspaceFiles

if TYPE_CHECKING:
    from builtins import list as list_type
    from os import stat_result
    from pathlib import Path
    from re import Pattern
    from urllib.parse import SplitResult

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.project_info import ProjectInfo


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root_id: Grouped module constant.
        folder: Grouped module constant.
        file_name: Grouped module constant.
        recents_file: Grouped module constant.
        recents_kept: Grouped module constant.
        slug_pattern: Grouped module constant.
        default_name: Grouped module constant.

    """

    root_id: Final[str] = "@root"
    folder: Final[str] = "projects"
    file_name: Final[str] = "flows.pwflow.json"
    recents_file: Final[str] = ".exactus-library/recents.json"
    recents_kept: Final[int] = 10
    slug_pattern: Final[Pattern[str]] = re_compile(
        pattern="^[a-z0-9][a-z0-9-]{0,63}$",
    )
    default_name: Final[str] = "Default project"


class ProjectError(ValueError):
    """Raise when a project action cannot be done."""


def target_from_address(*, address: str, base: Target | None = None) -> Target:
    """Turn an address a person typed into the project's target.

    The target keeps the port apart from the address, so
    ``http://localhost:3000/app`` becomes the address ``http://localhost/app``
    and the port 3000.

    Args:
        address: A full address, with or without the scheme.
        base: The target whose other settings are kept.

    Returns:
        A URL-mode target; an empty address leaves it unconfigured.

    Raises:
        ProjectError: When the address is not a usable http or https one.

    """
    current: Target = base or Target()
    text: str = address.strip()
    if not text:
        return replace(current, mode=TargetMode.URL, url="", port=None)
    parts: SplitResult = urlsplit(
        url=text if "://" in text else f"http://{text}",
    )
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        msg: str = "Use an http:// or https:// address with a host."
        raise ProjectError(msg)
    host: str = (
        f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    )
    rest: str = urlunsplit(
        components=("", "", parts.path, parts.query, parts.fragment),
    )
    try:
        return replace(
            current,
            mode=TargetMode.URL,
            url=f"{parts.scheme}://{host}{rest}",
            port=parts.port,
        )
    except ValueError as error:
        raise ProjectError(str(object=error)) from error


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectSummary:
    """Describe one project for the gallery.

    Attributes:
        slug: Identifier, which is also the folder name.
        info: Name, description, tags and authorship.
        modified_at: When the project file was last saved.
        last_run_at: When its most recent run started, or empty.
        flows: How many flows it has.
        runs: How many runs it remembers.
        base_url: The address its tests start from.
        legacy: Whether this is the library folder's own project.

    """

    slug: str
    info: ProjectInfo
    modified_at: str
    last_run_at: str
    flows: int
    runs: int
    base_url: str
    legacy: bool

    def to_json_value(self) -> dict[str, JsonValue]:
        """Return the summary as the gallery shows it.

        Returns:
            A JSON object.

        """
        return cast(
            typ="dict[str, JsonValue]",
            val={
                "slug": self.slug,
                "name": self.info.name,
                "description": self.info.description,
                "tags": list(self.info.tags),
                "author": self.info.author,
                "version": self.info.version,
                "created_at": self.info.created_at,
                "modified_at": self.modified_at,
                "last_run_at": self.last_run_at,
                "flows": self.flows,
                "runs": self.runs,
                "base_url": self.base_url,
                "legacy": self.legacy,
            },
        )


class ProjectLibrary:
    """Create, find and manage the projects under one Studio root."""

    def __init__(self, *, root: Path) -> None:
        """Remember the library root.

        Args:
            root: The Studio root folder.

        """
        self.root: Path = root.resolve()
        self._cache: dict[str, tuple[tuple[int, int], ProjectSummary]] = {}

    def folder(self, *, slug: str) -> Path:
        """Return the folder of a project.

        Args:
            slug: A project identifier.

        Returns:
            The project's folder, which is inside the library root.

        Raises:
            ProjectError: When the identifier is not a valid project.

        """
        if slug == Constants.root_id:
            return self.root
        if not Constants.slug_pattern.fullmatch(string=slug):
            msg: str = f"{slug!r} is not a project."
            raise ProjectError(msg)
        return self.root / Constants.folder / slug

    def slug_of(self, *, folder: Path) -> str:
        """Return the identifier of the project in a folder.

        Args:
            folder: A project folder.

        Returns:
            ``@root`` for the library folder itself, else the folder name.

        """
        return (
            Constants.root_id
            if folder.resolve() == self.root
            else folder.resolve().name
        )

    def list(self) -> tuple[ProjectSummary, ...]:
        """Describe every project, newest changes first.

        Returns:
            One summary per project folder that has a project file.

        """
        found: list[ProjectSummary] = []
        if (self.root / Constants.file_name).is_file():
            found.append(self._summary(slug=Constants.root_id))
        base: Path = self.root / Constants.folder
        if base.is_dir():
            found.extend(
                self._summary(slug=item.name)
                for item in sorted(base.iterdir())
                if Constants.slug_pattern.fullmatch(string=item.name)
                and (item / Constants.file_name).is_file()
            )
        return tuple(
            sorted(found, key=lambda item: item.modified_at, reverse=True),
        )

    def get(self, *, slug: str) -> ProjectSummary:
        """Describe one project.

        Args:
            slug: A project identifier.

        Returns:
            Its summary.

        Raises:
            ProjectError: When there is no such project.

        """
        if not (self.folder(slug=slug) / Constants.file_name).is_file():
            msg: str = "There is no such project."
            raise ProjectError(msg)
        return self._summary(slug=slug)

    def name_taken(self, *, name: str, ignore: str = "") -> bool:
        """Say whether another project already has a name.

        Args:
            name: The name to check; case does not matter.
            ignore: A project that may keep its own name.

        Returns:
            True when a different project uses the name.

        """
        wanted: str = name.strip().casefold()
        return any(
            item.info.name.casefold() == wanted
            for item in self.list()
            if item.slug != ignore
        )

    def create(
        self,
        *,
        info: ProjectInfo,
        base_url: str = "",
    ) -> ProjectSummary:
        """Create an empty project in its own folder.

        Args:
            info: Name and optional details; the name must be unique.
            base_url: Address the project's tests start from, if known.

        Returns:
            The new project.

        """
        self._check_name(name=info.name, ignore="")
        slug: str = self._new_slug(name=info.name)
        target: Target = target_from_address(address=base_url)
        workspace: Workspace = Workspace(
            flows=(
                Flow(
                    flow_id="flow-1",
                    name="Flow A",
                    task_description="",
                    expected_behavior="",
                    notes="",
                ),
            ),
            edges=(),
            target=target,
            project=replace(info, created_at=self._now()),
        )
        self._write(slug=slug, workspace=workspace)
        return self.get(slug=slug)

    def ensure(self, *, info: ProjectInfo, workspace: Workspace) -> str:
        """Return the project with a name, creating it when it is missing.

        Args:
            info: Details used when the project has to be created.
            workspace: Content used when the project has to be created.

        Returns:
            The identifier of the project, new or existing.

        """
        wanted: str = info.name.strip().casefold()
        existing: ProjectSummary | None = next(
            (
                item
                for item in self.list()
                if item.info.name.casefold() == wanted
            ),
            None,
        )
        if existing is not None:
            return existing.slug
        slug: str = self._new_slug(name=info.name)
        self._write(
            slug=slug,
            workspace=replace(
                workspace,
                project=replace(info, created_at=self._now()),
            ),
        )
        return slug

    def duplicate(self, *, slug: str, name: str) -> ProjectSummary:
        """Copy a project's definition, without its runs or screenshots.

        Args:
            slug: The project to copy.
            name: Name of the copy; it must be unique.

        Returns:
            The copy.

        """
        self._check_name(name=name, ignore="")
        source: Workspace = self._open(slug=slug)
        copy_slug: str = self._new_slug(name=name)
        workspace: Workspace = replace(
            source,
            screenshots=(),
            runs=(),
            checkpoint_artifacts=(),
            project=replace(
                source.project,
                name=name.strip(),
                created_at=self._now(),
            ),
        )
        self._write(slug=copy_slug, workspace=workspace)
        return self.get(slug=copy_slug)

    def delete(self, *, slug: str) -> None:
        """Delete a project's folder for good.

        Args:
            slug: The project to delete.

        Raises:
            ProjectError: When it is the library folder's own project, which
                holds the whole library and is never deleted from here.

        """
        if slug == Constants.root_id:
            msg: str = "The default project is the library folder itself."
            raise ProjectError(msg)
        folder: Path = self.folder(slug=slug)
        if not folder.is_dir():
            msg = "There is no such project."
            raise ProjectError(msg)
        rmtree(path=folder)
        self._cache.pop(slug, None)
        self._forget(slug=slug)

    def import_document(
        self,
        *,
        document: dict[str, JsonValue],
        name: str = "",
    ) -> ProjectSummary:
        """Add a project from an exported document.

        Args:
            document: A project exported from Studio.
            name: Name to give it; the document's own name when blank.

        Returns:
            The new project.

        Raises:
            ProjectError: When the document cannot be read.

        """
        slug_name: str = name.strip()
        try:
            probe: Workspace = WorkspaceCodec.from_json_value(value=document)
        except WorkspaceError as error:
            raise ProjectError(str(object=error)) from error
        wanted: str = slug_name or probe.project.name or "Imported project"
        final_name: str = self._free_name(name=wanted)
        slug: str = self._new_slug(name=final_name)
        folder: Path = self.folder(slug=slug)
        folder.mkdir(parents=True)
        try:
            workspace: Workspace = WorkspaceFiles(root=folder).open(
                data={"workspace": document},
            )
        except WorkspaceError as error:
            rmtree(path=folder)
            raise ProjectError(str(object=error)) from error
        self._write(
            slug=slug,
            workspace=replace(
                workspace,
                project=replace(
                    workspace.project,
                    name=final_name,
                    created_at=workspace.project.created_at or self._now(),
                ),
            ),
        )
        return self.get(slug=slug)

    def export_document(self, *, slug: str) -> dict[str, JsonValue]:
        """Return a project as one portable document.

        Args:
            slug: The project to export.

        Returns:
            The project with its screenshots and selectors included.

        """
        files: WorkspaceFiles = WorkspaceFiles(root=self.folder(slug=slug))
        workspace: Workspace = files.open(
            data={"filename": Constants.file_name},
        )
        return files.project_document(workspace=workspace)

    def recents(self) -> tuple[str, ...]:
        """List recently opened projects that still exist.

        Returns:
            Up to five identifiers, most recent first.

        """
        known: set[str] = {item.slug for item in self.list()}
        return tuple(item for item in self._read_recents() if item in known)[
            :5
        ]

    def touch(self, *, slug: str) -> None:
        """Remember that a project was just opened.

        Args:
            slug: The project opened.

        """
        recents: list[str] = [
            slug,
            *(i for i in self._read_recents() if i != slug),
        ]
        path: Path = self.root / Constants.recents_file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            data=dumps(obj={"recent": recents[: Constants.recents_kept]}),
            encoding="utf-8",
        )

    @staticmethod
    def _address(*, target: Target) -> str:
        """Return the address a project's tests start from, if it has one.

        Args:
            target: The project's target.

        Returns:
            The full address, or empty for a service or an unset address.

        """
        if target.mode is not TargetMode.URL or not target.url:
            return ""
        return target.address()

    @staticmethod
    def _now() -> str:
        """Return the current UTC time as ISO 8601 text.

        Returns:
            The time, to the second.

        """
        return datetime.now(tz=UTC).astimezone().isoformat(timespec="seconds")

    def _forget(self, *, slug: str) -> None:
        """Drop a project from the recents.

        Args:
            slug: The project that no longer exists.

        """
        kept: list[str] = [i for i in self._read_recents() if i != slug]
        path: Path = self.root / Constants.recents_file
        if path.exists():
            path.write_text(data=dumps(obj={"recent": kept}), encoding="utf-8")

    def _read_recents(self) -> list_type[str]:
        """Read the remembered identifiers.

        Returns:
            The identifiers, most recent first; empty when none are kept.

        """
        path: Path = self.root / Constants.recents_file
        try:
            value: JsonValue = loads(s=path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        items: JsonValue = (
            value.get("recent") if isinstance(value, dict) else None
        )
        return (
            [item for item in items if isinstance(item, str)]
            if isinstance(items, list)
            else []
        )

    def _summary(self, *, slug: str) -> ProjectSummary:
        """Describe a project, reusing the last reading while unchanged.

        Args:
            slug: A project that exists.

        Returns:
            Its summary.

        """
        path: Path = self.folder(slug=slug) / Constants.file_name
        stat: stat_result = path.stat()
        key: tuple[int, int] = (stat.st_mtime_ns, stat.st_size)
        cached: tuple[tuple[int, int], ProjectSummary] | None = (
            self._cache.get(slug)
        )
        if cached is not None and cached[0] == key:
            return cached[1]
        workspace: Workspace = WorkspaceCodec.load(path=path)
        info: ProjectInfo = workspace.project
        legacy: bool = slug == Constants.root_id
        summary: ProjectSummary = ProjectSummary(
            slug=slug,
            info=replace(
                info,
                name=info.name or (Constants.default_name if legacy else slug),
                created_at=info.created_at
                or datetime.fromtimestamp(stat.st_ctime, tz=UTC)
                .astimezone()
                .isoformat(timespec="seconds"),
            ),
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC)
            .astimezone()
            .isoformat(timespec="seconds"),
            last_run_at=max(
                (run.started_at_utc for run in workspace.runs),
                default="",
            ),
            flows=len(workspace.flows),
            runs=len(workspace.runs),
            base_url=self._address(target=workspace.target),
            legacy=legacy,
        )
        self._cache[slug] = (key, summary)
        return summary

    def _open(self, *, slug: str) -> Workspace:
        """Load a project's workspace and selectors.

        Args:
            slug: A project that exists.

        Returns:
            The workspace.

        """
        self.get(slug=slug)
        return WorkspaceFiles(root=self.folder(slug=slug)).open(
            data={"filename": Constants.file_name},
        )

    def _write(self, *, slug: str, workspace: Workspace) -> None:
        """Save a workspace as a project's file.

        Args:
            slug: The project folder to write.
            workspace: What to save.

        """
        folder: Path = self.folder(slug=slug)
        folder.mkdir(parents=True, exist_ok=True)
        target: Path = folder / Constants.file_name
        if target.exists():
            target.unlink()
        WorkspaceFiles(root=folder).save(
            workspace=workspace,
            data={"filename": Constants.file_name},
        )
        self._cache.pop(slug, None)

    def _check_name(self, *, name: str, ignore: str) -> None:
        """Require a non-blank name that no other project uses.

        Args:
            name: The proposed name.
            ignore: A project allowed to keep the name.

        Raises:
            ProjectError: When the name is blank or taken.

        """
        if not name.strip():
            msg: str = "A project needs a name."
            raise ProjectError(msg)
        if self.name_taken(name=name, ignore=ignore):
            msg = f"A project named {name.strip()!r} already exists."
            raise ProjectError(msg)

    def _free_name(self, *, name: str) -> str:
        """Return the name, or the name with a number when it is taken.

        Args:
            name: The wanted name.

        Returns:
            A name no project uses.

        """
        candidate: str = name.strip()
        number: int = 2
        while self.name_taken(name=candidate):
            candidate = f"{name.strip()} ({number})"
            number += 1
        return candidate

    def _new_slug(self, *, name: str) -> str:
        """Choose an unused folder name for a project.

        Args:
            name: The project's name.

        Returns:
            A valid identifier whose folder does not exist.

        """
        base: str = sub(
            pattern="[^a-z0-9]+",
            repl="-",
            string=name.casefold(),
        ).strip("-")[:56]
        base = base or "project"
        slug: str = base
        number: int = 2
        while (self.root / Constants.folder / slug).exists():
            slug = f"{base}-{number}"
            number += 1
        return slug


def tags_of(*, projects: tuple[ProjectSummary, ...]) -> list[str]:
    """Collect every tag used by any project.

    Args:
        projects: The library's projects.

    Returns:
        Distinct tags, sorted without regard to case.

    """
    seen: dict[str, str] = {}
    for project in projects:
        for tag in project.info.tags:
            seen.setdefault(tag.casefold(), tag)
    return [seen[key] for key in sorted(seen)]
