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


class PolicyError(RuntimeError):
    """策略连续推理失败，已超出可容忍范围。"""


# 连续失败多少次后不再静默返回零动作，而是抛错让上层处理
MAX_CONSECUTIVE_FAILURES = 10


class PolicyRunner:
    """策略推理封装。

    Args:
        checkpoint: 本地目录或 Hub 仓库名；为空则始终返回零动作
        action_chunk: 一次推理输出的动作步数
        dof: 关节数
        device: 推理设备
    """

    def __init__(self, checkpoint: str | None = None, action_chunk: int = 16,
                 dof: int = 6, device: str = "cuda",
                 action_unit: str = "auto"):
        self.action_chunk = action_chunk
        self.dof = dof
        self.device = device
        self.action_unit = action_unit          # auto | rad | deg
        self._output_unit = "rad"
        self._pre = None                        # checkpoint 的 preprocessor
        self._post = None                       # checkpoint 的 postprocessor
        self._failures = 0                      # 连续推理失败次数
        self.healthy = True                     # 供上层监控；连续失败后置 False
        self.load_error: str | None = None      # checkpoint 加载失败的说明
        self.policy = None
        self.instruction = ""
        if checkpoint:
            try:
                self._load(checkpoint)
            except PolicyError as exc:
                # 构造阶段不抛（便于单测与降级演示），但记录错误；
                # orchestrator 启动时据此拒绝运行，避免带着坏策略上真机
                self.load_error = str(exc)
                log.error("策略不可用：%s", exc)

    # ---------- 加载 ----------
    def _dataset_meta(self, checkpoint: str):
        """从 checkpoint 的 train_config.json 还原数据集元数据。

        ACT 的预处理/后处理器需要数据集统计量（归一化参数），
        make_policy 传 ds_meta=None 会直接报
        "Either one of a dataset metadata or a sim env must be provided."。
        """
        import json
        from pathlib import Path

        from lerobot.datasets.lerobot_dataset import LeRobotDatasetMetadata

        train_cfg = Path(checkpoint) / "train_config.json"
        if not train_cfg.exists():
            return None
        dataset = json.loads(train_cfg.read_text()).get("dataset") or {}
        repo_id = dataset.get("repo_id")
        if not repo_id:
            return None
        return LeRobotDatasetMetadata(repo_id, root=dataset.get("root"))

    def _load_processors(self, checkpoint: str) -> None:
        """加载 checkpoint 里的归一化/反归一化管线。

        lerobot 0.4 的 ACT 不在 policy 内部做归一化，而是在
        policy_preprocessor.json / policy_postprocessor.json 里描述。
        跳过这一步会得到归一化空间的数（实测 -0.74~0.54），
        既不是度也不是弧度，关节会被打到限位且不报错。
        """
        from lerobot.processor import PolicyProcessorPipeline

        overrides = {"device_processor": {"device": self.device}}
        try:
            self._pre = PolicyProcessorPipeline.from_pretrained(
                checkpoint, config_filename="policy_preprocessor.json", overrides=overrides
            )
            self._post = PolicyProcessorPipeline.from_pretrained(
                checkpoint, config_filename="policy_postprocessor.json", overrides=overrides
            )
            log.info("处理器已加载：pre %d 步 / post %d 步",
                     len(self._pre.steps), len(self._post.steps))
        except Exception as exc:  # noqa: BLE001
            self._pre = self._post = None
            # 没有 processor 的 ACT 输出停在归一化空间，动作必然错，
            # 不存在“降级可用”的情况，所以这里直接报错。
            raise PolicyError(
                f"归一化处理器加载失败，ACT 动作数值不可用：{exc}"
            ) from exc

    def _resolve_action_unit(self, checkpoint: str) -> str:
        """判断 checkpoint 训练数据的动作单位。

        项目的 RobotInterface 用弧度，但公开数据集（如 geonmin-kim 的 SO-101
        数据）用度。两者数值差 57 倍，直接用会把关节打到限位，而且不会报错。
        auto 模式按动作跨度判断：超过 10 视为度（弧度跨度不会超过 2π）。
        """
        if self.action_unit in ("rad", "deg"):
            return self.action_unit

        import json
        from pathlib import Path

        try:
            train_cfg = Path(checkpoint) / "train_config.json"
            dataset = json.loads(train_cfg.read_text()).get("dataset") or {}
            root = dataset.get("root")
            if not root:
                return "rad"
            stats = json.loads((Path(root) / "meta" / "stats.json").read_text())
            action = stats["action"]
            span = float(
                max(abs(hi - lo) for lo, hi in zip(action["min"], action["max"]))
            )
            unit = "deg" if span > 10.0 else "rad"
            log.info("训练数据动作单位检测：%s（关节跨度 %.1f）", unit, span)
            return unit
        except Exception as exc:  # noqa: BLE001  缺统计量时按接口默认弧度
            log.debug("动作单位检测失败（%s），按弧度处理", exc)
            return "rad"

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
            policy = make_policy(cfg, ds_meta=self._dataset_meta(checkpoint))
            policy.eval()
            self.policy = policy
            self._output_unit = self._resolve_action_unit(checkpoint)
            self._load_processors(checkpoint)
            log.info("policy loaded from %s（动作单位 %s）", checkpoint, self._output_unit)
        except PolicyError:
            raise
        except Exception as exc:  # noqa: BLE001  接口变动或权重损坏
            log.warning("加载策略失败（%s），保持零动作回退", exc)
            raise PolicyError(f"checkpoint 加载失败：{exc}") from exc

    # ---------- 推理 ----------
    def predict(self, frames: dict[str, np.ndarray], instruction: str,
                state: np.ndarray | None = None) -> np.ndarray:
        """返回 shape=(action_chunk, dof) 的动作块。

        Args:
            frames: 至少包含 front；wrist 可选
            instruction: 已由上层拼好的英文任务模板
            state: 当前关节位置；ACT 的输入需要它，缺失时策略会报错回退
        """
        self.instruction = instruction
        if self.policy is None:
            return np.zeros((self.action_chunk, self.dof), dtype=np.float32)

        try:
            raw = self._to_batch(frames, instruction, state)
            if self._pre is not None:
                batch = self._pre(raw)
            else:
                # 没有归一化管线时退回旧路径：手动补 batch 维
                batch = {k: (v.unsqueeze(0) if hasattr(v, "unsqueeze") else v)
                         for k, v in raw.items()}
            with np.errstate(all="ignore"):
                action = self.policy.select_action(batch)
            if self._post is not None:
                out = self._post({"action": action})
                action = out["action"] if isinstance(out, dict) else out
            # GPU 上 select_action 返回 cuda tensor，必须先搬到 host 再转 numpy
            if hasattr(action, "detach"):
                action = action.detach().cpu().numpy()
            arr = np.asarray(action, dtype=np.float32).reshape(-1, self.dof)
            if self._output_unit == "deg":
                # 公开数据集的 checkpoint 输出度，接口约定是弧度
                arr = np.deg2rad(arr).astype(np.float32)
            if arr.shape[0] < self.action_chunk:
                pad = np.repeat(arr[-1:], self.action_chunk - arr.shape[0], axis=0)
                arr = np.concatenate([arr, pad], axis=0)
            self._failures = 0
            self.healthy = True
            return arr[: self.action_chunk]
        except Exception as exc:  # noqa: BLE001  单次失败不打断控制环
            self._failures += 1
            self.healthy = False
            # 只在前几次和每 10 次打 error，避免 30 Hz 刷屏，但不会静默
            if self._failures == 1 or self._failures % 10 == 0:
                log.error("策略推理失败（连续 %d 次）：%s", self._failures, exc)
            if self._failures >= MAX_CONSECUTIVE_FAILURES:
                raise PolicyError(
                    f"策略连续 {self._failures} 次推理失败，最后一次：{exc}"
                ) from exc
            return np.zeros((self.action_chunk, self.dof), dtype=np.float32)

    def _camera_mapping(self) -> dict[str, str]:
        """按 checkpoint 的 input_features 推导接口相机名到观测键的映射。

        公开数据集的相机名可能是 top / wrist，也可能是 camera1 / camera2，
        不能硬编码：优先同名匹配，剩余槽位按声明顺序分给 front。
        """
        features = getattr(getattr(self.policy, "config", None), "input_features", None) or {}
        keys = [k for k in features if k.startswith("observation.images.")]
        mapping: dict[str, str] = {}
        for name in ("front", "wrist"):
            same = f"observation.images.{name}"
            if same in keys:
                mapping[name] = same
        rest = [k for k in keys if k not in mapping.values()]
        for name in ("front", "wrist"):
            if name not in mapping and rest:
                mapping[name] = rest.pop(0)
        return mapping or {
            "front": "observation.images.camera1",
            "wrist": "observation.images.camera2",
        }

    def _to_batch(self, frames: dict[str, np.ndarray], instruction: str,
                  state: np.ndarray | None = None) -> dict:
        """把帧字典转成 lerobot 期望的 batch。

        lerobot 的观测键为 observation.images.<camera> 与 observation.state；
        这里按接口相机名 front/wrist 映射到 checkpoint 实际使用的键。
        """
        import torch

        mapping = self._camera_mapping()
        batch: dict = {"task": [instruction]}
        for name, key in mapping.items():
            img = frames.get(name)
            if img is None:
                continue
            rgb = np.asarray(img)[:, :, ::-1]           # BGR -> RGB
            tensor = torch.from_numpy(rgb.copy()).permute(2, 0, 1).float() / 255.0
            batch[key] = tensor.to(self.device)
        if state is not None:
            st = torch.as_tensor(np.asarray(state, dtype=np.float32)).reshape(-1)
            batch["observation.state"] = st.to(self.device)
        return batch
