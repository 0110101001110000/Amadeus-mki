
from dataclasses import dataclass, field
from typing import List, Optional, Union
from motion.controller import ControllerConfig
from motion.planner import PlannerConfig, CartesianPoint
from motion.kinematics import ArmConfiguration, JointCalibration


@dataclass(frozen=True)
class SerialConfig:
    enabled: bool
    port: Optional[str]
    baudrate: int
    timeout_seconds: float
    reconnection_attempts: int
    reconnect_interval_seconds: float

    @classmethod
    def from_dict(cls, data: dict) -> "SerialConfig":
        return cls(
            enabled=bool(data.get("enabled", True)),
            port=data.get("port"),
            baudrate=int(data.get("baudrate", 9600)),
            timeout_seconds=float(data.get("timeout_seconds", 1.0)),
            reconnection_attempts=int(data.get("reconnection_attempts", 5)),
            reconnect_interval_seconds=float(data.get("reconnect_interval_seconds", 5.0)),
        )


@dataclass(frozen=True)
class CameraConfig:
    device_index: Union[int, str]
    frame_width: int
    frame_height: int
    fps: int

    @classmethod
    def from_dict(cls, data: dict) -> "CameraConfig":
        return cls(
            device_index=data.get("device_index", 0),
            frame_width=int(data.get("frame_width", 640)),
            frame_height=int(data.get("frame_height", 480)),
            fps=int(data.get("fps", 30)),
        )


@dataclass(frozen=True)
class DetectorConfig:
    confidence_threshold: float
    iou_threshold: float
    target_labels: List[str] = field(default_factory=list)
    model_path: str = ""

    @classmethod
    def from_dict(cls, detector_data: dict, model_data: dict) -> "DetectorConfig":
        return cls(
            confidence_threshold=float(detector_data.get("confidence_threshold", 0.4)),
            iou_threshold=float(detector_data.get("iou_threshold", 0.45)),
            target_labels=list(detector_data.get("target_labels", [])),
            model_path=str(model_data.get("path", "")),
        )


@dataclass(frozen=True)
class ToolConfig:
    offset_x_mm: float
    offset_y_mm: float
    offset_z_mm: float

    @classmethod
    def from_dict(cls, data: dict) -> "ToolConfig":
        return cls(
            offset_x_mm=float(data.get("offset_x_mm", 0.0)),
            offset_y_mm=float(data.get("offset_y_mm", 0.0)),
            offset_z_mm=float(data.get("offset_z_mm", 0.0)),
        )


@dataclass(frozen=True)
class SegmentationConfig:
    enabled: bool
    checkpoint_path: str
    device: str
    bbox_expansion_factor: float

    @classmethod
    def from_dict(
        cls,
        data: dict
    ) -> "SegmentationConfig":

        return cls(
            enabled=bool(
                data.get(
                    "enabled",
                    False
                )
            ),
            checkpoint_path=str(
                data.get(
                    "checkpoint_path",
                    ""
                )
            ),
            device=str(
                data.get(
                    "device",
                    "cuda"
                )
            ),
            bbox_expansion_factor=float(
                data.get(
                    "bbox_expansion_factor",
                    0.25
                )
            )
        )


@dataclass(frozen=True)
class VLMConfig:
    server_url: str
    username: str
    password: str
    model_name: str
    timeout: float

    @classmethod
    def from_dict(cls, data: dict) -> "VLMConfig":
        return cls(
            server_url=str(data.get("server_url", "")),
            username=str(data.get("username", "")),
            password=str(data.get("password", "")),
            model_name=str(data.get("model_name", "")),
            timeout=float(data.get("timeout", 30.0)),
        )


