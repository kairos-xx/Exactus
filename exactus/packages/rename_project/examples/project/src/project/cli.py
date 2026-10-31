# Copyright (c) 2026
"""Command line entry point for ``project``."""

from sys import stdout

from project import Constants, Project


def main() -> int:
    """Print the Project banner.

    Returns:
        Process exit status, always ``0``.

    """
    _ = stdout.write(
        f"Project {Constants.project_version} — "
        f"{Project().greet(name='world')}\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
