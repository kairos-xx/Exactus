# Copyright (c) 2026 João Lopes.
"""Command-line and programmatic orchestration for the patcher package."""

from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from stat import S_IXGRP, S_IXOTH, S_IXUSR
from textwrap import dedent
from types import ModuleType
from typing import Final, Never, cast, final
from zipfile import ZIP_DEFLATED, ZipFile

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.patcher.core import (
    ProjectSource,
    PyzProjectPatch,
    resolve_invocation_root,
)
from exactus.packages.patcher.diff import DiffRenderer

sys: ModuleType = __import__("sys")


@dataclass(frozen=True, slots=True)
class DeltaBuildOptions:
    """Configure executable delta generation.

    Attributes:
        includes: Source include globs.
        excludes: Source exclude globs.
        detect_moves: Whether identical moves are detected.
        reversible: Whether before-state blobs are retained.
        compression_threshold: Minimum blob size for DEFLATE compression.

    """

    includes: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()
    detect_moves: bool = True
    reversible: bool = True
    compression_threshold: int = 64


@dataclass(frozen=True, slots=True)
class CliArguments:
    """Represent fully typed parsed CLI arguments.

    Attributes:
        a: Before-state source.
        b: After-state source.
        project_root: Destination project root.
        output: Generated delta path.
        includes: Source include globs.
        excludes: Source exclude globs.
        detect_moves: Whether identical moves are detected.
        reversible: Whether before-state blobs are retained.
        compression_threshold: Minimum blob size for DEFLATE compression.
        diff: Whether to render a read-only diff.
        no_color: Whether ANSI output is disabled.
        diff_context: Number of unified-diff context lines.
        bin: Optional binary output directory.
        bin_dir: Legacy binary output directory.

    """

    a: str | None
    b: str | None
    project_root: str
    output: str
    includes: tuple[str, ...]
    excludes: tuple[str, ...]
    detect_moves: bool
    reversible: bool
    compression_threshold: int
    diff: bool
    no_color: bool
    diff_context: int
    bin: str | None
    bin_dir: str | None


@final
class Defaults:
    """Provide immutable-by-convention patcher defaults.

    Attributes:
        delta_build_options: Default options used when building project
            deltas through the Python API.
        project_root: Default project root resolved relative to the process
            invocation directory.
        output: Default filename used for generated executable delta PYZs.
        compression_threshold: Default minimum payload size, in bytes, at
            which DEFLATE compression is used.
        diff_context: Default number of unchanged context lines included in
            unified diff output.
        bin_directory: Default project-root-relative directory used for
            generated patcher CLI binaries.
        bin_filename: Default filename used for the generated self-contained
            patcher CLI PYZ.

    """

    delta_build_options: Final[DeltaBuildOptions] = DeltaBuildOptions()
    project_root: Final[str] = "."
    output: Final[str] = "update.pyz"
    compression_threshold: Final[int] = 64
    diff_context: Final[int] = 3
    bin_directory: Final[str] = "bin"
    bin_filename: Final[str] = "patcher.pyz"

    def __new__(cls) -> Never:
        """Prevent construction of the constants namespace.

        Raises:
            TypeError: Always, because this class is a constants namespace
                and must not be instantiated.

        """
        msg: str = f"{cls.__name__} cannot be instantiated"
        raise TypeError(msg)


