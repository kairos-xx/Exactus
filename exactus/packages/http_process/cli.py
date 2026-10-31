"""Command-line interface for HTTP process inspection."""

from argparse import ArgumentParser, Namespace
from dataclasses import asdict
from json import dumps
from sys import stdout

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.http_process import (
    HttpInspection,
    HttpProcess,
    HttpServer,
    ProcessInfo,
)


class Cli:
    """Expose HTTP process inspection through a command-line interface."""

    @classmethod
    def run(cls) -> int:
        """Run the command-line interface.

        Returns:
            Process exit code.
        """
        arguments: Namespace = cls.parser().parse_args()
        inspector: HttpProcess = HttpProcess(
            command=arguments.command or None,
            timeout=arguments.timeout,
            http_timeout=arguments.http_timeout,
        )
        if arguments.command:
            inspector.start()
            try:
                servers: tuple[HttpServer, ...] = inspector.wait_for_http()
                stdout.write(
                    dumps(
                        obj=[
                            {
                                **asdict(obj=server),
                                "scope": server.scope.value,
                                "family": server.family.value,
                                "process": cls._process_data(
                                    process=server.process,
                                ),
                            }
                            for server in servers
                        ],
                        indent=2,
                        default=str,
                    )
                    + "\n",
                )
            finally:
                inspector.stop()
            return 0
        if arguments.port is None:
            cls.parser().error(
                message="--port is required when no command is supplied",
            )
        result: HttpInspection = inspector.inspect(
            host=arguments.host,
            port=arguments.port,
        )
        stdout.write(
            dumps(obj=cls._inspection_data(result=result), indent=2) + "\n",
        )
        return 0 if result.http else 1

    @staticmethod
    def parser() -> ArgumentParser:
        """Build the command-line parser.

        Returns:
            Configured argument parser.
        """
        parser: ArgumentParser = ExactusArgumentParser(
            prog="http_process",
            description=(
                "Inspect an IP/port or run a process and discover HTTP."
            ),
        )
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int)
        parser.add_argument("--timeout", type=float, default=30.0)
        parser.add_argument("--http-timeout", type=float, default=0.5)
        parser.add_argument(
            "command",
            nargs="*",
            help="Optional command to run and inspect.",
        )
        return parser

    @classmethod
    def _inspection_data(
        cls,
        *,
        result: HttpInspection,
    ) -> dict[
        str,
        str
        | int
        | bool
        | dict[str, str | int | float | list[str] | None]
        | None,
    ]:
        """Convert an inspection result into JSON-compatible data.

        Args:
            result: Inspection result.

        Returns:
            JSON-compatible result mapping.
        """
        return {
            "host": result.host,
            "port": result.port,
            "tcp_open": result.tcp_open,
            "http": result.http,
            "url": result.url,
            "status": result.status,
            "reason": result.reason,
            "process": cls._process_data(process=result.process),
        }

    @staticmethod
    def _process_data(
        *,
        process: ProcessInfo | None,
    ) -> dict[str, str | int | float | list[str] | None] | None:
        """Convert process information into JSON-compatible data.

        Args:
            process: Optional process information.

        Returns:
            JSON-compatible process mapping.
        """
        if process is None:
            return None
        return {
            "pid": process.pid,
            "ppid": process.ppid,
            "name": process.name,
            "executable": (
                None
                if process.executable is None
                else str(object=process.executable)
            ),
            "command": [*process.command],
            "username": process.username,
            "create_time": process.create_time,
        }


def main() -> int:
    """Run the package CLI.

    Returns:
        Process exit code.
    """
    return Cli.run()
