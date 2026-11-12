"""仿真实现：无硬件时也能跑通全链路。"""
from __future__ import annotations

import numpy as np

from .interface import RobotInterface


class SimRobot(RobotInterface):
    """返回固定关节角与合成图像，用于联调与测试。"""

    def __init__(self, dof: int = 6, image_size: tuple[int, int] = (480, 640)):
        self.dof = dof
        self.h, self.w = image_size
        self._q = np.zeros(dof, dtype=np.float32)
        self._gripper = 0.0
        self._connected = False

    def connect(self, port: str | None = None) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def get_joint_positions(self) -> np.ndarray:
        return self._q.copy()

    def set_joint_positions(self, q: np.ndarray) -> None:
        q = np.asarray(q, dtype=np.float32)
        if q.shape != (self.dof,):
            raise ValueError(f"expected shape ({self.dof},), got {q.shape}")
        self._q = q.copy()

    def get_gripper_state(self) -> float:
        return self._gripper

    def set_gripper(self, value: float) -> None:
        self._gripper = float(np.clip(value, 0.0, 1.0))

    def get_frames(self) -> dict[str, np.ndarray]:
        # 合成图像：浅灰背景 + 中心色块，便于验证管线
        frame = np.full((self.h, self.w, 3), 220, dtype=np.uint8)
        frame[self.h // 3 : 2 * self.h // 3, self.w // 3 : 2 * self.w // 3] = (60, 160, 60)
        return {"front": frame.copy(), "wrist": frame.copy()}
