# Copyright (c) 2026 Project contributors
"""Define typed action inputs, outputs and stable value-source bindings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


class FlowValueType(StrEnum):
    """Name every value category accepted by an action contract.

    Attributes:
        STRING: Text.
        INTEGER: Whole number.
        FLOAT: Floating-point number.
        NUMBER: Integer-or-float union.
        BOOLEAN: Boolean.
        JSON: JSON-compatible value.
        URL: URL text with URL semantics.
        SELECTOR: Extended selector expression.
        DURATION: Time duration.
        ARTIFACT: Artifact reference.
        LIST: Ordered collection.
        VOID: No value.
        ENUM: Schema-owned choice.
        EXPRESSION: Typed expression.
        VARIABLE_REF: Stable variable reference.
        VARIABLE_TYPE: Type inherited from a variable declaration.
        INFERRED: Type inferred from another slot or expression.
        DEVICE_STATE: Runtime device state.
        BROWSER_PAGE: Browser page handle.
        BROWSER_FRAME: Browser frame handle.
        BROWSER_DOWNLOAD: Browser download handle.
        BROWSER_DIALOG: Browser dialog result.

    """

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    NUMBER = "number"
    BOOLEAN = "boolean"
    JSON = "json"
    URL = "url"
    SELECTOR = "selector"
    DURATION = "duration"
    ARTIFACT = "artifact"
    LIST = "list"
    VOID = "void"
    ENUM = "enum"
    EXPRESSION = "expression"
    VARIABLE_REF = "variable_ref"
    VARIABLE_TYPE = "variable_type"
    INFERRED = "inferred"
    DEVICE_STATE = "device_state"
    BROWSER_PAGE = "browser.page"
    BROWSER_FRAME = "browser.frame"
    BROWSER_DOWNLOAD = "browser.download"
    BROWSER_DIALOG = "browser.dialog"


class BindingKind(StrEnum):
    """Identify how an input obtains its value.

    Attributes:
        LITERAL: Persisted JSON literal.
        ACTION_OUTPUT: Stable output of another action.
        VARIABLE: Stable named-variable identity.
        TEMPLATE: Text containing typed value tokens.
        PROMPT: Value requested when execution reaches the node.

    """

    LITERAL = "literal"
    ACTION_OUTPUT = "action_output"
    VARIABLE = "variable"
    TEMPLATE = "template"
    PROMPT = "prompt"


class SlotSensitivity(StrEnum):
    """Describe which sensitivity an input slot accepts.

    Attributes:
        PUBLIC: Accept only public values.
        ACCEPTS_SENSITIVE: Accept public or secret values.
        SENSITIVE_ONLY: Accept only secret values.

    """

    PUBLIC = "public"
    ACCEPTS_SENSITIVE = "accepts_secret"
    SENSITIVE_ONLY = "secret_only"


class PortSensitivity(StrEnum):
    """Describe the sensitivity an output publishes.

    Attributes:
        PUBLIC: Always public.
        INHERITED: Inherit sensitivity from contributing inputs.
        SENSITIVE: Always secret.

    """

    PUBLIC = "public"
    INHERITED = "inherited"
    SENSITIVE = "secret"


class ExposureDestination(StrEnum):
    """Name a destination to which an action can expose an input.

    Attributes:
        PAGE: Browser page content.
        NETWORK: Network request.
        LOG: Runtime log.
        SCREENSHOT: Captured image.
        ERROR: Error detail.
        EVIDENCE: Evidence artifact.

    """

    PAGE = "page"
    NETWORK = "network"
    LOG = "log"
    SCREENSHOT = "screenshot"
    ERROR = "error"
    EVIDENCE = "evidence"


class EvaluationTiming(StrEnum):
    """Choose when an input binding is evaluated.

    Attributes:
        COMPILE: Once while compiling the executable program.
        NODE_ENTRY: Whenever execution enters the node.
        EACH_ATTEMPT: Before every retry attempt.

    """

    COMPILE = "compile"
    NODE_ENTRY = "node_entry"
    EACH_ATTEMPT = "each_attempt"


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class LiteralBindingValue:
    """Wrap a literal so JSON null differs from an absent payload.

    Attributes:
        value: JSON-compatible literal, including null.

    """

    value: JsonValue


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class ActionOutputReference:
    """Identify one published action result independently of its label.

    Attributes:
        producer_id: Stable action identity.
        port_id: Stable output-port identity.
        path: Optional structured-value path.
        getter: Optional named conversion applied after the path.

    """

    producer_id: str
    port_id: str
    path: tuple[str, ...] = ()
    getter: str | None = None

    @property
    def source_id(self) -> str:
        """Return the stable identity used by indexes and persisted links.

        Returns:
            The ``producer_id/port_id`` identity.

        """
        return f"{self.producer_id}/{self.port_id}"

    def __post_init__(self) -> None:
        """Reject references that cannot form a stable source identity.

        Raises:
            ValueError: When an identity, path part or getter is empty.

        """
        if self.producer_id.strip() == "" or self.port_id.strip() == "":
            msg: str = (
                "Action-output references require producer and port IDs."
            )
            raise ValueError(msg)
        if any(part.strip() == "" for part in self.path):
            msg = "Action-output reference paths cannot contain empty parts."
            raise ValueError(msg)
        if self.getter is not None and self.getter.strip() == "":
            msg = "Action-output reference getters cannot be empty."
            raise ValueError(msg)


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class ActionInputBinding:
    """Bind one input slot to exactly one kind-specific payload.

    Attributes:
        kind: Payload interpretation.
        literal: Wrapped literal payload.
        action_output: Stable output reference payload.
        variable_id: Stable variable identity payload.
        template: Tokenized text payload.
        prompt: Runtime prompt label payload.
        timing: Evaluation point.

    """

    kind: BindingKind
    literal: LiteralBindingValue | None = None
    action_output: ActionOutputReference | None = None
    variable_id: str | None = None
    template: str | None = None
    prompt: str | None = None
    timing: EvaluationTiming = EvaluationTiming.NODE_ENTRY

    @property
    def hard_dependency_id(self) -> str | None:
        """Return the producer action that must precede this binding.

        Returns:
            The producer ID for an action-output binding, otherwise None.

        """
        if self.action_output is None:
            return None
        return self.action_output.producer_id

    def __post_init__(self) -> None:
        """Require exactly one non-empty payload matching ``kind``.

        Raises:
            ValueError: When payload cardinality or kind does not match.

        """
        payloads: tuple[bool, ...] = (
            self.literal is not None,
            self.action_output is not None,
            self.variable_id is not None,
            self.template is not None,
            self.prompt is not None,
        )
        if sum(payloads) != 1:
            msg: str = "An input binding requires exactly one payload."
            raise ValueError(msg)
        expected: dict[BindingKind, bool] = {
            BindingKind.LITERAL: self.literal is not None,
            BindingKind.ACTION_OUTPUT: self.action_output is not None,
            BindingKind.VARIABLE: self.variable_id is not None,
            BindingKind.TEMPLATE: self.template is not None,
            BindingKind.PROMPT: self.prompt is not None,
        }
        if not expected[self.kind]:
            msg = f"Binding kind {self.kind.value} does not match its payload."
            raise ValueError(msg)
        text_payloads: tuple[str | None, ...] = (
            self.variable_id,
            self.template,
            self.prompt,
        )
        if any(
            value is not None and value.strip() == ""
            for value in text_payloads
        ):
            msg = "Variable, template and prompt payloads cannot be empty."
            raise ValueError(msg)


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class InputSlot:
    """Define one typed action input and its secret destination policy.

    Attributes:
        slot_id: Stable slot identity.
        value_type: Accepted value category.
        required: Whether compilation requires a binding.
        many: Whether the slot accepts repeated bindings.
        item_type: Element type for list-like inputs.
        sensitivity: Accepted value sensitivity.
        exposes_to: Destinations the action may reach with this input.
        allows_each_attempt: Whether retry-time evaluation is allowed.

    """

    slot_id: str
    value_type: FlowValueType
    required: bool
    many: bool = False
    item_type: FlowValueType | None = None
    sensitivity: SlotSensitivity = SlotSensitivity.PUBLIC
    exposes_to: frozenset[ExposureDestination] = frozenset()
    allows_each_attempt: bool = False

    def accepts_secret(self, *, secret: bool) -> bool:
        """Return whether a value's sensitivity can enter this slot.

        Args:
            secret: Whether the incoming value is secret.

        Returns:
            True when the slot permits that sensitivity.

        """
        if self.sensitivity is SlotSensitivity.SENSITIVE_ONLY:
            return secret
        if self.sensitivity is SlotSensitivity.ACCEPTS_SENSITIVE:
            return True
        return not secret

    def accepts_timing(self, *, timing: EvaluationTiming) -> bool:
        """Return whether the slot permits the requested evaluation timing.

        Args:
            timing: Requested binding evaluation point.

        Returns:
            True when the slot supports the timing.

        """
        return (
            timing is not EvaluationTiming.EACH_ATTEMPT
            or self.allows_each_attempt
        )

    def __post_init__(self) -> None:
        """Reject empty identities and public slots with exposure claims.

        Raises:
            ValueError: When the slot definition is internally inconsistent.

        """
        if self.slot_id.strip() == "":
            msg: str = "Input slot IDs cannot be empty."
            raise ValueError(msg)
        if self.value_type is FlowValueType.VOID:
            msg = "An input slot cannot accept void."
            raise ValueError(msg)
        if self.sensitivity is SlotSensitivity.PUBLIC and self.exposes_to:
            msg = (
                "Public-only slots cannot declare secret exposure "
                "destinations."
            )
            raise ValueError(msg)
        if (
            self.value_type is not FlowValueType.LIST
            and self.item_type is not None
        ):
            msg = "Only list inputs may declare an item type."
            raise ValueError(msg)


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class OutputPort:
    """Define one stable result published by an action.

    Attributes:
        port_id: Stable port identity.
        value_type: Published value category.
        nullable: Whether the result may be null.
        primary: Whether this is the action's default result.
        item_type: Element type for list results.
        sensitivity: Published sensitivity rule.

    """

    port_id: str
    value_type: FlowValueType
    nullable: bool = False
    primary: bool = False
    item_type: FlowValueType | None = None
    sensitivity: PortSensitivity = PortSensitivity.PUBLIC

    def __post_init__(self) -> None:
        """Reject empty IDs and inconsistent list metadata.

        Raises:
            ValueError: When the output definition is internally inconsistent.

        """
        if self.port_id.strip() == "":
            msg: str = "Output port IDs cannot be empty."
            raise ValueError(msg)
        if self.value_type is FlowValueType.VOID:
            msg = "Void actions publish no output port."
            raise ValueError(msg)
        if (
            self.value_type is not FlowValueType.LIST
            and self.item_type is not None
        ):
            msg = "Only list outputs may declare an item type."
            raise ValueError(msg)


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class ActionSchema:
    """Define the complete input/output interface of one action kind.

    Attributes:
        action_id: Stable action kind.
        inputs: Ordered input slots.
        outputs: Ordered output ports.
        dynamic_inputs: Whether authored code adds named inputs.
        dynamic_outputs: Whether authored code adds named outputs.

    """

    action_id: str
    inputs: tuple[InputSlot, ...]
    outputs: tuple[OutputPort, ...]
    dynamic_inputs: bool = False
    dynamic_outputs: bool = False

    def __post_init__(self) -> None:
        """Require stable unique IDs and at most one primary output.

        Raises:
            ValueError: When the schema has ambiguous identities or results.

        """
        if self.action_id.strip() == "":
            msg: str = "Action schema IDs cannot be empty."
            raise ValueError(msg)
        input_ids: tuple[str, ...] = tuple(
            slot.slot_id for slot in self.inputs
        )
        output_ids: tuple[str, ...] = tuple(
            port.port_id for port in self.outputs
        )
        if len(set(input_ids)) != len(input_ids):
            msg = f"Action {self.action_id} has duplicate input slot IDs."
            raise ValueError(msg)
        if len(set(output_ids)) != len(output_ids):
            msg = f"Action {self.action_id} has duplicate output port IDs."
            raise ValueError(msg)
        if sum(port.primary for port in self.outputs) > 1:
            msg = f"Action {self.action_id} has multiple primary outputs."
            raise ValueError(msg)


def hard_dependency_ids(
    *,
    bindings: tuple[ActionInputBinding, ...],
) -> tuple[str, ...]:
    """Return producer IDs in first-use order without duplicates.

    Args:
        bindings: Bindings owned by one consumer action.

    Returns:
        Stable producer action IDs that must run before the consumer.

    """
    dependencies: list[str] = []
    for binding in bindings:
        dependency: str | None = binding.hard_dependency_id
        if dependency is not None and dependency not in dependencies:
            dependencies.append(dependency)
    return tuple(dependencies)
