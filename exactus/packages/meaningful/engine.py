# Copyright (c) 2026 João Lopes.
"""Policy evaluation and source evidence for meaningful findings."""

from ast import (
    AST,
    AsyncFor,
    Call,
    For,
    If,
    Raise,
    Try,
    TryStar,
    While,
    parse,
    walk,
)
from pathlib import Path
from re import findall, finditer, sub

from exactus.packages.meaningful.analyzer import (
    Category,
    Classification,
    Metrics,
    PythonTestNeedClassifier,
    UnitTestLevel,
)
from exactus.packages.meaningful.models import (
    DecisionNode,
    EvaluationPolicy,
    FindingEvidence,
    PromotionScores,
    PromotionThresholds,
    SourceLine,
)


class PolicyEvaluator:
    """Convert objective metrics into normalized promotion decisions.

    Attributes:
        COMPLEXITY_FLOOR: Complexity threshold for the high-risk floor.
        NESTING_FLOOR: Nesting threshold for the high-risk floor.

    """

    COMPLEXITY_FLOOR: int = 6
    NESTING_FLOOR: int = 3

    def __init__(self, *, policy: EvaluationPolicy) -> None:
        """Store the immutable evaluation policy.

        Args:
            policy: Value supplied for ``policy``.

        """
        self._policy: EvaluationPolicy = policy

    @staticmethod
    def category(*, level: UnitTestLevel) -> Category:
        """Map test level to semantic category.

        Args:
            level: Value supplied for ``level``.

        Returns:
            The resulting value.

        """
        return {
            UnitTestLevel.TEST_0: Category.STRUCTURAL,
            UnitTestLevel.TEST_1: Category.TRIVIAL,
            UnitTestLevel.TEST_2: Category.BEHAVIORAL,
            UnitTestLevel.TEST_3: Category.COMPLEX,
        }[level]

    def scores(
        self,
        *,
        metrics: Metrics,
        source_lines: int,
    ) -> PromotionScores:
        """Calculate independent normalized promotion evidence scores.

        Args:
            metrics: Value supplied for ``metrics``.
            source_lines: Value supplied for ``source_lines``.

        Returns:
            The resulting value.

        """
        decisions: int = (
            metrics.branches
            + metrics.loops
            + metrics.boolean_decisions
            + metrics.comprehension_decisions
        )
        errors: int = metrics.exception_handlers + metrics.raises
        behavior: float = self._ratio(
            value=metrics.behavioral_statements,
            cap=self._policy.caps.behavioral_statements,
        )
        public: float = self._ratio(
            value=metrics.public_behavioral_members,
            cap=self._policy.caps.public_members,
        )
        effects: float = self._ratio(
            value=metrics.side_effects,
            cap=self._policy.caps.side_effects,
        )
        mutations: float = self._ratio(
            value=metrics.mutations,
            cap=self._policy.caps.mutations,
        )
        decision_score: float = self._ratio(
            value=decisions,
            cap=self._policy.caps.decisions,
        )
        error_score: float = self._ratio(
            value=errors,
            cap=self._policy.caps.errors,
        )
        computations: float = self._ratio(
            value=metrics.computations,
            cap=self._policy.caps.computations,
        )
        size: float = self._ratio(
            value=source_lines,
            cap=self._policy.caps.source_lines,
        )
        nesting: float = self._ratio(
            value=metrics.max_control_nesting,
            cap=self._policy.caps.nesting,
        )
        score_0_to_1: float = self._weighted(
            values=(
                (behavior, 1.0),
                (public, 0.8),
                (computations, 0.7),
                (size, 0.4),
                (effects, 1.0),
                (mutations, 1.0),
            ),
        )
        score_1_to_2: float = self._weighted(
            values=(
                (behavior, self._policy.weights.behavior),
                (public, self._policy.weights.public_surface),
                (effects, self._policy.weights.side_effects),
                (mutations, self._policy.weights.mutations),
                (decision_score, self._policy.weights.decisions),
                (error_score, self._policy.weights.errors),
                (computations, self._policy.weights.computations),
            ),
        )
        score_1_to_2 = max(
            score_1_to_2,
            self._policy.floors.side_effect_test_1_to_2
            if metrics.side_effects
            else 0.0,
            self._policy.floors.mutation_test_1_to_2
            if metrics.mutations
            else 0.0,
            self._policy.floors.error_test_1_to_2 if errors else 0.0,
            self._policy.floors.import_runtime_test_1_to_2
            if metrics.module_runtime_statements
            else 0.0,
        )
        score_2_to_3: float = self._weighted(
            values=(
                (behavior, self._policy.weights.behavior),
                (public, self._policy.weights.public_surface),
                (decision_score, self._policy.weights.decisions),
                (error_score, self._policy.weights.errors),
                (computations, self._policy.weights.computations),
                (size, self._policy.weights.size),
                (nesting, self._policy.weights.nesting),
                (effects, self._policy.weights.side_effects),
            ),
        )
        if (
            metrics.cyclomatic_complexity >= self.COMPLEXITY_FLOOR
            or metrics.max_control_nesting >= self.NESTING_FLOOR
        ):
            score_2_to_3 = max(
                score_2_to_3,
                self._policy.floors.high_complexity_test_2_to_3,
            )
        return PromotionScores(
            test_0_to_1=round(number=score_0_to_1, ndigits=6),
            test_1_to_2=round(number=score_1_to_2, ndigits=6),
            test_2_to_3=round(number=score_2_to_3, ndigits=6),
        )

    def level(self, *, scores: PromotionScores) -> UnitTestLevel:
        """Apply thresholds while preserving zero-evidence TEST-0.

        Args:
            scores: Value supplied for ``scores``.

        Returns:
            The resulting value.

        """
        thresholds: PromotionThresholds = self._policy.thresholds
        if not self._promotes(
            score=scores.test_0_to_1,
            threshold=thresholds.test_0_to_1,
        ):
            return UnitTestLevel.TEST_0
        if not self._promotes(
            score=scores.test_1_to_2,
            threshold=thresholds.test_1_to_2,
        ):
            return UnitTestLevel.TEST_1
        if not self._promotes(
            score=scores.test_2_to_3,
            threshold=thresholds.test_2_to_3,
        ):
            return UnitTestLevel.TEST_2
        return UnitTestLevel.TEST_3

    def decisions(
        self,
        *,
        scores: PromotionScores,
        evidence: tuple[FindingEvidence, ...],
    ) -> tuple[DecisionNode, ...]:
        """Return the exact adjacent-promotion decisions used by the policy.

        Args:
            scores: Promotion evidence scores.
            evidence: Source evidence collected for the resulting level.

        Returns:
            Ordered audit trail from TEST-0 to the final level.

        """
        thresholds: PromotionThresholds = self._policy.thresholds
        evidence_ids: tuple[str, ...] = tuple(item.id for item in evidence)
        boundaries: tuple[
            tuple[str, str, float, float, UnitTestLevel, UnitTestLevel],
            ...,
        ] = (
            (
                "promote-test-0-to-1",
                "Does the file contain substantive behavior?",
                scores.test_0_to_1,
                thresholds.test_0_to_1,
                UnitTestLevel.TEST_0,
                UnitTestLevel.TEST_1,
            ),
            (
                "promote-test-1-to-2",
                (
                    "Is the behavior meaningful enough that tests "
                    "should visit it?"
                ),
                scores.test_1_to_2,
                thresholds.test_1_to_2,
                UnitTestLevel.TEST_1,
                UnitTestLevel.TEST_2,
            ),
            (
                "promote-test-2-to-3",
                "Is there strong evidence of significant or complex behavior?",
                scores.test_2_to_3,
                thresholds.test_2_to_3,
                UnitTestLevel.TEST_2,
                UnitTestLevel.TEST_3,
            ),
        )
        decisions: list[DecisionNode] = []
        for rule, question, score, threshold, before, after in boundaries:
            promoted: bool = self._promotes(score=score, threshold=threshold)
            decisions.append(
                DecisionNode(
                    rule=rule,
                    question=question,
                    outcome=promoted,
                    score=score,
                    threshold=threshold,
                    level_before=before,
                    level_after=after if promoted else before,
                    evidence_ids=evidence_ids if promoted else (),
                ),
            )
            if not promoted:
                break
        return tuple(decisions)

    @staticmethod
    def _promotes(*, score: float, threshold: float) -> bool:
        """Promote on threshold only when positive evidence exists.

        Args:
            score: Value supplied for ``score``.
            threshold: Value supplied for ``threshold``.

        Returns:
            The resulting value.

        """
        return score > 0.0 and score >= threshold

    @staticmethod
    def _ratio(*, value: int, cap: int) -> float:
        """Normalize an integer feature to zero through one.

        Args:
            value: Value supplied for ``value``.
            cap: Value supplied for ``cap``.

        Returns:
            The resulting value.

        """
        return min(1.0, value / max(1, cap))

    @staticmethod
    def _weighted(*, values: tuple[tuple[float, float], ...]) -> float:
        """Return a bounded weighted average.

        Args:
            values: Value supplied for ``values``.

        Returns:
            The resulting value.

        """
        denominator: float = sum(weight for _, weight in values)
        return (
            0.0
            if denominator == 0.0
            else min(
                1.0,
                sum(value * weight for value, weight in values) / denominator,
            )
        )


