"""
Calibration dataset generation script for AMADEUS MK-I Client.

This module processes chessboard calibration images to estimate:
- Camera intrinsics
- Lens distortion coefficients
- Camera extrinsics

The generated calibration parameters are exported to:
vision/calibration_data.yaml
"""

from __future__ import annotations

import sys
import cv2
import yaml
import logging
import argparse
import numpy as np
from pathlib import Path
from typing import List, Tuple


# Global -------------------------------------------------------------------- #


logger = logging.getLogger(__name__)


# Utils --------------------------------------------------------------------- #


def setup_logging(log_level: str) -> None:
    """Configure application logging."""

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def create_object_points(
    chessboard_size: Tuple[int, int],
    square_size: float,
) -> np.ndarray:
    """
    Generate real-world chessboard coordinates.

    Args:
        chessboard_size: Number of internal corners (columns, rows).
        square_size: Physical square size in millimeters.

    Returns:
        Object points array.
    """

    object_points = np.zeros(
        (chessboard_size[0] * chessboard_size[1], 3),
        np.float32,
    )

    object_points[:, :2] = np.mgrid[
        0 : chessboard_size[0],
        0 : chessboard_size[1],
    ].T.reshape(-1, 2)

    object_points *= square_size

    return object_points


def save_calibration_yaml(
    output_path: Path,
    camera_matrix: np.ndarray,
    distortion_coefficients: np.ndarray,
    rotation_matrix: np.ndarray,
    translation_vector: np.ndarray,
) -> None:
    """
    Save calibration parameters to YAML file.

    Args:
        output_path: Output YAML file path.
        camera_matrix: Intrinsic camera matrix.
        distortion_coefficients: Lens distortion coefficients.
        rotation_matrix: Extrinsic rotation matrix.
        translation_vector: Extrinsic translation vector.
    """

    calibration_data = {
        "intrinsics": {
            "camera_matrix": camera_matrix.tolist(),
            "distortion_coefficients": distortion_coefficients.tolist(),
        },
        "extrinsics": {
            "rotation_matrix": rotation_matrix.tolist(),
            "translation_vector": translation_vector.tolist(),
        },
    }

    try:
        with output_path.open("w", encoding="utf-8") as yaml_file:
            yaml.dump(
                calibration_data,
                yaml_file,
                sort_keys=False,
                default_flow_style=False,
            )

        logger.info(f"Calibration data saved to: {output_path}")

    except Exception:
        logger.exception("Failed to save calibration YAML file.")
        raise


def scale_camera_matrix(
    camera_matrix: np.ndarray,
    original_size: Tuple[int, int],
    target_size: Tuple[int, int],
) -> np.ndarray:
    """
    Scale intrinsic camera matrix to a target resolution.

    Args:
        camera_matrix: Original intrinsic matrix.
        original_size: Calibration image resolution (width, height).
        target_size: Target runtime resolution (width, height).

    Returns:
        Scaled intrinsic matrix.
    """

    original_width, original_height = original_size
    target_width, target_height = target_size

    scale_x = target_width / original_width
    scale_y = target_height / original_height

    scaled_matrix = camera_matrix.copy()

    scaled_matrix[0, 0] *= scale_x  # fx
    scaled_matrix[1, 1] *= scale_y  # fy
    scaled_matrix[0, 2] *= scale_x  # cx
    scaled_matrix[1, 2] *= scale_y  # cy

    return scaled_matrix


# Classes ------------------------------------------------------------------- #


