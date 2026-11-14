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

# 关节角超出限位多少弧度以内可以直接截断（避免浮点误差误报）
CLAMP_TOLERANCE = 1e-3


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
        self._limit_warned = False

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
        # 初始运动学必须算一次，否则 xpos 全为 0，渲染时所有几何体堆在原点
        mujoco.mj_forward(self._mj, self._data)
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

        # 超限动作在仿真里会被静默接受，真机上会撞限位。这里截断并显式报错一次，
        # 让“策略输出超出关节范围”这类问题在第一次发生时就暴露出来。
        if self._mj is not None:
            limited = self._mj.jnt_limited[: self.dof].astype(bool)
            lo = np.where(limited, self._mj.jnt_range[: self.dof, 0], -np.inf)
            hi = np.where(limited, self._mj.jnt_range[: self.dof, 1], np.inf)
            excess = float(np.max(np.maximum(lo - q, q - hi)))
            if excess > CLAMP_TOLERANCE:
                if not self._limit_warned:
                    log.error("关节角超限 %.3f rad，已截断；检查策略单位或训练数据：q=%s",
                              excess, np.round(q, 2))
                    self._limit_warned = True
                q = np.clip(q, lo, hi).astype(np.float32)

        self._q = q.copy()

        if self._data is not None:
            self._data.qpos[: self.dof] = q
            import mujoco

            mujoco.mj_forward(self._mj, self._data)

    def get_gripper_state(self) -> float:
        return self._gripper

    def set_gripper(self, value: float) -> None:
        self._gripper = float(np.clip(value, 0.0, 1.0))

    # ---------- MuJoCo 句柄 ----------
    @property
    def model(self):
        """MuJoCo 模型；未加载模型时为 None。"""
        return self._mj

    @property
    def data(self):
        """MuJoCo 数据；未加载模型时为 None。"""
        return self._data

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
