# Copyright (c) 2026
"""Select monitoring only where the installed tracer supports the workload."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec
from os import environ
from sys import version_info


@dataclass(frozen=True, slots=True)
class TracerCapabilities:
    """Describe independently testable monitoring prerequisites.

    Attributes:
        python: Interpreter major/minor pair.
        coverage: Installed coverage release tuple.
        green_threads: Whether green-thread switching may be required.
        dynamic_contexts: Whether pytest requests dynamic test contexts.

    """

    python: tuple[int, int]
    coverage: tuple[int, ...]
    green_threads: bool
    dynamic_contexts: bool

    def sysmon(self, *, branch: bool) -> bool:
        """Return whether monitoring can preserve requested coverage semantics.

        Args:
            branch: Whether branch arcs must be measured.

        Returns:
            Whether the validated monitoring implementation is available.

        """
        return (
            self.python >= ((3, 14) if branch else (3, 12))
            and self.coverage >= (7, 16, 2)
            and not self.green_threads
            and not self.dynamic_contexts
        )


def monitoring_supported(
    *,
    branch: bool,
    pytest_args: tuple[str, ...],
) -> bool:
    """Probe the installed runtime without enabling unsupported tracing.

    Args:
        branch: Required branch measurement.
        pytest_args: Forwarded pytest context options.

    Returns:
        Whether to explicitly select sysmon; false preserves native defaults.

    """
    if environ.get("COVERAGE_CORE"):
        return False
    try:
        release: tuple[int, ...] = tuple(
            int(part)
            for part in version(distribution_name="coverage").split(sep=".")
        )
    except (PackageNotFoundError, ValueError):
        return False
    return TracerCapabilities(
        python=(version_info.major, version_info.minor),
        coverage=release,
        green_threads=any(
            find_spec(name=name) is not None
            for name in ("greenlet", "eventlet", "gevent")
        ),
        dynamic_contexts=any(
            "cov-context" in argument for argument in pytest_args
        ),
    ).sysmon(branch=branch)
