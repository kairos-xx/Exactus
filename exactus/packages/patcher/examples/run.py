#!/usr/bin/env python3
"""Exercise folders, ZIPs, PYZs, reversal, and inspection."""

from contextlib import suppress
from importlib import import_module
from pathlib import Path
from subprocess import CompletedProcess
from sys import path as sys_path

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from shutil import make_archive, rmtree
from subprocess import run
from sys import executable
from tempfile import mkdtemp

from exactus.packages.patcher import PyzProjectPatch


def require(*, condition: bool, message: str) -> None:
    """Require an example postcondition.

    Args:
        condition: Condition that must evaluate to true.
        message: Error message used when the condition fails.

    Raises:
        RuntimeError: If the condition is false.

    """
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    """Build and execute a representative reversible project patch.

    Returns:
        Zero after the forward and reverse patch operations complete
        successfully.

    """
    workspace: Path = Path(mkdtemp(prefix="patcher-example-"))
    before: Path = workspace / "before"
    after: Path = workspace / "after"
    target: Path = workspace / "target"
    output: Path = workspace / "update.pyz"
    try:
        for root in (before, after, target):
            (root / "src").mkdir(parents=True)
        (before / "src/app.py").write_text(
            data="VERSION = 1\n",
            encoding="utf-8",
        )
        (before / "obsolete.txt").write_text(
            data="remove me\n",
            encoding="utf-8",
        )
        (after / "src/app.py").write_text(
            data="VERSION = 2\n",
            encoding="utf-8",
        )
        (after / "src/new.py").write_text(
            data="ENABLED = True\n",
            encoding="utf-8",
        )
        (target / "src/app.py").write_text(
            data="VERSION = 1\n",
            encoding="utf-8",
        )
        (target / "obsolete.txt").write_text(
            data="remove me\n",
            encoding="utf-8",
        )
        archive: Path = Path(
            make_archive(
                base_name=str(object=workspace / "after"),
                format="zip",
                root_dir=after,
            ),
        )
        patch: PyzProjectPatch = PyzProjectPatch.delta(
            a=before,
            b=archive,
            project_root=target,
        )
        _built_patch: Path = patch.build(output=output)
        _apply_result: CompletedProcess[bytes] = run(
            args=(executable, str(object=output), "--root", "."),
            cwd=target,
            check=True,
        )
        updated_content: str = (target / "src/app.py").read_text(
            encoding="utf-8",
        )
        require(
            condition=updated_content == "VERSION = 2\n",
            message="Patch did not update src/app.py.",
        )
        require(
            condition=(target / "src/new.py").is_file(),
            message="Patch did not create src/new.py.",
        )
        require(
            condition=not (target / "obsolete.txt").exists(),
            message="Patch did not remove obsolete.txt.",
        )
        reverse: PyzProjectPatch = patch.inverse()
        rollback: Path = workspace / "rollback.pyz"
        _built_rollback: Path = reverse.build(output=rollback)
        _rollback_result: CompletedProcess[bytes] = run(
            args=(executable, str(object=rollback), "--root", "."),
            cwd=target,
            check=True,
        )
        restored_content: str = (target / "src/app.py").read_text(
            encoding="utf-8",
        )
        require(
            condition=restored_content == "VERSION = 1\n",
            message="Reverse patch did not restore src/app.py.",
        )
        require(
            condition=(target / "obsolete.txt").is_file(),
            message="Reverse patch did not restore obsolete.txt.",
        )
        require(
            condition=not (target / "src/new.py").exists(),
            message="Reverse patch did not remove src/new.py.",
        )
        return 0
    finally:
        rmtree(path=workspace)


if __name__ == "__main__":
    raise SystemExit(main())
