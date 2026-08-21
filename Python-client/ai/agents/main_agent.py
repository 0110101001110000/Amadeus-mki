"""
ai/agents/main_agent.py
"""

from __future__ import annotations

import re
import json
import logging
from typing import Any, Iterable
from ai.clients.llm_client import LLMClient
from ai.prompts.system_prompt import SYSTEM_PROMPT
from ai.agents.dependencies import AgentDependencies
from ai.tools.robot_context_tool import RobotContextTool
from ai.tools.state_machine_tool import StateMachineTool
from ai.models.agent_decision import AgentAction, AgentDecision
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai import Agent, ModelMessage, ModelResponse, RunContext, TextPart, ToolCallPart


# Global -------------------------------------------------------------------- #


logger = logging.getLogger(__name__)


# Utils --------------------------------------------------------------------- #


def _normalize_text(text: str) -> str:
    """Normalize textual input."""

    return text.strip()


def _extract_json_from_text(text: str) -> dict[str, Any]:
    """Extract the first JSON object from a string."""

    candidate = text.strip()

    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            return parsed[0]
    except json.JSONDecodeError:
        pass

    match = re.search(r"(\{.*\})", candidate, flags=re.DOTALL)
    if match:
        parsed = json.loads(match.group(1))
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            return parsed[0]

    raise ValueError("No valid JSON object found in model response.")


def _safe_get_part_text(part: Any) -> str:
    """Extract readable text from a Pydantic AI message part."""

    return str(getattr(part, "content", "") or "").strip()


def _message_summary(messages: Iterable[ModelMessage]) -> str:
    """Create a concise summary of the conversation."""

    lines: list[str] = []

    for message in messages:
        parts = getattr(message, "parts", [])
        for part in parts:
            part_kind = getattr(part, "part_kind", "")
            if part_kind == "user-prompt":
                lines.append(f"USER: {_safe_get_part_text(part)}")
            elif part_kind == "tool-return":
                tool_name = getattr(part, "tool_name", "unknown_tool")
                lines.append(f"TOOL_RETURN[{tool_name}]: {_safe_get_part_text(part)}")
            elif part_kind == "text":
                lines.append(f"MODEL: {_safe_get_part_text(part)}")

    return "\n".join(lines[-12:])


def _available_tool_summary(info: AgentInfo) -> str:
    """Summarize available function tools for the LLM."""

    tool_lines: list[str] = []

    for tool in getattr(info, "function_tools", []):
        name = getattr(tool, "name", "unknown_tool")
        description = getattr(tool, "description", "")
        tool_lines.append(f"- {name}: {description}")

    return "\n".join(tool_lines) or "- No tools available."


def _heuristic_decision(text: str) -> AgentDecision:
    """Build a fallback decision when the model response is malformed."""

    lowered = text.lower()

    if any(keyword in lowered for keyword in ("stop", "halt", "abort", "emergency", "parar", "pare", "emergencia")):
        return AgentDecision(
            action=AgentAction.EMERGENCY_STOP,
            message="Emergency stop requested.",
            confidence=0.6,
            requires_confirmation=False,
            metadata={"source": "heuristic"},
        )

    if any(keyword in lowered for keyword in ("cancel", "cancelar")):
        return AgentDecision(
            action=AgentAction.CANCEL,
            message="Operation cancelled.",
            confidence=0.6,
            requires_confirmation=False,
            metadata={"source": "heuristic"},
        )

    if any(keyword in lowered for keyword in ("inspect", "look", "observe", "analyze", "ver", "observar", "analisar", "inspecionar")):
        return AgentDecision(
            action=AgentAction.INSPECT,
            target_object=None,
            message="Scene inspection requested.",
            confidence=0.6,
            requires_confirmation=False,
            metadata={"source": "heuristic"},
        )

    if lowered:
        return AgentDecision(
            action=AgentAction.PICK,
            target_object=lowered,
            message=f"Searching for '{lowered}'.",
            confidence=0.5,
            requires_confirmation=False,
            metadata={"source": "heuristic"},
        )

    return AgentDecision(
        action=AgentAction.IDLE,
        message="No action requested.",
        confidence=0.5,
        requires_confirmation=False,
        metadata={"source": "heuristic"},
    )


