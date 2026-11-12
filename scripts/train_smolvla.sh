#!/usr/bin/env bash
set -euo pipefail
# SmolVLA + LoRA：8 GB 显存需小批大小与梯度累积
DATASET=${1:?usage: bash scripts/train_smolvla.sh <dataset_repo_id>}
lerobot-train \
  --policy.path=lerobot/smolvla_base \
  --dataset.repo_id="${DATASET}" \
  --output_dir=outputs/train/smolvla \
  --batch_size=2 \
  --steps=20000 \
  --policy.device=cuda \
  --policy.freeze_vision_encoder=true \
  --peft.method_type=LORA \
  --peft.r=64 \
  --peft.lora_alpha=64
