
import time
import logging
from typing import Dict, Optional
from abc import ABC, abstractmethod
from config.config import TaskConfig
from motion.planner import CartesianPoint
from communication.protocol import GripState
from ai.models.agent_decision import AgentDecision


# Global -------------------------------------------------------------------- #


logger = logging.getLogger(__name__)


# Classes ------------------------------------------------------------------- #


class RobotContext:
    """Carries shared subsystem references and coordinate states across state transitions."""

    def __init__(self, comm_manager, vision_manager, motion_manager, task_config: TaskConfig) -> None:
        self.comm = comm_manager
        self.vision = vision_manager
        self.motion = motion_manager
        self.task_config = task_config
        
        # State coordinates tracking
        self.current_position: CartesianPoint = self.motion.get_home_position()
        self.target_position: Optional[CartesianPoint] = None
        self.trigger_received: bool = False
        self.state_machine: Optional["StateMachine"] = None

        # Agent
        self.agent_enabled: bool = True
        self.agent_status: str = "READY"
        self.pending_decision: Optional[AgentDecision] = None
        self.inspect_requested = False
        self.cancel_requested: bool = False
        self.emergency_requested: bool = False
        self.last_agent_response: str = ""
        self.user_command: str = ""
        self.object_query: str = ""

class State(ABC):
    """Abstract Base Class representing a singular machine state."""

    def __init__(self, context: RobotContext) -> None:
        self.context = context

    def on_enter(self) -> None:
        """Executed immediately when transitioning into this state."""
        pass

    @abstractmethod
    def on_update(self) -> Optional[str]:
        """Runs cyclical logic inside the active state. Returns target state name for transition or None."""
        pass

    def on_exit(self) -> None:
        """Executed immediately when transitioning out of this state."""
        pass


# States -------------------------------------------------------------------- #


class InitState(State):
    """Calibrates hardware parameters and transitions to IDLE."""

    def on_update(self) -> Optional[str]:
        logger.info("Initializing system baseline configurations...")
        self.context.motion.setup_hardware_limits()

        # Move arm at start for safety
        home_pos = self.context.motion.get_home_position()
        self.context.motion.execute_move(home_pos, home_pos)

        self.context.motion.set_gripper_state(GripState.CLOSE)

        return "IDLE"


class IdleState(State):
    """Waits for trigger condition to begin pick-and-place pipeline."""

    def on_enter(self) -> None:
        self.context.vision.disable_processing()

        self.context.vision.update_status(
            state="IDLE",
            camera="ONLINE",
            detection="WAITING"
        )

        logger.info("Arm in IDLE position. Awaiting activation trigger.")

    def on_update(self) -> Optional[str]:
        if self.context.trigger_received:
            self.context.trigger_received = False
            return "DETECT_TARGET"
        return None


class DetectTargetState(State):
    """Safely handles the camera power state during targeting operations."""

    def on_enter(self) -> None:
        self.context.vision.enable_processing()

        self.context.vision.update_status(
            state="DETECT_TARGET",
            camera="CAPTURING",
            detection="SEARCHING"
        )

        time.sleep(1.0)

    # def on_update(self) -> Optional[str]:
    #     frame = self.context.vision.get_latest_frame()
    #     if frame is None:
    #         return None
    #
    #     # Project world z coordinates constraint
    #     targets = self.context.vision.process_and_localize(
    #         frame,
    #         target_z_plane=self.context.task_config.pickup_height_mm
    #     )
    #
    #     if targets:
    #         self.context.vision.update_status(
    #             state="DETECT_TARGET",
    #             camera="CAPTURING",
    #             detection="TARGET FOUND"
    #         )
    #
    #         target = targets[0]
    #         coord = target.world_coordinate
    #         self.context.target_position = CartesianPoint(x=coord.x, y=coord.y, z=coord.z)
    #         logger.info(f"Target locked at: {self.context.target_position}")
    #         return "PICKUP_PREP"
    #
    #     self.context.vision.update_status(
    #         state="DETECT_TARGET",
    #         camera="CAPTURING",
    #         detection="NOT FOUND"
    #     )
    #
    #     logger.info("No targets located. Returning to IDLE state.")
    #     return "IDLE"

    def on_update(self) -> Optional[str]:
        frame = self.context.vision.get_latest_frame()
        if frame is None:
            return None

        logger.info(f"VLM searching for: {self.context.object_query}")

        targets = self.context.vision.vlm_process_and_localize(
            frame,
            target_label=self.context.object_query,
            target_z_plane=self.context.task_config.pickup_height_mm
        )

        if targets:
            self.context.vision.update_status(
                state="DETECT_TARGET",
                camera="CAPTURING",
                detection=f"FOUND {self.context.object_query.upper()}"
            )

            target = targets[0]
            coord = target.world_coordinate
            self.context.target_position = CartesianPoint(x=coord.x, y=coord.y, z=coord.z)
            return "PICKUP_PREP"

        logger.warning(f"VLM could not find {self.context.object_query}. Returning to IDLE state.")
        return "IDLE"

    def on_exit(self) -> None:
        logger.debug("DetectTargetState exited – leaving camera feed running.")


