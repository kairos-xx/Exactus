# Copyright (c) 2026
"""Run the Actions example."""

from exactus.packages.project_python import auto as _project_python_auto
from exactus.tools.actions.examples.run import main

_project_python_active: bool = _project_python_auto.Constants.activated
raise SystemExit(main())
