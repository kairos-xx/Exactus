# Copyright (c) 2026 João Lopes.
"""Tests for source-preserving Python class method organization."""

from ast import ClassDef, FunctionDef, Module, parse
from io import StringIO
from pathlib import Path
from textwrap import dedent

import pytest

from exactus.packages.organize import core as organize_core
from exactus.packages.organize.core import (
    Constants,
    PythonClassMethodReorderer,
    ReorderMetrics,
    ReorderResult,
    configured_order,
    main,
    validate_order,
)


def expect(*, condition: bool) -> None:
    """Fail when a test condition is false.

    Args:
        condition: Condition that must hold.

    Raises:
        AssertionError: If the condition does not hold.

    """
    if not condition:
        raise AssertionError


def method_names(*, source: str, class_name: str = "Example") -> list[str]:
    """Return direct method names from a class.

    Args:
        source: Python source to inspect.
        class_name: Class whose methods are returned.

    Returns:
        Direct method names in source order.

    """
    tree: Module = parse(source=source)
    class_node: ClassDef = next(
        node
        for node in tree.body
        if isinstance(node, ClassDef) and node.name == class_name
    )
    return [
        node.name for node in class_node.body if isinstance(node, FunctionDef)
    ]


def test_reorders_every_category_stably() -> None:
    """Place every supported method category in canonical order."""
    source: str = dedent(
        text=(
            '\n        class Example:\n            """Example containing '
            'every supported method category."""\n\n            def '
            '_instance(self) -> None:\n                """Perform private '
            'instance work."""\n\n            @staticmethod\n            def '
            '_static() -> None:\n                """Perform private static '
            'work."""\n\n            @property\n            def '
            '_hidden(self) -> int:\n                """Return the hidden '
            "marker.\n\n                Returns:\n                    Hidden "
            'marker value.\n\n                """\n                return '
            "1\n\n            @classmethod\n            def _factory(cls) -> "
            'None:\n                """Perform private factory work."""\n\n  '
            "          def __repr__(self) -> str:\n                "
            '"""Return a debugging representation.\n\n                '
            "Returns:\n                    Debugging representation.\n\n     "
            '           """\n                return "Example()"\n\n          '
            '  def public(self) -> None:\n                """Perform '
            'public work."""\n\n            @staticmethod\n            def '
            'utility() -> None:\n                """Perform public utility '
            'work."""\n\n            @property\n            def value(self) '
            '-> int:\n                """Return the public value.\n\n        '
            "        Returns:\n                    Public value.\n\n         "
            '       """\n                return 1\n\n            '
            "@classmethod\n            def create(cls) -> None:\n           "
            '     """Perform public factory work."""\n\n            def _'
            '_init__(self) -> None:\n                """Initialize the '
            'example."""\n\n            def __new__(cls) -> "Example":\n     '
            '           """Allocate the example.\n\n                '
            "Returns:\n                    Allocated example.\n\n            "
            '    """\n                return super().__new__(cls)\n        '
        ),
    ).removeprefix("\n")
    result: str = PythonClassMethodReorderer.reorder_source(source=source)
    expect(
        condition=method_names(source=result)
        == [
            "__new__",
            "__init__",
            "create",
            "value",
            "utility",
            "public",
            "__repr__",
            "_factory",
            "_hidden",
            "_static",
            "_instance",
        ],
    )


def test_preserves_decorators_annotations_docstrings_and_comments() -> None:
    """Move complex method text without reconstructing its syntax."""
    source: str = dedent(
        text=(
            '\n        class Example:\n            """Example carrying a '
            'complex factory method."""\n\n            def _helper(self) -> '
            'None:\n                """Perform private helper work."""\n    '
            "            return None\n\n            # Factory documentation "
            "comment.\n            @custom(\n                "
            'mode="strict",\n            )\n            @classmethod\n       '
            "     async def create(\n                cls,\n                "
            "*,\n                value: tuple[int, str | None],\n           "
            '     callback: "Callable[[int], bool] | None" = None,\n       '
            '     ) -> "Example | None":\n                """Create an '
            "example with the exact original docstring.\n\n                "
            "Args:\n                    value: Packed settings for the "
            "example.\n                    callback: Optional acceptance "
            "predicate.\n\n                Returns:\n                    The "
            'new example or nothing when rejected.\n\n                """\n  '
            "              # Body comment remains exact.\n                "
            "return (\n                    cls()\n                    if "
            "callback is None or callback(value[0])\n                    "
            "else None\n                )\n\n            def __init__(self) "
            '-> None:\n                """Initialize the example."""\n      '
            "  "
        ),
    ).removeprefix("\n")
    method_start: int = source.index("    # Factory documentation comment.")
    method_end: int = source.index("\n\n    def __init__")
    method: str = source[method_start:method_end]
    result: str = PythonClassMethodReorderer.reorder_source(source=source)
    expect(condition=method in result)
    expect(
        condition=result.index("def __init__")
        < result.index("async def create"),
    )
    expect(
        condition=result.index("async def create")
        < result.index("def _helper"),
    )


