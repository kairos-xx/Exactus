# Copyright (c) 2026
"""The engine renders sandboxed Jinja2 templates from mapped JSON."""

from __future__ import annotations

from json import dumps
from re import compile as re_compile
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.packages.markdown import (
    MappingError,
    MarkdownEngine,
    TemplateEngineError,
    render_report,
)
from exactus.packages.markdown.api import load_json
from exactus.tests.common.support import expect_equal, expect_in

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        data: Grouped module constant.

    """

    data: Final[JsonValue] = {
        "project": {"name": "Exactus"},
        "tasks": [{"t": "A"}, {"t": "B"}],
    }


def _write(*, root: Path, name: str, text: str) -> Path:
    """Write a template file.

    Args:
        root: Template root directory.
        name: Path of the template under ``root``.
        text: Template source.

    Returns:
        The written path.

    """
    path: Path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data=text, encoding="utf-8")
    return path


def test_mapping_feeds_the_template(tmp_path: Path) -> None:
    """Mapped names and the original ``source`` are both available.

    Args:
        tmp_path: Temporary directory.

    """
    page: Path = _write(
        root=tmp_path,
        name="page.md",
        text="{{ title }}|{{ source.project.name }}",
    )
    engine: MarkdownEngine = MarkdownEngine(roots=(tmp_path,))
    out: str = engine.render(
        template=page,
        source=Constants.data,
        mapping={"title": "project.name"},
    )
    expect_equal(actual=out, expected="Exactus|Exactus")


def test_inheritance_includes_and_filters(tmp_path: Path) -> None:
    """Layouts, partials and Markdown filters work together.

    Args:
        tmp_path: Temporary directory.

    """
    _write(
        root=tmp_path,
        name="layouts/base.md",
        text=(
            "# {% block title %}{% endblock %}\n{% block body %}{% endblock %}"
        ),
    )
    _write(root=tmp_path, name="partials/item.md", text="- {{ t.t }}\n")
    page: Path = _write(
        root=tmp_path,
        name="page.md",
        text=(
            '{% extends "layouts/base.md" %}'
            "{% block title %}{{ project.name | md_code }}"
            "{% endblock %}{% block body %}{% for t in tasks %}"
            '{% include "partials/item.md" %}'
            "{% endfor %}{% endblock %}"
        ),
    )
    out: str = MarkdownEngine(roots=(tmp_path,)).render(
        template=page,
        source=Constants.data,
        mapping=None,
    )
    expect_in(member="# `Exactus`", container=out)
    expect_in(member="- A\n- B", container=out)


def test_strict_undefined_raises_and_lenient_renders(tmp_path: Path) -> None:
    """Strict mode reports missing variables; lenient mode blanks them.

    Args:
        tmp_path: Temporary directory.

    """
    page: Path = _write(root=tmp_path, name="p.md", text="[{{ nope }}]")
    with pytest.raises(
        expected_exception=TemplateEngineError,
        match=re_compile(pattern="p\\.md: .*nope"),
    ):
        MarkdownEngine(roots=(tmp_path,)).render(
            template=page,
            source={},
            mapping=None,
        )
    lenient: MarkdownEngine = MarkdownEngine(roots=(tmp_path,), strict=False)
    expect_equal(
        actual=lenient.render(template=page, source={}, mapping=None),
        expected="[]",
    )


def test_syntax_errors_are_wrapped(tmp_path: Path) -> None:
    """Jinja2 syntax errors surface as TemplateEngineError.

    Args:
        tmp_path: Temporary directory.

    """
    page: Path = _write(root=tmp_path, name="p.md", text="{% if %}")
    with pytest.raises(expected_exception=TemplateEngineError):
        MarkdownEngine(roots=(tmp_path,)).render(
            template=page,
            source={},
            mapping=None,
        )


def test_sandbox_blocks_unsafe_attribute_access(tmp_path: Path) -> None:
    """Templates cannot walk to ``__class__`` and friends.

    Args:
        tmp_path: Temporary directory.

    """
    page: Path = _write(
        root=tmp_path,
        name="p.md",
        text="{{ ().__class__.__mro__ }}",
    )
    with pytest.raises(expected_exception=TemplateEngineError, match="unsafe"):
        MarkdownEngine(roots=(tmp_path,)).render(
            template=page,
            source={},
            mapping=None,
        )


def test_template_outside_roots_is_rejected(tmp_path: Path) -> None:
    """Only templates under a configured root can be rendered.

    Args:
        tmp_path: Temporary directory.

    """
    allowed: Path = tmp_path / "allowed"
    allowed.mkdir()
    outside: Path = _write(root=tmp_path / "other", name="x.md", text="secret")
    with pytest.raises(
        expected_exception=TemplateEngineError,
        match="outside",
    ):
        MarkdownEngine(roots=(allowed,)).render(
            template=outside,
            source={},
            mapping=None,
        )


def test_render_report_accepts_paths_and_objects(tmp_path: Path) -> None:
    """``render_report`` loads JSON paths and takes objects as-is.

    Args:
        tmp_path: Temporary directory.

    """
    page: Path = _write(
        root=tmp_path,
        name="page.md",
        text="{{ title }}:{{ n }}",
    )
    data: Path = tmp_path / "result.json"
    data.write_text(
        data=dumps(obj={"project": {"name": "X"}, "n": 2}),
        encoding="utf-8",
    )
    mapping: Path = tmp_path / "mapping.json"
    mapping.write_text(
        data=dumps(obj={"title": "project.name", "n": "n"}),
        encoding="utf-8",
    )
    from_paths: str = render_report(
        result=data,
        template=page,
        mapping=mapping,
    )
    from_objects: str = render_report(
        result={"project": {"name": "X"}, "n": 2},
        template=page,
        mapping={"title": "project.name", "n": "n"},
    )
    expect_equal(actual=from_paths, expected="X:2")
    expect_equal(actual=from_objects, expected="X:2")


def test_render_report_extra_roots(tmp_path: Path) -> None:
    """Partials can live in an extra template root.

    Args:
        tmp_path: Temporary directory.

    """
    shared: Path = tmp_path / "shared"
    _write(root=shared, name="footer.md", text="-- end")
    page: Path = _write(
        root=tmp_path / "tpl",
        name="page.md",
        text='body {% include "footer.md" %}',
    )
    out: str = render_report(result={}, template=page, extra_roots=(shared,))
    expect_equal(actual=out, expected="body -- end")


def test_load_json_passes_values_through(tmp_path: Path) -> None:
    """Non-path values are returned unchanged.

    Args:
        tmp_path: Temporary directory.

    """
    expect_equal(actual=load_json(value={"a": 1}), expected={"a": 1})
    path: Path = tmp_path / "d.json"
    path.write_text(data="[1, 2]", encoding="utf-8")
    expect_equal(actual=load_json(value=path), expected=[1, 2])


def test_render_report_rejects_non_object_mapping(tmp_path: Path) -> None:
    """A mapping that is not a JSON object raises MappingError.

    Args:
        tmp_path: Temporary directory.

    """
    page: Path = _write(root=tmp_path, name="page.md", text="x")
    with pytest.raises(expected_exception=MappingError, match="JSON object"):
        render_report(result={}, template=page, mapping=[1])


def test_render_report_rejects_non_object_mapping_file(tmp_path: Path) -> None:
    """A mapping file holding a JSON array raises MappingError.

    Args:
        tmp_path: Temporary directory.

    """
    page: Path = _write(root=tmp_path, name="page.md", text="x")
    mapping: Path = tmp_path / "mapping.json"
    mapping.write_text(data="[1, 2]", encoding="utf-8")
    with pytest.raises(expected_exception=MappingError, match="JSON object"):
        render_report(result={}, template=page, mapping=mapping)


def test_symlink_include_outside_roots_is_refused(tmp_path: Path) -> None:
    """An include symlinked out of the roots is not rendered.

    Args:
        tmp_path: Temporary directory.

    """
    root: Path = tmp_path / "root"
    secret: Path = _write(root=tmp_path / "out", name="s.txt", text="SECRET")
    _write(root=root, name="ok.md", text="fine")
    (root / "link.md").symlink_to(target=secret)
    engine: MarkdownEngine = MarkdownEngine(roots=(root,))
    bad: Path = _write(
        root=root,
        name="bad.md",
        text='{% include "link.md" %}',
    )
    good: Path = _write(
        root=root,
        name="good.md",
        text='{% include "ok.md" %}',
    )
    with pytest.raises(expected_exception=TemplateEngineError):
        engine.render(template=bad, source={}, mapping=None)
    expect_equal(
        actual=engine.render(template=good, source={}, mapping=None),
        expected="fine",
    )


def test_same_named_template_in_second_root_is_rendered(
    tmp_path: Path,
) -> None:
    """The file that was asked for wins over an earlier root's copy.

    Args:
        tmp_path: Temporary directory.

    """
    first: Path = tmp_path / "a"
    second: Path = tmp_path / "b"
    _write(root=first, name="same.md", text="from a")
    wanted: Path = _write(root=second, name="same.md", text="from b")
    _write(root=first, name="part.md", text="part a")
    _write(root=second, name="part.md", text="part b")
    _write(root=second, name="top.md", text='{% include "part.md" %}')
    engine: MarkdownEngine = MarkdownEngine(roots=(first, second))
    expect_equal(
        actual=engine.render(template=wanted, source={}, mapping=None),
        expected="from b",
    )
    expect_equal(
        actual=engine.render(
            template=second / "top.md",
            source={},
            mapping=None,
        ),
        expected="part b",
    )


@pytest.mark.parametrize(
    "text",
    ["{{ 1 / 0 }}", '{{ "%5d" | format("3") }}', "{{ [1][5] }}"],
)
def test_runtime_errors_are_wrapped(tmp_path: Path, text: str) -> None:
    """Runtime failures inside templates become TemplateEngineError.

    Args:
        tmp_path: Temporary directory.
        text: Failing template source.

    """
    page: Path = _write(root=tmp_path, name="p.md", text=text)
    with pytest.raises(
        expected_exception=TemplateEngineError,
        match=re_compile(pattern="^p\\.md: "),
    ):
        MarkdownEngine(roots=(tmp_path,)).render(
            template=page,
            source={},
            mapping=None,
        )


def test_bad_json_files_are_wrapped(tmp_path: Path) -> None:
    """Unreadable or malformed JSON raises TemplateEngineError.

    Args:
        tmp_path: Temporary directory.

    """
    page: Path = _write(root=tmp_path, name="page.md", text="x")
    broken: Path = tmp_path / "broken.json"
    broken.write_text(data="{nope", encoding="utf-8")
    with pytest.raises(
        expected_exception=TemplateEngineError,
        match="Cannot load",
    ):
        load_json(value=tmp_path / "missing.json")
    with pytest.raises(
        expected_exception=TemplateEngineError,
        match="Cannot load",
    ):
        render_report(result=broken, template=page)
