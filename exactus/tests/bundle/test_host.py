# Copyright (c) 2026
"""Host routing and package dispatch for the bundled executables."""

from __future__ import annotations

from importlib import import_module
from subprocess import CompletedProcess
from types import ModuleType
from typing import TYPE_CHECKING, cast

import pytest

from exactus import bundle
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_true,
    private_call,
)

if TYPE_CHECKING:
    from pathlib import Path
bundle_main: ModuleType = import_module(name="exactus.bundle.__main__")


def _candidates() -> tuple[tuple[str, ...], ...]:
    """Return the privately resolved host candidates.

    Returns:
        Ordered platform package parts.

    """
    return cast(
        typ="tuple[tuple[str, ...], ...]",
        val=private_call(owner=bundle, name="_host_leaf_candidates"),
    )


@pytest.mark.parametrize(
    ("operating_system", "architecture", "musl", "expected"),
    [
        ("Linux", "x86_64", False, (("linux", "glibc", "amd64"),)),
        (
            "Linux",
            "aarch64",
            True,
            (("linux", "musl", "arm64"), ("linux", "glibc", "arm64")),
        ),
        ("Darwin", "arm64", False, (("macos", "arm64"),)),
        ("Windows", "AMD64", False, (("windows", "amd64"),)),
        ("Plan9", "x86_64", False, ()),
        ("Linux", "riscv64", False, ()),
    ],
)
def test_host_leaf_candidates(
    monkeypatch: pytest.MonkeyPatch,
    operating_system: str,
    architecture: str,
    *,
    musl: bool,
    expected: tuple[tuple[str, ...], ...],
) -> None:
    """Normalize supported host names and reject unsupported combinations.

    Args:
        monkeypatch: Pytest patching helper.
        operating_system: Reported platform system.
        architecture: Reported machine architecture.
        musl: Whether Linux should prefer the musl leaf.
        expected: Expected candidate package parts.

    """
    monkeypatch.setattr(
        target=bundle,
        name="system",
        value=lambda: operating_system,
    )
    monkeypatch.setattr(
        target=bundle,
        name="machine",
        value=lambda: architecture,
    )
    monkeypatch.setattr(target=bundle, name="_host_musl", value=lambda: musl)
    expect_equal(actual=_candidates(), expected=expected)


def test_host_leaf_uses_existing_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Select the first existing candidate and derive its package name.

    Args:
        tmp_path: Temporary bundle package root.
        monkeypatch: Pytest patching helper.

    """
    package: Path = tmp_path / "bundle"
    package.mkdir()
    source: Path = package / "__init__.py"
    source.write_text(data="", encoding="utf-8")
    leaf: Path = package / "linux" / "glibc" / "amd64"
    leaf.mkdir(parents=True)
    (leaf / "__init__.py").write_text(data="", encoding="utf-8")
    monkeypatch.setattr(
        target=bundle,
        name="__file__",
        value=str(object=source),
    )
    monkeypatch.setattr(
        target=bundle,
        name="_host_leaf_candidates",
        value=lambda: (
            ("linux", "musl", "amd64"),
            ("linux", "glibc", "amd64"),
        ),
    )
    expect_equal(actual=bundle.host_leaf(), expected=leaf)
    expect_equal(
        actual=private_call(owner=bundle, name="_host_leaf_package"),
        expected="exactus.bundle.linux.glibc.amd64",
    )


def test_lazy_import_and_missing_attribute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cache a host module while translating only its own absence.

    Args:
        monkeypatch: Pytest patching helper.

    """
    loaded: ModuleType = ModuleType(name="partition_fs")
    monkeypatch.setattr(
        target=bundle,
        name="_host_leaf_package",
        value=lambda: "exactus.bundle.test.leaf",
    )

    def load(*, name: str) -> ModuleType:
        """Return the expected module for its host-qualified name.

        Args:
            name: Requested dotted module name.

        Returns:
            Loaded marker module.

        """
        expect_equal(
            actual=name,
            expected="exactus.bundle.test.leaf.partition_fs",
        )
        return loaded

    monkeypatch.setattr(target=bundle, name="import_module", value=load)
    expect_true(condition=bundle.__getattr__(name="partition_fs") is loaded)
    expect_true(condition=bundle.__dict__["partition_fs"] is loaded)
    del bundle.__dict__["partition_fs"]

    def missing(*, name: str) -> ModuleType:
        """Raise the requested module's import error.

        Args:
            name: Requested dotted module name.

        Returns:
            Never reached; the function always raises.

        Raises:
            ModuleNotFoundError: Always, for the requested module.

        """
        raise ModuleNotFoundError(name=name)

    monkeypatch.setattr(target=bundle, name="import_module", value=missing)
    with pytest.raises(
        expected_exception=AttributeError,
        match="no attribute 'absent'",
    ):
        _ = bundle.__getattr__(name="absent")


def test_bundle_main_missing_and_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject a missing launcher and forward arguments and status otherwise.

    Args:
        tmp_path: Temporary host leaf.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=bundle_main,
        name="host_leaf",
        value=lambda: None,
    )
    expect_equal(actual=bundle_main.main(), expected=1)
    leaf: Path = tmp_path / "leaf"
    leaf.mkdir()
    monkeypatch.setattr(
        target=bundle_main,
        name="host_leaf",
        value=lambda: leaf,
    )
    expect_equal(actual=bundle_main.main(), expected=1)
    launcher: Path = leaf / "__main__.py"
    launcher.write_text(data="", encoding="utf-8")
    calls: list[tuple[list[str], bool]] = []

    def run(*, args: list[str], check: bool) -> CompletedProcess[str]:
        """Capture the delegated subprocess call.

        Args:
            args: Child command.
            check: Whether nonzero status raises.

        Returns:
            Completed child marker.

        """
        calls.append((args, check))
        return CompletedProcess(args=args, returncode=7)

    monkeypatch.setattr(
        target=bundle_main,
        name="host_leaf",
        value=lambda: leaf,
    )
    monkeypatch.setattr(target=bundle_main, name="run", value=run)
    monkeypatch.setattr(
        target=bundle_main,
        name="argv",
        value=["bundle", "--flag"],
    )
    monkeypatch.setattr(target=bundle_main, name="executable", value="python")
    expect_equal(actual=bundle_main.main(), expected=7)
    expect_equal(
        actual=calls,
        expected=[(["python", str(object=leaf), "--flag"], False)],
    )


def test_dir_includes_host_modules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expose host leaf modules and packages to introspection.

    Args:
        tmp_path: Temporary host leaf.
        monkeypatch: Pytest patching helper.

    """
    (tmp_path / "partition_fs.py").write_text(data="", encoding="utf-8")
    (tmp_path / "__main__.py").write_text(data="", encoding="utf-8")
    package: Path = tmp_path / "payload"
    package.mkdir()
    (package / "__init__.py").write_text(data="", encoding="utf-8")
    monkeypatch.setattr(
        target=bundle,
        name="host_leaf",
        value=lambda: tmp_path,
    )
    names: list[str] = bundle.__dir__()
    expect_in(member="partition_fs", container=names)
    expect_in(member="payload", container=names)
