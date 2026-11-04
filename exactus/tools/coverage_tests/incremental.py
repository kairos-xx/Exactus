# Copyright (c) 2026
"""Reuse verified passing coverage shards with content-addressed snapshots."""

from __future__ import annotations

from base64 import b64decode, b64encode
from binascii import Error as Base64Error
from collections import Counter
from hashlib import sha256
from json import dumps
from os import fsync
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Final, cast, final

from exactus.tools.common.process_control import read_json

if TYPE_CHECKING:
    from collections.abc import Sequence

    from exactus.tools.common.json_types import JsonValue


@final
class BaselineLimits:
    """Bound regenerable cache data and metadata.

    Attributes:
        data_bytes: Maximum total snapshot bytes retained locally.
        metadata_bytes: Maximum serialized baseline size.
        files: Maximum number of content-addressed snapshots.

    """

    data_bytes: Final[int] = 256 * 1024 * 1024
    metadata_bytes: Final[int] = 16 * 1024 * 1024
    files: Final[int] = 4096


def _atomic_bytes(*, path: Path, data: bytes) -> None:
    """Replace an owned cache file atomically on the same filesystem.

    Args:
        path: Cache destination.
        data: Complete serialized payload.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=path.parent,
        prefix=".snapshot-",
        delete=False,
    ) as temporary:
        staging: Path = Path(temporary.name)
        try:
            temporary.write(data)
            temporary.flush()
            fsync(fd=temporary.fileno())
        except BaseException:
            staging.unlink(missing_ok=True)
            raise
    try:
        staging.replace(target=path)
    finally:
        staging.unlink(missing_ok=True)


class ShardBaseline:
    """Own one passing baseline; failed runs cannot replace its manifest.

    Attributes:
        reused: Zero-based shard indexes restored from the passing baseline.
        executed: Zero-based shard indexes actually executed in this run.

    """

    def __init__(self, *, directory: Path, identity: str) -> None:
        """Load a versioned baseline bound to the analysis configuration.

        Args:
            directory: Private runtime cache directory.
            identity: Toolchain, configuration and shared-input digest.

        """
        self._directory: Path = directory
        self._identity: str = identity
        self._previous: dict[str, JsonValue] = (
            read_json(
                path=directory / "manifest.json",
            )
            or {}
        )
        if (
            self._previous.get("identity") != identity
            or self._previous.get("version") != 1
        ):
            self._previous = {}
        self._pending: dict[str, JsonValue] = {}
        self.reused: list[int] = []
        self.executed: list[int] = []

    @staticmethod
    def key(*, shard: Sequence[str]) -> str:
        """Identify a shard independently of learned scheduling weights.

        Args:
            shard: Pytest file paths or node identifiers.

        Returns:
            Stable content key.

        """
        return sha256(data="\0".join(sorted(shard)).encode()).hexdigest()

    def layout(
        self,
        *,
        fallback: tuple[tuple[str, ...], ...],
    ) -> tuple[tuple[str, ...], ...]:
        """Keep previous isolation boundaries when the selected nodes agree.

        Args:
            fallback: Newly planned isolated shards.

        Returns:
            Previous layout or the complete fresh plan.

        """
        raw: JsonValue = self._previous.get("layout")
        if not isinstance(raw, list) or not all(
            isinstance(shard, list)
            and shard
            and all(isinstance(node, str) for node in shard)
            for shard in raw
        ):
            return fallback
        layout: tuple[tuple[str, ...], ...] = tuple(
            tuple(cast(typ="list[str]", val=shard)) for shard in raw
        )
        return (
            layout
            if Counter(node for shard in layout for node in shard)
            == Counter(node for shard in fallback for node in shard)
            else fallback
        )

    def restore(
        self,
        *,
        shard: tuple[str, ...],
        fingerprint: str,
        target: Path,
    ) -> CompletedProcess[bytes] | None:
        """Verify all snapshot checksums before restoring any shard output.

        Args:
            shard: Exact test selection.
            fingerprint: Current transitive input identity.
            target: Per-shard coverage basename inside the run scratch tree.

        Returns:
            Prior passing process result, or None on a cache miss.

        """
        entries: JsonValue = self._previous.get("shards")
        key: str = self.key(shard=shard)
        entry: JsonValue = (
            entries.get(key) if isinstance(entries, dict) else None
        )
        if not isinstance(entry, dict):
            entry = {}
        files: JsonValue = (
            entry.get("files")
            if entry.get("fingerprint") == fingerprint
            else None
        )
        if not isinstance(files, list) or not files:
            return None
        restored: list[bytes] = []
        try:
            for digest in files:
                if (
                    not isinstance(digest, str)
                    or len(digest) != sha256().digest_size * 2
                    or any(c not in "0123456789abcdef" for c in digest)
                ):
                    return None
                data: bytes = (self._directory / digest).read_bytes()
                if sha256(data=data).hexdigest() != digest:
                    return None
                restored.append(data)
            output: JsonValue = entry.get("stdout")
            errors: JsonValue = entry.get("stderr")
            if not isinstance(output, str) or not isinstance(errors, str):
                return None
            stdout: bytes = b64decode(s=output, validate=True)
            stderr: bytes = b64decode(s=errors, validate=True)
        except (Base64Error, OSError, ValueError):
            return None
        target.parent.mkdir(parents=True, exist_ok=True)
        for index, data in enumerate(iterable=restored):
            target.with_name(name=f"{target.name}.cached-{index}").write_bytes(
                data=data,
            )
        self._pending[key] = entry
        return CompletedProcess(
            args=list(shard),
            returncode=0,
            stdout=stdout,
            stderr=stderr,
        )

    def stage(
        self,
        *,
        shard: tuple[str, ...],
        fingerprint: str,
        source: Path,
        result: CompletedProcess[bytes],
    ) -> None:
        """Snapshot successful data before the scratch directory is cleaned.

        Args:
            shard: Exact test selection.
            fingerprint: Current input identity.
            source: Per-shard coverage basename.
            result: Actual process outcome.

        """
        if result.returncode != 0:
            return
        paths: list[Path] = sorted(
            source.parent.glob(pattern=f"{source.name}.*"),
        )
        if source.is_file():
            paths.append(source)
        if not paths:
            return
        self._directory.mkdir(parents=True, exist_ok=True)
        existing: tuple[Path, ...] = tuple(
            path for path in self._directory.iterdir() if path.is_file()
        )
        if (
            len(existing) + len(paths) > BaselineLimits.files
            or sum(path.stat().st_size for path in (*existing, *paths))
            > BaselineLimits.data_bytes
        ):
            return
        hashes: list[JsonValue] = []
        for path in paths:
            data: bytes = path.read_bytes()
            digest: str = sha256(data=data).hexdigest()
            destination: Path = self._directory / digest
            if not destination.is_file():
                _atomic_bytes(path=destination, data=data)
            hashes.append(digest)
        stdout: bytes = b64encode(s=result.stdout or b"")
        stderr: bytes = b64encode(s=result.stderr or b"")
        self._pending[self.key(shard=shard)] = {
            "fingerprint": fingerprint,
            "files": hashes,
            "stdout": stdout.decode(encoding="ascii"),
            "stderr": stderr.decode(encoding="ascii"),
        }

    def commit(
        self,
        *,
        shards: tuple[tuple[str, ...], ...],
        passed: bool,
    ) -> None:
        """Promote only a complete baseline after every coverage gate passes.

        Args:
            shards: Final isolated execution layout.
            passed: Whole-run status including coverage and JavaScript gates.

        """
        if not passed or any(
            self.key(shard=shard) not in self._pending for shard in shards
        ):
            return
        payload: dict[str, JsonValue] = {
            "version": 1,
            "identity": self._identity,
            "layout": cast(
                typ="JsonValue",
                val=[list(shard) for shard in shards],
            ),
            "shards": self._pending,
        }
        data: bytes = dumps(obj=payload, sort_keys=True).encode()
        if len(data) <= BaselineLimits.metadata_bytes:
            _atomic_bytes(path=self._directory / "manifest.json", data=data)
