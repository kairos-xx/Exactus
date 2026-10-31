"""Adapters enriching Visual Cause reports with rendered scenes."""

from copy import deepcopy
from textwrap import dedent
from typing import cast

from exactus.packages.scene_description.changes import (
    ElementChange,
    SceneChangeDescriber,
)
from exactus.packages.scene_description.models import JsonValue


class VisualCauseDescriber:
    """Attach semantic A/B descriptions to Visual Cause change trees."""

    def __init__(self) -> None:
        """Initialize the deterministic scene-change describer."""
        self._describer: SceneChangeDescriber = SceneChangeDescriber()

    @staticmethod
    def markdown(*, report: dict[str, JsonValue]) -> str:
        """Render the enriched change description as Markdown.

        Args:
            report: Visual Cause report enriched by ``enrich``.

        Returns:
            The resulting value.

        """
        block: JsonValue = report.get("change_description")
        if not isinstance(block, dict):
            return dedent(
                text=(
                    "    ## Rendered change description\n    \n    No scene de"
                    "scription is available.\n    "
                ),
            )
        summary: JsonValue = block.get("summary")
        elements: JsonValue = block.get("elements")
        lines: list[str] = [
            "## Rendered change description",
            "",
            str(object=summary or "No rendered changes were described."),
            "",
        ]
        if isinstance(elements, list):
            lines.extend(
                f"- {item.get('summary')}"
                for item in elements
                if isinstance(item, dict) and item.get("summary")
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def strings(value: JsonValue) -> list[JsonValue]:
        """Return only the string members of a JSON list.

        Args:
            value: Candidate JSON list.

        Returns:
            The resulting value.

        """
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str)]

    @staticmethod
    def scene_metadata(scene: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Return the scene's metadata and reference blocks.

        Missing or malformed blocks are replaced by empty objects.

        Args:
            scene: Descriptor manifest to read.

        Returns:
            The resulting value.

        """
        metadata: JsonValue = scene.get("metadata")
        reference: JsonValue = scene.get("reference")
        return {
            "metadata": metadata if isinstance(metadata, dict) else {},
            "reference": reference if isinstance(reference, dict) else {},
        }

    def enrich(
        self,
        *,
        report: dict[str, JsonValue],
        scene_a: dict[str, JsonValue],
        scene_b: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        """Return a copy of the report with description fields added.

        Existing Visual Cause evidence is never rewritten. Each change-tree
        node receives ``visual_description`` when its selector can be matched
        to the descriptor scenes. The report receives ``change_description``
        containing the flattened descriptions and scene metadata.

        Args:
            report: Visual Cause report tree to enrich.
            scene_a: Descriptor manifest for the first render.
            scene_b: Descriptor manifest for the second render.

        Returns:
            The resulting value.

        """
        enriched: dict[str, JsonValue] = deepcopy(x=report)
        trees: JsonValue = enriched.get("change_trees")
        descriptions: list[JsonValue] = []
        if isinstance(trees, list):
            for tree in trees:
                if isinstance(tree, dict):
                    self._enrich_node(
                        node=cast(typ="dict[str, JsonValue]", val=tree),
                        scene_a=scene_a,
                        scene_b=scene_b,
                        descriptions=descriptions,
                    )
        change_description: dict[str, JsonValue] = {
            "schema": "scene-description/visual-cause/v1",
            "summary": self._summary(descriptions=descriptions),
            "elements": descriptions,
            "scene_a": self.scene_metadata(scene=scene_a),
            "scene_b": self.scene_metadata(scene=scene_b),
        }
        enriched["change_description"] = change_description
        return enriched

    @staticmethod
    def _summary(*, descriptions: list[JsonValue]) -> str:
        """Return the headline sentence for the description block.

        Args:
            descriptions: Flattened element descriptions.

        Returns:
            The resulting value.

        """
        count: int = len(descriptions)
        if count == 0:
            return (
                "No changed Visual Cause nodes could be matched "
                "to rendered scene elements."
            )
        noun: str = "elements" if count != 1 else "element"
        return f"{count} changed rendered {noun} described from A to B."

    def _enrich_node(
        self,
        *,
        node: dict[str, JsonValue],
        scene_a: dict[str, JsonValue],
        scene_b: dict[str, JsonValue],
        descriptions: list[JsonValue],
    ) -> None:
        """Recursively attach descriptions to matching change nodes.

        Args:
            node: Change-tree node receiving ``visual_description``.
            scene_a: Descriptor manifest for the first render.
            scene_b: Descriptor manifest for the second render.
            descriptions: Flattened description sink shared by the
                recursion.

        """
        selector: JsonValue = node.get("selector")
        if isinstance(selector, str):
            change: ElementChange | None = self._describer.describe_element(
                selector=selector,
                scene_a=scene_a,
                scene_b=scene_b,
            )
            if change is not None:
                serialized: dict[str, JsonValue] = change.as_json()
                serialized["categories"] = self.strings(
                    value=node.get("categories"),
                )
                serialized["mechanisms"] = self.strings(
                    value=node.get("mechanisms"),
                )
                serialized["root_cause"] = node.get("root_cause")
                node["visual_description"] = serialized
                descriptions.append(serialized)
        relations: JsonValue = node.get("relations")
        if not isinstance(relations, dict):
            return
        descendants: JsonValue = relations.get("descendants")
        if not isinstance(descendants, list):
            return
        for descendant in descendants:
            if isinstance(descendant, dict):
                self._enrich_node(
                    node=cast(typ="dict[str, JsonValue]", val=descendant),
                    scene_a=scene_a,
                    scene_b=scene_b,
                    descriptions=descriptions,
                )
