# Copyright (c) 2026
"""Command line entry point for ``demo_app``."""

from sys import stdout

from demo_app import Constants, DemoApp


def main() -> int:
    """Print the DemoApp banner.

    Returns:
        Process exit status, always ``0``.

    """
    _ = stdout.write(
        f"DemoApp {Constants.demo_app_version} — "
        f"{DemoApp().greet(name='world')}\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
