# Copyright (c) 2026 João Lopes.
"""Tests for standalone JavaScript class-method organization."""

from pathlib import Path
from subprocess import CompletedProcess
from textwrap import dedent
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.packages.organize import JavaScriptClassMethodReorderer
from exactus.tests.common.support import private_call

if TYPE_CHECKING:
    from exactus.packages.organize.javascript import JavaScriptReorderResult


@final
class Constants:
    """Group module-level constants.

    Attributes:
        fake_espree: Grouped module constant.

    """

    fake_espree: Final[str] = dedent(
        text=(
            '\n        "use strict";\n\n        const method = (\n          so'
            "urce,\n          text,\n          kind,\n          name,\n       "
            "   isStatic = false\n        ) => {\n          const start = sour"
            "ce.indexOf(text);\n          const end = start + text.length;\n  "
            '        return {\n            type: "MethodDefinition",\n        '
            "    kind,\n            static: isStatic,\n            computed: f"
            "alse,\n            range: [start, end],\n            key: {\n    "
            '          type: "Identifier",\n              name\n            },'
            "\n            value: {\n              body: {\n                ty"
            'pe: "BlockStatement"\n              }\n            }\n          }'
            ";\n        };\n\n        exports.parse = source => {\n          c"
            'onst bodyStart = source.indexOf("{");\n          return {\n      '
            '      type: "Program",\n            comments: [],\n            ra'
            "nge: [0, source.length],\n            body: [\n              {\n "
            '               type: "ClassDeclaration",\n                range: '
            "[0, source.length],\n                body: {\n                  t"
            'ype: "ClassBody",\n                  range: [bodyStart, source.le'
            "ngth],\n                  body: [\n                    method(\n "
            '                     source,\n                      "privateWork('
            ') {}",\n                      "method",\n                      "p'
            'rivateWork"\n                    ),\n                    method('
            '\n                      source,\n                      "static cr'
            'eate() {}",\n                      "method",\n                   '
            '   "create",\n                      true\n                    ),'
            "\n                    method(\n                      source,\n   "
            '                   "set value(value) {}",\n                      '
            '"set",\n                      "value"\n                    ),\n  '
            "                  method(\n                      source,\n       "
            '               "get value() {}",\n                      "get",\n '
            '                     "value"\n                    ),\n           '
            "         method(\n                      source,\n                "
            '      "constructor() {}",\n                      "constructor",\n'
            '                      "constructor"\n                    )\n     '
            "             ].sort(\n                    (left, right) => left.r"
            "ange[0] - right.range[0]\n                  )\n                }"
            "\n              }\n            ]\n          };\n        };\n     "
            "   "
        ),
    ).removeprefix("\n")


def expect(*, condition: bool) -> None:
    """Fail when a test condition is false.

    Args:
        condition: Condition that must hold.

    Raises:
        AssertionError: If the condition does not hold.

    """
    if not condition:
        raise AssertionError


def test_javascript_reorders_and_is_idempotent(tmp_path: Path) -> None:
    """Reorder JavaScript through the standalone public API.

    Args:
        tmp_path: Temporary test directory.

    """
    module: Path = tmp_path / "node_modules" / "espree"
    module.mkdir(parents=True)
    _written: int = (module / "index.js").write_text(
        data=Constants.fake_espree,
        encoding="utf-8",
    )
    source: str = dedent(
        text=(
            "\n        class Example {\n          privateWork() {}\n          "
            "static create() {}\n          set value(value) {}\n          get "
            "value() {}\n          constructor() {}\n        }\n        "
        ),
    ).removeprefix("\n")
    path: Path = tmp_path / "example.js"
    _written = path.write_text(data=source, encoding="utf-8")
    first: JavaScriptReorderResult = JavaScriptClassMethodReorderer(
        path=path,
    ).measure()
    expect(condition=first.changed)
    expect(condition=first.metrics.classes_reordered == 1)
    expect(
        condition=first.source.index("constructor")
        < first.source.index("static create"),
    )
    expect(
        condition=first.source.index("static create")
        < first.source.index("get value"),
    )
    expect(
        condition=first.source.index("get value")
        < first.source.index("set value"),
    )
    expect(
        condition=first.source.index("set value")
        < first.source.index("privateWork"),
    )
    reorderer: JavaScriptClassMethodReorderer = JavaScriptClassMethodReorderer(
        path=path,
    )
    expect(condition=reorderer.reorder() == first.source)
    expect(condition=reorderer.write())
    second: JavaScriptReorderResult = reorderer.measure()
    expect(condition=not reorderer.write())
    expect(condition=not second.changed)
    expect(condition=second.source == first.source)


