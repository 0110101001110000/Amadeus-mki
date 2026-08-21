"""
vision/segmentation.py
"""

from __future__ import annotations

import sys
import cv2
import logging
import numpy as np
from pathlib import Path
from mobile_sam import SamPredictor
from mobile_sam import sam_model_registry


# Global -------------------------------------------------------------------- #


logger = logging.getLogger(__name__)


# Classes ------------------------------------------------------------------- #


class MobileSAMSegmenter:
    """Handles object segmentation using MobileSAM."""

    def __init__(self, checkpoint_path: str, device: str = "cuda") -> None:

        self._device = device

        try:
            checkpoint = Path(checkpoint_path)

            if not checkpoint.exists():
                logger.error(f"MobileSAM checkpoint not found: {checkpoint}")
                sys.exit(1)

            model = sam_model_registry["vit_t"](checkpoint=str(checkpoint))

            model.to(device)

            self._predictor = SamPredictor(model)

            logger.info("MobileSAM initialized successfully.")

        except Exception:
            logger.exception("Failed to initialize MobileSAM.")
            sys.exit(1)

    def segment(self, image: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
        """
        Applies post-processing operations to the segmentation mask.
        """

        try:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            self._predictor.set_image(rgb)

            input_box = np.array([x1, y1, x2, y2])

            masks, _, _ = self._predictor.predict(
                point_coords=None,
                point_labels=None,
                box=input_box[None, :],
                multimask_output=False
            )

            mask = masks[0].astype(np.uint8)

            mask = self._keep_largest_component(mask)

            return mask

        except Exception:
            logger.exception("MobileSAM segmentation failed.")
            raise

    def _keep_largest_component(self, mask: np.ndarray) -> np.ndarray:
        """
        Keeps only the largest connected component of a binary mask.
        """

        try:

            binary_mask = mask.astype(np.uint8)

            num_labels, labels, stats, _ = (
                cv2.connectedComponentsWithStats(
                    binary_mask,
                    connectivity=8
                )
            )

            if num_labels <= 1:
                return binary_mask

            largest_label = (
                    1 +
                    np.argmax(
                        stats[
                            1:,
                            cv2.CC_STAT_AREA
                        ]
                    )
            )

            filtered_mask = (
                    labels == largest_label
            ).astype(
                np.uint8
            )

            logger.debug(
                "Connected components found: %d",
                num_labels - 1
            )

            logger.debug(
                "Largest component area: %d pixels",
                stats[
                    largest_label,
                    cv2.CC_STAT_AREA
                ]
            )

            return filtered_mask

        except Exception:
            logger.exception("Failed to filter connected components.")

            return mask
