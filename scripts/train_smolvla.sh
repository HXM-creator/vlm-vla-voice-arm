#!/usr/bin/env bash
# SmolVLA + LoRA：8 GB 显存需小批大小与梯度累积
set -euo pipefail

DATASET=${1:-}
if [ -z "$DATASET" ]; then
  echo "用法：bash scripts/train_smolvla.sh <dataset_repo_id>" >&2
  echo "示例：bash scripts/train_smolvla.sh local/sim_demo" >&2
  exit 1
fi

if ! command -v lerobot-train >/dev/null 2>&1; then
  echo "未找到 lerobot-train，安装：pip install 'lerobot>=0.4'" >&2
  exit 1
fi

# 训练与推理的相机名必须一致，否则会报特征不匹配
RENAME_MAP='{"observation.images.front": "observation.images.camera1", "observation.images.wrist": "observation.images.camera2"}'

echo ">> 数据集：$DATASET"
echo ">> LoRA r=64 alpha=64，冻结视觉编码器，批大小 2"
echo ">> 若出现 OOM：把 batch_size 降到 1，并增加梯度累积"

lerobot-train \
  --policy.path=lerobot/smolvla_base \
  --dataset.repo_id="$DATASET" \
  --rename_map="$RENAME_MAP" \
  --output_dir=outputs/train/smolvla \
  --batch_size=2 \
  --steps=20000 \
  --policy.device=cuda \
  --policy.freeze_vision_encoder=true \
  --peft.method_type=LORA \
  --peft.r=64 \
  --peft.lora_alpha=64
