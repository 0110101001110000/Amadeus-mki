"""
Spatial calibration and coordinate mapping module.

This module converts image pixel coordinates into real-world coordinates
using intrinsic and extrinsic camera calibration parameters.
"""

from __future__ import annotations

import cv2
import sys
import yaml
import logging
import argparse
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple


# Global -------------------------------------------------------------------- #


logger = logging.getLogger(__name__)


# Utils --------------------------------------------------------------------- #


def configure_logging(level: int = logging.INFO) -> None:
    """Configure global logging."""

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def load_yaml_file(file_path: Path) -> dict:
    """Load YAML configuration file."""

    try:
        with file_path.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file)

    except FileNotFoundError:
        logger.exception(f"Calibration file not found: {file_path}")
        sys.exit(1)

    except yaml.YAMLError:
        logger.exception(f"Invalid YAML format in: {file_path}")
        sys.exit(1)

    except Exception:
        logger.exception("Unexpected error while loading YAML file")
        sys.exit(1)


def validate_matrix_shape(
    matrix: np.ndarray,
    expected_shape: Tuple[int, int],
    matrix_name: str,
) -> None:
    """Validate matrix dimensions."""

    if matrix.shape != expected_shape:
        logger.error(
            f"{matrix_name} must have shape {expected_shape}, "
            f"but received {matrix.shape}"
        )
        sys.exit(1)


# Classes ------------------------------------------------------------------- #


@dataclass(frozen=True)
class CameraIntrinsics:
    """Camera intrinsic parameters."""

    camera_matrix: np.ndarray
    distortion_coefficients: np.ndarray


@dataclass(frozen=True)
class CameraExtrinsics:
    """Camera extrinsic parameters."""

    rotation_matrix: np.ndarray
    translation_vector: np.ndarray


@dataclass(frozen=True)
class WorldCoordinate:
    """3D world coordinate."""

    x: float
    y: float
    z: float


