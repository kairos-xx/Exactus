"""Update Python virtual-environment shebangs to the current project path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from sys import stdout


@dataclass(frozen=True, slots=True)
class Settings:
    """Configure recursive shebang replacement.

    Attributes:
        root: Project root containing the virtual environment.
        virtual_environment: Virtual-environment directory name.
        python_executable: Python executable relative to the environment.

    """

    root: Path
    virtual_environment: str = ".venv"
    python_executable: str = "bin/python"

    @property
    def shebang(self) -> bytes:
        """Return the expected project-local Python shebang.

        Returns:
            Absolute shebang encoded as bytes.

        """
        python: Path = (
            self.root / self.virtual_environment / self.python_executable
        )
        return f"#!{python.resolve()}".encode()


class ShebangUpdater:
    """Recursively replace stale virtual-environment Python shebangs."""

    def __init__(self, *, settings: Settings) -> None:
        """Initialize the updater.

        Args:
            settings: Shebang replacement configuration.

        """
        self._settings: Settings = settings

    def run(self) -> int:
        """Update matching shebangs below the project root.

        Files inside the project's virtual environment are intentionally
        excluded.

        Returns:
            Number of files whose shebang was changed.

        """
        updated: int = 0
        for path in self._settings.root.rglob(pattern="*"):
            if self._should_process(path=path) and self._update(path=path):
                updated += 1
        return updated

    @staticmethod
    def _is_python_venv_shebang(*, line: bytes) -> bool:
        """Determine whether a line is an absolute venv Python shebang.

        Args:
            line: First line of a candidate file.

        Returns:
            True for absolute Python shebangs targeting a `.venv` environment.

        """
        normalized: bytes = line.rstrip(b"\r\n")
        return (
            normalized.startswith(b"#!/")
            and b"/.venv/bin/python" in normalized
            and normalized.rsplit(sep=b"/", maxsplit=1)[-1].startswith(
                b"python",
            )
        )

    def _should_process(self, *, path: Path) -> bool:
        """Determine whether a filesystem entry should be inspected.

        Args:
            path: Filesystem entry to inspect.

        Returns:
            True when the entry is a file outside the virtual environment.

        """
        return (
            path.is_file()
            and self._settings.virtual_environment not in path.parts
        )

    def _update(self, *, path: Path) -> bool:
        """Replace a stale virtual-environment Python shebang.

        Args:
            path: File to inspect and potentially update.

        Returns:
            True when the file was modified.

        """
        try:
            with path.open(mode="rb") as stream:
                first_line: bytes = stream.readline()
                if not self._is_python_venv_shebang(line=first_line):
                    return False
                expected: bytes = self._settings.shebang + b"\n"
                if first_line.rstrip(b"\r\n") == self._settings.shebang:
                    return False
                remainder: bytes = stream.read()
            path.write_bytes(data=expected + remainder)
        except (OSError, UnicodeError):
            return False
        stdout.write(
            f"{path.relative_to(self._settings.root)}\n  "
            f"{first_line.decode(errors='replace').rstrip()}\n  "
            f"-> {self._settings.shebang.decode()}\n",
        )
        return True


def main() -> None:
    """Update stale shebangs using the current working directory."""
    root: Path = Path.cwd().resolve()
    updated: int = ShebangUpdater(settings=Settings(root=root)).run()
    stdout.write(
        f"\nUpdated {updated} {('file' if updated == 1 else 'files')}.\n",
    )


if __name__ == "__main__":
    main()