class EvidenceCollector:
    """Collect representative source evidence for the final finding level.

    Attributes:
        MAX_EVIDENCE: Maximum evidence records returned for one file.

    """

    MAX_EVIDENCE: int = 5

    def __init__(self, *, path: Path, context: int) -> None:
        """Read and parse the source once for evidence extraction.

        Args:
            path: Value supplied for ``path``.
            context: Value supplied for ``context``.

        """
        self._path: Path = path
        self._context: int = context
        self._text: str = path.read_text(encoding="utf-8")
        self._lines: tuple[str, ...] = tuple(self._text.splitlines())
        self._tree = parse(
            source=self._text,
            filename=str(object=path),
            mode="exec",
        )

    def collect(self, *, level: UnitTestLevel) -> tuple[FindingEvidence, ...]:
        """Return evidence only for the highest level reached.

        Args:
            level: Value supplied for ``level``.

        Returns:
            The resulting value.

        """
        if level is UnitTestLevel.TEST_0:
            return ()
        ranked: list[tuple[int, str, str, AST]] = [
            ranked_node
            for node in walk(node=self._tree)
            if (ranked_node := self._rank_node(level=level, node=node))
            is not None
        ]
        if not ranked:
            definitions: tuple[AST, ...] = tuple(
                node
                for node in walk(node=self._tree)
                if node.__class__.__name__
                in {"FunctionDef", "AsyncFunctionDef", "ClassDef"}
            )
            ranked.extend(
                (
                    30,
                    "behavioral_surface",
                    "Substantive public surface contributes test importance.",
                    node,
                )
                for node in definitions
            )
        selected: list[FindingEvidence] = []
        seen: set[tuple[str, int]] = set()
        ordered: list[tuple[int, str, str, AST]] = sorted(
            ranked,
            key=lambda item: (-item[0], getattr(item[3], "lineno", 0)),
        )
        for _, category, reason, node in ordered:
            line: int = getattr(node, "lineno", 1)
            key: tuple[str, int] = (category, line)
            if key in seen:
                continue
            seen.add(key)
            selected.append(
                self._evidence(category=category, reason=reason, node=node),
            )
            if len(selected) >= self.MAX_EVIDENCE:
                break
        return tuple(selected)

    @staticmethod
    def _rank_node(
        *,
        level: UnitTestLevel,
        node: AST,
    ) -> tuple[int, str, str, AST] | None:
        """Rank one AST node as report evidence when relevant.

        Args:
            level: Final semantic level.
            node: Candidate AST node.

        Returns:
            Ranked evidence tuple, or ``None`` for irrelevant nodes.

        """
        if level is UnitTestLevel.TEST_3 and isinstance(
            node,
            (Try, TryStar, Raise),
        ):
            return (
                100,
                "error_path",
                "Error paths increase testing criticality.",
                node,
            )
        if level is UnitTestLevel.TEST_3 and isinstance(
            node,
            (For, AsyncFor, While),
        ):
            return (
                90,
                "loop",
                "Iteration creates multiple behavioral paths.",
                node,
            )
        if isinstance(node, If):
            return (
                80,
                "branch",
                "Conditional behavior requires path validation.",
                node,
            )
        if isinstance(node, Call):
            return (
                50,
                "runtime_call",
                "Runtime collaboration contributes observable behavior.",
                node,
            )
        return None

    def _evidence(
        self,
        *,
        category: str,
        reason: str,
        node: AST,
    ) -> FindingEvidence:
        """Build one source-backed evidence record.

        Args:
            category: Value supplied for ``category``.
            reason: Value supplied for ``reason``.
            node: Value supplied for ``node``.

        Returns:
            The resulting value.

        """
        line: int = getattr(node, "lineno", 1)
        end_line: int = getattr(node, "end_lineno", line) or line
        start: int = max(1, line - self._context)
        end: int = min(len(self._lines), end_line + self._context)
        source: tuple[SourceLine, ...] = tuple(
            SourceLine(
                line=index,
                text=self._lines[index - 1],
                highlighted=line <= index <= end_line,
            )
            for index in range(start, end + 1)
        )
        return FindingEvidence(
            id=f"{category}:{line}:{end_line}",
            category=category,
            reason=reason,
            line=line,
            end_line=end_line,
            context_start_line=start,
            context_end_line=end,
            source=source,
        )


