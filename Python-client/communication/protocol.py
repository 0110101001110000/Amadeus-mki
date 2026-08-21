"""
communication/protocol.py
"""

from __future__ import annotations

import sys
import logging
import argparse
from enum import Enum
from typing import Dict
from dataclasses import dataclass, field


# Global -------------------------------------------------------------------- #


logger = logging.getLogger(__name__)
PROTOCOL_TERMINATOR = ";"


# Utils --------------------------------------------------------------------- #


def validate_servo(servo: int) -> None:
    """Validate servo identifier."""

    if servo < 0:
        raise ValueError("Servo ID must be greater than or equal to 0.")


def validate_position(position: int) -> None:
    """Validate servo position."""

    if not 0 <= position <= 180:
        raise ValueError("Servo position must be between 0 and 180.")


def validate_move_all_positions(
    **positions: int,
) -> None:
    """Validate MOVE_ALL positions."""

    for servo, position in positions.items():
        if position is None:
            continue

        validate_position(position)


def validate_speed(min_speed: int, max_speed: int) -> None:
    """Validate speed configuration."""

    if min_speed < 0 or max_speed < 0:
        raise ValueError("Speed values must be positive.")

    if min_speed > max_speed:
        raise ValueError(
            "Minimum speed cannot be greater than maximum speed.",
        )


def validate_argument_key(key: str) -> None:
    """Validate protocol argument key."""

    if not key.isupper():
        raise ValueError(
            f"Argument key '{key}' must be uppercase.",
        )


# Classes ------------------------------------------------------------------- #


class CommandCategory(Enum):
    """Available command categories."""

    MOVEMENT = "movement"
    MANIPULATION = "manipulation"
    SYSTEM = "system"
    CONFIGURATION = "configuration"
    EMERGENCY = "emergency"
    AUTOMATION = "automation"


class GripState(Enum):
    """Available gripper states."""

    OPEN = 1
    CLOSE = 0


class ShowcaseMode(Enum):
    """Available showcase modes."""

    MODE_0 = 0
    MODE_1 = 1


@dataclass(frozen=True)
class ProtocolMessage:
    """Represents a protocol message."""

    command: str
    arguments: Dict[str, str] = field(default_factory=dict)

    def serialize(self) -> str:
        """Serialize protocol message."""

        try:
            if not self.command.isupper():
                raise ValueError(
                    "Protocol commands must be uppercase.",
                )

            serialized_arguments = []

            for key, value in self.arguments.items():
                validate_argument_key(key)

                serialized_arguments.append(
                    f"{key}={value}"
                )

            arguments_section = " ".join(serialized_arguments)

            if arguments_section:
                serialized_message = (
                    f"{self.command} {arguments_section}"
                    f"{PROTOCOL_TERMINATOR}"
                )
            else:
                serialized_message = (
                    f"{self.command}"
                    f"{PROTOCOL_TERMINATOR}"
                )

            logger.debug(
                "Protocol message serialized successfully: %s",
                serialized_message,
            )

            return serialized_message

        except Exception as error:
            logger.exception(
                "Failed to serialize protocol message: %s",
                error,
            )
            raise


