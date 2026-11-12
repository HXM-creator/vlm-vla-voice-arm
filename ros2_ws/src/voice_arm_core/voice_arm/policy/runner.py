"""VLA 推理：输入图像与指令，输出动作块。"""
from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger(__name__)


class PolicyRunner:
    """策略推理封装。真实实现由 lerobot 加载检查点；未加载时返回安全零动作。"""

    def __init__(self, checkpoint: str | None = None, action_chunk: int = 16, dof: int = 6):
        self.action_chunk = action_chunk
        self.dof = dof
        self.policy = None
        if checkpoint:
            self._load(checkpoint)

    def _load(self, checkpoint: str) -> None:
        # 依赖 lerobot；未安装时保持 policy=None，走安全回退
        try:
            from lerobot.policies.factory import make_policy  # type: ignore
            log.info("loading policy from %s", checkpoint)
            # 具体加载参数在训练脚本确定后补齐
            self.policy = None
        except Exception as exc:  # noqa: BLE001
            log.warning("policy not loaded (%s), falling back to zero actions", exc)

    def predict(self, frames: dict[str, np.ndarray], instruction: str) -> np.ndarray:
        """返回 shape=(action_chunk, dof) 的动作块。"""
        if self.policy is None:
            return np.zeros((self.action_chunk, self.dof), dtype=np.float32)
        raise NotImplementedError("接入 lerobot 推理后实现")
