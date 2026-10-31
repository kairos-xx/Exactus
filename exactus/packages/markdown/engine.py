# Copyright (c) 2026
"""Sandboxed Jinja2 rendering of Markdown templates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from jinja2 import StrictUndefined, Undefined, select_autoescape
from jinja2.exceptions import TemplateError
from jinja2.sandbox import SandboxedEnvironment

from .errors import TemplateEngineError
from .filters import MarkdownFilters
from .loader import RootBoundLoader
from .mapping import Mapper

if TYPE_CHECKING:
    from pathlib import Path

    from jinja2 import Environment

    from .json_types import JsonValue


class MarkdownEngine:
    """Render Markdown templates with JSON mapping, loops and includes."""

    def __init__(
        self,
        *,
        roots: tuple[Path, ...],
        strict: bool = True,
    ) -> None:
        """Configure the sandbox.

        Args:
            roots: Directories templates and includes are loaded from.
            strict: Raise on undefined variables instead of rendering
                them as empty text.

        """
        self._roots: tuple[Path, ...] = tuple(root.resolve() for root in roots)
        self._env: SandboxedEnvironment = SandboxedEnvironment(
            loader=RootBoundLoader(roots=self._roots),
            undefined=StrictUndefined if strict else Undefined,
            autoescape=select_autoescape(
                default=False,
                default_for_string=False,
            ),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            extensions=("jinja2.ext.do", "jinja2.ext.loopcontrols"),
        )
        MarkdownFilters.register(env=self._env)
        self._mapper = Mapper(renderer=self)

    def context(
        self,
        *,
        source: JsonValue,
        mapping: dict[str, JsonValue] | None,
    ) -> dict[str, JsonValue]:
        """Build the template context.

        Args:
            source: Source document.
            mapping: Mapping specification, or ``None``.

        Returns:
            The render context.

        """
        return self._mapper.context(source=source, mapping=mapping)

    def render_name(self, *, name: str, context: dict[str, JsonValue]) -> str:
        """Render a template found under the roots.

        Args:
            name: Template name relative to a root.
            context: Render context.

        Returns:
            The rendered text. Any Jinja2 or template runtime failure
            surfaces as ``TemplateEngineError`` naming the template.

        """
        return self._render(env=self._env, name=name, context=context)

    def render_context(
        self,
        *,
        template: Path,
        context: dict[str, JsonValue],
    ) -> str:
        """Render a template file with a prepared context.

        Args:
            template: Template path under one of the roots.
            context: Render context.

        Returns:
            The rendered text.

        Raises:
            TemplateEngineError: The template is outside every root.

        """
        path: Path = template.resolve()
        for index, root in enumerate(iterable=self._roots):
            if path.is_relative_to(root):
                ordered: tuple[Path, ...] = (
                    root,
                    *self._roots[:index],
                    *self._roots[index + 1 :],
                )
                return self._render(
                    env=self._env.overlay(
                        loader=RootBoundLoader(roots=ordered),
                    ),
                    name=path.relative_to(root).as_posix(),
                    context=context,
                )
        msg: str = f"Template is outside configured roots: {path}"
        raise TemplateEngineError(msg)

    def render(
        self,
        *,
        template: Path,
        source: JsonValue,
        mapping: dict[str, JsonValue] | None,
    ) -> str:
        """Map ``source`` and render ``template``.

        Args:
            template: Template path under one of the roots.
            source: Source document.
            mapping: Mapping specification, or ``None``.

        Returns:
            The rendered text.

        """
        return self.render_context(
            template=template,
            context=self.context(source=source, mapping=mapping),
        )

    def __call__(self, *, name: str, context: dict[str, JsonValue]) -> str:
        """Render a named template (the ``Renderer`` protocol).

        Args:
            name: Template name relative to a root.
            context: Render context.

        Returns:
            The rendered text.

        """
        return self.render_name(name=name, context=context)

    @staticmethod
    def _render(
        *,
        env: Environment,
        name: str,
        context: dict[str, JsonValue],
    ) -> str:
        """Render ``name`` with ``env``, wrapping every template failure.

        Args:
            env: Environment to load and render with.
            name: Template name relative to a root.
            context: Render context.

        Returns:
            The rendered text.

        Raises:
            TemplateEngineError: A Jinja2 or runtime failure, prefixed
                with the template name.

        """
        try:
            return env.get_template(name=name).render(**context)
        except (
            TemplateError,
            ArithmeticError,
            TypeError,
            ValueError,
            LookupError,
            AttributeError,
        ) as exc:
            msg: str = f"{name}: {exc}"
            raise TemplateEngineError(msg) from exc
