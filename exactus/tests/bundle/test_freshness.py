# Copyright (c) 2026
"""Staleness detection for the packaged ``exactus`` executable."""

from io import BytesIO, StringIO
from json import dumps
from pathlib import Path
from shutil import rmtree
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from exactus.bundle import freshness
from exactus.bundle.freshness import (
    SIGNATURE_NAME,
    bundle_signature,
    bundle_stale,
    dev_project_root,
    render_signature,
    tree_signature,
    warn_if_stale,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_none,
    expect_true,
)


def _project(*, root: Path) -> Path:
    """Create a minimal development project layout.

    Args:
        root: Temporary repository root.

    Returns:
        The bundle path ``root/bin/exactus``.

    """
    exactus: Path = root / "exactus"
    exactus.mkdir(parents=True)
    _ = (exactus / "__main__.py").write_text(
        data="print('x')\n",
        encoding="utf-8",
    )
    _ = (exactus / "tool.py").write_text(data="VALUE = 1\n", encoding="utf-8")
    package: Path = root / "exactus" / "packages" / "package"
    package.mkdir(parents=True)
    _ = (package / "build.py").write_text(data="", encoding="utf-8")
    bundle: Path = root / "bin" / "exactus"
    bundle.parent.mkdir(parents=True)
    return bundle


