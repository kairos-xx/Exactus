# Copyright (c) 2026 Project contributors
"""Read target element identity without dispatching an interaction."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING, Final, cast, final

from playwright.sync_api import Error as PlaywrightError

if TYPE_CHECKING:
    from playwright.sync_api import Frame, Page
    from playwright.sync_api._generated import ElementHandle

    from exactus.tools.record.store import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        probe: Grouped module constant.
        frame_tags: Grouped module constant.
        max_frame_depth: Grouped module constant.

    """

    probe: Final[str] = dedent(
        text=(
            "    ({x, y}) => {\n            const element = document.elementFr"
            "omPoint(x, y);\n            if (!element) return null;\n         "
            "   let selector = '';\n            for (const attribute of ['id',"
            " 'data-testid', 'name']) {\n              const value = element.g"
            "etAttribute(attribute);\n              if (!value) continue;\n   "
            "           const candidate = attribute === 'id' ? '#' + CSS.escap"
            "e(value)\n                : '[' + attribute + '=' + JSON.stringif"
            "y(value) + ']';\n              if (document.querySelectorAll(cand"
            "idate).length === 1) {\n                selector = candidate;\n  "
            "              break;\n              }\n            }\n           "
            " if (!selector) {\n              const parts = [];\n             "
            " for (let node = element;\n                node && node !== docum"
            "ent.documentElement;\n                node = node.parentElement) "
            "{\n                const tag = node.localName;\n                c"
            "onst siblings = [...node.parentElement.children]\n               "
            "   .filter(child => child.localName === tag);\n                pa"
            "rts.unshift(siblings.length > 1\n                  ? tag + ':nth-"
            "of-type('\n                    + (siblings.indexOf(node) + 1) + '"
            ")' : tag);\n                const candidate = parts.join(' > ');"
            "\n                if (document.querySelectorAll(candidate).length"
            " === 1) {\n                  selector = candidate;\n             "
            "     break;\n                }\n              }\n            }\n "
            "           const rect = element.getBoundingClientRect();\n       "
            "     const implicit = {a: 'link', button: 'button',\n            "
            "  select: 'combobox', textarea: 'textbox', img: 'img',\n         "
            "     nav: 'navigation',\n              h1: 'heading', h2: 'headin"
            "g', h3: 'heading', h4: 'heading',\n              h5: 'heading', h"
            "6: 'heading', li: 'listitem', ul: 'list'};\n            const inp"
            "utRoles = {checkbox: 'checkbox', radio: 'radio',\n              b"
            "utton: 'button', submit: 'button', range: 'slider'};\n           "
            " const roleOf = node => node.getAttribute('role')\n              "
            "|| (node.localName === 'input'\n                ? inputRoles[node"
            ".type] || 'textbox'\n                : implicit[node.localName] |"
            "| '');\n            const nameOf = node => (node.getAttribute('ar"
            "ia-label')\n              || node.textContent || node.getAttribut"
            "e('placeholder')\n              || '').trim().replace(/\\s+/g, ' "
            "').slice(0, 60);\n            const role = roleOf(element);\n    "
            "        const name = nameOf(element);\n            const alternat"
            "ives = [];\n            const testId = element.getAttribute('data"
            "-testid');\n            if (testId)\n              alternatives.p"
            "ush({strategy: 'test id',\n                selector: '[data-testi"
            "d=' + JSON.stringify(testId) + ']',\n                matches: doc"
            "ument.querySelectorAll(\n                  '[data-testid=' + JSON"
            ".stringify(testId) + ']').length});\n            if (role && name"
            ")\n              alternatives.push({strategy: 'role and name',\n "
            "               selector: 'role=' + role + '[name='\n             "
            "     + JSON.stringify(name) + ']',\n                matches: [..."
            "document.querySelectorAll('*')].filter(\n                  node ="
            "> roleOf(node) === role\n                    && nameOf(node) === "
            "name).length});\n            if (selector)\n              alterna"
            "tives.push({strategy: 'css', selector,\n                matches: "
            "document.querySelectorAll(selector).length});\n            return"
            " {selector: selector || 'html', tag: element.localName,\n        "
            "      text: (element.getAttribute('aria-label')\n                "
            "|| element.textContent || '').trim().slice(0, 120),\n            "
            "  role, name, alternatives,\n              matches: selector ? do"
            "cument.querySelectorAll(selector).length\n                : 0,\n "
            "             frame: window === window.top ? 'main page'\n        "
            "        : 'frame ' + (window.name || location.pathname),\n       "
            "       page: location.href,\n              rect: {x: rect.x, y: r"
            "ect.y,\n                width: rect.width, height: rect.height}};"
            "\n          }"
        ),
    )
    frame_tags: Final[set[str]] = {"iframe", "frame"}
    max_frame_depth: Final[int] = 4


