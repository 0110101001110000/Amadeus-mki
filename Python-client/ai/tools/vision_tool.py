"""
ai/tools/vision_tool.py
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from ai.models.agent_decision import AgentDecision, AgentAction

logger = logging.getLogger(__name__)


class VisionTool:
    """Tool for gathering general workspace metadata for the Agent."""

    @staticmethod
    def get_workspace_snapshot(robot_context: Any) -> Dict[str, Any]:
        """Captures general information about the current vision state."""
        vision = getattr(robot_context, "vision_manager", None)

        if not vision:
            return {"status": "offline", "error": "VisionManager unavailable"}

        # Coleta dados brutos do Manager
        return {
            "status": "active" if vision._camera and vision._camera.is_running else "idle",
            "last_detections_count": len(vision._current_detections),
            "detected_objects": [d.class_name for d in vision._current_detections],
            "has_frame": vision._last_frame is not None,
        }

    @staticmethod
    def inspect_scene(robot_context: Any) -> AgentDecision:
        """Standard tool for the agent to 'look' at the workspace."""
        info = VisionTool.get_workspace_snapshot(robot_context)

        message = (
            f"Workspace is {info['status']}. "
            f"Currently seeing {info['last_detections_count']} objects: {info['detected_objects']}."
        )

        return AgentDecision(
            action=AgentAction.INSPECT,
            message=message,
            metadata=info,
            confidence=1.0
        )
