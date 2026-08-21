"""
Inverse kinematics module for a robotic arm with:
    - 1 rotational base axis
    - 2DOF planar arm (shoulder + elbow)

This script converts a desired Cartesian coordinate (X, Y, Z)
into calibrated servo motor angles:
    - Motor 1: Base
    - Motor 2: Shoulder
    - Motor 3: Elbow

The coordinate system assumes:
    - X and Y define the horizontal plane around the base
    - Z defines the vertical axis
"""

from __future__ import annotations

import sys
import yaml
import math
import logging
import argparse
from dataclasses import dataclass
from typing import Optional, Dict, Any


# Global -------------------------------------------------------------------- #


logger = logging.getLogger(__name__)


# Utils --------------------------------------------------------------------- #


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a numeric value to a given range."""
    return max(minimum, min(maximum, value))

def _load_settings(config_path: str) -> Dict[str, Any]:
    """Loads configuration elements from settings yaml filepath."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"Critical error: Configuration path missing at {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Critical error parsing configuration parameters: {e}")
        sys.exit(1)


# Classes ------------------------------------------------------------------- #


@dataclass(frozen=True)
class JointCalibration:
    """Servo calibration parameters."""

    base_ref_deg: float
    base_ref_pwd: float

    shoulder_ref_deg: float
    shoulder_ref_pwd: float

    elbow_ref_deg: float
    elbow_ref_pwd: float

    shoulder_gain: float
    elbow_gain: float

    base_inverted: bool
    shoulder_inverted: bool
    elbow_inverted: bool


@dataclass(frozen=True)
class ArmConfiguration:
    """Robotic arm configuration."""

    upper_arm_length_mm: float
    forearm_length_mm: float
    base_height_offset_mm: float

    max_reach_mm: float
    min_reach_mm: float

    base_servo_min_angle: float
    base_servo_max_angle: float

    shoulder_servo_min_angle: float
    shoulder_servo_max_angle: float

    elbow_servo_min_angle: float
    elbow_servo_max_angle: float

    calibration: JointCalibration


@dataclass(frozen=True)
class MotorAngles:
    """Calculated motor angles."""

    base: float
    shoulder: float
    elbow: float


class InverseKinematicsError(Exception):
    """Raised when inverse kinematics calculation fails."""


class RoboticArmKinematics:
    """Handles inverse kinematics calculations for a base plus 2DOF planar arm."""

    def __init__(self, configuration: ArmConfiguration):
        if configuration.upper_arm_length_mm <= 0:
            raise ValueError("Upper arm length must be greater than zero.")

        if configuration.forearm_length_mm <= 0:
            raise ValueError("Forearm length must be greater than zero.")

        self._configuration = configuration

    def calculate(
            self,
            x: float,
            y: float,
            z: float,
    ) -> MotorAngles:
        """Compute servo commands for the requested Cartesian target."""

        configuration = self._configuration

        a1 = configuration.upper_arm_length_mm
        a2 = configuration.forearm_length_mm
        d1 = configuration.base_height_offset_mm

        theta_base_rad = math.atan2(y, x)
        theta_base_deg = math.degrees(theta_base_rad)

        r = math.sqrt(x ** 2 + y ** 2)
        z_relative = z - d1

        distance = math.sqrt(r ** 2 + z_relative ** 2)

        if distance > configuration.max_reach_mm:
            raise InverseKinematicsError(
                f"Target is outside the maximum reach "
                f"({configuration.max_reach_mm} mm). "
                f"Distance: {distance:.2f} mm"
            )

        if distance < configuration.min_reach_mm:
            raise InverseKinematicsError(
                f"Target is inside the minimum physical limit "
                f"({configuration.min_reach_mm} mm). "
                f"Distance: {distance:.2f} mm"
            )

        alpha_rad = math.atan2(-z_relative, r)

        cos_beta = distance / (2.0 * a1)
        cos_beta = clamp(cos_beta, -1.0, 1.0)

        beta_rad = math.acos(cos_beta)

        alpha_deg = math.degrees(alpha_rad)
        beta_deg = math.degrees(beta_rad)

        shoulder_angle_deg = alpha_deg - beta_deg
        elbow_angle_deg = alpha_deg + beta_deg

        calibrated_angles = self._apply_calibration(
            base_angle_deg=theta_base_deg,
            shoulder_angle_deg=shoulder_angle_deg,
            elbow_angle_deg=elbow_angle_deg,
        )

        logger.debug(
            "Calculated angles -> Base: %.2f°, Shoulder: %.2f°, Elbow: %.2f°",
            calibrated_angles.base,
            calibrated_angles.shoulder,
            calibrated_angles.elbow,
        )

        return calibrated_angles

    def _apply_calibration(
            self,
            base_angle_deg: float,
            shoulder_angle_deg: float,
            elbow_angle_deg: float,
    ) -> MotorAngles:
        """Apply servo calibration and limits."""

        calibration = self._configuration.calibration

        base_multiplier = -1.0 if calibration.base_inverted else 1.0
        shoulder_multiplier = -1.0 if calibration.shoulder_inverted else 1.0
        elbow_multiplier = -1.0 if calibration.elbow_inverted else 1.0

        base_angle = (
                calibration.base_ref_pwd
                + base_multiplier
                * (base_angle_deg - calibration.base_ref_deg)
        )

        shoulder_angle = (
                calibration.shoulder_ref_pwd
                + shoulder_multiplier
                * (
                        (shoulder_angle_deg - calibration.shoulder_ref_deg)
                        / calibration.shoulder_gain
                )
        )

        elbow_angle = (
                calibration.elbow_ref_pwd
                + elbow_multiplier
                * (
                        (elbow_angle_deg - calibration.elbow_ref_deg)
                        / calibration.elbow_gain
                )
        )

        base_angle = clamp(
            base_angle,
            self._configuration.base_servo_min_angle,
            self._configuration.base_servo_max_angle,
        )

        shoulder_angle = clamp(
            shoulder_angle,
            self._configuration.shoulder_servo_min_angle,
            self._configuration.shoulder_servo_max_angle,
        )

        elbow_angle = clamp(
            elbow_angle,
            self._configuration.elbow_servo_min_angle,
            self._configuration.elbow_servo_max_angle,
        )

        return MotorAngles(
            base=round(base_angle),
            shoulder=round(shoulder_angle),
            elbow=round(elbow_angle),
        )


# Init ---------------------------------------------------------------------- #


def parse_arguments(argv: Optional[list[str]] = None) -> tuple[Optional[float], Optional[float], Optional[float]]:
    parser = argparse.ArgumentParser(
        description="Compute servo angles for a given (X Y Z) target."
    )
    parser.add_argument("x", type=float, nargs="?",
                        help="Target X coordinate in mm")
    parser.add_argument("y", type=float, nargs="?",
                        help="Target Y coordinate in mm")
    parser.add_argument("z", type=float, nargs="?",
                        help="Target Z coordinate in mm")
    args = parser.parse_args(argv)
    return args.x, args.y, args.z


def main(argv: Optional[list[str]] = None) -> None:
    x_arg, y_arg, z_arg = parse_arguments(argv)

    settings_path = "config/settings.yaml"
    settings = _load_settings(settings_path)

    logging.basicConfig(
        level=getattr(logging, settings["logging"]["level"].upper(), logging.INFO)
    )

    kin_cfg = settings["motion"]["kinematics"]

    calib = JointCalibration(
        base_ref_deg=kin_cfg["base_ref_deg"],
        base_ref_pwd=kin_cfg["base_ref_pwd"],
        shoulder_ref_deg=kin_cfg["shoulder_ref_deg"],
        shoulder_ref_pwd=kin_cfg["shoulder_ref_pwd"],
        elbow_ref_deg=kin_cfg["elbow_ref_deg"],
        elbow_ref_pwd=kin_cfg["elbow_ref_pwd"],
        shoulder_gain=kin_cfg["shoulder_gain"],
        elbow_gain=kin_cfg["elbow_gain"],
        base_inverted=kin_cfg["base_inverted"],
        shoulder_inverted=kin_cfg["shoulder_inverted"],
        elbow_inverted=kin_cfg["elbow_inverted"],
    )

    arm_cfg = ArmConfiguration(
        upper_arm_length_mm=kin_cfg["upper_arm_length_mm"],
        forearm_length_mm=kin_cfg["forearm_length_mm"],
        base_height_offset_mm=kin_cfg["base_height_mm"],
        max_reach_mm=kin_cfg["max_reach_mm"],
        min_reach_mm=kin_cfg["min_reach_mm"],
        base_servo_min_angle=kin_cfg["base_servo_min_angle"],
        base_servo_max_angle=kin_cfg["base_servo_max_angle"],
        shoulder_servo_min_angle=kin_cfg["shoulder_servo_min_angle"],
        shoulder_servo_max_angle=kin_cfg["shoulder_servo_max_angle"],
        elbow_servo_min_angle=kin_cfg["elbow_servo_min_angle"],
        elbow_servo_max_angle=kin_cfg["elbow_servo_max_angle"],
        calibration=calib,
    )

    engine = RoboticArmKinematics(arm_cfg)

    # Determine the target coordinates (use workspace centre if not supplied)
    workspace = settings["motion"]["workspace"]
    x = x_arg if x_arg is not None else (workspace["x_min"] + workspace["x_max"]) / 2
    y = y_arg if y_arg is not None else (workspace["y_min"] + workspace["y_max"]) / 2
    z = z_arg if z_arg is not None else (workspace["z_min"] + workspace["z_max"]) / 2

    # Perform calculation
    try:
        angles = engine.calculate(x, y, z)
    except InverseKinematicsError as exc:
        logger.error(exc)
        exit(1)

    print(f"Target: X={x:.2f} mm, Y={y:.2f} mm, Z={z:.2f} mm")
    print(f"Base angle   : {angles.base}°")
    print(f"Shoulder angle: {angles.shoulder}°")
    print(f"Elbow angle   : {angles.elbow}°")


if __name__ == "__main__":
    main()
