
import logging
from typing import Optional
from config.config import MotionConfig
from communication.protocol import GripState
from motion.kinematics import RoboticArmKinematics
from communication.serial_client import SerialClient
from motion.controller import MotionController, MotionControlError
from motion.workspace import WorkspaceValidator, WorkspaceValidationError
from motion.planner import TrajectoryPlanner, CartesianPoint, TrajectoryPlanningError

logger = logging.getLogger(__name__)


class MotionManager:
    """Manages planning, coordination, and physical execution of robotic trajectories."""

    def __init__(self, config: MotionConfig) -> None:
        self._config = config
        self._kinematics: Optional[RoboticArmKinematics] = None
        self._planner: Optional[TrajectoryPlanner] = None
        self._controller: Optional[MotionController] = None

        self._last_position: Optional[CartesianPoint] = None

        self._workspace = WorkspaceValidator(config.workspace)

    def initialize(self, serial_client: SerialClient) -> bool:
        """Instantiates kinematics, planning, and control modules.

        Args:
            serial_client: Connected, functional SerialClient instance.

        Returns:
            bool: True if initialization succeeded, False otherwise.
        """
        try:
            # Validate that the kinematics configuration is available
            if not self._config.kinematics:
                logger.error("Missing kinematics configuration in MotionConfig.")
                return False

            # Create the kinematics instance
            self._kinematics = RoboticArmKinematics(
                configuration=self._config.kinematics
            )

            # If, for some reason, the instance is still None, treat it as a failure
            if not self._kinematics:
                logger.error("Failed to create RoboticArmKinematics instance.")
                return False

            # Proceed with the rest of the initialization
            self._planner = TrajectoryPlanner(
                kinematics=self._kinematics,
                config=self._config.planner
            )
            self._controller = MotionController(
                kinematics=self._kinematics,
                serial_client=serial_client,
                config=self._config.controller
            )
            logger.info("Motion Manager modules configured successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Motion Manager modules: {e}")
            return False

    def setup_hardware_limits(self) -> None:
        """Transmits minimum and maximum hardware velocity safety limits to the device."""
        if self._controller:
            try:
                self._controller.configure_system_limits()
                logger.info("System operational speed limits transmitted to device.")
            except MotionControlError as e:
                logger.error(f"Failed to configure hardware limits: {e}")

    def get_home_position(self) -> CartesianPoint:
        """Returns the configured home CartesianPoint coordinates."""
        return self._config.planner.home_position

    def execute_move(self, start: CartesianPoint, target: CartesianPoint) -> bool:
        """Plans and safe-executes a collision-free path from start to target.

        Args:
            start: Current Cartesian position.
            target: Desired target Cartesian position.

        Returns:
            bool: True if motion succeeded, False if error occurred.
        """
        if not self._planner or not self._controller:
            logger.error("Planning or control subsystems are inactive.")
            return False

        try:
            self._workspace.validate(target)

            logger.info(f"Planning route from {start} to {target}...")
            waypoints = self._planner.plan_trajectory(start, target)

            logger.info(f"Sending trajectory sequence ({len(waypoints)} waypoints) to controller...")
            self._controller.execute_trajectory(waypoints)

            self._last_position = target

            return True

        except (TrajectoryPlanningError, MotionControlError) as e:
            logger.error(f"Movement command failed: {e}")
            return False
        except WorkspaceValidationError as e:
            logger.error(f"Workspace violation: {e}")
            return False

    def execute_pose(self, target: CartesianPoint) -> bool:
        """
        Executes a direct Cartesian pose without requiring
        the caller to provide the current position.
        """

        if not self._controller:
            logger.error(
                "Controller subsystem inactive."
            )
            return False

        try:
            self._workspace.validate(target)

            self._controller.execute_trajectory(
                [target]
            )

            return True

        except MotionControlError as e:
            logger.error(f"Pose execution failed: {e}")
            return False
        except WorkspaceValidationError as e:
            logger.error(f"Workspace violation: {e}")
            return False

    def get_current_position(
            self,
    ) -> Optional[CartesianPoint]:
        """
        Returns the last successfully executed position.
        """

        return self._last_position

    def set_gripper_state(self, state: GripState) -> bool:
        """Sets physical gripper state (open/closed)."""
        if not self._controller:
            logger.error("Controller inactive. Gripper command refused.")
            return False
        try:
            self._controller.control_gripper(state)
            return True
        except MotionControlError as e:
            logger.error(f"Gripper actuation failed: {e}")
            return False

    def trigger_emergency_stop(self) -> None:
        """Triggers emergency stop commands immediately to arrest physical movement."""
        if self._controller:
            try:
                self._controller.emergency_stop()
                logger.info("Emergency Stop dispatched to hardware.")
            except Exception as e:
                logger.error(f"Critical error executing emergency arrest command: {e}")