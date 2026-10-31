"""Capture a URL screenshot (``python -m exactus.packages.screenshot``)."""

from asyncio import run
from pathlib import Path
from sys import modules, stdout
from typing import TYPE_CHECKING, cast

from exactus.packages.argument_parser import ExactusArgumentParser

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from types import ModuleType

    from exactus.packages.screenshot import Capture, CaptureSpec, Screenshot


def main() -> int:
    """Capture ``url`` into a PNG file.

    Returns:
        Zero after the screenshot is saved.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        prog="screenshot",
        description="Capture a fully exposed screenshot of a URL.",
    )
    _ = parser.add_argument("url", help="URL to capture.")
    _ = parser.add_argument(
        "--target",
        default="body",
        help="CSS selector to expose fully (default: body).",
    )
    _ = parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination PNG path.",
    )
    _ = parser.add_argument(
        "--width",
        type=int,
        default=1440,
        help="Viewport width in CSS pixels (default: 1440).",
    )
    _ = parser.add_argument(
        "--height",
        type=int,
        default=900,
        help="Viewport height in CSS pixels (default: 900).",
    )
    arguments: Namespace = parser.parse_args()
    module: ModuleType = modules["importlib"].import_module(
        name="exactus.packages.screenshot",
    )
    spec_type: type[CaptureSpec] = cast(
        typ="type[CaptureSpec]",
        val=module.CaptureSpec,
    )
    screenshot: type[Screenshot] = cast(
        typ="type[Screenshot]",
        val=module.Screenshot,
    )
    result: Capture = run(
        main=screenshot.capture(
            url=arguments.url,
            target=arguments.target,
            spec=spec_type(
                path=arguments.output,
                width=arguments.width,
                height=arguments.height,
            ),
        ),
    )
    stdout.write(f"{result.path}\n")
    return 0
