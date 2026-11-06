# Copyright (c) 2026 Project contributors
"""Embed and restore verified PNG assets in portable Studio projects."""

from __future__ import annotations

from base64 import b64decode, b64encode
from binascii import Error as Base64Error
from hashlib import sha256
from io import BytesIO
from json import dumps, loads
from os import fsync
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Final, cast, final

from PIL import Image

if TYPE_CHECKING:
    from collections.abc import Callable

    from exactus.tools.record.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        sha256_length: Grouped module constant.
        max_asset_bytes: Grouped module constant.
        max_project_assets: Grouped module constant.

    """

    sha256_length: Final[int] = 64
    max_asset_bytes: Final[int] = 8 * 1024 * 1024
    max_project_assets: Final[int] = 32 * 1024 * 1024


def embed_assets(
    *,
    document: dict[str, JsonValue],
    resolve: Callable[[dict[str, JsonValue]], Path],
) -> dict[str, JsonValue]:
    """Embed known PNG screenshots without depending on machine paths.

    Args:
        document: Serialized current project.
        resolve: Trusted resolver enforcing the caller's artifact ownership.

    Returns:
        Project with deduplicated inline assets and relative asset references.

    """
    result: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(s=dumps(obj=document)),
    )
    assets: dict[str, JsonValue] = {}
    screenshots: JsonValue | None = result.get("screenshots", [])
    if isinstance(screenshots, list):
        for shot in screenshots:
            if not isinstance(shot, dict):
                continue
            data: bytes = resolve(shot).read_bytes()
            digest: str = sha256(data=data).hexdigest()
            _validate_png(data=data, digest=digest, shot=shot)
            assets[digest] = b64encode(s=data).decode(encoding="ascii")
            shot["path"] = f"assets/{digest}.png"
    result["assets"] = assets
    return result


def _validate_png(
    *,
    data: bytes,
    digest: str,
    shot: dict[str, JsonValue],
) -> None:
    """Verify screenshot hashes, dimensions, format and size.

    Args:
        data: Decoded image bytes.
        digest: Asset identifier.
        shot: Current screenshot metadata.

    Raises:
        ValueError: When metadata or PNG content is invalid.

    """
    if (
        len(data) > Constants.max_asset_bytes
        or sha256(data=data).hexdigest() != digest
        or shot.get("sha256") != digest
    ):
        msg: str = (
            "Screenshot asset size or SHA256 does not match its metadata."
        )
        raise ValueError(msg)
    with Image.open(fp=BytesIO(initial_bytes=data)) as image:
        if image.format != "PNG" or image.size != (
            shot.get("width"),
            shot.get("height"),
        ):
            msg = "Screenshot asset format or dimensions do not match."
            raise ValueError(msg)
        image.verify()


def _decode_asset(
    *,
    shot: dict[str, JsonValue],
    assets: dict[str, JsonValue],
) -> tuple[str, bytes]:
    """Decode and verify one inline screenshot.

    Args:
        shot: Screenshot metadata.
        assets: Inline assets indexed by SHA256.

    Returns:
        Verified asset hash and bytes.

    Raises:
        ValueError: When an asset is missing or invalid.

    """
    digest: str = str(object=shot.get("sha256", ""))
    if (
        len(digest) != Constants.sha256_length
        or any(character not in "0123456789abcdef" for character in digest)
        or shot.get("path") != f"assets/{digest}.png"
    ):
        msg: str = "Project screenshot must reference its SHA256 asset."
        raise ValueError(msg)
    encoded: JsonValue | None = assets.get(digest)
    if (
        not isinstance(encoded, str)
        or len(encoded) > Constants.max_asset_bytes * 2
    ):
        msg = "Screenshot asset is missing or exceeds the size limit."
        raise ValueError(msg)
    try:
        data: bytes = b64decode(s=encoded, validate=True)
    except Base64Error as error:
        msg = "Screenshot asset has invalid base64 encoding."
        raise ValueError(msg) from error
    _validate_png(data=data, digest=digest, shot=shot)
    return (digest, data)


def _pending_assets(
    *,
    shots: list[JsonValue],
    assets: dict[str, JsonValue],
) -> dict[str, bytes]:
    """Verify all referenced PNGs before modifying the artifact directory.

    Args:
        shots: Imported screenshot metadata.
        assets: Inline image data.

    Returns:
        Verified images indexed by content hash.

    Raises:
        TypeError: When screenshot metadata is not an object.

    """
    pending: dict[str, bytes] = {}
    for shot in shots:
        if not isinstance(shot, dict):
            msg: str = "Screenshot metadata must be an object."
            raise TypeError(msg)
        digest, data = _decode_asset(shot=shot, assets=assets)
        pending[digest] = data
    return pending


def restore_assets(
    *,
    document: dict[str, JsonValue],
    root: Path,
) -> dict[str, JsonValue]:
    """Restore verified assets exclusively into the service artifact root.

    Validate every blob before writing any file.

    Args:
        document: Imported current project.
        root: Explicit service-owned artifact directory.

    Returns:
        Project with verified local screenshot paths.

    Raises:
        TypeError: When the operation cannot complete with these arguments.
        ValueError: When references, encoding or image metadata are invalid.

    """
    assets: JsonValue | None = document.get("assets")
    if assets is None:
        return document
    if not isinstance(assets, dict):
        msg: str = "Project assets must be a SHA256-to-base64 object."
        result: dict[str, JsonValue]
        raise TypeError(msg)
    result = cast(typ="dict[str, JsonValue]", val=loads(s=dumps(obj=document)))
    shots: JsonValue | None = result.get("screenshots", [])
    if not isinstance(shots, list):
        pending: dict[str, bytes]
        msg = "Project screenshots must be a list."
        raise TypeError(msg)
    pending = _pending_assets(shots=shots, assets=assets)
    if sum(map(len, pending.values())) > Constants.max_project_assets:
        msg = "Project assets exceed the total size limit."
        raise ValueError(msg)
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for digest in pending:
        if (root / f"{digest}.png").is_symlink():
            msg = "Screenshot destinations cannot be symbolic links."
            raise ValueError(msg)
    for digest, data in pending.items():
        path: Path = root / f"{digest}.png"
        with NamedTemporaryFile(dir=root, delete=False) as stream:
            temporary: Path = Path(stream.name)
            stream.write(data)
            stream.flush()
            fsync(fd=stream.fileno())
        try:
            temporary.replace(target=path)
        finally:
            temporary.unlink(missing_ok=True)
    for shot in shots:
        if isinstance(shot, dict):
            shot["path"] = str(object=root / f"{shot['sha256']}.png")
    result.pop("assets", None)
    return result
