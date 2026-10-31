"""Inspect an already-running local HTTP endpoint."""

from sys import stdout

from exactus.packages.http_process import HttpInspection, HttpProcess


def main() -> None:
    """Inspect a local endpoint and write the result."""
    inspector: HttpProcess = HttpProcess()
    result: HttpInspection = inspector.inspect(host="127.0.0.1", port=8000)
    stdout.write(f"{result}\n")


if __name__ == "__main__":
    main()
