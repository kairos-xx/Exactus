# Copyright (c) 2026
"""The engine exposes one exception tree rooted at TemplateEngineError."""

from __future__ import annotations

from exactus.packages.markdown.errors import MappingError, TemplateEngineError
from exactus.tests.common.support import expect_true


def test_mapping_error_is_a_template_engine_error() -> None:
    """Callers can catch every engine failure with one except clause."""
    expect_true(condition=TemplateEngineError in MappingError.__mro__)
    expect_true(condition=Exception in TemplateEngineError.__mro__)
