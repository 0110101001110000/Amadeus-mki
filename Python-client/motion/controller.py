"""
motion/controller.py
"""

from __future__ import annotations

import time
import logging
import threading
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from motion.planner import CartesianPoint
from communication.serial_client import SerialClient
from communication.protocol import ProtocolBuilder, GripState
from motion.kinematics import RoboticArmKinematics, InverseKinematicsError, MotorAngles


# Global -------------------------------------------------------------------- #


logger = logging.getLogger(__name__)


# Utils --------------------------------------------------------------------- #


def angle_to_servo_position(angle_degrees: float, range_limits: tuple = (0, 180)) -> int:
    """
    Converts a floating-point joint angle in degrees to an integer servo step.
    Clamps the final value within safe operational bounds.
    """
    min_limit, max_limit = range_limits
    clamped_angle = max(min_limit, min(max_limit, angle_degrees))
    return int(round(clamped_angle))


def extract_angles(motor_angles: MotorAngles) -> List[float]:
    """
    Safely extracts individual joint angles from a MotorAngles object.
    Prioritizes specific known structures (like MotorAngles) before
    falling back to generic iteration or other definitions.
    """
    # 1. Handle the specific, known structure (MotorAngles)
    if isinstance(motor_angles, MotorAngles):
        return [motor_angles.base, motor_angles.shoulder, motor_angles.elbow]

    # 2. Fallback for other known structures (e.g., older kinematic models)
    if hasattr(motor_angles, "theta1") and hasattr(motor_angles, "theta2") and hasattr(motor_angles, "theta3"):
        return [motor_angles.theta1, motor_angles.theta2, motor_angles.theta3]

    if hasattr(motor_angles, "base") and hasattr(motor_angles, "shoulder") and hasattr(motor_angles, "elbow"):
        # This catch-all remains for compatibility if the object isn't MotorAngles
        return [motor_angles.base, motor_angles.shoulder, motor_angles.elbow]

    # 3. Generic fallback for iterable objects
    try:
        return list(motor_angles)
    except TypeError as e:
        raise MotionControlError(
            f"Failed to extract angles from unknown kinematic structure: {type(motor_angles)}"
        ) from e


def serialize_protocol_message(message: Any) -> str:
    """
    Serializes a protocol message object to its raw string format.
    Falls back to a standard string representation if no custom serialization method is found.
    """
    if hasattr(message, "serialize") and callable(message.serialize):
        return str(message.serialize())
    return str(message)


def parse_arduino_message(msg: str) -> Optional[ArduinoFeedback]:
    """
    Parses a feedback string into structured ArduinoFeedback parameters.
    Format expected: <TYPE>:<COMMAND>:<STATUS>[:<DATA>]
    """
    parts = msg.strip().split(":", 2)
    if len(parts) < 2:
        return None

    msg_type = parts[0]
    command = parts[1]
    status = parts[2] if len(parts) > 2 else ""

    return ArduinoFeedback(
        msg_type=msg_type,
        command=command,
        status=status,
        raw_message=msg
    )


# Classes ------------------------------------------------------------------- #


@dataclass(frozen=True)
class ControllerConfig:
    """Configuration settings for the motion control loop and safety limits."""
    servo_mapping: Dict[str, int] = field(default_factory=lambda: {
        "base": 1,
        "shoulder": 2,
        "elbow": 3
    })
    min_speed: int = 22     # 22 -> 45 graus/s
    max_speed: int = 11     # 11 -> 90 graus/s
    command_settle_delay: float = 0.05
    wait_timeout_seconds: float = 8.0
    default_angle_range: tuple = (0, 180)


@dataclass(frozen=True)
class ArduinoFeedback:
    """Structure for parsed Arduino serial feedback messages."""
    msg_type: str
    command: str
    status: str
    raw_message: str


class MotionControlError(Exception):
    """Raised when an error occurs during execution of motion commands."""
    pass


