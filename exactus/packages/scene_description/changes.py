"""Deterministically describe visual changes between semantic scene graphs."""

from dataclasses import dataclass
from typing import Final, cast, final

from exactus.packages.scene_description.models import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        geometry_tolerance: Grouped module constant.

    """

    geometry_tolerance: Final[float] = 0.01


@dataclass(frozen=True, slots=True)
class ElementChange:
    """Machine and human description for one matched rendered element.

    Attributes:
        selector: Stable element selector the change belongs to.
        summary: One-line human description of the change.
        details: Individual change bullets composing ``summary``.

    """

    selector: str
    summary: str
    details: tuple[str, ...]

    def as_json(self) -> dict[str, JsonValue]:
        """Serialize the description for report enrichment.

        Returns:
            The resulting value.

        """
        return {
            "selector": self.selector,
            "summary": self.summary,
            "details": cast(typ="list[JsonValue]", val=list(self.details)),
        }


class SceneChangeDescriber:
    """Compare descriptor manifests using stable element selectors."""

    @staticmethod
    def frame(element: dict[str, JsonValue]) -> dict[str, float]:
        """Extract numeric viewport-frame geometry from one element.

        Args:
            element: Element record carrying ``visual.viewportFrame``.

        Returns:
            The resulting value.

        """
        visual: JsonValue = element.get("visual")
        if not isinstance(visual, dict):
            return {}
        frame: JsonValue = visual.get("viewportFrame")
        if not isinstance(frame, dict):
            return {}
        return {
            key: float(value)
            for key in ("x", "y", "width", "height")
            if isinstance((value := frame.get(key)), int | float)
        }

    def describe_element(
        self,
        *,
        selector: str,
        scene_a: dict[str, JsonValue],
        scene_b: dict[str, JsonValue],
    ) -> ElementChange | None:
        """Describe one selector's visible A/B change.

        Args:
            selector: Stable element selector to compare.
            scene_a: Descriptor manifest for the first render.
            scene_b: Descriptor manifest for the second render.

        Returns:
            The resulting value.

        """
        before: dict[str, JsonValue] | None = self._element(
            scene=scene_a,
            selector=selector,
        )
        after: dict[str, JsonValue] | None = self._element(
            scene=scene_b,
            selector=selector,
        )
        if before is None and after is None:
            return None
        if before is None:
            return ElementChange(
                selector=selector,
                summary=(
                    f"{self._label(element=after, selector=selector)} "
                    "appeared."
                ),
                details=("The element is present in B but not in A.",),
            )
        if after is None:
            return ElementChange(
                selector=selector,
                summary=(
                    f"{self._label(element=before, selector=selector)} "
                    "disappeared."
                ),
                details=("The element is present in A but not in B.",),
            )
        details: list[str] = []
        self._geometry(before=before, after=after, output=details)
        self._identity(before=before, after=after, output=details)
        if not details:
            return None
        label: str = self._label(element=after, selector=selector)
        return ElementChange(
            selector=selector,
            summary=f"{label}: {'; '.join(details)}.",
            details=tuple(details),
        )

    def describe_scene(
        self,
        *,
        scene_a: dict[str, JsonValue],
        scene_b: dict[str, JsonValue],
        selectors: tuple[str, ...] | None = None,
    ) -> tuple[ElementChange, ...]:
        """Describe changed elements, optionally restricted by selector.

        Args:
            scene_a: Descriptor manifest for the first render.
            scene_b: Descriptor manifest for the second render.
            selectors: Subset of selectors to compare; defaults to every
                selector present in either scene.

        Returns:
            The resulting value.

        """
        candidates: tuple[str, ...] = selectors or tuple(
            sorted(
                self._selectors(scene=scene_a)
                | self._selectors(scene=scene_b),
            ),
        )
        return tuple(
            change
            for selector in candidates
            if (
                change := self.describe_element(
                    selector=selector,
                    scene_a=scene_a,
                    scene_b=scene_b,
                )
            )
            is not None
        )

    @staticmethod
    def _elements(
        scene: dict[str, JsonValue],
    ) -> tuple[dict[str, JsonValue], ...]:
        """Return every element record inside one descriptor manifest.

        Args:
            scene: Descriptor manifest holding an ``elements`` map.

        Returns:
            The resulting value.

        """
        value: JsonValue = scene.get("elements")
        if not isinstance(value, dict):
            return ()
        return tuple(
            cast(typ="dict[str, JsonValue]", val=element)
            for element in value.values()
            if isinstance(element, dict)
        )

    @staticmethod
    def _label(element: dict[str, JsonValue] | None, selector: str) -> str:
        """Return a human label for one element record.

        Args:
            element: Matched element record, when any.
            selector: Selector fallback when no label field exists.

        Returns:
            The resulting value.

        """
        if element is None:
            return selector
        name: JsonValue = element.get("name")
        text: JsonValue = element.get("text")
        tag: JsonValue = element.get("tag")
        if isinstance(name, str) and name.strip():
            return f"{tag or 'element'} “{name.strip()}”"
        if isinstance(text, str) and text.strip():
            compact: str = " ".join(text.split())
            return f"{tag or 'element'} “{compact[:80]}”"
        return str(object=tag or selector)

    @staticmethod
    def _identity(
        *,
        before: dict[str, JsonValue],
        after: dict[str, JsonValue],
        output: list[str],
    ) -> None:
        """Append text, name and role differences between two elements.

        Args:
            before: Element record from the first render.
            after: Element record from the second render.
            output: Change bullets receiving identity differences.

        """
        for key, label in (
            ("text", "text"),
            ("name", "accessible name"),
            ("role", "role"),
        ):
            a: JsonValue = before.get(key)
            b: JsonValue = after.get(key)
            if a != b:
                output.append(f"{label} changed from {a!r} to {b!r}")

    def _selectors(self, *, scene: dict[str, JsonValue]) -> set[str]:
        """Return the selector universe of one descriptor manifest.

        Args:
            scene: Descriptor manifest holding an ``elements`` map.

        Returns:
            The resulting value.

        """
        return {
            selector
            for element in self._elements(scene=scene)
            if isinstance((selector := element.get("selector")), str)
        }

    def _element(
        self,
        *,
        scene: dict[str, JsonValue],
        selector: str,
    ) -> dict[str, JsonValue] | None:
        """Return the element matching one selector, when present.

        Args:
            scene: Descriptor manifest holding an ``elements`` map.
            selector: Element or visual-cause selector to find.

        Returns:
            The resulting value.

        """
        return next(
            (
                element
                for element in self._elements(scene=scene)
                if element.get("selector") == selector
                or element.get("visualCauseSelector") == selector
            ),
            None,
        )

    def _geometry(
        self,
        *,
        before: dict[str, JsonValue],
        after: dict[str, JsonValue],
        output: list[str],
    ) -> None:
        """Append movement and resize descriptions between two frames.

        Args:
            before: Element record from the first render.
            after: Element record from the second render.
            output: Change bullets receiving geometry differences.

        """
        a: dict[str, float] = self.frame(element=before)
        b: dict[str, float] = self.frame(element=after)
        if not a or not b:
            return
        dx: float = b.get("x", 0.0) - a.get("x", 0.0)
        dy: float = b.get("y", 0.0) - a.get("y", 0.0)
        dw: float = b.get("width", 0.0) - a.get("width", 0.0)
        dh: float = b.get("height", 0.0) - a.get("height", 0.0)
        movement: list[str] = []
        if abs(dx) >= Constants.geometry_tolerance:
            movement.append(f"{abs(dx):g}px {('right' if dx > 0 else 'left')}")
        if abs(dy) >= Constants.geometry_tolerance:
            movement.append(f"{abs(dy):g}px {('down' if dy > 0 else 'up')}")
        if movement:
            output.append("moved " + " and ".join(movement))
        size: list[str] = []
        if abs(dw) >= Constants.geometry_tolerance:
            size.append(f"width {a.get('width', 0):g}→{b.get('width', 0):g}px")
        if abs(dh) >= Constants.geometry_tolerance:
            size.append(
                f"height {a.get('height', 0):g}→{b.get('height', 0):g}px",
            )
        if size:
            output.append("resized (" + ", ".join(size) + ")")
