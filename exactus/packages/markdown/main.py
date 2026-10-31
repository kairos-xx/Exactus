# Copyright (c) 2026
"""Command-line interface for the Markdown template engine."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from json import dumps
from pathlib import Path
from sys import modules
from typing import TYPE_CHECKING, TextIO

from exactus.packages.argument_parser import ExactusArgumentParser

from .api import load_json
from .engine import MarkdownEngine
from .errors import MappingError, TemplateEngineError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .json_types import JsonValue


class Arguments(Namespace):
    """Typed command-line arguments.

    Attributes:
        template: Template path.
        data: Source JSON path.
        mapping: Optional mapping JSON path.
        output: Optional output path.
        template_root: Additional template roots.
        context_output: Optional path to dump the render context.
        lenient: Render undefined variables as empty text.
        validate_only: Render but do not emit output.

    """

    template: Path
    data: Path
    mapping: Path | None
    output: Path | None
    template_root: list[Path]
    context_output: Path | None
    lenient: bool
    validate_only: bool


class Streams:
    """Resolve the process streams when they are used, not at import."""

    @staticmethod
    def stdout() -> TextIO:
        """Return the current standard output stream.

        Returns:
            ``sys.stdout`` as it is right now.

        """
        stream: TextIO = modules["sys"].stdout
        return stream

    @staticmethod
    def stderr() -> TextIO:
        """Return the current standard error stream.

        Returns:
            ``sys.stderr`` as it is right now.

        """
        stream: TextIO = modules["sys"].stderr
        return stream


class Cli:
    """Run the template engine from the command line."""

    @classmethod
    def run(
        cls,
        *,
        argv: Sequence[str] | None = None,
        out: TextIO | None = None,
        err: TextIO | None = None,
    ) -> int:
        """Render according to ``argv``.

        Args:
            argv: Command-line arguments, defaulting to ``sys.argv``.
            out: Stream for the rendered Markdown, default ``sys.stdout``.
            err: Stream for error messages, default ``sys.stderr``.

        Returns:
            ``0`` on success, ``2`` on any load or render error.

        """
        sink: TextIO = Streams.stdout() if out is None else out
        errors: TextIO = Streams.stderr() if err is None else err
        args: Arguments = cls.parser().parse_args(
            args=argv,
            namespace=Arguments(),
        )
        try:
            source: JsonValue = load_json(value=args.data)
            spec: dict[str, JsonValue] | None = cls._mapping(path=args.mapping)
            engine: MarkdownEngine = MarkdownEngine(
                roots=(args.template.parent, *args.template_root),
                strict=not args.lenient,
            )
            context: dict[str, JsonValue] = engine.context(
                source=source,
                mapping=spec,
            )
            rendered: str = engine.render_context(
                template=args.template,
                context=context,
            )
            if args.context_output is not None:
                args.context_output.write_text(
                    data=dumps(obj=context, ensure_ascii=False, indent=2)
                    + "\n",
                    encoding="utf-8",
                )
            if args.validate_only:
                sink.write("Template validation succeeded.\n")
            elif args.output is not None:
                args.output.write_text(data=rendered, encoding="utf-8")
            else:
                sink.write(rendered)
        except (OSError, TemplateEngineError) as exc:
            errors.write(f"error: {exc}\n")
            return 2
        return 0

    @staticmethod
    def parser() -> ArgumentParser:
        """Build the argument parser.

        Returns:
            The configured parser.

        """
        parser: ArgumentParser = ExactusArgumentParser(
            prog="python -m exactus.packages.markdown",
            description="JSON-driven Markdown template engine",
        )
        parser.add_argument("template", type=Path)
        parser.add_argument("data", type=Path)
        parser.add_argument("-m", "--mapping", type=Path)
        parser.add_argument("-o", "--output", type=Path)
        parser.add_argument(
            "--template-root",
            action="append",
            type=Path,
            default=[],
        )
        parser.add_argument("--context-output", type=Path)
        parser.add_argument("--lenient", action="store_true")
        parser.add_argument("--validate-only", action="store_true")
        return parser

    @staticmethod
    def _mapping(*, path: Path | None) -> dict[str, JsonValue] | None:
        """Load the optional mapping file.

        Args:
            path: Mapping JSON path, or ``None``.

        Returns:
            The mapping object, or ``None`` when no path is given.

        Raises:
            MappingError: The file does not hold a JSON object.

        """
        if path is None:
            return None
        spec: JsonValue = load_json(value=path)
        if not isinstance(spec, dict):
            msg: str = "Mapping must be a JSON object"
            raise MappingError(msg)
        return spec


def main(
    *,
    argv: Sequence[str] | None = None,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    """Run the command-line interface.

    Args:
        argv: Command-line arguments, defaulting to ``sys.argv``.
        out: Stream for the rendered Markdown, default ``sys.stdout``.
        err: Stream for error messages, default ``sys.stderr``.

    Returns:
        The process exit code.

    """
    return Cli.run(argv=argv, out=out, err=err)
