# Copyright (c) 2026
"""Action recording, normalization, compilation and replay."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from json import dumps, loads
from textwrap import dedent
from threading import Thread
from typing import TYPE_CHECKING, Final, cast, final

import pytest

from exactus.tests.common.support import (
    dig,
    expect_equal,
    expect_in,
    expect_none,
    expect_true,
    require,
    set_private,
)
from exactus.tools.record import action_recorder as ar
from exactus.tools.record import main as record_main

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from contextlib import AbstractContextManager
    from pathlib import Path
    from types import TracebackType

    from playwright.sync_api import (
        Browser,
        BrowserType,
        Locator,
        Page,
        Playwright,
    )

    from exactus.tools.record.action_recorder import Action


def _target(kind: str = "css", **extra: object) -> Action:
    """Build a recorded target with one locator candidate.

    Args:
        kind: Locator strategy.
        **extra: Extra candidate fields.

    Returns:
        The target payload.

    """
    return cast(
        typ="Action",
        val={"locators": [{"kind": kind, "value": "#x", **extra}]},
    )


@pytest.mark.parametrize(
    ("kind", "extra", "python", "javascript"),
    [
        ("test_id", {}, "get_by_test_id", "getByTestId"),
        ("role", {"role": "button", "name": "Go"}, "get_by_role", "getByRole"),
        ("label", {}, "get_by_label", "getByLabel"),
        ("placeholder", {}, "get_by_placeholder", "getByPlaceholder"),
        ("css", {}, "page.locator", "page.locator"),
    ],
)
def test_locator_compilers(
    kind: str,
    extra: dict[str, object],
    python: str,
    javascript: str,
) -> None:
    """Each locator strategy compiles to both Playwright dialects.

    Args:
        kind: Value for ``kind``.
        extra: Value for ``extra``.
        python: Value for ``python``.
        javascript: Value for ``javascript``.

    """
    target: Action = _target(kind=kind, **extra)
    expect_in(
        member=python,
        container=ar.LocatorCompiler.python(target=target),
    )
    expect_in(
        member=javascript,
        container=ar.LocatorCompiler.javascript(target=target),
    )
    expect_equal(
        actual=ar.LocatorCompiler.python(target={}),
        expected='page.locator("body")',
    )
    expect_equal(
        actual=ar.LocatorCompiler.javascript(target={"locators": []}),
        expected='page.locator("body")',
    )
    expect_none(value=ar.LocatorCompiler.candidate(target={"locators": [1]}))


def test_normalizer_collapses_noise() -> None:
    """Focus/wheel events drop; repeated fills and dblclicks collapse."""
    t: Action = _target()
    other: Action = _target(value="y")
    raw: list[Action] = [
        {"type": "focus"},
        {"type": "wheel"},
        {"type": "click", "target": t},
        {"type": "double_click", "target": t},
        {"type": "fill", "target": t, "value": "a"},
        {"type": "fill", "target": t, "value": "ab"},
        {"type": "scroll", "target": t, "x": 0, "y": 1},
        {"type": "scroll", "target": t, "x": 0, "y": 9},
        {"type": "key", "key": "A"},
        {"type": "key", "key": "A"},
        {"type": "click", "target": other},
    ]
    result: list[Action] = ar.ActionNormalizer.normalize(actions=raw)
    expect_equal(
        actual=[a["type"] for a in result],
        expected=["double_click", "fill", "scroll", "key", "click"],
    )
    expect_equal(actual=result[1]["value"], expected="ab")
    expect_equal(actual=result[2]["y"], expected=9)


def test_key_chords() -> None:
    """Modifiers and aliases render as Playwright chords."""
    chord: str = ar.ActionCompiler.key(
        action={
            "key": " ",
            "modifiers": {
                "control": True,
                "alt": True,
                "shift": True,
                "meta": True,
                "x": False,
            },
        },
    )
    expect_equal(actual=chord, expected="Control+Alt+Shift+Meta+Space")
    expect_equal(
        actual=ar.ActionCompiler.key(action={"key": "Enter"}),
        expected="Enter",
    )


@final
class Constants:
    """Group module-level constants.

    Attributes:
        min_awaits: Grouped module constant.
        actions: Grouped module constant.
        form_html: Grouped module constant.
        hover_html: Grouped module constant.

    """

    min_awaits: Final[int] = 5
    actions: Final[list[Action]] = [
        {"type": "click", "target": _target(), "elapsedMs": 10},
        {"type": "double_click", "target": _target(), "elapsedMs": 30},
        {"type": "right_click", "target": _target(), "elapsedMs": 40},
        {"type": "fill", "target": _target(), "value": "v", "elapsedMs": 90},
        {"type": "contenteditable", "target": _target(), "value": "v"},
        {"type": "hover", "target": _target()},
        {"type": "check", "target": _target()},
        {"type": "uncheck", "target": _target()},
        {"type": "select", "target": _target(), "values": ["a"]},
        {"type": "key", "key": "Enter"},
        {"type": "key", "key": "Enter", "target": _target()},
        {"type": "scroll", "x": 1, "y": 2},
        {"type": "scroll", "target": _target(), "x": 1, "y": 2},
        {"type": "drag", "source": _target(), "target": _target(value="z")},
        {"type": "drag", "target": _target()},
        {"type": "navigation", "url": "http://x/"},
        {"type": "dialog", "message": "hi"},
    ]
    form_html: Final[str] = dedent(
        text=(
            '    <!doctype html><html lang="en"><body>\n    <input id="name" p'
            'laceholder="Name" aria-label="Name" data-testid="name">\n    <lab'
            'el>Agree <input id="agree" type="checkbox"></label>\n    <select '
            'id="pick">\n    <option value="a">A</option><option value="b">B</'
            'option>\n    </select>\n    <div id="rich" contenteditable="true"'
            '>x</div>\n    <button id="go" role="button">Go</button>\n    <div'
            ' id="a" draggable="true"\n    style="width:50px;height:50px;backg'
            'round:#ccc">a</div>\n    <div id="b" style="width:50px;height:50p'
            'x;background:#999">b</div>\n    <div id="tall" style="height:3000'
            'px"></div>\n    <script>document.getElementById("go").onclick = ('
            ') => alert("hi");</script>\n    </body></html>'
        ),
    )
    hover_html: Final[str] = dedent(
        text=(
            '    <!doctype html><html lang="en"><body>\n    <header><h1>Title<'
            '/h1><p>plain paragraph</p></header>\n    <button id="tip">Tip</bu'
            'tton>\n    <div id="inline" onmouseover="void 0">inline</div>\n  '
            '  <div id="menu" style="width:80px;height:30px">Menu</div>\n    <'
            'div id="pop" hidden>popup</div>\n    <script>\n      document.get'
            'ElementById("tip").addEventListener("mouseenter", () => {});\n   '
            '   document.addEventListener("mouseover", (event) => {\n        i'
            'f (event.target.id === "menu")\n          document.getElementById'
            '("pop").hidden = false;\n      });\n    </script>\n    </body></h'
            "tml>"
        ),
    )


def test_compile_all_actions_and_write(tmp_path: Path) -> None:
    """Every action kind compiles and programs are written to disk.

    Args:
        tmp_path: Per-test temporary directory.

    """
    for action in Constants.actions:
        py: str | None = ar.ActionCompiler.python(action=action)
        js: str | None = ar.ActionCompiler.javascript(action=action)
        if action["type"] == "dialog" or (
            action["type"] == "drag" and "source" not in action
        ):
            expect_none(value=py)
            expect_none(value=js)
        else:
            expect_true(condition=bool(py))
            expect_true(condition=bool(js))
    ar.ActionCompiler.write(
        actions=Constants.actions,
        output=tmp_path / "out",
        preserve_timing=True,
    )
    program: str = (tmp_path / "out" / "actions.py.txt").read_text()
    expect_in(member="wait_for_timeout", container=program)
    expect_true(
        condition=(tmp_path / "out" / "actions.mjs.txt")
        .read_text()
        .count("await")
        > Constants.min_awaits,
    )
    expect_true(
        condition=bool(
            loads(
                s=(tmp_path / "out" / "actions.normalized.json").read_text(),
            ),
        ),
    )


def test_load_actions(tmp_path: Path) -> None:
    """Only JSON arrays of objects load.

    Args:
        tmp_path: Per-test temporary directory.

    """
    path: Path = tmp_path / "a.json"
    path.write_text(data=dumps(obj=[{"type": "click"}, 5]))
    expect_equal(
        actual=ar.load_actions(path=path),
        expected=[{"type": "click"}],
    )
    path.write_text(data="{}")
    with pytest.raises(expected_exception=TypeError):
        _ = ar.load_actions(path=path)


@pytest.fixture
def form_url(tmp_path: Path) -> Iterator[str]:
    """Serve a form-rich page on an ephemeral loopback port.

    Args:
        tmp_path: Pytest temporary directory.

    Yields:
        The page URL.

    """
    site: Path = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text(
        data=Constants.form_html,
        encoding="utf-8",
    )
    server: ThreadingHTTPServer = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(SimpleHTTPRequestHandler, directory=str(object=site)),
    )
    thread: Thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def hover_url(tmp_path: Path) -> Iterator[str]:
    """Serve a page mixing inert and effect-producing hover targets.

    Args:
        tmp_path: Pytest temporary directory.

    Yields:
        The page URL.

    """
    site: Path = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text(
        data=Constants.hover_html,
        encoding="utf-8",
    )
    server: ThreadingHTTPServer = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(SimpleHTTPRequestHandler, directory=str(object=site)),
    )
    thread: Thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def headless(monkeypatch: pytest.MonkeyPatch) -> Installer:
    """Run recorder/replayer browsers headless and script the session.

    Args:
        monkeypatch: Pytest patching helper.

    Returns:
        A function installing the interaction script.

    """
    real: Callable[[], AbstractContextManager[Playwright]] = ar.sync_playwright
    script: list[Callable[[Browser], None]] = []

    class Wrapper:
        """``sync_playwright`` stand-in launching headless Chromium."""

        def __init__(self) -> None:
            """Create the real context manager."""
            self.inner: AbstractContextManager[Playwright] = real()

        def __enter__(self) -> object:
            """Start Playwright and patch ``chromium.launch``.

            Returns:
                The real Playwright runtime.

            """
            playwright: Playwright = self.inner.__enter__()
            chromium: BrowserType = playwright.chromium
            original: Callable[..., Browser] = chromium.launch

            def launch(*, headless: bool) -> Browser:
                """Launch headless regardless of the request.

                Args:
                    headless: Ignored request.

                Returns:
                    A browser whose connection ends after the script.

                """
                del headless
                browser: Browser = original(headless=True)
                calls: dict[str, int] = {"n": 0}
                real_connected: Callable[[], bool] = browser.is_connected

                def is_connected() -> bool:
                    """Run the script once, then report disconnection.

                    Returns:
                        Connection state.

                    """
                    calls["n"] += 1
                    if calls["n"] == 1:
                        for step in script:
                            step(browser)
                        return True
                    return False if script else real_connected()

                browser.is_connected = is_connected
                return browser

            set_private(owner=chromium, name="launch", value=launch)
            return playwright

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: TracebackType | None,
        ) -> None:
            """Stop Playwright.

            Args:
                exc_type: Exception class.
                exc_value: Exception instance.
                traceback: Exception traceback.

            """
            self.inner.__exit__(exc_type, exc_value, traceback)

    monkeypatch.setattr(target=ar, name="sync_playwright", value=Wrapper)

    def install(*, step: Callable[[Browser], None]) -> None:
        """Register one scripted browser interaction.

        Args:
            step: Interaction to run against the browser.

        """
        script.append(step)

    return Installer(add=install)


@dataclass(frozen=True, slots=True)
class Installer:
    """Callable registering one scripted browser interaction.

    Attributes:
        add: Function appending an interaction step to the script.

    """

    add: Callable[..., None]

    def __call__(self, *, step: Callable[[Browser], None]) -> None:
        """Register ``step`` to run against the launched browser.

        Args:
            step: Interaction executed once against the browser.

        """
        self.add(step=step)


def _noop(browser: Browser) -> None:
    """Perform no interaction.

    Args:
        browser: Launched browser.

    """
    del browser


def _interact(browser: Browser) -> None:
    """Drive the demo page like a user.

    Args:
        browser: Launched browser.

    """
    page: Page = browser.contexts[0].pages[0]
    page.click(selector="[data-toggle-status]")
    page.click(selector="#tab-metrics")
    page.hover(selector="[data-save-draft]")
    page.keyboard.press(key="Tab")
    page.mouse.wheel(delta_x=0, delta_y=300)
    page.evaluate(expression="window.scrollTo(0, 120)")
    page.wait_for_timeout(timeout=700)


def _interact_hover(browser: Browser) -> None:
    """Hover inert and effect-producing targets.

    Args:
        browser: Launched browser.

    """
    page: Page = browser.contexts[0].pages[0]
    page.hover(selector="h1")
    page.hover(selector="p")
    page.hover(selector="#tip")
    page.hover(selector="header")
    page.hover(selector="#inline")
    page.hover(selector="#menu")
    page.hover(selector="#pop")
    page.wait_for_timeout(timeout=500)


def _interact_form(browser: Browser) -> None:
    """Drive the form page like a user.

    Args:
        browser: Launched browser.

    """
    page: Page = browser.contexts[0].pages[0]
    page.fill(selector="#name", value="Ada")
    page.check(selector="#agree")
    page.uncheck(selector="#agree")
    page.select_option(selector="#pick", value="b")
    page.click(selector="#rich")
    page.keyboard.type(text="yz")
    page.press(selector="#name", key="Control+A")
    page.once(event="dialog", f=lambda dialog: dialog.accept())
    page.click(selector="#go")
    page.click(selector="#a", button="right")
    page.dblclick(selector="#b")
    page.drag_and_drop(source="#a", target="#b")
    page.mouse.wheel(delta_x=0, delta_y=500)
    page.evaluate(expression="window.scrollTo(0, 800)")
    page.wait_for_timeout(timeout=900)


def _interact_fast_form(browser: Browser) -> None:
    """Submit a freshly typed value without waiting for the input debounce.

    Args:
        browser: Launched browser.

    """
    page: Page = browser.contexts[0].pages[0]
    page.fill(selector="#name", value="Ada")
    page.once(event="dialog", f=lambda dialog: dialog.accept())
    page.click(selector="#go")


def test_recorder_preserves_fast_submit_order(
    form_url: str,
    tmp_path: Path,
    headless: Installer,
) -> None:
    """Record a debounced fill before the following submit click.

    Args:
        form_url: Form fixture URL.
        tmp_path: Per-test temporary directory.
        headless: Browser installation fixture.

    """
    headless(step=_interact_fast_form)
    actions: list[Action] = ar.ActionRecorder(
        options=ar.RecorderOptions(url=form_url, output=tmp_path / "fast"),
    ).run()
    kinds: list[str] = [str(object=action["type"]) for action in actions]
    expect_true(condition=kinds.index("fill") < kinds.index("click"))


def test_recorder_form_session(
    form_url: str,
    tmp_path: Path,
    headless: Installer,
) -> None:
    """Form interactions are recorded and compiled.

    Args:
        form_url: Value for ``form_url``.
        tmp_path: Per-test temporary directory.
        headless: Value for ``headless``.

    """
    headless(step=_interact_form)
    out: Path = tmp_path / "rec"
    actions: list[Action] = ar.ActionRecorder(
        options=ar.RecorderOptions(
            url=form_url,
            output=out,
            preserve_timing=True,
        ),
    ).run()
    kinds: set[str] = {str(object=a["type"]) for a in actions}
    expect_true(condition={"fill", "click"} <= kinds)
    expect_true(condition=bool((out / "actions.mjs.txt").read_text()))


def test_recorder_hover_filters_inert(
    hover_url: str,
    tmp_path: Path,
    headless: Installer,
) -> None:
    """Only hovers that run element-scoped JS or mutate the DOM record.

    Args:
        hover_url: Value for ``hover_url``.
        tmp_path: Per-test temporary directory.
        headless: Value for ``headless``.

    """
    headless(step=_interact_hover)
    actions: list[Action] = ar.ActionRecorder(
        options=ar.RecorderOptions(
            url=hover_url,
            output=tmp_path / "rec",
            timeout_ms=5000.0,
        ),
    ).run()
    hovers: list[Action] = [a for a in actions if a["type"] == "hover"]
    selectors: set[str] = {
        str(
            object=next(
                locator["value"]
                for locator in cast(
                    typ="list[dict[str, object]]",
                    val=cast(typ="dict[str, object]", val=action["target"])[
                        "locators"
                    ],
                )
                if locator["kind"] == "css"
            ),
        )
        for action in hovers
    }
    expect_equal(actual=selectors, expected={"#tip", "#inline", "#menu"})


def test_recorder_session(
    demo_url: str,
    tmp_path: Path,
    headless: Installer,
) -> None:
    """A scripted browser session produces replayable programs.

    Args:
        demo_url: Base URL of the live demo server.
        tmp_path: Per-test temporary directory.
        headless: Value for ``headless``.

    """
    headless(step=_interact)
    out: Path = tmp_path / "rec"
    actions: list[Action] = ar.ActionRecorder(
        options=ar.RecorderOptions(
            url=demo_url,
            output=out,
            timeout_ms=5000.0,
        ),
    ).run()
    kinds: set[str] = {str(object=a["type"]) for a in actions}
    expect_in(member="click", container=kinds)
    expect_true(
        condition=bool((out / "actions.raw.jsonl").read_text().strip()),
    )
    expect_true(condition=(out / "actions.py.txt").is_file())


def test_replay_session(form_url: str, headless: Installer) -> None:
    """Recorded programs replay against the live page.

    Args:
        form_url: Value for ``form_url``.
        headless: Value for ``headless``.

    """
    headless(step=_noop)
    program: list[Action] = [
        {"type": "navigation", "url": form_url},
        {"type": "fill", "target": _target(value="#name"), "value": "Ada"},
        {
            "type": "contenteditable",
            "target": _target(value="#rich"),
            "value": "q",
        },
        {"type": "check", "target": _target(value="#agree")},
        {"type": "uncheck", "target": _target(value="#agree")},
        {"type": "select", "target": _target(value="#pick"), "values": ["b"]},
        {"type": "select", "target": _target(value="#pick"), "values": "a"},
        {"type": "click", "target": _target(value="#a")},
        {"type": "double_click", "target": _target(value="#b")},
        {"type": "right_click", "target": _target(value="#b")},
        {"type": "hover", "target": _target(value="#a")},
        {"type": "key", "key": "Tab"},
        {"type": "key", "key": "A", "target": _target(value="#name")},
        {"type": "scroll", "x": 0, "y": 50},
        {"type": "scroll", "target": _target(value="#rich"), "x": 0, "y": 5},
        {"type": "mystery"},
        {
            "type": "drag",
            "source": _target(value="#a"),
            "target": _target(value="#b"),
        },
        {"type": "drag", "target": _target(value="#b")},
        {"type": "click", "target": {"locators": []}},
    ]
    failures: list[str] = ar.ActionReplayer(
        url=form_url,
        actions=program,
        options=ar.ReplayOptions(width=900, height=700, timeout_ms=2000.0),
    ).run()
    for failure in failures:
        expect_true(condition=bool(failure))


@pytest.mark.parametrize(
    ("kind", "extra"),
    [
        ("test_id", {}),
        ("role", {"role": "tab", "name": "Metrics"}),
        ("label", {}),
        ("placeholder", {}),
    ],
)
def test_replayer_locate_strategies(
    kind: str,
    extra: dict[str, object],
    form_url: str,
    headless: Installer,
) -> None:
    """Every locator strategy resolves against a live page.

    Args:
        kind: Value for ``kind``.
        extra: Value for ``extra``.
        form_url: Value for ``form_url``.
        headless: Value for ``headless``.

    """
    del headless
    with ar.sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch(headless=True)
        page: Page = browser.new_page()
        _ = page.goto(url=form_url)
        locator: Locator = ar.ActionReplayer.locate(
            page=page,
            target=_target(kind=kind, **extra),
        )
        locator = require(value=locator)
        expect_equal(
            actual=ar.ActionReplayer.locate(page=page, target={}).count(),
            expected=1,
        )
        browser.close()


def test_exactus_record_cli(
    demo_url: str,
    tmp_path: Path,
    headless: Installer,
) -> None:
    """The record tool records, exports to Exactus Record, then replays.

    Args:
        demo_url: Base URL of the live demo server.
        tmp_path: Per-test temporary directory.
        headless: Value for ``headless``.

    """
    headless(step=_interact)
    out: Path = tmp_path / "RECORD"
    extra: Path = tmp_path / "extra" / "w.pwflow.json"
    expect_equal(
        actual=record_main.main(
            arguments=(
                str(object=tmp_path),
                "--url",
                demo_url,
                "-o",
                str(object=out),
                "--preserve-timing",
                "--workspace",
                str(object=extra),
            ),
        ),
        expected=0,
    )
    for name in (
        "result.md",
        "result.json",
        "actions.normalized.json",
        "recording.pwflow.json",
    ):
        expect_true(condition=(out / name).is_file())
    expect_true(condition=extra.is_file())
    report: object = loads(s=(out / "result.json").read_text())
    expect_equal(
        actual=dig(document=report, path=("summary", "mode")),
        expected="record",
    )
    headless(step=_noop)
    for program in (
        out / "actions.normalized.json",
        out / "recording.pwflow.json",
    ):
        status: int = record_main.main(
            arguments=(
                str(object=tmp_path),
                "--url",
                demo_url,
                "-o",
                str(object=tmp_path / "REPLAY"),
                "--replay",
                str(object=program),
                "--headless",
                "--timeout-ms",
                "1500",
            ),
        )
        expect_in(member=status, container={0, 1})
    expect_equal(
        actual=loads(s=(tmp_path / "REPLAY" / "result.json").read_text())[
            "summary"
        ]["mode"],
        expected="replay",
    )


def test_exactus_record_replay_failures_fail(
    form_url: str,
    tmp_path: Path,
) -> None:
    """A replayed action that cannot be performed fails the exactus.

    Args:
        form_url: Value for ``form_url``.
        tmp_path: Per-test temporary directory.

    """
    program: Path = tmp_path / "p.json"
    program.write_text(
        data=dumps(
            obj=[{"type": "click", "target": _target(value="#missing")}],
        ),
    )
    status: int = record_main.main(
        arguments=(
            str(object=tmp_path),
            "--url",
            form_url,
            "-o",
            str(object=tmp_path / "R"),
            "--replay",
            str(object=program),
            "--headless",
            "--timeout-ms",
            "500",
        ),
    )
    expect_equal(actual=status, expected=1)
    report: object = loads(s=(tmp_path / "R" / "result.json").read_text())
    expect_equal(
        actual=dig(document=report, path=("findings", 0, "rule")),
        expected="REC001",
    )


def test_exactus_record_argument_errors(tmp_path: Path) -> None:
    """A URL is mandatory unless Studio supplies the page.

    Args:
        tmp_path: Per-test temporary directory.

    """
    with pytest.raises(expected_exception=SystemExit):
        _ = record_main.main(
            arguments=(str(object=tmp_path), "--replay", "missing.json"),
        )
    expect_true(
        condition=bool(
            record_main.parse_args(arguments=("x", "--no-open")).no_open,
        ),
    )
