"""Typed data models for rendered-scene change descriptions."""

from dataclasses import dataclass

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True, slots=True)
class DescriptionOptions:
    """Configure browser-side scene capture.

    Attributes:
        include_computed_style: Include Chromium's complete computed style.
        include_relationships: Include inferred visual relationships.
        infer_spatial_layouts: Infer rendered-coordinate layouts.
        include_binary: Retain binary descriptors in the scene manifest.
        include_element_screenshots: Capture per-element raster evidence.

    """

    include_computed_style: bool = False
    include_relationships: bool = True
    infer_spatial_layouts: bool = True
    include_binary: bool = False
    include_element_screenshots: bool = False

    def browser_options(self) -> dict[str, JsonValue]:
        """Return options using the browser runtime's camelCase API.

        Returns:
            The resulting value.

        """
        return {
            "includeComputedStyle": self.include_computed_style,
            "includeRelationships": self.include_relationships,
            "inferSpatialLayouts": self.infer_spatial_layouts,
            "includeBinary": self.include_binary,
            "includeElementScreenshots": self.include_element_screenshots,
        }
