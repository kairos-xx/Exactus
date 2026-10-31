# Copyright (c) 2026
"""Resolve the launcher baked into generated shell adapters.

Generated adapters must invoke something that exists even when the
command is not on ``PATH``, so the invocation path is baked in: a
zipapp or script keeps its absolute path, ``python -m <command>``
becomes ``<python> -m <command>``, and a ``.py`` script gains its
interpreter.
"""

from __future__ import annotations

from pathlib import Path
from shutil import which
from sys import argv, executable


def resolve_launcher(*, command_name: str) -> tuple[str, ...]:
    """Resolve the executable the current process was invoked as.

    Args:
        command_name: Registered command name; becomes the ``-m``
            module and the fallback executable name.

    Returns:
        Executable and fixed arguments for the adapters.

    """
    invoked: Path = Path(argv[0])
    if invoked.name == "__main__.py":
        return (executable, "-m", command_name)
    if invoked.parent == Path() and not invoked.is_file():
        found: str | None = which(cmd=argv[0])
        if found is None:
            return (command_name,)
        invoked = Path(found)
    absolute: Path = invoked.resolve()
    if invoked.suffix == ".py" or is_zipapp(path=absolute):
        return (executable, str(object=absolute))
    return (str(object=absolute),)


def is_zipapp(*, path: Path) -> bool:
    """Return whether an executable is a Python zipapp.

    A zipapp's own ``/usr/bin/env python3`` shebang may resolve to an
    interpreter without the toolkit's dependencies, so adapters must
    invoke it through the interpreter that is running now.

    Args:
        path: Resolved executable path.

    Returns:
        Whether the file carries the zip signature.

    """
    try:
        with path.open(mode="rb") as stream:
            head: bytes = stream.read(4096)
    except OSError:
        return False
    if head.startswith(b"#!"):
        head = head.split(sep=b"\n", maxsplit=1)[-1]
    return head.startswith(b"PK")
