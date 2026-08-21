"""
Workspace Calibration Script for AMADEUS MK-I Client.

This script establishes a coordinate transformation mapping between the
Camera/Vision frame (CalibrationEngine) and the Robot Arm's physical frame.
It uses an SVD-based rigid registration (Kabsch algorithm) based on N points.
"""

from __future__ import annotations

import sys
import cv2
import time
import yaml
import logging
import argparse
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
try:
    from vision.camera import Camera
    from motion.planner import CartesianPoint
    from communication.protocol import ProtocolBuilder, GripState
    from motion.controller import MotionController, ControllerConfig
    from vision.calibration import CalibrationEngine, WorldCoordinate
    from communication.serial_client import SerialClient, detect_arduino_port
    from motion.kinematics import RoboticArmKinematics, ArmConfiguration, MotorAngles, JointCalibration
except ImportError:
    # Fallback to absolute paths or standard relative layout if run from root
    sys.path.append(str(Path(__file__).resolve().parent))
    from communication.serial_client import SerialClient
    from communication.protocol import ProtocolBuilder, GripState
    from vision.camera import Camera
    from vision.calibration import CalibrationEngine, WorldCoordinate
    from motion.kinematics import RoboticArmKinematics, ArmConfiguration, MotorAngles
    from motion.controller import MotionController, ControllerConfig
    from motion.planner import CartesianPoint


# Logger setup
logger = logging.getLogger("workspace_calibrator")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

clicked_pixel: Optional[Tuple[int, int]] = None


def click_callback(event: int, x: int, y: int, flags: int, param: Any) -> None:
    """Handle mouse clicks on the video frame for manual landmark identification."""
    global clicked_pixel
    if event == cv2.EVENT_LBUTTONDOWN:
        clicked_pixel = (x, y)
        logger.info(f"Manual pixel marked at: {clicked_pixel}")


