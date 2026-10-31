# Copyright (c) 2026 João Lopes.
"""Export and serve the interactive performance dashboard."""

from importlib.resources import files
from importlib.resources.abc import Traversable
from json import dumps
from pathlib import Path
from shutil import copyfileobj
from typing import IO

from exactus.packages.performance.model import PerformanceRun
from exactus.packages.performance.report import Constants as ReportConstants
from exactus.packages.performance.report import PerformanceReport


class DashboardExporter:
    """Write profiler assets and trace data to a destination directory.

    Attributes:
        assets: Packaged profiler asset filenames copied verbatim.
        styles: Packaged stylesheet folder copied recursively.

    """

    assets: tuple[str, ...] = ("index.html", "code.js")
    styles: str = "styles"

    @classmethod
    def export(
        cls,
        *,
        runs: tuple[PerformanceRun, ...],
        destination: Path,
    ) -> Path:
        """Export dashboard assets and raw trace data.

        Args:
            runs: Analyzed runs to expose in the dashboard.
            destination: Directory receiving the dashboard.

        Returns:
            Path to the generated ``index.html``.

        """
        destination.mkdir(parents=True, exist_ok=True)
        for name in cls.assets:
            cls._copy_asset(name=name, destination=destination / name)
        cls._copy_styles(
            source=files("exactus.packages.performance.web").joinpath(
                cls.styles,
            ),
            destination=destination / cls.styles,
        )
        data: dict[str, list[str]] = {
            run.tool: cls.raw_lines(run=run) for run in runs
        }
        _ = (destination / "steps.json").write_text(
            data=dumps(obj=data, indent=2) + "\n",
            encoding="utf-8",
        )
        _ = PerformanceReport.write(
            runs=runs,
            path=destination / ReportConstants.file_name,
        )
        _ = (destination / "data.js").write_text(
            data=cls.steps_data_js(data=data),
            encoding="utf-8",
        )
        return destination / "index.html"

    @staticmethod
    def raw_lines(*, run: PerformanceRun) -> list[str]:
        """Return a run's event and resource lines in time order.

        Args:
            run: Analyzed run.

        Returns:
            Original trace lines; events precede samples at equal times.

        """
        timed: list[tuple[float, int, str]] = [
            (event.elapsed, 0, event.raw) for event in run.events
        ]
        timed.extend(
            (sample.elapsed, 1, sample.raw)
            for sample in run.samples
            if sample.raw
        )
        return [raw for _elapsed, _rank, raw in sorted(timed)]

    @staticmethod
    def steps_data_js(*, data: dict[str, list[str]]) -> str:
        r"""Render trace data as a script-includable JavaScript document.

        ``file://`` pages cannot ``fetch`` sibling JSON, so the export
        ships the same payload twice: ``steps.json`` for tools and
        ``data.js`` for ``index.html`` to load through a plain
        ``<script src>`` tag. ``json.dumps`` already emits pure ASCII
        with ``\uXXXX`` escapes, so only backslashes, backticks and
        ``${`` need guarding before the text lands inside the template
        literal fed to ``JSON.parse`` — matching the report-bundle
        ``data.js`` convention in ``exactus.tools.reports``.

        Args:
            data: Tool name to raw trace-line payload.

        Returns:
            JavaScript document assigning the payload global.

        """
        escaped: str = (
            dumps(obj=data, indent=2)
            .replace("\\", "\\\\")
            .replace("`", "\\`")
            .replace("${", "\\${")
        )
        return f"window.__PERFORMANCE_STEPS__ = JSON.parse(`{escaped}`);\n"

    @classmethod
    def _copy_styles(cls, *, source: Traversable, destination: Path) -> None:
        """Copy the stylesheet tree, keeping ``.css`` files only.

        Args:
            source: Packaged stylesheet folder.
            destination: Output folder.

        """
        destination.mkdir(parents=True, exist_ok=True)
        entry: Traversable
        for entry in source.iterdir():
            if entry.is_dir():
                cls._copy_styles(
                    source=entry,
                    destination=destination / entry.name,
                )
            elif entry.name.endswith(".css"):
                with (
                    entry.open(mode="rb") as origin,
                    (destination / entry.name).open(mode="wb") as target,
                ):
                    copyfileobj(fsrc=origin, fdst=target)

    @staticmethod
    def _copy_asset(*, name: str, destination: Path) -> None:
        """Copy one packaged web asset.

        Args:
            name: Packaged asset filename.
            destination: Output file path.

        """
        resource: Traversable = files(
            "exactus.packages.performance.web",
        ).joinpath(name)
        with resource.open(mode="rb") as source:
            source_stream: IO[bytes] = source
            with destination.open(mode="wb") as target:
                copyfileobj(fsrc=source_stream, fdst=target)