def test_property_family_is_adjacent_and_accessor_order_is_normalized() -> (
    None
):
    """Keep a property getter, setter, and deleter together."""
    source: str = dedent(
        text=(
            '\n        class Example:\n            """Example owning a managed'
            ' property family."""\n\n            @property\n            def ot'
            'her(self) -> int:\n                """Return the other value.\n\n'
            "                Returns:\n                    Other value.\n\n   "
            '             """\n                return 2\n\n            @value.'
            'deleter\n            def value(self) -> None:\n                ""'
            '"Delete the stored value."""\n\n            @value.setter\n      '
            '      def value(self, new_value: int) -> None:\n                "'
            '""Store a new value.\n\n                Args:\n                  '
            '  new_value: Value to store.\n\n                """\n            '
            "    self._value = new_value\n\n            @property\n           "
            ' def value(self) -> int:\n                """Return the stored va'
            "lue.\n\n                Returns:\n                    Stored valu"
            'e.\n\n                """\n                return self._value\n  '
            "      "
        ),
    ).removeprefix("\n")
    result: str = PythonClassMethodReorderer.reorder_source(source=source)
    getter: int = result.index("@property\n    def value")
    setter: int = result.index("@value.setter")
    deleter: int = result.index("@value.deleter")
    expect(condition=getter < setter < deleter)
    expect(condition=result.index("def other") < getter)


def test_qualified_binding_decorators_are_recognized() -> None:
    """Recognize terminal names of qualified binding decorators."""
    source: str = dedent(
        text=(
            '\n        class Example:\n            """Example using '
            'qualified binding decorators."""\n\n            def '
            'normal(self) -> None:\n                """Perform normal '
            'work."""\n\n            @builtins.staticmethod\n            def '
            'utility() -> None:\n                """Perform utility '
            'work."""\n\n            @builtins.classmethod\n            def '
            'create(cls) -> None:\n                """Create an '
            'example."""\n        '
        ),
    ).removeprefix("\n")
    result: str = PythonClassMethodReorderer.reorder_source(source=source)
    expect(
        condition=method_names(source=result)
        == ["create", "utility", "normal"],
    )


def test_blank_line_separated_comment_remains_anchored() -> None:
    """Do not attach a separated section comment to a moving method."""
    source: str = dedent(
        text=(
            '\n        class Example:\n            """Example with an '
            'anchored section comment."""\n            # SECTION: '
            "helpers\n\n            def _helper(self) -> None:\n             "
            '   """Perform helper work."""\n\n            def __init_'
            '_(self) -> None:\n                """Initialize the '
            'example."""\n        '
        ),
    ).removeprefix("\n")
    result: str = PythonClassMethodReorderer.reorder_source(source=source)
    expect(condition="    # SECTION: helpers\n\n    def __init__" in result)


def test_direct_comment_moves_with_method() -> None:
    """Move a directly adjacent comment together with its method."""
    source: str = dedent(
        text=(
            '\n        class Example:\n            """Example with directly '
            'anchored method comments."""\n            # helper comment\n   '
            "         def _helper(self) -> None:\n                "
            '"""Perform helper work."""\n\n            # init comment\n      '
            "      def __init__(self) -> None:\n                "
            '"""Initialize the example."""\n        '
        ),
    ).removeprefix("\n")
    result: str = PythonClassMethodReorderer.reorder_source(source=source)
    expect(
        condition=result.index("# init comment")
        < result.index("def __init__"),
    )
    expect(
        condition=result.index("def __init__")
        < result.index("# helper comment"),
    )


