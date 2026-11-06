# Copyright (c) 2026 Project contributors
"""Restrict workspace and artifact access to the selected project root."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from json import loads
from pathlib import Path
from typing import TYPE_CHECKING, cast

from exactus.tools.record.project_assets import embed_assets, restore_assets
from exactus.tools.record.selectors import Constants as SelectorConstants
from exactus.tools.record.selectors import (
    SelectorCodec,
    SelectorDef,
    SelectorError,
)
from exactus.tools.record.store import (
    Constants,
    WorkspaceCodec,
    WorkspaceError,
)
from exactus.tools.record.workspace_actions import write_workspace

if TYPE_CHECKING:
    from exactus.tools.record.model import ScreenshotArtifact, Workspace
    from exactus.tools.record.store import JsonValue


class WorkspaceFiles:
    """Keep recovery and project saves atomic and detect external changes.

    Attributes:
        root: Explicit resolved project root.
        artifact_root: Service-owned browser evidence directory.
        recovered: Whether an unsaved workspace was recovered.
        saved_name: Relative saved destination shown in the editor.

    """

    def __init__(self, *, root: Path) -> None:
        """Create project-local recovery storage.

        Args:
            root: Project explicitly chosen by the caller.

        """
        self.root: Path = root.resolve()
        self.artifact_root: Path = self.safe_path(name=".studio/artifacts")
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self.recovered: bool = False
        self.saved_name: str | None = None
        self._saved_hash: str | None = None
        self._saved_selectors_hash: str | None = None
        self._recovery: Path = self.safe_path(
            name=".studio/recovery.pwflow.json",
        )
        self._recovery_selectors: Path = self.safe_path(
            name=".studio/recovery.selectors.pwflow.json",
        )

    @classmethod
    def public_document(
        cls,
        *,
        value: JsonValue,
        artifact_links: bool = True,
    ) -> JsonValue:
        """Redact runtime secrets and expose artifact IDs instead of paths.

        Args:
            value: Serialized workspace or nested record.
            artifact_links: Expose preview links instead of local paths.

        Returns:
            Safe browser-facing document.

        """
        if isinstance(value, list):
            return [
                cls.public_document(value=item, artifact_links=artifact_links)
                for item in value
            ]
        if isinstance(value, dict):
            result: dict[str, JsonValue] = {
                key: cls.public_document(
                    value=item,
                    artifact_links=artifact_links,
                )
                for key, item in value.items()
            }
            if result.get("secret") is True:
                result["value"] = None
            if artifact_links and "path" in result:
                result["path"] = f"/artifacts/{result.get('id', '')}"
            return result
        return value

    def safe_path(self, *, name: str) -> Path:
        """Reject absolute paths, traversal, and symlink escape.

        Args:
            name: Relative project path.

        Returns:
            Path contained by the selected project.

        Raises:
            ValueError: When the requested path escapes the root.

        """
        relative: Path = Path(name)
        if (
            not name
            or relative.is_absolute()
            or ".." in relative.parts
            or ("\\" in name)
        ):
            msg: str = "Use a relative project filename without traversal."
            raise ValueError(msg)
        resolved: Path = (self.root / relative).resolve()
        if not resolved.is_relative_to(self.root):
            msg = "The filename escapes the project root."
            raise ValueError(msg)
        return resolved

    def recover(self) -> Workspace | None:
        """Load durable unsaved work without starting any browser operation.

        Returns:
            Recovered workspace or no recovery state.

        """
        if not self._recovery.exists():
            return None
        workspace: Workspace = WorkspaceCodec.load(path=self._recovery)
        if self._recovery_selectors.exists():
            workspace = replace(
                workspace,
                selectors=self._load_selectors(path=self._recovery_selectors),
            )
        self.recovered = True
        return workspace

    def open(self, *, data: dict[str, JsonValue]) -> Workspace:
        """Validate an uploaded document or a project-local workspace file.

        Args:
            data: Workspace JSON or relative filename.

        Returns:
            Validated workspace without changing the controller.

        Raises:
            WorkspaceError: When the import is invalid or unsupported.

        """
        value: JsonValue = data.get("workspace")
        if value is not None:
            if (
                not isinstance(value, dict)
                or value.get("version") != Constants.workspace_version
            ):
                msg: str = (
                    f"Only current version {Constants.workspace_version}"
                    " workspaces are supported."
                )
                raise WorkspaceError(msg)
            candidate: Workspace = WorkspaceCodec.from_json_value(value=value)
            if not candidate.flows:
                msg = "Projects require at least one flow."
                raise WorkspaceError(msg)
            selectors: tuple[SelectorDef, ...] = self._selectors_in(
                document=value,
            )
            value = restore_assets(document=value, root=self.artifact_root)
            result: Workspace = replace(
                WorkspaceCodec.from_json_value(value=value),
                selectors=selectors,
            )
            self.saved_name = None
            self._saved_hash = None
            self._saved_selectors_hash = None
            return result
        name: JsonValue = data.get("filename")
        if not isinstance(name, str):
            msg = "Choose a workspace file to import."
            raise WorkspaceError(msg)
        path: Path = self.safe_path(name=name)
        document: JsonValue = loads(s=path.read_text(encoding="utf-8"))
        candidate = WorkspaceCodec.from_json_value(value=document)
        if not candidate.flows:
            msg = "Projects require at least one flow."
            raise WorkspaceError(msg)
        result = WorkspaceCodec.from_json_value(
            value=restore_assets(
                document=cast(typ="dict[str, JsonValue]", val=document),
                root=self.artifact_root,
            ),
        )
        selectors_path: Path = self._selectors_path(name=name)
        if selectors_path.exists():
            result = replace(
                result,
                selectors=self._load_selectors(path=selectors_path),
            )
            self._saved_selectors_hash = self._hash(path=selectors_path)
        else:
            self._saved_selectors_hash = None
        self.saved_name = name
        self._saved_hash = self._hash(path=path)
        return result

    def save(
        self,
        *,
        workspace: Workspace,
        data: dict[str, JsonValue],
    ) -> None:
        """Atomically save without silently overwriting external edits.

        Args:
            workspace: Current validated document.
            data: Optional relative destination filename.

        Raises:
            ValueError: When the destination exists or changed externally.

        """
        name: str = str(
            object=data.get("filename")
            or self.saved_name
            or "flows.pwflow.json",
        )
        if not name.endswith(".pwflow.json"):
            msg: str = "Workspace filenames must end with .pwflow.json."
            raise ValueError(msg)
        path: Path = self.safe_path(name=name)
        if path.exists() and (
            name != self.saved_name
            or self._hash(path=path) != self._saved_hash
        ):
            msg = (
                "Workspace changed externally; import it or choose a new"
                " filename."
            )
            raise ValueError(msg)
        path.parent.mkdir(parents=True, exist_ok=True)
        selectors_path: Path = self._selectors_path(name=name)
        if selectors_path.exists() and (
            self._saved_selectors_hash is None
            or self._hash(path=selectors_path) != self._saved_selectors_hash
        ):
            msg = (
                "Selectors changed externally; import the project or choose"
                " a new folder."
            )
            raise ValueError(msg)
        # Selectors first: a crash between the two writes leaves an unused
        # selector, never an action that points at a selector that is gone.
        if workspace.selectors or selectors_path.exists():
            SelectorCodec.save(
                path=selectors_path,
                selectors=workspace.selectors,
            )
            self._saved_selectors_hash = self._hash(path=selectors_path)
        write_workspace(
            path=path,
            workspace=self.project_document(
                workspace=workspace,
                include_selectors=False,
            ),
        )
        self.saved_name = name
        self._saved_hash = self._hash(path=path)

    def project_document(
        self,
        *,
        workspace: Workspace,
        include_selectors: bool = True,
    ) -> dict[str, JsonValue]:
        """Export a portable project with owned screenshot assets.

        Args:
            workspace: Current project.
            include_selectors: Add the selectors to the document; saving to
                disk leaves them out because they have their own file.

        Returns:
            Self-contained current-schema project.

        Raises:
            WorkspaceError: When the project is invalid.

        """
        document: JsonValue = WorkspaceCodec.to_json_value(workspace=workspace)
        if not isinstance(document, dict):
            portable: dict[str, JsonValue]
            msg: str = "Project must serialize to an object."
            raise WorkspaceError(msg)
        portable = embed_assets(
            document=document,
            resolve=lambda shot: self.artifact(
                workspace=workspace,
                artifact_id=str(object=shot["id"]),
            ),
        )
        exported: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=self.public_document(value=portable, artifact_links=False),
        )
        if include_selectors and workspace.selectors:
            exported["selectors"] = [
                SelectorCodec.selector_to_json(item=item)
                for item in workspace.selectors
            ]
        return exported

    def discard_recovery(self) -> None:
        """Forget unsaved changes; the next open starts from the saved file."""
        self._recovery.unlink(missing_ok=True)
        self._recovery_selectors.unlink(missing_ok=True)

    def persist_recovery(self, *, workspace: Workspace) -> None:
        """Persist unsaved changes independently of browser unload events.

        Args:
            workspace: Current authoritative state.

        """
        SelectorCodec.save(
            path=self._recovery_selectors,
            selectors=workspace.selectors,
        )
        WorkspaceCodec.save(path=self._recovery, workspace=workspace)

    def artifact(self, *, workspace: Workspace, artifact_id: str) -> Path:
        """Resolve a known screenshot without accepting a client path.

        Args:
            workspace: Authoritative artifact metadata.
            artifact_id: Stable screenshot identifier.

        Returns:
            Validated existing PNG file.

        Raises:
            FileNotFoundError: When the artifact is missing or outside
                ownership.

        """
        item: ScreenshotArtifact | None = next(
            (
                shot
                for shot in workspace.screenshots
                if shot.artifact_id == artifact_id
            ),
            None,
        )
        if item is None:
            msg: str = "Unknown screenshot artifact."
            raise FileNotFoundError(msg)
        path: Path = Path(item.path).resolve()
        if (
            not path.is_relative_to(self.artifact_root)
            or not path.is_file()
            or path.suffix != ".png"
        ):
            msg = "Screenshot unavailable. Run the test again."
            raise FileNotFoundError(msg)
        return path

    @staticmethod
    def _load_selectors(*, path: Path) -> tuple[SelectorDef, ...]:
        """Read a selectors file, reporting problems as workspace errors.

        Args:
            path: Selectors file.

        Returns:
            The selectors.

        Raises:
            WorkspaceError: When the file is unreadable or inconsistent.

        """
        try:
            return SelectorCodec.load(path=path)
        except SelectorError as error:
            raise WorkspaceError(str(object=error)) from error

    @staticmethod
    def _selectors_in(
        *,
        document: dict[str, JsonValue],
    ) -> tuple[SelectorDef, ...]:
        """Read the selectors carried by an uploaded project document.

        Args:
            document: Uploaded workspace document.

        Returns:
            The selectors, or none when the document has no such list.

        Raises:
            WorkspaceError: When the list is malformed.

        """
        items: JsonValue = document.get("selectors")
        if items is None:
            return ()
        try:
            return SelectorCodec.from_json_value(
                value={
                    "version": SelectorConstants.version,
                    "selectors": items,
                },
            )
        except SelectorError as error:
            raise WorkspaceError(str(object=error)) from error

    @staticmethod
    def _hash(*, path: Path) -> str:
        """Hash the small workspace document for conflict detection.

        Args:
            path: Workspace JSON file.

        Returns:
            Content identity of the file.

        """
        return sha256(data=path.read_bytes()).hexdigest()

    def _selectors_path(self, *, name: str) -> Path:
        """Return the selectors file that belongs next to a workspace file.

        Args:
            name: Relative workspace filename.

        Returns:
            ``selectors.pwflow.json`` in the same folder.

        """
        return self.safe_path(
            name=str(object=Path(name).parent / SelectorConstants.file_name),
        )