def baseline_metrics(*, path: Path) -> Metrics:
    """Measure a source with the established AST analyzer.

    Args:
        path: Value supplied for ``path``.

    Returns:
        The resulting value.

    """
    classification: Classification = PythonTestNeedClassifier(
        path=path,
        threshold=10**9,
    ).classify()
    return classification.metrics


def javascript_metrics(*, path: Path) -> Metrics:
    """Measure conservative behavioral signals in JavaScript source.

    The scanner removes comments and literals before counting control-flow and
    mutation tokens. It intentionally promotes ambiguous executable scripts
    instead of filtering them as safe to leave untested.

    Args:
        path: JavaScript-family source file.

    Returns:
        Metrics compatible with the language-neutral policy evaluator.

    """
    text: str = path.read_text(encoding="utf-8")
    code: str = _javascript_code(text=text)
    branches: int = len(
        findall(pattern=r"\b(?:if|switch|case)\b|\?", string=code),
    )
    loops: int = len(findall(pattern=r"\b(?:for|while|do)\b", string=code))
    handlers: int = len(findall(pattern=r"\bcatch\b", string=code))
    raises: int = len(findall(pattern=r"\bthrow\b", string=code))
    booleans: int = len(findall(pattern=r"&&|\|\||\?\?", string=code))
    calls: int = len(
        findall(
            pattern=r"\b[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*\s*\(",
            string=code,
        ),
    )
    mutations: int = len(
        findall(
            pattern=(
                "(?<![=!<>])=(?!=|>)|\\+\\+|--|\\.(?:push|pop|set|delete)\\s*"
                "\\("
            ),
            string=code,
        ),
    )
    callables: int = len(findall(pattern=r"\bfunction\b|=>", string=code))
    statements: int = code.count(";") + branches + loops + handlers + raises
    nesting: int = 0
    depth: int = 0
    for character in code:
        if character == "{":
            depth += 1
            nesting = max(nesting, depth)
        elif character == "}":
            depth = max(0, depth - 1)
    computations: int = len(
        findall(
            pattern=r"(?<![+\-*/%])(?:\+|-|\*|/|%)(?![=+\-*/%])",
            string=code,
        ),
    )
    public_members: int = len(
        findall(
            pattern=r"\bexport\b|\bglobalThis\.[A-Za-z_$][\w$]*",
            string=code,
        ),
    )
    return Metrics(
        cyclomatic_complexity=1 + branches + loops + handlers + booleans,
        branches=branches,
        loops=loops,
        exception_handlers=handlers,
        raises=raises,
        boolean_decisions=booleans,
        comprehension_decisions=0,
        computations=computations,
        side_effects=min(calls, statements),
        mutations=mutations,
        behavioral_statements=statements,
        runtime_calls=calls,
        substantive_callables=callables,
        trivial_callables=0,
        public_behavioral_members=public_members or min(callables * 3, 10),
        module_runtime_statements=statements,
        max_control_nesting=nesting,
    )


