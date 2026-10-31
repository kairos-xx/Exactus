#!/usr/bin/env python3
# Copyright (c) 2026
"""Build incremental partitioned offline tool bundles and catalogs."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from errno import ENOTEMPTY
from inspect import getsource
from json import dumps, loads
from os import environ, getpid
from os.path import relpath
from pathlib import Path
from platform import libc_ver, machine, system
from shutil import copyfile, rmtree, which
from subprocess import run
from sys import argv
from sys import path as sys_path
from tempfile import TemporaryDirectory
from textwrap import dedent
from threading import Event, Thread
from time import monotonic, sleep
from tomllib import load as load_toml
from typing import (
    TYPE_CHECKING,
    ClassVar,
    Final,
    Literal,
    Protocol,
    cast,
    final,
)
from urllib.error import HTTPError, URLError
from urllib.parse import ParseResult, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4
from zipfile import ZipFile

if __package__ in (None, ""):
    sys_path.insert(0, str(object=Path(__file__).resolve().parents[3]))
    sys_path.insert(0, str(object=Path(__file__).resolve().parents[1]))
from exactus.bundle.content import write_content
from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.tools.common.conflict_copies import clear_conflict_copies

from .process_control import new_run_id
from .progress import RunDocument, RunItem, utc_now

if TYPE_CHECKING or __package__:
    from .partition_fs import (
        Catalog,
        ChunkingConfig,
        FormatError,
        PartitionStore,
        Recipe,
        RecipeScanner,
        atomic_bytes,
        canonical,
        hash_file,
        identity,
        load_catalog,
        load_recipe,
        recipe_identity,
        write_delta,
    )
    from .partition_fs import Json as PartitionJson
    from .partition_launcher import cache_lock
    from .readmes import write_directory_readmes
else:
    from partition_fs import (
        Catalog,
        ChunkingConfig,
        FormatError,
        PartitionStore,
        Recipe,
        RecipeScanner,
        atomic_bytes,
        canonical,
        hash_file,
        identity,
        load_catalog,
        load_recipe,
        recipe_identity,
        write_delta,
    )
    from partition_fs import Json as PartitionJson
    from partition_launcher import cache_lock
    from readmes import write_directory_readmes
if TYPE_CHECKING or bool(__package__):
    from exactus.packages.zstd_portable import Constants as ZstdConstants
    from exactus.packages.zstd_portable import (
        __file__ as zstd_portable___file__,
    )
    from exactus.packages.zstd_portable import export_package
else:
    from zstd_portable import Constants as ZstdConstants
    from zstd_portable import __file__ as zstd_portable___file__
    from zstd_portable import export_package
if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from urllib.response import addinfourl
type Json = bool | int | float | str | list[Json] | dict[str, Json] | None
type ToolKind = Literal["python-module", "js-entry", "binary", "probe"]


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolSpec:
    """One invocable tool a component archive provides.

    Attributes:
        name: Command name accepted by the generated launcher.
        kind: Invocation style: ``python-module`` runs ``python -m``,
            ``js-entry`` runs ``node`` on a ``js/node_modules`` script,
            ``binary`` runs an executable inside the component (falling
            back to ``module`` when the file is absent), and ``probe``
            runs ``python -c`` on the target source.
        target: Module name, JS entry path, binary path relative to the
            component root, or probe source.
        module: Fallback module for ``binary`` tools (``python -m``).

    """

    name: str
    kind: ToolKind
    target: str
    module: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class ComponentSpec:
    """One logical filesystem component sharing a dependency set.

    Attributes:
        name: Stable logical component identifier in the catalog.
        tools: Invocable tools declared in component metadata.
        python_packages: pip packages bundled under ``python/``.
        node_packages: npm packages bundled under
            ``js/node_modules/``.
        requires: Component names that must also be present; selecting
            this component selects its requirements transitively.
        env: Extra environment entries merged into component
            metadata; values are paths relative to the component root
            (``../`` reaches sibling components in the cache).
        optional: Whether the component may be dropped without breaking
            required tools.
        node_runtime: Stage the Node.js distribution into this
            component.
        browsers: Stage Playwright browsers into this component
            (requires the ``playwright`` component's catalog at build
            time).
        python_extras: Append the target's platform-extra Python
            packages (for example ``msvc-runtime`` on Windows).
        zstd_cli: Stage the portable compression package for this target.


    """

    name: str
    tools: tuple[ToolSpec, ...] = ()
    python_packages: tuple[str, ...] = ()
    node_packages: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    env: tuple[tuple[str, tuple[str, ...]], ...] = ()
    optional: bool = True
    node_runtime: bool = False
    browsers: bool = False
    python_extras: bool = False
    zstd_cli: bool = False


@dataclass(frozen=True, slots=True)
class BrowserArchive:
    """One Playwright browser download for a target.

    Attributes:
        name: ``browsers.json`` catalog name.
        cdn_file: Playwright builds CDN archive filename; always a valid
            fallback download.
        cft_file: Chrome-for-Testing archive filename, tried first when
            the target has CFT builds; ``None`` for CDN-only browsers.

    """

    name: str
    cdn_file: str
    cft_file: str | None = None


@dataclass(frozen=True, slots=True)
class BrowserDistribution:
    """Playwright browser archives and payload pruning for a target.

    Attributes:
        archives: Downloads looked up in the bundled ``browsers.json``
            catalog; empty when the platform has no Playwright browser
            builds (musl and Windows ARM64 targets rely on a system
            Chromium via ``executable_path``).
        cft_dir: Chrome-for-Testing platform directory, or ``None`` when
            CFT publishes no build for the target. CFT covers
            ``linux64``, ``mac-x64``, ``mac-arm64``, ``win32``, ``win64``.
        prune_names: File and directory names deleted anywhere inside
            ``playwright-browsers`` (DRM, crash reporting, helpers).
        locale_suffix: Locale entry suffix, ``.pak`` or ``.lproj``.
        locale_parent: Directory name locale entries must live under;
            ``None`` matches the suffix anywhere (macOS ``.lproj``).
        locale_keep: Locale entry names retained.

    """

    archives: tuple[BrowserArchive, ...]
    cft_dir: str | None
    prune_names: frozenset[str]
    locale_suffix: str
    locale_parent: str | None
    locale_keep: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NodeDistribution:
    """Node.js runtime source and on-disk layout for a target.

    Attributes:
        suffix: Distribution archive suffix such as ``linux-x64``.
        mirror: Download mirror base URL; musl builds are published on
            the unofficial-builds mirror only.
        archive: Archive format: ``tar.xz``, ``tar.gz``, or ``zip``.
        binary: Runtime executable path inside the extracted root.
        npm: npm launcher path inside the extracted root.
        prune: Distribution paths deleted after ``npm install``.

    """

    suffix: str
    mirror: str
    archive: str
    binary: str
    npm: str
    prune: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Distribution:
    """Payload layout shared by every target.

    Attributes:
        status_name: Live heartbeat filename inside the parts directory;
            an informational ``exactus-run/v1`` document readers may watch
            while a build runs.

    """

    status_name: str = "@activity.json"


@dataclass(frozen=True, slots=True)
class BuildTarget:
    """Target platform description driving every build step.

    Attributes:
        name: Target identifier such as ``linux-glibc-amd64``.
        os: Operating system family.
        arch: CPU architecture.
        libc: C library for Linux targets; ``None`` elsewhere.
        node: Node.js runtime source and layout.
        wheel_platforms: pip ``--platform`` wheel tags, preferred first.
        browsers: Playwright browser archives and pruning rules.
        python_extras: Additional pip packages required by this OS only.

    """

    name: str
    os: OperatingSystem
    arch: Architecture
    libc: Libc | None
    node: NodeDistribution
    wheel_platforms: tuple[str, ...]
    browsers: BrowserDistribution
    python_extras: tuple[str, ...] = ()


def _mac_browsers(*, arm64: bool) -> BrowserDistribution:
    """Playwright browser archives for a macOS target.

    Args:
        arm64: Whether the target is Apple Silicon.

    Returns:
        Browser distribution for the requested chip.

    """
    flavor: str = "arm64" if arm64 else "x64"
    suffix: str = f"-mac-{flavor}" if arm64 else "-mac"
    return BrowserDistribution(
        archives=(
            BrowserArchive(
                name="chromium",
                cdn_file=f"chromium{suffix}.zip",
                cft_file=f"chrome-mac-{flavor}.zip",
            ),
            BrowserArchive(
                name="chromium-headless-shell",
                cdn_file=f"chromium-headless-shell{suffix}.zip",
                cft_file=f"chrome-headless-shell-mac-{flavor}.zip",
            ),
            BrowserArchive(name="ffmpeg", cdn_file=f"ffmpeg{suffix}.zip"),
        ),
        cft_dir=f"mac-{flavor}",
        prune_names=frozenset({"WidevineCdm", "chrome_crashpad_handler"}),
        locale_suffix=".lproj",
        locale_parent=None,
        locale_keep=("en.lproj", "en_US.lproj", "en_GB.lproj", "Base.lproj"),
    )


@final
class Constants:
    """Group module-level constants.

    Attributes:
        size_base: Grouped module constant.
        heartbeat_seconds: Grouped module constant.
        node_mirror: Grouped module constant.
        node_mirror_unofficial: Grouped module constant.
        cft_cdn: Grouped module constant.
        node_prune_posix: Grouped module constant.
        node_prune_windows: Grouped module constant.
        browser_prune_names: Grouped module constant.
        build_steps: Grouped module constant.
        fetch_schemes: Grouped module constant.
        fetch_retryable: Grouped module constant.
        fetch_chunk: Grouped module constant.
        fetch_user_agent: Grouped module constant.
        max_line_length: Grouped module constant.
        zstd_probe: Grouped module constant.
        browser_probe: Grouped module constant.
        chromium_patterns: Grouped module constant.
        headless_patterns: Grouped module constant.
        ffmpeg_patterns: Grouped module constant.
        components: Grouped module constant.
        groups: Grouped module constant.
        tool_component: Grouped module constant.
        optional_components: Grouped module constant.
        mandatory_components: Grouped module constant.
        linux_browsers: Grouped module constant.
        windows_browsers: Grouped module constant.
        no_browsers: Grouped module constant.
        mac_wheels_arm64: Grouped module constant.
        mac_wheels_x64: Grouped module constant.
        targets: Grouped module constant.
        target_groups: Grouped module constant.
        distribution: Grouped module constant.
        target_unavailable: Grouped module constant.

    """

    size_base: Final[int] = 1000
    heartbeat_seconds: Final[float] = 1.0
    node_mirror: Final[str] = "https://nodejs.org/dist"
    node_mirror_unofficial: Final[str] = (
        "https://unofficial-builds.nodejs.org/download/release"
    )
    cft_cdn: Final[str] = (
        "https://storage.googleapis.com/chrome-for-testing-public"
    )
    node_prune_posix: Final[tuple[str, ...]] = (
        "bin/npm",
        "bin/npx",
        "bin/corepack",
        "include",
        "share",
        "lib/node_modules/npm",
        "lib/node_modules/corepack",
    )
    node_prune_windows: Final[tuple[str, ...]] = (
        "npm",
        "npm.cmd",
        "npm.ps1",
        "npx",
        "npx.cmd",
        "npx.ps1",
        "corepack",
        "corepack.cmd",
        "corepack.ps1",
        "node_etw_provider.man",
        "nodevars.bat",
        "install_tools.bat",
        "CHANGELOG.md",
        "README.md",
        "node_modules/npm",
        "node_modules/corepack",
    )
    browser_prune_names: Final[frozenset[str]] = frozenset(
        {
            "WidevineCdm",
            "MEIPreload",
            "PrivacySandboxAttestationsPreloaded",
            "chrome_crashpad_handler",
            "crashpad_handler.exe",
            "notification_helper.exe",
            "reading_mode_gdocs_helper",
            "reading_mode_gdocs_helper_manifest.json",
        },
    )
    build_steps: Final[tuple[str, ...]] = (
        "fingerprint",
        "stage",
        "scan",
        "membership",
        "pack",
        "catalog",
        "launcher",
        "delta",
    )
    fetch_schemes: Final[frozenset[str]] = frozenset({"http", "https"})
    fetch_retryable: Final[frozenset[int]] = frozenset(
        {408, 425, 429, 500, 502, 503, 504},
    )
    fetch_chunk: Final[int] = 1024 * 1024
    fetch_user_agent: Final[str] = "exactus"
    max_line_length: Final[int] = 79
    zstd_probe: Final[str] = (
        "import subprocess,sys;from pathlib import Path;from platform "
        "import machine,system;from tempfile import gettempdir;from zstd"
        "_portable import export_binary;p=export_binary(os"
        "_name=system().lower(),machine=machine(),target=Path(gettempdir()"
        ")/'exactus-zstd-cli');import "
        "os;sys.exit(subprocess.run([str(p),*sys.argv[1:]]).returncode)"
    )
    browser_probe: Final[str] = (
        "import glob,os,subprocess,sys;b=os.environ['PLAYWRIGHT_BROWSERS"
        "_PATH'];c=[x for q in '{0}'.split(',') for x in "
        "sorted(glob.glob(os.path.join(b,q),recursive=True)) if "
        "os.path.isfile(x)];sys.exit(subprocess.run([c[0],*sys.argv[1:]])."
        "returncode) if c else sys.exit('no bundled browser executable "
        "found')"
    )
    chromium_patterns: Final[str] = (
        "chromium-*/chrome-linux/chrome,chromium-*/chrome-mac*"
        "/Chromium.app/Contents/MacOS/Chromium,chromium-*/chrome-mac*"
        "/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for "
        "Testing,chromium-*/chrome-win*/chrome.exe,chromium_headless_shell"
        "-*/chrome-headless-shell-*/chrome-headless-shell,chromium"
        "_headless_shell-*/chrome-headless-shell-*/headless_shell,chromium"
        "_headless_shell-*/chrome-linux/headless_shell,chromium_headless"
        "_shell-*/chrome-win*/headless_shell.exe"
    )
    headless_patterns: Final[str] = (
        "chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell,chromium_headless_shell-*/chrome-headless-shell-*/headless_shell,chromium_headless_shell-*/chrome-linux/headless_shell,chromium_headless_shell-*/chrome-win*/headless_shell.exe,chromium-*/chrome-linux/chrome,chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium,chromium-*/chrome-win*/chrome.exe"
    )
    ffmpeg_patterns: Final[str] = (
        "ffmpeg-*/ffmpeg-linux,ffmpeg-*/ffmpeg-mac,ffmpeg-*/ffmpeg-mac-arm64,ffmpeg-*/ffmpeg-win64.exe,ffmpeg-*/ffmpeg.exe,ffmpeg-*/ffmpeg"
    )
    components: Final[dict[str, ComponentSpec]] = {
        "zstd-cli": ComponentSpec(
            name="zstd-cli",
            optional=False,
            zstd_cli=True,
            env=(("PYTHONPATH", (".",)),),
            tools=(
                ToolSpec(name="zstd", kind="probe", target=zstd_probe),
                ToolSpec(name="zstd-cli", kind="probe", target=zstd_probe),
            ),
        ),
        "node": ComponentSpec(
            name="node",
            optional=False,
            node_runtime=True,
            tools=(ToolSpec(name="node", kind="binary", target="bin/node"),),
        ),
        "eslint_htmlhint_jslint_prettier_stylelint_tsc": ComponentSpec(
            name="eslint_htmlhint_jslint_prettier_stylelint_tsc",
            optional=False,
            node_packages=(
                "eslint",
                "eslint-plugin-jsdoc",
                "htmlhint",
                "jslint",
                "prettier",
                "stylelint",
                "typescript",
            ),
            requires=("node",),
            tools=(
                ToolSpec(
                    name="eslint",
                    kind="js-entry",
                    target="eslint/bin/eslint.js",
                ),
                ToolSpec(
                    name="tsc",
                    kind="js-entry",
                    target="typescript/bin/tsc",
                ),
                ToolSpec(
                    name="jslint",
                    kind="js-entry",
                    target="jslint/bin/jslint.js",
                ),
                ToolSpec(
                    name="stylelint",
                    kind="js-entry",
                    target="stylelint/bin/stylelint.mjs",
                ),
                ToolSpec(
                    name="htmlhint",
                    kind="js-entry",
                    target="htmlhint/bin/htmlhint",
                ),
                ToolSpec(
                    name="prettier",
                    kind="js-entry",
                    target="prettier/bin/prettier.cjs",
                ),
                ToolSpec(
                    name="acorn",
                    kind="js-entry",
                    target="acorn/bin/acorn",
                ),
                ToolSpec(
                    name="cssesc",
                    kind="js-entry",
                    target="cssesc/bin/cssesc",
                ),
                ToolSpec(
                    name="js-yaml",
                    kind="js-entry",
                    target="js-yaml/bin/js-yaml.js",
                ),
                ToolSpec(
                    name="nanoid",
                    kind="js-entry",
                    target="nanoid/bin/nanoid.cjs",
                ),
                ToolSpec(
                    name="node-which",
                    kind="js-entry",
                    target="which/bin/node-which",
                ),
                ToolSpec(
                    name="nopt",
                    kind="js-entry",
                    target="nopt/bin/nopt.js",
                ),
                ToolSpec(
                    name="semver",
                    kind="js-entry",
                    target="semver/bin/semver.js",
                ),
                ToolSpec(
                    name="tsserver",
                    kind="js-entry",
                    target="typescript/bin/tsserver",
                ),
                ToolSpec(
                    name="typescript",
                    kind="js-entry",
                    target="typescript/bin/tsc",
                ),
                ToolSpec(
                    name="which",
                    kind="js-entry",
                    target="which/bin/node-which",
                ),
            ),
        ),
        "basedpyright_coverage_pyrefly_pytest_ruff": ComponentSpec(
            name="basedpyright_coverage_pyrefly_pytest_ruff",
            optional=False,
            python_extras=True,
            python_packages=(
                "basedpyright",
                "coverage",
                "iniconfig",
                "nodejs_wheel_binaries",
                "packaging",
                "pluggy",
                "pygments",
                "pyrefly",
                "pytest",
                "ruff",
            ),
            requires=("node",),
            tools=(
                ToolSpec(
                    name="ruff",
                    kind="binary",
                    target="python/bin/ruff",
                    module="ruff",
                ),
                ToolSpec(
                    name="basedpyright",
                    kind="python-module",
                    target="basedpyright",
                ),
                ToolSpec(
                    name="pyrefly",
                    kind="binary",
                    target="python/bin/pyrefly",
                    module="pyrefly",
                ),
                ToolSpec(name="pytest", kind="python-module", target="pytest"),
                ToolSpec(
                    name="coverage",
                    kind="python-module",
                    target="coverage",
                ),
                ToolSpec(
                    name="basedpyright-langserver",
                    kind="probe",
                    target="from basedpyright.langserver import main;main()",
                ),
                ToolSpec(
                    name="coverage3",
                    kind="python-module",
                    target="coverage",
                ),
                ToolSpec(
                    name="coverage-3.13",
                    kind="python-module",
                    target="coverage",
                ),
                ToolSpec(
                    name="nodejs_wheel",
                    kind="python-module",
                    target="nodejs_wheel",
                ),
                ToolSpec(
                    name="nodejs_wheel_binaries",
                    kind="python-module",
                    target="nodejs_wheel",
                ),
                ToolSpec(
                    name="py.test",
                    kind="python-module",
                    target="pytest",
                ),
                ToolSpec(
                    name="pygmentize",
                    kind="python-module",
                    target="pygments",
                ),
                ToolSpec(
                    name="pygments",
                    kind="python-module",
                    target="pygments",
                ),
            ),
        ),
        "playwright": ComponentSpec(
            name="playwright",
            python_packages=(
                "greenlet",
                "playwright",
                "pyee",
                "typing_extensions",
            ),
            node_packages=("playwright",),
            requires=("node",),
            env=(
                (
                    "PLAYWRIGHT_BROWSERS_PATH",
                    ("../chromium/playwright-browsers",),
                ),
            ),
            tools=(
                ToolSpec(
                    name="playwright",
                    kind="python-module",
                    target="playwright",
                ),
            ),
        ),
        "chromium": ComponentSpec(
            name="chromium",
            requires=("playwright",),
            browsers=True,
            tools=(
                ToolSpec(
                    name="chromium",
                    kind="probe",
                    target=browser_probe.format(chromium_patterns),
                ),
                ToolSpec(
                    name="chromium-headless-shell",
                    kind="probe",
                    target=browser_probe.format(headless_patterns),
                ),
                ToolSpec(
                    name="ffmpeg",
                    kind="probe",
                    target=browser_probe.format(ffmpeg_patterns),
                ),
            ),
        ),
        "defusedxml": ComponentSpec(
            name="defusedxml",
            optional=False,
            python_packages=("defusedxml",),
        ),
        "build_twine": ComponentSpec(
            name="build_twine",
            python_packages=(
                "build",
                "certifi",
                "charset_normalizer",
                "docutils",
                "id",
                "idna",
                "jaraco.classes",
                "jaraco_context",
                "jaraco_functools",
                "keyring",
                "markdown_it_py",
                "mdurl",
                "more_itertools",
                "nh3",
                "packaging",
                "pygments",
                "pyproject_hooks",
                "readme_renderer",
                "requests",
                "requests_toolbelt",
                "rfc3986",
                "rich",
                "twine",
                "urllib3",
            ),
            tools=(
                ToolSpec(name="build", kind="python-module", target="build"),
                ToolSpec(name="twine", kind="python-module", target="twine"),
                ToolSpec(
                    name="certifi",
                    kind="python-module",
                    target="certifi",
                ),
                ToolSpec(
                    name="charset_normalizer",
                    kind="python-module",
                    target="charset_normalizer",
                ),
                ToolSpec(
                    name="docutils",
                    kind="python-module",
                    target="docutils",
                ),
                ToolSpec(name="id", kind="python-module", target="id"),
                ToolSpec(name="idna", kind="python-module", target="idna"),
                ToolSpec(
                    name="keyring",
                    kind="python-module",
                    target="keyring",
                ),
                ToolSpec(
                    name="normalizer",
                    kind="python-module",
                    target="charset_normalizer",
                ),
                ToolSpec(
                    name="readme_renderer",
                    kind="python-module",
                    target="readme_renderer",
                ),
                ToolSpec(name="rich", kind="python-module", target="rich"),
                ToolSpec(
                    name="markdown-it",
                    kind="probe",
                    target="from markdown_it.cli.parse import main;main()",
                ),
                ToolSpec(
                    name="markdown_it_py",
                    kind="probe",
                    target="from markdown_it.cli.parse import main;main()",
                ),
                ToolSpec(
                    name="pyproject-build",
                    kind="probe",
                    target=(
                        "from build.__main__ import entrypoint;entrypoint()"
                    ),
                ),
                ToolSpec(
                    name="rst2html",
                    kind="probe",
                    target="from docutils.core import rst2html;rst2html()",
                ),
                ToolSpec(
                    name="rst2html4",
                    kind="probe",
                    target="from docutils.core import rst2html4;rst2html4()",
                ),
                ToolSpec(
                    name="rst2html5",
                    kind="probe",
                    target="from docutils.core import rst2html5;rst2html5()",
                ),
                ToolSpec(
                    name="rst2latex",
                    kind="probe",
                    target="from docutils.core import rst2latex;rst2latex()",
                ),
                ToolSpec(
                    name="rst2man",
                    kind="probe",
                    target="from docutils.core import rst2man;rst2man()",
                ),
                ToolSpec(
                    name="rst2odt",
                    kind="probe",
                    target="from docutils.core import rst2odt;rst2odt()",
                ),
                ToolSpec(
                    name="rst2pseudoxml",
                    kind="probe",
                    target=(
                        "from docutils.core import "
                        "rst2pseudoxml;rst2pseudoxml()"
                    ),
                ),
                ToolSpec(
                    name="rst2s5",
                    kind="probe",
                    target="from docutils.core import rst2s5;rst2s5()",
                ),
                ToolSpec(
                    name="rst2xetex",
                    kind="probe",
                    target="from docutils.core import rst2xetex;rst2xetex()",
                ),
                ToolSpec(
                    name="rst2xml",
                    kind="probe",
                    target="from docutils.core import rst2xml;rst2xml()",
                ),
            ),
        ),
        "fastapi_httpx_httpx2_mcp_pydantic_uvicorn": ComponentSpec(
            name="fastapi_httpx_httpx2_mcp_pydantic_uvicorn",
            python_packages=(
                "annotated_doc",
                "annotated_types",
                "anyio",
                "attrs",
                "certifi",
                "cffi",
                "click",
                "cryptography",
                "fastapi",
                "h11",
                "httpcore",
                "httpcore2",
                "httpx",
                "httpx2",
                "idna",
                "jsonschema",
                "jsonschema_specifications",
                "mcp",
                "mcp_types",
                "opentelemetry_api",
                "pycparser",
                "pydantic",
                "pydantic_core",
                "pyjwt",
                "python_dotenv",
                "python_multipart",
                "referencing",
                "rpds_py",
                "shellingham",
                "sse_starlette",
                "starlette",
                "truststore",
                "typer",
                "typing_extensions",
                "typing_inspection",
                "uvicorn",
            ),
            tools=(
                ToolSpec(
                    name="exactus-mcp",
                    kind="python-module",
                    target="exactus.packages.exactus_mcp",
                ),
                ToolSpec(
                    name="exactus-mcp-wakeup",
                    kind="python-module",
                    target="exactus.packages.exactus_mcp.wakeup_cli",
                ),
                ToolSpec(
                    name="uvicorn",
                    kind="python-module",
                    target="uvicorn",
                ),
                ToolSpec(
                    name="jsonschema",
                    kind="python-module",
                    target="jsonschema",
                ),
                ToolSpec(
                    name="httpx2",
                    kind="probe",
                    target="from httpx2._main import main;main()",
                ),
                ToolSpec(
                    name="mcp",
                    kind="probe",
                    target="from mcp.cli import app;app()",
                ),
            ),
        ),
        "hypothesis_mutmut": ComponentSpec(
            name="hypothesis_mutmut",
            python_packages=(
                "click",
                "coverage",
                "hypothesis",
                "iniconfig",
                "libcst",
                "linkify_it_py",
                "markdown_it_py",
                "mdit_py_plugins",
                "mdurl",
                "mutmut",
                "packaging",
                "platformdirs",
                "pluggy",
                "pygments",
                "pytest",
                "pyyaml",
                "rich",
                "setproctitle",
                "sortedcontainers",
                "textual",
                "typing_extensions",
            ),
            tools=(
                ToolSpec(name="mutmut", kind="python-module", target="mutmut"),
                ToolSpec(
                    name="platformdirs",
                    kind="python-module",
                    target="platformdirs",
                ),
            ),
        ),
        "jinja2": ComponentSpec(
            name="jinja2",
            python_packages=("jinja2", "markupsafe"),
            tools=(
                ToolSpec(
                    name="jinja2",
                    kind="probe",
                    target=(
                        "import jinja2; print(f'Jinja2 {jinja2.__version__}')"
                    ),
                ),
            ),
        ),
        "pillow": ComponentSpec(
            name="pillow",
            python_packages=("pillow",),
            tools=(
                ToolSpec(
                    name="pillow",
                    kind="probe",
                    target="import PIL; print(f'Pillow {PIL.__version__}')",
                ),
            ),
        ),
        "psutil": ComponentSpec(name="psutil", python_packages=("psutil",)),
        "tree-sitter_tree-sitter-language-pack": ComponentSpec(
            name="tree-sitter_tree-sitter-language-pack",
            python_packages=("tree-sitter", "tree-sitter-language-pack"),
        ),
    }
    groups: Final[dict[str, tuple[str, ...]]] = {
        "browser": ("playwright", "chromium"),
        "docs": ("jinja2", "pillow"),
        "imaging": ("pillow",),
        "parsing": ("tree-sitter_tree-sitter-language-pack",),
        "publishing": ("build_twine",),
        "runtime": ("node",),
        "system": ("psutil",),
        "testing": ("hypothesis_mutmut",),
        "web": ("fastapi_httpx_httpx2_mcp_pydantic_uvicorn",),
    }
    tool_component: Final[dict[str, str]] = {
        tool.name: name
        for name, spec in components.items()
        for tool in spec.tools
    }
    optional_components: Final[tuple[str, ...]] = tuple(
        (name for name, spec in components.items() if spec.optional),
    )
    mandatory_components: Final[frozenset[str]] = frozenset({"zstd-cli"})
    linux_browsers: Final[BrowserDistribution] = BrowserDistribution(
        archives=(
            BrowserArchive(
                name="chromium",
                cdn_file="chromium-linux.zip",
                cft_file="chrome-linux64.zip",
            ),
            BrowserArchive(
                name="chromium-headless-shell",
                cdn_file="chromium-headless-shell-linux.zip",
                cft_file="chrome-headless-shell-linux64.zip",
            ),
            BrowserArchive(name="ffmpeg", cdn_file="ffmpeg-linux.zip"),
        ),
        cft_dir="linux64",
        prune_names=browser_prune_names,
        locale_suffix=".pak",
        locale_parent="locales",
        locale_keep=("en-US.pak", "en-GB.pak"),
    )
    windows_browsers: Final[BrowserDistribution] = BrowserDistribution(
        archives=(
            BrowserArchive(
                name="chromium",
                cdn_file="chromium-win64.zip",
                cft_file="chrome-win64.zip",
            ),
            BrowserArchive(
                name="chromium-headless-shell",
                cdn_file="chromium-headless-shell-win64.zip",
                cft_file="chrome-headless-shell-win64.zip",
            ),
            BrowserArchive(name="ffmpeg", cdn_file="ffmpeg-win64.zip"),
        ),
        cft_dir="win64",
        prune_names=browser_prune_names,
        locale_suffix=".pak",
        locale_parent="locales",
        locale_keep=("en-US.pak", "en-GB.pak"),
    )
    no_browsers: Final[BrowserDistribution] = BrowserDistribution(
        archives=(),
        cft_dir=None,
        prune_names=frozenset(),
        locale_suffix=".pak",
        locale_parent=None,
        locale_keep=(),
    )
    mac_wheels_arm64: Final[tuple[str, ...]] = (
        "macosx_14_0_arm64",
        "macosx_13_0_arm64",
        "macosx_12_0_arm64",
        "macosx_11_0_arm64",
        "macosx_13_0_universal2",
        "macosx_12_0_universal2",
        "macosx_11_0_universal2",
        "macosx_10_9_universal2",
    )
    mac_wheels_x64: Final[tuple[str, ...]] = (
        "macosx_14_0_x86_64",
        "macosx_13_0_x86_64",
        "macosx_12_0_x86_64",
        "macosx_11_0_x86_64",
        "macosx_10_15_x86_64",
        "macosx_10_13_x86_64",
        "macosx_13_0_universal2",
        "macosx_12_0_universal2",
        "macosx_11_0_universal2",
        "macosx_10_9_universal2",
    )
    targets: Final[dict[str, BuildTarget]] = {
        "linux-glibc-amd64": BuildTarget(
            name="linux-glibc-amd64",
            os="linux",
            arch="amd64",
            libc="glibc",
            node=NodeDistribution(
                suffix="linux-x64",
                mirror=node_mirror,
                archive="tar.xz",
                binary="bin/node",
                npm="bin/npm",
                prune=node_prune_posix,
            ),
            wheel_platforms=(
                "manylinux_2_34_x86_64",
                "manylinux_2_17_x86_64",
                "manylinux2014_x86_64",
                "manylinux1_x86_64",
            ),
            browsers=linux_browsers,
        ),
        "linux-glibc-arm64": BuildTarget(
            name="linux-glibc-arm64",
            os="linux",
            arch="arm64",
            libc="glibc",
            node=NodeDistribution(
                suffix="linux-arm64",
                mirror=node_mirror,
                archive="tar.xz",
                binary="bin/node",
                npm="bin/npm",
                prune=node_prune_posix,
            ),
            wheel_platforms=(
                "manylinux_2_39_aarch64",
                "manylinux_2_17_aarch64",
                "manylinux2014_aarch64",
            ),
            browsers=BrowserDistribution(
                archives=(
                    BrowserArchive(
                        name="chromium",
                        cdn_file="chromium-linux-arm64.zip",
                        cft_file="chrome-linux-arm64.zip",
                    ),
                    BrowserArchive(
                        name="chromium-headless-shell",
                        cdn_file="chromium-headless-shell-linux-arm64.zip",
                        cft_file="chrome-headless-shell-linux-arm64.zip",
                    ),
                    BrowserArchive(
                        name="ffmpeg",
                        cdn_file="ffmpeg-linux-arm64.zip",
                    ),
                ),
                cft_dir="linux-arm64",
                prune_names=browser_prune_names,
                locale_suffix=".pak",
                locale_parent="locales",
                locale_keep=("en-US.pak", "en-GB.pak"),
            ),
        ),
        "linux-musl-amd64": BuildTarget(
            name="linux-musl-amd64",
            os="linux",
            arch="amd64",
            libc="musl",
            node=NodeDistribution(
                suffix="linux-x64-musl",
                mirror=node_mirror_unofficial,
                archive="tar.xz",
                binary="bin/node",
                npm="bin/npm",
                prune=node_prune_posix,
            ),
            wheel_platforms=("musllinux_1_2_x86_64", "musllinux_1_1_x86_64"),
            browsers=no_browsers,
        ),
        "linux-musl-arm64": BuildTarget(
            name="linux-musl-arm64",
            os="linux",
            arch="arm64",
            libc="musl",
            node=NodeDistribution(
                suffix="linux-arm64-musl",
                mirror=node_mirror_unofficial,
                archive="tar.xz",
                binary="bin/node",
                npm="bin/npm",
                prune=node_prune_posix,
            ),
            wheel_platforms=("musllinux_1_2_aarch64", "musllinux_1_1_aarch64"),
            browsers=no_browsers,
        ),
        "macos-arm64": BuildTarget(
            name="macos-arm64",
            os="darwin",
            arch="arm64",
            libc=None,
            node=NodeDistribution(
                suffix="darwin-arm64",
                mirror=node_mirror,
                archive="tar.xz",
                binary="bin/node",
                npm="bin/npm",
                prune=node_prune_posix,
            ),
            wheel_platforms=mac_wheels_arm64,
            browsers=_mac_browsers(arm64=True),
        ),
        "macos-amd64": BuildTarget(
            name="macos-amd64",
            os="darwin",
            arch="amd64",
            libc=None,
            node=NodeDistribution(
                suffix="darwin-x64",
                mirror=node_mirror,
                archive="tar.xz",
                binary="bin/node",
                npm="bin/npm",
                prune=node_prune_posix,
            ),
            wheel_platforms=mac_wheels_x64,
            browsers=_mac_browsers(arm64=False),
        ),
        "windows-amd64": BuildTarget(
            name="windows-amd64",
            os="windows",
            arch="amd64",
            libc=None,
            node=NodeDistribution(
                suffix="win-x64",
                mirror=node_mirror,
                archive="zip",
                binary="node.exe",
                npm="npm.cmd",
                prune=node_prune_windows,
            ),
            wheel_platforms=("win_amd64", "win32"),
            browsers=windows_browsers,
            python_extras=("msvc-runtime",),
        ),
        "windows-arm64": BuildTarget(
            name="windows-arm64",
            os="windows",
            arch="arm64",
            libc=None,
            node=NodeDistribution(
                suffix="win-arm64",
                mirror=node_mirror,
                archive="zip",
                binary="node.exe",
                npm="npm.cmd",
                prune=node_prune_windows,
            ),
            wheel_platforms=("win_arm64",),
            browsers=no_browsers,
        ),
    }
    target_groups: Final[dict[str, tuple[str, ...]]] = {
        "linux": (
            "linux-glibc-amd64",
            "linux-glibc-arm64",
            "linux-musl-amd64",
            "linux-musl-arm64",
        ),
        "linux-amd64": ("linux-glibc-amd64", "linux-musl-amd64"),
        "linux-arm64": ("linux-glibc-arm64", "linux-musl-arm64"),
        "glibc-amd64": ("linux-glibc-amd64",),
        "glibc-arm64": ("linux-glibc-arm64",),
        "musl-amd64": ("linux-musl-amd64",),
        "musl-arm64": ("linux-musl-arm64",),
        "musl": ("linux-musl-amd64", "linux-musl-arm64"),
        "glibc": ("linux-glibc-amd64", "linux-glibc-arm64"),
        "amd64": (
            "linux-glibc-amd64",
            "linux-musl-amd64",
            "macos-amd64",
            "windows-amd64",
        ),
        "arm64": (
            "linux-glibc-arm64",
            "linux-musl-arm64",
            "macos-arm64",
            "windows-arm64",
        ),
        "macos": ("macos-amd64", "macos-arm64"),
        "windows": ("windows-amd64", "windows-arm64"),
    }
    distribution: Final[Distribution] = Distribution()
    target_unavailable: Final[dict[str, tuple[str, ...]]] = {
        "linux-musl-amd64": ("browser",),
        "linux-musl-arm64": (
            "browser",
            "tree-sitter_tree-sitter-language-pack",
        ),
        "windows-arm64": ("hypothesis_mutmut",),
    }


@final
class BuildToolsDefaults:
    """Immutable filesystem defaults for the bundle builder.

    Attributes:
        script_dir: Directory containing this script.
        project_root: Repository root containing the ``exactus`` tree.
        bundle_root: Root of the per-target bundle hierarchy under
            ``exactus/bundle``.
        default_parts_bytes: Maximum default payload-part size in bytes.
        playwright_cdn: Base URL of the Playwright browser CDN.

    """

    script_dir: ClassVar[Path] = Path(__file__).resolve().parent
    project_root: ClassVar[Path] = script_dir.parent.parent.parent
    bundle_root: ClassVar[Path] = project_root / "exactus" / "bundle"
    default_parts_bytes: ClassVar[int] = 90000000
    playwright_cdn: ClassVar[str] = "https://cdn.playwright.dev"


type OperatingSystem = Literal["darwin", "linux", "windows"]
type Architecture = Literal["amd64", "arm64"]
type Libc = Literal["glibc", "musl"]


def stub_marker() -> str:
    """Return the marker embedded in generated dispatchers.

    Returns:
        Marker identifying a generated tools dispatcher.

    """
    return "__EXACTUS_TOOLS_PAYLOAD__"


def bundle_dir(*, target: str) -> Path:
    """Return the emitted bundle directory for one target identifier.

    Args:
        target: Target name such as ``linux-glibc-amd64`` or
            ``linux-musl-arm64``.

    Returns:
        ``exactus/bundle/<os>/<arch>`` style directory selected by
        the target name's hyphen-separated parts.

    """
    return BuildToolsDefaults.bundle_root.joinpath(*target.split(sep="-"))


def host_target() -> str | None:
    """Return the bundle target matching the build host, if any.

    Returns:
        Target identifier for the host platform, or ``None`` when the
        host operating system or architecture is unsupported.

    """
    os_name: str | None = {
        "Linux": "linux",
        "Darwin": "macos",
        "Windows": "windows",
    }.get(system())
    arch: str | None = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(machine().lower())
    if os_name is None or arch is None:
        return None
    if os_name != "linux":
        return f"{os_name}-{arch}"
    musl: bool = "musl" in libc_ver()[0].lower() or any(
        loader.is_file()
        for root in ("/lib", "/usr/lib")
        for loader in Path(root).glob(pattern="ld-musl-*.so*")
    )
    return f"linux-musl-{arch}" if musl else f"linux-glibc-{arch}"


def size_label(*, size: int) -> str:
    """Format a byte count with decimal SI units.

    Args:
        size: Byte count.

    Returns:
        Human-readable size such as ``512B``, ``3.2KB``, or ``90MB``.

    """
    value: float = float(size)
    unit: str = "B"
    for candidate in ("KB", "MB", "GB"):
        if value < Constants.size_base:
            break
        value /= Constants.size_base
        unit = candidate
    if unit == "B":
        return f"{size}B"
    return f"{f'{value:.1f}'.removesuffix('.0')}{unit}"


class FetchError(RuntimeError):
    """Failed to download a remote resource."""


@dataclass(frozen=True, slots=True, kw_only=True)
class FetchOptions:
    """Optional tuning for one ``fetch`` transfer.

    Attributes:
        timeout: Socket timeout in seconds.
        limit: Maximum response size in bytes.
        attempts: Maximum request attempts including the first.

    """

    timeout: float = 30.0
    limit: int = 64 * 1024 * 1024
    attempts: int = 3


class ResponseReader(Protocol):
    """Common positional read interface of urllib response streams."""

    def read(self, size: int, /) -> bytes:
        """Read at most the requested number of response bytes.

        Args:
            size: Maximum number of bytes to consume.

        Returns:
            Available bytes, or empty bytes at end of stream.

        """
        ...


def fetch(*, url: str, options: FetchOptions | None = None) -> bytes:
    """Download ``url`` over HTTP(S) with retries and a size cap.

    Args:
        url: HTTP(S) URL to download.
        options: Tuning for timeout, response-size limit, and attempts.

    Returns:
        Response body bytes.

    Raises:
        FetchError: When the URL is invalid or every attempt fails.

    """
    resolved: FetchOptions = options if options is not None else FetchOptions()
    parsed: ParseResult = urlparse(url=url)
    if (
        parsed.scheme.lower() not in Constants.fetch_schemes
        or not parsed.netloc
    ):
        msg: str = f"Refusing URL: {url!r}."
        raise FetchError(msg)
    request_type: type[Request] = Request
    prepared: Request = request_type(
        url=url,
        headers={
            "User-Agent": Constants.fetch_user_agent,
            "Accept-Encoding": "identity",
        },
    )
    delay: float = 0.5
    failure: FetchError = FetchError(f"No attempts configured for {url}.")
    open_url: Callable[..., addinfourl] = urlopen
    for attempt in range(resolved.attempts):
        if attempt:
            sleep(delay)
            delay = min(delay * 2.0, 10.0)
        try:
            response: addinfourl = open_url(
                url=prepared,
                timeout=resolved.timeout,
            )
            break
        except HTTPError as http_error:
            failure = FetchError(
                f"HTTP {http_error.code} for {url}: {http_error.reason}",
            )
            if http_error.code not in Constants.fetch_retryable:
                raise failure from http_error
        except URLError as url_error:
            failure = FetchError(
                f"Request failed for {url}: {url_error.reason}",
            )
    else:
        raise failure
    chunks: list[bytes] = []
    received: int = 0
    reader: ResponseReader = cast(typ="ResponseReader", val=response)
    with response:
        while chunk := reader.read(
            min(Constants.fetch_chunk, resolved.limit - received + 1),
        ):
            received += len(chunk)
            if received > resolved.limit:
                msg = f"Response from {url} exceeded {resolved.limit} bytes."
                raise FetchError(msg)
            chunks.append(chunk)
    return b"".join(chunks)


def resolve_components(
    *,
    names: tuple[str, ...],
    follow_requires: bool = True,
) -> tuple[str, ...]:
    """Resolve tools, groups, and component names to components.

    Args:
        names: Requested tool, group, or component names.
        follow_requires: Extend the selection transitively over
            ``requires`` edges; exclusion passes ``False`` so a name
            drops only its own components.

    Returns:
        Selected component names closed over ``requires`` edges, in
        ``COMPONENTS`` table order.

    Raises:
        ValueError: A name matches no tool, group, or component.

    """
    requested: set[str] = set()
    for name in names:
        if name == "all":
            requested.update(Constants.optional_components)
        elif name in Constants.groups:
            requested.update(Constants.groups[name])
        elif name in Constants.components:
            requested.add(name)
        elif name in Constants.tool_component:
            requested.add(Constants.tool_component[name])
        else:
            msg: str = f"unknown optional component or group: {name}"
            raise ValueError(msg)
    resolved: set[str] = set(requested)
    pending: list[str] = list(requested) if follow_requires else []
    while pending:
        component: str = pending.pop()
        for requirement in Constants.components[component].requires:
            if requirement not in resolved:
                resolved.add(requirement)
                pending.append(requirement)
    return tuple(name for name in Constants.components if name in resolved)


def unavailable_components(*, target: str) -> frozenset[str]:
    """Return optional components that cannot stage on a target.

    Args:
        target: Concrete bundle target name.

    Returns:
        Resolved optional component names to drop for the target.

    """
    names: tuple[str, ...] = Constants.target_unavailable.get(target, ())
    return frozenset(resolve_components(names=names, follow_requires=False))


@dataclass(frozen=True, slots=True)
class BundleConfig:
    """Immutable exactus-tool bundle configuration.

    Attributes:
        node_version: Node.js runtime version bundled offline.
        optional: Selected optional component names, already resolved
            through :func:`resolve_components`.
        exclude: Component names dropped from the final selection;
            members of :data:`MANDATORY_COMPONENTS` and dependencies a
            kept component still requires are always retained.

    """

    node_version: str = "22.21.1"
    optional: tuple[str, ...] = ()
    exclude: frozenset[str] = frozenset()

    @property
    def selected_optional(self) -> frozenset[str]:
        """Selected optional component names.

        Returns:
            Optional component names requested for this bundle.

        """
        return frozenset(self.optional)

    @property
    def components(self) -> tuple[ComponentSpec, ...]:
        """Components to stage, required first in table order.

        Selected optional components pull in their ``requires``
        dependencies transitively. Excluded components are dropped
        unless a kept component still requires them or they are
        members of :data:`MANDATORY_COMPONENTS`.

        Returns:
            Required components plus selected optional ones.

        """
        resolved: set[str] = set(self.selected_optional)
        pending: list[str] = list(resolved)
        while pending:
            for requirement in Constants.components.get(
                pending.pop(),
                ComponentSpec(name=""),
            ).requires:
                if requirement not in resolved:
                    resolved.add(requirement)
                    pending.append(requirement)
        kept: set[str] = {
            name
            for name, spec in Constants.components.items()
            if not spec.optional or name in resolved
        } - self.exclude | Constants.mandatory_components
        pending = list(kept)
        while pending:
            for requirement in Constants.components[pending.pop()].requires:
                if requirement not in kept:
                    kept.add(requirement)
                    pending.append(requirement)
        return tuple(
            spec for spec in Constants.components.values() if spec.name in kept
        )

    @property
    def available_tools(self) -> tuple[str, ...]:
        """Tool names exposed by this exact bundle.

        Returns:
            Bundled executable tool names.

        """
        return tuple(
            tool.name for spec in self.components for tool in spec.tools
        )


@dataclass(slots=True)
class BuildOptions(Namespace):
    """Typed command-line options for the bundle builder.

    Attributes:
        rebuild: Rebuild recorded by this structure.
        output: Destination self-extracting executable, resolved from
            the target when unset.
        exclude: Component names or groups subtracted from the final
            selection unless another kept component requires them.
        node_version: Node.js runtime version to bundle, resolved from
            ``[tool.bundle]`` when unset.
        optional: Requested optional component names or groups, merged
            with ``[tool.bundle]`` entries.
        part_bytes: Maximum payload-part size in bytes, resolved from
            ``[tool.bundle]`` when unset.
        only: Component names restricting the build to incremental
            archive emission.
        parts_dir: Destination directory for payload parts, resolved
            beside ``output`` when unset.
        target: Target platform identifiers, resolved from
            ``[tool.bundle]`` when unset.

    """

    output: Path | None = None
    exclude: list[str] | None = None
    node_version: str | None = None
    only: list[str] | None = None
    optional: list[str] | None = None
    part_bytes: int | None = None
    parts_dir: Path | None = None
    target: list[str] | None = None
    rebuild: bool = False


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class BundleFileConfig:
    """``[tool.bundle]`` defaults layered under command-line options.

    Attributes:
        exclude: Component or group names merged with ``--exclude``
            arguments and subtracted from the final selection unless
            another kept component requires them.
        node_version: Node.js runtime version to bundle.
        only: Component names merged with ``--only`` arguments.
        optional: Optional component or group names merged with
            ``--optional`` arguments.
        output: Destination launcher merged with ``--output``.
        part_bytes: Maximum payload-part size in bytes.
        parts_dir: Payload-parts directory merged with ``--parts-dir``.
        rebuild: Rebuild flag merged with ``--rebuild``.
        target: Single target platform identifier (legacy key).
        targets: Target platform identifiers built when ``--target``
            is absent.

    """

    exclude: tuple[str, ...] = ()
    node_version: str | None = None
    only: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    output: Path | None = None
    part_bytes: int | None = None
    parts_dir: Path | None = None
    rebuild: bool = False
    target: str | None = None
    targets: tuple[str, ...] = ()


def bundle_file_config(*, path: Path) -> BundleFileConfig:
    """Read ``[tool.bundle]`` defaults from a ``pyproject.toml`` file.

    Args:
        path: Candidate ``pyproject.toml`` location.

    Returns:
        Parsed bundle defaults; every field is unset when the file or
        the ``[tool.bundle]`` section is absent.

    Raises:
        TypeError: A configured key holds a value of the wrong type.

    """
    if not path.is_file():
        return BundleFileConfig()
    with path.open(mode="rb") as stream:
        document: dict[str, object] = load_toml(stream)
    tools: object = document.get("tool", {})
    if not isinstance(tools, dict):
        return BundleFileConfig()
    section: object = cast(typ="dict[str, object]", val=tools).get(
        "bundle",
        {},
    )
    if not isinstance(section, dict):
        return BundleFileConfig()
    table: dict[str, object] = cast(typ="dict[str, object]", val=section)
    str_lists: dict[str, tuple[str, ...]] = {}
    for key in ("targets", "optional", "exclude", "only"):
        names: object = table.get(key, [])
        items: list[object] = cast(typ="list[object]", val=names)
        if not isinstance(names, list) or not all(
            isinstance(name, str) for name in items
        ):
            msg: str = f"[tool.bundle] {key} must be a list of strings"
            raise TypeError(msg)
        str_lists[key] = tuple(name for name in items if isinstance(name, str))
    scalars: dict[str, object] = {}
    for key, expected, label in (
        ("target", str, "a string"),
        ("node-version", str, "a string"),
        ("part-bytes", int, "an integer"),
        ("output", str, "a string"),
        ("parts-dir", str, "a string"),
        ("rebuild", bool, "a boolean"),
    ):
        raw: object = table.get(key)
        if raw is not None and (not isinstance(raw, expected)):
            msg = f"[tool.bundle] {key} must be {label}"
            raise TypeError(msg)
        scalars[key] = raw
    return BundleFileConfig(
        exclude=str_lists["exclude"],
        node_version=cast(typ="str | None", val=scalars["node-version"]),
        only=str_lists["only"],
        optional=str_lists["optional"],
        output=path.parent / output
        if isinstance((output := scalars["output"]), str)
        else None,
        part_bytes=cast(typ="int | None", val=scalars["part-bytes"]),
        parts_dir=path.parent / parts_dir
        if isinstance((parts_dir := scalars["parts-dir"]), str)
        else None,
        rebuild=bool(scalars["rebuild"]),
        target=cast(typ="str | None", val=scalars["target"]),
        targets=str_lists["targets"],
    )


@final
@dataclass(slots=True)
class _Heartbeat:
    """Live build-status handle for ``parts/@activity.json``.

    Attributes:
        state: Mutable mapping whose ``step`` key names the current
            build phase; ``step_at``/``step_mono`` timestamp it.
        steps: Records of completed steps (name, start, end, seconds).
        started: Monotonic timestamp of the build start.
        started_at: Wall-clock timestamp of the build start.
        run_id: Unique build run identifier.
        part_bytes: Maximum payload-part size in bytes.
        stop_event: Event that ends the heartbeat once set.
        thread: Daemon thread refreshing ``@activity.json``, attached
            after construction.

    """

    state: dict[str, str]
    steps: list[dict[str, Json]]
    started: float
    started_at: datetime
    run_id: str
    part_bytes: int
    stop_event: Event
    thread: Thread | None = None

    def stop(self) -> None:
        """End the heartbeat, waiting briefly for the last write."""
        self.stop_event.set()
        if self.thread is not None:
            _ = self.thread.join(timeout=Constants.heartbeat_seconds * 2)

    def advance(self, *, step: str) -> None:
        """Record the running step and switch to a new build phase.

        Args:
            step: New build phase name.

        """
        now: datetime = datetime.now(tz=UTC).astimezone()
        now_mono: float = monotonic()
        name: str = self.state.get("step") or ""
        if name in Constants.build_steps:
            self.steps.append(
                {
                    "name": name,
                    "started": self.state.get("step_at") or "",
                    "finished": now.isoformat(),
                    "seconds": round(
                        number=now_mono
                        - float(self.state.get("step_mono") or "0"),
                        ndigits=1,
                    ),
                },
            )
        self.state.clear()
        self.state["step"] = step
        self.state["step_at"] = now.isoformat()
        self.state["step_mono"] = str(object=now_mono)


@dataclass(slots=True)
class _PartitionBuild:
    """Typed phase state for one serialized filesystem build.

    Attributes:
        cache: Cache recorded by this structure.
        heartbeat: Heartbeat recorded by this structure.
        part_bytes: Part bytes recorded by this structure.
        only: Only recorded by this structure.
        rebuild: Rebuild recorded by this structure.
        chunking: Chunking recorded by this structure.
        state_path: State path recorded by this structure.
        previous_records: Previous records recorded by this structure.
        previous: Previous recorded by this structure.
        previous_root: Previous root recorded by this structure.
        store: Store recorded by this structure.
        specs: Specs recorded by this structure.
        selected: Selected recorded by this structure.
        fingerprints: Fingerprints recorded by this structure.
        lock_hash: Lock hash recorded by this structure.
        policy: Policy recorded by this structure.
        recipes: Recipes recorded by this structure.
        reused: Reused recorded by this structure.
        plan: Plan recorded by this structure.
        generation: Generation recorded by this structure.
        records: Records recorded by this structure.
        candidate: Candidate recorded by this structure.
        root: Root recorded by this structure.
        snapshot: Snapshot recorded by this structure.
        catalog: Catalog recorded by this structure.
        parts_relative: Parts relative recorded by this structure.
        launcher: Launcher recorded by this structure.
        runtime_files: Runtime files recorded by this structure.
        metadata: Metadata recorded by this structure.
        readme: Readme recorded by this structure.
        stats: Stats recorded by this structure.
        scratch: Scratch recorded by this structure.
        delta_bytes: Delta bytes recorded by this structure.

    """

    cache: Path
    heartbeat: _Heartbeat
    part_bytes: int
    only: tuple[str, ...]
    rebuild: bool
    chunking: ChunkingConfig
    state_path: Path = field(default_factory=Path)
    previous_records: dict[str, dict[str, PartitionJson]] = field(
        default_factory=dict,
    )
    previous: Catalog | None = None
    previous_root: Path | None = None
    store: PartitionStore = field(
        default_factory=lambda: PartitionStore(cache=Path()),
    )
    specs: tuple[ComponentSpec, ...] = ()
    selected: set[str] = field(default_factory=set)
    fingerprints: dict[str, str] = field(default_factory=dict)
    lock_hash: str = ""
    policy: str = ""
    recipes: dict[str, Recipe] = field(default_factory=dict)
    reused: dict[str, dict[str, PartitionJson]] = field(default_factory=dict)
    plan: dict[str, str] = field(default_factory=dict)
    generation: Path = field(default_factory=Path)
    records: dict[str, dict[str, PartitionJson]] = field(default_factory=dict)
    candidate: Path = field(default_factory=Path)
    root: str = ""
    snapshot: Path = field(default_factory=Path)
    catalog: Catalog = field(
        default_factory=lambda: cast(typ="Catalog", val={}),
    )
    parts_relative: str = ""
    launcher: str = ""
    runtime_files: tuple[str, ...] = ()
    metadata: dict[str, PartitionJson] = field(default_factory=dict)
    readme: str = ""
    stats: dict[str, PartitionJson] = field(default_factory=dict)
    scratch: str = ""
    delta_bytes: int = 0


class BundleBuilder:
    """Build one portable self-extracting exactus tool dispatcher."""

    def __init__(
        self,
        *,
        config: BundleConfig,
        output: Path,
        rebuild_args: tuple[str, ...] = (),
        parts_dir: Path | None = None,
        target: BuildTarget = Constants.targets["linux-glibc-amd64"],
    ) -> None:
        """Initialize the builder.

        Args:
            config: Bundle dependency configuration.
            output: Destination executable.
            rebuild_args: Original CLI arguments used for this build; empty
                for direct programmatic construction.
            parts_dir: Directory containing payload parts; resolved to
                ``data/parts`` beside ``output`` when unset.
            target: Target platform.

        """
        self._config: BundleConfig = config
        self._output: Path = output.resolve()
        self._rebuild_args: tuple[str, ...] = rebuild_args
        self._parts_dir: Path = (
            parts_dir or self._output.parent / "data" / "parts"
        ).resolve()
        self._target: BuildTarget = target

    @staticmethod
    def prune(*, payload: Path) -> None:
        """Remove bytecode caches and source maps from the payload.

        Args:
            payload: Payload root.

        """
        for directory in tuple(
            path
            for path in payload.rglob(pattern="__pycache__")
            if path.is_dir()
        ):
            rmtree(path=directory)
        for file in tuple(
            path
            for path in payload.rglob(pattern="*")
            if path.is_file()
            and (
                path.name == ".DS_Store"
                or path.suffix in {".map", ".pyc", ".pyo"}
                or path.name.startswith("._")
            )
        ):
            file.unlink()

    def build(
        self,
        *,
        part_bytes: int = BuildToolsDefaults.default_parts_bytes,
        only: tuple[str, ...] = (),
        rebuild: bool = False,
        chunking: ChunkingConfig | None = None,
    ) -> Path:
        """Build an incremental partitioned distribution and pack update.

        Args:
            part_bytes: Raw shard target, capped at 64 MiB by default.
            only: Force these selected components, reusing valid siblings.
            rebuild: Force acquisition/scanning for every selected component.
            chunking: Versioned CDC tuning for reproducible benchmarks.

        Returns:
            Generated offline launcher path.

        Raises:
            ValueError: When the operation detects invalid input or state.

        """
        if not 0 < part_bytes <= BuildToolsDefaults.default_parts_bytes:
            msg: str = "part_bytes must be between 1 and 90000000"
            raise ValueError(msg)
        cache: Path = (
            self._output.parent / "data" / ".build-cache" / self._target.name
        )
        with (
            cache_lock(root=cache),
            self._heartbeat(part_bytes=part_bytes) as heartbeat,
        ):
            return self._build_partitioned(
                ctx=_PartitionBuild(
                    cache=cache,
                    heartbeat=heartbeat,
                    part_bytes=part_bytes,
                    only=only,
                    rebuild=rebuild,
                    chunking=chunking or ChunkingConfig(),
                ),
            )

    @staticmethod
    def _run(
        *,
        args: tuple[str, ...],
        cwd: Path,
        env: dict[str, str] | None = None,
    ) -> None:
        """Run one required build command.

        Args:
            args: Command and arguments.
            cwd: Working directory.
            env: Full environment replacement, or the host environment.

        """
        _ = run(args=args, cwd=cwd, check=True, env=env)

    @staticmethod
    def _extract_zip(*, archive: Path, destination: Path) -> None:
        """Extract a zip archive preserving recorded file permissions.

        Args:
            archive: Zip archive to extract.
            destination: Directory receiving the extracted files.

        """
        with ZipFile(file=archive) as zipped:
            for info in zipped.infolist():
                extracted: Path = Path(
                    zipped.extract(member=info, path=destination),
                )
                mode: int = info.external_attr >> 16
                if mode:
                    extracted.chmod(mode=mode)

    @staticmethod
    def _python_versions(*, stage: Path) -> dict[str, str]:
        """Read bundled Python package versions from dist-info dirs.

        Args:
            stage: Component staging root.

        Returns:
            Distribution name to version mapping.

        """
        versions: dict[str, str] = {}
        python: Path = stage / "python"
        if not python.is_dir():
            return versions
        for entry in sorted(python.glob(pattern="*.dist-info")):
            name, _, version = entry.name[: -len(".dist-info")].rpartition("-")
            if name and version:
                versions[name] = version
        return versions

    @staticmethod
    def _node_versions(*, stage: Path) -> dict[str, str]:
        """Read bundled Node package versions from their manifests.

        Args:
            stage: Component staging root.

        Returns:
            Package name to version mapping.

        """
        versions: dict[str, str] = {}
        packages: Path = stage / "js" / "node_modules"
        if not packages.is_dir():
            return versions
        for package in sorted(
            entry.name for entry in packages.iterdir() if entry.is_dir()
        ):
            manifest: Path = packages / package / "package.json"
            if not manifest.is_file():
                continue
            metadata: Json = cast(
                typ="Json",
                val=loads(s=manifest.read_text(encoding="utf-8")),
            )
            if isinstance(metadata, dict) and isinstance(
                metadata.get("version"),
                str,
            ):
                versions[package] = cast(
                    typ="str",
                    val=metadata.get("version", ""),
                )
        return versions

    @staticmethod
    def _remove(*, path: Path) -> None:
        """Remove one payload file, symlink, or directory when present.

        Args:
            path: Payload path to remove.

        Raises:
            OSError: When filesystem removal fails after retry.

        """
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            try:
                rmtree(path=path)
            except OSError as error:
                if error.errno != ENOTEMPTY:
                    raise
                rmtree(path=path)

    @staticmethod
    def _tree_bytes(*, root: Path) -> int:
        """Sum the file bytes under a directory tree.

        Args:
            root: Directory tree to measure.

        Returns:
            Total file size in bytes.

        """
        return sum(
            entry.lstat().st_size
            for entry in root.rglob(pattern="*")
            if not entry.is_dir()
        )

    @staticmethod
    def _partition_recover(ctx: _PartitionBuild) -> None:
        """Recover the incremental filesystem build phase.

        Args:
            ctx: Current incremental build state.

        """
        for name in sorted(set(ctx.previous_records) - ctx.selected):
            ctx.plan[name] = "REMOVE"
        if ctx.previous is not None and ctx.previous_root is not None:
            try:
                ctx.store.recover(
                    catalog=ctx.previous,
                    root=ctx.previous_root,
                    recipes=ctx.recipes,
                )
            except (OSError, RuntimeError, ValueError):
                for name in tuple(ctx.recipes):
                    if any(
                        not ctx.store.objects.valid(digest=digest)
                        for entry in ctx.recipes[name]["entries"]
                        for digest in entry.get("chunks", [])
                    ):
                        ctx.plan[name] = "BUILD"
                        del ctx.recipes[name]
                        ctx.reused.pop(name, None)
        ctx.generation = ctx.cache / "components" / uuid4().hex
        ctx.generation.mkdir(parents=True)
        ctx.records = {}

    @staticmethod
    def _partition_metrics(ctx: _PartitionBuild) -> None:
        """Metrics the incremental filesystem build phase.

        Args:
            ctx: Current incremental build state.

        """
        ctx.stats = {
            "logical_payload_bytes": sum(
                recipe["logical_bytes"] for recipe in ctx.recipes.values()
            ),
            "unique_object_bytes": sum(
                row["size"] for row in ctx.catalog["objects"].values()
            ),
            "shared_object_bytes": sum(
                row["size"]
                for row in ctx.catalog["objects"].values()
                if len(row["members"]) > 1
            ),
            "physical_pack_bytes": sum(
                row["bytes"] for row in ctx.catalog["packs"].values()
            ),
            "catalog_bytes": (ctx.snapshot / "catalog.json").stat().st_size,
            "object_count": len(ctx.catalog["objects"]),
            "shared_object_count": sum(
                len(row["members"]) > 1
                for row in ctx.catalog["objects"].values()
            ),
            "membership_partition_count": len(
                {
                    tuple(row["members"])
                    for row in ctx.catalog["objects"].values()
                },
            ),
            "pack_count": len(ctx.catalog["packs"]),
            "packs_reused": ctx.store.packs_reused,
            "packs_built": ctx.store.packs_built,
            "components_reused": sum(
                action == "REUSE" for action in ctx.plan.values()
            ),
            "components_built": sum(
                action == "BUILD" for action in ctx.plan.values()
            ),
            "components_removed": sum(
                action == "REMOVE" for action in ctx.plan.values()
            ),
            "delta_bytes": ctx.delta_bytes,
            "plan": cast(typ="PartitionJson", val=ctx.plan),
            "build_seconds": monotonic() - ctx.heartbeat.started,
            "entry_count": sum(
                len(recipe["entries"]) for recipe in ctx.recipes.values()
            ),
            "chunk_references": sum(
                len(entry.get("chunks", []))
                for recipe in ctx.recipes.values()
                for entry in recipe["entries"]
            ),
        }

    def _install_python(self, *, stage: Path, spec: ComponentSpec) -> None:
        """Install one component's Python packages into ``python/``.

        Args:
            stage: Component staging root.
            spec: Component whose packages are installed.

        """
        self._run(
            args=(
                "python3",
                "-m",
                "pip",
                "install",
                "--only-binary=:all:",
                *(
                    f"--platform={platform}"
                    for platform in self._target.wheel_platforms
                ),
                "--implementation=cp",
                "--python-version=3.13",
                "--target",
                str(object=stage / "python"),
                *spec.python_packages,
                *(self._target.python_extras if spec.python_extras else ()),
            ),
            cwd=stage,
        )

    def _install_node_runtime(self, *, stage: Path) -> None:
        """Install the Node.js distribution under ``node/``.

        Args:
            stage: Component staging root.

        """
        node: NodeDistribution = self._target.node
        archive: Path = stage / f"node.{node.archive}"
        archive_name: str = (
            f"node-v{self._config.node_version}-{node.suffix}.{node.archive}"
        )
        url: str = f"{node.mirror}/v{self._config.node_version}/{archive_name}"
        _ = archive.write_bytes(
            data=fetch(url=url, options=FetchOptions(limit=512 * 1024 * 1024)),
        )
        if node.archive == "zip":
            self._extract_zip(archive=archive, destination=stage)
        else:
            self._run(args=("tar", "-xf", str(object=archive)), cwd=stage)
        node_root: Path = stage / "node"
        extracted: Path = stage / archive_name.removesuffix(f".{node.archive}")
        _ = extracted.rename(target=node_root)
        archive.unlink()
        for relative in node.prune:
            self._remove(path=node_root / relative)

    def _install_node_packages(
        self,
        *,
        stage: Path,
        spec: ComponentSpec,
        staging: Path,
    ) -> None:
        """Install one component's npm packages under ``js/``.

        Args:
            stage: Component staging root.
            spec: Component whose packages are installed.
            staging: Build staging root holding every component, used
                to locate the freshly bundled npm for same-host builds.

        Raises:
            ValueError: Host npm is unavailable for a cross-platform
                build.

        """
        node: NodeDistribution = self._target.node
        host_suffix: str | None = {
            ("Linux", "x86_64"): "linux-x64",
            ("Linux", "aarch64"): "linux-arm64",
            ("Linux", "arm64"): "linux-arm64",
            ("Darwin", "arm64"): "darwin-arm64",
            ("Darwin", "x86_64"): "darwin-x64",
        }.get((system(), machine()))
        same_host: bool = self._target.node.suffix == host_suffix
        bundled_npm: Path = staging / "node" / "node" / node.npm
        host_npm: str | None = which(cmd="npm")
        npm: str
        if same_host and bundled_npm.is_file():
            npm = str(object=bundled_npm)
        elif host_npm is not None:
            npm = host_npm
        else:
            msg: str = (
                f"host npm is required to install JavaScript "
                f"tools when the build host is not {self._target.name}"
            )
            raise ValueError(msg)
        self._run(
            args=(
                npm,
                "install",
                "--prefix",
                str(object=stage / "js"),
                "--omit=dev",
                *spec.node_packages,
            ),
            cwd=stage,
            env={**environ, "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "1"},
        )

    def _install_chromium(
        self,
        *,
        stage: Path,
        staging: Path,
        heartbeat: _Heartbeat,
    ) -> dict[str, dict[str, str]]:
        """Install the target's Playwright browsers into the component.

        Downloads the platform archives without running any
        target-native executable on the build host.
        Mirrors `playwright install chromium`, which resolves to the
        chromium, chromium-headless-shell, and ffmpeg descriptors.
        Both chromium builds are kept: headless launches use the shell
        while `headless=False` launches (for example under Xvfb on
        hosts without a UI) need the full binary. Revisions and
        browser versions come from the ``playwright`` component's
        `browsers.json` catalog.

        Args:
            stage: Chromium component staging root.
            staging: Build staging root holding every component.
            heartbeat: Live heartbeat handle for download detail.

        Returns:
            Installed browser descriptors keyed by catalog name, or an
            empty mapping when the target ships no browser builds.

        Raises:
            ValueError: If the bundled Playwright catalog is missing a
                required browser descriptor.

        """
        spec: BrowserDistribution = self._target.browsers
        if not spec.archives:
            heartbeat.state["detail"] = (
                f"no Playwright browser builds for {self._target.name}"
            )
            return {}
        catalog: Json = cast(
            typ="Json",
            val=loads(
                s=(
                    staging
                    / "playwright"
                    / "python"
                    / "playwright"
                    / "driver"
                    / "package"
                    / "browsers.json"
                ).read_text(encoding="utf-8"),
            ),
        )
        entries: dict[str, tuple[str, str | None]] = {}
        browsers: Json = (
            catalog.get("browsers") if isinstance(catalog, dict) else None
        )
        if isinstance(browsers, list):
            for entry in browsers:
                if not isinstance(entry, dict):
                    continue
                name: Json = entry.get("name")
                revision: Json = entry.get("revision")
                version: Json = entry.get("browserVersion")
                if isinstance(name, str) and isinstance(revision, str):
                    entries[name] = (
                        revision,
                        version if isinstance(version, str) else None,
                    )
        browsers_root: Path = stage / "playwright-browsers"
        installed: dict[str, dict[str, str]] = {}
        for archive in spec.archives:
            descriptor: str = archive.name
            resolved: tuple[str, str | None] | None = entries.get(descriptor)
            if resolved is None:
                msg: str = (
                    f"bundled playwright catalog is missing {descriptor}"
                )
                raise ValueError(msg)
            revision, browser_version = resolved
            heartbeat.state["detail"] = f"{descriptor}-{revision}"
            downloaded: bytes = self._download_browser(
                archive=archive,
                descriptor=descriptor,
                revision=revision,
                browser_version=browser_version,
            )
            archive_file: Path = stage.parent / f"{descriptor}-{revision}.zip"
            _ = archive_file.write_bytes(data=downloaded)
            directory: str = f"{descriptor.replace('-', '_')}-{revision}"
            self._extract_zip(
                archive=archive_file,
                destination=browsers_root / directory,
            )
            archive_file.unlink()
            (browsers_root / directory / "INSTALLATION_COMPLETE").touch()
            installed[descriptor] = {
                "revision": revision,
                "version": browser_version or "",
            }
        return installed

    def _download_browser(
        self,
        *,
        archive: BrowserArchive,
        descriptor: str,
        revision: str,
        browser_version: str | None,
    ) -> bytes:
        """Download one browser archive, CFT first then the CDN.

        Args:
            archive: Target browser archive spec.
            descriptor: ``browsers.json`` catalog name.
            revision: Playwright build revision.
            browser_version: Chrome-for-Testing version, when the
                descriptor publishes one.

        Returns:
            Downloaded zip bytes.

        Raises:
            ValueError: If every download source failed.

        """
        urls: list[str] = []
        spec: BrowserDistribution = self._target.browsers
        if (
            spec.cft_dir is not None
            and archive.cft_file is not None
            and (browser_version is not None)
        ):
            urls.append(
                f"{Constants.cft_cdn}/{browser_version}/{spec.cft_dir}/{archive.cft_file}",
            )
        family: str = (
            "chromium" if descriptor.startswith("chromium") else descriptor
        )
        urls.append(
            f"{BuildToolsDefaults.playwright_cdn}/dbazure/download/playwright/builds/{family}/{revision}/{archive.cdn_file}",
        )
        for url in urls:
            try:
                return fetch(
                    url=url,
                    options=FetchOptions(limit=512 * 1024 * 1024),
                )
            except FetchError:
                continue
        msg: str = (
            f"no downloadable {descriptor} archive for {self._target.name}"
        )
        raise ValueError(msg)

    def _dedupe_node(self, *, stage: Path, staging: Path) -> None:
        """Point embedded Node.js runtimes at the bundled component.

        basedpyright's ``nodejs_wheel`` dependency and the Playwright
        Python driver each ship a private ``node`` binary; both are
        replaced by relative symlinks escaping into the sibling
        ``node`` component, which stays valid once every component is
        extracted beside the others inside the launcher cache. The
        wheel copies of npm, corepack, headers, and manuals are then
        removed because the offline bundle never installs packages.

        Args:
            stage: Component staging root whose ``python/`` tree is
                deduplicated.
            staging: Build staging root holding every component.

        """
        bundled: Path = staging / "node" / "node" / self._target.node.binary
        if not bundled.is_file():
            return
        binary: str = Path(self._target.node.binary).name
        python: Path = stage / "python"
        for parent in (
            python / "nodejs_wheel",
            python / "playwright" / "driver",
        ):
            for embedded in parent.rglob(pattern=binary):
                if embedded.is_file() and (not embedded.is_symlink()):
                    embedded.unlink()
                    embedded.symlink_to(
                        target=relpath(path=bundled, start=embedded.parent),
                    )
        wheel: Path = python / "nodejs_wheel"
        for relative in (
            *Constants.node_prune_posix,
            *Constants.node_prune_windows,
        ):
            self._remove(path=wheel / relative)

    def _prune_browsers(self, *, payload: Path) -> None:
        """Drop DRM, crash reporting, and non-English UI locales.

        Rendering dependencies are kept: the SwiftShader/Vulkan/GLES
        libraries headless WebGL needs, ``icudtl.dat``, the resource
        paks, the V8 snapshot, the setuid sandbox helper, and
        ``en-US.pak``.

        Args:
            payload: Payload root.

        """
        browsers: BrowserDistribution = self._target.browsers
        root: Path = payload / "playwright-browsers"
        for entry in tuple(
            path
            for path in root.rglob(pattern="*")
            if path.name in browsers.prune_names
        ):
            self._remove(path=entry)
        for entry in tuple(
            path
            for path in root.rglob(pattern=f"*{browsers.locale_suffix}")
            if path.name not in browsers.locale_keep
            and (
                browsers.locale_parent is None
                or path.parent.name == browsers.locale_parent
            )
        ):
            self._remove(path=entry)

    def _component_manifest(
        self,
        *,
        spec: ComponentSpec,
        stage: Path,
        tree_sha256: str,
    ) -> dict[str, Json]:
        """Collect original tool/environment/version metadata for a recipe.

        Args:
            spec: Component being packaged.
            stage: Component staging root.
            tree_sha256: Portable identity from the streaming scanner.

        Returns:
            The manifest document for the build catalog.

        """
        env: dict[str, list[str]] = {}
        if (stage / "python").is_dir():
            env.setdefault("PYTHONPATH", []).append("python")
            env.setdefault("PATH", []).extend(("python/bin", "python/Scripts"))
        if (stage / "js").is_dir():
            env.setdefault("NODE_PATH", []).append("js/node_modules")
        if (stage / "node").is_dir():
            env.setdefault("PATH", []).append("node/bin")
            env.setdefault("PATH", []).append("node")
        if (stage / "playwright-browsers").is_dir():
            env.setdefault("PLAYWRIGHT_BROWSERS_PATH", []).append(
                "playwright-browsers",
            )
        for variable, entries in spec.env:
            env.setdefault(variable, []).extend(entries)
        tools: dict[str, dict[str, str]] = {}
        for tool in spec.tools:
            entry: dict[str, str] = {
                "kind": tool.kind,
                "target": f"node/{self._target.node.binary}"
                if spec.node_runtime
                else tool.target,
            }
            if tool.module:
                entry["module"] = tool.module
            tools[tool.name] = entry
        manifest: dict[str, Json] = cast(
            typ="dict[str, Json]",
            val={
                "name": spec.name,
                "tools": tools,
                "requires": sorted(spec.requires),
                "env": env,
                "python_packages": spec.python_packages,
                "node_packages": spec.node_packages,
                "tree_sha256": tree_sha256,
                "bytes": self._tree_bytes(root=stage),
                "platform": self._target.name,
                "optional": spec.optional,
                "versions": {
                    "python": self._python_versions(stage=stage),
                    "node": self._node_versions(stage=stage),
                },
            },
        )
        if spec.zstd_cli:
            manifest["version"] = ZstdConstants.version
        return manifest

    def _write_status(self, *, document: dict[str, Json]) -> None:
        """Atomically write the parts status file.

        Args:
            document: Status document written to ``@activity.json``.

        """
        temporary: Path = (
            self._parts_dir / f"{Constants.distribution.status_name}.tmp"
        )
        _ = temporary.write_text(
            data=dumps(obj=document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _ = temporary.replace(
            target=self._parts_dir / Constants.distribution.status_name,
        )

    def _document(
        self,
        *,
        heartbeat: _Heartbeat,
        status: str,
        extra: dict[str, Json] | None = None,
    ) -> dict[str, Json]:
        """Build the uniform ``exactus-run/v1`` doc. for ``@activity.json``.

        Steps report intra-step progress either directly through the
        ``fraction`` key or indirectly through ``watch``/``watch_total``
        — a growing output file sampled against its expected size.

        Args:
            heartbeat: Live heartbeat handle; the ``state`` mapping's
                ``step`` key names the current build phase and optional
                ``fraction``, ``detail``, ``watch``, ``watch_total``,
                and ``payload_bytes`` keys refine progress.
            status: Lifecycle state (``RUNNING``/``DONE``/``FAIL``).
            extra: Producer-specific fields kept under ``extra``.

        Returns:
            Uniform run document with one item per build step.

        """
        state: dict[str, str] = heartbeat.state
        step: str = state.get("step") or "starting"
        fraction: float = min(float(state.get("fraction") or "0"), 1.0)
        watch: str | None = state.get("watch")
        watch_total: float = float(state.get("watch_total") or "0")
        if watch and watch_total > 0:
            watch_path: Path = Path(watch)
            if watch_path.is_file():
                fraction = min(watch_path.stat().st_size / watch_total, 0.99)
        records: dict[str, list[dict[str, Json]]] = {}
        for record in heartbeat.steps:
            records.setdefault(
                str(object=record.get("name") or ""),
                [],
            ).append(record)
        items: list[RunItem] = []
        for name in Constants.build_steps:
            if status == "DONE":
                history_done: list[dict[str, Json]] = records.get(name) or []
                items.append(
                    RunItem(
                        name=name,
                        status="DONE",
                        progress=1.0,
                        started_at=str(
                            object=history_done[0].get("started") or "",
                        )
                        or None
                        if history_done
                        else None,
                        finished_at=str(
                            object=history_done[-1].get("finished") or "",
                        )
                        or None
                        if history_done
                        else None,
                        elapsed_seconds=round(
                            number=sum(
                                float(str(object=row.get("seconds") or "0"))
                                for row in history_done
                            ),
                            ndigits=1,
                        ),
                    ),
                )
            elif name == step:
                items.append(
                    RunItem(
                        name=step,
                        status=status,
                        progress=fraction,
                        started_at=state.get("step_at") or None,
                        elapsed_seconds=round(
                            number=monotonic()
                            - float(state.get("step_mono") or "0"),
                            ndigits=1,
                        ),
                        detail=state.get("detail") or "",
                    ),
                )
            elif name in records:
                history: list[dict[str, Json]] = records[name]
                items.append(
                    RunItem(
                        name=name,
                        status="DONE",
                        progress=1.0,
                        started_at=str(object=history[0].get("started") or "")
                        or None,
                        finished_at=str(
                            object=history[-1].get("finished") or "",
                        )
                        or None,
                        elapsed_seconds=round(
                            number=sum(
                                float(str(object=row.get("seconds") or "0"))
                                for row in history
                            ),
                            ndigits=1,
                        ),
                    ),
                )
            else:
                items.append(RunItem(name=name, status="WAITING"))
        completed: int = (
            len(Constants.build_steps) if status == "DONE" else len(records)
        )
        extras: dict[str, Json] = {
            "target": {
                "name": self._target.name,
                "os": self._target.os,
                "arch": self._target.arch,
                "libc": self._target.libc,
            },
            "limits": {
                "part_bytes_max": heartbeat.part_bytes,
                "part_size_max": size_label(size=heartbeat.part_bytes),
            },
        }
        if payload_bytes := state.get("payload_bytes"):
            extras["payload"] = {
                "bytes": int(payload_bytes),
                "size": size_label(size=int(payload_bytes)),
            }
        if extra:
            extras.update(extra)
        return RunDocument(
            kind="build",
            name=self._target.name,
            status=status,
            run_id=heartbeat.run_id,
            pid=getpid(),
            progress=1.0
            if status == "DONE"
            else min((completed + fraction) / len(Constants.build_steps), 1.0),
            completed=completed,
            total=len(Constants.build_steps),
            step=step,
            detail=state.get("detail") or "",
            started_at=heartbeat.started_at.isoformat(),
            finished_at=utc_now() if status in ("DONE", "FAIL") else None,
            elapsed_seconds=round(
                number=monotonic() - heartbeat.started,
                ndigits=1,
            ),
            items=tuple(items),
            extra=extras,
        ).payload()

    def _beat(self, *, heartbeat: _Heartbeat) -> None:
        """Refresh ``parts/@activity.json`` while a build is running.

        Args:
            heartbeat: Live heartbeat handle tracking the current step.

        """
        while not heartbeat.stop_event.is_set():
            with suppress(OSError):
                self._write_status(
                    document=self._document(
                        heartbeat=heartbeat,
                        status="RUNNING",
                    ),
                )
            _ = heartbeat.stop_event.wait(timeout=Constants.heartbeat_seconds)

    @contextmanager
    def _heartbeat(self, *, part_bytes: int) -> Generator[_Heartbeat]:
        """Start a daemon refreshing ``parts/@activity.json`` each second.

        Args:
            part_bytes: Maximum payload-part size in bytes.

        Yields:
            Live heartbeat handle tracking the current build step.

        """
        self._parts_dir.mkdir(parents=True, exist_ok=True)
        heartbeat: _Heartbeat = _Heartbeat(
            state={"step": "starting"},
            steps=[],
            started=monotonic(),
            started_at=datetime.now(tz=UTC).astimezone(),
            run_id=new_run_id(),
            part_bytes=part_bytes,
            stop_event=Event(),
        )
        heartbeat.thread = Thread(
            target=self._beat,
            kwargs={"heartbeat": heartbeat},
            daemon=True,
        )
        heartbeat.thread.start()
        try:
            yield heartbeat
        except BaseException as error:
            heartbeat.stop()
            self._write_status(
                document=self._document(
                    heartbeat=heartbeat,
                    status="FAIL",
                    extra={"error": f"{type(error).__name__}: {error}"},
                ),
            )
            raise
        finally:
            heartbeat.stop()

    def _stage_component(
        self,
        *,
        spec: ComponentSpec,
        staging: Path,
        heartbeat: _Heartbeat,
    ) -> dict[str, dict[str, str]]:
        """Install one component's packages into its staging root.

        Args:
            spec: Component to stage.
            staging: Build staging root holding every component.
            heartbeat: Live heartbeat handle for progress detail.

        Returns:
            Browser descriptors installed for ``browsers`` components,
            otherwise an empty mapping.

        """
        stage: Path = staging / spec.name
        stage.mkdir(parents=True)
        heartbeat.state["detail"] = spec.name
        browsers: dict[str, dict[str, str]] = {}
        if spec.zstd_cli:
            self._install_zstd_cli(stage=stage)
        if spec.node_runtime:
            self._install_node_runtime(stage=stage)
        if spec.node_packages:
            self._install_node_packages(
                stage=stage,
                spec=spec,
                staging=staging,
            )
        if spec.python_packages or spec.python_extras:
            self._install_python(stage=stage, spec=spec)
        if spec.browsers:
            browsers = self._install_chromium(
                stage=stage,
                staging=staging,
                heartbeat=heartbeat,
            )
        self._dedupe_node(stage=stage, staging=staging)
        self.prune(payload=stage)
        if spec.browsers:
            self._prune_browsers(payload=stage)
        return browsers

    def _install_zstd_cli(self, *, stage: Path) -> None:
        """Stage ``zstd_portable`` with the target's CLI payload.

        Args:
            stage: Component staging root receiving the package.

        """
        _ = export_package(
            os_name=self._target.os,
            machine=self._target.arch,
            target=stage,
        )

    def _build_partitioned(self, ctx: _PartitionBuild) -> Path:
        """Run cohesive phases and commit state after verified publication.

        Args:
            ctx: Current incremental build state.


        Returns:
            Run cohesive phases and commit state after verified publication.

        """
        self._partition_prepare(ctx=ctx)
        self._partition_plan(ctx=ctx)
        self._partition_recover(ctx=ctx)
        self._partition_stage(ctx=ctx)
        with TemporaryDirectory(
            prefix="partition-output-",
            dir=ctx.cache,
        ) as scratch:
            ctx.scratch = scratch
            self._partition_packs(ctx=ctx)
            self._partition_runtime(ctx=ctx)
            self._partition_delta(ctx=ctx)
            self._partition_publish(ctx=ctx)
            self._partition_metrics(ctx=ctx)
            self._partition_finish(ctx=ctx)
        return self._output

    def _partition_prepare(self, ctx: _PartitionBuild) -> None:
        """Prepare the incremental filesystem build phase.

        Args:
            ctx: Current incremental build state.


        Raises:
            ValueError: When the operation detects invalid input or state.

        """
        ctx.heartbeat.advance(step="fingerprint")
        ctx.state_path = ctx.cache / "state.json"
        state: dict[str, PartitionJson] = {}
        if ctx.state_path.is_file():
            try:
                state = cast(
                    typ="dict[str, PartitionJson]",
                    val=loads(s=ctx.state_path.read_text()),
                )
            except ValueError:
                state = {}
        ctx.previous_records = cast(
            typ="dict[str, dict[str, PartitionJson]]",
            val=state.get("components", {}),
        )
        ctx.previous = None
        ctx.previous_root = None
        root_hash: Json = state.get("catalog_root")
        if isinstance(root_hash, str):
            ctx.previous_root = ctx.cache / "catalogs" / root_hash
            try:
                ctx.previous = load_catalog(
                    path=ctx.previous_root / "catalog.json",
                )
            except (OSError, ValueError):
                ctx.previous = None
        ctx.store = PartitionStore(cache=ctx.cache, chunking=ctx.chunking)
        ctx.specs = self._config.components
        ctx.selected = {spec.name for spec in ctx.specs}
        if set(ctx.only) - ctx.selected:
            msg: str = "--only components must be selected with --optional"
            raise ValueError(msg)
        ctx.fingerprints = {}
        source_lock: Path = (
            BuildToolsDefaults.project_root / "tools-source-lock.json"
        )
        ctx.lock_hash = (
            hash_file(path=source_lock) if source_lock.is_file() else ""
        )
        ctx.policy = identity(
            value={
                "prune": getsource(object=self.prune),
                "browser_prune": getsource(object=self._prune_browsers),
                "dedupe": getsource(object=self._dedupe_node),
            },
        )
        ctx.recipes = {}
        ctx.reused = {}
        ctx.plan = {}

    def _partition_plan(self, ctx: _PartitionBuild) -> None:
        """Plan the incremental filesystem build phase.

        Args:
            ctx: Current incremental build state.


        Raises:
            FormatError: When the operation detects invalid input or state.

        """
        for spec in ctx.specs:
            fingerprint: str = identity(
                value=cast(
                    typ="PartitionJson",
                    val={
                        "spec": asdict(obj=spec),
                        "target": {
                            **asdict(obj=self._target),
                            "browsers": {
                                **asdict(obj=self._target.browsers),
                                "prune_names": sorted(
                                    self._target.browsers.prune_names,
                                ),
                            },
                        },
                        "node_version": self._config.node_version
                        if spec.node_runtime
                        else "",
                        "policy": ctx.policy,
                        "source_lock": ctx.lock_hash,
                        "chunking": ctx.chunking.document(),
                        "format": 1,
                        "dependencies": {
                            name: ctx.fingerprints[name]
                            for name in spec.requires
                        },
                        "acquisition": getsource(object=self._stage_component)
                        + (
                            getsource(object=self._install_python)
                            if spec.python_packages
                            else ""
                        )
                        + (
                            getsource(object=self._install_chromium)
                            if spec.browsers
                            else ""
                        )
                        + (
                            getsource(object=self._install_node_runtime)
                            if spec.node_runtime
                            else ""
                        )
                        + (
                            getsource(object=self._install_node_packages)
                            if spec.node_packages
                            else ""
                        )
                        + (
                            hash_file(path=Path(zstd_portable___file__))
                            if spec.zstd_cli
                            else ""
                        ),
                    },
                ),
            )
            ctx.fingerprints[spec.name] = fingerprint
            record: dict[str, Json] = ctx.previous_records.get(spec.name, {})
            changed: bool = (
                ctx.rebuild
                or spec.name in ctx.only
                or ctx.previous is None
                or (record.get("fingerprint") != fingerprint)
                or any(ctx.plan.get(name) == "BUILD" for name in spec.requires)
            )
            if not changed:
                try:
                    stage_relative: str = str(object=record["stage"])
                    if not (ctx.cache / stage_relative).is_dir():
                        msg: str = "Missing staged component"
                        raise FormatError(msg)
                    recipe: Recipe = load_recipe(value=record.get("recipe"))
                    if (
                        ctx.previous is None
                        or recipe != ctx.previous["components"][spec.name]
                    ):
                        msg = "Cached recipe differs from previous catalog"
                        raise FormatError(msg)
                    ctx.recipes[spec.name] = recipe
                    ctx.reused[spec.name] = record
                except (OSError, ValueError, KeyError):
                    changed = True
            ctx.plan[spec.name] = "BUILD" if changed else "REUSE"

    def _partition_stage(self, ctx: _PartitionBuild) -> None:
        """Stage the incremental filesystem build phase.

        Args:
            ctx: Current incremental build state.

        """
        total: int = len(ctx.specs)
        ctx.heartbeat.advance(step="stage")
        for index, spec in enumerate(iterable=ctx.specs):
            ctx.heartbeat.state["fraction"] = str(object=index / total)
            ctx.heartbeat.state["detail"] = (
                f"{spec.name} ({index + 1}/{total})"
            )
            if ctx.plan[spec.name] == "REUSE":
                record: dict[str, Json] = ctx.reused[spec.name]
                (ctx.generation / spec.name).symlink_to(
                    target=ctx.cache / str(object=record["stage"]),
                    target_is_directory=True,
                )
                ctx.records[spec.name] = record
                continue
            browsers: dict[str, dict[str, str]] = self._stage_component(
                spec=spec,
                staging=ctx.generation,
                heartbeat=ctx.heartbeat,
            )
            ctx.heartbeat.advance(step="scan")
            ctx.heartbeat.state["fraction"] = str(object=(index + 0.5) / total)
            ctx.heartbeat.state["detail"] = (
                f"{spec.name} ({index + 1}/{total})"
            )

            def scanned(files: int, size: int, name: str = spec.name) -> None:
                """Update file and byte scan progress.

                Args:
                    files: Files for this operation.
                    size: Size for this operation.
                    name: Name for this operation.

                """
                ctx.heartbeat.state["detail"] = (
                    f"{name}: {files} files, {size} bytes scanned"
                )
                ctx.heartbeat.state["files_scanned"] = str(object=files)
                ctx.heartbeat.state["bytes_scanned"] = str(object=size)

            scanner: RecipeScanner = RecipeScanner(
                objects=ctx.store.objects,
                chunking=ctx.chunking,
                progress=scanned,
            )
            recipe: Recipe = scanner.scan(
                root=ctx.generation / spec.name,
                name=spec.name,
                metadata={},
            )
            ctx.metadata = self._component_manifest(
                spec=spec,
                stage=ctx.generation / spec.name,
                tree_sha256=recipe["tree_sha256"],
            )
            if browsers:
                ctx.metadata["browsers"] = cast(typ="Json", val=browsers)
            recipe["metadata"] = ctx.metadata
            recipe["recipe_sha256"] = recipe_identity(recipe=recipe)
            ctx.recipes[spec.name] = recipe
            ctx.records[spec.name] = {
                "fingerprint": ctx.fingerprints[spec.name],
                "stage": (ctx.generation / spec.name)
                .relative_to(ctx.cache)
                .as_posix(),
                "recipe": cast(typ="PartitionJson", val=recipe),
            }
            ctx.heartbeat.advance(step="stage")
        ctx.heartbeat.advance(step="membership")

    def _partition_packs(self, ctx: _PartitionBuild) -> None:
        """Packs the incremental filesystem build phase.

        Args:
            ctx: Current incremental build state.

        """
        ctx.candidate = Path(ctx.scratch) / "fs"
        ctx.heartbeat.advance(step="pack")

        def packed(built: int, reused_count: int, total: int) -> None:
            """Publish the current pack build and reuse counts.

            Args:
                built: Built for this operation.
                reused_count: Reused count for this operation.
                total: Planned pack count for this build.

            """
            ctx.heartbeat.state["fraction"] = (
                str(object=(built + reused_count) / total) if total else "1"
            )
            ctx.heartbeat.state["detail"] = f"{built + reused_count}/{
                total
            } packs ({built} built, {reused_count} reused)"

        ctx.catalog = ctx.store.build(
            recipes=ctx.recipes,
            output=ctx.candidate,
            platform=self._target.name,
            pack_target=min(ctx.part_bytes, 64 * 1024 * 1024),
            progress=packed,
        )
        ctx.heartbeat.advance(step="catalog")
        ctx.store.verify(catalog=ctx.catalog, root=ctx.candidate)
        ctx.root = ctx.catalog["root_sha256"]
        ctx.snapshot = ctx.cache / "catalogs" / ctx.root
        if not ctx.snapshot.exists():
            ctx.snapshot.parent.mkdir(parents=True, exist_ok=True)
            ctx.candidate.rename(target=ctx.snapshot)
        else:
            ctx.store.verify(
                catalog=load_catalog(path=ctx.snapshot / "catalog.json"),
                root=ctx.snapshot,
            )

    def _partition_runtime(self, ctx: _PartitionBuild) -> None:
        """Runtime the incremental filesystem build phase.

        Args:
            ctx: Current incremental build state.

        """
        ctx.heartbeat.advance(step="launcher")
        self._output.parent.mkdir(parents=True, exist_ok=True)
        ctx.parts_relative = Path(
            relpath(
                path=self._parts_dir / "fs" / "catalog.json",
                start=self._output.parent,
            ),
        ).as_posix()
        ctx.launcher = dedent(
            text=(
                f"\n            #!/usr/bin/env python3\n  "
                f"          # {stub_marker()}\n            "
                f'"""Offline partitioned filesystem dispatcher."""\n'
                f"            from pathlib import Path\n            "
                f"from typing import TYPE_CHECKING\n\n            "
                f"if TYPE_CHECKING or __package__:\n                "
                f"from .partition_launcher import main\n            "
                f"else:\n                "
                f"from partition_launcher import main\n\n            "
                f'if __name__ == "__main__":\n                '
                f"catalog: Path = Path(__file__)"
                f".resolve().parent\n                "
                f"catalog /= {dumps(obj=ctx.parts_relative)}\n"
                f"                raise SystemExit("
                f"main(catalog_path=catalog))\n            "
            ),
        ).removeprefix("\n")
        atomic_bytes(
            path=self._output.parent / "__init__.py",
            data=(
                b'"""Provide the generated partitioned offline tool runtim'
                b'e."""\n'
            ),
        )
        ancestor: Path = self._output.parent.parent
        while (
            ancestor != BuildToolsDefaults.bundle_root
            and BuildToolsDefaults.bundle_root in ancestor.parents
        ):
            marker: Path = ancestor / "__init__.py"
            if not marker.is_file():
                atomic_bytes(
                    path=marker,
                    data=(
                        b'"""Provide the generated tool-bundle namespace."""\n'
                    ),
                )
            ancestor = ancestor.parent
        ctx.runtime_files = (
            "partition_fs.py",
            "partition_launcher.py",
            "conflict_copies.py",
        )
        for filename in ctx.runtime_files:
            source: Path = BuildToolsDefaults.script_dir / filename
            if not source.is_file():
                source = (
                    BuildToolsDefaults.script_dir.parents[1]
                    / "tools"
                    / "common"
                    / filename
                )
            atomic_bytes(
                path=self._output.parent / filename,
                data=source.read_bytes(),
            )
        atomic_bytes(
            path=self._output.parent / "__main__.py",
            data=ctx.launcher.encode(),
        )
        export_package(
            os_name=self._target.os,
            machine=self._target.arch,
            target=self._output.parent,
        )
        ctx.metadata = {
            "schema_version": 5,
            "format": ctx.catalog["format"],
            "platform": self._target.name,
            "catalog_root": ctx.root,
            "catalog": ctx.parts_relative,
            "components": cast(typ="PartitionJson", val=ctx.recipes),
            "versions": {
                "node": self._config.node_version,
                "python": {
                    key: value
                    for recipe in ctx.recipes.values()
                    for key, value in cast(
                        typ="dict[str, PartitionJson]",
                        val=cast(
                            typ="dict[str, PartitionJson]",
                            val=recipe["metadata"]["versions"],
                        )["python"],
                    ).items()
                },
                "node_packages": {
                    key: value
                    for recipe in ctx.recipes.values()
                    for key, value in cast(
                        typ="dict[str, PartitionJson]",
                        val=cast(
                            typ="dict[str, PartitionJson]",
                            val=recipe["metadata"]["versions"],
                        )["node"],
                    ).items()
                },
            },
        }
        module: str = "exactus.bundle." + self._target.name.replace("-", ".")
        relative: str = "exactus/bundle/" + self._target.name.replace("-", "/")
        ctx.readme = (
            f"# Offline partitioned tools\n\nRun this "
            f"package with `python -m {module}` or `python {relative}`. "
            f"Keep __init__.py, __main__.py, partition_fs.py, "
            f"partition_launcher.py, conflict_copies.py, zstd_portable/, "
            f"and data/ together. JSON metadata is in data/bundle.json "
            f"and data/metrics.json; the catalog and packs are in "
            f"data/parts/fs/. Runtime is offline.\n\n"
            f"Use `list-tools`, `--verify`, `--verify-deep`, or `TOOL "
            f"[ARGS...]`. Components materialize lazily with their "
            f"dependencies. Cache: EXACTUS_TOOLS_CACHE or "
            f"${{XDG_CACHE_HOME:-~/.cache}}/exactus-tools/<catalog-root>. "
            f"Set EXACTUS_TOOLS_OBJECT_CACHE=discard to discard decoded "
            f"objects after materialization.\n\n"
            f"Builds reuse unchanged staged recipes and packs. --only "
            f"forces named selected components; --rebuild restages all. "
            f"Incremental rebuilds emit a sibling `<leaf>.update/` "
            f"directory holding the new catalog and only the changed "
            f"packs. Apply with `--apply-update <dir>`; rollback with "
            f"`--rollback`. Explicit GC is opt-in.\n\n"
            f"Catalog root: `{ctx.root}`\n"
        )

    def _partition_delta(self, ctx: _PartitionBuild) -> None:
        """Delta the incremental filesystem build phase.

        Args:
            ctx: Current incremental build state.

        """
        ctx.heartbeat.advance(step="delta")
        ctx.delta_bytes = 0
        if ctx.previous is not None:
            delta_folder: Path = Path(ctx.scratch) / "update"
            update: dict[str, Json] = write_delta(
                baseline=ctx.previous,
                current=ctx.catalog,
                source=ctx.snapshot,
                output=delta_folder,
            )
            ctx.delta_bytes = int(str(object=update["update_bytes"]))
            leaf: Path = (
                self._output.parent
                if self._output.name == "__main__.py"
                else self._output.with_suffix(suffix="")
            )
            update_dir: Path = leaf.with_name(name=f"{leaf.name}.update")
            if update_dir.exists():
                rmtree(path=update_dir)
            delta_folder.rename(target=update_dir)
            write_directory_readmes(root=update_dir)

    def _partition_publish(self, ctx: _PartitionBuild) -> None:
        """Publish the incremental filesystem build phase.

        Args:
            ctx: Current incremental build state.

        """
        live: Path = self._parts_dir / "fs"
        for pack in ctx.catalog["packs"].values():
            path: Path = live / pack["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or hash_file(path=path) != pack["sha256"]:
                sibling: Path = path.with_name(
                    name=f".{path.name}.{uuid4().hex}.tmp",
                )
                copyfile(src=ctx.snapshot / pack["path"], dst=sibling)
                sibling.replace(target=path)
        PartitionStore.verify(catalog=ctx.catalog, root=live)
        if ctx.previous is not None:
            atomic_bytes(
                path=live / "catalogs" / f"{ctx.previous['root_sha256']}.json",
                data=canonical(
                    value=cast(typ="PartitionJson", val=ctx.previous),
                ),
            )
        atomic_bytes(
            path=live / "catalogs" / f"{ctx.root}.json",
            data=canonical(value=cast(typ="PartitionJson", val=ctx.catalog)),
        )
        atomic_bytes(
            path=live / "catalog.json",
            data=canonical(value=cast(typ="PartitionJson", val=ctx.catalog)),
        )
        atomic_bytes(path=self._output, data=ctx.launcher.encode())
        self._output.chmod(mode=493)
        atomic_bytes(
            path=self._output.parent / "data" / "bundle.json",
            data=canonical(value=ctx.metadata),
        )
        atomic_bytes(
            path=self._output.parent / "README.md",
            data=ctx.readme.encode(),
        )
        atomic_bytes(
            path=self._parts_dir / "README.md",
            data=ctx.readme.encode(),
        )
        write_directory_readmes(root=self._output.parent / "data")
        write_directory_readmes(root=self._parts_dir)

    def _partition_finish(self, ctx: _PartitionBuild) -> None:
        """Finish the incremental filesystem build phase.

        Args:
            ctx: Current incremental build state.

        """
        atomic_bytes(
            path=self._output.parent / "data" / "metrics.json",
            data=canonical(value=ctx.stats),
        )
        atomic_bytes(
            path=ctx.state_path,
            data=canonical(
                value={
                    "schema_version": 1,
                    "catalog_root": ctx.root,
                    "components": cast(typ="PartitionJson", val=ctx.records),
                },
            ),
        )
        ctx.heartbeat.stop()
        self._write_status(
            document=self._document(
                heartbeat=ctx.heartbeat,
                status="DONE",
                extra=cast(typ="dict[str, Json]", val=ctx.stats),
            ),
        )


def _build_parser() -> ArgumentParser:
    """Build the command-line parser.

    Returns:
        Parser configured with every builder option.

    """
    parser: ArgumentParser = ExactusArgumentParser()
    _ = parser.add_argument(
        "--target",
        action="extend",
        nargs="+",
        choices=(*Constants.targets, *Constants.target_groups, "auto", "all"),
        default=None,
        help=(
            "Target platform(s) (OS/architecture/libc); accepts several "
            "values after one flag and may be repeated. `auto` selects "
            "the build host, `all` selects every target, and group "
            "aliases expand to their members: "
        )
        + ", ".join(sorted(Constants.target_groups))
        + ". Default: `[tool.bundle] targets`, else `auto`.",
    )
    _ = parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Destination launcher for a single target. Default: PROJECT"
            "_ROOT/exactus/bundle/<target>/__main__.py."
        ),
    )
    _ = parser.add_argument("--node-version", default="22.21.1")
    _ = parser.add_argument(
        "--parts-dir",
        type=Path,
        default=None,
        help=(
            "Payload-parts directory. Default: data/parts/ beside the "
            "resolved launcher."
        ),
    )
    _ = parser.add_argument(
        "--part-bytes",
        type=int,
        default=BuildToolsDefaults.default_parts_bytes,
        help="Maximum bytes per Git payload file; must be <= 90,000,000.",
    )
    optional_choices: tuple[str, ...] = tuple(
        sorted(
            {
                "all",
                *Constants.groups,
                *Constants.components,
                *Constants.tool_component,
            },
        ),
    )
    _ = parser.add_argument(
        "--optional",
        action="extend",
        nargs="+",
        choices=optional_choices,
        default=[],
        help=(
            "Optional component, tool, or group; accepts several values "
            "after one flag (`--optional browser docs`) and may be "
            "repeated. Merged with `[tool.bundle] optional` from "
            "pyproject.toml. Groups: "
        )
        + ", ".join(sorted(Constants.groups))
        + (
            ", all (every optional component). This project's bundle "
            "requires `browser`, `jinja2`, and `pillow`."
        ),
    )
    _ = parser.add_argument(
        "--exclude",
        action="extend",
        nargs="+",
        choices=optional_choices,
        default=[],
        help=(
            "Component, tool, or group to drop from the final selection, "
            "e.g. `--exclude pillow` removes the component pulled in by "
            "`[tool.bundle] optional`. Exclusions are ignored for "
            "dependencies a kept component still requires and for the "
            "mandatory `zstd-cli` component."
        ),
    )
    _ = parser.add_argument(
        "--only",
        action="extend",
        nargs="+",
        choices=tuple(sorted(Constants.components)),
        default=[],
        help=(
            "Force acquisition/scanning of these selected components; "
            "reuse valid siblings. Names can include tools or groups."
        ),
    )
    _ = parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Force all selected components to restage and rescan.",
    )
    return parser


