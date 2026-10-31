# Copyright (c) 2026
"""Inspect the bundled branching Record workspace."""

from exactus.packages.project_python import auto as _project_python_auto
from exactus.tools.record.examples.run import main

_project_python_active: bool = _project_python_auto.Constants.activated
raise SystemExit(main())
