# Copyright (c) 2026
"""Normalize the KWARGS_TYPEHINTS report: findings, metrics and tables.

The exactus core builds the legacy payload (``summary``, positional-call
``findings``, ``bare_imports``, ``type_hints``, ``ambiguous``,
``unresolved``) plus the call sites behind every unresolved callee
(``unresolved_sites``), the files that failed to parse
(``parse_failure_files``) and the path filters (``filters``).
``report_data`` keeps every legacy key and adds the normalized blocks the
report templates read: ``summary`` counters, ``scope``, one findings list
over every category (``id``/``title``/``severity``/``rule``/``category``/
``path``/``line``/``blocking``) ordered blocking categories first, and
``extension`` (``metrics``, ``unresolved_callees``,
``ambiguous_call_sites``, ``bare_imports``, ``methodology``) whose rows
name the finding they belong to.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

    from exactus.tools.common.json_types import JsonValue


class ReportTables:
    """Constants of the normalized KWARGS_TYPEHINTS report.

    Attributes:
        id_prefix: Prefix of every finding identifier.
        categories: Finding categories in report order (blocking first).
        labels: Display name of every category (the web filter and the
            Markdown group headings).
        severities: Severity of every category.
        blocking: Categories that fail the run (the tool exit status).
        levels: Severity names in report order.
        reasons: Why an unresolved callee has no signature, per reason
            code: short table label and the finding sentence.
        methodology: Methodology and caveat notes.

    """

    id_prefix: Final[str] = "KWARGS"
    categories: Final[tuple[str, ...]] = (
        "missing-kwargs",
        "bare-import",
        "missing-hint",
        "parse-failure",
        "ambiguous-call",
        "unresolved-callee",
    )
    labels: Final[dict[str, str]] = {
        "missing-kwargs": "Missing keyword arguments",
        "bare-import": "Bare imports",
        "missing-hint": "Missing type hints",
        "parse-failure": "Parse failures",
        "ambiguous-call": "Ambiguous calls",
        "unresolved-callee": "Unresolved callees",
    }
    severities: Final[dict[str, str]] = {
        "missing-kwargs": "error",
        "bare-import": "error",
        "missing-hint": "error",
        "parse-failure": "error",
        "ambiguous-call": "warning",
        "unresolved-callee": "info",
    }
    blocking: Final[frozenset[str]] = frozenset(
        {"missing-kwargs", "bare-import", "missing-hint", "parse-failure"},
    )
    levels: Final[tuple[str, ...]] = ("error", "warning", "info")
    reasons: Final[dict[str, tuple[str, str]]] = {
        "unknown-name": (
            "name not defined",
            "The name has no known definition",
        ),
        "unknown-receiver": (
            "receiver type unknown",
            "The receiver's type is unknown",
        ),
        "call-result": (
            "result of a call",
            "The callee is the result of another call",
        ),
        "subscript-lookup": (
            "subscript lookup",
            "The callee is a subscript lookup",
        ),
        "dynamic-expression": (
            "dynamic expression",
            "The callee is a dynamic expression",
        ),
    }
    methodology: Final[tuple[str, ...]] = (
        (
            "Signatures come from a repository-wide AST index (functions, "
            "methods, dataclass and `NamedTuple` fields, imports, "
            "`self.attr` assignments, annotations), `inspect.signature` "
            "for external callables and the typeshed stubs bundled with "
            "basedpyright."
        ),
        (
            "Confidence of a missing-keyword finding: `resolved` (project "
            "index), `constructor` (project class constructor), `external` "
            "(`inspect.signature`), `stub` (typeshed), `stub-rt` (typeshed "
            "checked by a runtime probe), `unique-name` (one class defines "
            "the method), `ambiguous-all-flag` (every candidate flags it)."
        ),
        (
            "Arguments after a `*unpack`, beyond the named parameters of a "
            "`*args` signature, or already passed by keyword are not "
            "reported."
        ),
        (
            "Calls to `pytest.mark.*`, standard-library positional-only "
            "methods and Qt-style `lowerCamelCase` methods are counted as "
            "exempt, not as unresolved."
        ),
        (
            "A variable needs one annotation per lexical scope; parameters "
            "own their type, walrus bindings, TypeVar declarations and "
            "Enum members are exempt, "
            "`self`/`cls` need none, and lambdas cannot be annotated."
        ),
        (
            "Hint coverage counts the parameters (receivers excluded) and "
            "return annotations of every function; variables are not part "
            "of the ratio."
        ),
        (
            "Unresolved callees (dynamic objects, `*args` wrappers, mocks, "
            "higher-order results) are listed so they can be checked by "
            "hand; they never fail the run."
        ),
        (
            "`ARTIFACTS/heuristics.json` holds the argument types observed "
            "by fuzzing builtin callables."
        ),
    )


def _object(value: JsonValue) -> dict[str, JsonValue]:
    """Return a JSON object, or an empty one for any other value.

    Args:
        value: Any JSON value.

    Returns:
        ``value`` when it is an object, else ``{}``.

    """
    return value if isinstance(value, dict) else {}


def _list(value: JsonValue) -> list[JsonValue]:
    """Return a JSON list, or an empty one for any other value.

    Args:
        value: Any JSON value.

    Returns:
        ``value`` when it is a list, else ``[]``.

    """
    return value if isinstance(value, list) else []


def _int(value: JsonValue) -> int:
    """Return a JSON integer, or zero for any other value.

    Args:
        value: Any JSON value.

    Returns:
        ``value`` when it is an integer (not a boolean), else ``0``.

    """
    return (
        value if isinstance(value, int) and not isinstance(value, bool) else 0
    )


def _text(value: JsonValue) -> str:
    """Return a JSON string, or an empty one for any other value.

    Args:
        value: Any JSON value.

    Returns:
        ``value`` when it is a string, else ``""``.

    """
    return value if isinstance(value, str) else ""


def _sentence(text: str) -> str:
    """Capitalize the first letter of a sentence fragment.

    Args:
        text: Sentence fragment.

    Returns:
        ``text`` with its first character upper-cased.

    """
    return text[:1].upper() + text[1:]


def _percent(*, part: int, whole: int) -> float | None:
    """Return ``part`` as a percentage of ``whole``.

    Args:
        part: Counted items.
        whole: All items.

    Returns:
        The percentage rounded to one decimal, or ``None`` without items.

    """
    if whole <= 0:
        return None
    return round(number=part * 100 / whole, ndigits=1)


def _finding(
    *,
    category: str,
    item: Mapping[str, JsonValue],
    rule: str,
    title: str,
    message: str,
) -> dict[str, JsonValue]:
    """Return one normalized finding (without its identifier).

    Args:
        category: Finding category.
        item: Legacy record; its fields are kept.
        rule: Rule within the category.
        title: One-line title.
        message: Full message.

    Returns:
        The legacy record plus the normalized fields.

    """
    line: int = _int(value=item.get("line"))
    column: int = _int(value=item.get("column"))
    return {
        **item,
        "title": title,
        "severity": ReportTables.severities[category],
        "rule": rule,
        "category": category,
        "source": ReportTables.labels[category],
        "path": _text(value=item.get("file")),
        "line": line or None,
        "column": column or None,
        "message": message,
        "blocking": category in ReportTables.blocking,
    }


def _missing_kwargs(item: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Normalize one positional argument that should be a keyword.

    Args:
        item: Legacy positional-call finding.

    Returns:
        The normalized finding.

    """
    callee: str = _text(value=item.get("callee"))
    parameter: str = _text(value=item.get("parameter"))
    return _finding(
        category="missing-kwargs",
        item=item,
        rule="positional-argument",
        title=f"Pass `{parameter}` by keyword to `{callee}`",
        message=(
            f"`{callee}(…)` passes `{_text(value=item.get('argument'))}` "
            f"positionally to the keyword-capable parameter `{parameter}` "
            f"(signature: {_text(value=item.get('confidence'))}). Write "
            f"`{_text(value=item.get('suggestion'))}`."
        ),
    )


