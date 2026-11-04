# Copyright (c) 2026
"""Visual-cause targets resolve from flags and configuration."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING, cast

import pytest

from exactus.tests.common.support import expect_equal, expect_true
from exactus.tools.visual_cause.arguments import create_parser
from exactus.tools.visual_cause.targets import (
    Target,
    TargetOptions,
    Viewport,
    configured,
    resolve,
)

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


def _options(*, root: Path, flags: tuple[str, ...] = ()) -> TargetOptions:
    """Parse flags into typed target options rooted at ``root``.

    Args:
        root: Project root the options resolve relative paths against.
        flags: Command-line flags after the root argument.

    Returns:
        Parsed target options.

    """
    return cast(
        typ="TargetOptions",
        val=create_parser().parse_args(args=[str(object=root), *flags]),
    )


def _project(*, root: Path, targets: str) -> Path:
    """Write a project whose pyproject declares visual-cause targets.

    Args:
        root: Directory to create the project in.
        targets: TOML array-of-tables text for ``targets``.

    Returns:
        The project root.

    """
    _ = (root / "pyproject.toml").write_text(
        data="""\
[tool.exactus]
root = true
"""
        + targets,
        encoding="utf-8",
    )
    return root


def test_viewport_parses_and_labels() -> None:
    """A ``WIDTHxHEIGHT`` string becomes an ordered viewport."""
    viewport: Viewport = Viewport.parse(value="1440X900")
    expect_equal(
        actual=(viewport.width, viewport.height),
        expected=(1440, 900),
    )
    expect_equal(actual=viewport.label, expected="1440x900")


@pytest.mark.parametrize("value", ["1440", "axb", "0x10", "10x0", "1x2x3"])
def test_viewport_rejects_malformed_values(value: str) -> None:
    """Non-numeric, non-positive and wrongly shaped viewports are errors.

    Args:
        value: Malformed viewport string.

    """
    with pytest.raises(expected_exception=ValueError, match="viewport"):
        _ = Viewport.parse(value=value)


def test_ad_hoc_stylesheet_target(tmp_path: Path) -> None:
    """One page with two stylesheets resolves to a stylesheets target.

    Args:
        tmp_path: Per-test directory.

    """
    page: Path = tmp_path / "page.html"
    _ = page.write_text(data="<p>x</p>", encoding="utf-8")
    options: TargetOptions = _options(
        root=tmp_path,
        flags=(
            "--html",
            str(object=page),
            "--css-a",
            "a.css",
            "--css-b",
            "b.css",
            "--viewport",
            "400x300",
            "--fail",
            "#box",
            "--threshold",
            "4",
        ),
    )
    targets: tuple[Target, ...] = resolve(options=options)
    expect_equal(actual=len(targets), expected=1)
    target: Target = targets[0]
    expect_equal(actual=target.name, expected="adhoc")
    expect_equal(actual=target.mode, expected="stylesheets")
    expect_equal(actual=target.fail, expected=("#box",))
    expect_equal(actual=target.threshold, expected=4)
    expect_equal(
        actual=target.viewports,
        expected=(Viewport(width=400, height=300),),
    )


def test_default_viewport_and_modes(tmp_path: Path) -> None:
    """A B page selects page mode; css-b alone selects overlay mode.

    Args:
        tmp_path: Per-test directory.

    """
    page_mode: Target = resolve(
        options=_options(
            root=tmp_path,
            flags=("--url", "http://a/", "--url-b", "http://b/"),
        ),
    )[0]
    expect_equal(actual=page_mode.mode, expected="page")
    expect_equal(
        actual=page_mode.viewports,
        expected=(Viewport(width=1440, height=900),),
    )
    overlay: Target = resolve(
        options=_options(
            root=tmp_path,
            flags=("--url", "http://a/", "--css-b", "b.css"),
        ),
    )[0]
    expect_equal(actual=overlay.mode, expected="overlay")


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        (("--url", "http://a/", "--target", "home"), "separately"),
        (("--css-b", "b.css"), "exactly one of url or html"),
        (
            ("--url", "http://a/", "--html", "p.html", "--css-b", "b"),
            "exactly",
        ),
        (
            ("--url", "http://a/", "--url-b", "http://b/", "--html-b", "b"),
            "conflict",
        ),
        (
            ("--url", "http://a/", "--url-b", "http://b/", "--css-a", "a"),
            "cannot use CSS sides",
        ),
        (("--url", "http://a/"), "B page or css-b"),
        (
            ("--url", "http://a/", "--css-b", "b", "--viewport", "bad"),
            "viewport",
        ),
        (
            ("--url", "http://a/", "--css-b", "b", "--threshold", "999"),
            "threshold",
        ),
        (
            ("--url", "http://a/", "--css-b", "b", "--timeout-ms", "0"),
            "positive",
        ),
        (
            ("--url", "http://a/", "--css-b", "b", "--screenshot-scale", "0"),
            "screenshot-scale",
        ),
    ],
)
def test_invalid_ad_hoc_options_are_rejected(
    flags: tuple[str, ...],
    message: str,
    tmp_path: Path,
) -> None:
    """Contradictory or out-of-range flags raise a descriptive error.

    Args:
        flags: Offending command-line flags.
        message: Fragment the error must contain.
        tmp_path: Per-test directory.

    """
    with pytest.raises(expected_exception=ValueError, match=message):
        _ = resolve(options=_options(root=tmp_path, flags=flags))


def test_missing_source_without_configuration(tmp_path: Path) -> None:
    """Without flags or configuration a target must be provided.

    Args:
        tmp_path: Per-test directory.

    """
    root: Path = _project(root=tmp_path, targets="")
    with pytest.raises(
        expected_exception=ValueError,
        match="Provide a target",
    ):
        _ = resolve(options=_options(root=root))


def test_configured_targets_resolve_by_name(tmp_path: Path) -> None:
    """Named targets load from pyproject, relative to their file.

    Args:
        tmp_path: Per-test directory.

    """
    root: Path = _project(
        root=tmp_path,
        targets=(
            dedent(
                text=(
                    """\
    [[tool.exactus.visual_cause.targets]]
    name = "home"
    html = "site"
    css-b = "b.css"
    viewports = ["320x480", "1024x768"]
    accept = ["p"]
    default-level = "warning"
    native-styles-b = true
    [[tool.exactus.visual_cause.targets]]
    name = "docs"
    url = "http://x/"
    url_b = "http://y/"
    max-candidates = 9
    screenshot-scale = 1
    """
                ),
            )
        ),
    )
    entries: tuple[dict[str, JsonValue], ...] = configured(start=root)
    expect_equal(actual=len(entries), expected=2)
    targets: tuple[Target, ...] = resolve(options=_options(root=root))
    expect_equal(
        actual=[item.name for item in targets],
        expected=["home", "docs"],
    )
    home: Target = targets[0]
    expect_equal(actual=home.html, expected=(root / "site").resolve())
    expect_equal(actual=len(home.viewports), expected=2)
    expect_equal(actual=home.default_level, expected="warning")
    expect_true(condition=home.native_styles_b)
    expect_equal(actual=targets[1].max_candidates, expected=9)
    only: tuple[Target, ...] = resolve(
        options=_options(root=root, flags=("--target", "docs")),
    )
    expect_equal(actual=[item.name for item in only], expected=["docs"])
    with pytest.raises(expected_exception=ValueError, match="Unknown"):
        _ = resolve(options=_options(root=root, flags=("--target", "nope")))


@pytest.mark.parametrize(
    ("body", "error", "message"),
    [
        (
            """\