def javascript_evidence(
    *,
    path: Path,
    context: int,
    level: UnitTestLevel,
) -> tuple[FindingEvidence, ...]:
    """Collect source-backed evidence for a JavaScript classification.

    Args:
        path: JavaScript-family source file.
        context: Surrounding source lines retained per item.
        level: Classification level selected by policy.

    Returns:
        Up to four deterministic executable-behavior evidence records.

    """
    lines: list[str] = path.read_text(encoding="utf-8").splitlines()
    patterns: tuple[tuple[str, str, str], ...] = (
        (
            "control-flow",
            r"\b(?:if|else|switch|case|for|while|catch)\b",
            "Control flow requires behavioral coverage.",
        ),
        (
            "error-path",
            r"\b(?:throw|catch)\b",
            "Explicit error behavior requires a failure-path test.",
        ),
        (
            "mutation",
            r"(?<![=!<>])=(?!=|>)|\+\+|--|\.push\s*\(",
            "State mutation requires observable verification.",
        ),
        (
            "callable",
            r"=>|\bfunction\b",
            "Executable callable behavior requires a direct test.",
        ),
    )
    evidence: list[FindingEvidence] = []
    category: str
    pattern: str
    reason: str
    for category, pattern, reason in patterns:
        line_number: int | None = next(
            (
                index
                for index, line in enumerate(iterable=lines, start=1)
                if next(finditer(pattern=pattern, string=line), None)
                is not None
            ),
            None,
        )
        if line_number is None:
            continue
        start: int = max(1, line_number - context)
        end: int = min(len(lines), line_number + context)
        evidence.append(
            FindingEvidence(
                id=f"javascript-{category}:{line_number}:{line_number}",
                category=f"javascript-{category}",
                reason=reason,
                line=line_number,
                end_line=line_number,
                context_start_line=start,
                context_end_line=end,
                source=tuple(
                    SourceLine(
                        line=index,
                        text=lines[index - 1],
                        highlighted=index == line_number,
                    )
                    for index in range(start, end + 1)
                ),
            ),
        )
        if len(evidence) >= (1 if level is UnitTestLevel.TEST_1 else 4):
            break
    return tuple(evidence)


def _javascript_code(*, text: str) -> str:
    """Replace JavaScript comments and literals with whitespace.

    Args:
        text: Raw JavaScript source.

    Returns:
        Text retaining executable punctuation and keywords.

    """
    without_comments: str = sub(
        pattern=r"/\*[\s\S]*?\*/|//[^\n]*",
        repl=" ",
        string=text,
    )
    return sub(
        pattern=r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`",
        repl=" ",
        string=without_comments,
    )
