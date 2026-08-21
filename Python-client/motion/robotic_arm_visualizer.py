from __future__ import annotations

import math
import matplotlib.pyplot as plt

from dataclasses import dataclass, field
from matplotlib.widgets import Slider
from mpl_toolkits.mplot3d import Axes3D


# --------------------------------------------------------------------------- #
# Utils
# --------------------------------------------------------------------------- #

def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def safe_acos(value: float) -> float:
    return math.acos(clamp(value, -1.0, 1.0))


def direction_multiplier(is_inverted: bool) -> float:
    return -1.0 if is_inverted else 1.0


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class JointCalibration:
    base_offset_deg: float = 0.0
    shoulder_offset_deg: float = 0.0
    elbow_offset_deg: float = 0.0

    base_inverted: bool = False
    shoulder_inverted: bool = False
    elbow_inverted: bool = False


@dataclass(frozen=True)
class ArmConfiguration:
    upper_arm_length: float = 80.0
    forearm_length: float = 80.0
    base_height_offset: float = 0.0

    calibration: JointCalibration = field(
        default_factory=JointCalibration
    )


@dataclass(frozen=True)
class MotorAngles:
    base: float
    shoulder: float
    elbow: float


# --------------------------------------------------------------------------- #
# Kinematics
# --------------------------------------------------------------------------- #

class RoboticArmKinematics:

    def __init__(self, configuration: ArmConfiguration):
        self.cfg = configuration

    def calculate(self, x: float, y: float, z: float) -> MotorAngles:

        base_angle = math.degrees(math.atan2(y, x))

        radial = math.hypot(x, y)
        vertical = z - self.cfg.base_height_offset

        upper = self.cfg.upper_arm_length
        fore = self.cfg.forearm_length

        d = math.hypot(radial, vertical)

        elbow_cos = (
            (radial**2 + vertical**2 - upper**2 - fore**2)
            / (2 * upper * fore)
        )

        elbow_rad = safe_acos(elbow_cos)

        shoulder_rad = (
            math.atan2(vertical, radial)
            - math.atan2(
                fore * math.sin(elbow_rad),
                upper + fore * math.cos(elbow_rad),
            )
        )

        shoulder_deg = math.degrees(shoulder_rad)
        elbow_deg = math.degrees(elbow_rad)

        return MotorAngles(
            base=base_angle,
            shoulder=shoulder_deg,
            elbow=elbow_deg,
        )


# --------------------------------------------------------------------------- #
# Interactive Visualizer
# --------------------------------------------------------------------------- #

class InteractiveArmVisualizer:

    def __init__(self):

        self.cfg = ArmConfiguration()

        self.kinematics = RoboticArmKinematics(self.cfg)

        self.fig = plt.figure(figsize=(10, 10))

        self.ax = self.fig.add_subplot(
            111,
            projection="3d",
        )

        plt.subplots_adjust(bottom=0.25)

        # Initial coordinates
        self.x = 40
        self.y = 40
        self.z = 80

        # Sliders
        self._create_sliders()

        # First render
        self.update(None)

    def _create_sliders(self):

        ax_x = plt.axes([0.2, 0.12, 0.6, 0.03])
        ax_y = plt.axes([0.2, 0.08, 0.6, 0.03])
        ax_z = plt.axes([0.2, 0.04, 0.6, 0.03])

        self.slider_x = Slider(
            ax=ax_x,
            label="X",
            valmin=-150,
            valmax=150,
            valinit=self.x,
        )

        self.slider_y = Slider(
            ax=ax_y,
            label="Y",
            valmin=-150,
            valmax=150,
            valinit=self.y,
        )

        self.slider_z = Slider(
            ax=ax_z,
            label="Z",
            valmin=0,
            valmax=200,
            valinit=self.z,
        )

        self.slider_x.on_changed(self.update)
        self.slider_y.on_changed(self.update)
        self.slider_z.on_changed(self.update)

    def update(self, _):

        self.x = self.slider_x.val
        self.y = self.slider_y.val
        self.z = self.slider_z.val

        self.ax.clear()

        try:

            angles = self.kinematics.calculate(
                self.x,
                self.y,
                self.z,
            )

            self._draw_arm(angles)

            title = (
                f"Base={angles.base:.1f}° | "
                f"Shoulder={angles.shoulder:.1f}° | "
                f"Elbow={angles.elbow:.1f}°"
            )

            self.ax.set_title(title)

        except Exception as exc:

            self.ax.set_title(f"Unreachable position: {exc}")

        self._configure_axes()

        plt.draw()

    def _draw_arm(self, angles: MotorAngles):

        upper = self.cfg.upper_arm_length
        fore = self.cfg.forearm_length
        base_h = self.cfg.base_height_offset

        base_rad = math.radians(angles.base)
        shoulder_rad = math.radians(angles.shoulder)
        elbow_rad = math.radians(angles.elbow)

        # Base
        x0, y0, z0 = 0, 0, 0

        # Shoulder
        x1, y1, z1 = 0, 0, base_h

        # Elbow
        radial_upper = upper * math.cos(shoulder_rad)

        x2 = radial_upper * math.cos(base_rad)
        y2 = radial_upper * math.sin(base_rad)
        z2 = base_h + upper * math.sin(shoulder_rad)

        # End effector
        total_angle = shoulder_rad + elbow_rad

        radial_fore = fore * math.cos(total_angle)

        x3 = x2 + radial_fore * math.cos(base_rad)
        y3 = y2 + radial_fore * math.sin(base_rad)
        z3 = z2 + fore * math.sin(total_angle)

        # Draw segments
        self.ax.plot(
            [x0, x1],
            [y0, y1],
            [z0, z1],
            linewidth=5,
        )

        self.ax.plot(
            [x1, x2],
            [y1, y2],
            [z1, z2],
            linewidth=5,
        )

        self.ax.plot(
            [x2, x3],
            [y2, y3],
            [z2, z3],
            linewidth=5,
        )

        # Draw joints
        self.ax.scatter(
            [x0, x1, x2, x3],
            [y0, y1, y2, y3],
            [z0, z1, z2, z3],
            s=80,
        )

        # Target
        self.ax.scatter(
            [self.x],
            [self.y],
            [self.z],
            s=150,
            marker="x",
        )

    def _configure_axes(self):

        limit = 180

        self.ax.set_xlim(-limit, limit)
        self.ax.set_ylim(-limit, limit)
        self.ax.set_zlim(0, limit)

        self.ax.set_xlabel("X")
        self.ax.set_ylabel("Y")
        self.ax.set_zlabel("Z")

        self.ax.grid(True)

    def show(self):
        plt.show()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

if __name__ == "__main__":

    app = InteractiveArmVisualizer()

    app.show()