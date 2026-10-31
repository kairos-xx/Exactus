# Copyright (c) 2026
"""Exceptions raised by the Markdown template engine."""

from __future__ import annotations


class TemplateEngineError(Exception):
    """Base error for template loading, rendering, and validation."""


class MappingError(TemplateEngineError):
    """Raised when a mapping specification is invalid."""
