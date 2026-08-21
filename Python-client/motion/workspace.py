
import math
import logging
from typing import Any
from motion.planner import CartesianPoint


# Global -------------------------------------------------------------------- #


logger = logging.getLogger(__name__)


# Classes ------------------------------------------------------------------- #


class WorkspaceValidationError(Exception):
    """Raised when a point is outside the configured workspace."""


class WorkspaceValidator:
    """Validate workspace boundaries and pickup zone constraints."""

    def __init__(self, config: Any) -> None:
        self._config = config

    def validate(self, point: CartesianPoint) -> None:
        """Validate a cartesian point against workspace rules."""

        if not self._config.enabled:
            logger.info("Workspace validation is disabled.")
            return

        self._validate_global_limits(point)
        self._validate_pickup_limits(point)

    def _validate_global_limits(self, point: CartesianPoint) -> None:
        """Validate global workspace boundaries."""

        if not self._config.x_min <= point.x <= self._config.x_max:
            logger.warning(
                f"Point X coordinate is outside workspace: {point.x}"
            )
            raise WorkspaceValidationError(
                f"X outside workspace: {point.x}"
            )

        if not self._config.y_min <= point.y <= self._config.y_max:
            logger.warning(
                f"Point Y coordinate is outside workspace: {point.y}"
            )
            raise WorkspaceValidationError(
                f"Y outside workspace: {point.y}"
            )

        if not self._config.z_min <= point.z <= self._config.z_max:
            logger.warning(
                f"Point Z coordinate is outside workspace: {point.z}"
            )
            raise WorkspaceValidationError(
                f"Z outside workspace: {point.z}"
            )

    def _validate_pickup_limits(self, point: CartesianPoint) -> None:
        """Validate pickup zone restrictions."""

        pickup_zone = self._config.pickup_zone

        if not pickup_zone.enabled:
            logger.info("Pickup zone validation is disabled.")
            return

        height_difference = abs(
            point.z - pickup_zone.activation_height_mm
        )

        if height_difference > pickup_zone.tolerance_mm:
            return

        radius = math.hypot(point.x, point.y)

        logger.warning(f"X: {point.x:.2f}, Y: {point.y:.2f}, Radius: {radius:.2f}")

        if radius < pickup_zone.min_radius_mm:
            logger.warning(
                f"Pickup radius is below the minimum limit: "
                f"{radius:.2f}"
            )
            raise WorkspaceValidationError(
                f"Pickup radius too small: {radius:.2f}"
            )

        if radius > pickup_zone.max_radius_mm:
            logger.warning(
                f"Pickup radius exceeds the maximum limit: "
                f"{radius:.2f}"
            )
            raise WorkspaceValidationError(
                f"Pickup radius too large: {radius:.2f}"
            )
