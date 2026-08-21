"""YOLO object detection module."""

from __future__ import annotations

import sys
import cv2
import logging
import argparse
import numpy as np
from typing import Any
from pathlib import Path
from ultralytics import YOLO
from dataclasses import dataclass


# Global -------------------------------------------------------------------- #


logger = logging.getLogger(__name__)


# Utils --------------------------------------------------------------------- #


def validate_model_path(model_path: str | Path) -> Path:
    """Validate YOLO model path."""

    resolved_path = Path(model_path).expanduser().resolve()

    if not resolved_path.exists():
        raise FileNotFoundError(
            f"YOLO model file not found: {resolved_path}"
        )

    if not resolved_path.is_file():
        raise ValueError(
            f"YOLO model path is not a valid file: {resolved_path}"
        )

    return resolved_path


# Classes ------------------------------------------------------------------- #


@dataclass(slots=True)
class BoundingBox:
    """Detected object bounding box."""

    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        """Return bounding box width."""

        return self.x2 - self.x1

    @property
    def height(self) -> int:
        """Return bounding box height."""

        return self.y2 - self.y1

    @property
    def center_x(self) -> int:
        """Return bounding box center X coordinate."""

        return (self.x1 + self.x2) // 2

    @property
    def center_y(self) -> int:
        """Return bounding box center Y coordinate."""

        return (self.y1 + self.y2) // 2


@dataclass(slots=True)
class Detection:
    """Detected object metadata."""

    class_id: int
    class_name: str
    confidence: float
    bounding_box: BoundingBox


class DetectorError(Exception):
    """Custom exception for detector-related errors."""


class YOLODetector:
    """YOLO object detection interface."""

    def __init__(
        self,
        model_path: str | Path,
        confidence_threshold: float = 0.4,
        iou_threshold: float = 0.45,
        device: str = "cpu",
    ) -> None:
        self._model_path: Path = validate_model_path(model_path)
        self._confidence_threshold: float = confidence_threshold
        self._iou_threshold: float = iou_threshold
        self._device: str = device

        self._model: YOLO | None = None

        self._load_model()

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Run object detection on a frame."""

        if frame is None:
            logger.warning("Received empty frame for detection.")
            return []

        if not isinstance(frame, np.ndarray):
            raise TypeError("Frame must be a numpy.ndarray instance.")

        try:
            logger.debug("Running YOLO inference.")

            results = self._model.predict(
                source=frame,
                conf=self._confidence_threshold,
                iou=self._iou_threshold,
                device=self._device,
                verbose=False,
            )

            detections = self._parse_results(results)

            logger.info(
                "Detection completed successfully. Objects detected: %s %s",
                len(detections), [i.class_name for i in detections],
            )

            return detections

        except Exception as error:
            logger.exception("YOLO inference failed: %s", error)
            raise DetectorError("Object detection failed.") from error

    def _load_model(self) -> None:
        """Load YOLO model safely."""

        try:
            logger.info(
                "Loading YOLO model from: %s",
                self._model_path,
            )

            self._model = YOLO(str(self._model_path))

            logger.info("YOLO model loaded successfully.")

        except Exception as error:
            logger.exception("Failed to load YOLO model: %s", error)
            raise DetectorError("Unable to load YOLO model.") from error

    def _parse_results(self, results: list[Any]) -> list[Detection]:
        """Parse YOLO inference results."""

        detections: list[Detection] = []

        try:
            for result in results:
                boxes = result.boxes

                if boxes is None:
                    continue

                for box in boxes:
                    class_id = int(box.cls[0].item())
                    confidence = float(box.conf[0].item())

                    coordinates = box.xyxy[0].cpu().numpy().astype(int)

                    x1, y1, x2, y2 = coordinates.tolist()

                    class_name = result.names.get(class_id, "unknown")

                    bounding_box = BoundingBox(
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                    )

                    detection = Detection(
                        class_id=class_id,
                        class_name=class_name,
                        confidence=confidence,
                        bounding_box=bounding_box,
                    )

                    detections.append(detection)

            return detections

        except Exception as error:
            logger.exception("Failed to parse YOLO results: %s", error)
            raise DetectorError("Failed to parse inference results.") from error

    def draw_detections(
        self,
        frame: np.ndarray,
        detections: list[Detection],
    ) -> np.ndarray:
        """Draw detections on frame."""

        annotated_frame = frame.copy()

        try:
            for detection in detections:
                bounding_box = detection.bounding_box

                cv2.rectangle(
                    annotated_frame,
                    (bounding_box.x1, bounding_box.y1),
                    (bounding_box.x2, bounding_box.y2),
                    (0, 255, 0),
                    2,
                )

                label = (
                    f"{detection.class_name} "
                    f"{detection.confidence:.2f}"
                )

                cv2.putText(
                    annotated_frame,
                    label,
                    (bounding_box.x1, bounding_box.y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2,
                )

            return annotated_frame

        except Exception as error:
            logger.exception("Failed to draw detections: %s", error)
            raise DetectorError("Unable to annotate detections.") from error


# Main ---------------------------------------------------------------------- #


def main() -> None:
    """Run standalone YOLO detector test."""

    parser = argparse.ArgumentParser(
        description="YOLO object detector module."
    )

    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Path to YOLO model weights.",
    )

    parser.add_argument(
        "--image",
        type=str,
        required=True,
        help="Path to input image.",
    )

    parser.add_argument(
        "--confidence",
        type=float,
        default=0.4,
        help="Confidence threshold.",
    )

    parser.add_argument(
        "--iou",
        type=float,
        default=0.45,
        help="IOU threshold.",
    )

    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Inference device.",
    )

    args = parser.parse_args()

    try:
        image_path = Path(args.image).expanduser().resolve()

        if not image_path.exists():
            raise FileNotFoundError(
                f"Input image not found: {image_path}"
            )

        frame = cv2.imread(str(image_path))

        if frame is None:
            raise ValueError(
                f"Failed to load image: {image_path}"
            )

        detector = YOLODetector(
            model_path=args.model,
            confidence_threshold=args.confidence,
            iou_threshold=args.iou,
            device=args.device,
        )

        detections = detector.detect(frame)

        logger.info("Detected objects summary:")

        for index, detection in enumerate(detections, start=1):
            bounding_box = detection.bounding_box

            logger.info(
                "[%s] class=%s confidence=%.2f center=(%s,%s)",
                index,
                detection.class_name,
                detection.confidence,
                bounding_box.center_x,
                bounding_box.center_y,
            )

        annotated_frame = detector.draw_detections(
            frame,
            detections,
        )

        cv2.imshow("YOLO Detection", annotated_frame)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    except Exception as error:
        logger.exception("Critical detector runtime failure: %s", error)
        sys.exit(1)

if __name__ == "__main__":
    main()
