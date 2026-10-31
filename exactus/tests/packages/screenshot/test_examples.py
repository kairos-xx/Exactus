# Copyright (c) 2026
"""Run the public screenshot example against a live demonstration site."""

from __future__ import annotations

from importlib import import_module
from io import StringIO
from pathlib import Path
from runpy import run_path
from sys import modules

import pytest
from PIL import Image

from exactus.packages.screenshot import Screenshot
from exactus.packages.screenshot.examples import run as screenshot_example
from exactus.packages.server import local
from exactus.tests.common.support import expect_equal, expect_in, expect_true


def test_screenshot_example(
    tmp_path: Path,
    demo_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The screenshot CLI writes real PNGs at all documented widths.

    Args:
        tmp_path: Isolated output directory.
        demo_url: Live demonstration site.
        monkeypatch: Restore command arguments.

    """
    monkeypatch.setattr(
        target=import_module(name="sys"),
        name="argv",
        value=["example", demo_url, "--output", str(object=tmp_path)],
    )
    expect_equal(actual=screenshot_example.main(), expected=0)
    width: int
    for width in (390, 1440, 1728):
        with Image.open(fp=tmp_path / f"page-{width}.png") as image:
            expect_equal(actual=image.width, expected=width)
            expect_true(condition=image.height > 0)


def test_main_module_serves_the_demo_as_a_script(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run ``examples/run.py`` via ``__main__`` with a stubbed server.

    Args:
        tmp_path: Isolated output directory.
        monkeypatch: Pytest patching helper.

    """
    events: list[str] = []
    output: StringIO = StringIO()

    def reuse_server(*, path: Path) -> tuple[int, int] | None:
        """Report no recorded server.

        Args:
            path: Served root directory.

        Returns:
            Always ``None``.

        """
        _ = path
        return None

    def serve(*, path: Path, log: Path) -> tuple[int, str, bool]:
        """Return a synthetic server spawn.

        Args:
            path: Served root directory.
            log: Access-log destination.

        Returns:
            Synthetic pid, origin, and reuse flag.

        """
        _ = path
        _ = log
        events.append("serve")
        return (99, "http://127.0.0.1:8080/", False)

    def wait_ready(*, url: str, pid: int) -> bool:
        """Report the synthetic server as ready.

        Args:
            url: Server origin.
            pid: Spawned process id.

        Returns:
            Always ``True``.

        """
        _ = url
        _ = pid
        events.append("ready")
        return True

    def terminate(*, pid: int) -> None:
        """Record the terminated process id.

        Args:
            pid: Process id to terminate.

        """
        events.append(f"kill:{pid}")

    def clear_server_state(*, path: Path) -> None:
        """Record the cleared server state.

        Args:
            path: Served root directory.

        """
        _ = path
        events.append("clear")

    async def fake_capture(
        url: str | None,
        target: str,
        spec: object | None = None,
        *,
        source: object | None = None,
    ) -> object:
        """Return a synthetic capture without a browser.

        Args:
            url: Requested URL.
            target: Requested selector.
            spec: Recorded capture specification.
            source: Optional reusable page source.

        Returns:
            A synthetic capture marker.

        """
        _ = source
        events.append(f"capture:{url}:{target}:{type(spec).__name__}")
        return object()

    monkeypatch.setattr(target=local, name="reuse_server", value=reuse_server)
    monkeypatch.setattr(target=local, name="serve", value=serve)
    monkeypatch.setattr(target=local, name="wait_ready", value=wait_ready)
    monkeypatch.setattr(
        target=local,
        name="clear_server_state",
        value=clear_server_state,
    )
    monkeypatch.setattr(
        target=import_module(name="exactus.packages.server.process_control"),
        name="terminate_tree",
        value=terminate,
    )
    monkeypatch.setattr(
        target=Screenshot,
        name="capture",
        value=staticmethod(fake_capture),
    )
    monkeypatch.setattr(target=modules["sys"], name="stdout", value=output)
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=["example", "--output", str(object=tmp_path)],
    )
    example: Path = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "packages"
        / "screenshot"
        / "examples"
        / "run.py"
    )
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(path_name=str(object=example), run_name="__main__")
    expect_equal(actual=raised.value.code, expected=0)
    expect_equal(actual=events.count("capture"), expected=0)
    expect_equal(
        actual=[event for event in events if event.startswith("capture:")],
        expected=[
            "capture:http://127.0.0.1:8080/index.html:body:CaptureSpec",
            "capture:http://127.0.0.1:8080/index.html:body:CaptureSpec",
            "capture:http://127.0.0.1:8080/index.html:body:CaptureSpec",
        ],
    )
    expect_in(member="kill:99", container=" ".join(events))


def test_main_module_with_explicit_url_skips_the_server(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A positional URL captures directly without serving the bundle.

    Args:
        tmp_path: Isolated output directory.
        monkeypatch: Pytest patching helper.

    """
    captures: list[str] = []
    output: StringIO = StringIO()

    async def fake_capture(
        url: str | None,
        target: str,
        spec: object | None = None,
        *,
        source: object | None = None,
    ) -> object:
        """Return a synthetic capture without a browser.

        Args:
            url: Requested URL.
            target: Requested selector.
            spec: Recorded capture specification.
            source: Optional reusable page source.

        Returns:
            A synthetic capture marker.

        """
        _ = target
        _ = spec
        _ = source
        captures.append(str(object=url))
        return object()

    monkeypatch.setattr(
        target=Screenshot,
        name="capture",
        value=staticmethod(fake_capture),
    )
    monkeypatch.setattr(target=modules["sys"], name="stdout", value=output)
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=[
            "example",
            "https://example.invalid/",
            "--output",
            str(object=tmp_path),
        ],
    )
    example: Path = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "packages"
        / "screenshot"
        / "examples"
        / "run.py"
    )
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(path_name=str(object=example), run_name="__main__")
    expect_equal(actual=raised.value.code, expected=0)
    expect_equal(actual=len(captures), expected=3)
    expect_true(
        condition=all(url == "https://example.invalid/" for url in captures),
    )


def test_main_module_reuses_the_recorded_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An adopted demo server is not terminated afterwards.

    Args:
        monkeypatch: Pytest patching helper.

    """
    events: list[str] = []

    def reuse_server(*, path: Path) -> tuple[int, int] | None:
        """Return the recorded demo server.

        Args:
            path: Served root directory.

        Returns:
            The recorded process id and port.

        """
        _ = path
        return (4321, 8080)

    def wait_ready(*, url: str, pid: int) -> bool:
        """Report the adopted server as never ready.

        Args:
            url: Server origin.
            pid: Spawned process id.

        Returns:
            Always ``False``.

        """
        _ = url
        _ = pid
        return False

    def terminate(*, pid: int) -> None:
        """Record the terminated process id.

        Args:
            pid: Process id to terminate.

        """
        events.append(f"kill:{pid}")

    monkeypatch.setattr(target=local, name="reuse_server", value=reuse_server)
    monkeypatch.setattr(target=local, name="wait_ready", value=wait_ready)
    monkeypatch.setattr(
        target=import_module(name="exactus.packages.server.process_control"),
        name="terminate_tree",
        value=terminate,
    )
    monkeypatch.setattr(target=modules["sys"], name="argv", value=["example"])
    example: Path = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "packages"
        / "screenshot"
        / "examples"
        / "run.py"
    )
    with pytest.raises(expected_exception=RuntimeError, match="ready"):
        run_path(path_name=str(object=example), run_name="__main__")
    expect_equal(actual=events, expected=[])
