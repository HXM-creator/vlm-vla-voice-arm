"""训练入口说明。

实际训练调用 lerobot-train，本文件只做参数整理与命令拼装，避免在脚本里硬编码。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrainConfig:
    policy: str = "act"                 # act | smolvla
    dataset_repo: str = ""
    output_dir: str = "outputs/train"
    batch_size: int = 8
    steps: int = 20000
    use_lora: bool = False
    lora_r: int = 64
    lora_alpha: int = 64
    freeze_vision: bool = False

    def to_command(self) -> list[str]:
        cmd = [
            "lerobot-train",
            f"--policy.type={self.policy}" if self.policy == "act"
            else "--policy.path=lerobot/smolvla_base",
            f"--dataset.repo_id={self.dataset_repo}",
            f"--output_dir={self.output_dir}",
            f"--batch_size={self.batch_size}",
            f"--steps={self.steps}",
            "--policy.device=cuda",
        ]
        if self.use_lora:
            cmd += ["--peft.method_type=LORA", f"--peft.r={self.lora_r}",
                    f"--peft.lora_alpha={self.lora_alpha}"]
        if self.freeze_vision:
            cmd.append("--policy.freeze_vision_encoder=true")
        return cmd
