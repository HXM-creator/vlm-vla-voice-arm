"""仿真实现：优先加载 MuJoCo 模型，未配置时回退到合成图像。

设计要点：
- 不硬依赖 mujoco，未安装时仍可 import 并跑单元测试
- 渲染结果是 RGB，接口约定是 BGR，出口统一转换
- 相机数量可配置，默认两路（front / wrist）
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from .interface import RobotInterface

log = logging.getLogger(__name__)

# MuJoCo 模型里相机命名与接口相机名的映射
DEFAULT_CAMERA_MAP = {
    "front": "front_cam",
    "wrist": "wrist_cam",
}


class SimRobot(RobotInterface):
    """仿真机械臂。

    两种模式：
    - ``xml_path`` 为空：返回合成图像，用于快速跑通管线与单元测试
    - ``xml_path`` 指向 MuJoCo XML：渲染真实场景
    """

    def __init__(
        self,
        dof: int = 6,
        image_size: tuple[int, int] = (480, 640),
        xml_path: str | Path | None = None,
        cameras: tuple[str, ...] = ("front", "wrist"),
        camera_map: dict[str, str] | None = None,
    ):
        self.dof = dof
        self.h, self.w = image_size
        self.cameras = cameras
        self.camera_map = camera_map or DEFAULT_CAMERA_MAP

        self._q = np.zeros(dof, dtype=np.float32)
        self._gripper = 0.0
        self._connected = False

        self._mj = None
        self._data = None
        self._renderer = None
        if xml_path:
            self._load_mujoco(Path(xml_path))

    # ---------- MuJoCo ----------
    def _load_mujoco(self, xml_path: Path) -> None:
        try:
            import mujoco
        except ImportError:
            log.warning("mujoco 未安装，回退到合成图像。安装：pip install 'mujoco>=3.0'")
            return

        if not xml_path.exists():
            log.warning("MuJoCo 模型不存在：%s，回退到合成图像", xml_path)
            return

        self._mj = mujoco.MjModel.from_xml_path(str(xml_path))
        self._data = mujoco.MjData(self._mj)
        self._renderer = mujoco.Renderer(self._mj, self.h, self.w)
        log.info("MuJoCo 模型已加载：%s（nq=%d）", xml_path.name, self._mj.nq)

    def _render_rgb(self, camera: str) -> np.ndarray:
        """按相机名渲染一帧，返回 RGB。"""
        self._renderer.update_scene(self._data, camera=camera)
        return self._renderer.render().copy()

    # ---------- RobotInterface ----------
    def connect(self, port: str | None = None) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def get_joint_positions(self) -> np.ndarray:
        if self._data is not None and self._data.qpos.size >= self.dof:
            return self._data.qpos[: self.dof].astype(np.float32).copy()
        return self._q.copy()

    def set_joint_positions(self, q: np.ndarray) -> None:
        q = np.asarray(q, dtype=np.float32)
        if q.shape != (self.dof,):
            raise ValueError(f"expected shape ({self.dof},), got {q.shape}")
        self._q = q.copy()

        if self._data is not None:
            self._data.qpos[: self.dof] = q
            import mujoco

            mujoco.mj_forward(self._mj, self._data)

    def get_gripper_state(self) -> float:
        return self._gripper

    def set_gripper(self, value: float) -> None:
        self._gripper = float(np.clip(value, 0.0, 1.0))

    def get_frames(self) -> dict[str, np.ndarray]:
        if self._renderer is None:
            return self._placeholder_frames()

        frames: dict[str, np.ndarray] = {}
        for name in self.cameras:
            cam = self.camera_map.get(name, name)
            rgb = self._render_rgb(cam)
            # 接口约定 BGR，MuJoCo 输出 RGB
            frames[name] = rgb[:, :, ::-1].copy()
        return frames

    # ---------- 回退 ----------
    def _placeholder_frames(self) -> dict[str, np.ndarray]:
        frame = np.full((self.h, self.w, 3), 220, dtype=np.uint8)
        frame[self.h // 3 : 2 * self.h // 3, self.w // 3 : 2 * self.w // 3] = (60, 160, 60)
        return {name: frame.copy() for name in self.cameras}