def _write_zipapp(*, bundle: Path, members: dict[str, str]) -> None:
    """Write a shebang-prefixed zipapp with the given members.

    Args:
        bundle: Destination executable path.
        members: Member name to text content mapping.

    """
    payload: BytesIO = BytesIO()
    with ZipFile(file=payload, mode="w", compression=ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(zinfo_or_arcname=name, data=content)
    _ = bundle.write_bytes(
        data=b"#!/usr/bin/env python3\n" + payload.getvalue(),
    )


def _stamped_zipapp(*, bundle: Path, root: Path) -> None:
    """Write a zipapp stamped with the sources under ``root/exactus``.

    Args:
        bundle: Destination executable path.
        root: Repository root whose ``exactus/`` tree is fingerprinted.

    """
    members: dict[str, str] = {
        "__main__.py": "from exactus.__main__ import main\n",
        f"exactus/{SIGNATURE_NAME}": render_signature(
            exactus_dir=root / "exactus",
        ).decode(encoding="utf-8"),
    }
    _write_zipapp(bundle=bundle, members=members)


def _stale_warning(*, bundle: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Run the staleness check against ``bundle`` and capture output.

    Args:
        bundle: Executable passed as ``sys.argv[0]``.
        monkeypatch: Pytest patching helper.

    Returns:
        Everything written to the diagnostic stream.

    """
    monkeypatch.setattr(
        target=freshness,
        name="argv",
        value=[str(object=bundle)],
    )
    stream: StringIO = StringIO()
    warn_if_stale(stream=stream)
    return stream.getvalue()


def test_dev_project_root_detects_repository(tmp_path: Path) -> None:
    """A bundle one level below the repository root resolves it.

    Args:
        tmp_path: Temporary repository root.

    """
    bundle: Path = _project(root=tmp_path)
    expect_equal(
        actual=dev_project_root(bundle=bundle),
        expected=tmp_path.resolve(),
    )


def test_dev_project_root_detects_release_layout(tmp_path: Path) -> None:
    """Platform release dirs resolve the root two levels up.

    Args:
        tmp_path: Temporary repository root.

    """
    _ = _project(root=tmp_path)
    release: Path = tmp_path / "bin" / "exactus_macos_arm64" / "exactus"
    release.parent.mkdir(parents=True)
    _ = release.write_bytes(data=b"#!x\nPK")
    expect_equal(
        actual=dev_project_root(bundle=release),
        expected=tmp_path.resolve(),
    )


def test_dev_project_root_rejects_foreign_layout(tmp_path: Path) -> None:
    """A bundle without the build markers is not a dev checkout.

    Args:
        tmp_path: Temporary directory holding the foreign layout.

    """
    bundle: Path = tmp_path / "bin" / "check"
    bundle.parent.mkdir(parents=True)
    _ = bundle.write_bytes(data=b"#!x\nPK")
    expect_none(value=dev_project_root(bundle=bundle))


def test_tree_signature_fingerprints_sources(tmp_path: Path) -> None:
    """Source files hash; caches, dotfiles, and the stamp skip.

    Args:
        tmp_path: Temporary exactus package parent.

    """
    exactus: Path = tmp_path / "exactus"
    exactus.mkdir(parents=True)
    _ = (exactus / "__main__.py").write_text(data="x = 1\n", encoding="utf-8")
    _ = (exactus / ".hidden").write_text(data="x\n", encoding="utf-8")
    _ = (exactus / SIGNATURE_NAME).write_text(data="{}\n", encoding="utf-8")
    cache: Path = exactus / "__pycache__"
    cache.mkdir()
    _ = (cache / "__main__.cpython-313.pyc").write_bytes(data=b"\x00")
    signature: dict[str, str] = tree_signature(exactus_dir=exactus)
    expect_equal(actual=sorted(signature), expected=["__main__.py"])


def test_bundle_signature_round_trip(tmp_path: Path) -> None:
    """A stamped bundle returns the exact fingerprint mapping.

    Args:
        tmp_path: Temporary repository root.

    """
    bundle: Path = _project(root=tmp_path)
    _stamped_zipapp(bundle=bundle, root=tmp_path)
    stamped: dict[str, str] | None = bundle_signature(bundle=bundle)
    expect_equal(
        actual=stamped,
        expected=tree_signature(exactus_dir=tmp_path / "exactus"),
    )


def test_tree_signature_skips_generated_reports(tmp_path: Path) -> None:
    """``EXACTUS_RESULTS`` trees never enter the fingerprint.

    Args:
        tmp_path: Temporary exactus package parent.

    """
    exactus: Path = tmp_path / "exactus"
    reports: Path = exactus / "EXACTUS_RESULTS" / "LINTS"
    reports.mkdir(parents=True)
    _ = (reports / "result.md").write_text(data="# report\n", encoding="utf-8")
    _ = (exactus / "__main__.py").write_text(data="x = 1\n", encoding="utf-8")
    expect_equal(
        actual=sorted(tree_signature(exactus_dir=exactus)),
        expected=["__main__.py"],
    )


def test_bundle_signature_absent(tmp_path: Path) -> None:
    """Bundles predating stamping report ``None``.

    Args:
        tmp_path: Temporary directory for the bundle.

    """
    bundle: Path = tmp_path / "check"
    _write_zipapp(bundle=bundle, members={"__main__.py": "x = 1\n"})
    expect_none(value=bundle_signature(bundle=bundle))


def test_warn_if_stale_fresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unchanged project produces no output.

    Args:
        tmp_path: Temporary repository root.
        monkeypatch: Pytest patching helper.

    """
    bundle: Path = _project(root=tmp_path)
    _stamped_zipapp(bundle=bundle, root=tmp_path)
    expect_equal(
        actual=_stale_warning(bundle=bundle, monkeypatch=monkeypatch),
        expected="",
    )


def test_warn_if_stale_after_source_edit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Editing a packaged source after the build warns.

    Args:
        tmp_path: Temporary repository root.
        monkeypatch: Pytest patching helper.

    """
    bundle: Path = _project(root=tmp_path)
    _stamped_zipapp(bundle=bundle, root=tmp_path)
    _ = (tmp_path / "exactus" / "tool.py").write_text(
        data="VALUE = 2\n",
        encoding="utf-8",
    )
    expect_in(
        member="exactus is outdated",
        container=_stale_warning(bundle=bundle, monkeypatch=monkeypatch),
    )


def test_warn_if_stale_after_source_addition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adding a packaged source file after the build warns.

    Args:
        tmp_path: Temporary repository root.
        monkeypatch: Pytest patching helper.

    """
    bundle: Path = _project(root=tmp_path)
    _stamped_zipapp(bundle=bundle, root=tmp_path)
    _ = (tmp_path / "exactus" / "fresh.py").write_text(
        data="x = 1\n",
        encoding="utf-8",
    )
    output: str = _stale_warning(bundle=bundle, monkeypatch=monkeypatch)
    expect_in(member="--rebuild", container=output)


def test_warn_if_stale_missing_stamp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dev-project bundle without a stamp is treated as outdated.

    Args:
        tmp_path: Temporary repository root.
        monkeypatch: Pytest patching helper.

    """
    bundle: Path = _project(root=tmp_path)
    _write_zipapp(bundle=bundle, members={"__main__.py": "x = 1\n"})
    expect_in(
        member="exactus is outdated",
        container=_stale_warning(bundle=bundle, monkeypatch=monkeypatch),
    )


def test_warn_if_stale_outside_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A distributed bundle outside the dev project stays silent.

    Args:
        tmp_path: Temporary directory outside the dev project.
        monkeypatch: Pytest patching helper.

    """
    bundle: Path = tmp_path / "tools" / "check"
    bundle.parent.mkdir(parents=True)
    _write_zipapp(bundle=bundle, members={"__main__.py": "x = 1\n"})
    expect_equal(
        actual=_stale_warning(bundle=bundle, monkeypatch=monkeypatch),
        expected="",
    )


def test_warn_if_stale_script_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-zipapp entry points are ignored.

    Args:
        tmp_path: Temporary repository root.
        monkeypatch: Pytest patching helper.

    """
    script: Path = _project(root=tmp_path)
    _ = script.write_text(data="#!x\nprint('x')\n", encoding="utf-8")
    expect_equal(
        actual=_stale_warning(bundle=script, monkeypatch=monkeypatch),
        expected="",
    )


def test_warn_if_stale_extra_payload_ignored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Source partition payloads absent from the bundle do not warn.

    Args:
        tmp_path: Temporary repository root.
        monkeypatch: Pytest patching helper.

    """
    bundle: Path = _project(root=tmp_path)
    _stamped_zipapp(bundle=bundle, root=tmp_path)
    payload: Path = (
        tmp_path
        / "exactus"
        / "bundle"
        / "linux"
        / "glibc"
        / "amd64"
        / "data"
        / "parts"
        / "fs"
        / "packs"
    )
    payload.mkdir(parents=True)
    _ = (payload / "extra.zst").write_bytes(data=b"\x00" * 8)
    expect_equal(
        actual=_stale_warning(bundle=bundle, monkeypatch=monkeypatch),
        expected="",
    )


def test_bundle_stale_ignores_staged_vendor(tmp_path: Path) -> None:
    """Staged-only ``vendor/`` shims absent from sources stay fresh.

    ``shims.generate`` writes ``exactus/vendor/`` into the staged
    package after the source copy, so the stamp legitimately records
    members the checkout never contains.

    Args:
        tmp_path: Temporary repository root.

    """
    bundle: Path = _project(root=tmp_path)
    vendor: Path = tmp_path / "exactus" / "vendor" / "_vendor" / "pkg"
    vendor.mkdir(parents=True)
    _ = (vendor / "mod.py").write_text(data="x = 1\n", encoding="utf-8")
    _stamped_zipapp(bundle=bundle, root=tmp_path)
    rmtree(path=tmp_path / "exactus" / "vendor")
    expect_true(
        condition=not bundle_stale(
            bundle=bundle,
            exactus_dir=tmp_path / "exactus",
        ),
    )


def test_bundle_stale_flags_every_drift(tmp_path: Path) -> None:
    """``bundle_stale`` reports additions, edits, and missing stamps.

    Args:
        tmp_path: Temporary repository root.

    """
    bundle: Path = _project(root=tmp_path)
    _stamped_zipapp(bundle=bundle, root=tmp_path)
    expect_true(
        condition=not bundle_stale(
            bundle=bundle,
            exactus_dir=tmp_path / "exactus",
        ),
    )
    _ = (tmp_path / "exactus" / "tool.py").write_text(
        data="VALUE = 2\n",
        encoding="utf-8",
    )
    expect_true(
        condition=bundle_stale(
            bundle=bundle,
            exactus_dir=tmp_path / "exactus",
        ),
    )
    _write_zipapp(bundle=bundle, members={"__main__.py": "x = 1\n"})
    expect_true(
        condition=bundle_stale(
            bundle=bundle,
            exactus_dir=tmp_path / "exactus",
        ),
    )


def test_render_signature_deterministic(tmp_path: Path) -> None:
    """Signature JSON is stable for identical trees.

    Args:
        tmp_path: Temporary exactus package parent.

    """
    exactus: Path = tmp_path / "exactus"
    exactus.mkdir(parents=True)
    _ = (exactus / "x.py").write_text(data="x = 1\n", encoding="utf-8")
    expect_equal(
        actual=render_signature(exactus_dir=exactus),
        expected=dumps(
            obj={"files": tree_signature(exactus_dir=exactus)},
            sort_keys=True,
        ).encode(encoding="utf-8"),
    )
    expect_true(condition=SIGNATURE_NAME.startswith("_"))
