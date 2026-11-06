"""Conflict-first three-way reconciliation through tracked.

Conflict-first three-way reconciliation through tracked syntax identities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from io import StringIO
from pathlib import Path
from re import DOTALL, escape, findall, search, sub
from subprocess import CompletedProcess, TimeoutExpired, run
from tempfile import TemporaryDirectory
from tokenize import COMMENT, TokenError, generate_tokens
from typing import TYPE_CHECKING, cast, final

from exactus.packages.source_merger.cache import SnapshotCache, StatementIndex
from exactus.packages.source_merger.delta import DeltaPolicy, violations
from exactus.packages.source_merger.expression import (
    Texts,
    project_python_expression,
)
from exactus.packages.source_merger.foreign_parser import (
    HtmlParser,
    NodeParser,
)
from exactus.packages.source_merger.html_attributes import (
    Fork,
)
from exactus.packages.source_merger.html_attributes import (
    reconcile as reconcile_html_attributes,
)
from exactus.packages.source_merger.model import (
    AppliedChange,
    Language,
    MergeConflict,
    MergeResult,
    Replacement,
    Snapshot,
    Statement,
    SymbolMatch,
    Unit,
)
from exactus.packages.source_merger.patch import (
    apply,
    indent_at,
    insertion,
    reindent,
)
from exactus.packages.source_merger.python_imports import ImportRegion
from exactus.packages.source_merger.python_imports import (
    collect as collect_imports,
)
from exactus.packages.source_merger.python_imports import hide as hide_imports
from exactus.packages.source_merger.python_imports import (
    reconcile as reconcile_imports,
)
from exactus.packages.source_merger.python_literals import (
    LiteralFork,
    literal_replacements,
)
from exactus.packages.source_merger.python_parser import PythonParser

if TYPE_CHECKING:
    from exactus.packages.source_merger import DeltaMetrics
    from exactus.packages.source_merger.tracking import Tracking


def _parse(*, source: str, language: Language) -> Snapshot:
    """Parse source with the language's strict structural frontend.

    Args:
        source: Source-code snapshot.
        language: Declared language.

    Returns:
        Parsed snapshot or parser failure.

    """
    if language == "python":
        return PythonParser().parse(source=source)
    if language == "html":
        return HtmlParser().parse(source=source)
    return NodeParser().parse(source=source, language=language)


def _git_merge(*, original: str, user: str, tool: str) -> tuple[str, bool]:
    """Reconcile unmatched source regions with Git's diff3 engine.

    Args:
        original: Original unmatched content.
        user: User unmatched content.
        tool: Tool unmatched content.

    Returns:
        Merged string and a no-conflict flag.

    Raises:
        RuntimeError: Git was unavailable or the command could not run.

    """
    with TemporaryDirectory(
        prefix="exactus.packages.source_merger-",
    ) as directory:
        paths: tuple[Path, Path, Path] = (
            Path(directory) / "original",
            Path(directory) / "user",
            Path(directory) / "tool",
        )
        for path, content in zip(paths, (original, user, tool), strict=True):
            path.write_text(data=content, encoding="utf-8")
        try:
            process: CompletedProcess[bytes] = run(
                args=[
                    "git",
                    "merge-file",
                    "--diff3",
                    "-p",
                    "user",
                    "original",
                    "tool",
                ],
                cwd=directory,
                capture_output=True,
                check=False,
                timeout=15,
            )
        except (OSError, TimeoutExpired) as error:
            msg: str = f"Git diff3 unavailable: {error}"
            raise RuntimeError(msg) from error
        if process.returncode not in {0, 1}:
            msg = process.stderr.decode(encoding="utf-8", errors="replace")
            raise RuntimeError(
                msg or "Git diff3 returned an unexpected status",
            )
        return process.stdout.decode(encoding="utf-8"), process.returncode == 0


def _comments(*, source: str, language: Language) -> tuple[str, ...]:
    """Identify meaningful comments without treating whitespace as content.

    Args:
        source: Text within a tracked source declaration.
        language: Language of the declaration.

    Returns:
        Comment tokens in lexical order.

    """
    if language == "python":
        try:
            return tuple(
                token.string
                for token in generate_tokens(
                    readline=StringIO(initial_value=source).readline,
                )
                if token.type == COMMENT
            )
        except (SyntaxError, TokenError, StopIteration):
            return ()
    if language in {"javascript", "typescript", "css"}:
        return tuple(
            findall(
                pattern=r"/\*.*?\*/|(?://[^\n]*)",
                string=source,
                flags=DOTALL,
            ),
        )
    return tuple(findall(pattern=r"<!--.*?-->", string=source, flags=DOTALL))


def _rewrite(
    *,
    snippet: str,
    mapping: dict[str, str],
    language: Language,
) -> str:
    """Translate verified old identifier references into tool-side names.

    Args:
        snippet: User-added or modified statement.
        mapping: Old or user spelling to refactored spelling.
        language: Language for lexical substitution.

    Returns:
        Syntax-preserving renamed snippet; raises on unsupported ambiguity.

    """
    clean: dict[str, str] = {
        key: value for key, value in mapping.items() if key != value
    }
    if not clean:
        return snippet
    if language == "python":
        return PythonParser.rewrite_names(text=snippet, mapping=clean)
    if language == "css":
        result: str = snippet
        for key, value in sorted(
            clean.items(),
            key=lambda item: -len(item[0]),
        ):
            if not key.startswith("--") or not value.startswith("--"):
                continue
            # Only CSS custom-property definitions and var() references are
            # scope-relevant. Never touch arbitrary strings or URL contents.
            result = sub(
                pattern=(r"(var\(\s*)" + escape(pattern=key) + r"(?=[\s,)])"),
                repl=(lambda matched, value=value: matched.group(1) + value),
                string=result,
            )
            result = sub(
                pattern=(r"(^|[;{]\s*)" + escape(pattern=key) + r"(?=\s*:)"),
                repl=(lambda matched, value=value: matched.group(1) + value),
                string=result,
            )
        return result
    if language in {"javascript", "typescript"}:
        return NodeParser().rewrite_identifiers(
            source=snippet,
            language=language,
            mapping=clean,
        )
    return snippet


def _name_map(*, original: Unit, user: Unit, tool: Unit) -> dict[str, str]:
    """Derive conservative parameter and local variable substitutions.

    Args:
        original: Ancestor declaration.
        user: User descendant declaration.
        tool: Tool descendant declaration.

    Returns:
        Verified spelling substitutions for user statement projection.

    """
    mapping: dict[str, str] = {
        own: new
        for own, new in zip(user.param_names, tool.param_names, strict=False)
        if own != new
    }
    for old_statement in original.statements:
        if not old_statement.binding:
            continue
        match: list[Statement] = [
            statement
            for statement in tool.statements
            if statement.shape == old_statement.shape
        ]
        if (
            len(match) == 1
            and match[0].binding
            and match[0].binding != old_statement.binding
        ):
            mapping[old_statement.binding] = match[0].binding
    return mapping


def _assignment_guard(
    *,
    base: Statement,
    own: Statement,
    target: Statement,
    key: str,
) -> MergeConflict | None:
    """Check cheaply rejected assignment reconciliation cases.

    Args:
        base: Ancestor statement.
        own: User statement.
        target: Tool statement.
        key: Ancestor unit key for conflict records.

    Returns:
        Conflict describing the rejection, or None to proceed.

    """
    if base.binding != own.binding:
        return MergeConflict(
            kind="unsupported_transformation",
            scope=key,
            detail=(
                "User-side variable renaming needs full reference migration"
            ),
        )
    if own.annotation not in (base.annotation, target.annotation):
        return MergeConflict(
            kind="concurrent_change",
            scope=key,
            detail=(
                "User changed an assignment type annotation; "
                "annotation migration requires structural reconciliation"
            ),
        )
    if (
        own.value_start is None
        or own.value_end is None
        or target.value_start is None
        or target.value_end is None
    ):
        return MergeConflict(
            kind="unsupported_transformation",
            scope=key,
            detail="Unsupported assignment transformation",
        )
    return None


def _unit_guard(
    *,
    original: Unit,
    own: Unit,
    target: Unit,
) -> MergeConflict | None:
    """Reject units with incompatible rename, relocation or signature edits.

    Args:
        original: Common-ancestor unit.
        own: Matched user unit.
        target: Matched tool unit.

    Returns:
        Conflict describing the rejection, or None to dispatch.

    """
    if own.name not in (original.name, target.name) and (
        original.kind != "element"
    ):
        return MergeConflict(
            kind="unsupported_transformation",
            scope=original.key,
            detail=(
                "User renamed a declaration differently from the tool; "
                "references require scope resolution"
            ),
        )
    if (
        original.parent not in (own.parent, target.parent)
        and target.parent != own.parent
    ):
        return MergeConflict(
            kind="concurrent_change",
            scope=original.key,
            detail="Both forks relocated the declaration to different owners",
        )
    if original.kind in {"function", "async_function", "arrow"} and (
        original.header_semantic != own.header_semantic
        or original.signature != own.signature
    ):
        return MergeConflict(
            kind="unsupported_transformation",
            scope=original.key,
            detail=(
                "User modified a callable signature, annotation or decorator"
            ),
        )
    return None


def _outside_reference_conflicts(
    *,
    language: Language,
    base: Snapshot,
    user: tuple[Snapshot, dict[int, int]],
    tool: tuple[Snapshot, dict[int, int]],
) -> list[MergeConflict]:
    """Reject user edits that refer to declarations independently.

    Reject user edits that refer to declarations independently renamed by a
    tool.

    Args:
        language: Parser grammar for source identifiers.
        base: Parsed common ancestor.
        user: User snapshot and ancestor-to-user declaration matches.
        tool: Tool snapshot and ancestor-to-tool declaration matches.

    Returns:
        Reference migration conflicts where scope-aware edits remain
        necessary.

    """
    user_snapshot, user_pairs = user
    _tool, tool_pairs = tool
    renamed: list[tuple[str, str]] = [
        (base.units[index].name, _tool.units[position].name)
        for index, position in tool_pairs.items()
        if base.units[index].name != _tool.units[position].name
        and base.units[index].kind
        in {"function", "async_function", "arrow", "assignment"}
    ]
    if not renamed:
        return []
    original_mask: dict[int, int] = {
        index: index for index in range(len(base.units))
    }
    user_mask: dict[int, int] = {
        index: ancestor for ancestor, index in user_pairs.items()
    }
    try:
        original_skeleton: str = SourceMerger.mask(
            snapshot=base,
            matched=original_mask,
            language=language,
        )
        user_skeleton: str = SourceMerger.mask(
            snapshot=user_snapshot,
            matched=user_mask,
            language=language,
        )
    except ValueError:
        return [
            MergeConflict(
                kind="structural_change",
                scope="references",
                detail="Nested structural identities overlap",
            ),
        ]
    before: list[str] = original_skeleton.splitlines(keepends=True)
    after: list[str] = user_skeleton.splitlines(keepends=True)
    changed: str = "".join(
        "".join(after[j1:j2])
        for operation, _i1, _i2, j1, j2 in SequenceMatcher(
            isjunk=None,
            a=before,
            b=after,
            autojunk=False,
        ).get_opcodes()
        if operation in {"replace", "insert"}
    )
    return [
        MergeConflict(
            kind="unsupported_transformation",
            scope="external references",
            detail=(
                "User modified an unmatched region referring to renamed "
                f"symbol {old} -> {new}"
            ),
        )
        for old, new in renamed
        if search(
            pattern=r"(?<![\w$-])" + escape(pattern=old) + r"(?![\w$-])",
            string=changed,
        )
    ]


def _prepare_inline_bodies(
    *,
    original: Snapshot,
    user: Snapshot,
    tool: Snapshot,
    language: Language,
    context: tuple[SnapshotCache, DeltaPolicy | None],
) -> Snapshot:
    """Expand inline refactored bodies before statement-level source surgery.

    Args:
        original: Parsed common ancestor.
        user: Parsed user fork.
        tool: Current refactoring source.
        language: Grammar whose inlined blocks may require expansion.
        context: ``(cache, policy)`` shared merge context.
        context: ``(cache, policy)`` shared merge context.

    Returns:
        Refactored snapshot with edit-safe multiline insertion locations.

    """
    cache, policy = context
    if language not in {"javascript", "typescript", "css"}:
        return tool
    min_identity_confidence: float = getattr(
        policy,
        "min_identity_confidence",
        0.0,
    )
    min_identity_margin: float = getattr(policy, "min_identity_margin", 0.0)
    users: dict[int, int] = dict(
        cache.match(
            original=original,
            changed=user,
            branch="user",
            minimum_confidence=min_identity_confidence,
            minimum_margin=min_identity_margin,
        ).pairs,
    )
    tools: dict[int, int] = dict(
        cache.match(
            original=original,
            changed=tool,
            branch="tool",
            minimum_confidence=min_identity_confidence,
            minimum_margin=min_identity_margin,
        ).pairs,
    )
    replacements: list[Replacement] = []
    for index, tool_index in tools.items():
        if index not in users:
            continue
        original_unit: Unit = original.units[index]
        user_unit: Unit = user.units[users[index]]
        target: Unit = tool.units[tool_index]
        if [item.exact for item in original_unit.statements] == [
            item.exact for item in user_unit.statements
        ]:
            continue
        outer: str = indent_at(source=tool.source, position=target.start)
        inner: str = outer + "    "
        body: str = tool.source[target.body_start : target.body_end]
        if target.implicit_return:
            rewritten: str = (
                """\
{
"""
                + inner
                + "return "
                + body.strip()
                + """\
;
"""
                + outer
                + "}"
            )
            replacements.append(
                Replacement(
                    start=target.body_start,
                    end=target.body_end,
                    text=rewritten,
                    scope=target.key,
                ),
            )
        elif (
            """\

"""
            not in body
            and target.statements
        ):
            if "//" in body or "/*" in body:
                continue
            rewritten = (
                """\

"""
                + inner
                + body.strip()
                + """\

"""
                + outer
            )
            replacements.append(
                Replacement(
                    start=target.body_start,
                    end=target.body_end,
                    text=rewritten,
                    scope=target.key,
                ),
            )
    if not replacements:
        return tool
    return cache.parse(
        source=apply(source=tool.source, replacements=tuple(replacements)),
        language=language,
    )


@final
@dataclass(slots=True)
class _BodyCtx:
    """Shared state for statement transfer inside one callable.

    Attributes:
        patches: Accumulated replacements.
        conflicts: Accumulated conflicts.
        applied: Accumulated audit records.
        index: Tool-side statement index.
        tool: Containing refactored callable.
        tool_snapshot: All tool-fork statements.
        mapping: Verified symbol substitutions.
        original_key: Ancestor callable key.

    """

    patches: list[Replacement]
    conflicts: list[MergeConflict]
    applied: list[AppliedChange]
    index: StatementIndex
    tool: Unit
    tool_snapshot: Snapshot
    mapping: dict[str, str]
    original_key: str


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class SourceMerger:
    """Reconcile concurrent user changes against identity-tracked refactoring.

    The tool fork is the structural template. No heuristic selection silently
    resolves overlapping semantic changes. Syntax errors and missing parsers
    are errors, not successful merges. Instances are immutable after creation.

    Attributes:
        original: Common-ancestor source text.
        user_edited: Concurrent user-edited source.
        tool_refactored: Refactored source to merge into.
        language: Source grammar.
        delta_policy: Fork mutation budget policy.
        fork_elapsed_seconds: Editing-time budget in seconds.
        snapshot_cache: Shared snapshot reuse cache.

    """

    original: str
    user_edited: str
    tool_refactored: str
    language: Language
    delta_policy: DeltaPolicy | None = field(default_factory=DeltaPolicy)
    fork_elapsed_seconds: float | None = None
    snapshot_cache: SnapshotCache | None = None

    @staticmethod
    def mask(
        *,
        snapshot: Snapshot,
        matched: dict[int, int],
        language: Language,
    ) -> str:
        """Replace matched units with stable ancestor placeholders.

        Args:
            snapshot: Parsed source version.
            matched: Mapping from current unit index to ancestor index.
            language: Source syntax for placeholder comments.

        Returns:
            Source skeleton preserving all unmatched edits and tool movements.

        """
        replacements: list[Replacement] = []
        for current, base_index in matched.items():
            unit: Unit = snapshot.units[current]
            sentinel: str = f"MERGEKIT_UNIT_{base_index:08d}"
            marker: str = (
                f"# {sentinel}"
                if language == "python"
                else f"<!-- {sentinel} -->"
                if language == "html"
                else f"/* {sentinel} */"
            )
            replacements.append(
                Replacement(
                    start=unit.start,
                    end=unit.end,
                    text=marker,
                    scope=unit.key,
                ),
            )
        return apply(source=snapshot.source, replacements=tuple(replacements))

    def merge(self) -> MergeResult:
        """Perform conservative identity-aware three-way source reconciliation.

        Returns:
            Merged source when unambiguous, else a structured conflict result.

        """
        conflicts: list[MergeConflict] = []
        applied: list[AppliedChange] = []
        matches: list[SymbolMatch] = []
        cache: SnapshotCache = self.snapshot_cache or SnapshotCache()
        preflight: MergeResult | None = self._preflight(
            cache=cache,
            conflicts=conflicts,
            matches=matches,
            applied=applied,
        )
        if preflight is not None:
            return preflight
        snapshots: tuple[Snapshot, Snapshot, Snapshot] | MergeResult = (
            self._snapshots(
                cache=cache,
                conflicts=conflicts,
                matches=matches,
                applied=applied,
            )
        )
        if isinstance(snapshots, MergeResult):
            return snapshots
        base, user, tool = snapshots
        user_pairs, tool_pairs = self._track(
            cache=cache,
            base=base,
            user=user,
            tool=tool,
            ledger=(matches, conflicts),
        )
        patches, local_conflicts, local_applied = self._units(
            base=base,
            user=user,
            tool=tool,
            user_pairs=user_pairs,
            tool_pairs=tool_pairs,
        )
        conflicts.extend(local_conflicts)
        applied.extend(local_applied)
        return self._finish(
            cache=cache,
            forks=(base, user, tool),
            patches=patches,
            user_pairs=user_pairs,
            ledger=(conflicts, matches, applied),
        )

    @staticmethod
    def _expand(*, source: str, units: dict[int, str]) -> str:
        """Restore declarations into the final structure after skeleton merge.

        Args:
            source: Merged source skeleton.
            units: Complete tool-rendered unit source by ancestor index.

        Returns:
            Source with identity tokens expanded into refactored declarations.

        """
        pattern: str = (
            r"(?:#|/\*|<!--)[ \t]*MERGEKIT_UNIT_(\d{8})[ \t]*(?:\*/|-->)?"
        )
        return sub(
            pattern=pattern,
            repl=lambda matched: units.get(
                int(matched.group(1)),
                matched.group(0),
            ),
            string=source,
        )

    @staticmethod
    def _delete_block(
        *,
        old: tuple[Statement, ...],
        spans: tuple[int, int],
        ctx: _BodyCtx,
    ) -> None:
        """Delete ancestor statements at their tool-side locations.

        Args:
            old: Ancestor statements.
            spans: ``(i1, i2)`` diff bounds.
            ctx: Shared transfer state.

        """
        span_i1, span_i2 = spans
        for original_item in old[span_i1:span_i2]:
            target: Statement | None = ctx.index.locate(
                original=original_item,
                preferred=ctx.tool,
            )
            if target is None:
                ctx.conflicts.append(
                    MergeConflict(
                        kind="missing_anchor",
                        scope=ctx.original_key,
                        detail=(
                            "Deletion targets an untracked or "
                            "modified statement"
                        ),
                    ),
                )
                return
            start: int = (
                ctx.tool_snapshot.source.rfind(
                    """\

""",
                    0,
                    target.start,
                )
                + 1
            )
            end: int = ctx.tool_snapshot.source.find(
                """\

""",
                target.end,
            )
            ctx.patches.append(
                Replacement(
                    start=start,
                    end=len(ctx.tool_snapshot.source) if end < 0 else end + 1,
                    text="",
                    scope=ctx.tool.key,
                ),
            )
            ctx.applied.append(
                AppliedChange(
                    scope=ctx.original_key,
                    operation="statement_delete",
                    detail="Deleted statement at its new location",
                ),
            )

    def _merge_skeletons(
        self,
        *,
        cache: SnapshotCache,
        snapshots: tuple[Snapshot, Snapshot, Snapshot],
        user_pairs: dict[int, int],
        ledger: tuple[
            list[MergeConflict],
            list[SymbolMatch],
            list[AppliedChange],
        ],
    ) -> tuple[str, str | None, dict[int, int]] | MergeResult:
        """Mask tracked declarations and merge residual skeletons.

        Args:
            cache: Snapshot cache shared across merge calls.
            snapshots: ``(base, user, patched)`` snapshots.
            user_pairs: Ancestor-to-user declaration matches.
            ledger: ``(conflicts, matches, applied)`` accumulators.

        Returns:
            ``(skeleton, import_text, patched_pairs)`` or a failed result.

        """
        base, user, patched = snapshots
        conflicts, matches, applied = ledger
        policy: DeltaPolicy = self.delta_policy or DeltaPolicy()
        patched_tracking: Tracking = cache.match(
            original=base,
            changed=patched,
            branch="tool",
            minimum_confidence=policy.min_identity_confidence,
            minimum_margin=policy.min_identity_margin,
        )
        patched_pairs: dict[int, int] = dict(patched_tracking.pairs)
        original_mask: dict[int, int] = {
            index: index for index in range(len(base.units))
        }
        user_mask: dict[int, int] = {
            index: ancestor for ancestor, index in user_pairs.items()
        }
        tool_mask: dict[int, int] = {
            index: ancestor for ancestor, index in patched_pairs.items()
        }
        try:
            base_skeleton: str = self.mask(
                snapshot=base,
                matched=original_mask,
                language=self.language,
            )
            user_skeleton: str = self.mask(
                snapshot=user,
                matched=user_mask,
                language=self.language,
            )
            tool_skeleton: str = self.mask(
                snapshot=patched,
                matched=tool_mask,
                language=self.language,
            )
            import_text: str | None = None
            if self.language == "python":
                base_imports: ImportRegion | None = collect_imports(
                    source=base_skeleton,
                )
                user_imports: ImportRegion | None = collect_imports(
                    source=user_skeleton,
                )
                tool_imports: ImportRegion | None = collect_imports(
                    source=tool_skeleton,
                )
                if base_imports and user_imports and tool_imports:
                    import_text, import_conflicts = reconcile_imports(
                        original=base_imports,
                        user=user_imports,
                        tool=tool_imports,
                    )
                    conflicts.extend(import_conflicts)
                    if not import_conflicts and import_text is not None:
                        base_skeleton = hide_imports(
                            source=base_skeleton,
                            region=base_imports,
                        )
                        user_skeleton = hide_imports(
                            source=user_skeleton,
                            region=user_imports,
                        )
                        tool_skeleton = hide_imports(
                            source=tool_skeleton,
                            region=tool_imports,
                        )
            if conflicts:
                return self._result(
                    source=None,
                    conflicts=conflicts,
                    matches=matches,
                    applied=applied,
                )
            skeleton: str
            clean: bool
            skeleton, clean = _git_merge(
                original=base_skeleton,
                user=user_skeleton,
                tool=tool_skeleton,
            )
        except (RuntimeError, ValueError) as error:
            conflicts.append(
                MergeConflict(
                    kind="textual_conflict",
                    scope="skeleton",
                    detail=str(object=error),
                ),
            )
            return self._result(
                source=None,
                conflicts=conflicts,
                matches=matches,
                applied=applied,
            )
        if not clean:
            conflicts.append(
                MergeConflict(
                    kind="textual_conflict",
                    scope="skeleton",
                    detail=(
                        "Concurrent unmatched edits conflict after tracked "
                        "declarations are separated"
                    ),
                ),
            )
            return self._result(
                source=None,
                conflicts=conflicts,
                matches=matches,
                applied=applied,
            )
        return skeleton, import_text, patched_pairs

    def _finish(
        self,
        *,
        cache: SnapshotCache,
        forks: tuple[Snapshot, Snapshot, Snapshot],
        patches: list[Replacement],
        user_pairs: dict[int, int],
        ledger: tuple[
            list[MergeConflict],
            list[SymbolMatch],
            list[AppliedChange],
        ],
    ) -> MergeResult:
        """Apply patches, then merge the residual skeletons textually.

        Args:
            cache: Snapshot cache shared across merge calls.
            forks: ``(base, user, tool)`` snapshots.
            patches: Accumulated tracked-declaration replacements.
            user_pairs: Ancestor-to-user declaration matches.
            ledger: ``(conflicts, matches, applied)`` accumulators.

        Returns:
            Final merge result.

        """
        base, user, tool = forks
        conflicts, matches, applied = ledger
        if conflicts:
            return self._result(
                source=None,
                conflicts=conflicts,
                matches=matches,
                applied=applied,
            )
        try:
            updated_tool: str = apply(
                source=tool.source,
                replacements=tuple(patches),
            )
        except ValueError as error:
            conflicts.append(
                MergeConflict(
                    kind="concurrent_change",
                    scope="patches",
                    detail=str(object=error),
                ),
            )
            return self._result(
                source=None,
                conflicts=conflicts,
                matches=matches,
                applied=applied,
            )
        patched: Snapshot = cache.parse(
            source=updated_tool,
            language=self.language,
        )
        if not patched.valid:
            conflicts.append(
                MergeConflict(
                    kind="validation_error",
                    scope="patched refactor",
                    detail=patched.error,
                ),
            )
            return self._result(
                source=None,
                conflicts=conflicts,
                matches=matches,
                applied=applied,
            )
        skeleton_result: (
            tuple[str, str | None, dict[int, int]] | MergeResult
        ) = self._merge_skeletons(
            cache=cache,
            snapshots=(base, user, patched),
            user_pairs=user_pairs,
            ledger=(conflicts, matches, applied),
        )
        if isinstance(skeleton_result, MergeResult):
            return skeleton_result
        skeleton, import_text, patched_pairs = skeleton_result
        content: dict[int, str] = {
            ancestor: updated_tool[
                patched.units[index].start : patched.units[index].end
            ]
            for ancestor, index in patched_pairs.items()
        }
        for ancestor, index in user_pairs.items():
            if ancestor not in content:
                content[ancestor] = self.user_edited[
                    user.units[index].start : user.units[index].end
                ]
        result: str = self._expand(source=skeleton, units=content)
        if import_text is not None:
            result = result.replace(
                """\
# MERGEKIT_IMPORT_BLOCK
""",
                import_text,
            )
        if "MERGEKIT_IMPORT_BLOCK" in result:
            conflicts.append(
                MergeConflict(
                    kind="structural_change",
                    scope="imports",
                    detail="Import placeholder was not resolved",
                ),
            )
        if "MERGEKIT_UNIT_" in result:
            conflicts.append(
                MergeConflict(
                    kind="structural_change",
                    scope="skeleton",
                    detail=(
                        "Source placeholders could not be resolved uniquely"
                    ),
                ),
            )
        return self._result(
            source=result,
            conflicts=conflicts,
            matches=matches,
            applied=applied,
        )

    def _result(
        self,
        *,
        source: str | None,
        conflicts: list[MergeConflict],
        matches: list[SymbolMatch],
        applied: list[AppliedChange],
    ) -> MergeResult:
        """Validate source before returning a review-safe merge outcome.

        Args:
            source: Candidate final source.
            conflicts: Unresolved differences.
            matches: Identity tracking evidence.
            applied: Accepted user changes.

        Returns:
            Explicit immutable result; unresolved source is never auto-applied.

        """
        valid: bool | None = None
        if source is not None:
            valid = _parse(source=source, language=self.language).valid
            if not valid:
                conflicts.append(
                    MergeConflict(
                        kind="validation_error",
                        scope="file",
                        detail="Merged source fails syntax parsing",
                    ),
                )
        return MergeResult(
            source=source if not conflicts else None,
            conflicts=tuple(conflicts),
            matches=tuple(matches),
            applied_changes=tuple(applied),
            success=not conflicts and source is not None,
            syntax_valid=valid,
        )

    def _snapshots(
        self,
        *,
        cache: SnapshotCache,
        conflicts: list[MergeConflict],
        matches: list[SymbolMatch],
        applied: list[AppliedChange],
    ) -> tuple[Snapshot, Snapshot, Snapshot] | MergeResult:
        """Parse all three forks and normalize tool inline bodies.

        Args:
            cache: Snapshot cache shared across merge calls.
            conflicts: Accumulated conflict records.
            matches: Accumulated symbol matches.
            applied: Accumulated audit changes.

        Returns:
            ``(base, user, tool)`` snapshots, or a failed merge result.

        """
        base, user, tool = cache.parse_forks(
            original=self.original,
            user=self.user_edited,
            tool=self.tool_refactored,
            language=self.language,
        )
        for name, snapshot in (
            ("original", base),
            ("user", user),
            ("tool", tool),
        ):
            if not snapshot.valid:
                conflicts.append(
                    MergeConflict(
                        kind="parse_error",
                        scope=name,
                        detail=snapshot.error,
                    ),
                )
        if conflicts:
            return self._result(
                source=None,
                conflicts=conflicts,
                matches=matches,
                applied=applied,
            )
        try:
            tool: Snapshot = _prepare_inline_bodies(
                original=base,
                user=user,
                tool=tool,
                language=self.language,
                context=(cache, self.delta_policy),
            )
        except ValueError as error:
            conflicts.append(
                MergeConflict(
                    kind="unsupported_transformation",
                    scope="inline bodies",
                    detail=str(object=error),
                ),
            )
            return self._result(
                source=None,
                conflicts=conflicts,
                matches=matches,
                applied=applied,
            )
        if not tool.valid:
            conflicts.append(
                MergeConflict(
                    kind="parse_error",
                    scope="normalized refactor",
                    detail=tool.error,
                ),
            )
            return self._result(
                source=None,
                conflicts=conflicts,
                matches=matches,
                applied=applied,
            )
        return base, user, tool

    def _preflight(
        self,
        *,
        cache: SnapshotCache,
        conflicts: list[MergeConflict],
        matches: list[SymbolMatch],
        applied: list[AppliedChange],
    ) -> MergeResult | None:
        """Run budget checks and trivial equality short-circuits.

        Args:
            cache: Snapshot cache shared across merge calls.
            conflicts: Accumulated conflict records.
            matches: Accumulated symbol matches.
            applied: Accumulated audit changes.

        Returns:
            Early merge result, or None to continue reconciliation.

        """
        if self.delta_policy is not None:
            user_delta: DeltaMetrics = cache.delta(
                original=self.original,
                changed=self.user_edited,
                language=self.language,
            )
            tool_delta: DeltaMetrics = cache.delta(
                original=self.original,
                changed=self.tool_refactored,
                language=self.language,
            )
            conflicts.extend(
                MergeConflict(
                    kind="delta_exceeded",
                    scope="fork mutation budget",
                    detail=detail,
                )
                for detail in violations(
                    user=user_delta,
                    tool=tool_delta,
                    policy=self.delta_policy,
                    elapsed_seconds=self.fork_elapsed_seconds,
                )
            )
            if conflicts:
                return self._result(
                    source=None,
                    conflicts=conflicts,
                    matches=matches,
                    applied=applied,
                )
        if self.original == self.user_edited:
            return self._result(
                source=self.tool_refactored,
                conflicts=conflicts,
                matches=matches,
                applied=applied,
            )
        if self.tool_refactored in (self.original, self.user_edited):
            return self._result(
                source=self.user_edited,
                conflicts=conflicts,
                matches=matches,
                applied=applied,
            )
        return None

    def _track(
        self,
        *,
        cache: SnapshotCache,
        base: Snapshot,
        user: Snapshot,
        tool: Snapshot,
        ledger: tuple[list[SymbolMatch], list[MergeConflict]],
    ) -> tuple[dict[int, int], dict[int, int]]:
        """Match declarations in both forks and record ambiguities.

        Args:
            cache: Snapshot cache shared across merge calls.
            base: Common-ancestor snapshot.
            user: User-edited snapshot.
            tool: Refactored snapshot.
            ledger: ``(matches, conflicts)`` accumulators.

        Returns:
            Ancestor-to-user and ancestor-to-tool declaration matches.

        """
        matches, conflicts = ledger
        policy: DeltaPolicy = self.delta_policy or DeltaPolicy()
        user_tracking: Tracking = cache.match(
            original=base,
            changed=user,
            branch="user",
            minimum_confidence=policy.min_identity_confidence,
            minimum_margin=policy.min_identity_margin,
        )
        tool_tracking: Tracking = cache.match(
            original=base,
            changed=tool,
            branch="tool",
            minimum_confidence=policy.min_identity_confidence,
            minimum_margin=policy.min_identity_margin,
        )
        matches.extend((*user_tracking.matches, *tool_tracking.matches))
        conflicts.extend(
            MergeConflict(
                kind="ambiguous_identity",
                scope=base.units[index].key,
                detail=(
                    "Multiple plausible declarations have similar identities"
                ),
            )
            for index in set(user_tracking.ambiguous)
            | set(tool_tracking.ambiguous)
        )
        user_pairs: dict[int, int] = dict(user_tracking.pairs)
        tool_pairs: dict[int, int] = dict(tool_tracking.pairs)
        conflicts.extend(
            _outside_reference_conflicts(
                language=self.language,
                base=base,
                user=(user, user_pairs),
                tool=(tool, tool_pairs),
            ),
        )
        return user_pairs, tool_pairs

    def _units(
        self,
        *,
        base: Snapshot,
        user: Snapshot,
        tool: Snapshot,
        user_pairs: dict[int, int],
        tool_pairs: dict[int, int],
    ) -> tuple[list[Replacement], list[MergeConflict], list[AppliedChange]]:
        """Reconcile every tracked declaration between the two forks.

        Args:
            base: Common-ancestor snapshot.
            user: User-edited snapshot.
            tool: Refactored snapshot.
            user_pairs: Ancestor-to-user declaration matches.
            tool_pairs: Ancestor-to-tool declaration matches.

        Returns:
            Patches, conflicts, and audit changes for all units.

        """
        patches: list[Replacement] = []
        conflicts: list[MergeConflict] = []
        applied: list[AppliedChange] = []
        name_counts: dict[str, int] = {}
        for unit in base.units:
            name_counts[unit.name] = name_counts.get(unit.name, 0) + 1
        global_renames: dict[str, str] = {
            base.units[ancestor].name: tool.units[index].name
            for ancestor, index in tool_pairs.items()
            if base.units[ancestor].name != tool.units[index].name
            and name_counts[base.units[ancestor].name] == 1
        }
        for index, original_unit in enumerate(iterable=base.units):
            unit_patches, unit_conflicts, unit_applied, handled = (
                self._reconcile_unit(
                    index=index,
                    original=original_unit,
                    user=user,
                    tool=tool,
                    maps=(user_pairs, tool_pairs, global_renames),
                )
            )
            patches.extend(unit_patches)
            conflicts.extend(unit_conflicts)
            applied.extend(unit_applied)
            if not handled:
                continue
            if (
                original_unit.kind != "element"
                and index in user_pairs
                and index in tool_pairs
                and _comments(
                    source=self.original[
                        original_unit.start : original_unit.end
                    ],
                    language=self.language,
                )
                != _comments(
                    source=self.user_edited[
                        user.units[user_pairs[index]].start : user.units[
                            user_pairs[index]
                        ].end
                    ],
                    language=self.language,
                )
            ):
                conflicts.append(
                    MergeConflict(
                        kind="unsupported_transformation",
                        scope=original_unit.key,
                        detail=(
                            "Concurrent user comment changes require "
                            "CST-aware attachment tracking"
                        ),
                    ),
                )
        return patches, conflicts, applied

    def _reconcile_unit(
        self,
        *,
        index: int,
        original: Unit,
        user: Snapshot,
        tool: Snapshot,
        maps: tuple[dict[int, int], dict[int, int], dict[str, str]],
    ) -> tuple[
        list[Replacement],
        list[MergeConflict],
        list[AppliedChange],
        bool,
    ]:
        """Reconcile one tracked declaration across both forks.

        Args:
            index: Ancestor unit index.
            original: Common-ancestor unit.
            user: User-edited snapshot.
            tool: Refactored snapshot.
            maps: User/tool match maps and global renames.

        Returns:
            Patches, conflicts, audit changes, and whether the unit was
            matched in both forks.

        """
        user_pairs, tool_pairs, global_renames = maps
        if index not in user_pairs or index not in tool_pairs:
            return (
                *self._removed_unit(
                    index=index,
                    original=original,
                    user=user,
                    user_pairs=user_pairs,
                ),
                False,
            )
        own: Unit = user.units[user_pairs[index]]
        target: Unit = tool.units[tool_pairs[index]]
        if (
            self.original[original.start : original.end]
            == self.user_edited[own.start : own.end]
        ):
            return [], [], [], False
        guard: MergeConflict | None = _unit_guard(
            original=original,
            own=own,
            target=target,
        )
        if guard is not None:
            return [], [guard], [], False
        return (
            *self._dispatch_unit(
                original=original,
                own=own,
                target=target,
                tool=tool,
                global_renames=global_renames,
            ),
            True,
        )

    def _removed_unit(
        self,
        *,
        index: int,
        original: Unit,
        user: Snapshot,
        user_pairs: dict[int, int],
    ) -> tuple[list[Replacement], list[MergeConflict], list[AppliedChange]]:
        """Report a user edit to a declaration the tool removed.

        Args:
            index: Ancestor unit index.
            original: Common-ancestor unit.
            user: User-edited snapshot.
            user_pairs: Ancestor-to-user declaration matches.

        Returns:
            Conflict when the user edited a removed declaration.

        """
        if index in user_pairs:
            own: Unit = user.units[user_pairs[index]]
            if (
                self.user_edited[own.start : own.end]
                != self.original[original.start : original.end]
            ):
                return (
                    [],
                    [
                        MergeConflict(
                            kind="structural_change",
                            scope=original.key,
                            detail=(
                                "Refactor removed an independently edited "
                                "declaration"
                            ),
                        ),
                    ],
                    [],
                )
        return [], [], []

    def _dispatch_unit(
        self,
        *,
        original: Unit,
        own: Unit,
        target: Unit,
        tool: Snapshot,
        global_renames: dict[str, str],
    ) -> tuple[list[Replacement], list[MergeConflict], list[AppliedChange]]:
        """Route one matched unit to its kind-specific reconciler.

        Args:
            original: Common-ancestor unit.
            own: Matched user unit.
            target: Matched tool unit.
            tool: Refactored snapshot.
            global_renames: Verified global symbol substitutions.

        Returns:
            Patches, conflicts, and audit changes.

        """
        if original.kind == "assignment":
            return self._assignment(
                original=original,
                user=own,
                tool=target,
                mapping={},
            )
        if original.kind in {"function", "async_function", "arrow", "rule"}:
            mapping: dict[str, str] = _name_map(
                original=original,
                user=own,
                tool=target,
            )
            mapping.update(global_renames)
            return self._body(
                original=original,
                user=own,
                tool=target,
                tool_snapshot=tool,
                mapping=mapping,
            )
        if original.kind == "element":
            return self._element(
                original=original,
                own=own,
                target=target,
                tool=tool,
            )
        return [], [], []

    def _element(
        self,
        *,
        original: Unit,
        own: Unit,
        target: Unit,
        tool: Snapshot,
    ) -> tuple[list[Replacement], list[MergeConflict], list[AppliedChange]]:
        """Reconcile a moved HTML element via subtree merge and attributes.

        Args:
            original: Common-ancestor element.
            own: Matched user element.
            target: Matched tool element.
            tool: Refactored snapshot.

        Returns:
            Body patches, attribute patches, conflicts, and audit changes.

        """
        patches: list[Replacement] = []
        conflicts: list[MergeConflict] = []
        applied: list[AppliedChange] = []
        original_content: str = self.original[
            original.body_start : original.body_end
        ]
        user_content: str = self.user_edited[own.body_start : own.body_end]
        tool_content: str = tool.source[target.body_start : target.body_end]
        try:
            merged_content, okay = _git_merge(
                original=original_content,
                user=user_content,
                tool=tool_content,
            )
        except RuntimeError as error:
            return (
                [],
                [
                    MergeConflict(
                        kind="textual_conflict",
                        scope=original.key,
                        detail=str(object=error),
                    ),
                ],
                [],
            )
        if not okay:
            return (
                [],
                [
                    MergeConflict(
                        kind="textual_conflict",
                        scope=original.key,
                        detail="Overlapping changes inside moved HTML element",
                    ),
                ],
                [],
            )
        if user_content != original_content:
            patches.append(
                Replacement(
                    start=target.body_start,
                    end=target.body_end,
                    text=merged_content,
                    scope=target.key,
                ),
            )
            applied.append(
                AppliedChange(
                    scope=original.key,
                    operation="html_subtree",
                    detail=(
                        "Transferred child edits into refactored HTML element"
                    ),
                ),
            )
        attributes, attr_conflicts, attr_applied = reconcile_html_attributes(
            original=Fork(source=self.original, unit=original),
            user=Fork(source=self.user_edited, unit=own),
            tool=Fork(source=tool.source, unit=target),
        )
        patches.extend(attributes)
        conflicts.extend(attr_conflicts)
        applied.extend(attr_applied)
        return patches, conflicts, applied

    def _project_assignment_rhs(
        self,
        *,
        base: Statement,
        own: Statement,
        target: Statement,
        keys: tuple[str, str],
        mapping: dict[str, str],
    ) -> tuple[list[Replacement], list[MergeConflict], list[AppliedChange]]:
        """Project a user RHS edit through the expression projector.

        Args:
            base: Ancestor statement.
            own: User statement.
            target: Tool statement.
            keys: Ancestor unit key and patch scope label.
            mapping: Verified symbol substitutions.

        Returns:
            Expression patches, conflicts, and audit changes.

        """
        key, scope = keys
        try:
            independent: tuple[Replacement, ...] | None = (
                project_python_expression(
                    texts=Texts(
                        original=self.original[
                            base.value_start : base.value_end
                        ],
                        user=self.user_edited[own.value_start : own.value_end],
                        tool=self.tool_refactored[
                            target.value_start : target.value_end
                        ],
                    ),
                    tool_start=cast(typ="int", val=target.value_start),
                    mapping=mapping,
                    scope=scope,
                )
            )
        except ValueError as error:
            return (
                [],
                [
                    MergeConflict(
                        kind="unsupported_transformation",
                        scope=key,
                        detail=str(object=error),
                    ),
                ],
                [],
            )
        if independent is None:
            return (
                [],
                [
                    MergeConflict(
                        kind="concurrent_change",
                        scope=key,
                        detail=(
                            "User and tool modified overlapping assignment "
                            "expression paths"
                        ),
                    ),
                ],
                [],
            )
        return (
            list(independent),
            [],
            [
                AppliedChange(
                    scope=key,
                    operation="assignment_expression",
                    detail=(
                        "Preserved independently refactored RHS and type "
                        "annotations"
                    ),
                ),
            ],
        )

    def _transfer_expression(
        self,
        *,
        original_item: Statement,
        user_item: Statement,
        target: Statement,
        ctx: _BodyCtx,
    ) -> None:
        """Project an expression-level user edit into the tool span.

        Args:
            original_item: Ancestor statement.
            user_item: User-edited statement.
            target: Matched tool statement.
            ctx: Shared transfer state.

        """
        try:
            original_span: str = self.original[
                original_item.value_start : original_item.value_end
            ]
            independent: tuple[Replacement, ...] | None = (
                project_python_expression(
                    texts=Texts(
                        original=original_span,
                        user=self.user_edited[
                            user_item.value_start : user_item.value_end
                        ],
                        tool=ctx.tool_snapshot.source[
                            target.value_start : target.value_end
                        ],
                    ),
                    tool_start=cast(typ="int", val=target.value_start),
                    mapping=ctx.mapping,
                    scope=ctx.tool.key,
                )
            )
        except ValueError as error:
            ctx.conflicts.append(
                MergeConflict(
                    kind="unsupported_transformation",
                    scope=ctx.original_key,
                    detail=str(object=error),
                ),
            )
            return
        if independent is None:
            ctx.conflicts.append(
                MergeConflict(
                    kind="concurrent_change",
                    scope=ctx.original_key,
                    detail=(
                        "User and tool modified overlapping "
                        "expression-tree paths"
                    ),
                ),
            )
            return
        if independent:
            ctx.patches.extend(independent)
            ctx.applied.append(
                AppliedChange(
                    scope=ctx.original_key,
                    operation="expression_edit",
                    detail="Projected changed expression subtrees",
                ),
            )
        return

    def _transfer(
        self,
        *,
        original_item: Statement,
        user_item: Statement,
        ctx: _BodyCtx,
    ) -> None:
        """Transfer a changed statement to its tool-side descendant.

        Args:
            original_item: Ancestor statement.
            user_item: User-edited statement.
            ctx: Shared transfer state.

        """
        if original_item.annotation != user_item.annotation:
            ctx.conflicts.append(
                MergeConflict(
                    kind="concurrent_change",
                    scope=ctx.original_key,
                    detail="User changed a local declaration annotation",
                ),
            )
            return
        if (
            original_item.exact == user_item.exact
            and original_item.shape == user_item.shape
        ):
            return
        target: Statement | None = ctx.index.locate(
            original=original_item,
            preferred=ctx.tool,
        )
        if target is None and self.language == "python":
            target = ctx.index.locate_mutated(
                original=original_item,
                preferred=ctx.tool,
            )
        if target is None:
            ctx.conflicts.append(
                MergeConflict(
                    kind="missing_anchor",
                    scope=ctx.original_key,
                    detail=(
                        "A changed statement moved or changed without "
                        "unique correspondence"
                    ),
                ),
            )
            return
        if (
            self.language == "python"
            and original_item.value_start is not None
            and original_item.value_end is not None
            and user_item.value_start is not None
            and user_item.value_end is not None
            and target.value_start is not None
            and target.value_end is not None
        ):
            self._transfer_expression(
                original_item=original_item,
                user_item=user_item,
                target=target,
                ctx=ctx,
            )
            return
        self._transfer_fallback(
            original_item=original_item,
            user_item=user_item,
            target=target,
            ctx=ctx,
        )

    def _transfer_fallback(
        self,
        *,
        original_item: Statement,
        user_item: Statement,
        target: Statement,
        ctx: _BodyCtx,
    ) -> None:
        """Rewrite a changed statement into its unique tool-side anchor.

        Args:
            original_item: Ancestor statement.
            user_item: User-edited statement.
            target: Matched tool statement.
            ctx: Shared transfer state.

        """
        user_fragment: str = self.user_edited[user_item.start : user_item.end]
        try:
            fragment: str = _rewrite(
                snippet=user_fragment,
                mapping=ctx.mapping,
                language=self.language,
            )
        except ValueError as error:
            ctx.conflicts.append(
                MergeConflict(
                    kind="unsupported_transformation",
                    scope=ctx.original_key,
                    detail=str(object=error),
                ),
            )
            return
        if original_item.shape != target.shape:
            if user_item.shape == target.shape:
                return
            ctx.conflicts.append(
                MergeConflict(
                    kind="concurrent_change",
                    scope=ctx.original_key,
                    detail="Both forks changed the same statement's semantics",
                ),
            )
            return
        if self.language == "python":
            literals: tuple[Replacement, ...] | None = literal_replacements(
                original=LiteralFork(
                    source=self.original,
                    record=original_item,
                ),
                user=LiteralFork(
                    source=self.user_edited,
                    record=user_item,
                ),
                tool=LiteralFork(
                    source=ctx.tool_snapshot.source,
                    record=target,
                ),
            )
            if literals is not None:
                ctx.patches.extend(literals)
                ctx.applied.append(
                    AppliedChange(
                        scope=ctx.original_key,
                        operation="literal_edit",
                        detail=(
                            "Preserved tool wrapping while replacing "
                            "changed literal leaves"
                        ),
                    ),
                )
                return
        if (
            self.language == "python"
            and original_item.kind in {"Assign", "AnnAssign"}
            and user_item.kind in {"Assign", "AnnAssign"}
            and target.kind in {"Assign", "AnnAssign"}
            and original_item.binding == user_item.binding
            and user_item.value_start is not None
            and user_item.value_end is not None
            and target.value_start is not None
            and target.value_end is not None
        ):
            value: str = self.user_edited[
                user_item.value_start : user_item.value_end
            ]
            ctx.patches.append(
                Replacement(
                    start=target.value_start,
                    end=target.value_end,
                    text=_rewrite(
                        snippet=value,
                        mapping=ctx.mapping,
                        language=self.language,
                    ),
                    scope=ctx.tool.key,
                ),
            )
        elif (
            self.language == "css"
            and user_item.value_start is not None
            and target.value_start is not None
        ):
            raw: str = self.user_edited[
                user_item.value_start : user_item.value_end
            ]
            fragment = _rewrite(
                snippet=raw,
                mapping=ctx.mapping,
                language=self.language,
            )
            ctx.patches.append(
                Replacement(
                    start=target.value_start,
                    end=target.value_end or target.value_start,
                    text=fragment,
                    scope=ctx.tool.key,
                ),
            )
        else:
            ctx.patches.append(
                Replacement(
                    start=target.start,
                    end=target.end,
                    text=reindent(
                        text=fragment,
                        target=indent_at(
                            source=ctx.tool_snapshot.source,
                            position=target.start,
                        ),
                        origin=indent_at(
                            source=self.user_edited,
                            position=user_item.start,
                        ),
                    ),
                    scope=ctx.tool.key,
                ),
            )
        ctx.applied.append(
            AppliedChange(
                scope=ctx.original_key,
                operation="statement_edit",
                detail="Projected into unique refactored statement",
            ),
        )

    def _assignment(
        self,
        *,
        original: Unit,
        user: Unit,
        tool: Unit,
        mapping: dict[str, str],
    ) -> tuple[list[Replacement], list[MergeConflict], list[AppliedChange]]:
        """Project RHS edits while retaining generated annotations and owners.

        Args:
            original: Base assignment.
            user: User assignment.
            tool: Refactored assignment, possibly moved into a @final class.
            mapping: Verified symbol substitutions.

        Returns:
            Proposed patches, conflicts, and audit changes.

        """
        base: Statement = original.statements[0]
        own: Statement = user.statements[0]
        target: Statement = tool.statements[0]
        guard: MergeConflict | None = _assignment_guard(
            base=base,
            own=own,
            target=target,
            key=original.key,
        )
        if guard is not None:
            return [], [guard], []
        if own.shape == base.shape and own.exact == base.exact:
            return [], [], []
        if (
            self.language == "python"
            and base.value_start is not None
            and base.value_end is not None
        ):
            return self._project_assignment_rhs(
                base=base,
                own=own,
                target=target,
                keys=(original.key, tool.key),
                mapping=mapping,
            )
        if target.shape not in (base.shape, own.shape):
            return (
                [],
                [
                    MergeConflict(
                        kind="concurrent_change",
                        scope=original.key,
                        detail="Both forks changed the assignment value",
                    ),
                ],
                [],
            )
        if target.shape == own.shape and target.exact == own.exact:
            return [], [], []
        return self._rewrite_assignment(
            own=own,
            target=target,
            keys=(original.key, tool.key),
            mapping=mapping,
        )

    def _rewrite_assignment(
        self,
        *,
        own: Statement,
        target: Statement,
        keys: tuple[str, str],
        mapping: dict[str, str],
    ) -> tuple[list[Replacement], list[MergeConflict], list[AppliedChange]]:
        """Rewrite the user RHS through verified symbol substitutions.

        Args:
            own: User statement.
            target: Tool statement.
            keys: Ancestor unit key and patch scope label.
            mapping: Verified symbol substitutions.

        Returns:
            Replacement patch, conflict, or audit record.

        """
        original_key, tool_key = keys
        user_source: str = self.user_edited[own.value_start : own.value_end]
        value: str = user_source
        try:
            value = _rewrite(
                snippet=user_source,
                mapping=mapping,
                language=self.language,
            )
        except ValueError as error:
            return (
                [],
                [
                    MergeConflict(
                        kind="unsupported_transformation",
                        scope=original_key,
                        detail=str(object=error),
                    ),
                ],
                [],
            )
        return (
            [
                Replacement(
                    start=cast(typ="int", val=target.value_start),
                    end=cast(typ="int", val=target.value_end),
                    text=value,
                    scope=tool_key,
                ),
            ],
            [],
            [
                AppliedChange(
                    scope=original_key,
                    operation="assignment_value",
                    detail=(
                        "Preserved generated type annotation and declaration "
                        "relocation"
                    ),
                ),
            ],
        )

    def _dispatch_opcodes(
        self,
        *,
        matcher: SequenceMatcher[str],
        old: tuple[Statement, ...],
        own: tuple[Statement, ...],
        ctx: _BodyCtx,
    ) -> None:
        """Dispatch diff opcodes to transfer or block rewrites.

        Args:
            matcher: Aligned statement diff.
            old: Ancestor statements.
            own: User statements.
            ctx: Shared transfer state.

        """
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
                for base_item, user_item in zip(
                    old[i1:i2],
                    own[j1:j2],
                    strict=True,
                ):
                    self._transfer(
                        original_item=base_item,
                        user_item=user_item,
                        ctx=ctx,
                    )
            elif tag == "replace" and i2 - i1 == 1:
                self._replace_block(
                    old=old,
                    own=own,
                    spans=(i1, i2, j1, j2),
                    ctx=ctx,
                )
            elif tag == "delete":
                self._delete_block(
                    old=old,
                    spans=(i1, i2),
                    ctx=ctx,
                )
            elif tag == "insert":
                following: Statement | None = (
                    old[i1] if i1 < len(old) else None
                )
                preceding: Statement | None = old[i1 - 1] if i1 else None
                anchor: Statement | None = (
                    ctx.index.locate(original=following, preferred=ctx.tool)
                    if following is not None
                    else None
                )
                before: bool = anchor is not None
                if anchor is None and preceding is not None:
                    anchor = ctx.index.locate(
                        original=preceding,
                        preferred=ctx.tool,
                    )
                if anchor is None:
                    ctx.conflicts.append(
                        MergeConflict(
                            kind="missing_anchor",
                            scope=ctx.original_key,
                            detail=(
                                "New statement has no uniquely tracked "
                                "insertion context"
                            ),
                        ),
                    )
                    continue
                first: Statement = own[j1]
                last: Statement = own[j2 - 1]
                try:
                    fragment: str = _rewrite(
                        snippet=self.user_edited[first.start : last.end],
                        mapping=ctx.mapping,
                        language=self.language,
                    )
                except ValueError as error:
                    ctx.conflicts.append(
                        MergeConflict(
                            kind="unsupported_transformation",
                            scope=ctx.original_key,
                            detail=str(object=error),
                        ),
                    )
                    continue
                ctx.patches.append(
                    insertion(
                        source=ctx.tool_snapshot.source,
                        anchor=anchor,
                        before=before,
                        snippet=fragment,
                        origin=indent_at(
                            source=self.user_edited,
                            position=first.start,
                        ),
                    ),
                )
                ctx.applied.append(
                    AppliedChange(
                        scope=ctx.original_key,
                        operation="statement_insert",
                        detail=(
                            "Inserted adjacent to tracked refactoring survivor"
                        ),
                    ),
                )
            else:
                ctx.conflicts.append(
                    MergeConflict(
                        kind="unsupported_transformation",
                        scope=ctx.original_key,
                        detail=(
                            "Complex simultaneous block surgery requires "
                            "manual reconciliation"
                        ),
                    ),
                )

    def _replace_block(
        self,
        *,
        old: tuple[Statement, ...],
        own: tuple[Statement, ...],
        spans: tuple[int, int, int, int],
        ctx: _BodyCtx,
    ) -> None:
        """Replace a single statement block with rewritten user text.

        Args:
            old: Ancestor statements.
            own: User statements.
            spans: ``(i1, i2, j1, j2)`` diff bounds.
            ctx: Shared transfer state.

        """
        i1, _, j1, j2 = spans
        target: Statement | None = ctx.index.locate(
            original=old[i1],
            preferred=ctx.tool,
        )
        if target is None:
            ctx.conflicts.append(
                MergeConflict(
                    kind="missing_anchor",
                    scope=ctx.original_key,
                    detail="Cannot locate replaced statement block",
                ),
            )
            return
        first: Statement = own[j1]
        last: Statement = own[j2 - 1]
        raw: str = self.user_edited[first.start : last.end]
        try:
            rewritten: str = _rewrite(
                snippet=raw,
                mapping=ctx.mapping,
                language=self.language,
            )
        except ValueError as error:
            ctx.conflicts.append(
                MergeConflict(
                    kind="unsupported_transformation",
                    scope=ctx.original_key,
                    detail=str(object=error),
                ),
            )
            return
        ctx.patches.append(
            Replacement(
                start=target.start,
                end=target.end,
                text=reindent(
                    text=rewritten,
                    target=indent_at(
                        source=ctx.tool_snapshot.source,
                        position=target.start,
                    ),
                    origin=indent_at(
                        source=self.user_edited,
                        position=first.start,
                    ),
                ),
                scope=ctx.tool.key,
            ),
        )
        ctx.applied.append(
            AppliedChange(
                scope=ctx.original_key,
                operation="statement_block",
                detail="Transferred complete replacement block",
            ),
        )

    def _body(
        self,
        *,
        original: Unit,
        user: Unit,
        tool: Unit,
        tool_snapshot: Snapshot,
        mapping: dict[str, str],
    ) -> tuple[list[Replacement], list[MergeConflict], list[AppliedChange]]:
        """Reconcile statement-level edits across reorganization and renaming.

        Args:
            original: Common-ancestor callable.
            user: Current user callable.
            tool: Callable in the refactored fork.
            tool_snapshot: All source statements, including extracted helpers.
            mapping: Verified user-to-tool symbol spellings.

        Returns:
            Proposed nonoverlapping edits, conflicts, and provenance records.

        """
        old: tuple[Statement, ...] = original.statements
        own: tuple[Statement, ...] = user.statements
        patches: list[Replacement] = []
        conflicts: list[MergeConflict] = []
        applied: list[AppliedChange] = []
        index: StatementIndex = StatementIndex(snapshot=tool_snapshot)
        matcher: SequenceMatcher[str] = SequenceMatcher(
            isjunk=None,
            a=[item.exact for item in old],
            b=[item.exact for item in own],
            autojunk=False,
        )
        ctx: _BodyCtx = _BodyCtx(
            patches=patches,
            conflicts=conflicts,
            applied=applied,
            index=index,
            tool=tool,
            tool_snapshot=tool_snapshot,
            mapping=mapping,
            original_key=original.key,
        )
        self._dispatch_opcodes(
            matcher=matcher,
            old=old,
            own=own,
            ctx=ctx,
        )
        return patches, conflicts, applied


TrackedSourceMerger = SourceMerger
