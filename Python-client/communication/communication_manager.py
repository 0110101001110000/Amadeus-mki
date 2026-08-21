
import time
import logging
from config.config import SerialConfig
from typing import Callable, List, Optional
from communication.serial_client import SerialClient, detect_arduino_port
from motion.controller import parse_arduino_message, ArduinoFeedback

logger = logging.getLogger(__name__)


class CommunicationManager:
    """Coordinates serial connection lifecycle, auto-detection, and feedback routing."""

    def __init__(self, config: SerialConfig) -> None:
        self._config = config
        self._client: Optional[SerialClient] = None
        self._listeners: List[Callable[[ArduinoFeedback], None]] = []

    def initialize(self) -> bool:
        """Determines the target port and initializes the underlying SerialClient.

        Returns:
            bool: True if initialization was successful, False otherwise.
        """
        if not self._config.enabled:
            logger.info("Serial communication is disabled by configuration.")
            return False

        target_port = self._config.port
        if not target_port:
            logger.info("Serial port not specified. Scanning for compatible devices...")
            target_port = detect_arduino_port()

            if not target_port:
                logger.error("No compatible serial devices detected.")
                return False
            logger.info(f"Auto-detected device on port: {target_port}")

        self._client = SerialClient(
            port=target_port,
            baudrate=self._config.baudrate,
            timeout=self._config.timeout_seconds
        )
        self._client.register_callback(self._on_raw_message_received)
        return True

    def connect_with_retry(self) -> bool:
        """Attempts to establish a connection with the device, retrying on failure.

        Returns:
            bool: True if connection is established, False otherwise.
        """
        if not self._client:
            logger.error("CommunicationManager must be initialized before connecting.")
            return False

        attempts = self._config.reconnection_attempts
        delay = self._config.reconnect_interval_seconds

        for attempt in range(1, attempts + 1):
            try:
                logger.info(f"Connecting to serial device (Attempt {attempt}/{attempts})...")
                self._client.connect()
                logger.info("Serial connection established successfully.")
                return True
            except Exception as e:
                logger.warning(f"Connection attempt {attempt} failed: {e}")
                if attempt < attempts:
                    logger.info(f"Waiting {delay} seconds before retrying...")
                    time.sleep(delay)

        logger.error("Failed to establish serial connection after maximum attempts.")
        return False

    def register_feedback_listener(self, listener: Callable[[ArduinoFeedback], None]) -> None:
        """Registers a callback to receive parsed Arduino feedback."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def send_message(self, serialized_message: str) -> None:
        """Transmits a pre-serialized protocol string to the hardware."""
        if not self._client or not self._client.running:
            logger.warning("Attempted to send message but serial client is not active.")
            return

        try:
            self._client.send(serialized_message)
        except Exception as e:
            logger.error(f"Error transmitting serial message: {e}")

    def disconnect(self) -> None:
        """Gracefully disconnects the serial connection and cleans up resources."""
        if self._client:
            logger.info("Disconnecting serial client...")
            try:
                self._client.disconnect()
                logger.info("Serial client disconnected.")
            except Exception as e:
                logger.error(f"Error during disconnection: {e}")

    def _on_raw_message_received(self, raw_message: str) -> None:
        """Internal callback invoked when raw data is received on the serial thread."""
        parsed_feedback = parse_arduino_message(raw_message)
        if parsed_feedback is None:
            logger.debug(f"Ignored or failed to parse serial message: {raw_message}")
            return

        self._dispatch_feedback(parsed_feedback)

    def _dispatch_feedback(self, feedback: ArduinoFeedback) -> None:
        """Dispatches parsed feedback to all registered system listeners."""
        for listener in self._listeners:
            try:
                listener(feedback)
            except Exception as e:
                logger.error(f"Error in registered feedback listener {listener.__name__}: {e}")