def _build_final_decision(payload: dict[str, Any]) -> AgentDecision:
    """Coerce a dictionary payload into an AgentDecision."""

    if "decision" in payload and isinstance(payload["decision"], dict):
        payload = payload["decision"]

    return AgentDecision(
        action=AgentAction(payload.get("action", AgentAction.IDLE.value)),
        target_object=payload.get("target_object"),
        message=payload.get("message"),
        confidence=float(payload.get("confidence", 1.0)),
        requires_confirmation=bool(payload.get("requires_confirmation", False)),
        metadata=dict(payload.get("metadata", {}) or {}),
    )


# Classes ------------------------------------------------------------------- #


class MainAgent:
    """High-level coordinator that converts user requests into decisions."""

    def __init__(
        self,
        llm_config: Any,
        agent_config: Any | None = None,
    ) -> None:
        self._enabled: bool = True
        self._agent_config = agent_config
        self._llm_client = LLMClient(llm_config)
        self._message_history: list[ModelMessage] = []

        self._agent = Agent(
            model=FunctionModel(self._model_router),
            deps_type=AgentDependencies,
            output_type=AgentDecision,
            instructions=SYSTEM_PROMPT,
        )

        self._register_tools()

        logger.info("MainAgent initialized successfully.")

    @property
    def enabled(self) -> bool:
        """Return the current agent status."""

        return self._enabled

    def enable(self) -> None:
        """Enable the agent."""

        self._enabled = True
        logger.info("MainAgent enabled.")

    def disable(self) -> None:
        """Disable the agent."""

        self._enabled = False
        logger.info("MainAgent disabled.")

    def process(self, user_input: str, deps: AgentDependencies) -> AgentDecision:
        """Convert a user request into a structured decision."""

        if not self._enabled:
            logger.warning("MainAgent is disabled.")
            return AgentDecision(
                action=AgentAction.IDLE,
                message="Agent disabled.",
                confidence=0.0,
                requires_confirmation=False,
                metadata={"source": "disabled"},
            )

        text = _normalize_text(user_input)
        logger.info("Processing user request: %s", text)

        try:
            result = self._agent.run_sync(
                text,
                deps=deps,
                message_history=list(self._message_history) or None,
            )

            self._message_history = list(result.new_messages())
            decision = result.output
            self._apply_decision_to_context(deps, decision)

            logger.info("Agent decision generated: %s", decision)
            return decision

        except Exception:
            logger.exception("Unexpected error while processing user request.")
            fallback = _heuristic_decision(text)
            self._apply_decision_to_context(deps, fallback)
            return fallback

    def _register_tools(self) -> None:
        """Register PydanticAI tools."""

        @self._agent.tool
        def request_pick(
            ctx: RunContext[AgentDependencies],
            target: str,
        ) -> AgentDecision:
            """Request a pick action for a target object."""

            return RobotContextTool.request_pick(ctx.deps.robot_context, target)

        @self._agent.tool
        def request_inspect(
            ctx: RunContext[AgentDependencies],
            #target: str | None = None,
        ) -> AgentDecision:
            """Request a scene inspection."""

            # if target:
            #     return VisionTool.locate_target(ctx.deps.robot_context, target)

            return RobotContextTool.request_inspect(ctx.deps.robot_context)

        @self._agent.tool
        def request_cancel(
            ctx: RunContext[AgentDependencies],
        ) -> AgentDecision:
            """Request cancellation of the current operation."""

            return RobotContextTool.request_cancel(ctx.deps.robot_context)

        @self._agent.tool
        def request_emergency_stop(
            ctx: RunContext[AgentDependencies],
        ) -> AgentDecision:
            """Request an emergency stop."""

            return RobotContextTool.request_emergency_stop(ctx.deps.robot_context)

        @self._agent.tool
        def transition_to(
            ctx: RunContext[AgentDependencies],
            next_state_name: str,
        ) -> bool:
            """Request a state transition."""

            return StateMachineTool.transition_to(
                ctx.deps.robot_context,
                next_state_name,
            )

    def _model_router(
        self,
        messages: list[ModelMessage],
        info: AgentInfo,
    ) -> ModelResponse:
        """Route the agent request through the remote LLM."""

        try:
            prompt = self._build_prompt(messages, info)
            raw_text = self._llm_client.generate(prompt)
            payload = self._parse_model_payload(raw_text, messages)

            if self._can_call_tool(messages) and self._has_tool_name(payload):
                tool_name = str(payload["tool_name"]).strip()
                tool_args = dict(payload.get("tool_args", {}) or {})
                logger.info("LLM requested tool call: %s", tool_name)
                return ModelResponse(
                    parts=[
                        ToolCallPart(
                            tool_name,
                            tool_args,
                        )
                    ]
                )

            decision = _build_final_decision(payload)
            return ModelResponse(
                parts=[
                    TextPart(decision.model_dump_json()),
                ]
            )

        except Exception:
            logger.exception("Model routing failed. Falling back to heuristic decision.")
            fallback = _heuristic_decision(_message_summary(messages))
            return ModelResponse(
                parts=[
                    TextPart(fallback.model_dump_json()),
                ]
            )

    def _build_prompt(self, messages: list[ModelMessage], info: AgentInfo) -> str:
        """Build the prompt sent to the local Gradio-hosted model."""

        tool_summary = _available_tool_summary(info)
        conversation_summary = _message_summary(messages)

        return (
            f"{SYSTEM_PROMPT}"
            
            "You must answer with valid JSON only."
            
            "When a tool is needed, return JSON in this shape:"
            '{"tool_name": "pick", "tool_args": {"target": "white cube"}}'
            
            "When you are ready to finish, return JSON with this shape:"
            '{"action": "pick", "target_object": "white cube", "message": "...", "confidence": 0.95, "requires_confirmation": false, "metadata": {}}'
            
            "Available tools:"
            f"{tool_summary}"
            
            "Conversation summary:"
            f"{conversation_summary}"
        )

    @staticmethod
    def _parse_model_payload(raw_text: str, messages: list[ModelMessage]) -> dict[str, Any]:
        """Parse JSON from the model response, with fallbacks."""

        try:
            return _extract_json_from_text(raw_text)
        except Exception:
            logger.warning("Model response was not valid JSON. Falling back to heuristic parsing.")
            return {"action": _heuristic_decision(raw_text).action.value, "message": raw_text}

    @staticmethod
    def _has_tool_name(payload: dict[str, Any]) -> bool:
        """Check if a payload requests a tool call."""

        return bool(payload.get("tool_name"))

    @staticmethod
    def _can_call_tool(messages: list[ModelMessage]) -> bool:
        """Allow tool calls only before the first tool return."""

        if not messages:
            return True

        last_message = messages[-1]
        for part in getattr(last_message, "parts", []):
            if getattr(part, "part_kind", "") == "tool-return":
                return False

        return True

    @staticmethod
    def _apply_decision_to_context(
        deps: AgentDependencies,
        decision: AgentDecision,
    ) -> None:
        """Apply an agent decision to the runtime context."""

        context = deps.robot_context
        if context is None:
            return

        try:
            setattr(context, "pending_decision", decision)
            setattr(context, "last_agent_response", decision.message or "")

            if decision.target_object:
                setattr(context, "object_query", decision.target_object)

            if decision.action == AgentAction.PICK:
                setattr(context, "trigger_received", True)
                setattr(context, "inspect_requested", False)

            elif decision.action == AgentAction.INSPECT:
                setattr(context, "inspect_requested", True)

            elif decision.action == AgentAction.CANCEL:
                setattr(context, "cancel_requested", True)

            elif decision.action == AgentAction.EMERGENCY_STOP:
                setattr(context, "emergency_requested", True)
                state_machine = getattr(context, "state_machine", None) or deps.state_machine
                if state_machine is not None:
                    state_machine.transition_to("EMERGENCY_STOP")

        except Exception:
            logger.exception("Failed to apply agent decision to context.")
