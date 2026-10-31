"""Carry recorded URLs to wherever the application under test runs now."""

from __future__ import annotations

from ipaddress import IPv4Address
from urllib.parse import SplitResult, urlsplit, urlunsplit

__all__: list[str] = ["rebase_url"]


class Constants:
    """Hosts that mean "this computer", whose port changes between runs.

    Attributes:
        local_hosts: Hostnames and addresses equivalent to this machine.

    """

    local_hosts: frozenset[str] = frozenset(
        {"localhost", "127.0.0.1", "::1", str(object=IPv4Address(address=0))},
    )


def rebase_url(*, url: str, origin: str | None) -> str:
    """Move a local URL onto the target's origin, keeping path and query.

    A flow recorded against ``http://127.0.0.1:5173/cart?id=1`` must still
    work when the service restarts on another port, or when the same flow is
    pointed at a staging address. Only local URLs move: a step that visits an
    outside site keeps visiting it.

    Args:
        url: Address stored in the flow.
        origin: Scheme, host and port of the current target, if any.

    Returns:
        The URL on the target's origin, or ``url`` unchanged.

    """
    if not origin:
        return url
    recorded: SplitResult = urlsplit(url=url)
    target: SplitResult = urlsplit(url=origin)
    if (
        recorded.scheme not in {"http", "https"}
        or target.scheme not in {"http", "https"}
        or recorded.hostname not in Constants.local_hosts
        or (recorded.scheme, recorded.netloc) == (target.scheme, target.netloc)
    ):
        return url
    return urlunsplit(
        components=(
            target.scheme,
            target.netloc,
            recorded.path,
            recorded.query,
            recorded.fragment,
        ),
    )
