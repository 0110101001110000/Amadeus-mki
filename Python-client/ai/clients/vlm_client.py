"""
Production-ready Gradio client for AI integrations.
"""

from __future__ import annotations

import logging
import sys
from typing import Any
from pathlib import Path
from dataclasses import dataclass, field
from gradio_client import Client, handle_file


# Global -------------------------------------------------------------------- #


logger = logging.getLogger(__name__)


# Utils --------------------------------------------------------------------- #


def _validate_optional_file(file_path: str | Path | None) -> Any:
    """Validate and prepare a file for Gradio upload."""

    if file_path is None:
        return None

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    return handle_file(str(path))


def _extract_text_from_history(history: list[dict[str, Any]]) -> str:
    """Extract the latest textual response from Gradio history."""

    if not history:
        return ""

    for message in reversed(history):
        contents = message.get("content", [])

        for content in contents:
            if content.get("type") == "text":
                return content.get("text", "")

    return ""


# Classes ------------------------------------------------------------------- #


class GradioClientError(Exception):
    """Base exception for Gradio client errors."""


class GradioConnectionError(GradioClientError):
    """Raised when the client cannot connect to the server."""


class GradioInferenceError(GradioClientError):
    """Raised when an inference request fails."""


@dataclass(slots=True)
class ChatMessage:
    """Simple chat message representation."""

    role: str
    content: str


@dataclass(slots=True)
class GradioConfig:
    """Gradio server configuration."""

    server_url: str
    username: str
    password: str
    timeout: int = 60


@dataclass(slots=True)
class InferenceRequest:
    """Inference request payload."""

    prompt: str
    image_path: str | Path | None = None
    audio_path: str | Path | None = None
    video_path: str | Path | None = None


@dataclass(slots=True)
class InferenceResponse:
    """Structured inference response."""

    text: str
    history: list[ChatMessage] = field(default_factory=list)
    raw_response: Any = None


class GradioVisionClient:
    """Encapsulates all communication with the Gradio AI server."""

    def __init__(self, config: GradioConfig) -> None:
        self._config = config
        self._client: Client | None = None
        self._history: list[dict[str, Any]] = []

        self._connect()

    @property
    def history(self) -> list[dict[str, Any]]:
        """Return a copy of the internal history."""

        return list(self._history)

    def clear_history(self) -> None:
        """Reset conversation history."""

        logger.info("Clearing conversation history.")
        self._history.clear()

    def _connect(self) -> None:
        """Connect to the Gradio server."""

        try:
            logger.info("Connecting to Gradio server: %s", self._config.server_url)

            self._client = Client(
                src=self._config.server_url,
                auth=(
                    self._config.username,
                    self._config.password,
                ),
            )

            logger.info("Gradio connection established.")

        except Exception as exc:
            logger.exception("Unable to connect to Gradio server.")
            raise GradioConnectionError(str(exc)) from exc

    def health_check(self) -> bool:
        """Verify server availability."""

        if self._client is None:
            logger.error("Client not initialized.")
            return False

        try:
            logger.info("Performing Gradio health check.")

            self._client.predict(
                api_name="/lambda",
            )

            logger.info("Gradio server is available.")
            return True

        except Exception:
            logger.exception("Health check failed.")
            return False

    def send_inference(self, request: InferenceRequest) -> InferenceResponse:
        """Execute a multimodal inference request."""

        if self._client is None:
            raise GradioConnectionError("Gradio client is not connected.")

        try:
            logger.debug("Preparing inference request.")

            image = _validate_optional_file(request.image_path)
            audio = _validate_optional_file(request.audio_path)
            video = _validate_optional_file(request.video_path)

            logger.debug("Sending inference request.")

            result = self._client.predict(
                prompt=request.prompt,
                image_file=image,
                audio_file=audio,
                video_file=video,
                history=self._history,
                api_name="/handle_inference",
            )

            if not isinstance(result, list):
                raise GradioInferenceError("Unexpected response format.")

            self._history = result

            response = InferenceResponse(
                text=_extract_text_from_history(result),
                history=self._convert_history(result),
                raw_response=result,
            )

            logger.debug("Inference completed successfully.")
            return response

        except FileNotFoundError:
            logger.exception("Invalid file path.")
            raise
        except Exception as exc:
            logger.exception("Inference request failed.")
            raise GradioInferenceError(str(exc)) from exc

    def _convert_history(self, history: list[dict[str, Any]]) -> list[ChatMessage]:
        """Convert Gradio history into internal DTOs."""

        messages: list[ChatMessage] = []

        for item in history:
            role = item.get("role", "unknown")
            contents = item.get("content", [])

            for content in contents:
                if content.get("type") == "text":
                    messages.append(
                        ChatMessage(
                            role=role,
                            content=content.get("text", ""),
                        )
                    )

        return messages


# Init ---------------------------------------------------------------------- #


def build_gradio_client(config: GradioConfig) -> GradioVisionClient:
    """Factory helper."""

    try:
        client = GradioVisionClient(config)

        if not client.health_check():
            logger.error("Gradio server health check failed.")
            sys.exit(1)

        return client

    except Exception:
        logger.exception("Critical failure during Gradio client initialization.")
        sys.exit(1)
