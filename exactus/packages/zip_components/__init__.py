# Copyright (c) 2026 João Lopes.
"""Public API for reproducible source-bundle archives."""

from .core import (
    BundleOptions,
    BundleResult,
    Selection,
    available_components,
    bundle_name,
    collect_files,
    create_bundle,
    create_project_archive,
    discover_components,
    main,
    project_root,
)

__all__: list[str] = [
    "BundleOptions",
    "BundleResult",
    "Selection",
    "available_components",
    "bundle_name",
    "collect_files",
    "create_bundle",
    "create_project_archive",
    "discover_components",
    "main",
    "project_root",
]
