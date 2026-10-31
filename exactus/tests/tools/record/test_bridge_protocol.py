# Copyright (c) 2026 Project contributors
"""HTML-editor architecture regression tests."""

from pathlib import Path
from typing import Final, final


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.
        studio: Grouped module constant.

    """

    root: Final[Path] = Path(__file__).resolve().parents[4]
    studio: Final[Path] = root / "exactus" / "tools" / "record" / "studio"


def test_editor_assets_are_local_and_iframe_free() -> None:
    """Handle test editor assets are local and iframe free.

    Raises:
        AssertionError: When the operation cannot complete.

    """
    root: Path = Constants.studio / "web"
    html: str = (root / "index.html").read_text(encoding="utf-8")
    required: tuple[str, ...] = ("editor.css", "editor.js")
    if not (root / "transport.js").is_file():
        msg: str = "Required local transport asset is missing."
        raise AssertionError(msg)
    if not all(value in html for value in required):
        msg = "Required local editor assets are missing."
        raise AssertionError(msg)
    if "<iframe" in html.lower() or "https://" in html:
        msg = "Editor must remain local and iframe-free."
        raise AssertionError(msg)