def test_nested_class_is_reordered_but_function_local_class_is_not() -> None:
    """Transform structural nested classes without touching runtime locals."""
    source: str = dedent(
        text=(
            '\n        def factory() -> type:\n            """Build a local '
            "class.\n\n            Returns:\n                The local "
            'class.\n\n            """\n            class Local:\n            '
            '    """Local class kept in source order."""\n\n                '
            'def _helper(self) -> None:\n                    """Perform '
            'local helper work."""\n\n                def __init__(self) -> '
            'None:\n                    """Initialize the local class."""\n '
            "           return Local\n\n        class Outer:\n            "
            '"""Outer class containing a nested inner class."""\n\n         '
            '   class Inner:\n                """Nested inner class."""\n\n  '
            "              def _helper(self) -> None:\n                    "
            '"""Perform inner helper work."""\n\n                def __init'
            '__(self) -> None:\n                    """Initialize the '
            'inner class."""\n\n            def _outer(self) -> None:\n      '
            '          """Perform outer work."""\n\n            def __init_'
            '_(self) -> None:\n                """Initialize the outer '
            'class."""\n        '
        ),
    ).removeprefix("\n")
    result: str = PythonClassMethodReorderer.reorder_source(source=source)
    local_start: int = result.index("    class Local:")
    local_end: int = result.index("    return Local")
    local: str = result[local_start:local_end]
    inner_start: int = result.index("    class Inner:")
    inner_end: int = result.index("    def __init__(self)", inner_start + 1)
    expect(condition=local.index("def _helper") < local.index("def __init__"))
    expect(
        condition=result.index("def __init__", inner_start)
        < result.index("def _helper", inner_start),
    )
    expect(condition=inner_end > inner_start)
    expect(
        condition=result.rindex("def __init__") < result.rindex("def _outer"),
    )


def test_idempotent_and_already_ordered_source_is_byte_identical() -> None:
    """Return byte-identical source once canonical order is reached."""
    source: str = dedent(
        text=(
            '\n        class Example:\n            """Example already '
            'arranged in canonical order."""\n\n            def __init_'
            '_(self) -> None:\n                """Initialize the '
            'example."""\n\n            def public(self) -> None:\n          '
            '      """Perform public work."""\n\n            def '
            '_private(self) -> None:\n                """Perform private '
            'work."""\n        '
        ),
    ).removeprefix("\n")
    once: str = PythonClassMethodReorderer.reorder_source(source=source)
    twice: str = PythonClassMethodReorderer.reorder_source(source=once)
    expect(condition=once == source)
    expect(condition=twice == once)


def test_single_method_and_empty_class_are_unchanged() -> None:
    """Leave classes with fewer than two direct methods untouched."""
    source: str = dedent(
        text=(
            '\n        class Empty:\n            """Empty class."""\n\n       '
            ' class Single:\n            """Class declaring a single '
            'method."""\n\n            def method(self) -> None:\n           '
            '     """Perform the only method\'s work."""\n        '
        ),
    ).removeprefix("\n")
    expect(
        condition=PythonClassMethodReorderer.reorder_source(source=source)
        == source,
    )


def test_file_api_reorders_and_reports_change(tmp_path: Path) -> None:
    """Support preview and idempotent in-place file writing.

    Args:
        tmp_path: Temporary test directory.

    """
    path: Path = tmp_path / "sample.py"
    source: str = dedent(
        text=(
            '\n        class Example:\n            """Example exercised '
            'through the file API."""\n\n            def _helper(self) -> '
            'None:\n                """Perform helper work."""\n\n           '
            ' def __init__(self) -> None:\n                """Initialize '
            'the example."""\n        '
        ),
    ).removeprefix("\n")
    _bytes_written: int = path.write_text(data=source, encoding="utf-8")
    reorderer: PythonClassMethodReorderer = PythonClassMethodReorderer(
        path=path,
    )
    preview: str = reorderer.reorder()
    expect(condition=preview != source)
    expect(condition=reorderer.write())
    expect(condition=path.read_text(encoding="utf-8") == preview)
    expect(condition=not reorderer.write())


