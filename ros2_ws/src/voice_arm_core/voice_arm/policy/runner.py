"""VLA 推理：输入图像与指令，输出动作块。

设计要点：
- 未加载 checkpoint 时返回零动作，保证编排器与回放脚本可以跑通
- 加载失败只记录警告并保持回退，不让整个系统起不来
- lerobot 为可选依赖，未安装时不影响单元测试
"""
from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger(__name__)


class PolicyRunner:
    """策略推理封装。

    Args:
        checkpoint: 本地目录或 Hub 仓库名；为空则始终返回零动作
        action_chunk: 一次推理输出的动作步数
        dof: 关节数
        device: 推理设备
    """

    def __init__(self, checkpoint: str | None = None, action_chunk: int = 16,
                 dof: int = 6, device: str = "cuda"):
        self.action_chunk = action_chunk
        self.dof = dof
        self.device = device
        self.policy = None
        self.instruction = ""
        if checkpoint:
            self._load(checkpoint)

    # ---------- 加载 ----------
    def _load(self, checkpoint: str) -> None:
        try:
            from lerobot.configs.policies import PreTrainedConfig
            from lerobot.policies.factory import make_policy
        except ImportError as exc:
            log.warning("lerobot 未安装，策略保持零动作回退：%s", exc)
            return

        try:
            cfg = PreTrainedConfig.from_pretrained(checkpoint)
            cfg.pretrained_path = checkpoint
            cfg.device = self.device
            policy = make_policy(cfg, ds_meta=None)
            policy.eval()
            self.policy = policy
            log.info("policy loaded from %s", checkpoint)
        except Exception as exc:  # noqa: BLE001  接口变动或权重损坏
            log.warning("加载策略失败（%s），保持零动作回退", exc)

    # ---------- 推理 ----------
    def predict(self, frames: dict[str, np.ndarray], instruction: str) -> np.ndarray:
        """返回 shape=(action_chunk, dof) 的动作块。

        Args:
            frames: 至少包含 front；wrist 可选
            instruction: 已由上层拼好的英文任务模板
        """
        self.instruction = instruction
        if self.policy is None:
            return np.zeros((self.action_chunk, self.dof), dtype=np.float32)

        try:
            batch = self._to_batch(frames, instruction)
            with np.errstate(all="ignore"):
                action = self.policy.select_action(batch)
            arr = np.asarray(action, dtype=np.float32).reshape(-1, self.dof)
            if arr.shape[0] < self.action_chunk:
                pad = np.repeat(arr[-1:], self.action_chunk - arr.shape[0], axis=0)
                arr = np.concatenate([arr, pad], axis=0)
            return arr[: self.action_chunk]
        except Exception as exc:  # noqa: BLE001  推理失败不应打断控制环
            log.warning("策略推理失败（%s），本次返回零动作", exc)
            return np.zeros((self.action_chunk, self.dof), dtype=np.float32)

    def _to_batch(self, frames: dict[str, np.ndarray], instruction: str) -> dict:
        """把帧字典转成 lerobot 期望的 batch。

        lerobot 的观测键为 observation.images.<camera> 与 observation.state；
        这里按接口相机名 front/wrist 映射到 camera1/camera2。
        """
        import torch

        mapping = {"front": "observation.images.camera1", "wrist": "observation.images.camera2"}
        batch: dict = {"task": [instruction]}
        for name, key in mapping.items():
            img = frames.get(name)
            if img is None:
                continue
            rgb = np.asarray(img)[:, :, ::-1]           # BGR -> RGB
            tensor = torch.from_numpy(rgb.copy()).permute(2, 0, 1).float() / 255.0
            batch[key] = tensor.unsqueeze(0).to(self.device)
        return batch