def _bare_import(item: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Normalize one forbidden bare import.

    Args:
        item: Legacy bare-import finding.

    Returns:
        The normalized finding.

    """
    module: str = _text(value=item.get("module"))
    safe: bool = item.get("safe") is True
    uses: int = len(_list(value=item.get("replacements")))
    message: str = (
        f"Replace it with `{_text(value=item.get('suggestion'))}` and "
        f"rewrite {uses} {'use' if uses == 1 else 'uses'} of the module."
        if safe
        else (
            "No complete automatic rewrite is proposed because "
            f"{_text(value=item.get('reason'))}."
        )
    )
    return _finding(
        category="bare-import",
        item=item,
        rule="bare-import-fix" if safe else "bare-import-manual",
        title=f"Bare `import {module}`",
        message=message,
    )


def _missing_hint(item: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Normalize one missing type annotation.

    Args:
        item: Legacy missing-type-hint finding.

    Returns:
        The normalized finding.

    """
    kind: str = _text(value=item.get("kind")) or "variable"
    name: str = _text(value=item.get("name"))
    reason: str = _sentence(text=_text(value=item.get("reason")))
    scope: str = f"`{_text(value=item.get('scope'))}`"
    where: str = "" if scope in reason else f" Scope: {scope}."
    return _finding(
        category="missing-hint",
        item=item,
        rule=f"missing-{kind}-hint",
        title=f"Missing {kind} type hint for `{name}`",
        message=(
            f"{reason}.{where} Add `{_text(value=item.get('suggestion'))}`."
        ),
    )


def _parse_failure(path: str) -> dict[str, JsonValue]:
    """Normalize one file that failed to parse.

    Args:
        path: Root-relative file path.

    Returns:
        The normalized finding (no line).

    """
    return _finding(
        category="parse-failure",
        item={"file": path},
        rule="syntax-error",
        title="File failed to parse",
        message=(
            "The file could not be parsed, so its calls, imports and type "
            "hints were not checked."
        ),
    )


def _ambiguous(item: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Normalize one call whose candidate signatures disagree.

    Args:
        item: Legacy ambiguous-call record.

    Returns:
        The normalized finding.

    """
    callee: str = _text(value=item.get("callee"))
    candidates: list[str] = [
        f"`{candidate}`" for candidate in _list(value=item.get("candidates"))
    ]
    return _finding(
        category="ambiguous-call",
        item=item,
        rule="disagreeing-signatures",
        title=f"Ambiguous call `{callee}`",
        message=(
            f"{len(candidates)} candidate definitions disagree on the "
            f"signature: {', '.join(candidates)}. Review the call by hand."
        ),
    )


def _unresolved(
    item: Mapping[str, JsonValue],
    *,
    sites: Mapping[str, int],
) -> dict[str, JsonValue]:
    """Normalize one call site whose callee has no known signature.

    Args:
        item: Unresolved call site (``file``, ``line``, ``column``,
            ``callee``, ``reason``).
        sites: Call sites per callee across the project.

    Returns:
        The normalized finding; ``sites`` is the callee's project count.

    """
    callee: str = _text(value=item.get("callee"))
    reason: str = _text(value=item.get("reason"))
    explanation: str = ReportTables.reasons.get(reason, ("", ""))[1]
    return _finding(
        category="unresolved-callee",
        item={**item, "sites": sites.get(callee, 0)},
        rule=reason or "dynamic-expression",
        title=f"Unresolved callee `{callee}`",
        message=(
            f"{explanation or 'No signature was found'}, so its "
            "positional arguments were not checked."
        ),
    )


def _location_key(item: JsonValue) -> tuple[int, str, int, int, int, str]:
    """Return the report order of one normalized finding.

    Args:
        item: Normalized finding.

    Returns:
        Category position, path, line, column, argument position (of a
        missing keyword) and title.

    """
    finding: dict[str, JsonValue] = _object(value=item)
    category: str = _text(value=finding.get("category"))
    rank: int = (
        ReportTables.categories.index(category)
        if category in ReportTables.categories
        else len(ReportTables.categories)
    )
    return (
        rank,
        _text(value=finding.get("path")),
        _int(value=finding.get("line")),
        _int(value=finding.get("column")),
        _int(value=finding.get("index")),
        _text(value=finding.get("title")),
    )


def normalized_findings(*, report: Mapping[str, JsonValue]) -> list[JsonValue]:
    """Return every finding of the run in the normalized shape.

    Args:
        report: Legacy KWARGS_TYPEHINTS payload.

    Returns:
        Findings of every category ordered by category, path, line and
        column and numbered ``KWARGS-001`` onwards; each keeps its legacy
        fields.

    """
    unresolved: list[dict[str, JsonValue]] = [
        _object(value=item)
        for item in _list(value=report.get("unresolved_sites"))
    ]
    sites: Counter[str] = Counter(
        _text(value=item.get("callee")) for item in unresolved
    )
    collected: list[JsonValue] = [
        *(
            _missing_kwargs(item=_object(value=item))
            for item in _list(value=report.get("findings"))
        ),
        *(
            _bare_import(item=_object(value=item))
            for item in _list(value=report.get("bare_imports"))
        ),
        *(
            _missing_hint(item=_object(value=item))
            for item in _list(value=report.get("type_hints"))
        ),
        *(
            _parse_failure(path=_text(value=path))
            for path in _list(value=report.get("parse_failure_files"))
        ),
        *(
            _ambiguous(item=_object(value=item))
            for item in _list(value=report.get("ambiguous"))
        ),
        *(_unresolved(item=item, sites=sites) for item in unresolved),
    ]
    ordered: list[JsonValue] = sorted(collected, key=_location_key)
    width: int = max(3, len(str(object=len(ordered))))
    return [
        {
            **_object(value=item),
            "id": f"{ReportTables.id_prefix}-{index:0{width}d}",
        }
        for index, item in enumerate(iterable=ordered, start=1)
    ]


def _severity_counts(*, findings: list[JsonValue]) -> dict[str, JsonValue]:
    """Count findings per severity.

    Args:
        findings: Normalized findings.

    Returns:
        Counts of every report severity (zero included).

    """
    counts: Counter[str] = Counter(
        _text(value=_object(value=item).get("severity")) for item in findings
    )
    return {level: counts[level] for level in ReportTables.levels}


def _summary(
    *,
    report: Mapping[str, JsonValue],
    findings: list[JsonValue],
) -> dict[str, JsonValue]:
    """Return the legacy summary with the normalized counters added.

    Args:
        report: Legacy KWARGS_TYPEHINTS payload.
        findings: Normalized findings.

    Returns:
        Legacy counters plus ``targets_eligible`` (Python files found),
        ``targets_analyzed`` (files that parsed), ``findings_total`` and
        ``severity``.

    """
    legacy: dict[str, JsonValue] = _object(value=report.get("summary"))
    files: int = _int(value=legacy.get("python_files"))
    return {
        **legacy,
        "targets_eligible": files,
        "targets_analyzed": files - _int(value=legacy.get("parse_failures")),
        "findings_total": len(findings),
        "auto_fixes": len(_list(value=report.get("auto_fixes"))),
        "severity": _severity_counts(findings=findings),
    }


def _scope(*, report: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Return the normalized ``scope`` block.

    Args:
        report: Legacy KWARGS_TYPEHINTS payload.

    Returns:
        Include and exclude globs, and the files that failed to parse as
        ``skipped``.

    """
    filters: dict[str, JsonValue] = _object(value=report.get("filters"))
    return {
        "include": [
            _text(value=item) for item in _list(value=filters.get("include"))
        ]
        or ["**/*.py"],
        "exclude": [
            _text(value=item) for item in _list(value=filters.get("exclude"))
        ],
        "skipped": [
            {"target": _text(value=path), "reason": "failed to parse"}
            for path in _list(value=report.get("parse_failure_files"))
        ],
    }


def _overview(
    *,
    report: Mapping[str, JsonValue],
    findings: list[JsonValue],
) -> dict[str, JsonValue]:
    """Return the headline counters of the run.

    Args:
        report: Legacy KWARGS_TYPEHINTS payload.
        findings: Normalized findings.

    Returns:
        Files, call sites, signature checks, hint coverage and findings.

    """
    summary: dict[str, JsonValue] = _object(value=report.get("summary"))
    files: int = _int(value=summary.get("python_files"))
    failures: int = _int(value=summary.get("parse_failures"))
    calls: int = _int(value=summary.get("call_sites"))
    resolved: int = _int(value=summary.get("resolved_call_sites"))
    exempt: int = _int(value=summary.get("exempt_call_sites"))
    unresolved: int = _int(value=summary.get("unresolved_call_sites"))
    functions: int = _int(value=summary.get("functions_checked"))
    parameters: int = _int(value=summary.get("parameters_checked"))
    kinds: Counter[str] = Counter(
        _text(value=_object(value=item).get("kind"))
        for item in _list(value=report.get("type_hints"))
    )
    slots: int = functions + parameters
    missing: int = kinds["parameter"] + kinds["return"]
    return {
        "files_scanned": files,
        "files_analyzed": files - failures,
        "parse_failures": failures,
        "call_sites": calls,
        "resolved_call_sites": resolved,
        "resolution_percent": _percent(part=resolved, whole=calls),
        "exempt_call_sites": exempt,
        "unresolved_call_sites": unresolved,
        "skipped_call_sites": max(0, calls - resolved - exempt - unresolved),
        "functions_checked": functions,
        "parameters_checked": parameters,
        "missing_parameter_hints": kinds["parameter"],
        "missing_return_hints": kinds["return"],
        "missing_variable_hints": kinds["variable"] + kinds["attribute"],
        "hint_coverage_percent": _percent(part=slots - missing, whole=slots),
        "findings": len(findings),
        "blocking_findings": sum(
            1 for item in findings if _object(value=item).get("blocking")
        ),
        "auto_fixes": len(_list(value=report.get("auto_fixes"))),
    }


def _categories(*, findings: list[JsonValue]) -> list[JsonValue]:
    """Count findings per category, every category listed.

    Args:
        findings: Normalized findings.

    Returns:
        ``category``/``label``/``severity``/``blocking``/``count`` rows in
        report order.

    """
    counts: Counter[str] = Counter(
        _text(value=_object(value=item).get("category")) for item in findings
    )
    return [
        {
            "category": category,
            "label": ReportTables.labels[category],
            "severity": ReportTables.severities[category],
            "blocking": category in ReportTables.blocking,
            "count": counts[category],
        }
        for category in ReportTables.categories
    ]


def _of(*, findings: list[JsonValue], category: str) -> list[JsonValue]:
    """Return the findings of one category.

    Args:
        findings: Normalized findings.
        category: Wanted category.

    Returns:
        Findings of ``category`` in report order.

    """
    return [
        item
        for item in findings
        if _object(value=item).get("category") == category
    ]


def _unresolved_key(item: JsonValue) -> tuple[int, str, str, int]:
    """Return the order of one unresolved-callee row.

    Args:
        item: Unresolved-callee row.

    Returns:
        Most call sites first, then callee, path and line.

    """
    row: dict[str, JsonValue] = _object(value=item)
    return (
        -_int(value=row.get("count")),
        _text(value=row.get("callee")),
        _text(value=row.get("path")),
        _int(value=row.get("line")),
    )


def _unresolved_rows(*, findings: list[JsonValue]) -> list[JsonValue]:
    """List every unresolved call site with the finding that reports it.

    Args:
        findings: Normalized findings.

    Returns:
        ``callee``/``path``/``line``/``reason``/``count``/``finding`` rows,
        callees with the most call sites first; ``count`` is the callee's
        call sites across the project.

    """
    rows: list[JsonValue] = []
    item: JsonValue
    for item in _of(findings=findings, category="unresolved-callee"):
        finding: dict[str, JsonValue] = _object(value=item)
        reason: str = _text(value=finding.get("rule"))
        rows.append(
            {
                "callee": finding.get("callee"),
                "path": finding.get("path"),
                "line": finding.get("line"),
                "reason": ReportTables.reasons.get(reason, (reason, ""))[0],
                "count": finding.get("sites"),
                "finding": finding.get("id"),
            },
        )
    return sorted(rows, key=_unresolved_key)


def _ambiguous_rows(*, findings: list[JsonValue]) -> list[JsonValue]:
    """List every ambiguous call site with the finding that reports it.

    Args:
        findings: Normalized findings.

    Returns:
        ``callee``/``path``/``line``/``candidates``/``finding`` rows in
        report order.

    """
    return [
        {
            "callee": finding.get("callee"),
            "path": finding.get("path"),
            "line": finding.get("line"),
            "candidates": ", ".join(
                _text(value=candidate)
                for candidate in _list(value=finding.get("candidates"))
            ),
            "finding": finding.get("id"),
        }
        for finding in map(
            _object,
            _of(findings=findings, category="ambiguous-call"),
        )
    ]


def _bare_import_rows(*, findings: list[JsonValue]) -> list[JsonValue]:
    """List every bare import with its proposed fix and finding.

    Args:
        findings: Normalized findings.

    Returns:
        ``module``/``path``/``line``/``fix``/``suggestion``/``finding``
        rows in report order; ``fix`` is ``automatic`` or ``manual``.

    """
    return [
        {
            "module": finding.get("module"),
            "path": finding.get("path"),
            "line": finding.get("line"),
            "fix": "automatic" if finding.get("safe") is True else "manual",
            "suggestion": finding.get("suggestion") or None,
            "finding": finding.get("id"),
        }
        for finding in map(
            _object,
            _of(findings=findings, category="bare-import"),
        )
    ]


def report_data(*, report: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Return the KWARGS_TYPEHINTS payload with the normalized blocks.

    Args:
        report: Legacy payload built by the exactus core.

    Returns:
        Every legacy key, with ``summary`` extended, ``findings`` holding
        every category in the normalized shape (legacy fields kept), and
        new ``scope`` and ``extension`` blocks.

    """
    findings: list[JsonValue] = normalized_findings(report=report)
    return {
        **report,
        "summary": _summary(report=report, findings=findings),
        "scope": _scope(report=report),
        "findings": findings,
        "extension": {
            "metrics": {
                "overview": _overview(report=report, findings=findings),
                "categories": _categories(findings=findings),
            },
            "unresolved_callees": _unresolved_rows(findings=findings),
            "ambiguous_call_sites": _ambiguous_rows(findings=findings),
            "bare_imports": _bare_import_rows(findings=findings),
            "auto_fixes": _list(value=report.get("auto_fixes")),
            "methodology": list(ReportTables.methodology),
        },
    }
