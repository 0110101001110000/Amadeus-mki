"""
ai/tools/state_machine_tool.py
"""

from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


class StateMachineTool:
    """Utility functions for state machine coordination."""

    @staticmethod
    def transition_to(robot_context: Any, state_name: str) -> bool:
        """Request a state transition when possible."""

        state_machine = getattr(robot_context, "state_machine", None)
        if state_machine is None:
            logger.warning("State machine is not attached to the robot context.")
            return False

        try:
            logger.info("Requesting transition to state '%s'.", state_name)
            state_machine.transition_to(state_name)
            return True
        except Exception:
            logger.exception("State transition to '%s' failed.", state_name)
            return False

    @staticmethod
    def request_emergency_stop(robot_context: Any) -> bool:
        """Request an emergency stop transition."""

        _ = getattr(robot_context, "emergency_requested", True)
        setattr(robot_context, "emergency_requested", True)

        return StateMachineTool.transition_to(robot_context, "EMERGENCY_STOP")

    @staticmethod
    def request_idle(robot_context: Any) -> bool:
        """Request a transition to IDLE."""

        return StateMachineTool.transition_to(robot_context, "IDLE")
