# `bundle/` contents

Generated inventory of the offline tool payloads staged in this
directory. Regenerate with `python exactus/scripts/bundle_make`
(full source bundle) or `python exactus/scripts/build_make`
(staged subset).

## Targets

| Platform | OS | Libc | Architecture | Components |
| --- | --- | --- | --- | --- |
| `linux-glibc-amd64` | linux | glibc | amd64 | `basedpyright_coverage_pyrefly_pytest_ruff`, `build_twine`, `chromium`, `defusedxml`, `eslint_htmlhint_jslint_prettier_stylelint_tsc`, `fastapi_httpx_httpx2_mcp_pydantic_uvicorn`, `hypothesis_mutmut`, `jinja2`, `node`, `pillow`, `playwright`, `psutil`, `tree-sitter_tree-sitter-language-pack`, `zstd-cli` |
| `linux-glibc-arm64` | linux | glibc | arm64 | `basedpyright_coverage_pyrefly_pytest_ruff`, `build_twine`, `chromium`, `defusedxml`, `eslint_htmlhint_jslint_prettier_stylelint_tsc`, `fastapi_httpx_httpx2_mcp_pydantic_uvicorn`, `hypothesis_mutmut`, `jinja2`, `node`, `pillow`, `playwright`, `psutil`, `tree-sitter_tree-sitter-language-pack`, `zstd-cli` |
| `linux-musl-amd64` | linux | musl | amd64 | `basedpyright_coverage_pyrefly_pytest_ruff`, `build_twine`, `defusedxml`, `eslint_htmlhint_jslint_prettier_stylelint_tsc`, `fastapi_httpx_httpx2_mcp_pydantic_uvicorn`, `hypothesis_mutmut`, `jinja2`, `node`, `pillow`, `psutil`, `tree-sitter_tree-sitter-language-pack`, `zstd-cli` |
| `linux-musl-arm64` | linux | musl | arm64 | `basedpyright_coverage_pyrefly_pytest_ruff`, `build_twine`, `defusedxml`, `eslint_htmlhint_jslint_prettier_stylelint_tsc`, `fastapi_httpx_httpx2_mcp_pydantic_uvicorn`, `hypothesis_mutmut`, `jinja2`, `node`, `pillow`, `psutil`, `zstd-cli` |
| `macos-amd64` | macos | — | amd64 | `basedpyright_coverage_pyrefly_pytest_ruff`, `build_twine`, `chromium`, `defusedxml`, `eslint_htmlhint_jslint_prettier_stylelint_tsc`, `fastapi_httpx_httpx2_mcp_pydantic_uvicorn`, `hypothesis_mutmut`, `jinja2`, `node`, `pillow`, `playwright`, `psutil`, `tree-sitter_tree-sitter-language-pack`, `zstd-cli` |
| `macos-arm64` | macos | — | arm64 | `basedpyright_coverage_pyrefly_pytest_ruff`, `build_twine`, `chromium`, `defusedxml`, `eslint_htmlhint_jslint_prettier_stylelint_tsc`, `fastapi_httpx_httpx2_mcp_pydantic_uvicorn`, `hypothesis_mutmut`, `jinja2`, `node`, `pillow`, `playwright`, `psutil`, `tree-sitter_tree-sitter-language-pack`, `zstd-cli` |
| `windows-amd64` | windows | — | amd64 | `basedpyright_coverage_pyrefly_pytest_ruff`, `build_twine`, `chromium`, `defusedxml`, `eslint_htmlhint_jslint_prettier_stylelint_tsc`, `fastapi_httpx_httpx2_mcp_pydantic_uvicorn`, `hypothesis_mutmut`, `jinja2`, `node`, `pillow`, `playwright`, `psutil`, `tree-sitter_tree-sitter-language-pack`, `zstd-cli` |
| `windows-arm64` | windows | — | arm64 | `basedpyright_coverage_pyrefly_pytest_ruff`, `build_twine`, `chromium`, `defusedxml`, `eslint_htmlhint_jslint_prettier_stylelint_tsc`, `fastapi_httpx_httpx2_mcp_pydantic_uvicorn`, `jinja2`, `node`, `pillow`, `playwright`, `psutil`, `tree-sitter_tree-sitter-language-pack`, `zstd-cli` |

## Installed tools

