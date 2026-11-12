"""真机实现（待硬件负责人填写）。

实现要求见 docs/interface.md：7 个方法、弧度单位、30 Hz、超时 100 ms。
"""
from __future__ import annotations

import numpy as np

from .interface import RobotInterface


class RealRobot(RobotInterface):
    """真实机械臂驱动。

    TODO(硬件负责人):
      1. 串口连接与协议握手
      2. 关节角度读写（弧度）
      3. 夹爪开合控制与回读
      4. 双相机 OpenCV 采集
    """

    def __init__(self, port: str = "/dev/ttyACM0", **kwargs):
        self.port = port
        raise NotImplementedError("真机实现待硬件选型确定后填写，见 docs/interface.md")

    def connect(self, port: str | None = None) -> bool:
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError

    def get_joint_positions(self) -> np.ndarray:
        raise NotImplementedError

    def set_joint_positions(self, q: np.ndarray) -> None:
        raise NotImplementedError

    def get_gripper_state(self) -> float:
        raise NotImplementedError

    def set_gripper(self, value: float) -> None:
        raise NotImplementedError

    def get_frames(self) -> dict[str, np.ndarray]:
        raise NotImplementedError
