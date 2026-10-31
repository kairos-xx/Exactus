# Copyright (c) 2026
"""Template loader that never reads files outside its roots."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import FileSystemLoader
from jinja2.exceptions import TemplateNotFound

if TYPE_CHECKING:
    from collections.abc import Callable

    from jinja2 import Environment


class RootBoundLoader(FileSystemLoader):
    """File-system loader that refuses symlinks leaving the roots."""

    def __init__(self, *, roots: tuple[Path, ...]) -> None:
        """Remember the resolved roots.

        Args:
            roots: Directories templates are loaded from, in order.

        """
        self._bound: tuple[Path, ...] = tuple(root.resolve() for root in roots)
        super().__init__(
            searchpath=[str(object=root) for root in self._bound],
            followlinks=False,
        )

    def get_source(
        self,
        environment: Environment,
        template: str,
    ) -> tuple[str, str, Callable[[], bool]]:
        """Load a template, rejecting files that resolve outside a root.

        Args:
            environment: Jinja2 environment requesting the template.
            template: Template name relative to a root.

        Returns:
            Source, filename and freshness callback.

        Raises:
            TemplateNotFound: The file resolves outside every root.

        """
        source, filename, uptodate = super().get_source(
            environment=environment,
            template=template,
        )
        real: Path = Path(filename).resolve()
        if not any(real.is_relative_to(root) for root in self._bound):
            raise TemplateNotFound(name=template)
        return source, filename, uptodate