| Tool | Version | Targets |
| --- | --- | --- |
| `abbrev` | `1.1.1` | all |
| `acorn` | `8.19.0` | all |
| `acorn-jsx` | `5.3.2` | all |
| `ajv` | `6.15.0` | all |
| `annotated_doc` | `0.0.5` | all |
| `annotated_types` | `0.8.0` | all |
| `ansi-regex` | `6.4.0` | all |
| `ansi-styles` | `4.3.0` | all |
| `anyio` | `4.15.1` | all |
| `are-docs-informative` | `0.1.1` | all |
| `argparse` | `2.0.1` | all |
| `astral-regex` | `2.0.0` | all |
| `async` | `3.2.6` | all |
| `attrs` | `26.1.0` | all |
| `balanced-match` | `4.0.4` | all |
| `basedpyright` | `1.40.2` | all |
| `brace-expansion` | `5.0.12` | all |
| `braces` | `3.0.3` | all |
| `buffer-shims` | `1.0.0` | all |
| `build` | `1.6.1` | all |
| `cacheable` | `2.5.0` | all |
| `callsites` | `3.1.0` | all |
| `certifi` | `2026.10.23` | all |
| `cffi` | `2.1.1` | all |
| `chalk` | `4.1.2` | all |
| `charset_normalizer` | `3.5.2` | all |
| `click` | `8.5.0` | all |
| `color-convert` | `2.0.1` | all |
| `color-name` | `1.1.4` | all |
| `colord` | `2.10.0` | all |
| `commander` | `11.1.0` | all |
| `comment-parser` | `1.4.9` | all |
| `concat-map` | `0.0.1` | all |
| `core-util-is` | `1.0.3` | all |
| `cosmiconfig` | `9.0.2` | all |
| `coverage` | `7.17.0` | all |
| `cross-spawn` | `7.0.6` | all |
| `cryptography` | `46.0.3` | windows-arm64 |
| `cryptography` | `48.0.1` | macos-amd64 |
| `cryptography` | `50.0.2` | linux-glibc-amd64, linux-glibc-arm64, linux-musl-amd64, linux-musl-arm64, macos-arm64, windows-amd64 |
| `css-functions-list` | `3.3.3` | all |
| `css-tree` | `3.2.1` | all |
| `cssesc` | `3.0.0` | all |
| `debug` | `4.4.3` | all |
| `deep-is` | `0.1.4` | all |
| `defusedxml` | `0.7.1` | all |
| `docutils` | `0.23` | all |
| `emoji-regex` | `8.0.0` | all |
| `env-paths` | `2.2.1` | all |
| `error-ex` | `1.3.4` | all |
| `escape-string-regexp` | `4.0.0` | all |
| `eslint` | `10.13.0` | all |
| `eslint-plugin-jsdoc` | `65.4.2` | all |
| `eslint-scope` | `9.1.2` | all |
| `eslint-visitor-keys` | `5.0.1` | all |
| `espree` | `11.2.0` | all |
| `esprima` | `4.0.1` | all |
| `esquery` | `1.7.0` | all |
| `esrecurse` | `4.3.0` | all |
| `estraverse` | `5.3.0` | all |
| `esutils` | `2.0.3` | all |
| `exit` | `0.1.2` | all |
| `fast-deep-equal` | `3.1.3` | all |
| `fast-glob` | `3.3.3` | all |
| `fast-json-stable-stringify` | `2.1.0` | all |
| `fast-levenshtein` | `2.0.6` | all |
| `fast-uri` | `3.1.9` | all |
| `fastapi` | `0.162.0` | all |
| `fastest-levenshtein` | `1.0.16` | all |
| `fastq` | `1.20.3` | all |
| `file-entry-cache` | `11.1.5` | all |
| `fill-range` | `7.1.1` | all |
| `find-up` | `5.0.0` | all |
| `flat-cache` | `6.1.23` | all |
| `flatted` | `3.4.4` | all |
| `fs-extra` | `11.4.1` | all |
| `fs.realpath` | `1.0.0` | all |
| `get-east-asian-width` | `1.7.0` | all |
| `glob` | `13.0.6` | all |
| `glob-parent` | `6.0.2` | all |
| `global-modules` | `2.0.0` | all |
| `global-prefix` | `3.0.0` | all |
| `globby` | `16.2.4` | all |
| `globjoin` | `0.1.4` | all |
| `graceful-fs` | `4.2.11` | all |
| `greenlet` | `3.2.5` | linux-glibc-amd64, linux-glibc-arm64 |
| `greenlet` | `3.5.6` | macos-amd64, macos-arm64, windows-amd64, windows-arm64 |
| `h11` | `0.16.0` | all |
| `has-flag` | `4.0.0` | all |
| `hashery` | `1.5.1` | all |
| `hookified` | `1.15.1` | all |
| `html-entities` | `2.6.0` | all |
| `html-tags` | `5.1.0` | all |
| `htmlhint` | `1.9.2` | all |
| `httpcore` | `1.0.9` | all |
| `httpcore2` | `2.16.0` | all |
| `httpx` | `0.28.1` | all |
| `httpx2` | `2.16.0` | all |
| `hypothesis` | `6.170.13` | linux-glibc-amd64, linux-glibc-arm64, linux-musl-amd64, linux-musl-arm64, macos-amd64, macos-arm64, windows-amd64 |
| `id` | `1.6.1` | all |
| `idna` | `3.20` | all |
| `ignore` | `5.3.2` | all |
| `import-fresh` | `3.3.1` | all |
| `import-meta-resolve` | `4.2.0` | all |
| `imurmurhash` | `0.1.4` | all |
| `inflight` | `1.0.6` | all |
| `inherits` | `2.0.4` | all |
| `ini` | `1.3.8` | all |
| `iniconfig` | `2.3.1` | all |
| `is-arrayish` | `0.2.1` | all |
| `is-extglob` | `2.1.1` | all |
| `is-fullwidth-code-point` | `3.0.0` | all |
| `is-glob` | `4.0.3` | all |
| `is-number` | `7.0.0` | all |
| `is-path-inside` | `4.0.0` | all |
| `isarray` | `1.0.0` | all |
| `isexe` | `2.0.0` | all |
| `jaraco.classes` | `3.4.0` | all |
| `jaraco_context` | `6.1.2` | all |
| `jaraco_functools` | `4.6.0` | all |
| `jinja2` | `3.1.6` | all |
| `js-tokens` | `4.0.0` | all |
| `js-yaml` | `4.3.2` | all |
| `jsdoc-type-pratt-parser` | `9.4.0` | all |
| `jslint` | `0.12.1` | all |
| `json-parse-even-better-errors` | `2.3.1` | all |
| `json-schema-traverse` | `0.4.1` | all |
| `json-stable-stringify-without-jsonify` | `1.0.1` | all |
| `jsonfile` | `6.2.1` | all |
| `jsonschema` | `4.26.0` | all |
| `jsonschema_specifications` | `2025.9.1` | all |
| `keyring` | `25.7.0` | all |
| `keyv` | `5.6.0` | all |
| `kind-of` | `6.0.3` | all |
| `levn` | `0.4.1` | all |
| `libcst` | `1.7.0` | linux-glibc-amd64, linux-glibc-arm64 |
| `libcst` | `1.8.6` | macos-amd64 |
| `libcst` | `1.9.0` | linux-musl-amd64, linux-musl-arm64, macos-arm64, windows-amd64 |
| `lines-and-columns` | `1.2.4` | all |
| `linkify_it_py` | `2.2.0` | linux-glibc-amd64, linux-glibc-arm64, linux-musl-amd64, linux-musl-arm64, macos-amd64, macos-arm64, windows-amd64 |
| `locate-path` | `6.0.0` | all |
| `lodash.truncate` | `4.4.2` | all |
| `lru-cache` | `11.5.3` | all |
| `markdown_it_py` | `4.2.0` | all |
| `markupsafe` | `3.0.4` | all |
| `mathml-tag-names` | `4.0.0` | all |
| `mcp` | `2.3.0` | all |
| `mcp_types` | `2.3.0` | all |
| `mdit_py_plugins` | `0.6.1` | linux-glibc-amd64, linux-glibc-arm64, linux-musl-amd64, linux-musl-arm64, macos-amd64, macos-arm64, windows-amd64 |
| `mdn-data` | `2.27.1` | all |
| `mdurl` | `0.1.2` | all |
| `meow` | `14.1.0` | all |
| `merge2` | `1.4.1` | all |
| `micromatch` | `4.0.8` | all |
| `minimatch` | `10.2.6` | all |
| `minipass` | `7.1.3` | all |
| `more_itertools` | `11.2.1` | all |
| `ms` | `2.1.3` | all |
| `msvc_runtime` | `14.51.36231` | windows-amd64 |
| `mutmut` | `3.3.1` | linux-glibc-amd64, linux-glibc-arm64 |
| `mutmut` | `3.7.0` | macos-amd64 |
| `mutmut` | `3.8.1` | linux-musl-amd64, linux-musl-arm64, macos-arm64, windows-amd64 |
| `nanoid` | `3.3.20` | all |
| `natural-compare` | `1.4.0` | all |
| `nh3` | `0.3.7` | all |
| `node` | `22.21.1` | all |
| `node-sarif-builder` | `3.2.0` | all |
| `nodejs_wheel_binaries` | `22.20.0` | linux-glibc-amd64, linux-glibc-arm64 |
| `nodejs_wheel_binaries` | `24.19.0` | linux-musl-amd64, linux-musl-arm64, macos-amd64, macos-arm64, windows-amd64, windows-arm64 |
| `nopt` | `4.0.3` | all |
| `normalize-path` | `3.0.0` | all |
| `object-deep-merge` | `2.0.1` | all |
| `once` | `1.4.0` | all |
| `opentelemetry_api` | `1.45.1` | all |
| `optionator` | `0.9.4` | all |
| `os-homedir` | `1.0.2` | all |
| `os-tmpdir` | `1.0.2` | all |
| `osenv` | `0.1.5` | all |
| `p-limit` | `3.1.0` | all |
| `p-locate` | `5.0.0` | all |
| `packaging` | `26.3` | all |
| `parent-module` | `1.0.1` | all |
| `parse-imports-exports` | `0.2.4` | all |
| `parse-json` | `5.2.0` | all |
| `parse-statements` | `1.0.11` | all |
| `path-exists` | `4.0.0` | all |
| `path-is-absolute` | `1.0.1` | all |
| `path-key` | `3.1.1` | all |
| `path-scurry` | `2.0.2` | all |
| `picocolors` | `1.1.1` | all |
| `picomatch` | `2.3.2` | all |
| `pillow` | `12.2.0` | linux-glibc-amd64, linux-glibc-arm64 |
| `pillow` | `13.0.0` | linux-musl-amd64, linux-musl-arm64, macos-amd64, macos-arm64, windows-amd64, windows-arm64 |
| `platformdirs` | `4.14.0` | linux-glibc-amd64, linux-glibc-arm64, linux-musl-amd64, linux-musl-arm64, macos-amd64, macos-arm64, windows-amd64 |
| `playwright` | `1.64.1` | linux-glibc-amd64, linux-glibc-arm64, macos-amd64, macos-arm64, windows-amd64, windows-arm64 |
| `playwright-core` | `1.64.1` | linux-glibc-amd64, linux-glibc-arm64, macos-amd64, macos-arm64, windows-amd64, windows-arm64 |
| `pluggy` | `1.7.0` | all |
| `postcss` | `8.5.32` | all |
| `postcss-safe-parser` | `7.1.0` | all |
| `postcss-selector-parser` | `7.1.7` | all |
| `postcss-value-parser` | `4.2.0` | all |
| `prelude-ls` | `1.2.1` | all |
| `prettier` | `3.9.10` | all |
| `process-nextick-args` | `1.0.7` | all |
| `psutil` | `7.2.2` | all |
| `punycode` | `2.3.1` | all |
| `pycparser` | `3.12` | all |
| `pydantic` | `2.14.1` | all |
| `pydantic_core` | `2.50.1` | all |
| `pyee` | `14.0.0` | linux-glibc-amd64, linux-glibc-arm64, macos-amd64, macos-arm64, windows-amd64, windows-arm64 |
| `pygments` | `2.21.0` | all |
| `pyjwt` | `2.15.1` | all |
| `pyproject_hooks` | `1.3.3` | all |
| `pyrefly` | `1.4.0` | all |
| `pytest` | `9.2.0` | all |
| `python_dotenv` | `1.2.4` | all |
| `python_multipart` | `0.0.32` | all |
| `pyyaml` | `6.0.3` | linux-glibc-amd64, linux-glibc-arm64, linux-musl-amd64, linux-musl-arm64, macos-amd64, macos-arm64, windows-amd64 |
| `pyyaml_ft` | `8.0.0` | linux-musl-amd64, linux-musl-arm64, macos-amd64, macos-arm64, windows-amd64 |
| `qified` | `0.10.1` | all |
| `queue-microtask` | `1.2.3` | all |
| `readable-stream` | `2.1.5` | all |
| `readme_renderer` | `46.0` | all |
| `referencing` | `0.37.0` | all |
| `requests` | `2.34.2` | all |
| `requests_toolbelt` | `1.0.0` | all |
| `require-from-string` | `2.0.2` | all |
| `reserved-identifiers` | `1.2.0` | all |
| `resolve-from` | `4.0.0` | all |
| `reusify` | `1.1.0` | all |
| `rfc3986` | `2.0.0` | all |
| `rich` | `15.0.0` | all |
| `rpds_py` | `2026.9.1` | all |
| `ruff` | `0.17.3` | all |
| `run-parallel` | `1.2.0` | all |
| `semver` | `7.8.5` | all |
| `setproctitle` | `1.3.8` | linux-glibc-amd64, linux-glibc-arm64, linux-musl-amd64, linux-musl-arm64, macos-amd64, macos-arm64, windows-amd64 |
| `shebang-command` | `2.0.0` | all |
| `shebang-regex` | `3.0.0` | all |
| `shellingham` | `1.5.4` | all |
| `signal-exit` | `4.1.0` | all |
| `slash` | `5.1.0` | all |
| `slice-ansi` | `4.0.0` | all |
| `sortedcontainers` | `2.4.0` | linux-glibc-amd64, linux-glibc-arm64, linux-musl-amd64, linux-musl-arm64, macos-amd64, macos-arm64, windows-amd64 |
| `source-map` | `0.7.6` | all |
| `source-map-js` | `1.2.2` | all |
| `spdx-exceptions` | `2.5.0` | all |
| `spdx-expression-parse` | `5.0.0` | all |
| `spdx-license-ids` | `3.0.24` | all |
| `sse_starlette` | `3.6.0` | all |
| `starlette` | `1.10.0` | all |
| `string-width` | `8.3.0` | all |
| `string_decoder` | `0.10.31` | all |
| `strip-ansi` | `7.2.0` | all |
| `strip-json-comments` | `3.1.1` | all |
| `stylelint` | `17.16.0` | all |
| `supports-color` | `7.2.0` | all |
| `supports-hyperlinks` | `4.6.0` | all |
| `svg-tags` | `1.0.0` | all |
| `table` | `6.9.0` | all |
| `textual` | `8.2.8` | linux-glibc-amd64, linux-glibc-arm64, linux-musl-amd64, linux-musl-arm64, macos-amd64, macos-arm64, windows-amd64 |
| `tinyglobby` | `0.2.17` | all |
| `to-regex-range` | `5.0.1` | all |
| `to-valid-identifier` | `1.0.0` | all |
| `tree_sitter` | `0.26.0` | linux-glibc-amd64, linux-glibc-arm64, linux-musl-amd64, macos-amd64, macos-arm64, windows-amd64, windows-arm64 |
| `tree_sitter_c_sharp` | `0.23.5` | linux-glibc-arm64, linux-musl-amd64 |
| `tree_sitter_embedded_template` | `0.25.0` | linux-glibc-arm64, linux-musl-amd64 |
| `tree_sitter_language_pack` | `0.13.0` | linux-glibc-arm64, linux-musl-amd64 |
| `tree_sitter_language_pack` | `1.22.1` | linux-glibc-amd64, macos-amd64, macos-arm64, windows-amd64, windows-arm64 |
| `tree_sitter_yaml` | `0.7.2` | linux-glibc-arm64, linux-musl-amd64 |
| `truststore` | `0.10.5` | all |
| `ts-api-utils` | `2.5.0` | all |
| `twine` | `7.0.0` | all |
| `type-check` | `0.4.0` | all |
| `typer` | `0.27.3` | all |
| `typescript` | `6.0.3` | all |
| `typing_extensions` | `4.16.0` | all |
| `typing_inspection` | `0.4.4` | all |
| `unicorn-magic` | `0.4.1` | all |
| `universalify` | `2.0.1` | all |
| `uri-js` | `4.4.1` | all |
| `urllib3` | `2.8.0` | all |
| `util-deprecate` | `1.0.2` | all |
| `uvicorn` | `0.54.0` | all |
| `which` | `2.0.2` | all |
| `word-wrap` | `1.2.5` | all |
| `wrappy` | `1.0.2` | all |
| `write-file-atomic` | `7.0.1` | all |
| `xml` | `1.0.1` | all |
| `yocto-queue` | `0.1.0` | all |
