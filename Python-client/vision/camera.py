"""Camera interface module for continuous video capture."""

from __future__ import annotations

import sys
import cv2
import time
import logging
import argparse
import threading
import numpy as np
from typing import Optional, Callable


# Global -------------------------------------------------------------------- #


logger = logging.getLogger(__name__)


# Utils --------------------------------------------------------------------- #


def validate_camera_source(source: int | str) -> int | str:
    """Validate and normalize camera source."""

    if isinstance(source, int):
        if source < 0:
            raise ValueError("Camera index must be greater than or equal to zero.")

        return source

    if isinstance(source, str):
        if not source.strip():
            raise ValueError("Camera source string cannot be empty.")

        return source.strip()

    raise TypeError("Camera source must be an integer or string.")


# Classes ------------------------------------------------------------------- #


class CameraError(Exception):
    """Custom exception for camera-related errors."""


class Camera:
    """Continuous camera capture interface."""

    def __init__(
        self,
        source: int | str = 0,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        backend: Optional[int] = None,
        reconnect_delay: float = 2.0,
    ) -> None:
        self._source: int | str = validate_camera_source(source)
        self._width: int = width
        self._height: int = height
        self._fps: int = fps
        self._backend: Optional[int] = backend
        self._reconnect_delay: float = reconnect_delay

        self._capture: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()

        self._running: bool = False
        self._thread: Optional[threading.Thread] = None

        self._capture_enabled: bool = False

        self._display_callback: Optional[
            Callable[[Optional[np.ndarray]], None]
        ] = None

        logger.info(
            "Camera initialized with source=%s resolution=%sx%s fps=%s",
            self._source,
            self._width,
            self._height,
            self._fps,
        )

    @property
    def is_running(self) -> bool:
        """Return current camera running state."""

        return self._running

    @property
    def capture_enabled(self) -> bool:
        """Indicates whether new frames are being acquired."""
        return self._capture_enabled

    def enable_capture(self) -> None:
        """Enables continuous frame acquisition."""

        self._capture_enabled = True

    def disable_capture(self) -> None:
        """Disables frame acquisition while preserving the last frame."""

        self._capture_enabled = False

    def register_display_callback(
            self,
            callback: Callable[[Optional[np.ndarray]], None]
    ) -> None:
        """Registers a callback executed every camera loop iteration.

        The callback receives the latest cached frame. It is executed
        regardless of whether frame acquisition is currently enabled.

        Args:
            callback:
                Function responsible for rendering the live window.
        """

        self._display_callback = callback

    def start(self) -> None:
        """Start continuous frame capture."""

        if self._running:
            logger.warning("Camera capture thread is already running.")
            return

        self._initialize_capture()

        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="CameraCaptureThread",
            daemon=True,
        )

        self._thread.start()

        logger.info("Camera capture thread started successfully.")

    def stop(self) -> None:
        """Stop continuous frame capture."""

        if not self._running:
            logger.warning("Camera capture thread is not running.")
            return

        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        self._release_capture()

        logger.info("Camera capture stopped successfully.")

    def read(self) -> Optional[np.ndarray]:
        """Return the latest captured frame."""

        with self._frame_lock:
            if self._frame is None:
                return None

            return self._frame.copy()

    def _initialize_capture(self) -> None:
        """Initialize OpenCV video capture."""

        try:
            if self._backend is not None:
                self._capture = cv2.VideoCapture(self._source, self._backend)
            else:
                self._capture = cv2.VideoCapture(self._source)

            if not self._capture.isOpened():
                raise CameraError(
                    f"Failed to open camera source: {self._source}"
                )

            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            self._capture.set(cv2.CAP_PROP_FPS, self._fps)
            self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            logger.info("Camera source opened successfully.")

        except Exception as error:
            logger.exception("Camera initialization failed: %s", error)
            raise CameraError("Unable to initialize camera capture.") from error

    def _release_capture(self) -> None:
        """Release camera resources safely."""

        try:
            if self._capture is not None:
                self._capture.release()
                self._capture = None

                logger.info("Camera resources released successfully.")

        except Exception as error:
            logger.exception("Failed to release camera resources: %s", error)

    def _capture_loop(self) -> None:
        """Background frame capture loop."""

        logger.info("Camera capture loop started.")

        while self._running:
            if self._capture_enabled:
                try:
                    if self._capture is None or not self._capture.isOpened():
                        logger.warning("Camera capture is unavailable. Attempting reconnection.")

                        self._reconnect()
                        continue

                    success, frame = self._capture.read()

                    if success and frame is not None:
                        with self._frame_lock:
                            self._frame = frame

                except Exception as error:
                    logger.exception("Unexpected error during frame capture: %s", error)

            if self._display_callback is not None:
                try:
                    self._display_callback(
                        self.read()
                    )

                except Exception as error:
                    logger.warning(
                        "Display callback failed: %s",
                        error
                    )

            time.sleep(0.01)

        logger.info("Camera capture loop terminated.")

    def _reconnect(self) -> None:
        """Reconnect camera source safely."""

        try:
            self._release_capture()

            logger.info(
                "Attempting camera reconnection in %.2f seconds.",
                self._reconnect_delay,
            )

            time.sleep(self._reconnect_delay)

            self._initialize_capture()

            logger.info("Camera reconnection successful.")

        except Exception as error:
            logger.error("Camera reconnection failed: %s", error)
            time.sleep(self._reconnect_delay)


# Main ---------------------------------------------------------------------- #


def main() -> None:
    """Run standalone camera interface test."""

    parser = argparse.ArgumentParser(
        description="Continuous camera capture interface."
    )

    parser.add_argument(
        "--source",
        type=int,
        default=0,
        help="Camera source index.",
    )

    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="Capture frame width.",
    )

    parser.add_argument(
        "--height",
        type=int,
        default=720,
        help="Capture frame height.",
    )

    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="Capture frames per second.",
    )

    args = parser.parse_args()

    camera = Camera(
        source=args.source,
        width=args.width,
        height=args.height,
        fps=args.fps,
    )

    try:
        camera.start()

        logger.info("Press CTRL+C to stop camera capture.")

        while True:
            frame = camera.read()

            if frame is None:
                time.sleep(0.01)
                continue

            cv2.imshow("Live Camera Feed", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            time.sleep(0.01)

    except KeyboardInterrupt:
        logger.info("Shutdown signal received.")

    except Exception as error:
        logger.exception("Critical camera runtime failure: %s", error)
        sys.exit(1)

    finally:
        camera.stop()

if __name__ == "__main__":
    main()