def estimate_rigid_transform_3d(A: np.ndarray, B: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Finds the optimal rotation R and translation t such that: B = R * A + t
    Using Singular Value Decomposition (SVD).

    Args:
        A: N x 3 matrix of source points (Vision coordinate space)
        B: N x 3 matrix of target points (Robot physical coordinate space)

    Returns:
        R: 3 x 3 Rotation matrix
        t: 3 x 1 Translation vector
        rmse: Root Mean Square Error of the alignment
    """
    assert A.shape == B.shape
    num_rows, num_cols = A.shape

    # 1. Find centroids
    centroid_A = np.mean(A, axis=0)
    centroid_B = np.mean(B, axis=0)

    # 2. Center the points
    Am = A - centroid_A
    Bm = B - centroid_B

    # 3. Covariance matrix
    H = np.dot(Am.T, Bm)

    # 4. SVD factorization
    U, S, Vt = np.linalg.svd(H)

    # 5. Determine Rotation matrix
    R = np.dot(Vt.T, U.T)

    # Handle reflection case
    if np.linalg.det(R) < 0:
        logger.warning("Reflection detected in SVD calculation. Correcting...")
        Vt[2, :] *= -1
        R = np.dot(Vt.T, U.T)

    # 6. Determine Translation vector
    t = centroid_B.T - np.dot(R, centroid_A.T)
    t = t.reshape(3, 1)

    # Calculate RMSE
    A_transformed = (np.dot(R, A.T) + t).T
    err = B - A_transformed
    rmse = np.sqrt(np.mean(np.sum(err ** 2, axis=1)))

    return R, t, float(rmse)


class WorkspaceCalibrator:
    """Manages automation cycle to map vision space coordinates into kinematics space."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.config = self._load_config()

        # Load Vision Calibration Engine
        calib_file = Path("calibration_data.yaml")
        if not calib_file.exists():
            raise FileNotFoundError(
                f"Camera calibration file not found at: {calib_file}. "
                "Run camera_calibrator.py first."
            )
        self.calibration_engine = CalibrationEngine.from_yaml(calib_file)

        # Initialize Hardware & Kinematics
        self.serial_client = self._init_serial()
        self.kinematics = self._init_kinematics()
        self.controller = self._init_controller()

        # Camera
        cam_cfg = self.config["vision"]["camera"]
        self.camera = Camera(
            source=cam_cfg["device_index"],
            width=cam_cfg["frame_width"],
            height=cam_cfg["frame_height"],
            fps=cam_cfg["fps"]
        )

        # HSV calibration target properties (Default calibration marker: Bright Green)
        self.hsv_min = np.array([35, 50, 50])
        self.hsv_max = np.array([85, 255, 255])

    def _load_config(self) -> Dict[str, Any]:
        with self.config_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _init_serial(self) -> SerialClient:
        comm_cfg = self.config["communication"]["serial"]
        port = comm_cfg["port"]
        if not port:
            detected = detect_arduino_port()
            if detected:
                port = detected
                logger.info(f"Auto-detected hardware port: {port}")
            else:
                raise ConnectionError("No serial port specified and auto-detection failed.")

        client = SerialClient(
            port=port,
            baudrate=comm_cfg["baudrate"],
            timeout=comm_cfg["timeout_seconds"]
        )
        client.connect()
        return client

    def _init_kinematics(self) -> RoboticArmKinematics:
        k_cfg = self.config["motion"]["kinematics"]

        joint_calibration_config = JointCalibration(
            base_ref_deg=k_cfg["base_ref_deg"],
            base_ref_pwd=k_cfg["base_ref_pwd"],
            shoulder_ref_deg=k_cfg["shoulder_ref_deg"],
            shoulder_ref_pwd=k_cfg["shoulder_ref_pwd"],
            elbow_ref_deg=k_cfg["elbow_ref_deg"],
            elbow_ref_pwd=k_cfg["elbow_ref_pwd"],
            shoulder_gain=k_cfg["shoulder_gain"],
            elbow_gain=k_cfg["elbow_gain"],
            base_inverted=k_cfg["base_inverted"],
            shoulder_inverted=k_cfg["shoulder_inverted"],
            elbow_inverted=k_cfg["elbow_inverted"],
        )

        config = ArmConfiguration(
            upper_arm_length_mm=k_cfg["upper_arm_length_mm"],
            forearm_length_mm=k_cfg["forearm_length_mm"],
            base_height_offset_mm=k_cfg["base_height_mm"],
            max_reach_mm=k_cfg["max_reach_mm"],
            min_reach_mm=k_cfg["min_reach_mm"],
            base_servo_min_angle=k_cfg["base_servo_min_angle"],
            base_servo_max_angle=k_cfg["base_servo_max_angle"],
            shoulder_servo_min_angle=k_cfg["shoulder_servo_min_angle"],
            shoulder_servo_max_angle=k_cfg["shoulder_servo_max_angle"],
            elbow_servo_min_angle=k_cfg["elbow_servo_min_angle"],
            elbow_servo_max_angle=k_cfg["elbow_servo_max_angle"],
            calibration=joint_calibration_config,
        )

        return RoboticArmKinematics(config)

    def _init_controller(self) -> MotionController:
        m_cfg = self.config["motion"]
        joints = m_cfg["joints"]
        controller_config = ControllerConfig(
            max_speed=joints["max_speed_deg_per_sec"],
            min_speed=joints["min_speed_deg_per_sec"],
        )
        return MotionController(
            kinematics=self.kinematics,
            serial_client=self.serial_client,
            config=controller_config
        )

    def detect_colored_marker(self, frame: np.ndarray) -> Optional[Tuple[int, int]]:
        """Identify the end-effector coordinate via HSV color masking."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.hsv_min, self.hsv_max)

        # Apply basic noise cleaning operations
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest_contour) > 50:  # Noise constraint threshold
                M = cv2.moments(largest_contour)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    return cx, cy
        return None

    def setup_marker_color(self) -> None:
        """Helper visual environment to tune the HSV range for marker detection."""
        logger.info("Starting HSV setup. Use trackbars to capture the marker color. Press 'q' when ready.")
        cv2.namedWindow("HSV Tuning")
        cv2.createTrackbar("H_Min", "HSV Tuning", self.hsv_min[0], 180, lambda x: None)
        cv2.createTrackbar("S_Min", "HSV Tuning", self.hsv_min[1], 255, lambda x: None)
        cv2.createTrackbar("V_Min", "HSV Tuning", self.hsv_min[2], 255, lambda x: None)
        cv2.createTrackbar("H_Max", "HSV Tuning", self.hsv_max[0], 180, lambda x: None)
        cv2.createTrackbar("S_Max", "HSV Tuning", self.hsv_max[1], 255, lambda x: None)
        cv2.createTrackbar("V_Max", "HSV Tuning", self.hsv_max[2], 255, lambda x: None)

        while True:
            frame = self.camera.read()
            if frame is None:
                continue

            h_min = cv2.getTrackbarPos("H_Min", "HSV Tuning")
            s_min = cv2.getTrackbarPos("S_Min", "HSV Tuning")
            v_min = cv2.getTrackbarPos("V_Min", "HSV Tuning")
            h_max = cv2.getTrackbarPos("H_Max", "HSV Tuning")
            s_max = cv2.getTrackbarPos("S_Max", "HSV Tuning")
            v_max = cv2.getTrackbarPos("V_Max", "HSV Tuning")

            self.hsv_min = np.array([h_min, s_min, v_min])
            self.hsv_max = np.array([h_max, s_max, v_max])

            # Apply and render mask
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, self.hsv_min, self.hsv_max)
            result = cv2.bitwise_and(frame, frame, mask=mask)

            marker_pos = self.detect_colored_marker(frame)
            if marker_pos:
                cv2.circle(result, marker_pos, 8, (0, 0, 255), -1)

            cv2.imshow("HSV Tuning", result)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cv2.destroyWindow("HSV Tuning")

    def run_calibration(self) -> None:
        """Executes calibration workflow moving through predefined points."""
        global clicked_pixel
        self.camera.start()
        time.sleep(1.0)  # Settle camera connection
        self.camera.enable_capture()

        # Ask to configure color
        tune_hsv = input("Tune target marker HSV thresholds? (y/n): ").strip().lower()
        if tune_hsv == 'y':
            self.setup_marker_color()

        # Generate a set of calibration points (distributed in workspace)
        # Based on limits in settings.yaml: x: (55, 160), y: (-100, 100), z: (20, 90)
        target_coordinates = [
            CartesianPoint(x=120, y=-50, z=18),
            CartesianPoint(x=50, y=-115, z=40),
            CartesianPoint(x=125, y=-50, z=35),
            CartesianPoint(x=50, y=-120, z=30),
            CartesianPoint(x=135, y=-50, z=25),
            CartesianPoint(x=50, y=-140, z=20),
        ]

        vision_points_list: List[np.ndarray] = []
        robot_points_list: List[np.ndarray] = []

        logger.info(f"Starting registration calibration sequence using {len(target_coordinates)} waypoints.")
        cv2.namedWindow("Calibration")
        cv2.setMouseCallback("Calibration", click_callback)

        try:
            for idx, pt in enumerate(target_coordinates):
                logger.info(f"Step {idx + 1}/{len(target_coordinates)}: Moving robot arm to {pt}")

                # Move robot safely
                self.controller.execute_trajectory([pt])
                time.sleep(1.5)  # Wait for mechanical stabilization

                # Clear previous clicks
                clicked_pixel = None
                detected_coord: Optional[Tuple[int, int]] = None

                # Capture frames to stabilize visual tracking
                for _ in range(15):
                    frame = self.camera.read()
                    if frame is not None:
                        detected_coord = self.detect_colored_marker(frame)
                    time.sleep(0.03)

                # Detection loop / User confirmation
                while True:
                    frame = self.camera.read()
                    if frame is None:
                        continue

                    display_frame = frame.copy()

                    # Highlight automated detection in magenta
                    if detected_coord:
                        cv2.circle(display_frame, detected_coord, 6, (255, 0, 255), -1)
                        cv2.putText(
                            display_frame, f"Auto: {detected_coord}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2
                        )

                    # Instructions
                    cv2.putText(
                        display_frame, f"Pt {idx + 1}: Target {pt.x}, {pt.y}, {pt.z}", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
                    )
                    cv2.putText(
                        display_frame, "Press 'Enter' to confirm auto, 'm' for manual click, 'q' to abort",
                        (10, display_frame.shape[0] - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1
                    )

                    cv2.imshow("Calibration", display_frame)
                    key = cv2.waitKey(30) & 0xFF

                    if key == 13:  # Enter Key: Accept auto-detection
                        if detected_coord is not None:
                            pixel_x, pixel_y = detected_coord
                            break
                        else:
                            logger.warning("No automatic detection found. Select manually.")

                    elif key == ord('m'):  # Manual mode: user clicks exact pixel on the window
                        logger.info("Manual placement enabled. Please click on the physical marker coordinate.")
                        while clicked_pixel is None:
                            # Keep displaying frame while waiting for the click
                            frame_click = self.camera.read()
                            if frame_click is not None:
                                cv2.putText(
                                    frame_click, "CLICK directly on the marker...", (10, 30),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2
                                )
                                cv2.imshow("Calibration", frame_click)
                            cv2.waitKey(30)
                        pixel_x, pixel_y = clicked_pixel
                        break

                    elif key == ord('q'):
                        logger.info("Process aborted by user request.")
                        return

                # Backproject pixel to vision coordinates (world units)
                # This project points onto chessboard coordinates frame
                world_vision = self.calibration_engine.pixel_to_world(
                    pixel_x=pixel_x,
                    pixel_y=pixel_y,
                    plane_z=0.0
                )

                logger.info(
                    f"Point correspondence established: "
                    f"Vision: ({world_vision.x:.2f}, {world_vision.y:.2f}, {world_vision.z:.2f}) -> "
                    f"Robot: ({pt.x:.2f}, {pt.y:.2f}, {pt.z:.2f})"
                )

                vision_points_list.append([world_vision.x, world_vision.y, world_vision.z])
                robot_points_list.append([pt.x, pt.y, pt.z])

            # Process coordinates
            A = np.array(vision_points_list)
            B = np.array(robot_points_list)

            # SVD optimization
            R, t, rmse = estimate_rigid_transform_3d(A, B)

            logger.info("Workspace Calibration solved successfully.")
            logger.info(f"Fitting Root Mean Square Error (RMSE): {rmse:.4f} mm")
            logger.info(f"Rotation Matrix R:\n{R}")
            logger.info(f"Translation Vector t:\n{t.ravel()}")

            # Save results
            self.save_transform(R, t, rmse)

        finally:
            # Safely release physical units and threads
            cv2.destroyAllWindows()
            self.camera.stop()
            self.serial_client.disconnect()

    def save_transform(self, R: np.ndarray, t: np.ndarray, rmse: float) -> None:
        """Saves workspace registration data into YAML configuration."""
        output_dir = Path(".")
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / "workspace_transform.yaml"

        transform_data = {
            "workspace_transform": {
                "rotation_matrix": R.tolist(),
                "translation_vector": t.ravel().tolist(),
                "rmse_mm": float(rmse),
                "timestamp": time.time()
            }
        }

        try:
            with output_path.open("w", encoding="utf-8") as f:
                yaml.dump(transform_data, f, sort_keys=False, default_flow_style=False)
            logger.info(f"Transform successfully written to: {output_path}")
        except Exception as e:
            logger.error(f"Failed to write transformation parameters to yaml: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute visual-to-physical space registration mapping (AMADEUS MK-I)."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("../config/settings.yaml"),
        help="Path to system settings.yaml file."
    )
    args = parser.parse_args()

    try:
        calibrator = WorkspaceCalibrator(args.config)
        calibrator.run_calibration()
    except Exception as err:
        logger.exception(f"Unexpected termination during calibration task: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
