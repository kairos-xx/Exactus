"""Update Python virtual-environment shebangs to the current project path."""

from .core import Settings, ShebangUpdater, main

__all__: tuple[str, ...] = ("Settings", "ShebangUpdater", "main")