class PickupPrepState(State):
    """Opens gripper and positions tool head safely over the target coordinate."""

    def on_update(self) -> Optional[str]:
        target = self.context.target_position
        if not target:
            return "RETURN_HOME"

        logger.info("Preparing pickup tools...")
        self.context.motion.set_gripper_state(GripState.OPEN)

        # Hover position coordinates (safe plane elevation)
        hover_point = CartesianPoint(
            x=target.x,
            y=target.y,
            z=self.context.task_config.safe_height_mm
        )

        success = self.context.motion.execute_move(self.context.current_position, hover_point)
        if success:
            self.context.current_position = hover_point
            return "PICKUP"
        
        logger.error("Failed to position arm above target.")
        return "RETURN_HOME"


class PickupState(State):
    """Lowers, grips, and lifts target up to safety margin."""

    def on_update(self) -> Optional[str]:
        target = self.context.target_position
        if not target:
            return "RETURN_HOME"

        # Lower to grab point
        grab_point = CartesianPoint(
            x=target.x, 
            y=target.y, 
            z=self.context.task_config.pickup_height_mm
        )
        logger.info(f"Lowering to tool height: {grab_point.z}mm")
        
        if not self.context.motion.execute_move(self.context.current_position, grab_point):
            return "RETURN_HOME"
        self.context.current_position = grab_point

        # Clamp down on object
        logger.info("Gripping target...")
        time.sleep(0.5)
        self.context.motion.set_gripper_state(GripState.CLOSE)
        time.sleep(0.5)

        # Lift back up to clear workspace
        lift_point = CartesianPoint(
            x=target.x, 
            y=target.y, 
            z=self.context.task_config.safe_height_mm
        )
        logger.info("Lifting target...")
        if self.context.motion.execute_move(self.context.current_position, lift_point):
            self.context.current_position = lift_point
            return "MOVE_TO_DROP"

        return "RETURN_HOME"


class MoveToDropState(State):
    """Dispatches loaded tool path coordinates to the Drop plane coordinates."""

    def on_update(self) -> Optional[str]:
        drop = self.context.task_config.drop_zone
        
        # Safe transit over drop zone
        hover_drop = CartesianPoint(
            x=drop.x,
            y=drop.y,
            z=self.context.task_config.safe_height_mm
        )
        
        logger.info(f"Transiting target to drop hover: {hover_drop}")
        if not self.context.motion.execute_move(self.context.current_position, hover_drop):
            return "EMERGENCY_STOP"
        self.context.current_position = hover_drop

        # Lower down to drop plane z coordinate
        lowered_drop = CartesianPoint(
            x=drop.x,
            y=drop.y,
            z=self.context.task_config.drop_height_mm
        )
        logger.info(f"Lowering to drop plane height: {lowered_drop.z}mm")
        if self.context.motion.execute_move(self.context.current_position, lowered_drop):
            self.context.current_position = lowered_drop
            return "DROP"

        return "EMERGENCY_STOP"


class DropState(State):
    """Releases target secure points and settles."""

    def on_update(self) -> Optional[str]:
        logger.info("Releasing target payload...")
        self.context.motion.set_gripper_state(GripState.OPEN)
        time.sleep(1.0)
        return "RETURN_HOME"


class ReturnHomeState(State):
    """Returns tool configuration back to baseline parameters."""

    def on_update(self) -> Optional[str]:
        home_pos = self.context.motion.get_home_position()
        logger.info(f"Returning workspace trajectory path to Home configuration: {home_pos}")
        
        self.context.motion.execute_move(self.context.current_position, home_pos)
        self.context.current_position = home_pos
        self.context.motion.set_gripper_state(GripState.CLOSE)
        
        return "IDLE"


class EmergencyStopState(State):
    """Dispatches override shutdown sequence commands immediately."""

    def on_enter(self) -> None:
        logger.critical("EMERGENCY STOP STATE ENGAGED. HALTING ROBOT SYSTEM.")
        self.context.motion.trigger_emergency_stop()

    def on_update(self) -> Optional[str]:
        # Lock state machine execution
        return None


# Main Class ---------------------------------------------------------------- #


class StateMachine:
    """Manages system execution registry loops and handles state transitions."""

    def __init__(self, context: RobotContext, initial_state: str) -> None:
        self.context = context
        self.context.state_machine = self
        self._states: Dict[str, State] = {}
        self._current_state_name: str = initial_state
        self._current_state: Optional[State] = None

    def register_state(self, name: str, state: State) -> None:
        """Binds a concrete State class with an access key string name."""
        self._states[name] = state

    def start(self) -> None:
        """Starts state tracking on the defined entry point."""
        self._current_state = self._states.get(self._current_state_name)
        if self._current_state:
            logger.info(f"Initializing state machine sequence on state: '{self._current_state_name}'")
            self._current_state.on_enter()

    def update(self) -> None:
        """Triggers dynamic loop update functions of the active state."""
        if not self._current_state:
            return

        try:
            next_state_name = self._current_state.on_update()
            if next_state_name and next_state_name != self._current_state_name:
                self.transition_to(next_state_name)
        except Exception as e:
            logger.critical(f"Unhandled fault in active state '{self._current_state_name}': {e}")
            self.transition_to("EMERGENCY_STOP")

    def transition_to(self, next_state_name: str) -> None:
        """Exits current state and targets subsequent operational state."""
        if next_state_name not in self._states:
            logger.error(f"Cannot transition: '{next_state_name}' state key registry is missing.")
            return

        logger.info(f"FSM State Transition: '{self._current_state_name}' ---> '{next_state_name}'")
        self._current_state.on_exit()
        
        self._current_state_name = next_state_name
        self._current_state = self._states[next_state_name]
        self._current_state.on_enter()