def _expand_target_name(
    *,
    parser: ArgumentParser,
    name: str,
) -> tuple[str, ...]:
    """Expand one requested name into catalog target names.

    Args:
        parser: Command-line parser used to report usage errors.
        name: Requested target, group alias, ``auto``, or ``all``.

    Returns:
        Catalog target names the request expands to.

    """
    if name == "all":
        return tuple(Constants.targets)
    if name in Constants.target_groups:
        return Constants.target_groups[name]
    if name == "auto":
        if (host := host_target()) is None:
            parser.error(message="--target auto cannot detect this host")
        return (host,)
    if name in Constants.targets:
        return (name,)
    return parser.error(message=f"[tool.bundle] unknown target: {name}")


def _resolve_targets(
    *,
    parser: ArgumentParser,
    options: BuildOptions,
    file_config: BundleFileConfig,
) -> tuple[BuildTarget, ...]:
    """Resolve requested target names into build targets.

    Args:
        parser: Command-line parser used to report usage errors.
        options: Parsed command-line options.
        file_config: ``[tool.bundle]`` defaults.

    Returns:
        Deduplicated build targets in request order.

    """
    raw_targets: list[str] = list(options.target or ())
    if not raw_targets:
        raw_targets = [*file_config.targets]
        if file_config.target is not None:
            raw_targets.append(file_config.target)
    if not raw_targets:
        raw_targets = ["auto"]
    target_names: list[str] = []
    for name in raw_targets:
        target_names.extend(_expand_target_name(parser=parser, name=name))
    targets: tuple[BuildTarget, ...] = tuple(
        Constants.targets[name] for name in dict.fromkeys(target_names)
    )
    if len(targets) > 1 and (
        (options.output or file_config.output) is not None
        or (options.parts_dir or file_config.parts_dir) is not None
    ):
        parser.error(
            message="--output and --parts-dir require a single --target",
        )
    return targets