class CameraCalibrator:
    """Handles camera calibration pipeline."""

    def __init__(
        self,
        images_directory: Path,
        output_file: Path,
        chessboard_width: int,
        chessboard_height: int,
        square_size: float,
        target_width: int | None,
        target_height: int | None,
    ) -> None:
        """
        Initialize calibration pipeline.

        Args:
            images_directory: Directory containing calibration images.
            output_file: Output YAML file.
            chessboard_width: Number of internal corners horizontally.
            chessboard_height: Number of internal corners vertically.
            square_size: Chessboard square size in millimeters.
        """

        self.images_directory = images_directory
        self.output_file = output_file
        self.chessboard_size = (
            chessboard_width,
            chessboard_height,
        )
        self.square_size = square_size

        self.object_points_list: List[np.ndarray] = []
        self.image_points_list: List[np.ndarray] = []

        self.object_template = create_object_points(
            chessboard_size=self.chessboard_size,
            square_size=self.square_size,
        )

        self.target_width = target_width
        self.target_height = target_height

    def _load_image_paths(self) -> List[Path]:
        """
        Load calibration image paths.

        Returns:
            List of image paths.
        """

        supported_extensions = ("*.png", "*.jpg", "*.jpeg", "*.bmp")

        image_paths: List[Path] = []

        for extension in supported_extensions:
            image_paths.extend(
                self.images_directory.glob(extension)
            )

        image_paths = sorted(image_paths)

        if not image_paths:
            logger.error(
                f"No calibration images found in: "
                f"{self.images_directory}"
            )
            sys.exit(1)

        logger.info(
            f"Found {len(image_paths)} calibration images."
        )

        return image_paths

    def _process_image(
        self,
        image_path: Path,
    ) -> Tuple[bool, np.ndarray | None]:
        """
        Detect chessboard corners in image.

        Args:
            image_path: Path to image.

        Returns:
            Tuple containing detection status and grayscale image.
        """

        try:
            image = cv2.imread(str(image_path))

            if image is None:
                logger.warning(
                    f"Failed to load image: {image_path}"
                )
                return False, None

            grayscale_image = cv2.cvtColor(
                image,
                cv2.COLOR_BGR2GRAY,
            )

            detection_success, corners = cv2.findChessboardCorners(
                grayscale_image,
                self.chessboard_size,
                None,
            )

            if not detection_success:
                logger.warning(
                    f"Chessboard not detected in: {image_path.name}"
                )
                return False, grayscale_image

            refinement_criteria = (
                cv2.TERM_CRITERIA_EPS
                + cv2.TERM_CRITERIA_MAX_ITER,
                30,
                0.001,
            )

            refined_corners = cv2.cornerSubPix(
                grayscale_image,
                corners,
                (11, 11),
                (-1, -1),
                refinement_criteria,
            )

            self.object_points_list.append(
                self.object_template
            )

            self.image_points_list.append(
                refined_corners
            )

            logger.info(
                f"Chessboard detected successfully: "
                f"{image_path.name}"
            )

            return True, grayscale_image

        except Exception:
            logger.exception(
                f"Error while processing image: {image_path}"
            )
            return False, None

    def calibrate(self) -> None:
        """Execute full calibration pipeline."""

        image_paths = self._load_image_paths()

        image_size: Tuple[int, int] | None = None

        for image_path in image_paths:
            success, grayscale_image = self._process_image(
                image_path=image_path,
            )

            if success and grayscale_image is not None:
                image_size = grayscale_image.shape[::-1]

        if not self.object_points_list:
            logger.error(
                "No valid chessboard detections found."
            )
            sys.exit(1)

        if image_size is None:
            logger.error(
                "Failed to determine image resolution."
            )
            sys.exit(1)

        try:
            logger.info("Starting camera calibration...")

            (
                reprojection_error,
                camera_matrix,
                distortion_coefficients,
                rotation_vectors,
                translation_vectors,
            ) = cv2.calibrateCamera(
                self.object_points_list,
                self.image_points_list,
                image_size,
                None,
                None,
            )

            if (
                    self.target_width is not None
                    and self.target_height is not None
            ):
                logger.info(
                    "Scaling intrinsic matrix from "
                    f"{image_size} to "
                    f"({self.target_width}, {self.target_height})"
                )

                camera_matrix = scale_camera_matrix(
                    camera_matrix=camera_matrix,
                    original_size=image_size,
                    target_size=(
                        self.target_width,
                        self.target_height,
                    ),
                )

            logger.info(
                f"Calibration completed with reprojection "
                f"error: {reprojection_error:.6f}"
            )

            rotation_matrix, _ = cv2.Rodrigues(
                rotation_vectors[0]
            )

            translation_vector = translation_vectors[0]

            save_calibration_yaml(
                output_path=self.output_file,
                camera_matrix=camera_matrix,
                distortion_coefficients=distortion_coefficients,
                rotation_matrix=rotation_matrix,
                translation_vector=translation_vector,
            )

        except Exception:
            logger.exception(
                "Camera calibration process failed."
            )
            sys.exit(1)


# Main ---------------------------------------------------------------------- #


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Generate camera calibration parameters "
            "from chessboard images."
        )
    )

    parser.add_argument(
        "--images-dir",
        type=Path,
        default=Path("calibration_images/"),
        help="Directory containing calibration images.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("calibration_data.yaml"),
        help="Output YAML calibration file.",
    )

    parser.add_argument(
        "--chessboard-width",
        type=int,
        default=9,
        help="Number of internal chessboard corners horizontally.",
    )

    parser.add_argument(
        "--chessboard-height",
        type=int,
        default=6,
        help="Number of internal chessboard corners vertically.",
    )

    parser.add_argument(
        "--square-size",
        type=float,
        default=16.0,
        help="Chessboard square size in millimeters.",
    )

    parser.add_argument(
        "--target-width",
        type=int,
        default=640,
        help=(
            "Target operating resolution width. "
            "If provided together with --target-height, "
            "the intrinsic matrix will be scaled."
        ),
    )

    parser.add_argument(
        "--target-height",
        type=int,
        default=480,
        help=(
            "Target operating resolution height. "
            "If provided together with --target-width, "
            "the intrinsic matrix will be scaled."
        ),
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=[
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        ],
        help="Logging verbosity level.",
    )

    return parser.parse_args()


def main() -> None:
    """Application entrypoint."""

    arguments = parse_arguments()

    setup_logging(arguments.log_level)

    logger.info("Initializing camera calibration pipeline.")

    try:
        calibrator = CameraCalibrator(
            images_directory=arguments.images_dir,
            output_file=arguments.output,
            chessboard_width=arguments.chessboard_width,
            chessboard_height=arguments.chessboard_height,
            square_size=arguments.square_size,
            target_width=arguments.target_width,
            target_height=arguments.target_height,
        )

        calibrator.calibrate()

        logger.info(
            "Camera calibration pipeline completed successfully."
        )

    except KeyboardInterrupt:
        logger.warning(
            "Calibration interrupted by user."
        )
        sys.exit(1)

    except Exception:
        logger.exception(
            "Unexpected fatal error during calibration."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
