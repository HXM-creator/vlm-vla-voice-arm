"""硬件抽象接口：上层代码只依赖本文件，不依赖任何具体型号。"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class RobotInterface(ABC):
    """机械臂统一接口。

    真机实现见 ``real.py``，仿真实现见 ``sim.py``。两者行为必须一致：
    角度单位为弧度，图像为 BGR 三通道 ndarray，单次调用超时 100 ms。
    """

    @abstractmethod
    def connect(self, port: str | None = None) -> bool:
        """建立连接。返回是否成功。"""

    @abstractmethod
    def disconnect(self) -> None:
        """断开连接，释放串口与相机。"""

    @abstractmethod
    def get_joint_positions(self) -> np.ndarray:
        """返回当前 6 个关节角（弧度），shape=(6,)。"""

    @abstractmethod
    def set_joint_positions(self, q: np.ndarray) -> None:
        """下发 6 个目标关节角（弧度），shape=(6,)。"""

    @abstractmethod
    def get_gripper_state(self) -> float:
        """返回夹爪开合值，0.0（闭合）~ 1.0（张开）。"""

    @abstractmethod
    def set_gripper(self, value: float) -> None:
        """设置夹爪开合值，0.0（闭合）~ 1.0（张开）。"""

    @abstractmethod
    def get_frames(self) -> dict[str, np.ndarray]:
        """返回相机帧字典，键为 ``front`` / ``wrist``。"""