class MotionController:
    """
    Translates spatial trajectories into physical motor signals and manages execution flow
    synchronously using feedback messages from the hardware to prevent command overlap.
    """

    def __init__(self, kinematics: RoboticArmKinematics, serial_client: SerialClient, config: ControllerConfig) -> None:
        """
        Initializes the MotionController and registers callbacks to serial events.

        :param kinematics: Kinematics engine for coordinate transformation.
        :param serial_client: Establishes raw physical serial interface communications.
        :param config: Hardware parameters and timing constraints.
        """
        self._kinematics = kinematics
        self._serial_client = serial_client
        self._config = config

        # Thread synchronization components
        self._command_execution_event = threading.Event()
        self._last_hardware_error: Optional[str] = None
        self._last_commanded_pose: Optional[Dict[str, int]] = None

        # Register callback to receive serial messages asynchronously
        self._serial_client.register_callback(self._on_serial_message_received)
        logger.info("MotionController initialized with thread synchronization support.")

    def configure_system_limits(self) -> None:
        """Transmits velocity limits and configures the micro-controller."""
        logger.info(f"Configuring system speeds: min={self._config.min_speed}, max={self._config.max_speed}")
        try:
            msg = ProtocolBuilder.speed(self._config.min_speed, self._config.max_speed)
            serialized_cmd = serialize_protocol_message(msg)
            self._send_command_and_wait(serialized_cmd)
        except Exception as e:
            logger.error(f"Failed to write velocity configuration: {e}")
            raise MotionControlError(f"System limit configuration failed: {e}") from e

    def execute_trajectory(self, waypoints: List[CartesianPoint]) -> None:
        """
        Sequentially executes spatial waypoints. All joints are transmitted
        through a single MOVE_ALL command and execution blocks until the
        micro-controller confirms completion.
        """
        if not waypoints:
            logger.warning("Aborted trajectory execution: empty waypoints list.")
            return

        logger.debug(f"Executing synchronized trajectory with {len(waypoints)} waypoints.")

        try:
            for index, point in enumerate(waypoints):
                logger.debug(f"Moving to waypoint {index + 1}/{len(waypoints)}: {point}")

                # Convert Cartesian coordinates to motor angles
                motor_angles_obj = self._kinematics.calculate(point.x, point.y, point.z)
                angles = extract_angles(motor_angles_obj)

                # Dispatch all joint targets through a single synchronized MOVE_ALL command
                self._dispatch_joint_positions_synchronously(angles)

            logger.info("Trajectory executed successfully without overlap.")

        except InverseKinematicsError as e:
            logger.error(f"Execution halted. Target point out of physical range: {e}")
            self.emergency_stop()
            raise MotionControlError(f"Kinematics error during trajectory: {e}") from e

        except Exception as e:
            logger.exception(f"Hardware execution error occurred: {e}")
            self.emergency_stop()
            raise MotionControlError(f"Trajectory execution failed: {e}") from e

    def control_gripper(self, state: GripState) -> None:
        """
        Sends gripper transition commands and blocks until execution is complete.
        """
        logger.info(f"Requesting gripper state change: {state}")
        try:
            msg = ProtocolBuilder.grip(state)
            serialized_cmd = serialize_protocol_message(msg)
            self._send_command_and_wait(serialized_cmd)
        except Exception as e:
            logger.error(f"Gripper execution failed: {e}")
            raise MotionControlError(f"Gripper action interrupted: {e}") from e

    def emergency_stop(self) -> None:
        """
        Immediately interrupts active signals, aborts waits, and halts hardware.
        """
        logger.warning("Emergency stop requested. Signaling immediate halt.")
        try:
            msg = ProtocolBuilder.stop()
            serialized_cmd = serialize_protocol_message(msg)
            self._serial_client.send(serialized_cmd)
            self._command_execution_event.set()  # Unblock any waiting threads immediately
        except Exception as e:
            logger.critical(f"Critical failure broadcasting stop command: {e}")

    def _dispatch_joint_positions_synchronously(
            self,
            angles: List[float],
    ) -> None:
        """
        Sends all joint targets using a single MOVE_ALL command.
        Execution blocks until the Arduino reports completion.
        """

        joint_keys = [
            "base",
            "shoulder",
            "elbow",
        ]

        target_positions: Dict[str, int] = {}

        for i, joint in enumerate(joint_keys):
            if i >= len(angles):
                break

            target_positions[joint] = angle_to_servo_position(
                angles[i],
                self._config.default_angle_range,
            )

        if (
                self._last_commanded_pose is not None
                and
                self._last_commanded_pose.get("base")
                == target_positions.get("base")
                and
                self._last_commanded_pose.get("shoulder")
                == target_positions.get("shoulder")
                and
                self._last_commanded_pose.get("elbow")
                == target_positions.get("elbow")
        ):
            logger.info(
                "All joints already in target position. Skipping MOVE_ALL."
            )
            return

        logger.debug(
            (
                "Dispatching MOVE_ALL | "
                "base=%s | shoulder=%s | elbow=%s"
            ),
            target_positions.get("base"),
            target_positions.get("shoulder"),
            target_positions.get("elbow"),
        )

        msg = ProtocolBuilder.move_all(
            s1=target_positions.get("base"),
            s2=target_positions.get("shoulder"),
            s3=target_positions.get("elbow"),
        )

        serialized_cmd = serialize_protocol_message(msg)

        self._send_command_and_wait(serialized_cmd)

        self._last_commanded_pose = {
            "base": target_positions.get("base"),
            "shoulder": target_positions.get("shoulder"),
            "elbow": target_positions.get("elbow"),
        }

    def _send_command_and_wait(self, command_string: str) -> None:
        """
        Transmits a protocol command and blocks the active execution context
        until the micro-controller signals completion or times out.
        """
        self._command_execution_event.clear()
        self._last_hardware_error = None

        self._serial_client.send(command_string)

        # Block context execution and wait for confirmation event from listener
        completed = self._command_execution_event.wait(timeout=self._config.wait_timeout_seconds)

        if not completed:
            logger.error(
                f"Command execution timed out after {self._config.wait_timeout_seconds} seconds: {command_string}")
            raise MotionControlError("Hardware command confirmation timed out.")

        if self._last_hardware_error:
            logger.error(f"Micro-controller reported a failure: {self._last_hardware_error}")
            raise MotionControlError(f"Hardware execution aborted: {self._last_hardware_error}")

        # Minor settling pause after receiving feedback
        time.sleep(self._config.command_settle_delay)

    def _on_serial_message_received(self, raw_message: str) -> None:
        """
        Asynchronous listener callback executed by the SerialClient thread to unblock
        the trajectory queue when commands are done.
        """
        feedback = parse_arduino_message(raw_message)
        if not feedback:
            return

        logger.debug(f"Received feedback message: {feedback}")

        # 1. Evaluate Move command completion
        if feedback.command in ("MOVE_TO", "MOVE_ALL"):
            if feedback.msg_type == "OK" or feedback.status == "STOPPED" or "STOPPED" in feedback.raw_message:
                logger.debug(f"Move complete callback signal processed: {feedback.raw_message}")
                self._command_execution_event.set()

        # 2. Evaluate Gripper adjustment completion
        elif feedback.command == "GRIP":
            if feedback.msg_type == "OK" or feedback.status == "STOPPED" or "STOPPED" in feedback.raw_message:
                logger.debug(f"Grip action callback signal processed: {feedback.raw_message}")
                self._command_execution_event.set()

        # 3. Evaluate speed and generic command ok status
        elif feedback.command in ("SPEED", "RESET"):
            if feedback.msg_type == "OK" or "DONE" in feedback.status:
                logger.debug(f"Command '{feedback.command}' complete callback signal processed.")
                self._command_execution_event.set()

        # 4. Handle emergency stop response
        elif feedback.command == "STOP":
            if "DONE" in feedback.status:
                logger.warning("Stop signal processed on hardware.")
                self._last_hardware_error = "Emergency halt complete"
                self._command_execution_event.set()

        # 5. Handle standard failure cases reported by micro-controller
        elif feedback.msg_type == "ERROR":
            logger.error(f"System error reported by Arduino: {feedback.raw_message}")
            self._last_hardware_error = feedback.raw_message
            self._command_execution_event.set()


# Main ---------------------------------------------------------------------- #


# ...
