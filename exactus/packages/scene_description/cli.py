"""Command-line enrichment of an existing Visual Cause report."""

from json import dumps, loads
from pathlib import Path
from typing import TYPE_CHECKING, cast

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.scene_description.models import JsonValue
from exactus.packages.scene_description.visual_cause import (
    VisualCauseDescriber,
)

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace


def _load(*, path: Path) -> dict[str, JsonValue]:
    """Read one JSON object file.

    Args:
        path: JSON report or scene manifest to read.

    Returns:
        The resulting value.

    Raises:
        TypeError: If the file does not contain a JSON object.

    """
    value: object = loads(s=path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        msg: str = f"Expected a JSON object: {path}"
        raise TypeError(msg)
    return cast(typ="dict[str, JsonValue]", val=value)


def main() -> None:
    """Enrich a Visual Cause report from two captured scene manifests."""
    parser: ArgumentParser = ExactusArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("scene_a", type=Path)
    parser.add_argument("scene_b", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args: Namespace = parser.parse_args()
    describer: VisualCauseDescriber = VisualCauseDescriber()
    enriched: dict[str, JsonValue] = describer.enrich(
        report=_load(path=args.report),
        scene_a=_load(path=args.scene_a),
        scene_b=_load(path=args.scene_b),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.json").write_text(
        data=dumps(obj=enriched, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (args.output / "description.md").write_text(
        data=describer.markdown(report=enriched),
        encoding="utf-8",
    )
