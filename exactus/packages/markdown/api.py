# Copyright (c) 2026
"""Public entry points for rendering reports."""

from __future__ import annotations

from json import JSONDecodeError, loads
from pathlib import Path
from typing import TYPE_CHECKING

from .engine import MarkdownEngine
from .errors import MappingError, TemplateEngineError

if TYPE_CHECKING:
    from .json_types import JsonValue


def load_json(*, value: Path | JsonValue) -> JsonValue:
    """Read JSON from a path, or pass a value through.

    Args:
        value: A path to a JSON file, or an already-parsed value.

    Returns:
        The parsed JSON value.

    Raises:
        TemplateEngineError: The file cannot be read or is not JSON.

    """
    if isinstance(value, Path):
        try:
            parsed: JsonValue = loads(s=value.read_text(encoding="utf-8"))
        except (OSError, JSONDecodeError) as exc:
            msg: str = f"Cannot load {value}: {exc}"
            raise TemplateEngineError(msg) from exc
        return parsed
    return value


def render_report(
    *,
    result: Path | JsonValue,
    template: Path,
    mapping: Path | JsonValue | None = None,
    extra_roots: tuple[Path, ...] = (),
    strict: bool = True,
) -> str:
    """Render ``result.md`` from ``result.json``.

    Args:
        result: Path to ``result.json`` or the parsed document.
        template: Markdown template path.
        mapping: Path to ``result_mapping.json``, a parsed mapping
            object, or ``None`` to expose the result directly.
        extra_roots: Additional template roots for includes.
        strict: Raise on undefined variables.

    Returns:
        The rendered Markdown. A JSON file that cannot be loaded or a
        template failure surfaces as ``TemplateEngineError``.

    Raises:
        MappingError: The mapping is not a JSON object.

    """
    source: JsonValue = load_json(value=result)
    spec: JsonValue = None if mapping is None else load_json(value=mapping)
    if spec is not None and not isinstance(spec, dict):
        msg: str = "Mapping must be a JSON object"
        raise MappingError(msg)
    engine: MarkdownEngine = MarkdownEngine(
        roots=(template.parent, *extra_roots),
        strict=strict,
    )
    return engine.render(template=template, source=source, mapping=spec)
