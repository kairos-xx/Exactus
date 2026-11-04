# Copyright (c) 2026 Project contributors
"""Execute a saved JSON or TOML Actions recipe."""

from pathlib import Path
from sys import path as sys_path
from typing import TYPE_CHECKING

if __package__ in (None, ""):
    sys_path.insert(0, str(object=Path(__file__).resolve().parents[3]))
from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.project_python import auto as _project_python_auto
from exactus.tools.actions.runner import load_actions, run_actions
from exactus.tools.common.config import reports_root

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace

    from exactus.tools.record.store import JsonValue
_project_python_active: bool = _project_python_auto.Constants.activated


def main() -> int:
    """Execute ordered tool calls and return their aggregate status.

    Returns:
        Zero for success, one for failed or cancelled actions.

    """
    parser: ArgumentParser = ExactusArgumentParser(description=__doc__)
    parser.add_argument("specification", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="results destination (default: <reports-dir>/ACTIONS)",
    )
    args: Namespace = parser.parse_args()
    root: Path = args.root or args.specification.resolve().parent
    report: dict[str, JsonValue]
    report = run_actions(
        specification=load_actions(path=args.specification),
        root=root,
        output=args.output or reports_root(start=root) / "ACTIONS",
    )
    return int(report["status"] != "succeeded")


if __name__ == "__main__":
    raise SystemExit(main())
