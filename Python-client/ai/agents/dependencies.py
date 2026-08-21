"""
ai/agents/dependencies.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AgentDependencies:
    """Shared runtime dependencies for the agent."""

    robot_context: Any
    vision_manager: Any
    motion_manager: Any
    state_machine: Any
    task_config: Any
    agent_config: Any
