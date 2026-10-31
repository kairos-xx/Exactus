# Copyright (c) 2026
"""Install portable-launcher completion and refresh changed bundles."""

from __future__ import annotations

from hashlib import file_digest
from pathlib import Path
from sys import argv, stderr
from textwrap import dedent

from exactus.packages.completion.install import (
    InstallResult,
    InstallStatus,
    Registration,
    install,
)
from exactus.packages.completion.launcher import is_zipapp, resolve_launcher
from exactus.packages.completion.profiles import profile_paths

from .main import Constants


def ensure_completion(*, home: Path | None = None) -> None:
    """Refresh user completion on ordinary portable-launcher invocations.

    Args:
        home: Optional isolated user home for verification.

    """
    bundle: Path = Path(argv[0]).resolve()
    if not is_zipapp(path=bundle):
        return
    try:
        with bundle.open(mode="rb") as stream:
            revision: str = file_digest(stream, "sha256").hexdigest()
        target: Path = Path.home() if home is None else home
        launcher: tuple[str, ...] = resolve_launcher(
            command_name=Constants.command_name,
        )
        aliases: tuple[str, ...] = tuple(
            dict.fromkeys((bundle.name, argv[0], str(object=bundle))),
        )
        changed: int = 0
        for shell, profile in profile_paths(
            home=target,
            command_name=Constants.command_name,
        ):
            try:
                result: InstallResult = install(
                    shell=shell,
                    command_name=Constants.command_name,
                    launcher=launcher,
                    home=target,
                    registration=Registration(
                        path=profile,
                        revision=revision,
                        aliases=aliases,
                    ),
                )
                changed += int(result.changed)
                if result.status == InstallStatus.BROKEN:
                    _ = stderr.write(
                        f"Completion: {result.detail}: {profile}\n",
                    )
            except (OSError, UnicodeError) as error:
                _ = stderr.write(
                    f"Completion: cannot update {profile}: {error}\n",
                )
        if changed:
            _ = stderr.write(
                dedent(
                    text=(
                        "    Completion installed/updated; open a new term"
                        "inal or reload your shell profile.\n    "
                    ),
                ),
            )
    except OSError as error:
        _ = stderr.write(f"Completion: cannot inspect bundle: {error}\n")
