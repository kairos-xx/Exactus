# Copyright (c) 2026 Project contributors
"""Read one value from a REST response by a JSON or XML path."""

from __future__ import annotations

from re import Match, Pattern
from re import compile as compile_pattern
from typing import TYPE_CHECKING, Final

from defusedxml import DTDForbidden
from defusedxml.ElementTree import ParseError, fromstring

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from exactus.tools.common.json_types import JsonValue


class Constants:
    """Path grammar shared by the response readers.

    Attributes:
        json_step: One ``.key`` or ``[index]`` step of a JSON path.
        xml_step: One ``name`` or ``name[index]`` step of an XML path.

    """

    json_step: Final[Pattern[str]] = compile_pattern(
        pattern="\\.([^{}.\\[\\]|]+)|\\[(\\d+)\\]",
    )
    xml_step: Final[Pattern[str]] = compile_pattern(
        pattern="^([^\\[\\]/@]+)(?:\\[(\\d+)\\])?$",
    )


class XmlRejectedError(ValueError):
    """An XML response that is unsafe or malformed to read."""


def read_json_path(*, value: JsonValue, path: str) -> JsonValue:
    """Read a dotted or indexed path from a JSON-compatible value.

    Args:
        value: Root response value.
        path: Dot and bracket path, such as ``data.items[0].id``; empty
            returns the root.

    Returns:
        The addressed value, or None when the path cannot be resolved.

    """
    current: JsonValue = value
    if not path:
        return current
    normalized: str = path if path.startswith((".", "[")) else f".{path}"
    consumed: str = ""
    for match in Constants.json_step.finditer(string=normalized):
        if match.start() != len(consumed):
            return None
        consumed += match.group(0)
        key, index_text = match.groups()
        if key is not None and isinstance(current, dict):
            current = current.get(key)
        elif index_text is not None and isinstance(current, list):
            index: int = int(index_text)
            current = current[index] if index < len(current) else None
        else:
            return None
    return current if consumed == normalized else None


def read_xml_path(*, text: str, path: str) -> str | None:
    """Read element text or an attribute from an XML document.

    Args:
        text: XML response body.
        path: Absolute path such as ``/root/item[2]/name``; a final
            ``@name`` step reads an attribute. Indexes are 1-based and
            default to 1.

    Returns:
        The text or attribute value, or None when the path does not match.

    Raises:
        XmlRejectedError: When the document declares a DTD or is not
            well-formed XML.

    """
    try:
        root: Element = fromstring(text=text, forbid_dtd=True)
    except DTDForbidden as error:
        msg: str = "XML with a DTD is not accepted"
        raise XmlRejectedError(msg) from error
    except ParseError as error:
        msg = "The response is not well-formed XML"
        raise XmlRejectedError(msg) from error
    steps: list[str] = [step for step in path.split(sep="/") if step]
    attribute: str | None = (
        steps.pop()[1:] if steps and steps[-1].startswith("@") else None
    )
    if not steps or not _matches(element=root, step=steps[0], position=1):
        return None
    current: Element = root
    for step in steps[1:]:
        found: Element | None = _child(parent=current, step=step)
        if found is None:
            return None
        current = found
    if attribute is not None:
        return current.get(key=attribute)
    return "".join(current.itertext())


def _matches(*, element: Element, step: str, position: int) -> bool:
    """Tell whether an element is the one a path step names.

    Args:
        element: Candidate element.
        step: ``name`` or ``name[index]``.
        position: The element's 1-based position among same-named siblings.

    Returns:
        True when the name matches and the index, if any, equals position.

    """
    parsed: Match[str] | None = Constants.xml_step.match(string=step)
    if parsed is None:
        return False
    name, index_text = parsed.groups()
    return element.tag == name and int(index_text or "1") == position


def _child(*, parent: Element, step: str) -> Element | None:
    """Find the child a path step names.

    Args:
        parent: Element whose children are searched.
        step: ``name`` or ``name[index]``; the index counts only children
            with that name.

    Returns:
        The matching child, or None.

    """
    parsed: Match[str] | None = Constants.xml_step.match(string=step)
    if parsed is None:
        return None
    name, index_text = parsed.groups()
    wanted: int = int(index_text or "1")
    named: list[Element] = [item for item in parent if item.tag == name]
    return named[wanted - 1] if 0 < wanted <= len(named) else None
