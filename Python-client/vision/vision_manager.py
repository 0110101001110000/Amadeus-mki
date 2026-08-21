
import cv2
import math
import yaml
import logging
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from ai.clients.llm_client import LLMClient
from typing import List, Optional, Dict, Any
from config.config import VisionConfig, VLMConfig
from vision.segmentation import MobileSAMSegmenter
from vision.refined_detection import RefinedDetection
from vision.calibration import CalibrationEngine, WorldCoordinate
from vision.bbox_refiner import refine_detection, expand_bounding_box
from vision.camera import Camera, CameraError, validate_camera_source
from vision.detector import YOLODetector, DetectorError, Detection, validate_model_path


# Global -------------------------------------------------------------------- #


logger = logging.getLogger(__name__)


# Classes ------------------------------------------------------------------- #


@dataclass(frozen=True)
class LocalizedTarget:
    """Combines object detection metadata with absolute world spatial coordinates."""
    detection: Detection
    world_coordinate: WorldCoordinate


class VisionManager:
    """Manages camera lifecycle, processes visual frames, and calculates targets in 3D space."""

    def __init__(self, config: VisionConfig, llm_config: VLMConfig) -> None:
        self._config = config
        self._llm_config = llm_config

        self._camera: Optional[Camera] = None
        self._detector: Optional[YOLODetector] = None
        self._calibration_engine: Optional[CalibrationEngine] = None

        self._workspace_transform: Optional[Dict[str, Any]] = None
        self._window_opened: bool = True

        self._last_frame: Optional[np.ndarray] = None
        self._current_detections: List[Detection] = []

        self._status_labels: Dict[str, str] = {}

        self._window_opened: bool = True

        self._llm_client: Optional[LLMClient] = None

        self._segmenter: Optional[MobileSAMSegmenter] = None
        self._current_masks: List[np.ndarray] = []
        self._current_refined_detections: List[RefinedDetection] = []

    def initialize(self) -> bool:
        """Instantiates visual perception modules, loading weights and calibration files.

        Returns:
            bool: True if initialization was fully successful, False otherwise.
        """
        try:
            # Initialize Camera Source
            source = validate_camera_source(self._config.camera.device_index)
            self._camera = Camera(
                source=source,
                width=self._config.camera.frame_width,
                height=self._config.camera.frame_height,
                fps=self._config.camera.fps
            )

            self._camera.register_display_callback(
                self._render_live_feed
            )

            # Initialize Model Detector
            validated_model = validate_model_path(self._config.detector.model_path)
            self._detector = YOLODetector(
                model_path=validated_model,
                confidence_threshold=self._config.detector.confidence_threshold,
                iou_threshold=self._config.detector.iou_threshold
            )

            if self._llm_config:
                self._llm_client = LLMClient(self._llm_config)
            else:
                logger.error("VLM configuration missing in settings.yaml")
                return False

            # Initialize Calibration Engine
            calib_path = Path(self._config.calibration_file_path)
            if not calib_path.exists():
                logger.error(f"Calibration file not found: {calib_path}")
                return False

            self._calibration_engine = CalibrationEngine.from_yaml(calib_path)

            # Inicialize Segmenter model
            if self._config.segmentation.enabled:
                self._segmenter = MobileSAMSegmenter(
                    checkpoint_path=self._config.segmentation.checkpoint_path,
                    device=self._config.segmentation.device
                )

                logger.info("MobileSAM refinement enabled.")

            # Load required 3D Workspace Transform
            transform_path = Path(self._config.transform_file_path)
            if not transform_path.exists():
                logger.error(f"Workspace transform calibration file not found: {transform_path}")
                return False

            try:
                with transform_path.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                self._workspace_transform = data.get("workspace_transform")
                if not self._workspace_transform:
                    logger.error("Workspace transform data is missing the 'workspace_transform' root key.")
                    return False
                logger.info(f"Loaded 3D workspace transform from: {transform_path}")
            except Exception as e:
                logger.error(f"Failed to read or parse workspace transform file: {e}")
                return False

            logger.info("Vision Manager modules initialized successfully.")
            return True

        except (CameraError, DetectorError, FileNotFoundError, ValueError) as e:
            logger.error(f"Vision Manager failed during initialization step: {e}")
            return False

    def start_capture(self) -> None:
        """Starts the background camera frame acquisition thread."""
        if self._camera and not self._camera.is_running:
            logger.info("Starting background camera feed thread.")
            self._camera.start()
        else:
            logger.warning("Camera thread already running – start_capture() ignored.")

    def stop_capture(self, destroy_window: bool = True) -> None:
        """Stops the camera frame acquisition thread and releases system resources."""
        if self._camera and self._camera.is_running:
            logger.info("Stopping camera feed thread.")
            self._camera.stop()

        if destroy_window and self._config.live_detection_window:
            cv2.destroyAllWindows()

    def enable_processing(self) -> None:
        """Enables visual frame acquisition."""

        if self._camera:
            self._camera.enable_capture()

    def disable_processing(self) -> None:
        """Disables visual frame acquisition."""

        if self._camera:
            self._camera.disable_capture()

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Fetches the most recent frame acquired from the camera cache."""
        if not self._camera:
            return None

        frame = self._camera.read()

        if frame is not None:
            self._last_frame = frame

        return self._last_frame

    def process_and_localize(self, frame: np.ndarray, target_z_plane: float = 0.0) -> List[LocalizedTarget]:
        """Analyzes a frame, filters target classes, and computes their coordinates relative to the Robot Base.

        Args:
            frame: Raw OpenCV frame array to analyze.
            target_z_plane: Real-world surface plane height constraint (z) of target objects.

        Returns:
            List[LocalizedTarget]: Complete list of targets located in 3D workspace.
        """
        if self._detector is None or self._calibration_engine is None:
            logger.error("Inference or spatial engines are uninitialized.")
            return []

        localized_targets: List[LocalizedTarget] = []

        try:
            detections = self._detector.detect(frame)

            self._last_frame = frame
            self._current_detections = detections

            filtered_detections = [
                d for d in detections if d.class_name in self._config.detector.target_labels
            ]

            for detection in filtered_detections:
                bbox = detection.bounding_box

                # Correct image lens distortion
                undistorted_x, undistorted_y = self._calibration_engine.undistort_pixel(
                    pixel_x=float(bbox.center_x),
                    pixel_y=float(bbox.center_y)
                )

                # Project 2D coordinates to 3D Calibration World Space
                calib_coord = self._calibration_engine.pixel_to_world(
                    pixel_x=undistorted_x,
                    pixel_y=undistorted_y,
                    plane_z=target_z_plane
                )

                # Transform Coordinate Frame (Calibration Frame -> Robot Frame)
                robot_coord = self._transform_to_robot_frame(calib_coord)

                robot_coord = self._apply_tool_offset(robot_coord, offset_mm=self._config.tool.offset_x_mm)

                localized_targets.append(LocalizedTarget(detection=detection, world_coordinate=robot_coord))

        except DetectorError as e:
            logger.error(f"Inference error during target localization: {e}")

        return localized_targets

    def vlm_process_and_localize(self, frame: np.ndarray, target_label: str, target_z_plane: float = 0.0) -> List[
        LocalizedTarget]:
        """Uses VLM to find specific objects and projects them to 3D space."""
        if not self._llm_client:
            logger.error("LLMClient (VLM) not initialized.")
            return []

        detections = self._llm_client.locate_target(frame, target_label)
        self._current_detections = detections

        self._current_masks.clear()
        self._current_refined_detections.clear()

        localized_targets: List[LocalizedTarget] = []

        for det in detections:
            bbox = det.bounding_box

            height, width = frame.shape[:2]

            x1, y1, x2, y2 = expand_bounding_box(
                x1=bbox.x1,
                y1=bbox.y1,
                x2=bbox.x2,
                y2=bbox.y2,
                image_width=width,
                image_height=height,
                expansion_factor=0.25
            )

            mask = self._segmenter.segment(
                image=frame,
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2
            )

            refined = refine_detection(
                detection=det,
                mask=mask
            )

            if refined is None:
                logger.warning("Refinement failed. Falling back to VLM bounding box.")

                center_x = bbox.center_x
                center_y = bbox.center_y

            else:
                center_x = refined.center_x
                center_y = refined.center_y

                self._current_masks.append(mask)
                self._current_refined_detections.append(refined)

            # Spatial Projection
            undist_x, undist_y = self._calibration_engine.undistort_pixel(float(center_x), float(center_y))
            calib_coord = self._calibration_engine.pixel_to_world(undist_x, undist_y, target_z_plane)

            robot_coord = self._transform_to_robot_frame(calib_coord)

            compensated_robot_coord = self._apply_tool_offset(robot_coord, offset_mm=self._config.tool.offset_x_mm)

            logger.debug(
                "Target compensated from %s to %s",
                robot_coord,
                compensated_robot_coord,
            )

            localized_targets.append(LocalizedTarget(detection=det, world_coordinate=compensated_robot_coord))

        return localized_targets

    def update_status(self, state: str, camera: str, detection: str) -> None:
        """Updates live status labels displayed in the camera window.

        Args:
            state:
                Current FSM state.

            camera:
                Camera acquisition status.

            detection:
                Object detection status.
        """

        self._status_labels = {
            "State": state,
            "Camera": camera,
            "Detection": detection
        }

    def _transform_to_robot_frame(self, calib_coord: WorldCoordinate) -> WorldCoordinate:
        """Applies 3D translation and rotation matrices to map coordinates to the Robot Base Frame."""
        if self._workspace_transform is None:
            logger.error("Workspace transform is uninitialized. Cannot map coordinate.")
            raise ValueError("Workspace transform is uninitialized.")

        try:
            R = np.array(self._workspace_transform["rotation_matrix"], dtype=np.float64)
            t = np.array(self._workspace_transform["translation_vector"], dtype=np.float64).reshape(3, 1)

            P_vision = np.array([[calib_coord.x], [calib_coord.y], [calib_coord.z]], dtype=np.float64)

            P_robot = np.dot(R, P_vision) + t

            return WorldCoordinate(
                x=float(P_robot[0, 0]),
                y=float(P_robot[1, 0]),
                z=float(P_robot[2, 0])
            )
        except Exception as e:
            logger.error(f"Mathematical projection failed during transform matrix operation: {e}")
            raise

    def _apply_tool_offset(
            self,
            coord: WorldCoordinate,
            offset_mm: float,
    ) -> WorldCoordinate:

        radial_distance = math.sqrt(
            coord.x ** 2 +
            coord.y ** 2
        )

        if radial_distance <= offset_mm:
            return coord

        ux = coord.x / radial_distance
        uy = coord.y / radial_distance

        return WorldCoordinate(
            x=coord.x - ux * offset_mm,
            y=coord.y - uy * offset_mm,
            z=coord.z
        )

    def _render_live_feed(self, frame: Optional[np.ndarray]) -> None:
        """Renders the live camera window.

        The window remains active during the entire application
        lifecycle. When frame acquisition is disabled, the last
        cached frame remains visible while system statuses continue
        to be updated.

        Args:
            frame:
                Latest cached camera frame.
        """

        if not self._config.live_detection_window:
            return

        if not self._window_opened:
            return

        if frame is None:
            return

        annotated_frame = frame.copy()
        annotated_frame = self._draw_segmentation_overlay(annotated_frame)

        if self._detector is not None:
            annotated_frame = self._detector.draw_detections(
                annotated_frame,
                self._current_detections
            )

        y_position = 25

        for key, value in self._status_labels.items():
            cv2.putText(
                annotated_frame,
                f"{key}: {value}",
                (10, y_position),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

            y_position += 25

        cv2.imshow(
            "AMADEUS MK-I Live Detection",
            annotated_frame
        )

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            self._window_opened = False

            cv2.destroyAllWindows()

    def _draw_segmentation_overlay(self, frame: np.ndarray) -> np.ndarray:
        """
        Draws MobileSAM refinement results over the current frame.
        """

        if (
                not self._current_masks
                or not self._current_refined_detections
        ):
            return frame

        try:
            overlay = frame.copy()

            for mask in self._current_masks:
                overlay[mask > 0] = (
                    0,
                    255,
                    0
                )

            result = cv2.addWeighted(
                overlay,
                0.30,
                frame,
                0.70,
                0
            )

            for refined in self._current_refined_detections:
                cv2.rectangle(
                    result,
                    (
                        refined.x1,
                        refined.y1
                    ),
                    (
                        refined.x2,
                        refined.y2
                    ),
                    (
                        0,
                        255,
                        0
                    ),
                    2
                )

                cv2.circle(
                    result,
                    (
                        int(refined.center_x),
                        int(refined.center_y)
                    ),
                    4,
                    (
                        255,
                        0,
                        0
                    ),
                    -1
                )

            return result

        except Exception:
            logger.exception("Failed to render segmentation overlay.")
            return frame