class ProtocolBuilder:
    """Builds protocol-compliant messages."""

    @staticmethod
    def move_to(
        servo: int,
        position: int,
    ) -> ProtocolMessage:
        """Build MOVE_TO command."""

        try:
            validate_servo(servo)
            validate_position(position)

            logger.debug(
                "Building MOVE_TO command | servo=%s | position=%s",
                servo,
                position,
            )

            return ProtocolMessage(
                command="MOVE_TO",
                arguments={
                    "SERVO": str(servo),
                    "POSITION": str(position),
                },
            )

        except Exception as error:
            logger.exception(
                "Failed to build MOVE_TO command: %s",
                error,
            )
            raise

    @staticmethod
    def move_all(
        s1: int | None = None,
        s2: int | None = None,
        s3: int | None = None,
        s4: int | None = None,
    ) -> ProtocolMessage:
        """Build MOVE_ALL command."""

        try:
            validate_move_all_positions(
                s1=s1,
                s2=s2,
                s3=s3,
                s4=s4,
            )

            logger.debug(
                (
                    "Building MOVE_ALL command | "
                    "s1=%s | s2=%s | s3=%s | s4=%s"
                ),
                s1,
                s2,
                s3,
                s4,
            )

            arguments = {}

            if s1 is not None:
                arguments["S1"] = str(s1)

            if s2 is not None:
                arguments["S2"] = str(s2)

            if s3 is not None:
                arguments["S3"] = str(s3)

            if s4 is not None:
                arguments["S4"] = str(s4)

            if not arguments:
                raise ValueError(
                    "MOVE_ALL requires at least one servo position."
                )

            return ProtocolMessage(
                command="MOVE_ALL",
                arguments=arguments,
            )

        except Exception as error:
            logger.exception(
                "Failed to build MOVE_ALL command: %s",
                error,
            )
            raise

    @staticmethod
    def grip(state: GripState) -> ProtocolMessage:
        """Build GRIP command."""

        try:
            logger.debug(
                "Building GRIP command | state=%s",
                state.value,
            )

            return ProtocolMessage(
                command="GRIP",
                arguments={
                    "STATE": state.value,
                },
            )

        except Exception as error:
            logger.exception(
                "Failed to build GRIP command: %s",
                error,
            )
            raise

    @staticmethod
    def reset() -> ProtocolMessage:
        """Build RESET command."""

        logger.debug("Building RESET command")

        return ProtocolMessage(command="RESET")

    @staticmethod
    def speed(
        min_speed: int,
        max_speed: int,
    ) -> ProtocolMessage:
        """Build SPEED command."""

        try:
            validate_speed(
                min_speed=min_speed,
                max_speed=max_speed,
            )

            logger.debug(
                "Building SPEED command | min=%s | max=%s",
                min_speed,
                max_speed,
            )

            return ProtocolMessage(
                command="SPEED",
                arguments={
                    "MIN": str(min_speed),
                    "MAX": str(max_speed),
                },
            )

        except Exception as error:
            logger.exception(
                "Failed to build SPEED command: %s",
                error,
            )
            raise

    @staticmethod
    def stop() -> ProtocolMessage:
        """Build STOP command."""

        logger.warning(
            "Building STOP emergency command.",
        )

        return ProtocolMessage(command="STOP")

    @staticmethod
    def showcase(
        mode: ShowcaseMode,
    ) -> ProtocolMessage:
        """Build SHOWCASE command."""

        try:
            logger.debug(
                "Building SHOWCASE command | mode=%s",
                mode.value,
            )

            return ProtocolMessage(
                command="SHOWCASE",
                arguments={
                    "MODE": mode.value,
                },
            )

        except Exception as error:
            logger.exception(
                "Failed to build SHOWCASE command: %s",
                error,
            )
            raise


# Init ---------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    """Create CLI parser."""

    parser = argparse.ArgumentParser(
        description="AMADEUS MK-I Protocol Builder",
    )

    parser.add_argument(
        "--command",
        type=str,
        required=True,
        choices=[
            "MOVE_TO",
            "GRIP",
            "RESET",
            "SPEED",
            "STOP",
            "SHOWCASE",
        ],
        help="Protocol command.",
    )

    parser.add_argument(
        "--servo",
        type=int,
        default=0,
        help="Servo ID for MOVE_TO.",
    )

    parser.add_argument(
        "--position",
        type=int,
        default=90,
        help="Servo position for MOVE_TO.",
    )

    parser.add_argument(
        "--state",
        type=str,
        default="OPEN",
        choices=["OPEN", "CLOSE"],
        help="Grip state.",
    )

    parser.add_argument(
        "--min-speed",
        type=int,
        default=10,
        help="Minimum speed.",
    )

    parser.add_argument(
        "--max-speed",
        type=int,
        default=100,
        help="Maximum speed.",
    )

    parser.add_argument(
        "--mode",
        type=str,
        default="START",
        choices=["START", "STOP"],
        help="Showcase mode.",
    )

    return parser


def execute_command(args: argparse.Namespace) -> str:
    """Execute selected command."""

    try:
        command = args.command

        if command == "MOVE_TO":
            message = ProtocolBuilder.move_to(
                servo=args.servo,
                position=args.position,
            )

        elif command == "GRIP":
            message = ProtocolBuilder.grip(
                state=GripState(args.state),
            )

        elif command == "RESET":
            message = ProtocolBuilder.reset()

        elif command == "SPEED":
            message = ProtocolBuilder.speed(
                min_speed=args.min_speed,
                max_speed=args.max_speed,
            )

        elif command == "STOP":
            message = ProtocolBuilder.stop()

        elif command == "SHOWCASE":
            message = ProtocolBuilder.showcase(
                mode=ShowcaseMode(args.mode),
            )

        else:
            raise ValueError(
                f"Unsupported command: {command}",
            )

        return message.serialize()

    except Exception as error:
        logger.exception(
            "Failed to execute command: %s",
            error,
        )
        raise


def main() -> None:
    """Application entrypoint."""

    parser = build_parser()
    args = parser.parse_args()

    try:
        serialized_message = execute_command(args)

        logger.info(
            "Generated protocol message: %s",
            serialized_message,
        )

    except Exception:
        logger.error("Protocol execution failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
