"""
ai/tools/robot_context_tool.py
"""

from __future__ import annotations

import logging
from typing import Any
from ai.models.agent_decision import AgentAction, AgentDecision


logger = logging.getLogger(__name__)


def _safe_setattr(target: Any, attribute: str, value: Any) -> None:
    """Set an attribute only when the target supports it."""

    if target is None:
        return

    try:
        setattr(target, attribute, value)
    except Exception:
        logger.exception("Unable to set attribute '%s'.", attribute)


class RobotContextTool:
    """Utility functions for robot state coordination."""

    @staticmethod
    def request_pick(robot_context: Any, target: str) -> AgentDecision:
        """Register a pick request in the robot context."""

        logger.info("Registering pick request for target '%s'.", target)

        _safe_setattr(robot_context, "object_query", target)
        _safe_setattr(robot_context, "trigger_received", True)
        _safe_setattr(robot_context, "inspect_requested", False)

        decision = AgentDecision(
            action=AgentAction.PICK,
            target_object=target,
            message=f"Searching for '{target}'.",
            confidence=1.0,
            requires_confirmation=False,
            metadata={"source": "tool", "request_type": "pick"},
        )
        _safe_setattr(robot_context, "pending_decision", decision)
        return decision

    @staticmethod
    def request_inspect(robot_context: Any, target: str | None = None) -> AgentDecision:
        """Register an inspection request in the robot context."""

        logger.info("Registering inspection request.")

        if target:
            _safe_setattr(robot_context, "object_query", target)

        _safe_setattr(robot_context, "inspect_requested", True)

        decision = AgentDecision(
            action=AgentAction.INSPECT,
            target_object=target,
            message="Scene inspection requested.",
            confidence=1.0,
            requires_confirmation=False,
            metadata={"source": "tool", "request_type": "inspect"},
        )
        _safe_setattr(robot_context, "pending_decision", decision)
        return decision

    @staticmethod
    def request_cancel(robot_context: Any) -> AgentDecision:
        """Register a cancel request in the robot context."""

        logger.info("Registering cancel request.")

        _safe_setattr(robot_context, "cancel_requested", True)

        decision = AgentDecision(
            action=AgentAction.CANCEL,
            message="Operation cancelled.",
            confidence=1.0,
            requires_confirmation=False,
            metadata={"source": "tool", "request_type": "cancel"},
        )
        _safe_setattr(robot_context, "pending_decision", decision)
        return decision

    @staticmethod
    def request_emergency_stop(robot_context: Any) -> AgentDecision:
        """Register an emergency stop request in the robot context."""

        logger.warning("Registering emergency stop request.")

        _safe_setattr(robot_context, "emergency_requested", True)

        decision = AgentDecision(
            action=AgentAction.EMERGENCY_STOP,
            message="Emergency stop requested.",
            confidence=1.0,
            requires_confirmation=False,
            metadata={"source": "tool", "request_type": "emergency_stop"},
        )
        _safe_setattr(robot_context, "pending_decision", decision)
        return decision

    @staticmethod
    def request_idle(robot_context: Any) -> AgentDecision:
        """Register an idle state request in the robot context."""

        logger.info("Registering idle request.")

        decision = AgentDecision(
            action=AgentAction.IDLE,
            message="No action requested.",
            confidence=1.0,
            requires_confirmation=False,
            metadata={"source": "tool", "request_type": "idle"},
        )
        _safe_setattr(robot_context, "pending_decision", decision)
        return decision
