#!/usr/bin/env python3
"""Run a Python HTTP server and discover its dynamically assigned port."""

from contextlib import suppress
from importlib import import_module
from pathlib import Path
from sys import executable, stdout
from sys import path as sys_path

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.http_process import HttpProcess, HttpServer


def main() -> None:
    """Start a server, discover it, and terminate it."""
    runner: HttpProcess = HttpProcess(
        command=[executable, "-m", "http.server", "0", "--bind", "127.0.0.1"],
    )
    runner.start()
    try:
        for server in runner.wait_for_http():
            server_result: HttpServer = server
            stdout.write(f"{server_result}\n")
    finally:
        runner.stop()


if __name__ == "__main__":
    main()
