"""Tests for Exactus executable staging."""

from argparse import ArgumentParser
from datetime import UTC, datetime
from email.message import Message
from hashlib import sha256
from importlib import import_module
from io import BytesIO
from json import dumps, loads
from pathlib import Path
from shutil import copytree as shutil_copytree
from shutil import rmtree
from sys import platform
from textwrap import dedent
from time import monotonic
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, NoReturn, cast
from urllib.error import HTTPError, URLError
from zipfile import ZipFile, ZipInfo

import pytest

from exactus.packages.package.build import Constants, build_check
from exactus.packages.package.bundle import (
    BrowserArchive,
    BuildOptions,
    BuildTarget,
    BuildToolsDefaults,
    BundleBuilder,
    BundleConfig,
    BundleFileConfig,
    Catalog,
    ComponentSpec,
    FetchError,
    FetchOptions,
    Json,
    PartitionStore,
    bundle_file_config,
    fetch,
    load_catalog,
    resolve_components,
    size_label,
)
from exactus.packages.package.bundle import Constants as _GroupFinalConstants
from exactus.packages.package.partition_fs import FormatError
from exactus.packages.package.partition_launcher import (
    Runtime,
    cache_lock,
    closure,
    main,
)
from exactus.packages.package.readmes import (
    directory_readme,
    write_directory_readmes,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_true,
    fail,
    private,
    private_as,
    private_call,
    private_result,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def test_stage_package_keeps_complete_package_tree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Every Exactus package is available to the built executable.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    source: Path = tmp_path / "source" / "exactus"
    packages: Path = source / "packages"
    tree: Path = packages / "tree"
    tree.mkdir(parents=True)
    _ = (source / "__init__.py").write_text(data="", encoding="utf-8")
    _ = (packages / "__init__.py").write_text(data="", encoding="utf-8")
    _ = (tree / "__init__.py").write_text(data="", encoding="utf-8")

    def no_stage_zstd(*, staging: Path) -> None:
        """Skip native payload staging for the synthetic package tree.

        Args:
            staging: Unused synthetic staging root.

        """
        del staging

    def no_validate_packs(*, staging: Path) -> None:
        """Skip bundle-pack validation for the synthetic package tree.

        Args:
            staging: Unused synthetic staging root.

        """
        del staging

    def no_write_content(*, root: Path) -> None:
        """Create the empty synthetic bundle namespace.

        Args:
            root: Synthetic bundle namespace root.

        """
        root.mkdir(parents=True, exist_ok=True)

    def fake_signature(*, exactus_dir: Path) -> bytes:
        """Return a deterministic signature for the synthetic package.

        Args:
            exactus_dir: Unused staged Exactus package root.

        Returns:
            Deterministic placeholder signature.

        """
        del exactus_dir
        return b"signature"

    package_build: ModuleType = import_module(
        name="exactus.packages.package.build",
    )
    monkeypatch.setattr(target=Constants, name="package", value=source)
    monkeypatch.setattr(
        target=package_build,
        name="_stage_zstd_portable",
        value=no_stage_zstd,
    )
    monkeypatch.setattr(
        target=package_build,
        name="_validate_staged_bundle_packs",
        value=no_validate_packs,
    )
    monkeypatch.setattr(
        target=package_build,
        name="write_content",
        value=no_write_content,
    )
    monkeypatch.setattr(
        target=package_build,
        name="render_signature",
        value=fake_signature,
    )
    executable: Path = tmp_path / "bin" / "exactus"
    build_check(target=executable)
    with ZipFile(file=executable) as archive:
        names: set[str] = set(archive.namelist())
    if "exactus/packages/tree/__init__.py" not in names:
        pytest.fail(reason="Complete package tree was not staged")


@pytest.mark.parametrize(
    ("name", "description"),
    [
        ("data", "Bundle metadata"),
        ("parts", "Payload filesystem"),
        ("fs", "Filesystem catalog"),
        ("catalogs", "Retained catalogs"),
        ("packs", "Content-addressed compressed packs"),
        ("ab", "Immutable compressed payload packs"),
    ],
)
def test_bundle_directory_descriptions(name: str, description: str) -> None:
    """Describe each asset directory and unknown hash-prefix leaves.

    Args:
        name: Generated directory basename.
        description: Expected purpose of its payload.

    """
    text: str = directory_readme(name=name)
    expect_in(member=f"# `{name}/`", container=text)
    expect_in(member=description, container=text)
    expect_in(member="preserve existing packs and catalogs", container=text)


def test_bundle_readmes_recurse_without_touching_private_or_linked_trees(
    tmp_path: Path,
) -> None:
    """Generate public inventories without following symlinks or caches.

    Args:
        tmp_path: Isolated asset tree.

    """
    root: Path = tmp_path / "data"
    prefix: Path = root / "parts" / "fs" / "packs" / "ab"
    prefix.mkdir(parents=True)
    _ = (root / "parts" / "fs" / "catalog.json").write_text(
        data="{}",
        encoding="utf-8",
    )
    _ = (prefix / "payload.zst").write_bytes(data=b"payload")
    private: Path
    for private in (root / ".cache", root / "__pycache__"):
        private.mkdir()
    external: Path = tmp_path / "external"
    external.mkdir()
    (root / "linked").symlink_to(target=external, target_is_directory=True)
    write_directory_readmes(root=root)
    expect_true(condition=(prefix / "README.md").is_file())
    expect_in(
        member="payload.zst",
        container=(prefix / "README.md").read_text(encoding="utf-8"),
    )
    expect_in(
        member="Filesystem catalog",
        container=(root / "parts" / "fs" / "README.md").read_text(
            encoding="utf-8",
        ),
    )
    expect_equal(actual=tuple(external.iterdir()), expected=())
    for private in (root / ".cache", root / "__pycache__"):
        expect_equal(actual=tuple(private.iterdir()), expected=())
    before: str = (prefix / "README.md").read_text(encoding="utf-8")
    write_directory_readmes(root=root)
    expect_equal(
        actual=(prefix / "README.md").read_text(encoding="utf-8"),
        expected=before,
    )
    write_directory_readmes(root=tmp_path / "missing")
    write_directory_readmes(root=prefix / "payload.zst")


def test_bundle_readmes_preserve_existing_prose_and_detect_catalogs(
    tmp_path: Path,
) -> None:
    """Keep authored prose while generating inventories and catalog labels.

    Args:
        tmp_path: Isolated asset tree.

    """
    _ = (tmp_path / "README.md").write_text(
        data="# Custom assets\n\nKeep this prose.\n",
        encoding="utf-8",
    )
    catalog: Path = tmp_path / "renamed-filesystem"
    catalog.mkdir()
    _ = (catalog / "catalog.json").write_text(data="{}", encoding="utf-8")
    write_directory_readmes(root=tmp_path)
    expect_in(
        member="Keep this prose.",
        container=(tmp_path / "README.md").read_text(encoding="utf-8"),
    )
    expect_in(
        member="# `fs/`",
        container=(catalog / "README.md").read_text(encoding="utf-8"),
    )


def verify_bundle_runtime(
    *,
    catalog_path: Path,
    cache: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Check command resolution and recovery of a damaged local component.

    Args:
        catalog_path: Published catalog path.
        cache: Runtime cache root.
        monkeypatch: Pytest monkeypatch fixture.

    """
    runtime: Runtime = Runtime(catalog_path=catalog_path, cache=cache)
    for tool in sorted(runtime.tools()):
        command, environment = runtime.command(tool=tool, args=["--version"])
        expect_true(condition=bool(command))
        expect_equal(
            actual=environment["PYTHONDONTWRITEBYTECODE"],
            expected="1",
        )
    materialized: Path = runtime.ensure(name="jinja2")
    expect_equal(
        actual=(materialized / "identity.txt").read_text(),
        expected="jinja2",
    )
    _ = (materialized / "identity.txt").write_text(
        data="corrupt",
        encoding="utf-8",
    )
    _ = runtime.ensure(name="jinja2")
    expect_equal(
        actual=(materialized / "identity.txt").read_text(),
        expected="jinja2",
    )
    expect_equal(
        actual=closure(catalog=runtime.catalog, name="node"),
        expected=["node"],
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="Unsupported bundled tool",
    ):
        _ = runtime.command(tool="unknown", args=[])
    verify_launcher_error_paths(runtime=runtime)
    orphan: Path = runtime.components / ".stale.tmp.01"
    orphan.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv(name="EXACTUS_TOOLS_OBJECT_CACHE", value="discard")
    _ = runtime.ensure(name="jinja2")
    expect_true(condition=not orphan.exists())
    expect_true(condition=not runtime.objects.root.exists())


def verify_launcher_error_paths(*, runtime: Runtime) -> None:
    """Inject malformed metadata to reach every validation failure path.

    Args:
        runtime: Runtime bound to the published catalog.

    """
    with pytest.raises(expected_exception=FormatError, match="Missing/cyclic"):
        _ = closure(catalog=runtime.catalog, name="missing-component")
    components: dict[str, Json] = cast(
        typ="dict[str, Json]",
        val=runtime.catalog["components"],
    )
    jinja2: dict[str, Json] = cast(
        typ="dict[str, Json]",
        val=components["jinja2"],
    )
    metadata: dict[str, Json] = cast(
        typ="dict[str, Json]",
        val=jinja2["metadata"],
    )
    node: dict[str, Json] = cast(typ="dict[str, Json]", val=components["node"])
    node_metadata: dict[str, Json] = cast(
        typ="dict[str, Json]",
        val=node["metadata"],
    )
    metadata["requires"] = ["node"]
    node_metadata["requires"] = ["jinja2"]
    with pytest.raises(expected_exception=FormatError, match="Missing/cyclic"):
        _ = closure(catalog=runtime.catalog, name="jinja2")
    metadata["requires"] = []
    node_metadata["requires"] = []
    metadata["env"] = {"ESCAPE": ["../../outside"]}
    with pytest.raises(expected_exception=FormatError, match="escapes"):
        _ = runtime.environment(name="jinja2")
    metadata["env"] = {}
    node_tools: dict[str, Json] = cast(
        typ="dict[str, Json]",
        val=node_metadata["tools"],
    )
    missing_tool: dict[str, Json] = {
        "kind": "binary",
        "target": "node/bin/missing",
    }
    node_tools["node"] = missing_tool
    with pytest.raises(
        expected_exception=FormatError,
        match="Missing bundled binary",
    ):
        _ = runtime.command(tool="node", args=[])
    jinja2_tools: dict[str, Json] = cast(
        typ="dict[str, Json]",
        val=metadata["tools"],
    )
    jinja2_tools["node"] = missing_tool
    with pytest.raises(expected_exception=FormatError, match="Duplicate tool"):
        _ = runtime.tools()
    del jinja2_tools["node"]


def verify_bundle_dispatch(
    *,
    catalog_path: Path,
    update: Path,
    cache: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Run launcher metadata and maintenance commands on a real catalog.

    Args:
        catalog_path: Published catalog path.
        update: Delta update directory produced by the rebuild.
        cache: Runtime cache root.
        monkeypatch: Pytest monkeypatch fixture.
        capsys: Pytest output capture fixture.

    """
    monkeypatch.setenv(name="EXACTUS_TOOLS_CACHE", value=str(object=cache))
    expect_equal(
        actual=main(catalog_path=catalog_path, arguments=["--version"]),
        expected=0,
    )
    root_sha: str = capsys.readouterr().out.strip()
    expect_true(condition=bool(root_sha))
    expect_equal(
        actual=main(catalog_path=catalog_path, arguments=["list-tools"]),
        expected=0,
    )
    expect_in(member="node", container=capsys.readouterr().out)
    expect_equal(
        actual=main(catalog_path=catalog_path, arguments=["--verify"]),
        expected=0,
    )
    expect_equal(
        actual=main(catalog_path=catalog_path, arguments=["--verify-deep"]),
        expected=0,
    )
    expect_equal(
        actual=main(catalog_path=catalog_path, arguments=["--help"]),
        expected=0,
    )
    expect_equal(
        actual=main(catalog_path=catalog_path, arguments=["missing-tool"]),
        expected=127,
    )
    expect_equal(
        actual=main(
            catalog_path=catalog_path.parents[3] / "missing" / "catalog.json",
            arguments=["--version"],
        ),
        expected=1,
    )
    expect_equal(
        actual=main(catalog_path=catalog_path, arguments=["--apply-update"]),
        expected=1,
    )
    dispatched: list[str] = []

    def replace_process(
        file: str,
        args: list[str],
        env: dict[str, str],
    ) -> NoReturn:
        """Record the dispatch instead of replacing the process.

        Args:
            file: Executable being dispatched.
            args: Full argument vector.
            env: Unused environment.

        Raises:
            LookupError: Always, to stop before ``exec``.

        """
        del env
        dispatched.append(file)
        dispatched.extend(args[1:])
        msg: str = "dispatched"
        raise LookupError(msg)

    with pytest.raises(expected_exception=LookupError, match="dispatched"):
        _ = main(
            catalog_path=catalog_path,
            arguments=["node", "--version"],
            replace_process=replace_process,
        )
    expect_true(condition=dispatched[0].endswith("node"))
    sanitized: Path = cache / "update-artifact"
    _ = shutil_copytree(src=update, dst=sanitized)
    for readme in sanitized.rglob(pattern="README.md"):
        readme.unlink()
    manifest: dict[str, Json] = cast(
        typ="dict[str, Json]",
        val=loads(s=(update / "update.json").read_text()),
    )
    baseline: str = str(object=manifest["baseline_root"])
    retained: Path = catalog_path.parent / "catalogs" / f"{baseline}.json"
    expect_true(condition=retained.is_file())
    expect_equal(
        actual=main(
            catalog_path=catalog_path,
            arguments=["--rollback", baseline],
        ),
        expected=0,
    )
    expect_equal(
        actual=main(
            catalog_path=catalog_path,
            arguments=["--apply-update", str(object=sanitized)],
        ),
        expected=0,
    )
    applied: str = capsys.readouterr().out.strip().splitlines()[-1]
    expect_equal(actual=applied, expected=root_sha)


def verify_corrupt_state_recovery(
    *,
    cache: Path,
    builder: BundleBuilder,
) -> None:
    """Rebuild cleanly after corrupt, dangling, and stale state records.

    Args:
        cache: Runtime cache root.
        builder: Builder republished after each corruption.

    """
    state_path: Path = cache / "state.json"
    _ = state_path.write_text(data="{", encoding="utf-8")
    _ = builder.build(part_bytes=4096)
    state: dict[str, Json] = cast(
        typ="dict[str, Json]",
        val=loads(s=state_path.read_text()),
    )
    state["catalog_root"] = "0" * 64
    _ = state_path.write_text(data=dumps(obj=state), encoding="utf-8")
    _ = builder.build(part_bytes=4096)
    state = cast(typ="dict[str, Json]", val=loads(s=state_path.read_text()))
    components: dict[str, Json] = cast(
        typ="dict[str, Json]",
        val=state["components"],
    )
    record: dict[str, Json] = cast(
        typ="dict[str, Json]",
        val=components["zstd-cli"],
    )
    record["stage"] = "missing-component-tree"
    _ = state_path.write_text(data=dumps(obj=state), encoding="utf-8")
    _ = builder.build(part_bytes=4096)


def verify_incremental_removal(
    *,
    output: Path,
    catalog_path: Path,
    staged: list[str],
) -> BundleBuilder:
    """Verify removal emits a delta update; return the smaller builder.

    Args:
        output: Bundle output directory.
        catalog_path: Published catalog path.
        staged: Staged component names recorded during the rebuild.

    Returns:
        The reduced builder used for the delta publication.

    """
    smaller: BundleBuilder = BundleBuilder(
        config=BundleConfig(),
        output=output,
        target=_GroupFinalConstants.targets["macos-arm64"],
    )
    _ = smaller.build(part_bytes=4096)
    expect_equal(actual=staged, expected=[])
    current: Catalog = load_catalog(path=catalog_path)
    expect_true(condition="jinja2" not in current["components"])
    update: Path = output.parent.with_name(name="arm64.update")
    expect_true(condition=(update / "update.json").is_file())
    metrics: dict[str, Json] = cast(
        typ="dict[str, Json]",
        val=loads(s=(output.parent / "data" / "metrics.json").read_text()),
    )
    expect_equal(actual=metrics["components_removed"], expected=1)
    expect_true(condition=metrics["components_reused"] != 0)
    with pytest.raises(
        expected_exception=ValueError,
        match="must be selected",
    ):
        _ = smaller.build(part_bytes=4096, only=("jinja2",))
    return smaller


def test_bundle_build_reuses_payloads_and_emits_incremental_updates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify real offline publication, reuse, forced rebuild and removal.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.
        capsys: Pytest output capture fixture.

    """
    staged: list[str] = []

    def stage_component(
        self: BundleBuilder,
        *,
        spec: ComponentSpec,
        staging: Path,
        heartbeat: object,
    ) -> dict[str, dict[str, str]]:
        """Write a minimal component tree in place of the real installers.

        Args:
            self: Unused builder.
            spec: Component being staged.
            staging: Per-component staging root.
            heartbeat: Unused progress handle.

        Returns:
            Empty alias table.

        """
        del self, heartbeat
        staged.append(spec.name)
        stage: Path = staging / spec.name
        stage.mkdir(parents=True)
        _ = (stage / "shared.txt").write_bytes(data=b"shared payload" * 100)
        _ = (stage / "identity.txt").write_text(
            data=spec.name,
            encoding="utf-8",
        )
        if spec.node_runtime:
            binary: Path = stage / "node" / "bin" / "node"
            binary.parent.mkdir(parents=True)
            _ = binary.write_bytes(data=b"fake node executable")
            binary.chmod(mode=493)
        if spec.python_packages:
            (stage / "python" / "fixture-1.2.dist-info").mkdir(parents=True)
        if spec.node_packages:
            manifest: Path = (
                stage / "js" / "node_modules" / "fixture" / "package.json"
            )
            manifest.parent.mkdir(parents=True)
            _ = manifest.write_text(data='{"version":"3.4"}', encoding="utf-8")
        return {}

    monkeypatch.setattr(
        target=BundleBuilder,
        name="_stage_component",
        value=stage_component,
    )
    monkeypatch.setattr(
        target=BuildToolsDefaults,
        name="bundle_root",
        value=tmp_path / "bundle-root",
    )
    output: Path = tmp_path / "bundle-root" / "macos" / "arm64" / "__main__.py"
    builder: BundleBuilder = BundleBuilder(
        config=BundleConfig(optional=("jinja2",)),
        output=output,
        target=_GroupFinalConstants.targets["macos-arm64"],
    )
    expect_equal(actual=builder.build(part_bytes=4096), expected=output)
    first_staged: tuple[str, ...] = tuple(staged)
    expect_in(member="jinja2", container=first_staged)
    catalog_path: Path = (
        output.parent / "data" / "parts" / "fs" / "catalog.json"
    )
    first: Catalog = load_catalog(path=catalog_path)
    PartitionStore.verify(catalog=first, root=catalog_path.parent)
    expect_true(condition=bool(first["packs"]))
    expect_true(condition=output.stat().st_mode & 73 != 0)
    verify_bundle_runtime(
        catalog_path=catalog_path,
        cache=tmp_path / "runtime",
        monkeypatch=monkeypatch,
    )
    staged.clear()
    _ = builder.build(part_bytes=4096)
    expect_equal(actual=staged, expected=[])
    second: Catalog = load_catalog(path=catalog_path)
    expect_equal(actual=second["root_sha256"], expected=first["root_sha256"])
    _ = builder.build(part_bytes=4096, only=("jinja2",))
    expect_equal(actual=staged, expected=["jinja2"])
    verify_corrupt_state_recovery(
        cache=output.parent / "data" / ".build-cache" / "macos-arm64",
        builder=builder,
    )
    staged.clear()
    _ = verify_incremental_removal(
        output=output,
        catalog_path=catalog_path,
        staged=staged,
    )
    verify_bundle_dispatch(
        catalog_path=catalog_path,
        update=output.parent.with_name(name="arm64.update"),
        cache=tmp_path / "dispatch-cache",
        monkeypatch=monkeypatch,
        capsys=capsys,
    )
    with pytest.raises(expected_exception=ValueError, match="part_bytes"):
        _ = builder.build(part_bytes=0)


@pytest.mark.parametrize(
    ("size", "label"),
    [(12, "12B"), (1500, "1.5KB"), (1000000, "1MB"), (1000000000, "1GB")],
)
def test_bundle_size_labels(size: int, label: str) -> None:
    """Format exact and fractional SI sizes without trailing zeroes.

    Args:
        size: Byte count under test.
        label: Expected human-readable label.

    """
    expect_equal(actual=size_label(size=size), expected=label)


def test_bundle_component_and_target_selection() -> None:
    """Expand groups and dependencies, preserving required components."""
    module: ModuleType = import_module(name="exactus.packages.package.bundle")
    parser: ArgumentParser = private_result(
        owner=module,
        name="_build_parser",
        kind=ArgumentParser,
    )
    expand: Callable[..., tuple[str, ...]] = cast(
        typ="Callable[..., tuple[str, ...]]",
        val=private(owner=module, name="_expand_target_name"),
    )
    expect_equal(
        actual=expand(parser=parser, name="all"),
        expected=tuple(_GroupFinalConstants.targets),
    )
    expect_equal(
        actual=expand(parser=parser, name="macos-arm64"),
        expected=("macos-arm64",),
    )
    expect_true(condition=bool(expand(parser=parser, name="linux")))
    with pytest.raises(expected_exception=SystemExit):
        _ = expand(parser=parser, name="invalid")
    with pytest.raises(
        expected_exception=ValueError,
        match="unknown optional",
    ):
        _ = resolve_components(names=("invalid",))
    expect_in(
        member="node",
        container=resolve_components(names=("playwright",)),
    )
    expect_equal(
        actual=resolve_components(
            names=("playwright",),
            follow_requires=False,
        ),
        expected=("playwright",),
    )
    expect_true(
        condition=bool(resolve_components(names=("all", "browser", "pytest"))),
    )
    config: BundleConfig = BundleConfig(
        optional=("playwright",),
        exclude=frozenset({"node", "zstd-cli"}),
    )
    names: tuple[str, ...] = tuple(spec.name for spec in config.components)
    expect_in(member="node", container=names)
    expect_in(member="zstd-cli", container=names)
    expect_in(member="playwright", container=config.available_tools)


@pytest.mark.parametrize(
    "text",
    [
        "tool=1",
        "[tool]\nbundle=1",
        "[tool.bundle]\ntargets=1",
        "[tool.bundle]\noptional=[1]",
        '[tool.bundle]\nrebuild="yes"',
    ],
)
def test_bundle_file_config_rejects_invalid_types(
    tmp_path: Path,
    text: str,
) -> None:
    """Validate lists and scalars without accepting malformed configuration.

    Args:
        tmp_path: Isolated filesystem root.
        text: ``pyproject.toml`` content under test.

    """
    path: Path = tmp_path / "pyproject.toml"
    _ = path.write_text(data=text, encoding="utf-8")
    if "[tool.bundle]" in text:
        with pytest.raises(expected_exception=TypeError, match="must be"):
            _ = bundle_file_config(path=path)
    else:
        expect_equal(actual=bundle_file_config(path=path).targets, expected=())


def test_bundle_file_config_resolves_relative_paths(tmp_path: Path) -> None:
    """Read all configured defaults relative to the project file.

    Args:
        tmp_path: Isolated filesystem root.

    """
    path: Path = tmp_path / "pyproject.toml"
    expect_equal(actual=bundle_file_config(path=path).optional, expected=())
    _ = path.write_text(
        data=(
            dedent(
                text="""\
    [tool.bundle]
    targets=["macos-arm64"]
    optional=["jinja2"]
    exclude=["pillow"]
    only=["jinja2"]
    node-version="22"
    part-bytes=4096
    output="out/tools"
    parts-dir="out/parts"
    rebuild=true
    """,
            )
        ),
        encoding="utf-8",
    )
    config: BundleFileConfig = bundle_file_config(path=path)
    expect_equal(actual=config.output, expected=tmp_path / "out" / "tools")
    expect_equal(actual=config.parts_dir, expected=tmp_path / "out" / "parts")
    expect_equal(actual=config.optional, expected=("jinja2",))
    expect_equal(actual=config.part_bytes, expected=4096)
    expect_true(condition=config.rebuild)


def test_bundle_fetch_enforces_limits_and_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry transient failures and enforce HTTP response limits.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    module: ModuleType = import_module(name="exactus.packages.package.bundle")
    calls: list[int] = []

    def open_url(*, url: object, timeout: float) -> BytesIO:
        """Fail twice then succeed to exercise the retry loop.

        Args:
            url: Unused request URL.
            timeout: Unused timeout.

        Returns:
            The canned payload on the third attempt.

        Raises:
            URLError: On the first attempt.
            HTTPError: On the second attempt.

        """
        del url, timeout
        calls.append(1)
        if len(calls) == 1:
            raise URLError(reason="temporary")
        retry_attempt: int = 2
        if len(calls) == retry_attempt:
            raise HTTPError(
                url="https://fixture.test",
                code=503,
                msg="retry",
                hdrs=Message(),
                fp=None,
            )
        return BytesIO(initial_bytes=b"payload")

    def no_sleep(seconds: float) -> None:
        """Skip retry backoff during the simulated transfer.

        Args:
            seconds: Unused delay.

        """
        del seconds

    monkeypatch.setattr(target=module, name="urlopen", value=open_url)
    monkeypatch.setattr(target=module, name="sleep", value=no_sleep)
    expect_equal(
        actual=fetch(
            url="https://fixture.test",
            options=FetchOptions(attempts=3),
        ),
        expected=b"payload",
    )
    expect_equal(actual=len(calls), expected=3)
    with pytest.raises(expected_exception=FetchError, match="exceeded"):
        _ = fetch(url="https://fixture.test", options=FetchOptions(limit=2))
    with pytest.raises(expected_exception=FetchError, match="No attempts"):
        _ = fetch(url="https://fixture.test", options=FetchOptions(attempts=0))
    with pytest.raises(expected_exception=FetchError, match="Refusing"):
        _ = fetch(url="file:///etc/hosts")

    def fail_url(*, url: object, timeout: float) -> BytesIO:
        """Fail every attempt with a terminal HTTP error.

        Args:
            url: Unused request URL.
            timeout: Unused timeout.

        Returns:
            Unreachable value; the call always raises.

        Raises:
            HTTPError: Always.

        """
        del url, timeout
        raise HTTPError(
            url="https://fixture.test",
            code=404,
            msg="missing",
            hdrs=Message(),
            fp=None,
        )

    monkeypatch.setattr(target=module, name="urlopen", value=fail_url)
    calls.clear()
    with pytest.raises(expected_exception=FetchError, match="HTTP 404"):
        _ = fetch(url="https://fixture.test", options=FetchOptions(attempts=3))


def test_bundle_filesystem_helpers(tmp_path: Path) -> None:
    """Exercise pruning, zip extraction, removal, and version scanning.

    Args:
        tmp_path: Isolated filesystem root.

    """
    payload: Path = tmp_path / "payload"
    cached: Path = payload / "mod" / "__pycache__"
    cached.mkdir(parents=True)
    _ = (cached / "mod.cpython-313.pyc").write_bytes(data=b"bytecode")
    _ = (payload / "app.map").write_bytes(data=b"map")
    _ = (payload / "._apple").write_bytes(data=b"apple")
    _ = (payload / ".DS_Store").write_bytes(data=b"store")
    _ = (payload / "keep.txt").write_bytes(data=b"keep")
    BundleBuilder.prune(payload=payload)
    expect_true(condition=not cached.exists())
    expect_equal(
        actual=tuple(
            path for path in payload.rglob(pattern="*") if path.is_file()
        ),
        expected=(payload / "keep.txt",),
    )
    archive: Path = tmp_path / "payload.zip"
    info: ZipInfo = ZipInfo(filename="tool")
    info.external_attr = 493 << 16
    with ZipFile(file=archive, mode="w") as zipped:
        zipped.writestr(zinfo_or_arcname=info, data=b"tool")
    private_call(
        owner=BundleBuilder,
        name="_extract_zip",
        archive=archive,
        destination=payload,
    )
    expect_true(condition=(payload / "tool").stat().st_mode & 73 != 0)
    private_call(owner=BundleBuilder, name="_remove", path=payload / "tool")
    expect_true(condition=not (payload / "tool").exists())
    private_call(owner=BundleBuilder, name="_remove", path=payload / "missing")
    link: Path = payload / "linked"
    link.symlink_to(target=payload / "keep.txt")
    private_call(owner=BundleBuilder, name="_remove", path=link)
    private_call(owner=BundleBuilder, name="_remove", path=payload)
    expect_true(condition=not payload.exists())
    stage: Path = tmp_path / "stage"
    (stage / "python" / "pkg-1.0.dist-info").mkdir(parents=True)
    modules: Path = stage / "js" / "node_modules"
    (modules / "empty").mkdir(parents=True)
    (modules / "pkg").mkdir(parents=True)
    _ = (modules / "pkg" / "package.json").write_bytes(data=b'{"version":"2"}')
    versions: dict[str, str] = cast(
        typ="dict[str, str]",
        val=private_call(
            owner=BundleBuilder,
            name="_python_versions",
            stage=stage,
        ),
    )
    expect_equal(actual=versions, expected={"pkg": "1.0"})
    versions = cast(
        typ="dict[str, str]",
        val=private_call(
            owner=BundleBuilder,
            name="_node_versions",
            stage=stage,
        ),
    )
    expect_equal(actual=versions, expected={"pkg": "2"})
    versions = cast(
        typ="dict[str, str]",
        val=private_call(
            owner=BundleBuilder,
            name="_node_versions",
            stage=tmp_path / "missing-stage",
        ),
    )
    expect_equal(actual=versions, expected={})
    expect_true(
        condition=private_result(
            owner=BundleBuilder,
            name="_tree_bytes",
            kind=int,
            root=tmp_path,
        )
        > 0,
    )


def test_bundle_installers_stage_runtimes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Stage Node, Python, npm, and zstd payloads with local doubles.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    module: ModuleType = import_module(name="exactus.packages.package.bundle")
    builder: BundleBuilder = BundleBuilder(
        config=BundleConfig(),
        output=tmp_path / "out",
        target=_GroupFinalConstants.targets["windows-amd64"],
    )
    commands: list[tuple[str, ...]] = []

    def record_run(
        self: BundleBuilder,
        *,
        args: tuple[str, ...],
        cwd: Path,
        env: dict[str, str] | None = None,
    ) -> None:
        """Record a staged command instead of running it.

        Args:
            self: Unused builder.
            args: Command line being recorded.
            cwd: Unused working directory.
            env: Unused environment.

        """
        del self, cwd, env
        commands.append(args)

    def fetch_zip(*, url: str, options: FetchOptions | None = None) -> bytes:
        """Return a canned Node zip archive.

        Args:
            url: Unused download URL.
            options: Unused fetch options.

        Returns:
            Zip bytes containing a minimal Node layout.

        """
        del url, options
        buffer: BytesIO = BytesIO()
        with ZipFile(file=buffer, mode="w") as zipped:
            for name in (
                "node-v22.21.1-win-x64/node.exe",
                "node-v22.21.1-win-x64/npm.cmd",
                "node-v22.21.1-win-x64/README.md",
            ):
                zipped.writestr(zinfo_or_arcname=name, data=b"x")
        return buffer.getvalue()

    monkeypatch.setattr(target=BundleBuilder, name="_run", value=record_run)
    monkeypatch.setattr(target=module, name="fetch", value=fetch_zip)
    stage: Path = tmp_path / "node-stage"
    stage.mkdir()
    private_call(owner=builder, name="_install_node_runtime", stage=stage)
    expect_true(condition=(stage / "node" / "node.exe").is_file())
    expect_true(condition=not (stage / "node" / "npm.cmd").exists())
    spec: ComponentSpec = ComponentSpec(
        name="packages",
        python_packages=("pytest",),
        node_packages=("eslint",),
        python_extras=True,
    )
    private_call(owner=builder, name="_install_python", stage=stage, spec=spec)
    expect_in(member="--python-version=3.13", container=commands[0])
    expect_in(member="msvc-runtime", container=commands[0])

    def host_tool(*, cmd: str) -> str:
        """Report npm as installed on the build host.

        Args:
            cmd: Tool name being located.

        Returns:
            A synthetic host path for the tool.

        """
        return f"/host/{cmd}"

    monkeypatch.setattr(target=module, name="which", value=host_tool)
    private_call(
        owner=builder,
        name="_install_node_packages",
        stage=stage,
        spec=spec,
        staging=tmp_path,
    )
    expect_in(member="eslint", container=commands[1])

    def no_which(*, cmd: str) -> str | None:
        """Report the tool as missing on the build host.

        Args:
            cmd: Unused tool name.

        Returns:
            Always ``None``.

        """
        del cmd
        return None

    monkeypatch.setattr(target=module, name="which", value=no_which)
    with pytest.raises(
        expected_exception=ValueError,
        match="host npm is required",
    ):
        private_call(
            owner=builder,
            name="_install_node_packages",
            stage=stage,
            spec=spec,
            staging=tmp_path,
        )
    exported: list[Path] = []

    def record_export(*, os_name: str, machine: str, target: Path) -> None:
        """Record an exported package instead of publishing it.

        Args:
            os_name: Unused operating-system selector.
            machine: Unused machine selector.
            target: Export destination.

        """
        del os_name, machine
        exported.append(target)

    monkeypatch.setattr(
        target=module,
        name="export_package",
        value=record_export,
    )
    private_call(owner=builder, name="_install_zstd_cli", stage=stage)
    expect_equal(actual=exported, expected=[stage])


def test_bundle_browser_installers_and_dedupe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Install Playwright archives, dedupe Node binaries, and prune locales.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    module: ModuleType = import_module(name="exactus.packages.package.bundle")
    builder: BundleBuilder = BundleBuilder(
        config=BundleConfig(),
        output=tmp_path / "out",
        target=_GroupFinalConstants.targets["macos-arm64"],
    )
    downloaded: list[str] = []

    def download_browser(**arguments: object) -> bytes:
        """Return a canned browser archive.

        Args:
            **arguments: Download descriptor arguments.

        Returns:
            Zip bytes containing a single tool binary.

        """
        downloaded.append(str(object=arguments.get("descriptor")))
        buffer: BytesIO = BytesIO()
        with ZipFile(file=buffer, mode="w") as zipped:
            zipped.writestr(zinfo_or_arcname="bin/tool", data=b"x")
        return buffer.getvalue()

    monkeypatch.setattr(
        target=builder,
        name="_download_browser",
        value=download_browser,
    )
    staging: Path = tmp_path / "staging"
    catalog: Path = (
        staging
        / "playwright"
        / "python"
        / "playwright"
        / "driver"
        / "package"
        / "browsers.json"
    )
    catalog.parent.mkdir(parents=True)
    _ = catalog.write_text(
        data=dumps(
            obj={
                "browsers": [
                    {
                        "name": "chromium",
                        "revision": "9",
                        "browserVersion": "1.0",
                    },
                    {
                        "name": "chromium-headless-shell",
                        "revision": "9",
                        "browserVersion": "1.0",
                    },
                    {"name": "ffmpeg", "revision": "9"},
                ],
            },
        ),
        encoding="utf-8",
    )
    heartbeat: SimpleNamespace = SimpleNamespace(state={})
    installed: dict[str, dict[str, str]] = cast(
        typ="dict[str, dict[str, str]]",
        val=private_call(
            owner=builder,
            name="_install_chromium",
            stage=staging / "chromium",
            staging=staging,
            heartbeat=heartbeat,
        ),
    )
    expect_equal(actual=len(installed), expected=3)
    expect_true(
        condition=(
            staging / "chromium" / "playwright-browsers" / "chromium-9"
        ).is_dir(),
    )
    _ = catalog.write_text(data='{"browsers":[]}', encoding="utf-8")
    with pytest.raises(
        expected_exception=ValueError,
        match="missing chromium",
    ):
        private_call(
            owner=builder,
            name="_install_chromium",
            stage=staging / "chromium2",
            staging=staging,
            heartbeat=heartbeat,
        )
    attempts: list[str] = []
    downloader: BundleBuilder = BundleBuilder(
        config=BundleConfig(),
        output=tmp_path / "other",
        target=_GroupFinalConstants.targets["macos-arm64"],
    )

    def fail_once(*, url: str, options: FetchOptions | None = None) -> bytes:
        """Fail the primary mirror once, then serve the CDN archive.

        Args:
            url: Download URL attempted.
            options: Unused fetch options.

        Returns:
            The CDN archive bytes.

        Raises:
            FetchError: On the first attempt.

        """
        del options
        attempts.append(url)
        if len(attempts) == 1:
            msg: str = "cft unavailable"
            raise FetchError(msg)
        return b"cdn-archive"

    monkeypatch.setattr(target=module, name="fetch", value=fail_once)
    archive: BrowserArchive = BrowserArchive(
        name="chromium",
        cdn_file="chromium-mac-arm64.zip",
        cft_file="chrome-mac-arm64.zip",
    )
    result: bytes = private_result(
        owner=downloader,
        name="_download_browser",
        kind=bytes,
        archive=archive,
        descriptor="chromium",
        revision="9",
        browser_version="1.0",
    )
    expect_equal(actual=result, expected=b"cdn-archive")
    expect_equal(actual=len(attempts), expected=2)
    attempts.clear()

    def fail_always(*, url: str, options: FetchOptions | None = None) -> bytes:
        """Fail every download mirror.

        Args:
            url: Unused download URL.
            options: Unused fetch options.

        Returns:
            Unreachable value; the call always raises.

        Raises:
            FetchError: Always.

        """
        del url, options
        msg: str = "unavailable"
        raise FetchError(msg)

    monkeypatch.setattr(target=module, name="fetch", value=fail_always)
    with pytest.raises(expected_exception=ValueError, match="no downloadable"):
        private_call(
            owner=downloader,
            name="_download_browser",
            archive=archive,
            descriptor="chromium",
            revision="9",
            browser_version="1.0",
        )


def test_bundle_payload_dedupe_prune_and_stage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Deduplicate embedded runtimes, prune browsers, and stage metadata.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    builder: BundleBuilder = BundleBuilder(
        config=BundleConfig(),
        output=tmp_path / "out",
        target=_GroupFinalConstants.targets["macos-arm64"],
    )
    heartbeat: SimpleNamespace = SimpleNamespace(state={})
    dedupe: Path = tmp_path / "dedupe-staging"
    bundled: Path = dedupe / "node" / "node" / "bin" / "node"
    bundled.parent.mkdir(parents=True)
    _ = bundled.write_bytes(data=b"node")
    stage: Path = dedupe / "pkg"
    embedded: Path = stage / "python" / "nodejs_wheel" / "lib" / "node"
    embedded.parent.mkdir(parents=True)
    _ = embedded.write_bytes(data=b"embedded")
    (stage / "python" / "nodejs_wheel" / "include").mkdir(parents=True)
    private_call(
        owner=builder,
        name="_dedupe_node",
        stage=stage,
        staging=dedupe,
    )
    expect_true(condition=embedded.is_symlink())
    expect_true(
        condition=not (stage / "python" / "nodejs_wheel" / "include").exists(),
    )
    browsers: Path = tmp_path / "payload" / "playwright-browsers"
    (browsers / "WidevineCdm").mkdir(parents=True)
    (browsers / "fr.lproj").mkdir()
    (browsers / "en.lproj").mkdir()
    private_call(
        owner=builder,
        name="_prune_browsers",
        payload=tmp_path / "payload",
    )
    expect_true(condition=not (browsers / "WidevineCdm").exists())
    expect_true(condition=not (browsers / "fr.lproj").exists())
    expect_true(condition=(browsers / "en.lproj").exists())
    spec: ComponentSpec = ComponentSpec(
        name="component",
        python_packages=("x",),
    )
    installed_python: list[ComponentSpec] = []

    def record_python(
        self: BundleBuilder,
        *,
        stage: Path,
        spec: ComponentSpec,
    ) -> None:
        """Record the staged Python component instead of installing it.

        Args:
            self: Unused builder.
            stage: Unused staging root.
            spec: Component being installed.

        """
        del self, stage
        installed_python.append(spec)

    monkeypatch.setattr(
        target=BundleBuilder,
        name="_install_python",
        value=record_python,
    )
    private_call(
        owner=builder,
        name="_stage_component",
        spec=spec,
        staging=tmp_path / "stage-root",
        heartbeat=heartbeat,
    )
    expect_equal(actual=installed_python, expected=[spec])


def test_bundle_document_and_cli_resolution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Render status documents and resolve CLI targets without building.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    module: ModuleType = import_module(name="exactus.packages.package.bundle")
    builder: BundleBuilder = BundleBuilder(
        config=BundleConfig(),
        output=tmp_path / "out",
    )
    watched: Path = tmp_path / "watch.bin"
    _ = watched.write_bytes(data=b"x" * 50)
    heartbeat: SimpleNamespace = SimpleNamespace(
        state={
            "step": "pack",
            "fraction": "0.5",
            "watch": str(object=watched),
            "watch_total": "100",
            "payload_bytes": "5000",
        },
        steps=[{"name": "fingerprint", "seconds": "1.0"}],
        started=monotonic() - 2,
        started_at=datetime.now(tz=UTC).astimezone(),
        run_id="run",
        part_bytes=4096,
    )
    document: dict[str, Json] = cast(
        typ="dict[str, Json]",
        val=private_call(
            owner=builder,
            name="_document",
            heartbeat=heartbeat,
            status="RUNNING",
        ),
    )
    expect_equal(
        actual=dig_text(document=document, path=("extra", "payload", "size")),
        expected="5KB",
    )
    heartbeat.state["watch_total"] = "0"
    document = cast(
        typ="dict[str, Json]",
        val=private_call(
            owner=builder,
            name="_document",
            heartbeat=heartbeat,
            status="DONE",
        ),
    )
    items: list[Json] = cast(typ="list[Json]", val=document["items"])
    expect_equal(actual=len(items), expected=8)
    parser: ArgumentParser = private_result(
        owner=module,
        name="_build_parser",
        kind=ArgumentParser,
    )
    options: BuildOptions = BuildOptions()
    options.target = ["macos-arm64", "windows-amd64"]
    options.output = tmp_path / "single"
    with pytest.raises(expected_exception=SystemExit):
        private_call(
            owner=module,
            name="_resolve_targets",
            parser=parser,
            options=options,
            file_config=BundleFileConfig(),
        )
    options = BuildOptions()
    options.target = ["all"]
    targets: tuple[object, ...] = cast(
        typ="tuple[object, ...]",
        val=private_call(
            owner=module,
            name="_resolve_targets",
            parser=parser,
            options=options,
            file_config=BundleFileConfig(),
        ),
    )
    expect_equal(
        actual=len(targets),
        expected=len(_GroupFinalConstants.targets),
    )

    def no_host() -> str | None:
        """Report an undetectable build host.

        Returns:
            Always ``None``.

        """
        return None

    monkeypatch.setattr(target=module, name="host_target", value=no_host)
    expand: Callable[..., tuple[str, ...]] = cast(
        typ="Callable[..., tuple[str, ...]]",
        val=private(owner=module, name="_expand_target_name"),
    )
    with pytest.raises(expected_exception=SystemExit):
        _ = expand(parser=parser, name="auto")


def dig_text(*, document: dict[str, Json], path: tuple[str, ...]) -> object:
    """Walk a decoded document to a scalar value.

    Args:
        document: Decoded JSON document.
        path: Key path to traverse.

    Returns:
        The value found at the path.

    """
    value: Json = document
    for key in path:
        value = cast(typ="dict[str, Json]", val=value)[key]
    return value


def test_bundle_main_builds_selected_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dispatch configured targets through the real CLI entry point.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    module: ModuleType = import_module(name="exactus.packages.package.bundle")
    built: list[str] = []

    def fake_build(
        self: BundleBuilder,
        *,
        part_bytes: int,
        only: tuple[str, ...],
        rebuild: bool,
        chunking: object = None,
    ) -> Path:
        """Record the requested target instead of building it.

        Args:
            self: Builder bound to a target.
            part_bytes: Unused pack size.
            only: Unused component filter.
            rebuild: Unused rebuild flag.
            chunking: Unused chunking overrides.

        Returns:
            A placeholder output path.

        """
        del part_bytes, only, rebuild, chunking
        built.append(
            private_as(owner=self, name="_target", kind=BuildTarget).name,
        )
        return Path("/dev/null")

    monkeypatch.setattr(target=BundleBuilder, name="build", value=fake_build)

    def no_cleanup(*, root: Path) -> int:
        """Skip working-copy cleanup.

        Args:
            root: Unused root path.

        Returns:
            Always ``0``.

        """
        del root
        return 0

    def no_content(*, root: Path) -> None:
        """Skip content-file generation.

        Args:
            root: Unused root path.

        """
        del root

    def no_file_config(*, path: Path) -> BundleFileConfig:
        """Return default file configuration.

        Args:
            path: Unused project file path.

        Returns:
            An empty ``BundleFileConfig``.

        """
        del path
        return BundleFileConfig()

    monkeypatch.setattr(
        target=module,
        name="clear_conflict_copies",
        value=no_cleanup,
    )
    monkeypatch.setattr(target=module, name="write_content", value=no_content)
    monkeypatch.setattr(
        target=module,
        name="bundle_file_config",
        value=no_file_config,
    )
    monkeypatch.setattr(
        target=import_module(name="sys"),
        name="argv",
        value=[
            "bundle",
            "--target",
            "linux-musl-arm64",
            "macos-arm64",
            "--optional",
            "playwright",
        ],
    )
    expect_equal(
        actual=private_result(owner=module, name="main", kind=int),
        expected=0,
    )
    expect_equal(actual=built, expected=["linux-musl-arm64", "macos-arm64"])


def test_bundle_cache_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Cache roots fall back deterministically and locks reject abuse.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    launcher: ModuleType = import_module(
        name="exactus.packages.package.partition_launcher",
    )
    base: Path = tmp_path / "cache"
    identity: str = "ab" * 32
    expect_equal(
        actual=private_result(
            owner=launcher,
            name="_select_cache_root",
            kind=Path,
            base=base,
            identity=identity,
        ),
        expected=base / identity,
    )
    blocked: Path = tmp_path / "blocked"
    blocked.mkdir()
    _ = (blocked / identity).write_text(data="block", encoding="utf-8")
    owner: str = private_result(owner=launcher, name="_cache_owner", kind=str)
    expect_equal(
        actual=private_result(
            owner=launcher,
            name="_select_cache_root",
            kind=Path,
            base=blocked,
            identity=identity,
        ),
        expected=blocked / f"{identity}.{owner}",
    )
    verify_cache_usability(launcher=launcher, tmp_path=tmp_path)
    verify_cache_lock_failures(
        launcher=launcher,
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        identity=identity,
    )


def verify_cache_usability(*, launcher: ModuleType, tmp_path: Path) -> None:
    """Reject symlink, file, and non-file-lock cache candidates.

    Args:
        launcher: Partition launcher module under test.
        tmp_path: Isolated filesystem root.

    """

    def usable(*, root: Path) -> bool:
        """Ask the launcher whether a cache candidate is usable.

        Args:
            root: Candidate cache root.

        Returns:
            The private ``_usable_cache_root`` verdict.

        """
        return private_result(
            owner=launcher,
            name="_usable_cache_root",
            kind=bool,
            root=root,
        )

    expect_true(condition=usable(root=tmp_path / "plain"))
    target: Path = tmp_path / "target"
    target.mkdir()
    linked: Path = tmp_path / "linked"
    linked.symlink_to(target=target)
    expect_equal(actual=usable(root=linked), expected=False)
    as_file: Path = tmp_path / "as-file"
    _ = as_file.write_text(data="x", encoding="utf-8")
    expect_equal(actual=usable(root=as_file), expected=False)
    lock_dir: Path = tmp_path / "lock-dir"
    (lock_dir / ".lock").mkdir(parents=True)
    expect_equal(actual=usable(root=lock_dir), expected=False)
    lock_link: Path = tmp_path / "lock-link"
    lock_link.mkdir()
    (lock_link / ".lock").symlink_to(target=target / "elsewhere")
    expect_equal(actual=usable(root=lock_link), expected=False)


def verify_cache_lock_failures(
    *,
    launcher: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    identity: str,
) -> None:
    """Exhaust candidates, reject symlinked locks, and bound flock waits.

    Args:
        launcher: Partition launcher module under test.
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.
        identity: Catalog identity used for cache candidates.

    """

    def deny(*, root: Path) -> bool:
        """Reject every cache candidate.

        Args:
            root: Unused candidate root.

        Returns:
            Always ``False``.

        """
        del root
        return False

    monkeypatch.setattr(target=launcher, name="_usable_cache_root", value=deny)
    with pytest.raises(
        expected_exception=PermissionError,
        match="No writable runtime cache",
    ):
        _ = private_result(
            owner=launcher,
            name="_select_cache_root",
            kind=Path,
            base=tmp_path / "none",
            identity=identity,
        )
    monkeypatch.undo()
    lock_root: Path = tmp_path / "locks"
    with cache_lock(root=lock_root):
        expect_true(condition=(lock_root / ".lock").is_file())
    bad: Path = tmp_path / "bad-lock"
    bad.mkdir()
    target_lock: Path = tmp_path / "target-lock"
    _ = target_lock.write_text(data="x", encoding="utf-8")
    (bad / ".lock").symlink_to(target=target_lock)
    with (
        pytest.raises(expected_exception=FormatError, match="symlink"),
        cache_lock(root=bad),
    ):
        fail(message="symlinked lock was accepted")
    if platform != "win32":
        fcntl_module: ModuleType = import_module(name="fcntl")

        def deny_flock(*positional: object) -> None:
            """Simulate a lock already held by another process.

            Args:
                *positional: Unused flock arguments.

            Raises:
                BlockingIOError: Always.

            """
            del positional
            msg: str = "held"
            raise BlockingIOError(msg)

        monkeypatch.setattr(
            target=fcntl_module,
            name="flock",
            value=deny_flock,
        )
        with (
            pytest.raises(expected_exception=TimeoutError, match="timed out"),
            cache_lock(root=tmp_path / "timeout", timeout=0.0),
        ):
            fail(message="contended lock was acquired")


def test_build_file_config_parses_tables_and_flags(tmp_path: Path) -> None:
    """``[tool.build]`` TOML defaults parse into build file config.

    Args:
        tmp_path: Isolated filesystem root.

    """
    package_build: ModuleType = import_module(
        name="exactus.packages.package.build",
    )
    missing: object = private_call(
        owner=package_build,
        name="build_file_config",
        path=tmp_path / "pyproject.toml",
    )
    expect_equal(actual=missing, expected=package_build.BuildFileConfig())
    for document in ('tool = "x"\n', "[tool]\nbuild = 1\n"):
        path: Path = tmp_path / f"doc{len(document)}.toml"
        _ = path.write_text(data=document, encoding="utf-8")
        expect_equal(
            actual=private_call(
                owner=package_build,
                name="build_file_config",
                path=path,
            ),
            expected=package_build.BuildFileConfig(),
        )
    valid: Path = tmp_path / "valid.toml"
    _ = valid.write_text(
        data=(
            dedent(
                text="""\
    [tool.build]
    exactus = true
    tree = true
    no-exactus = true
    target = "amd64"
    targets = ["all"]
    [tool.build.exec]
    target = "musl"
    targets = ["linux-glibc-amd64"]
    """,
            )
        ),
        encoding="utf-8",
    )
    parsed: object = private_call(
        owner=package_build,
        name="build_file_config",
        path=valid,
    )
    expect_equal(actual=private(owner=parsed, name="check"), expected=True)
    expect_equal(
        actual=private(owner=parsed, name="exec_targets"),
        expected=("linux-glibc-amd64",),
    )
    expect_equal(actual=private(owner=parsed, name="target"), expected="amd64")


@pytest.mark.parametrize(
    "document",
    [
        "[tool.build]\nexec = 1\n",
        "[tool.build]\ncheck = 1\n",
        '[tool.build]\ntargets = "amd64"\n',
        "[tool.build]\ntargets = [1]\n",
        "[tool.build]\ntarget = 1\n",
        "[tool.build.exec]\ntargets = 1\n",
    ],
)
def test_build_file_config_rejects_bad_types(
    document: str,
    tmp_path: Path,
) -> None:
    """Every malformed ``[tool.build]`` key raises ``TypeError``.

    Args:
        document: TOML document with one invalid key.
        tmp_path: Isolated filesystem root.

    """
    package_build: ModuleType = import_module(
        name="exactus.packages.package.build",
    )
    path: Path = tmp_path / "pyproject.toml"
    _ = path.write_text(data=document, encoding="utf-8")
    with pytest.raises(expected_exception=TypeError, match="tool\\.build"):
        _ = private_call(
            owner=package_build,
            name="build_file_config",
            path=path,
        )


def test_bundle_target_leaf_filtering(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``_ignore`` keeps selected bundle leaves and prunes the rest.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    package_build: ModuleType = import_module(
        name="exactus.packages.package.build",
    )
    source: Path = tmp_path / "exactus"
    bundle: Path = source / "bundle"
    macos: Path = bundle / "macos"
    linux: Path = bundle / "linux"
    _ = (macos / "arm64").mkdir(parents=True)
    _ = (macos / "amd64").mkdir(parents=True)
    _ = (macos / "arm64.update").mkdir(parents=True)
    _ = (linux / "glibc").mkdir(parents=True)
    _ = (bundle / ".hidden").mkdir()
    monkeypatch.setattr(target=Constants, name="package", value=source)
    kept: frozenset[Path] = frozenset({Path("bundle/macos/arm64")})
    ignored: object = private_call(
        owner=package_build,
        name="_ignore",
        directory=str(object=bundle),
        names=[
            "macos",
            "linux",
            ".hidden",
            ".DS_Store",
            "x.pyc",
            "__pycache__",
        ],
        kept=kept,
    )
    expect_equal(
        actual=ignored,
        expected={"linux", ".hidden", ".DS_Store", "x.pyc", "__pycache__"},
    )
    nested: object = private_call(
        owner=package_build,
        name="_ignore",
        directory=str(object=macos),
        names=["arm64", "amd64", "arm64.update"],
        kept=kept,
    )
    expect_equal(actual=nested, expected={"amd64"})
    outside: object = private_call(
        owner=package_build,
        name="_ignore",
        directory=str(object=source / "tools"),
        names=["anything"],
        kept=kept,
    )
    expect_equal(actual=outside, expected=cast(typ="set[str]", val=set()))
    expect_true(
        condition=private_call(
            owner=package_build,
            name="_kept_leaf",
            candidate=Path("bundle/macos/arm64.update"),
            leaf=Path("bundle/macos/arm64"),
        )
        is True,
    )


def verify_catalog_pack_rejections(
    *,
    package_build: ModuleType,
    staging: Path,
) -> None:
    """Exercise every catalog pack validation rejection branch.

    Args:
        package_build: Imported build module.
        staging: Synthetic staging root.

    """
    catalog_dir: Path = (
        staging
        / "exactus"
        / "bundle"
        / "target"
        / "data"
        / "parts"
        / "fs"
        / "catalogs"
    )
    catalog_dir.mkdir(parents=True)
    cases: list[tuple[str, str]] = [
        ("not-dict", "[]"),
        ("no-packs", '{"packs": 1}'),
        ("bad-record", '{"packs": {"p": 1}}'),
        (
            "incomplete",
            '{"packs": {"p": {"path": 1, "sha256": "x", "bytes": 0}}}',
        ),
        (
            "missing-pack",
            (
                '{"packs": {"p": {"path": "none.pack", "sha256": "x", '
                '"bytes": 0}}}'
            ),
        ),
    ]
    for index, (name, document) in enumerate(iterable=cases):
        _ = (catalog_dir / f"{index}{name}.json").write_text(
            data=document,
            encoding="utf-8",
        )
        with pytest.raises(expected_exception=(TypeError, ValueError)):
            _ = private_call(
                owner=package_build,
                name="_validate_staged_bundle_packs",
                staging=staging,
            )
        (catalog_dir / f"{index}{name}.json").unlink()


def test_build_stages_native_payloads_and_validates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Native zstd staging and catalog validation run on a real tree.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    package_build: ModuleType = import_module(
        name="exactus.packages.package.build",
    )
    archives: Path = tmp_path / "zstd"
    archives.mkdir()
    payload: Path = archives / "linux-x86_64.zip"
    _ = payload.write_bytes(data=b"payload")
    monkeypatch.setattr(
        target=Constants,
        name="bin_zstd_portable",
        value=archives,
    )
    staging: Path = tmp_path / "staging"
    zstd_package: Path = (
        staging
        / "exactus"
        / "bundle"
        / "linux"
        / "glibc"
        / "amd64"
        / "zstd_portable"
    )
    zstd_package.mkdir(parents=True)
    _ = private_call(
        owner=package_build,
        name="_stage_zstd_portable",
        staging=staging,
    )
    expect_true(
        condition=(zstd_package / "bin" / "linux-x86_64.zip").is_file(),
    )
    unmapped: Path = staging / "exactus" / "bundle" / "amiga" / "os" / "m68k"
    _ = (unmapped / "zstd_portable").mkdir(parents=True)
    with pytest.raises(expected_exception=ValueError, match="amiga"):
        _ = private_call(
            owner=package_build,
            name="_stage_zstd_portable",
            staging=staging,
        )
    rmtree(path=staging / "exactus" / "bundle" / "amiga")
    missing_dir: Path = (
        staging / "exactus" / "bundle" / "macos" / "arm" / "arm64"
    )
    _ = (missing_dir / "zstd_portable").mkdir(parents=True)
    with pytest.raises(
        expected_exception=FileNotFoundError,
        match="Missing zstd",
    ):
        _ = private_call(
            owner=package_build,
            name="_stage_zstd_portable",
            staging=staging,
        )
    verify_catalog_pack_rejections(
        package_build=package_build,
        staging=staging,
    )


def verify_staged_catalog_roundtrip(
    *,
    package_build: ModuleType,
    root: Path,
) -> None:
    """Validate a correct pack record against its staged pack file.

    Args:
        package_build: Imported build module.
        root: Staging root holding the pack and catalog.

    """
    pack: Path = root / "packs" / "p1.pack"
    pack.parent.mkdir(parents=True)
    data: bytes = b"pack-bytes"
    _ = pack.write_bytes(data=data)
    catalog_dir: Path = root / "catalogs"
    catalog_dir.mkdir()
    _ = (catalog_dir / "c.json").write_text(
        data=dumps(
            obj={
                "packs": {
                    "p1": {
                        "path": "packs/p1.pack",
                        "sha256": private_call(
                            owner=package_build,
                            name="_hash_file",
                            path=pack,
                        ),
                        "bytes": len(data),
                    },
                },
            },
        ),
        encoding="utf-8",
    )
    _ = private_call(
        owner=package_build,
        name="_validate_catalog_packs",
        catalog=catalog_dir / "c.json",
    )
    _ = pack.write_bytes(data=data + b"x")
    with pytest.raises(expected_exception=ValueError, match="size"):
        _ = private_call(
            owner=package_build,
            name="_validate_catalog_packs",
            catalog=catalog_dir / "c.json",
        )
    _ = pack.write_bytes(data=b"other-data")
    with pytest.raises(expected_exception=ValueError, match="hash"):
        _ = private_call(
            owner=package_build,
            name="_validate_catalog_packs",
            catalog=catalog_dir / "c.json",
        )


def make_fake_package(*, root: Path) -> Path:
    """Create a minimal staged Exactus package with bundle catalogs.

    Args:
        root: Synthetic project root.

    Returns:
        The synthetic ``exactus`` package directory.

    """
    package: Path = root / "exactus"
    catalog_dir: Path = (
        package
        / "bundle"
        / "linux"
        / "glibc"
        / "amd64"
        / "data"
        / "parts"
        / "fs"
    )
    catalog_dir.mkdir(parents=True)
    pack: Path = catalog_dir / "packs" / "p1.pack"
    pack.parent.mkdir(parents=True)
    data: bytes = b"pack-bytes"
    _ = pack.write_bytes(data=data)
    _ = (catalog_dir / "catalog.json").write_text(
        data=dumps(
            obj={
                "packs": {
                    "p1": {
                        "path": "packs/p1.pack",
                        "sha256": sha256(data=data).hexdigest(),
                        "bytes": len(data),
                    },
                },
            },
        ),
        encoding="utf-8",
    )
    _ = (package / "__init__.py").write_text(data="", encoding="utf-8")
    return package


def test_build_artifacts_stage_full_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``build_check``, ``build_dist`` and ``build_tree`` run end to end.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    package_build: ModuleType = import_module(
        name="exactus.packages.package.build",
    )
    root: Path = tmp_path / "project"
    root.mkdir()
    package: Path = make_fake_package(root=root)
    _ = (root / "marker.py").write_text(data="x = 1\n", encoding="utf-8")
    archives: Path = tmp_path / "zstd"
    archives.mkdir()
    _ = (archives / "linux-x86_64.zip").write_bytes(data=b"payload")
    dist: Path = tmp_path / "build"
    check: Path = tmp_path / "bin" / "exactus"
    monkeypatch.setattr(target=Constants, name="root", value=root)
    monkeypatch.setattr(target=Constants, name="package", value=package)
    monkeypatch.setattr(
        target=Constants,
        name="bin_zstd_portable",
        value=archives,
    )
    monkeypatch.setattr(target=Constants, name="dist", value=dist)
    monkeypatch.setattr(target=Constants, name="check", value=check)
    private_call(
        owner=package_build,
        name="build_check",
        target=check,
        kept=None,
    )
    expect_true(condition=check.is_file())
    with ZipFile(file=check) as archive:
        expect_in(member="__main__.py", container=archive.namelist())
        expect_in(member="exactus/__init__.py", container=archive.namelist())
    expect_true(condition=(tmp_path / "README.md").is_file())
    private_call(owner=package_build, name="build_dist", kept=None)
    expect_true(condition=(dist / "exactus" / "__init__.py").is_file())
    expect_true(condition=(dist / "README.md").is_file())
    tree: Path = tmp_path / "TREE.txt"
    private_call(
        owner=package_build,
        name="build_tree",
        target=tree,
        include_exactus_results=False,
    )
    expect_in(member="marker.py", container=tree.read_text(encoding="utf-8"))
    verify_staged_catalog_roundtrip(
        package_build=package_build,
        root=tmp_path / "catalog-root",
    )


def test_build_rmtree_retry_restores_permissions(tmp_path: Path) -> None:
    """``_rmtree_retry`` repairs permissions then retries removal.

    Args:
        tmp_path: Isolated filesystem root.

    """
    package_build: ModuleType = import_module(
        name="exactus.packages.package.build",
    )
    entry: Path = tmp_path / "stubborn"
    _ = (entry / "nested").mkdir(parents=True)
    _ = (entry / "nested" / "file.txt").write_text(data="x", encoding="utf-8")
    _ = (entry / "link").symlink_to(target=entry / "nested")
    removed: list[str] = []

    def record(path: str) -> None:
        """Record the retried removal path.

        Args:
            path: Path handed back to the removal operation.

        """
        removed.append(path)

    private_call(
        owner=package_build,
        name="_rmtree_retry",
        func=record,
        path=str(object=entry),
        _exc=OSError("denied"),
    )
    expect_equal(actual=removed, expected=[str(object=entry)])
    expect_true(condition=not list(entry.iterdir()))


def noop_stage(**kwargs: object) -> None:
    """Accept any keyword arguments without doing anything.

    Args:
        **kwargs: Ignored keyword arguments.

    """
    del kwargs


def test_build_main_dispatches_selected_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The build CLI resolves flags, config and target selections.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    package_build: ModuleType = import_module(
        name="exactus.packages.package.build",
    )
    calls: list[str] = []
    root: Path = tmp_path / "project"
    root.mkdir()
    _ = (root / "pyproject.toml").write_text(
        data="[tool.build]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(target=Constants, name="root", value=root)

    def make_stage_recorder(name: str) -> "Callable[..., None]":
        """Build a recorder appending the stage name for each call.

        Args:
            name: Stage name appended to ``calls``.

        Returns:
            Callable recording invocations.

        """

        def record(**kwargs: object) -> None:
            """Record one stage invocation.

            Args:
                **kwargs: Ignored stage arguments.

            """
            del kwargs
            calls.append(name)

        return record

    for name in ("build_check", "build_dist", "build_tree"):
        monkeypatch.setattr(
            target=package_build,
            name=name,
            value=make_stage_recorder(name=name),
        )
    monkeypatch.setattr(
        target=package_build,
        name="clear_conflict_copies",
        value=noop_stage,
    )
    monkeypatch.setattr(
        target=import_module(name="sys"),
        name="argv",
        value=["exactus-build", "--check", "--tree", "--no-exactus"],
    )
    main_result: object = private_call(owner=package_build, name="main")
    expect_equal(actual=main_result, expected=0)
    expect_equal(actual=calls, expected=["build_check", "build_tree"])
    calls.clear()
    monkeypatch.setattr(
        target=import_module(name="sys"),
        name="argv",
        value=["exactus-build", "--target", "amd64"],
    )
    _ = private_call(owner=package_build, name="main")
    expect_equal(actual=len(calls), expected=3)
    calls.clear()
    monkeypatch.setattr(
        target=import_module(name="sys"),
        name="argv",
        value=["exactus-build", "--check"],
    )
    _ = (root / "pyproject.toml").write_text(
        data='[tool.build]\ntargets = ["bogus"]\n',
        encoding="utf-8",
    )
    with pytest.raises(expected_exception=SystemExit):
        _ = private_call(owner=package_build, name="main")
    _ = (root / "pyproject.toml").write_text(
        data="[tool.build]\ncheck = 1\n",
        encoding="utf-8",
    )
    with pytest.raises(expected_exception=SystemExit):
        _ = private_call(owner=package_build, name="main")
    expect_equal(actual=calls, expected=[])


def test_build_parser_and_exec_target_resolution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``create_parser`` and ``--exec-target`` scope the pyz targets.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    package_build: ModuleType = import_module(
        name="exactus.packages.package.build",
    )
    kept_seen: list[frozenset[Path] | None] = []

    def fake_check(*, target: Path, kept: frozenset[Path] | None) -> None:
        """Capture the pyz kept-leaf selection.

        Args:
            target: Unused check destination.
            kept: Bundle leaves retained for the executable.

        """
        del target
        kept_seen.append(kept)

    root: Path = tmp_path / "project"
    root.mkdir()
    _ = (root / "pyproject.toml").write_text(data="", encoding="utf-8")
    monkeypatch.setattr(target=Constants, name="root", value=root)
    monkeypatch.setattr(
        target=package_build,
        name="build_check",
        value=fake_check,
    )
    monkeypatch.setattr(
        target=package_build,
        name="build_dist",
        value=noop_stage,
    )
    monkeypatch.setattr(
        target=package_build,
        name="build_tree",
        value=noop_stage,
    )
    monkeypatch.setattr(
        target=package_build,
        name="clear_conflict_copies",
        value=noop_stage,
    )
    monkeypatch.setattr(
        target=import_module(name="sys"),
        name="argv",
        value=[
            "exactus-build",
            "--check",
            "--target",
            "all",
            "--exec-target",
            "musl",
        ],
    )
    _ = private_call(owner=package_build, name="main")
    expect_equal(actual=len(kept_seen), expected=1)
    kept_exec: frozenset[Path] | None = kept_seen[0]
    if kept_exec is None:
        fail(message="expected a kept-leaf selection")
    expect_true(condition=Path("bundle/linux/musl/amd64") in kept_exec)


def test_tool_version_resolves_each_dispatch_kind() -> None:
    """Python, node, binary, and probe tools map to package versions."""
    versions: dict[str, dict[str, str]] = {
        "python": {"ruff": "0.17.3", "basedpyright": "1.40.2"},
        "node": {"eslint": "10.13.0"},
    }
    expect_equal(
        actual=private_result(
            owner=import_module(name="exactus.packages.package.build"),
            name="_tool_version",
            kind=str,
            tool="ruff",
            spec={"kind": "python-module", "target": "ruff"},
            versions=versions,
        ),
        expected="0.17.3",
    )
    expect_equal(
        actual=private_result(
            owner=import_module(name="exactus.packages.package.build"),
            name="_tool_version",
            kind=str,
            tool="basedpyright",
            spec={
                "kind": "binary",
                "module": "basedpyright",
                "target": "python/bin/basedpyright",
            },
            versions=versions,
        ),
        expected="1.40.2",
    )
    expect_equal(
        actual=private_result(
            owner=import_module(name="exactus.packages.package.build"),
            name="_tool_version",
            kind=str,
            tool="eslint",
            spec={"kind": "js-entry", "target": "eslint/bin/eslint.js"},
            versions=versions,
        ),
        expected="10.13.0",
    )
    expect_equal(
        actual=private_result(
            owner=import_module(name="exactus.packages.package.build"),
            name="_tool_version",
            kind=str,
            tool="ruff",
            spec={"kind": "probe", "target": "from ruff import main;main()"},
            versions=versions,
        ),
        expected="0.17.3",
    )


def test_tool_version_prefix_matches_dist_names() -> None:
    """Module names prefix-match longer dist names when needed."""
    versions: dict[str, dict[str, str]] = {
        "python": {"nodejs_wheel_binaries": "24.19.0"},
        "node": {},
    }
    expect_equal(
        actual=private_result(
            owner=import_module(name="exactus.packages.package.build"),
            name="_tool_version",
            kind=str,
            tool="nodejs_wheel",
            spec={"kind": "python-module", "target": "nodejs_wheel"},
            versions=versions,
        ),
        expected="24.19.0",
    )
    expect_equal(
        actual=private_result(
            owner=import_module(name="exactus.packages.package.build"),
            name="_tool_version",
            kind=str,
            tool="zstd",
            spec={"kind": "binary", "target": "zstd/bin/zstd"},
            versions=versions,
        ),
        expected="",
    )


def test_catalog_tools_reads_component_metadata(tmp_path: Path) -> None:
    """A catalog's declared tools resolve against its version map.

    Args:
        tmp_path: Isolated filesystem root.

    """
    catalog: Path = tmp_path / "catalog.json"
    _ = catalog.write_text(
        data=dumps(
            obj={
                "components": {
                    "demo": {
                        "metadata": {
                            "tools": {
                                "demo-tool": {
                                    "kind": "python-module",
                                    "target": "demo_pkg",
                                },
                            },
                            "versions": {
                                "python": {"demo_pkg": "1.2.3"},
                                "node": {},
                            },
                        },
                    },
                },
            },
        ),
        encoding="utf-8",
    )
    tools: dict[str, str] = cast(
        typ="dict[str, str]",
        val=private_result(
            owner=import_module(name="exactus.packages.package.build"),
            name="_catalog_tools",
            kind=dict,
            catalog=catalog,
        ),
    )
    expect_equal(actual=tools, expected={"demo-tool": "1.2.3"})
    missing: Path = tmp_path / "absent.json"
    absent_tools: dict[str, str] = cast(
        typ="dict[str, str]",
        val=private_result(
            owner=import_module(name="exactus.packages.package.build"),
            name="_catalog_tools",
            kind=dict,
            catalog=missing,
        ),
    )
    expect_equal(actual=absent_tools, expected={})


def test_write_manifest_lists_targets_and_tools(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``MANIFEST.md`` records the artifact and its bundled tools.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    package: Path = tmp_path / "pkg"
    catalog: Path = (
        package
        / "bundle"
        / "macos"
        / "arm64"
        / "data"
        / "parts"
        / "fs"
        / "catalog.json"
    )
    catalog.parent.mkdir(parents=True)
    _ = catalog.write_text(
        data=dumps(
            obj={
                "components": {
                    "demo": {
                        "metadata": {
                            "tools": {
                                "ruff": {
                                    "kind": "python-module",
                                    "target": "ruff",
                                },
                            },
                            "versions": {
                                "python": {"ruff": "0.17.3"},
                                "node": {},
                            },
                        },
                    },
                },
            },
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(target=Constants, name="package", value=package)
    monkeypatch.setattr(target=Constants, name="root", value=tmp_path)
    target: Path = tmp_path / "bin" / "exactus_all" / "exactus"
    target.parent.mkdir(parents=True)
    _ = target.write_bytes(data=b"pyz-bytes")
    _ = private_call(
        owner=import_module(name="exactus.packages.package.build"),
        name="_write_manifest",
        target=target,
        kept=frozenset({Path("bundle/macos/arm64")}),
        self_test=False,
    )
    rendered: str = (target.parent / "MANIFEST.md").read_text(encoding="utf-8")
    expect_in(member="- `macos-arm64`", container=rendered)
    expect_in(member="| `ruff` | `0.17.3` |", container=rendered)
    expect_in(member="Self-test | disabled", container=rendered)


def test_closure_rejects_missing_component() -> None:
    """Dependency resolution rejects components outside the catalog."""
    with pytest.raises(expected_exception=FormatError, match="Missing"):
        _ = closure(
            catalog=cast(typ="Catalog", val={"components": {}}),
            name="absent",
        )


def test_closure_rejects_cyclic_dependencies() -> None:
    """A dependency cycle raises ``FormatError`` instead of looping."""
    catalog: Catalog = cast(
        typ="Catalog",
        val={
            "components": {
                "alpha": {"metadata": {"requires": ["beta"]}},
                "beta": {"metadata": {"requires": ["alpha"]}},
            },
        },
    )
    with pytest.raises(expected_exception=FormatError, match="cyclic"):
        _ = closure(catalog=catalog, name="alpha")


def test_closure_orders_dependencies_first() -> None:
    """Resolved closures list requirements before dependents."""
    catalog: Catalog = cast(
        typ="Catalog",
        val={
            "components": {
                "app": {"metadata": {"requires": ["lib"]}},
                "lib": {"metadata": {"requires": []}},
            },
        },
    )
    expect_equal(
        actual=closure(catalog=catalog, name="app"),
        expected=["lib", "app"],
    )


def test_usable_cache_root_rejects_symlink(tmp_path: Path) -> None:
    """Symlinked cache roots are never trusted.

    Args:
        tmp_path: Isolated filesystem root.

    """
    real: Path = tmp_path / "real"
    real.mkdir()
    link: Path = tmp_path / "link"
    link.symlink_to(target=real)
    expect_true(
        condition=not private_result(
            owner=import_module(
                name="exactus.packages.package.partition_launcher",
            ),
            name="_usable_cache_root",
            kind=bool,
            root=link,
        ),
    )


def test_usable_cache_root_rejects_lock_dir(tmp_path: Path) -> None:
    """A ``.lock`` directory blocks cache publication.

    Args:
        tmp_path: Isolated filesystem root.

    """
    root: Path = tmp_path / "cache"
    (root / ".lock").mkdir(parents=True)
    expect_true(
        condition=not private_result(
            owner=import_module(
                name="exactus.packages.package.partition_launcher",
            ),
            name="_usable_cache_root",
            kind=bool,
            root=root,
        ),
    )


def test_usable_cache_root_accepts_writable_dir(tmp_path: Path) -> None:
    """A plain writable directory hosts the lock file.

    Args:
        tmp_path: Isolated filesystem root.

    """
    root: Path = tmp_path / "cache"
    expect_true(
        condition=private_result(
            owner=import_module(
                name="exactus.packages.package.partition_launcher",
            ),
            name="_usable_cache_root",
            kind=bool,
            root=root,
        ),
        message="writable root rejected",
    )
