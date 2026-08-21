"""
communication/serial_client.py
"""

import sys
import time
import serial
import logging
import argparse
import threading
from typing import Callable, List
from serial.tools import list_ports
from serial.serialutil import SerialException


# Global -------------------------------------------------------------------- #


logger = logging.getLogger(__name__)


# Utils --------------------------------------------------------------------- #


def detect_arduino_port():
    """Try to automatically detect Arduino serial port."""
    ports = list_ports.comports()

    for port in ports:
        description = f"{port.description} {port.manufacturer}".lower()

        if (
            "arduino" in description or
            "ch340"   in description or
            "usb serial" in description
        ):
            logger.info(f"Arduino detected on {port.device}")
            return port.device

    return None


# Classes ------------------------------------------------------------------- #


class SerialClient:
    """
    Manages the physical serial connection, transmitting commands and listening
    for real-time feedback from the micro-controller via a background thread.
    """

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 1.0) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

        self.serial_connection = None
        self.running = False
        self.listener_thread = None

        # Thread-safe callback registration
        self._callbacks: List[Callable[[str], None]] = []
        self._lock = threading.Lock()

    def register_callback(self, callback: Callable[[str], None]) -> None:
        """
        Registers an external callback function to process incoming serial messages.
        """
        with self._lock:
            self._callbacks.append(callback)
            logger.debug(
                f"Registered callback: {callback.__name__ if hasattr(callback, '__name__') else str(callback)}")

    def connect(self) -> None:
        """Open serial connection."""
        try:
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )

            # Wait for Arduino reset
            time.sleep(2)

            self.running = True
            logger.info(f"Connected to {self.port} at {self.baudrate} baud.")

            self.listener_thread = threading.Thread(
                target=self.listen,
                daemon=True
            )
            self.listener_thread.start()

        except SerialException as error:
            logger.error(f"Failed to connect: {error}")
            sys.exit(1)

    def listen(self) -> None:
        """Continuously listen for incoming serial messages and trigger callbacks."""
        while self.running:
            try:
                if self.serial_connection and self.serial_connection.in_waiting > 0:
                    message = self.serial_connection.readline().decode(
                        "utf-8",
                        errors="ignore"
                    ).strip()

                    if message:
                        logger.info(f"[ARDUINO] {message}")

                        # Disseminate raw feedback to all listeners securely
                        with self._lock:
                            for callback in self._callbacks:
                                try:
                                    callback(message)
                                except Exception as cb_err:
                                    logger.exception(f"Error in serial callback: {cb_err}")

            except Exception:
                logger.exception("Read failure")
                self.running = False

            # Prevent high CPU consumption when idle
            time.sleep(0.01)

    def send(self, message: str) -> None:
        """
        Send a serialized message to the connected micro-controller.
        Execution block delay has been removed to allow reactive event-driven synchronization.
        """
        if not self.serial_connection or not self.serial_connection.is_open:
            logger.warning("Serial connection is not open. Unable to send command.")
            return

        try:
            clean_message = message.strip()
            payload = f"{clean_message}\n".encode("utf-8")
            self.serial_connection.write(payload)
            logger.debug(f"Sent: {clean_message}")

        except Exception as error:
            logger.error(f"Write failure: {error}")

    def disconnect(self) -> None:
        """Close serial connection safely."""
        self.running = False

        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()

        logger.info("Serial connection closed.")


# Init ---------------------------------------------------------------------- #


def main():
    parser = argparse.ArgumentParser(
        description="Python serial client for Arduino communication."
    )

    parser.add_argument(
        "--port",
        required=False,
        help="Serial port (example: COM3 or /dev/ttyUSB0)"
    )

    parser.add_argument(
        "--baudrate",
        type=int,
        default=9600,
        help="Communication baudrate"
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        help="Serial read timeout"
    )

    args = parser.parse_args()

    port = args.port

    if not port:
        port = detect_arduino_port()

    if not port:
        logger.warning("Arduino port not detected automatically.")
        port = input("Enter serial port manually: ").strip()

    client = SerialClient(
        port=port,
        baudrate=args.baudrate,
        timeout=args.timeout
    )

    client.connect()

    logger.info("Type messages to send to Arduino.")
    logger.info("Type 'exit' to close the program.")

    try:
        while True:
            user_input = input("> ").strip()

            if user_input.lower() == "exit":
                break

            if user_input:
                client.send(user_input)

    except KeyboardInterrupt:
        logger.info("\n Interrupted by user.")

    finally:
        client.disconnect()


if __name__ == '__main__':
    main()
