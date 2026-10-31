# Copyright (c) 2026 Project contributors
"""Verify that response values are read by JSON and XML paths."""

from __future__ import annotations

import pytest

from exactus.tests.common.support import expect_equal
from exactus.tools.record.response_paths import (
    XmlRejectedError,
    read_json_path,
    read_xml_path,
)


def test_json_path_reads_nested_index() -> None:
    """A dotted path with an index reaches a nested JSON value."""
    expect_equal(
        actual=read_json_path(
            value={"data": {"items": [{"id": 7}]}},
            path="data.items[0].id",
        ),
        expected=7,
    )


def test_json_path_missing_returns_none() -> None:
    """A path that leaves the document yields nothing."""
    expect_equal(
        actual=read_json_path(value={"data": {}}, path="data.items[0].id"),
        expected=None,
    )


def test_xml_path_reads_text() -> None:
    """A 1-based element index selects the matching sibling's text."""
    expect_equal(
        actual=read_xml_path(text="<r><i>a</i><i>b</i></r>", path="/r/i[2]"),
        expected="b",
    )


def test_xml_path_reads_attribute() -> None:
    """A trailing @name step reads an attribute."""
    expect_equal(
        actual=read_xml_path(text='<r><i id="9"/></r>', path="/r/i[1]/@id"),
        expected="9",
    )


def test_xml_with_dtd_is_rejected() -> None:
    """A document declaring a DTD is refused before it is parsed."""
    with pytest.raises(
        expected_exception=XmlRejectedError,
        match="XML with a DTD is not accepted",
    ):
        _ = read_xml_path(
            text='<!DOCTYPE r [<!ENTITY x "y">]><r>&x;</r>',
            path="/r",
        )
