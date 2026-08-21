"""
Trajectory planning module for the robotic arm.
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass
from typing import List, Optional
from motion.kinematics import RoboticArmKinematics, InverseKinematicsError


# Global -------------------------------------------------------------------- #


logger = logging.getLogger(__name__)


# Utils --------------------------------------------------------------------- #


def calculate_euclidean_distance(point_a: CartesianPoint, point_b: CartesianPoint) -> float:
    """
    Calculates the Euclidean distance between two Cartesian points in 3D space.
    """
    return math.sqrt(
        (point_a.x - point_b.x) ** 2 +
        (point_a.y - point_b.y) ** 2 +
        (point_a.z - point_b.z) ** 2
    )


def remove_consecutive_duplicates(points: List[CartesianPoint]) -> List[CartesianPoint]:
    """
    Filters out consecutive duplicate coordinates to prevent redundant arm movements.
    """
    if not points:
        return []

    filtered = [points[0]]
    for point in points[1:]:
        if point != filtered[-1]:
            filtered.append(point)
    return filtered


# Classes ------------------------------------------------------------------- #


@dataclass(frozen=True)
class CartesianPoint:
    """Represents a 3D coordinate in the robot's workspace."""
    x: float
    y: float
    z: float


class TrajectoryPlanningError(Exception):
    """Raised when a trajectory path cannot be safely planned or validated."""
    pass


@dataclass(frozen=True)
class PlannerConfig:
    """Configuration parameters for the trajectory planner."""
    home_position: CartesianPoint
    safe_z_coordinate: Optional[float] = None


class TrajectoryPlanner:
    """
    Generates and validates safe trajectory waypoints for the robotic arm.
    """

    def __init__(self, kinematics: RoboticArmKinematics, config: PlannerConfig) -> None:
        """
        Initializes the TrajectoryPlanner.

        :param kinematics: Kinematics engine to validate waypoint reachability.
        :param config: Configuration containing default positions and constraints.
        """
        self._kinematics = kinematics
        self._config = config
        logger.info("TrajectoryPlanner initialized successfully.")

    def plan_trajectory(self, start: CartesianPoint, target: CartesianPoint) -> List[CartesianPoint]:
        """
        Generates a list of Cartesian waypoints from a start position to a target.
        The default pathway is defined as: start -> home (base) -> target.

        :param start: The current Cartesian position of the end-effector.
        :param target: The desired destination Cartesian position.
        :return: A filtered list of reachable CartesianPoint waypoints.
        :raises TrajectoryPlanningError: If any waypoint is unreachable.
        """
        logger.debug(f"Planning trajectory from {start} to {target}.")
        raw_waypoints: List[CartesianPoint] = []

        try:
            # Add current position as starting waypoint
            raw_waypoints.append(start)

            # Add transition to home/base position
            #raw_waypoints.append(self._config.home_position)

            # Add target position
            raw_waypoints.append(target)

            # Remove redundant transitions (e.g., if start is already at home)
            waypoints = remove_consecutive_duplicates(raw_waypoints)

            # Validate structural integrity and physical feasibility
            self._validate_waypoints(waypoints)

            logger.debug(f"Trajectory planned with {len(waypoints)} valid waypoints.")
            return waypoints

        except InverseKinematicsError as e:
            logger.error(f"Trajectory planning aborted. One or more points are out of reach: {e}")
            raise TrajectoryPlanningError(f"Kinematic validation failed for trajectory: {e}") from e

        except Exception as e:
            logger.exception(f"Unexpected error during trajectory planning execution: {e}")
            raise TrajectoryPlanningError(f"Unexpected planning error: {e}") from e

    def _validate_waypoints(self, waypoints: List[CartesianPoint]) -> None:
        """
        Verifies if all waypoints are within the physical range of the robotic arm.

        :param waypoints: List of points to validate.
        :raises InverseKinematicsError: If a point is geometrically unreachable.
        """
        for index, point in enumerate(waypoints):
            try:
                # Perform an inverse kinematics check to ensure reachability
                self._kinematics.calculate(point.x, point.y, point.z)
                logger.debug(f"Waypoint {index} {point} validated successfully.")
            except InverseKinematicsError as e:
                logger.warning(f"Unreachable waypoint detected at index {index} {point}: {e}")
                raise


# Main ---------------------------------------------------------------------- #


# ...
