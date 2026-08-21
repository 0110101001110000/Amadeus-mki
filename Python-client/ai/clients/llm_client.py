"""
ai/clients/llm_client.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import logging
import tempfile
from pathlib import Path
from typing import Any, List
from dataclasses import dataclass

import cv2
import numpy as np

from vision.detector import Detection, BoundingBox
from ai.clients.vlm_client import (
    GradioConfig, GradioInferenceError, GradioVisionClient, InferenceRequest,
)


logger = logging.getLogger(__name__)


def _coerce_config_value(config: Any, key: str, default: Any = None) -> Any:
    """Read a configuration value from multiple config styles."""
    if config is None: return default
    if hasattr(config, key):
        value = getattr(config, key)
        return default if value is None else value
    if isinstance(config, dict):
        return config.get(key, default)
    return default


@dataclass(slots=True)
class LLMClientConfig:
    """Configuration wrapper for the LLM client."""
    server_url: str
    username: str
    password: str
    timeout: int = 60


class LLMClient:
    """Text and Vision adapter over the Gradio AI server with JSON parsing."""
    MAX_RETRIES = 5

    def __init__(self, config: Any) -> None:
        try:
            self._config = LLMClientConfig(
                server_url=_coerce_config_value(config, "server_url", ""),
                username=_coerce_config_value(config, "username", ""),
                password=_coerce_config_value(config, "password", ""),
                timeout=int(_coerce_config_value(config, "timeout", 60)),
            )
            if not self._config.server_url:
                raise ValueError("server_url is required for LLMClient.")

            gradio_config = GradioConfig(
                server_url=self._config.server_url,
                username=self._config.username,
                password=self._config.password,
                timeout=self._config.timeout,
            )
            self._client = GradioVisionClient(gradio_config)
            logger.info("LLM client initialized successfully.")
        except Exception:
            logger.exception("Unable to initialize LLM client.")
            sys.exit(1)

    def _extract_json_from_text(self, text: str) -> Any:
        """Extract the first JSON object or list from a string."""
        candidate = text.strip()

        # Remove markdown code blocks
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\n?|```$", "", candidate, flags=re.MULTILINE).strip()

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        # Regex fallback
        match = re.search(r"(\{.*\}|\[.*\])", candidate, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        raise ValueError("No valid JSON object found in model response.")

    def locate_target(self, frame: np.ndarray, target_label: str) -> list[Any] | None:
        """Requests the VLM to locate an object using a numpy frame and returns Detections."""
        prompt = (
            f"Detect all {target_label} in the image and return their locations in the form of coordinates. "
            "The format of output should be a valid JSON: [{'label': str, 'bbox': [x1,y1,x2,y2]}, ...]."
        )

        temp_path = None
        try:
            # Salva frame temporário para o client processar
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                temp_path = tmp.name

            cv2.imwrite(temp_path, frame)

            # Retry loop for model generation and JSON parsing
            for attempt in range(self.MAX_RETRIES + 1):
                try:
                    raw_response = self.generate_with_image(prompt, temp_path)
                    data = self._extract_json_from_text(raw_response)

                    # Normaliza resposta para lista
                    items = [data] if isinstance(data, dict) else (data if isinstance(data, list) else [])

                    detections = []
                    for item in items:
                        try:
                            bbox_coords = item.get("bbox", [])
                            if not isinstance(bbox_coords, list) or len(bbox_coords) != 4:
                                continue

                            bbox = BoundingBox(
                                x1=int(bbox_coords[0]),
                                y1=int(bbox_coords[1]),
                                x2=int(bbox_coords[2]),
                                y2=int(bbox_coords[3])
                            )
                            detections.append(Detection(
                                class_id=0,
                                class_name=item.get("label", target_label),
                                confidence=1.0,  # Confidence not explicitly requested in new prompt
                                bounding_box=bbox
                            ))
                        except (KeyError, ValueError, TypeError, IndexError):
                            continue

                    return detections

                except ValueError as ve:
                    logger.warning(
                        "Attempt %d/%d failed to parse JSON from VLM: %s. Retrying...",
                        attempt + 1, self.MAX_RETRIES + 1, ve
                    )
                    if attempt == self.MAX_RETRIES:
                        raise

        except Exception as e:
            logger.error("VLM localization failed after retries: %s", e)
            return []
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    def generate(self, prompt: str) -> str:
        """Generate a text response from the remote LLM."""
        try:
            response = self._client.send_inference(InferenceRequest(prompt=prompt))
            return response.text
        except GradioInferenceError:
            logger.exception("LLM inference failed.")
            raise

    def generate_with_image(self, prompt: str, image_path: str | Path) -> str:
        """Generate a multimodal response from the remote LLM."""
        try:
            response = self._client.send_inference(
                InferenceRequest(prompt=prompt, image_path=str(image_path)),
            )
            return response.text
        except GradioInferenceError:
            logger.exception("Multimodal LLM inference failed.")
            raise
