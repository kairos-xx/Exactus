#!/usr/bin/env python3
# Copyright (c) 2026
"""Process-isolated Python API for canonical exactus tools."""

from __future__ import annotations

from json import JSONDecodeError, loads
from pathlib import Path
from re import Match, search
from time import monotonic, sleep
from typing import TYPE_CHECKING, Final, cast

from exactus.packages.pmanager import Orchestrator, ProcessStatus
from exactus.packages.pmanager.runtime import Discovery
from exactus.tools.common.models import ToolRequest, ToolRunResult
from exactus.tools.common.tool_worker import (
    build_spec,
    ensure_worker_path,
    live_status,
    result_from_status,
    tool_context,
    worker_arguments,
)

if TYPE_CHECKING:
    from exactus.tools.common.catalog import ToolSpec
    from exactus.tools.common.json_types import JsonValue


class ExactusApi:
    """Represent exactus api.

    Attributes:
        poll_seconds: Poll seconds.

    """

    poll_seconds: Final[float] = 0.1

    @classmethod
    def run_tool(
        cls,
        *,
        request: ToolRequest,
        spec: ToolSpec,
    ) -> ToolRunResult:
        """Return run tool.

        Args:
            request: Request.
            spec: Spec.

        Returns:
            The worker's result, or a failed result when the worker
            exited before reporting.

        """
        ensure_worker_path()
        context_name: str = tool_context(
            root=request.project_root or Path.cwd(),
            owner=request.run_id,
        )
        orchestrator: Orchestrator = Orchestrator.from_object_spec(
            specification=build_spec(
                tools=(spec,),
                root=request.project_root or Path.cwd(),
            ),
        )
        try:
            _ = orchestrator.context(name=context_name).create(
                process=spec.identifier,
                arguments=worker_arguments(request=request, spec=spec),
            )
            started: float = monotonic()
            process_status: ProcessStatus | None = None
            while True:
                process_status = live_status(
                    descriptors=Discovery.all(),
                    name=spec.identifier,
                    context=context_name,
                )
                if process_status is None or process_status.terminal:
                    break
                sleep(cls.poll_seconds)
            return result_from_status(
                request=request,
                spec=spec,
                process_status=process_status,
                started=started,
            )
        finally:
            orchestrator.close(kill_owned=True)

    @staticmethod
    def reconcile(*, result: ToolRunResult) -> ToolRunResult:
        """Return reconcile.

        Args:
            result: Result.

        Returns:
            The resulting value.

        """
        try:
            raw: str = result.report_json.read_text(encoding="utf-8")
        except OSError:
            return result
        match: Match[str] | None = search(
            pattern=r'"run_id"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"',
            string=raw,
        )
        if match is not None and match.group(1) == result.run_id:
            return result
        try:
            payload: JsonValue = cast(typ="JsonValue", val=loads(s=raw))
        except JSONDecodeError:
            return result.replaced()
        if not isinstance(payload, dict):
            return result.replaced()
        return ToolRunResult.from_report(
            payload=payload,
            output=result.report_json.parent,
            fallback=result,
        )
