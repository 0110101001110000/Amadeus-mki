"""
vision/bbox_refiner.py
"""

from __future__ import annotations

import cv2
import logging
import numpy as np
from typing import Optional, Tuple
from vision.detector import Detection
from vision.refined_detection import RefinedDetection


# Global -------------------------------------------------------------------- #


logger = logging.getLogger(__name__)


# Utils --------------------------------------------------------------------- #


def refine_detection(detection: Detection, mask: np.ndarray) -> Optional[RefinedDetection]:
    """
    Converts a segmentation mask into a refined detection.
    """

    try:

        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return None

        contour = max(contours, key=cv2.contourArea)

        rect = cv2.minAreaRect(contour)

        (cx, cy), _, angle = rect

        points = cv2.boxPoints(rect)

        points = np.int32(points)

        x, y, w, h = cv2.boundingRect(points)

        return RefinedDetection(
            original_detection=detection,
            mask=mask,
            center_x=float(cx),
            center_y=float(cy),
            x1=x,
            y1=y,
            x2=x + w,
            y2=y + h,
            angle=float(angle)
        )

    except Exception:
        logger.exception("Bounding box refinement failed.")
        return None


def expand_bounding_box(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    image_width: int,
    image_height: int,
    expansion_factor: float = 0.20
) -> Tuple[int, int, int, int]:
    """
    Expands a bounding box while respecting image boundaries.
    """

    width = x2 - x1
    height = y2 - y1

    expand_x = int(width * expansion_factor)
    expand_y = int(height * expansion_factor)

    new_x1 = max(0, x1 - expand_x)
    new_y1 = max(0, y1 - expand_y)

    new_x2 = min(
        image_width - 1,
        x2 + expand_x
    )

    new_y2 = min(
        image_height - 1,
        y2 + expand_y
    )

    return (
        new_x1,
        new_y1,
        new_x2,
        new_y2
    )
