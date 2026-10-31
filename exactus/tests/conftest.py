# Copyright (c) 2026
"""Shared pytest fixtures for the toolkit tests."""

from __future__ import annotations

from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import import_module
from json import dumps
from os import environ
from pathlib import Path
from signal import Handlers, Signals, getsignal, signal
from textwrap import dedent
from threading import Event, Thread
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.__main__ import Check
from exactus.tests.common.support import private, require_type, set_private

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from types import FrameType, ModuleType
type SignalHandler = (
    Callable[[int, FrameType | None], object] | Handlers | int | None
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.
        excludes: Grouped module constant.
        signals: Grouped module constant.

    """

    root: Final[Path] = Path(__file__).resolve().parents[2]
    excludes: Final[tuple[str, ...]] = (
        "EXACTUS_RESULTS/**",
        "build/**",
        "exec/**",
        "packages/**",
        "exactus/record/**",
        "demo/**",
    )
    signals: Final[tuple[Signals, ...]] = tuple(
        Signals[name]
        for name in ("SIGHUP", "SIGINT", "SIGTERM", "SIGQUIT", "SIGTSTP")
        if name in Signals.__members__
    )


def _no_reexec(_cls: type[Check]) -> None:
    """Replace ``Check.venv_reexec`` so tests never re-exec the process.

    Args:
        _cls: Orchestrator class the replacement is bound to.

    """


@pytest.fixture
def repo_args() -> tuple[str, ...]:
    """Return the root plus exclusion arguments for self-exactuss.

    Returns:
        Positional root and ``--exclude`` options.

    """
    return (
        str(object=Constants.root),
        *(arg for item in Constants.excludes for arg in ("--exclude", item)),
    )


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a small Python/JS/CSS/HTML project with known defects.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Root of the generated project.

    """
    root: Path = tmp_path / "proj"
    (root / "pkg").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "pkg" / "__init__.py").write_text(data="", encoding="utf-8")
    (root / "pkg" / "mod.py").write_text(
        data=(
            dedent(
                text=(
                    "    import os\n    from dataclasses import dataclass"
                    "\n    \n    \n    @dataclass\n    class Box:\n       "
                    " size: int = 0\n    \n    \n    def add(a, b):\n     "
                    "   return a + b\n    \n    \n    def use():\n        "
                    "x = add(1, 2)\n        return Box(3), x, os.sep\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    (root / "tests" / "test_mod.py").write_text(
        data=(
            dedent(
                text=(
                    "    from pkg.mod import add\n    \n    \n    def test"
                    "_add():\n        assert add(1, 2) == 3\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    (root / "app.js").write_text(
        data="function f(a){var x=a;return x}\nconsole.log(f(1))\n",
        encoding="utf-8",
    )
    (root / "app.css").write_text(data="a{color:red}\n", encoding="utf-8")
    (root / "index.html").write_text(
        data="<html><body><img src='a.png'></body></html>\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(data="# proj\n", encoding="utf-8")
    return root


@pytest.fixture
def defect_project(tmp_path: Path) -> Path:
    """Create a project packed with lint-worthy Python, JS, CSS and HTML.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Root of the generated project.

    """
    root: Path = tmp_path / "defects"
    (root / "src").mkdir(parents=True)
    (root / "src" / "bad.py").write_text(
        data=(
            dedent(
                text=(
                    "    import os, sys\n    import json\n    from typing "
                    "import *\n    CACHE = []\n    \n    \n    def f(a, b="
                    "[], *args, **kw):\n    \tglobal CACHE\n    \ttry:\n  "
                    "  \t\tprint(a == None)  \n    \texcept:\n    \t\tpass"
                    "\n    \treturn eval('1')\n    \n    \n    class K:\n "
                    "       def m(self, x):\n            return lambda y: "
                    "x+y\n    \n    \n    def g(x: int) -> int:\n        i"
                    "f x:\n            return 1\n        else:\n          "
                    "  return 2\n    async def h():\n        return [i for"
                    " i in range(3) if i if i]\n    x = 1; y = 2\n    asse"
                    "rt (x, 'msg')\n    open('f').read()\n    def very_lon"
                    "g_function_name_for_testing(argument_one, argument_tw"
                    "o, argument_three, argument_four):\n        pass\n   "
                    " "
                ),
            )
        ),
        encoding="utf-8",
    )
    (root / "src" / "broken.py").write_text(data="def (:\n", encoding="utf-8")
    (root / "web.js").write_text(
        data=(
            dedent(
                text=(
                    "    var a = 1\n    if (a == '1') { eval('x') }\n    f"
                    "unction f(a, b) { return a + b }\n    const unused = "
                    "3;\n    console.log(f(1))\n    document.write('x');\n"
                    "    let q = [1,2];\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    (root / "web.mjs").write_text(
        data=(
            dedent(
                text=(
                    "    export const a = () => { debugger; };\n    export"
                    " default function () { return undefined == null; }\n "
                    "   "
                ),
            )
        ),
        encoding="utf-8",
    )
    (root / "style.css").write_text(
        data=(
            dedent(
                text=(
                    "    a { color: #FFF; color: red !important; }\n    b "
                    "{}\n    .x{margin:0px;padding:0 0 0 0}\n    @media (m"
                    "ax-width:100px){c{display:none}}\n    d { colr: red; "
                    "background: url(  x.png ) }\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    (root / "page.html").write_text(
        data=(
            dedent(
                text=(
                    "    <html><head><title></title></head><body>\n    <im"
                    "g src=a.png><div id=a></div><div id=a></div>\n    <a "
                    "href=#>x</a><p style='color:red'>t</p>\n    <button o"
                    "nclick='go()'>b</button>\n    <input type=text><scrip"
                    "t>var z=1</script></body></html>\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    return root


@pytest.fixture
def isolated_check(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[None]:
    """Restore every piece of global state the orchestrator mutates.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    Yields:
        Nothing; state is restored afterwards.

    """
    handlers: dict[Signals, SignalHandler] = {
        sig: getsignal(signalnum=sig) for sig in Constants.signals
    }
    child: object = private(owner=Check, name="_child")
    saved: tuple[Path, Path] = (Check.root, Check.exactus_root)
    monkeypatch.chdir(path=tmp_path)
    monkeypatch.setattr(
        target=Check,
        name="venv_reexec",
        value=classmethod(_no_reexec),
    )
    monkeypatch.setenv(name="EXACTUS_ROOT", value=str(object=tmp_path))
    monkeypatch.setenv(name="EXACTUS_PROJECT_PYTHON", value="")
    yield
    Check.root, Check.exactus_root = saved
    set_private(owner=Check, name="_child", value=child)
    require_type(
        value=private(owner=Check, name="_interrupt"),
        kind=Event,
    ).clear()
    for sig, handler in handlers.items():
        _ = signal(signalnum=sig, handler=handler)
    _ = environ.pop("EXACTUS_ROOT", None)


@pytest.fixture
def demo_url() -> Iterator[str]:
    """Serve the demo static site on an ephemeral loopback port.

    Yields:
        The base URL of the running server.

    """
    module: ModuleType = import_module(name="demo.server")
    constants: type = module.Constants
    handler: type = module.DemoHandler
    server: ThreadingHTTPServer = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(
            handler,
            directory=str(object=getattr(constants, "static_root", "")),
        ),
    )
    thread: Thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class _EchoHandler(BaseHTTPRequestHandler):
    """Answer every GET with a JSON body echoing the Cookie header."""

    def do_get(self) -> None:
        """Write the echo response."""
        body: bytes = dumps(
            obj={"ok": True, "cookie": self.headers.get("Cookie", "")},
        ).encode(encoding="utf-8")
        self.send_response(code=200)
        self.send_header(keyword="Content-Type", value="application/json")
        self.send_header(keyword="Content-Length", value=str(object=len(body)))
        self.end_headers()
        _ = self.wfile.write(body)

    def __getattr__(self, name: str) -> object:
        """Resolve the ``do_GET`` dispatch name to ``do_get``.

        Args:
            name: Attribute being resolved.

        Returns:
            The GET handler for ``do_GET``.

        Raises:
            AttributeError: For every other missing attribute.

        """
        if name == "do_GET":
            return self.do_get
        raise AttributeError(name)


@pytest.fixture
def echo_url() -> Iterator[str]:
    """Serve the echo handler on a free loopback port.

    Yields:
        Base URL of the running server.

    """
    server: ThreadingHTTPServer = ThreadingHTTPServer(
        server_address=("127.0.0.1", 0),
        RequestHandlerClass=_EchoHandler,
    )
    thread: Thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()
