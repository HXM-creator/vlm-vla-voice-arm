"""真机实现（待硬件负责人填写）。

实现要求见 docs/interface.md：
- 7 个方法、弧度单位、控制与回读 ≥30 Hz、单次调用超时 100 ms
- 舵机驱动层以「度」为单位，本类负责转换为弧度
"""
from __future__ import annotations

import logging

import numpy as np

from .interface import RobotInterface

log = logging.getLogger(__name__)

DEG_TO_RAD = np.pi / 180.0


class RealRobot(RobotInterface):
    """真实机械臂驱动。

    与硬件侧的约定：
    - 驱动层读写均为「度」，本类统一转成「弧度」交给上层
    - 两路相机（front / wrist），BGR 三通道
    - 关节顺序：shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper
    """

    def __init__(
        self,
        port: str = "/dev/ttyACM0",
        camera_index: dict[str, int] | None = None,
        cameras: tuple[str, ...] = ("front", "wrist"),
        dof: int = 6,
        timeout_ms: int = 100,
    ):
        self.port = port
        self.cameras = cameras
        self.camera_index = camera_index or {"front": 0, "wrist": 1}
        self.dof = dof
        self.timeout_ms = timeout_ms
        self._connected = False
        raise NotImplementedError(
            "真机实现待硬件选型确定后填写。请按 docs/interface.md 实现 7 个方法，"
            "并确保关节角以度读写、本类负责转换为弧度。"
        )

    # ---------- 内部：单位转换 ----------
    @staticmethod
    def _deg_to_rad(deg: np.ndarray) -> np.ndarray:
        q = np.asarray(deg, dtype=np.float32) * DEG_TO_RAD
        # 6 自由度机械臂单关节不可能超过一整圈，超出说明单位或标定有问题
        if np.any(np.abs(q) > 2 * np.pi):
            raise ValueError(
                f"关节角超出合理范围（{q} rad）。请检查驱动层是否已经是以度为单位，"
                "避免度/弧度混用导致机械臂大幅甩动。"
            )
        return q

    # ---------- RobotInterface ----------
    def connect(self, port: str | None = None) -> bool:
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError

    def get_joint_positions(self) -> np.ndarray:
        # 参考实现：
        #   deg = self._bus.read_positions()
        #   return self._deg_to_rad(deg)
        raise NotImplementedError

    def set_joint_positions(self, q: np.ndarray) -> None:
        # 参考实现：
        #   deg = np.rad2deg(np.asarray(q, dtype=np.float32))
        #   self._bus.write_positions(deg)
        raise NotImplementedError

    def get_gripper_state(self) -> float:
        raise NotImplementedError

    def set_gripper(self, value: float) -> None:
        raise NotImplementedError

    def get_frames(self) -> dict[str, np.ndarray]:
        # 参考实现：
        #   return {name: self._caps[name].read() for name in self.cameras}
        raise NotImplementedError
