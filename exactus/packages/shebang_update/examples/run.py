#!/usr/bin/env python3
"""Fix stale virtual-environment shebangs in a throwaway demo project.

Each run rebuilds a tiny project under the git-ignored ``.scratch/``
folder: a ``.venv`` directory, a script whose shebang still points at the
project's previous location, a script whose shebang is already correct, a
plain text file, and a stale-looking file inside the environment itself.
``ShebangUpdater`` repairs only the stale script — the environment's own
files are excluded by design — so the example can be re-run any number of
times.
"""

from __future__ import annotations

from contextlib import suppress
from importlib import import_module
from pathlib import Path
from shutil import rmtree
from sys import path as sys_path
from sys import stdout
from typing import Final, final

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.shebang_update import Settings, ShebangUpdater


@final
class Constants:
    """Collect shared example paths and the stale shebang prefix.

    Attributes:
        here: Directory containing this example.
        work: Scratch project root recreated per run.
        stale: Shebang prefix left over from a previous checkout.

    """

    here: Final[Path] = Path(__file__).resolve().parent
    work: Final[Path] = here / ".scratch" / "demo_project"
    stale: Final[str] = "/previous/checkout/demo_project"


def _script(*, shebang: str, doc: str, message: str) -> str:
    """Build one executable demo script body.

    Args:
        shebang: First line, including the leading ``#!``.
        doc: Module docstring for the generated script.
        message: Line the generated script writes to stdout.

    Returns:
        Complete script text with a docstring and ``stdout.write`` call.

    """
    return (
        f"{shebang}\n"
        f'"""{doc}"""\n\n'
        "from sys import stdout\n\n"
        f'_ = stdout.write("{message}\\n")\n'
    )


def _seed() -> None:
    """Recreate the scratch project with a stale venv shebang."""
    if Constants.work.parent.exists():
        rmtree(path=Constants.work.parent)
    tools: Path = Constants.work / "tools"
    tools.mkdir(parents=True)
    environment: Path = Constants.work / ".venv" / "bin"
    environment.mkdir(parents=True)
    scripts: dict[Path, str] = {
        tools / "build.py": _script(
            shebang=f"#!{Constants.stale}/.venv/bin/python3",
            doc="Run the demo build step.",
            message="build",
        ),
        tools / "already_ok.py": _script(
            shebang=Settings(root=Constants.work).shebang.decode(),
            doc="Report an already-correct shebang.",
            message="ok",
        ),
        environment / "activate.py": _script(
            shebang=f"#!{Constants.stale}/.venv/bin/python",
            doc="Activation stub the updater must leave untouched.",
            message="untouched",
        ),
    }
    for script, data in scripts.items():
        script.write_text(data=data, encoding="utf-8")
        script.chmod(mode=0o755)
    (tools / "notes.txt").write_text(
        data="no shebang here\n",
        encoding="utf-8",
    )


def main() -> int:
    """Rebuild the demo project and repair its stale shebangs.

    Returns:
        Zero after the demonstration completes.

    """
    _seed()
    _ = stdout.write(f"scratch project: {Constants.work}\n\n")
    updated: int = ShebangUpdater(settings=Settings(root=Constants.work)).run()
    line: str = (
        (Constants.work / "tools" / "build.py")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    _ = stdout.write(f"\ntools/build.py now reads:\n  {line}\n")
    return 0 if updated == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