def test_invalid_python_propagates_syntax_error() -> None:
    """Reject invalid input rather than attempting a partial rewrite."""
    with pytest.raises(expected_exception=SyntaxError):
        _result: str = PythonClassMethodReorderer.reorder_source(
            source="class Broken(:\n",
        )


def test_metrics_report_moved_methods_classes_and_lines() -> None:
    """Aggregate moved-method counts for one reordered class."""
    source: str = dedent(
        text=(
            '\n        class Example:\n            """Example with two '
            'methods out of order."""\n\n            def _helper(self) -> '
            'None:\n                """Perform helper work."""\n\n           '
            ' def __init__(self) -> None:\n                """Initialize '
            'the example."""\n        '
        ),
    ).removeprefix("\n")
    result: ReorderResult = PythonClassMethodReorderer.reorder_source_detailed(
        source=source,
    )
    expect(condition=result.changed)
    expect(
        condition=result.metrics
        == ReorderMetrics(
            classes_reordered=1,
            classes_seen=1,
            lines_moved=4,
            methods_moved=2,
            methods_seen=2,
        ),
    )


def test_metrics_report_zero_moves_for_ordered_source() -> None:
    """Report zero movement when the source is already ordered."""
    source: str = dedent(
        text=(
            '\n        class Example:\n            """Example already in '
            'canonical order."""\n\n            def __init__(self) -> '
            'None:\n                """Initialize the example."""\n\n        '
            '    def public(self) -> None:\n                """Perform '
            'public work."""\n        '
        ),
    ).removeprefix("\n")
    result: ReorderResult = PythonClassMethodReorderer.reorder_source_detailed(
        source=source,
    )
    expect(condition=not result.changed)
    expect(
        condition=result.metrics
        == ReorderMetrics(classes_seen=1, methods_seen=2),
    )


def test_custom_order_reorders_by_given_categories() -> None:
    """Reorder methods using a caller-provided category order."""
    source: str = dedent(
        text=(
            '\n        class Example:\n            """Example reordered by '
            'a custom category order."""\n\n            def __init__(self) '
            '-> None:\n                """Initialize the example."""\n\n     '
            '       def public(self) -> None:\n                """Perform '
            'public work."""\n        '
        ),
    ).removeprefix("\n")
    order: tuple[str, ...] = (
        "method",
        *tuple(
            category
            for category in Constants.default_order
            if category != "method"
        ),
    )
    result: str = PythonClassMethodReorderer.reorder_source(
        source=source,
        order=order,
    )
    expect(condition=method_names(source=result) == ["public", "__init__"])


def test_validate_order_rejects_incomplete_and_unknown() -> None:
    """Reject orders missing categories or naming unknown categories."""
    with pytest.raises(
        expected_exception=ValueError,
        match="invalid organize order",
    ):
        _result: tuple[str, ...] = validate_order(order=("init", "method"))
    with pytest.raises(
        expected_exception=ValueError,
        match="invalid organize order",
    ):
        _result = validate_order(
            order=(*Constants.default_order[:-1], "bogus"),
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="invalid organize order",
    ):
        _result = validate_order(order=(*Constants.default_order, "init"))


def test_configured_order_reads_pyproject(tmp_path: Path) -> None:
    """Resolve [tool.organize] order from the nearest pyproject.

    Args:
        tmp_path: Temporary test directory.

    """
    _bytes: int = (tmp_path / "pyproject.toml").write_text(
        data='[tool.organize]\norder = ["method", '
        + ", ".join(
            f'"{category}"'
            for category in Constants.default_order
            if category != "method"
        )
        + "]\n",
        encoding="utf-8",
    )
    order: tuple[str, ...] = configured_order(start=tmp_path)
    expect(condition=order[0] == "method")
    expect(condition=frozenset(order) == frozenset(Constants.default_order))


def test_configured_order_defaults_without_section(tmp_path: Path) -> None:
    """Return the canonical order when no [tool.organize] section exists.

    Args:
        tmp_path: Temporary test directory.

    """
    _bytes: int = (tmp_path / "pyproject.toml").write_text(
        data='[project]\nname = "demo"\n',
        encoding="utf-8",
    )
    expect(
        condition=configured_order(start=tmp_path) == Constants.default_order,
    )


