#!/usr/bin/env python3
# Copyright (c) 2026 João Lopes.
"""Interactive browser lifecycle demonstration."""

from __future__ import annotations

from contextlib import suppress
from importlib import import_module
from operator import attrgetter
from pathlib import Path
from sys import path as import_paths
from sys import stdout
from tempfile import gettempdir
from time import sleep
from typing import TYPE_CHECKING, Final, final

if __package__ in {None, ""}:
    import_paths.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.browser.lifecycle import (
    BrowserBackend,
    BrowserEvent,
    BrowserLifecycle,
)
from exactus.packages.server import local
from exactus.packages.server.process_control import terminate_tree

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace


@final
class Constants:
    """Group module-level constants.

    Attributes:
        duration: Grouped module constant.

    """

    duration: Final[float] = 5.0


class Example:
    """Run the lifecycle demonstration."""

    @classmethod
    def run(cls, arguments: Namespace) -> None:
        """Run the browser example and release every owned resource.

        Args:
            arguments: Parsed CLI arguments.

        Raises:
            RuntimeError: When the bundled demo server does not become ready.
            ValueError: When the backend selection is unsupported.

        """
        url: str | None = arguments.url
        owned_server: tuple[int, Path] | None = None
        if url is None:
            pid: int
            origin: str
            reused: bool
            demo: Path
            pid, origin, reused, demo = cls._start_demo()
            if not local.wait_ready(url=origin, pid=pid):
                if not reused:
                    terminate_tree(pid=pid)
                    local.clear_server_state(path=demo)
                msg: str = "The demo server did not become ready."
                raise RuntimeError(msg)
            if not reused:
                owned_server = (pid, demo)
            url = f"{origin}index.html"
        lifecycle: BrowserLifecycle = BrowserLifecycle(callback=cls._event)
        try:
            if arguments.backend == BrowserBackend.PLAYWRIGHT.value:
                lifecycle.start_playwright(
                    url=url,
                    headless=arguments.headless,
                    executable_path=arguments.chrome,
                )
                _ = lifecycle.wait(
                    timeout=None
                    if arguments.duration <= 0
                    else arguments.duration,
                )
            elif arguments.backend == BrowserBackend.CHROME.value:
                _ = lifecycle.launch_chrome(
                    url=url,
                    executable=arguments.chrome,
                )
                cls._wait_native(
                    lifecycle=lifecycle,
                    duration=arguments.duration,
                )
            else:
                msg = f"Unsupported browser backend: {arguments.backend!r}"
                raise ValueError(msg)
        except KeyboardInterrupt:
            pass
        finally:
            lifecycle.close()
            if owned_server is not None:
                terminate_tree(pid=owned_server[0])
                local.clear_server_state(path=owned_server[1])

    @staticmethod
    def parser() -> ArgumentParser:
        """Build the example argument parser.

        Returns:
            Configured parser.

        """
        parser: ArgumentParser = ExactusArgumentParser(description=__doc__)
        _ = parser.add_argument(
            "url",
            nargs="?",
            default=None,
            help="Page to open (default: the bundled web/ demo).",
        )
        _ = parser.add_argument(
            "--backend",
            choices=tuple(map(attrgetter("value"), BrowserBackend)),
            default=BrowserBackend.PLAYWRIGHT.value,
        )
        _ = parser.add_argument("--chrome", type=Path)
        _ = parser.add_argument("--headless", action="store_true")
        _ = parser.add_argument(
            "--duration",
            type=float,
            default=Constants.duration,
            help=(
                "Seconds to keep the browser alive (default: %(default)s; "
                "0 waits until exit)."
            ),
        )
        return parser

    @staticmethod
    def _event(event: BrowserEvent) -> None:
        """Print one lifecycle event.

        Args:
            event: Event snapshot.

        """
        _ = stdout.write(
            f"{event.timestamp.isoformat()}"
            f" "
            f"{event.backend.value}"
            f":"
            f"{event.event.value}"
            f" pid="
            f"{event.pid}"
            f" url="
            f"{event.url!r}"
            f" title="
            f"{event.title!r}"
            f" exit="
            f"{event.exit_code!r}"
            f"\n",
        )

    @staticmethod
    def _start_demo() -> tuple[int, str, bool, Path]:
        """Serve the bundled page through the shared loopback server.

        Returns:
            Server PID, ready origin, reuse flag, and demo directory.

        """
        demo: Path = Path(__file__).resolve().parent / "web"
        existing: tuple[int, int] | None = local.reuse_server(path=demo)
        if existing is not None:
            return (
                existing[0],
                f"http://127.0.0.1:{existing[1]}/",
                True,
                demo,
            )
        pid: int
        origin: str
        reused: bool
        pid, origin, reused = local.serve(
            path=demo,
            log=Path(gettempdir()) / "exactus-browser.log",
        )
        return (pid, origin, reused, demo)

    @staticmethod
    def _wait_native(*, lifecycle: BrowserLifecycle, duration: float) -> None:
        """Wait for a native browser process or duration expiry.

        Args:
            lifecycle: Active browser lifecycle controller.
            duration: Maximum lifetime in seconds; zero waits indefinitely.

        """
        while (
            lifecycle.process is None or lifecycle.process.poll() is None
        ) and duration <= 0:
            sleep(0.1)
        if duration > 0:
            sleep(duration)


def main() -> None:
    """Run the command-line example."""
    Example.run(arguments=Example.parser().parse_args())


if __name__ == "__main__":
    main()
