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
                        """\
    async ({selector, options}) => {
                    const element = document.querySelector(selector);
                    if (!element)
                        throw new Error(`Scene root not found: ${selector}`);\

                    const scene = await globalThis.Descriptor
                        .describe(element, options);
                    const visualCauseSelector = node => {
                        if (node.id) return `#${CSS.escape(node.id)}`;
                        const parts = [];
                        let current = node;
                        while (current && current.nodeType === \
Node.ELEMENT_NODE &&
                               current !== document.documentElement) {
                            const localName = current.localName;
                            let part = localName;
                            if (current.classList.length)
                                part += `.${[...current.classList].slice(0, 3)\

                                    .map(value => CSS.escape(value)).join(".")\
}`;
                            if (current.parentElement) {
                                const siblings =
                                    [...current.parentElement.children]
                                        .filter(sibling =>
                                            sibling.localName === localName);\

                                if (siblings.length > 1)
                                    part += ":nth-of-type(" +
                                        (siblings.indexOf(current) + 1) + ")";\

                            }
                            parts.unshift(part);
                            current = current.parentElement;
                        }
                        return parts.join(" > ");
                    };
                    for (const item of Object.values(scene.elements ?? {})) \
{
                        const node = item.selector
                            ? document.querySelector(item.selector)
                            : null;
                        item.visualCauseSelector =
                            node ? visualCauseSelector(node) : null;
                    }
                    return scene;
                }"""
                    ),
                )
            ),
            arg=payload,
        )
        if not isinstance(raw, dict):
            msg: str = "Descriptor returned a non-object scene."
            raise TypeError(msg)
        return raw
