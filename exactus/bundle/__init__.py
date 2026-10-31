# Copyright (c) 2026
"""Packaged executable fingerprints, freshness checks, and host routing.

Importing a leaf module through this package resolves the host platform
automatically: ``from exactus.bundle import partition_fs`` routes to the
matching ``exactus.bundle.<os>/<arch>/partition_fs`` implementation.
"""
from __future__ import annotations

from importlib import import_module
from pathlib import Path
from platform import libc_ver, machine, system
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType
def _host_musl() -> bool:
    """Whether this host runs a musl-based Linux.

    Returns:
        ``True`` when the loader or reported libc is musl.

    """
    return "musl" in libc_ver()[0].lower() or any(
        loader.is_file()
        for root in ("/lib", "/usr/lib")
        for loader in Path(root).glob(pattern="ld-musl-*.so*")
    )
def _host_leaf_candidates() -> tuple[tuple[str, ...], ...]:
    """Bundle leaf package parts for this host, best first.

    Returns:
        Ordered relative package path tuples such as
        ``("linux", "glibc", "amd64")``, empty on unsupported hosts.

    """
    os_dir: str | None = {
        "Linux": "linux",
        "Darwin": "macos",
        "Windows": "windows",
    }.get(system())
    arch_dir: str | None = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(machine().lower())
    if os_dir is None or arch_dir is None:
        return ()
    if os_dir == "linux":
        glibc: tuple[str, ...] = (os_dir, "glibc", arch_dir)
        if _host_musl():
            return ((os_dir, "musl", arch_dir), glibc)
        return (glibc,)
    return ((os_dir, arch_dir),)
def host_leaf() -> Path | None:
    """Return the bundle leaf package directory matching this host.

    Returns:
        Existing ``bundle/<os>/<arch>`` leaf directory — for Linux, the
        musl leaf on musl hosts and the glibc leaf otherwise — or
        ``None`` when no bundle covers this platform.

    """
    base: Path = Path(__file__).resolve().parent
    for parts in _host_leaf_candidates():
        leaf: Path = base.joinpath(*parts)
        if (leaf / "__init__.py").is_file():
            return leaf
    return None
def _host_leaf_package() -> str | None:
    """Dotted package name of this host's bundle leaf.

    Returns:
        Name such as ``exactus.bundle.linux.glibc.amd64``, or ``None``
        when no leaf exists.

    """
    leaf: Path | None = host_leaf()
    if leaf is None:
        return None
    relative: Path = leaf.relative_to(Path(__file__).resolve().parent)
    return ".".join((__name__, *relative.parts))
def __getattr__(name: str) -> ModuleType:
    """Route leaf imports to this host's bundle package.

    Args:
        name: Attribute requested on ``exactus.bundle``.

    Returns:
        The leaf module or subpackage named ``name``.

    Raises:
        AttributeError: When no host leaf exists or the leaf does not
            provide ``name``.
        ModuleNotFoundError: When the leaf submodule exists but one of
            its own imports is missing.

    """
    leaf: str | None = _host_leaf_package()
    if leaf is not None:
        module_name: str = f"{leaf}.{name}"
        try:
            module: ModuleType = import_module(name=module_name)
        except ModuleNotFoundError as exc:
            if exc.name != module_name:
                raise
        else:
            globals()[name] = module
            return module
    msg: str = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
def __dir__() -> list[str]:
    """List package attributes plus the host leaf's importables.

    Returns:
        Sorted attribute names for completion and introspection.

    """
    names: set[str] = set(globals())
    leaf: Path | None = host_leaf()
    if leaf is not None:
        names.update(
            child.stem
            for child in leaf.glob("*.py")
            if child.stem not in {"__init__", "__main__"}
        )
        names.update(
            child.name
            for child in leaf.iterdir()
            if child.is_dir() and (child / "__init__.py").is_file()
        )
    return sorted(names)