def test_javascript_reports_organizer_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Surface organizer exit failures and malformed JSON payloads.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    path: Path = tmp_path / "demo.js"
    _written: int = path.write_text(data="class Demo {}\n", encoding="utf-8")

    def fake_executable(*, name: str) -> str:
        """Pretend every executable exists on ``PATH``.

        Args:
            name: Executable name looked up on ``PATH``.

        Returns:
            A fabricated executable path.

        """
        return f"/bin/{name}"

    def fake_espree(**_rest: object) -> str:
        """Pretend the Espree parser module resolves.

        Args:
            _rest: Call arguments accepted and ignored.

        Returns:
            A fabricated Espree module path.

        """
        return "/bin/espree.cjs"

    def fail_run(
        *,
        arguments: list[str],
        **_rest: object,
    ) -> CompletedProcess[str]:
        """Return a failed organizer subprocess.

        Args:
            arguments: Command line the organizer tried to run.
            _rest: Remaining call arguments accepted and ignored.

        Returns:
            A crafted failed completed process.

        """
        return CompletedProcess(
            args=arguments,
            returncode=1,
            stdout="",
            stderr="boom",
        )

    def bad_json_run(
        *,
        arguments: list[str],
        **_rest: object,
    ) -> CompletedProcess[str]:
        """Return a successful subprocess printing invalid JSON.

        Args:
            arguments: Command line the organizer tried to run.
            _rest: Remaining call arguments accepted and ignored.

        Returns:
            A crafted completed process with non-JSON output.

        """
        return CompletedProcess(
            args=arguments,
            returncode=0,
            stdout="not json",
            stderr="",
        )

    monkeypatch.setattr(
        target=JavaScriptClassMethodReorderer,
        name="_executable",
        value=fake_executable,
    )
    monkeypatch.setattr(
        target=JavaScriptClassMethodReorderer,
        name="_resolve_espree",
        value=fake_espree,
    )
    monkeypatch.setattr(
        target=JavaScriptClassMethodReorderer,
        name="_run",
        value=fail_run,
    )
    with pytest.raises(expected_exception=RuntimeError, match="boom"):
        JavaScriptClassMethodReorderer(path=path).measure()
    monkeypatch.setattr(
        target=JavaScriptClassMethodReorderer,
        name="_run",
        value=bad_json_run,
    )
    with pytest.raises(expected_exception=TypeError, match="invalid JSON"):
        JavaScriptClassMethodReorderer(path=path).measure()


def test_javascript_resolves_global_espree_or_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fall back to global npm modules before giving up on Espree.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    espree: Path = tmp_path / "global" / "espree" / "dist" / "espree.cjs"
    espree.parent.mkdir(parents=True)
    _written: int = espree.write_text(
        data="exports.parse = source => ({});\n",
        encoding="utf-8",
    )
    path: Path = tmp_path / "demo.js"
    _written = path.write_text(data="class Demo {}\n", encoding="utf-8")

    def fake_which(*, cmd: str) -> str | None:
        """Resolve node and npm while hiding eslint.

        Args:
            cmd: Executable name looked up on ``PATH``.

        Returns:
            The fake executable path, or ``None`` when hidden.

        """
        return {"node": "/bin/node", "npm": "/bin/npm"}.get(cmd)

    def fake_run(
        *,
        arguments: list[str],
        cwd: Path,
        stdin: str | None = None,
    ) -> CompletedProcess[str]:
        """Fail node probes but answer the global npm root query.

        Args:
            arguments: Command line the organizer tried to run.
            cwd: Working directory, unused.
            stdin: Optional piped input, unused.

        Returns:
            A crafted completed process.

        """
        del cwd, stdin
        if arguments[:2] == ["/bin/npm", "root"]:
            return CompletedProcess(
                args=arguments,
                returncode=0,
                stdout=str(object=tmp_path / "global"),
                stderr="",
            )
        return CompletedProcess(
            args=arguments,
            returncode=1,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(
        target="exactus.packages.organize.javascript.which",
        name=fake_which,
    )
    monkeypatch.setattr(
        target=JavaScriptClassMethodReorderer,
        name="_run",
        value=fake_run,
    )
    resolved: object = private_call(
        owner=JavaScriptClassMethodReorderer,
        name="_resolve_espree",
        path=path,
    )
    expect(condition=resolved == str(object=espree))

    def which_node_only(*, cmd: str) -> str | None:
        """Resolve only node while hiding npm and eslint.

        Args:
            cmd: Executable name looked up on ``PATH``.

        Returns:
            The fake node path, or ``None`` for other executables.

        """
        return "/bin/node" if cmd == "node" else None

    def which_none(**_rest: object) -> str | None:
        """Hide every executable from the resolver.

        Args:
            _rest: Call arguments accepted and ignored.

        Returns:
            ``None`` for every executable.

        """
        return None

    monkeypatch.setattr(
        target="exactus.packages.organize.javascript.which",
        name=which_node_only,
    )
    with pytest.raises(expected_exception=RuntimeError, match="Espree"):
        private_call(
            owner=JavaScriptClassMethodReorderer,
            name="_resolve_espree",
            path=path,
        )
    monkeypatch.setattr(
        target="exactus.packages.organize.javascript.which",
        name=which_none,
    )
    with pytest.raises(expected_exception=RuntimeError, match="required"):
        JavaScriptClassMethodReorderer(path=path).measure()


def test_javascript_rejects_malformed_payloads() -> None:
    """Reject organizer payloads that are not complete objects."""
    with pytest.raises(expected_exception=TypeError, match="object"):
        private_call(
            owner=JavaScriptClassMethodReorderer,
            name="_result",
            payload=[],
        )
    with pytest.raises(expected_exception=TypeError, match="incomplete"):
        private_call(
            owner=JavaScriptClassMethodReorderer,
            name="_result",
            payload={"source": "x"},
        )
    with pytest.raises(expected_exception=TypeError, match="incomplete"):
        private_call(
            owner=JavaScriptClassMethodReorderer,
            name="_result",
            payload={"source": "x", "metrics": []},
        )
    with pytest.raises(expected_exception=TypeError, match="integer"):
        private_call(
            owner=JavaScriptClassMethodReorderer,
            name="_integer",
            payload={"methods_seen": True},
            key="methods_seen",
        )
    with pytest.raises(expected_exception=TypeError, match="integer"):
        private_call(
            owner=JavaScriptClassMethodReorderer,
            name="_integer",
            payload={},
            key="methods_seen",
        )
