#!/usr/bin/env python3
"""Render the bundled example and check it against the golden output."""

from contextlib import suppress
from importlib import import_module
from pathlib import Path
from sys import path as sys_path
from sys import stderr, stdout

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.markdown import render_report


def main() -> int:
    """Render ``template.md`` and compare it with ``expected.md``.

    Returns:
        ``0`` when the render matches the checked-in golden file.

    """
    root: Path = Path(__file__).resolve().parent / "assets"
    rendered: str = render_report(
        result=root / "data.json",
        template=root / "template.md",
        mapping=root / "mapping.json",
    )
    stdout.write(rendered)
    golden: str = (root / "expected.md").read_text(encoding="utf-8")
    if rendered != golden:
        stderr.write("error: rendered output differs from expected.md\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
