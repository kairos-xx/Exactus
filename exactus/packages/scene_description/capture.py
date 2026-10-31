"""Playwright bridge for the rendered semantic scene descriptor."""

from pathlib import Path
from textwrap import dedent
from typing import Protocol

from exactus.packages.scene_description.models import (
    DescriptionOptions,
    JsonValue,
)


class PageLike(Protocol):
    """Narrow synchronous Playwright page boundary used by the descriptor."""

    def add_script_tag(self, *, content: str) -> JsonValue:
        """Inject JavaScript into the current document.

        Args:
            content: JavaScript source to inject.

        Returns:
            The resulting value.

        """
        ...

    def evaluate(self, *, expression: str, arg: JsonValue = None) -> JsonValue:
        """Evaluate JavaScript in the current document.

        Args:
            expression: JavaScript expression or function source.
            arg: JSON-serializable argument passed to ``expression``.

        Returns:
            The resulting value.

        """
        ...


class SceneDescriptor:
    """Capture a semantic scene graph from a rendered Playwright page."""

    def __init__(self, *, script_path: Path | None = None) -> None:
        """Initialize the descriptor.

        Args:
            script_path: Optional path to the browser runtime. The bundled
                runtime is used when omitted.

        """
        self._script_path: Path = script_path or (
            Path(__file__).parent / "js" / "unified_evidence.js"
        )
        self._source: str = self._script_path.read_text(encoding="utf-8")

    def install(self, *, page: PageLike) -> None:
        """Install the descriptor runtime into the current document.

        Args:
            page: Synchronous Playwright page to prepare.

        """
        available: JsonValue = page.evaluate(
            expression="() => typeof globalThis.Descriptor === 'function'",
        )
        if available is True:
            return
        page.add_script_tag(content=self._source)

    def describe(
        self,
        *,
        page: PageLike,
        selector: str = "html",
        options: DescriptionOptions | None = None,
    ) -> dict[str, JsonValue]:
        """Describe one rendered DOM subtree.

        Args:
            page: Synchronous Playwright page once the target state rendered.
            selector: CSS selector defining the scene root.
            options: Descriptor capture options.

        Returns:
            Semantic scene graph produced by the browser runtime.

        Raises:
            TypeError: If the descriptor runtime returns a non-object.

        """
        self.install(page=page)
        payload: dict[str, JsonValue] = {
            "selector": selector,
            "options": (options or DescriptionOptions()).browser_options(),
        }
        raw: JsonValue = page.evaluate(
            expression=(
                dedent(
                    text=(
                        "    async ({selector, options}) => {\n           "
                        "         const element = document.querySelector(s"
                        "elector);\n                    if (!element)\n   "
                        "                     throw new Error(`Scene root "
                        "not found: ${selector}`);\n                    co"
                        "nst scene = await globalThis.Descriptor\n        "
                        "                .describe(element, options);\n   "
                        "                 const visualCauseSelector = node"
                        " => {\n                        if (node.id) retur"
                        "n `#${CSS.escape(node.id)}`;\n                   "
                        "     const parts = [];\n                        l"
                        "et current = node;\n                        while"
                        " (current && current.nodeType === Node.ELEMENT_NO"
                        "DE &&\n                               current !=="
                        " document.documentElement) {\n                   "
                        "         const localName = current.localName;\n  "
                        "                          let part = localName;\n"
                        "                            if (current.classList"
                        ".length)\n                                part +="
                        " `.${[...current.classList].slice(0, 3)\n        "
                        "                            .map(value => CSS.esc"
                        'ape(value)).join(".")}`;\n                       '
                        "     if (current.parentElement) {\n              "
                        "                  const siblings =\n             "
                        "                       [...current.parentElement."
                        "children]\n                                      "
                        "  .filter(sibling =>\n                           "
                        "                 sibling.localName === localName)"
                        ";\n                                if (siblings.l"
                        "ength > 1)\n                                    p"
                        'art += ":nth-of-type(" +\n                       '
                        "                 (siblings.indexOf(current) + 1) "
                        '+ ")";\n                            }\n          '
                        "                  parts.unshift(part);\n         "
                        "                   current = current.parentElemen"
                        "t;\n                        }\n                  "
                        '      return parts.join(" > ");\n                '
                        "    };\n                    for (const item of Ob"
                        "ject.values(scene.elements ?? {})) {\n           "
                        "             const node = item.selector\n        "
                        "                    ? document.querySelector(item"
                        ".selector)\n                            : null;\n"
                        "                        item.visualCauseSelector "
                        "=\n                            node ? visualCause"
                        "Selector(node) : null;\n                    }\n  "
                        "                  return scene;\n                "
                        "}"
                    ),
                )
            ),
            arg=payload,
        )
        if not isinstance(raw, dict):
            msg: str = "Descriptor returned a non-object scene."
            raise TypeError(msg)
        return raw