def test_configured_order_rejects_invalid_pyproject(tmp_path: Path) -> None:
    """Reject a [tool.organize] order that is not a permutation.

    Args:
        tmp_path: Temporary test directory.

    """
    _bytes: int = (tmp_path / "pyproject.toml").write_text(
        data='[tool.organize]\norder = ["init"]\n',
        encoding="utf-8",
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="invalid organize order",
    ):
        _result: tuple[str, ...] = configured_order(start=tmp_path)


def test_main_dry_run_reports_metrics_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Report would-change metrics under --dry-run without writing.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Module attribute patcher.

    """
    path: Path = tmp_path / "target.py"
    source: str = dedent(
        text=(
            '\n        class Example:\n            """Example organized by '
            'the CLI."""\n\n            def _helper(self) -> None:\n         '
            '       """Perform helper work."""\n\n            def __init_'
            '_(self) -> None:\n                """Initialize the '
            'example."""\n        '
        ),
    ).removeprefix("\n")
    _bytes: int = path.write_text(data=source, encoding="utf-8")
    output: StringIO = StringIO()
    monkeypatch.setattr(target=organize_core, name="stdout", value=output)
    status: int = main(arguments=(str(object=path), "--dry-run"))
    expect(condition=status == 0)
    expect(condition=path.read_text(encoding="utf-8") == source)
    expect(condition=f"would update: {path}" in output.getvalue())
    expect(condition="2/2 methods moved" in output.getvalue())


def test_main_expands_globs_and_applies_exclude(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expand glob arguments and skip --exclude matches.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Module attribute patcher.

    """
    source: str = dedent(
        text=(
            '\n        class Example:\n            """Example organized by '
            'the CLI."""\n\n            def _helper(self) -> None:\n         '
            '       """Perform helper work."""\n\n            def __init_'
            '_(self) -> None:\n                """Initialize the '
            'example."""\n        '
        ),
    ).removeprefix("\n")
    first: Path = tmp_path / "a_module.py"
    second: Path = tmp_path / "b_module.py"
    _bytes: int = first.write_text(data=source, encoding="utf-8")
    _bytes = second.write_text(data=source, encoding="utf-8")
    output: StringIO = StringIO()
    monkeypatch.setattr(target=organize_core, name="stdout", value=output)
    status: int = main(
        arguments=(str(object=tmp_path / "*.py"), "--exclude", "*b_module.py"),
    )
    expect(condition=status == 0)
    expect(condition=f"updated: {first}" in output.getvalue())
    expect(condition="b_module.py" not in output.getvalue())
    expect(condition=second.read_text(encoding="utf-8") == source)


def test_main_order_flag_overrides_pyproject(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Apply the --order category list instead of the default.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Module attribute patcher.

    """
    path: Path = tmp_path / "ordered.py"
    source: str = dedent(
        text=(
            '\n        class Example:\n            """Example already '
            'ordered for a method-first order."""\n\n            def '
            'public(self) -> None:\n                """Perform public '
            'work."""\n\n            def __init__(self) -> None:\n           '
            '     """Initialize the example."""\n        '
        ),
    ).removeprefix("\n")
    _bytes: int = path.write_text(data=source, encoding="utf-8")
    order: str = ",".join(
        (
            "method",
            *tuple(
                category
                for category in Constants.default_order
                if category != "method"
            ),
        ),
    )
    output: StringIO = StringIO()
    monkeypatch.setattr(target=organize_core, name="stdout", value=output)
    status: int = main(arguments=(str(object=path), "--order", order))
    expect(condition=status == 0)
    expect(condition=f"unchanged: {path}" in output.getvalue())


def test_main_rejects_an_invalid_order_flag() -> None:
    """Exit through the parser for an unknown category name."""
    with pytest.raises(expected_exception=SystemExit):
        _status: int = main(arguments=("file.py", "--order", "bogus"))


def test_main_without_paths_returns_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Print usage and return nonzero when no paths are given.

    Args:
        monkeypatch: Module attribute patcher.

    """
    output: StringIO = StringIO()
    monkeypatch.setattr(target=organize_core, name="stdout", value=output)
    expect(condition=main(arguments=()) == 1)
    expect(condition="usage:" in output.getvalue())