name = " "
url = "http://x/"
css-b = "b"
""",
            ValueError,
            "nonempty",
        ),
        (
            """\
name = 3
url = "http://x/"
css-b = "b"
""",
            TypeError,
            "needs a name",
        ),
        (
            """\
url = 3
name = 'x'
css-b = 'b'
""",
            TypeError,
            "url must be text",
        ),
        (
            """\
name = 'x'
url = 'http://x/'
url-b = 3
""",
            TypeError,
            "url-b must be text",
        ),
        (
            """\
name = 'x'
url = 'http://x/'
css-b = 3
""",
            ValueError,
            "nonempty path",
        ),
        (
            """\
name = 'x'
url = 'http://x/'
css-b = 'b'
accept = 3
""",
            ValueError,
            "list of strings",
        ),
        (
            """\
name = 'x'
url = 'http://x/'
css-b = 'b'
threshold = true
""",
            TypeError,
            "must be an integer",
        ),
        (
            dedent(
                text=(
                    """\
    name = 'x'
    url = 'http://x/'
    css-b = 'b'
    screenshot-scale = 'big'
    """
                ),
            ),
            TypeError,
            "must be numeric",
        ),
        (
            dedent(
                text=(
                    """\
    name = 'x'
    url = 'http://x/'
    css-b = 'b'
    native-styles-a = 1
    """
                ),
            ),
            TypeError,
            "true or false",
        ),
        (
            dedent(
                text=(
                    """\
    name = 'x'
    url = 'http://x/'
    css-b = 'b'
    default-level = 'loud'
    """
                ),
            ),
            ValueError,
            "default-level",
        ),
        (
            """\
name = 'x'
url = 'http://x/'
css-b = 'b'
fail-on = 'x'
""",
            ValueError,
            "fail-on",
        ),
    ],
)
def test_invalid_configured_targets_are_rejected(
    body: str,
    error: type[Exception],
    message: str,
    tmp_path: Path,
) -> None:
    """Each malformed configured field raises a descriptive error.

    Args:
        body: Fields of one configured target.
        error: Expected exception type.
        message: Fragment the error must contain.
        tmp_path: Per-test directory.

    """
    root: Path = _project(
        root=tmp_path,
        targets="""\
[[tool.exactus.visual_cause.targets]]
"""
        + body,
    )
    with pytest.raises(expected_exception=error, match=message):
        _ = resolve(options=_options(root=root))


def test_unnamed_configured_target_is_rejected(tmp_path: Path) -> None:
    """A configured entry without a name cannot be addressed.

    Args:
        tmp_path: Per-test directory.

    """
    root: Path = _project(
        root=tmp_path,
        targets="""\
[[tool.exactus.visual_cause.targets]]
url = "http://x/"
""",
    )
    with pytest.raises(expected_exception=TypeError, match="needs a name"):
        _ = configured(start=root)