def _number(*, value: JsonValue) -> float | None:
    """Return a JSON field as a float when it holds a number.

    Args:
        value: JSON-decoded field to convert.

    Returns:
        The field as a float, or None for any non-numeric JSON value.

    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def inspect_target(*, page: Page, x: float, y: float) -> JsonValue:
    """Inspect a target CSS point without changing the target DOM.

    The hit test follows nested frames, so the result names the frame that
    owns the element and its bounds are in top-level viewport coordinates.
    Elements inside frames report ``unsupported`` because recorded selectors
    resolve against the main page only.

    Args:
        page: Actual Playwright page being recorded.
        x: Target viewport horizontal coordinate.
        y: Target viewport vertical coordinate.

    Returns:
        Unique CSS selector, accessible identity, selector alternatives with
        their match counts, page identity and viewport bounds. None when
        nothing is hit or the page changed while it was inspected.

    """
    try:
        return _inspect(
            frame=page.main_frame,
            x=x,
            y=y,
            offset=(0.0, 0.0),
            depth=0,
        )
    except PlaywrightError:
        return None


def _inspect(
    *,
    frame: Frame,
    x: float,
    y: float,
    offset: tuple[float, float],
    depth: int,
) -> JsonValue:
    """Inspect a point in one frame and descend through hit iframes.

    Args:
        frame: Frame whose document receives the hit test.
        x: Horizontal coordinate inside this frame.
        y: Vertical coordinate inside this frame.
        offset: Position of this frame's origin in the top-level viewport.
        depth: Number of frames already entered.

    Returns:
        Inspection of the deepest reachable element, or None.

    """
    found: JsonValue = cast(
        typ="JsonValue",
        val=frame.evaluate(expression=Constants.probe, arg={"x": x, "y": y}),
    )
    if not isinstance(found, dict):
        return None
    if (
        found.get("tag") in Constants.frame_tags
        and depth < Constants.max_frame_depth
    ):
        handle: ElementHandle | None = frame.evaluate_handle(
            expression="({x, y}) => document.elementFromPoint(x, y)",
            arg={"x": x, "y": y},
        ).as_element()
        child: Frame | None = handle.content_frame() if handle else None
        rect: JsonValue = found["rect"]
        rect_x: float | None = (
            _number(value=rect.get("x")) if isinstance(rect, dict) else None
        )
        rect_y: float | None = (
            _number(value=rect.get("y")) if isinstance(rect, dict) else None
        )
        if child is not None and rect_x is not None and (rect_y is not None):
            inner: JsonValue = _inspect(
                frame=child,
                x=x - rect_x,
                y=y - rect_y,
                offset=(offset[0] + rect_x, offset[1] + rect_y),
                depth=depth + 1,
            )
            if isinstance(inner, dict):
                return inner
    if depth:
        rect = found["rect"]
        if isinstance(rect, dict):
            frame_x: float | None = _number(value=rect.get("x"))
            frame_y: float | None = _number(value=rect.get("y"))
            if frame_x is not None and frame_y is not None:
                found["rect"] = {
                    **rect,
                    "x": frame_x + offset[0],
                    "y": frame_y + offset[1],
                }
        found["unsupported"] = (
            "Elements inside frames can not be targeted by recorded actions."
        )
    return found