class CalibrationEngine:
    """
    Handles camera calibration and spatial coordinate transformation.
    """

    def __init__(
        self,
        intrinsics: CameraIntrinsics,
        extrinsics: CameraExtrinsics,
    ) -> None:
        self._intrinsics = intrinsics
        self._extrinsics = extrinsics

        self._validate_parameters()

        logger.info("Calibration engine initialized successfully")

    @classmethod
    def from_yaml(cls, calibration_file: Path) -> "CalibrationEngine":
        """Create calibration engine from YAML configuration."""

        logger.info(f"Loading calibration file: {calibration_file}")

        data = load_yaml_file(calibration_file)

        try:
            camera_matrix = np.array(
                data["intrinsics"]["camera_matrix"],
                dtype=np.float64,
            )

            distortion_coefficients = np.array(
                data["intrinsics"]["distortion_coefficients"],
                dtype=np.float64,
            )

            rotation_matrix = np.array(
                data["extrinsics"]["rotation_matrix"],
                dtype=np.float64,
            )

            translation_vector = np.array(
                data["extrinsics"]["translation_vector"],
                dtype=np.float64,
            )

        except KeyError as error:
            logger.exception(f"Missing calibration parameter: {error}")
            sys.exit(1)

        intrinsics = CameraIntrinsics(
            camera_matrix=camera_matrix,
            distortion_coefficients=distortion_coefficients,
        )

        extrinsics = CameraExtrinsics(
            rotation_matrix=rotation_matrix,
            translation_vector=translation_vector,
        )

        return cls(
            intrinsics=intrinsics,
            extrinsics=extrinsics,
        )

    def undistort_pixel(
            self,
            pixel_x: float,
            pixel_y: float,
    ) -> Tuple[float, float]:
        """
        Remove lens distortion from image pixel.
        """

        points = np.array([[[pixel_x, pixel_y]]], dtype=np.float32)

        try:
            undistorted = cv2.undistortPoints(
                points,
                self._intrinsics.camera_matrix,
                self._intrinsics.distortion_coefficients,
                P=self._intrinsics.camera_matrix,
            )

            x_coord = float(undistorted[0][0][0])
            y_coord = float(undistorted[0][0][1])

            logger.debug(
                f"Undistorted pixel ({pixel_x}, {pixel_y}) "
                f"-> ({x_coord}, {y_coord})"
            )

            return x_coord, y_coord

        except Exception:
            logger.exception("Failed to undistort pixel")
            raise

    def pixel_to_world(
            self,
            pixel_x: float,
            pixel_y: float,
            plane_z: float = 0.0,
    ) -> WorldCoordinate:
        """
        Convert image pixel coordinates to world coordinates.

        Assumes object lies on a known Z plane.
        """

        logger.debug(
            f"Converting pixel coordinates "
            f"({pixel_x}, {pixel_y}) to world coordinates"
        )

        try:
            undistorted_x, undistorted_y = self.undistort_pixel(
                pixel_x,
                pixel_y,
            )

            image_point = np.array(
                [undistorted_x, undistorted_y, 1.0],
                dtype=np.float64,
            )

            camera_matrix_inv = np.linalg.inv(
                self._intrinsics.camera_matrix
            )

            normalized_camera_point = camera_matrix_inv @ image_point

            rotation_inv = np.linalg.inv(
                self._extrinsics.rotation_matrix
            )

            translation = self._extrinsics.translation_vector.reshape(3)

            scale = (
                            plane_z + (
                            rotation_inv @ translation
                    )[2]
                    ) / (
                            rotation_inv @ normalized_camera_point
                    )[2]

            world_point = rotation_inv @ (
                    scale * normalized_camera_point - translation
            )

            coordinate = WorldCoordinate(
                x=float(world_point[0]),
                y=float(world_point[1]),
                z=float(plane_z),
            )

            logger.debug(f"World coordinate computed: {coordinate}")

            return coordinate

        except np.linalg.LinAlgError:
            logger.exception("Linear algebra error during transformation")
            raise

        except Exception:
            logger.exception("Failed to convert pixel to world coordinates")
            raise

    def _validate_parameters(self) -> None:
        """Validate calibration matrices."""

        validate_matrix_shape(
            self._intrinsics.camera_matrix,
            (3, 3),
            "camera_matrix",
        )

        validate_matrix_shape(
            self._extrinsics.rotation_matrix,
            (3, 3),
            "rotation_matrix",
        )

        translation_shape = self._extrinsics.translation_vector.shape

        valid_translation_shapes = [(3,), (3, 1)]

        if translation_shape not in valid_translation_shapes:
            logger.error(
                "translation_vector must have shape "
                "(3,) or (3, 1)"
            )
            sys.exit(1)

        logger.info("Calibration parameters validated successfully")


# Main ---------------------------------------------------------------------- #


def parse_arguments() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Pixel to world coordinate converter"
    )

    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to calibration YAML file",
    )

    parser.add_argument(
        "--pixel-x",
        type=float,
        required=True,
        help="Pixel X coordinate",
    )

    parser.add_argument(
        "--pixel-y",
        type=float,
        required=True,
        help="Pixel Y coordinate",
    )

    parser.add_argument(
        "--plane-z",
        type=float,
        default=0.0,
        help="World Z plane value",
    )

    return parser.parse_args()


def main() -> None:
    """Application entrypoint."""

    configure_logging()

    args = parse_arguments()

    try:
        calibration_engine = CalibrationEngine.from_yaml(
            args.config
        )

        world_coordinate = calibration_engine.pixel_to_world(
            pixel_x=args.pixel_x,
            pixel_y=args.pixel_y,
            plane_z=args.plane_z,
        )

        logger.info(
            f"World Coordinate -> "
            f"X={world_coordinate.x:.3f}, "
            f"Y={world_coordinate.y:.3f}, "
            f"Z={world_coordinate.z:.3f}"
        )

    except Exception:
        logger.exception("Application failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

