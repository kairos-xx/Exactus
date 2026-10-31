# Copyright (c) 2026 João Lopes.
"""Open a URL in the managed browser and wait until the user closes it.

The URL is required — a bare ``python -m exactus.packages.browser`` prints
usage
and exits without launching anything:

    python -m exactus.packages.browser https://example.com
    python -m exactus.packages.browser https://example.com --timeout 30
"""

from typing import TYPE_CHECKING

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.browser.session import BrowserSession

if TYPE_CHECKING:
    from argparse import Action, Namespace


def main() -> int:
    """Open the given URL and wait for the browser window to close.

    Returns:
        Zero when the window closed, one when ``--timeout`` elapsed.

    """
    parser: ExactusArgumentParser = ExactusArgumentParser(
        prog="python -m exactus.packages.browser",
        description=__doc__,
    )
    _url_action: Action = parser.add_argument(
        "url",
        help="Address to display in the browser window.",
    )
    _timeout_action: Action = parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Seconds to wait for the window (default: no limit).",
    )
    arguments: Namespace = parser.parse_args()
    session: BrowserSession = BrowserSession()
    try:
        session.open(url=arguments.url)
        closed: bool = session.wait_closed(timeout=arguments.timeout)
    finally:
        session.close()
    return 0 if closed else 1