class PatcherCli:
    """Expose the complete patch-builder CLI as an equivalent Python API."""

    @classmethod
    def run(cls, *, arguments: Sequence[str] | None = None) -> int:
        """Parse CLI arguments and execute the requested builder operation.

        Args:
            arguments: Explicit CLI arguments, or ``None`` for ``sys.argv``.

        Returns:
            Process-compatible exit status.

        """
        parser: ArgumentParser = cls.parser()
        if arguments is not None and not arguments:
            parser.print_help()
            return 0
        parsed: CliArguments = cls._parse(parser=parser, arguments=arguments)
        root: Path = resolve_invocation_root(root=parsed.project_root)
        if parsed.bin is not None:
            return cls._run_binary(parser=parser, arguments=parsed, root=root)
        cls._require_delta_sources(parser=parser, arguments=parsed)
        if parsed.diff:
            return cls._run_diff(parser=parser, arguments=parsed)
        return cls._run_delta(arguments=parsed, root=root)

    @classmethod
    def build_binary(
        cls,
        *,
        project_root: Path | str,
        bin_dir: Path | str = Defaults.bin_directory,
        filename: str = Defaults.bin_filename,
    ) -> Path:
        """Build a self-contained CLI PYZ containing the patcher package.

        Args:
            project_root: Project root used for relative output resolution.
            bin_dir: Relative or absolute destination directory.
            filename: Generated executable PYZ filename.

        Returns:
            Path to the generated patcher CLI PYZ.

        """
        root: Path = resolve_invocation_root(root=project_root)
        requested: Path = Path(bin_dir).expanduser()
        destination_dir: Path = (
            requested.resolve(strict=False)
            if requested.is_absolute()
            else (root / requested).resolve(strict=False)
        )
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination: Path = destination_dir / filename
        package_root: Path = Path(__file__).resolve().parents[3]
        main: str = dedent(
            text=(
                '    """Executable entry point for exactus.packages.patcher.""'
                '"\n    from sys import argv\n    from exactus.packages.patche'
                'r.cli import main\n    \n    if __name__ == "__main__":\n    '
                "    raise SystemExit(main(arguments=tuple(argv[1:])))\n    "
            ),
        )
        packages_root: Path = package_root / "exactus" / "packages"
        sources: list[Path] = sorted(
            packages_root.rglob(pattern="*.py"),
            key=cls._path_key,
        )
        with ZipFile(
            file=destination,
            mode="w",
            compression=ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            archive.writestr(zinfo_or_arcname="__main__.py", data=main)
            for source in sources:
                relative_source: Path = source.relative_to(package_root)
                archive.write(
                    filename=source,
                    arcname=relative_source.as_posix(),
                )
        executable_mode: int = (
            destination.stat().st_mode | S_IXUSR | S_IXGRP | S_IXOTH
        )
        destination.chmod(mode=executable_mode)
        return destination

    @staticmethod
    def build_delta(
        *,
        a: Path | str,
        b: Path | str,
        project_root: Path | str,
        output: Path | str,
        options: DeltaBuildOptions = Defaults.delta_build_options,
    ) -> Path:
        """Build an executable A-to-B project delta.

        Args:
            a: Before-state directory, ZIP, or generated patch PYZ.
            b: After-state directory, ZIP, or generated patch PYZ.
            project_root: Destination project root embedded in the patch.
            output: Destination path for the generated patch PYZ.
            options: Advanced delta-generation options.

        Returns:
            Path to the generated patch PYZ.

        """
        patch: PyzProjectPatch = PyzProjectPatch.delta(
            a=a,
            b=b,
            project_root=project_root,
            includes=options.includes,
            excludes=options.excludes,
            detect_moves=options.detect_moves,
        )
        return patch.build(
            output=output,
            reversible=options.reversible,
            compression_threshold=options.compression_threshold,
        )

    @staticmethod
    def parser() -> ArgumentParser:
        """Return the exhaustive CLI parser.

        Returns:
            Configured argument parser.

        """
        parser: ArgumentParser = ExactusArgumentParser(
            prog="patcher",
            formatter_class=RawDescriptionHelpFormatter,
            description=(
                "Build deterministic, transactional executable filesystem "
                "deltas, or build a self-contained patcher CLI binary."
            ),
            epilog=(
                dedent(
                    text=(
                        "    SOURCE TYPES\n      --a and --b independently"
                        " accept:\n        * a project directory\n        "
                        "* a normal ZIP snapshot\n        * a patch PYZ pr"
                        "oduced by this package\n    \n    ROOT SEMANTICS"
                        "\n      --project-root is the destination root em"
                        "bedded into generated update\n      PYZs.\n      "
                        "A relative project root is resolved against the c"
                        "urrent working directory.\n    \n      Generated "
                        "update PYZs accept their own --root override. For"
                        " example:\n    \n          /home/user/Downloads/u"
                        "pdate.pyz --root .\n    \n      patches the direc"
                        "tory in which that command was invoked, NOT the d"
                        "irectory\n      containing update.pyz.\n    \n   "
                        " READ-ONLY DIFF\n      patcher --a OLD --b NEW --"
                        "diff\n    \n      Prints a conventional unified d"
                        "iff and exits without creating or applying\n     "
                        " a patch. ANSI syntax highlighting is available f"
                        "or JS, CSS, HTML, Python,\n      JSON, TOML and X"
                        "ML. Use --no-color for plain output.\n    \n    B"
                        "UILD A DELTA\n      patcher --a OLD --b NEW --pro"
                        "ject-root PROJECT --output update.pyz\n    \n    "
                        "  Only additions, modifications, removals, moves "
                        "and metadata transitions\n      needed to transfo"
                        "rm A into B are stored. By default the patch is r"
                        "eversible.\n    \n    BUILD THE PATCHER CLI BINAR"
                        "Y\n      patcher --project-root PROJECT --bin\n  "
                        "  \n      creates PROJECT/bin/patcher.pyz. The di"
                        "rectory may be supplied directly:\n    \n        "
                        "  patcher --project-root PROJECT --bin tools\n   "
                        "       patcher --project-root PROJECT --bin /opt/"
                        "tools\n    \n      --bin-dir remains available wi"
                        "th bare --bin:\n    \n          patcher --project"
                        "-root PROJECT --bin --bin-dir tools\n    \n      "
                        "Relative --bin-dir values are relative to --proje"
                        "ct-root. Absolute values\n      remain absolute. "
                        "The resulting patcher.pyz contains everything req"
                        "uired to\n      invoke this builder CLI with Pyth"
                        "on's standard library.\n    \n    FILTERING\n    "
                        "  --include and --exclude may be repeated. Filter"
                        "s are applied while\n      normalizing both A and"
                        " B. Quote shell wildcards when necessary.\n    \n"
                        "    MOVES AND REVERSIBILITY\n      Move detection"
                        " is enabled by default and avoids storing unchang"
                        "ed moved\n      content redundantly. Reversible p"
                        "atches retain before-state blobs so an\n      inv"
                        "erse patch can be produced without the original A"
                        " snapshot.\n    \n    GENERATED UPDATE PYZ COMMAN"
                        "DS\n      An update PYZ is a separate runtime and"
                        " supports:\n        --root PATH       override em"
                        "bedded destination root\n        --dry-run       "
                        "  report operations without mutation\n        --v"
                        "erify          validate destination preconditions"
                        " only\n        --list            list delta opera"
                        "tions\n        --info            print formatted "
                        "manifest information\n        --json            p"
                        "rint compact machine-readable manifest JSON\n    "
                        "    --diff            print a read-only unified c"
                        "ontent diff\n        --no-color        disable AN"
                        "SI diff colors\n        --diff-context N  configu"
                        "re unified-diff context lines\n        --force   "
                        "        ignore precondition conflicts\n        --"
                        "conflict POLICY abort|overwrite|skip|backup\n    "
                        "\n    PYTHON API\n      Every builder CLI capabil"
                        "ity has a direct API equivalent:\n    \n         "
                        " PatcherCli.build_delta(...)\n          PatcherCl"
                        "i.build_binary(...)\n          PyzProjectPatch.de"
                        "lta(...).build(...)\n          patch.inverse()\n "
                        "         patch.compose(next_patch=...)\n    \n   "
                        "   Advanced build settings are represented by Del"
                        "taBuildOptions.\n    \n    EXAMPLES\n      python"
                        " -m exactus.packages.patcher --a old --b new --pr"
                        "oject-root .\n      -o update.pyz\n      python -"
                        "m exactus.packages.patcher --a old --b new --diff"
                        "\n      python -m exactus.packages.patcher --proj"
                        "ect-root . --bin\n      python -m exactus.package"
                        "s.patcher --project-root . --bin tools\n      ./b"
                        "in/patcher.pyz --a old.zip --b new.zip --project-"
                        "root . -o update.pyz\n    "
                    ),
                )
            ),
        )
        parser.add_argument(
            "--a",
            metavar="PATH",
            help=("A/before source: directory, ZIP, or generated patch PYZ."),
        )
        parser.add_argument(
            "--b",
            metavar="PATH",
            help=("B/after source: directory, ZIP, or generated patch PYZ."),
        )
        parser.add_argument(
            "--project-root",
            default=Defaults.project_root,
            metavar="PATH",
            help=(
                "Project root embedded into an update or used as the base "
                "for relative --bin-dir. Relative paths use invocation CWD. "
                "Default: ."
            ),
        )
        parser.add_argument(
            "-o",
            "--output",
            default=Defaults.output,
            metavar="PATH",
            help="Generated delta PYZ path. Default: update.pyz",
        )
        parser.add_argument(
            "--include",
            action="append",
            default=[],
            metavar="GLOB",
            help="Include glob. Repeat for multiple patterns.",
        )
        parser.add_argument(
            "--exclude",
            action="append",
            default=[],
            metavar="GLOB",
            help="Exclude glob. Repeat for multiple patterns.",
        )
        parser.add_argument(
            "--detect-moves",
            action="store_true",
            default=True,
            help="Detect identical moved entries (default).",
        )
        parser.add_argument(
            "--no-detect-moves",
            action="store_false",
            dest="detect_moves",
            help=(
                "Represent moves as independent removal/addition operations."
            ),
        )
        parser.add_argument(
            "--reversible",
            action="store_true",
            default=True,
            help=(
                "Store before-state blobs so the patch can be inverted "
                "(default)."
            ),
        )
        parser.add_argument(
            "--forward-only",
            action="store_false",
            dest="reversible",
            help=("Omit before-state blobs to reduce generated patch size."),
        )
        parser.add_argument(
            "--compression-threshold",
            type=int,
            default=Defaults.compression_threshold,
            metavar="BYTES",
            help=(
                "Store payload blobs smaller than this many bytes without "
                "DEFLATE. Default: 64."
            ),
        )
        parser.add_argument(
            "--diff",
            action="store_true",
            help=(
                "Print a read-only unified diff from A to B and exit without "
                "creating or applying a patch."
            ),
        )
        parser.add_argument(
            "--no-color",
            action="store_true",
            help=(
                "Disable ANSI colors and syntax highlighting in --diff output."
            ),
        )
        parser.add_argument(
            "--diff-context",
            type=int,
            default=Defaults.diff_context,
            metavar="LINES",
            help=(
                "Number of unchanged context lines in --diff output. "
                "Default: 3."
            ),
        )
        parser.add_argument(
            "--bin",
            nargs="?",
            const=Defaults.bin_directory,
            default=None,
            metavar="PATH",
            help=(
                "Build a self-contained patcher.pyz CLI instead of an A-to-B "
                "delta. With no PATH, use bin (or --bin-dir when supplied). "
                "With PATH, write under that project-root-relative or "
                "absolute directory, e.g. --bin tools."
            ),
        )
        parser.add_argument(
            "--bin-dir",
            default=None,
            metavar="PATH",
            help=(
                "Directory for --bin output. Relative paths are resolved "
                "under --project-root; absolute paths are preserved. Used "
                "with bare --bin. Default when omitted: bin."
            ),
        )
        return parser

    @classmethod
    def _run_binary(
        cls,
        *,
        parser: ArgumentParser,
        arguments: CliArguments,
        root: Path,
    ) -> int:
        """Execute binary-builder mode.

        Args:
            parser: Configured CLI parser.
            arguments: Typed CLI arguments.
            root: Resolved project root.

        Returns:
            Process-compatible exit status.

        """
        bin_value: str = cls._require_bin_value(arguments=arguments)
        if (
            bin_value != Defaults.bin_directory
            and arguments.bin_dir is not None
        ):
            parser.error(
                message="--bin PATH and --bin-dir cannot be used together; "
                "use bare --bin with --bin-dir, or pass the directory "
                "to --bin",
            )
        bin_dir: str = (
            bin_value
            if bin_value != Defaults.bin_directory
            else arguments.bin_dir or Defaults.bin_directory
        )
        destination: Path = cls.build_binary(
            project_root=root,
            bin_dir=bin_dir,
        )
        _ = sys.stdout.write(f"{destination}\n")
        _ = sys.stdout.flush()
        return 0

    @classmethod
    def _run_delta(cls, *, arguments: CliArguments, root: Path) -> int:
        """Execute delta-builder mode.

        Args:
            arguments: Typed CLI arguments.
            root: Resolved project root.

        Returns:
            Process-compatible exit status.

        """
        a: str = cls._require_source(value=arguments.a, name="--a")
        b: str = cls._require_source(value=arguments.b, name="--b")
        output: Path = Path(arguments.output)
        options: DeltaBuildOptions = DeltaBuildOptions(
            includes=arguments.includes,
            excludes=arguments.excludes,
            detect_moves=arguments.detect_moves,
            reversible=arguments.reversible,
            compression_threshold=arguments.compression_threshold,
        )
        destination: Path = cls.build_delta(
            a=a,
            b=b,
            project_root=root,
            output=output,
            options=options,
        )
        _ = sys.stdout.write(f"{destination}\n")
        _ = sys.stdout.flush()
        return 0

    @classmethod
    def _run_diff(
        cls,
        *,
        parser: ArgumentParser,
        arguments: CliArguments,
    ) -> int:
        """Execute read-only diff mode.

        Args:
            parser: Configured CLI parser.
            arguments: Typed CLI arguments.

        Returns:
            Process-compatible exit status.

        """
        if arguments.diff_context < 0:
            parser.error(message="--diff-context must be zero or greater")
        a: str = cls._require_source(value=arguments.a, name="--a")
        b: str = cls._require_source(value=arguments.b, name="--b")
        DiffRenderer.write(
            before=ProjectSource.from_path(
                path=a,
                includes=arguments.includes,
                excludes=arguments.excludes,
            ),
            after=ProjectSource.from_path(
                path=b,
                includes=arguments.includes,
                excludes=arguments.excludes,
            ),
            color=not arguments.no_color,
            context=arguments.diff_context,
        )
        return 0

    @staticmethod
    def _parse(
        *,
        parser: ArgumentParser,
        arguments: Sequence[str] | None,
    ) -> CliArguments:
        """Convert argparse output into a fully typed immutable model.

        Args:
            parser: Configured CLI parser.
            arguments: Explicit arguments or ``None`` for ``sys.argv``.

        Returns:
            Fully typed parsed CLI arguments.

        """
        namespace: Namespace = parser.parse_args(args=arguments)
        a: str | None = cast(typ="str | None", val=namespace.a)
        b: str | None = cast(typ="str | None", val=namespace.b)
        project_root: str = cast(typ="str", val=namespace.project_root)
        output: str = cast(typ="str", val=namespace.output)
        include_values: list[str] = cast(
            typ="list[str]",
            val=namespace.include,
        )
        exclude_values: list[str] = cast(
            typ="list[str]",
            val=namespace.exclude,
        )
        detect_moves: bool = cast(typ="bool", val=namespace.detect_moves)
        reversible: bool = cast(typ="bool", val=namespace.reversible)
        compression_threshold: int = cast(
            typ="int",
            val=namespace.compression_threshold,
        )
        diff: bool = cast(typ="bool", val=namespace.diff)
        no_color: bool = cast(typ="bool", val=namespace.no_color)
        diff_context: int = cast(typ="int", val=namespace.diff_context)
        bin_value: str | None = cast(typ="str | None", val=namespace.bin)
        bin_dir: str | None = cast(typ="str | None", val=namespace.bin_dir)
        return CliArguments(
            a=a,
            b=b,
            project_root=project_root,
            output=output,
            includes=tuple(include_values),
            excludes=tuple(exclude_values),
            detect_moves=detect_moves,
            reversible=reversible,
            compression_threshold=compression_threshold,
            diff=diff,
            no_color=no_color,
            diff_context=diff_context,
            bin=bin_value,
            bin_dir=bin_dir,
        )

    @staticmethod
    def _require_delta_sources(
        *,
        parser: ArgumentParser,
        arguments: CliArguments,
    ) -> None:
        """Require both delta source arguments.

        Args:
            parser: Configured CLI parser.
            arguments: Typed CLI arguments.

        """
        if arguments.a is None or arguments.b is None:
            parser.error(
                message="--a and --b are required unless --bin is used",
            )

    @staticmethod
    def _require_source(*, value: str | None, name: str) -> str:
        """Return a required source value.

        Args:
            value: Parsed source value.
            name: Human-readable argument name.

        Returns:
            Non-null source value.

        Raises:
            ValueError: If the source value is unexpectedly absent.

        """
        if value is None:
            msg: str = f"{name} is required"
            raise ValueError(msg)
        return value

    @staticmethod
    def _require_bin_value(*, arguments: CliArguments) -> str:
        """Return the validated binary-directory argument.

        Args:
            arguments: Typed CLI arguments.

        Returns:
            Non-null binary-directory value.

        Raises:
            ValueError: If binary mode was not selected.

        """
        if arguments.bin is None:
            msg: str = "--bin is required for binary mode"
            raise ValueError(msg)
        return arguments.bin

    @staticmethod
    def _path_key(path: Path, /) -> str:
        """Return a deterministic sorting key for a path.

        Args:
            path: Path supplied positionally by ``sorted``.

        Returns:
            POSIX representation of the path.

        """
        return path.as_posix()


def main(*, arguments: Sequence[str] | None = None) -> int:
    """Run the patcher builder CLI.

    Args:
        arguments: Explicit CLI arguments, or ``None`` for ``sys.argv``.

    Returns:
        Process-compatible exit status.

    """
    return PatcherCli.run(arguments=arguments)