@dataclass(frozen=True)
class VisionConfig:
    camera: CameraConfig
    detector: DetectorConfig
    vlm: Optional[VLMConfig]
    segmentation: SegmentationConfig
    calibration_file_path: str
    transform_file_path: str
    live_detection_window: bool
    tool: ToolConfig

    @classmethod
    def from_dict(
        cls,
        data: dict,
        vlm: Optional[VLMConfig] = None
    ) -> "VisionConfig":
        camera_data = data.get("camera", {})
        detector_data = data.get("detector", {})
        model_data = data.get("model", {})
        calibration_data = data.get("calibration", {})
        tool_data = data.get("tool", {})
        segmentation_data = data.get("segmentation", {})

        return cls(
            camera=CameraConfig.from_dict(camera_data),
            detector=DetectorConfig.from_dict(detector_data, model_data),
            vlm=vlm,
            segmentation=SegmentationConfig.from_dict(segmentation_data),
            calibration_file_path=str(calibration_data.get("file_path",  "")),
            transform_file_path=str(calibration_data.get("transform_path", "")),
            live_detection_window=bool(data.get("live_detection_window", True)),
            tool=ToolConfig.from_dict(tool_data),
        )

@dataclass(frozen=True)
class PickupZoneConfig:
    enabled: bool

    activation_height_mm: float
    tolerance_mm: float

    min_radius_mm: float
    max_radius_mm: float


@dataclass(frozen=True)
class WorkspaceLimits:
    enabled: bool

    x_min: float
    x_max: float

    y_min: float
    y_max: float

    z_min: float
    z_max: float

    pickup_zone: PickupZoneConfig


@dataclass(frozen=True)
class MotionConfig:
    kinematics: ArmConfiguration
    calibration: JointCalibration
    planner: PlannerConfig
    controller: ControllerConfig
    workspace: WorkspaceLimits

    @classmethod
    def from_dict(cls, data: dict) -> "MotionConfig":
        """Constructs and returns nested motion configurations from raw dictionary parameters."""
        kin_data = data.get("kinematics", {})
        planner_data = data.get("planner", {})
        joints_data = data.get("joints", {})

        # Parse Joint Calibration Offsets and Gains
        joint_calibration = JointCalibration(
            base_ref_deg=float(kin_data.get("base_ref_deg", 0.0)),
            base_ref_pwd=float(kin_data.get("base_ref_pwd", 90.0)),
            shoulder_ref_deg=float(kin_data.get("shoulder_ref_deg", -24.0)),
            shoulder_ref_pwd=float(kin_data.get("shoulder_ref_pwd", 64.0)),
            elbow_ref_deg=float(kin_data.get("elbow_ref_deg", 24.0)),
            elbow_ref_pwd=float(kin_data.get("elbow_ref_pwd", 80.0)),
            shoulder_gain=float(kin_data.get("shoulder_gain", 0.725)),
            elbow_gain=float(kin_data.get("elbow_gain", 0.725)),
            base_inverted=bool(kin_data.get("base_inverted", True)),
            shoulder_inverted=bool(kin_data.get("shoulder_inverted", True)),
            elbow_inverted=bool(kin_data.get("elbow_inverted", False)),
        )

        # Parse Arm Physical Constraints
        arm_config = ArmConfiguration(
            upper_arm_length_mm=float(kin_data.get("upper_arm_length_mm", 80.0)),
            forearm_length_mm=float(kin_data.get("forearm_length_mm", 80.0)),
            base_height_offset_mm=float(kin_data.get("base_height_mm", 90.0)),
            max_reach_mm=float(kin_data.get("max_reach_mm", 150.0)),
            min_reach_mm=float(kin_data.get("min_reach_mm", 50.0)),
            base_servo_min_angle=float(kin_data.get("base_servo_min_angle", 0.0)),
            base_servo_max_angle=float(kin_data.get("base_servo_max_angle", 180.0)),
            shoulder_servo_min_angle=float(kin_data.get("shoulder_servo_min_angle", 0.0)),
            shoulder_servo_max_angle=float(kin_data.get("shoulder_servo_max_angle", 180.0)),
            elbow_servo_min_angle=float(kin_data.get("elbow_servo_min_angle", 0.0)),
            elbow_servo_max_angle=float(kin_data.get("elbow_servo_max_angle", 180.0)),
            calibration=joint_calibration,
        )

        # Parse Trajectory Planner Configuration
        home_pos_raw = planner_data.get("home_position", {"x": 60.0, "y": 0.0, "z": 90.0})
        planner_config = PlannerConfig(
            home_position=CartesianPoint(
                x=float(home_pos_raw.get("x")),
                y=float(home_pos_raw.get("y")),
                z=float(home_pos_raw.get("z")),
            ),
            safe_z_coordinate=float(data.get("tasks", {}).get("pick_and_place", {}).get("safe_height_mm", 90.0)),
        )

        # Parse Controller Profiles
        controller_config = ControllerConfig(
            max_speed=int(joints_data.get("max_speed_deg_per_sec", 22.0)),
            min_speed=int(joints_data.get("min_speed_deg_per_sec", 22.0)),
            # command_frequency=float(data.get("command_frequency_hz", 30.0)),
        )

        # Parse workspace
        workspace_data = data.get("workspace", {})

        global_data = workspace_data.get("global", {})
        pickup_data = workspace_data.get("pickup_zone", {})

        workspace = WorkspaceLimits(
            enabled=workspace_data.get("enabled", True),

            x_min=float(global_data.get("x_min", -160)),
            x_max=float(global_data.get("x_max", 160)),

            y_min=float(global_data.get("y_min", -160)),
            y_max=float(global_data.get("y_max", 160)),

            z_min=float(global_data.get("z_min", 20)),
            z_max=float(global_data.get("z_max", 100)),

            pickup_zone=PickupZoneConfig(
                enabled=pickup_data.get("enabled", True),
                activation_height_mm=float(
                    pickup_data.get("activation_height_mm", 20.0)
                ),
                tolerance_mm=float(
                    pickup_data.get("tolerance_mm", 5.0)
                ),
                min_radius_mm=float(
                    pickup_data.get("min_radius_mm", 55.0)
                ),
                max_radius_mm=float(
                    pickup_data.get("max_radius_mm", 70.0)
                ),
            )
        )

        return cls(
            kinematics=arm_config,
            calibration=joint_calibration,
            planner=planner_config,
            controller=controller_config,
            workspace=workspace,
        )


