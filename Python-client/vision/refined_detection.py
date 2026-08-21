"""
vision/refined_detection.py
"""

from __future__ import annotations

import logging
import numpy as np
from dataclasses import dataclass
from vision.detector import Detection


# Global -------------------------------------------------------------------- #


logger = logging.getLogger(__name__)


# Classes ------------------------------------------------------------------- #


@dataclass(frozen=True)
class RefinedDetection:
    """Stores refined object localization."""

    original_detection: Detection
    mask: np.ndarray

    center_x: float
    center_y: float

    x1: int
    y1: int
    x2: int
    y2: int

    angle: float