def main() -> int:
    """Build the configured bundle.

    Returns:
        Process status.

    """
    _ = clear_conflict_copies(root=BuildToolsDefaults.project_root)
    parser: ArgumentParser = _build_parser()
    options: BuildOptions = parser.parse_args(namespace=BuildOptions())
    try:
        file_config: BundleFileConfig = bundle_file_config(
            path=BuildToolsDefaults.project_root / "pyproject.toml",
        )
    except (TypeError, ValueError) as exc:
        parser.error(message=str(object=exc))
    try:
        requested_components: tuple[str, ...] = resolve_components(
            names=(*file_config.optional, *(options.optional or ())),
        )
        excluded_components: frozenset[str] = frozenset(
            resolve_components(
                names=(*file_config.exclude, *(options.exclude or ())),
                follow_requires=False,
            ),
        )
    except ValueError as exc:
        parser.error(message=str(object=exc))
    optional: tuple[str, ...] = tuple(
        name
        for name in requested_components
        if name not in excluded_components
        and Constants.components[name].optional
    )
    try:
        only: tuple[str, ...] = resolve_components(
            names=(*file_config.only, *(options.only or ())),
            follow_requires=False,
        )
    except ValueError as exc:
        parser.error(message=str(object=exc))
    targets: tuple[BuildTarget, ...] = _resolve_targets(
        parser=parser,
        options=options,
        file_config=file_config,
    )
    node_version: str = (
        options.node_version or file_config.node_version or "22.21.1"
    )
    part_bytes: int = (
        options.part_bytes
        or file_config.part_bytes
        or BuildToolsDefaults.default_parts_bytes
    )
    config: BundleConfig = BundleConfig(
        node_version=node_version,
        optional=tuple(
            dict.fromkeys(
                (
                    *optional,
                    *(
                        name
                        for name in only
                        if Constants.components[name].optional
                    ),
                ),
            ),
        ),
        exclude=excluded_components,
    )
    for target in targets:
        target_config: BundleConfig = config
        unavailable: frozenset[str] = unavailable_components(
            target=target.name,
        )
        if unavailable:
            target_config = replace(
                config,
                optional=tuple(
                    name for name in config.optional if name not in unavailable
                ),
            )
        _ = BundleBuilder(
            config=target_config,
            output=options.output
            or file_config.output
            or bundle_dir(target=target.name) / "__main__.py",
            rebuild_args=tuple(argv[1:]),
            parts_dir=options.parts_dir or file_config.parts_dir,
            target=target,
        ).build(
            part_bytes=part_bytes,
            only=only,
            rebuild=options.rebuild or file_config.rebuild,
        )
    _ = write_content(root=BuildToolsDefaults.bundle_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