@dataclass(frozen=True)
class TaskConfig:
    pickup_height_mm: float
    safe_height_mm: float
    drop_height_mm: float
    drop_zone: CartesianPoint

    @classmethod
    def from_dict(cls, data: dict) -> "TaskConfig":
        """Constructs TaskConfig mappings containing spatial variables for pick-and-place operations."""
        pp_data = data.get("tasks", {}).get("pick_and_place", {})
        drop_raw = pp_data.get("drop_zone", {"x": 60.0, "y": 25.0, "z": 40.0})

        return cls(
            pickup_height_mm=float(pp_data.get("pickup_height_mm", 40.0)),
            safe_height_mm=float(pp_data.get("safe_height_mm", 60.0)),
            drop_height_mm=float(pp_data.get("drop_height_mm", 40.0)),
            drop_zone=CartesianPoint(
                x=float(drop_raw.get("x")),
                y=float(drop_raw.get("y")),
                z=float(drop_raw.get("z")),
            )
        )


@dataclass(frozen=True)
class TTSConfig:
    server_url: str
    username: str
    password: str

    @classmethod
    def from_dict(cls, data: dict) -> "TTSConfig":
        return cls(
            server_url=str(data.get("server_url", "")),
            username=str(data.get("username", "")),
            password=str(data.get("password", "")),
        )


@dataclass(frozen=True)
class STTConfig:
    server_url: str
    username: str
    password: str

    @classmethod
    def from_dict(cls, data: dict) -> "STTConfig":
        return cls(
            server_url=str(data.get("server_url", "")),
            username=str(data.get("username", "")),
            password=str(data.get("password", "")),
        )


@dataclass(frozen=True)
class AgentConfig:
    confidence_threshold: float
    max_retries: int

    @classmethod
    def from_dict(cls, data: dict) -> "AgentConfig":
        return cls(
            confidence_threshold=float(
                data.get("confidence_threshold", 0.7)
            ),
            max_retries=int(data.get("max_retries", 3)),
        )


@dataclass(frozen=True)
class AIConfig:
    vlm: VLMConfig
    tts: TTSConfig
    stt: STTConfig
    agents: AgentConfig

    @classmethod
    def from_dict(cls, data: dict) -> "AIConfig":
        return cls(
            vlm=VLMConfig.from_dict(data.get("vlm", {})),
            tts=TTSConfig.from_dict(data.get("tts", {})),
            stt=STTConfig.from_dict(data.get("stt", {})),
            agents=AgentConfig.from_dict(data.get("agents", {})),
        )

