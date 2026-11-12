#!/usr/bin/env bash
set -euo pipefail
# ACT 基线训练：8 GB 显存可跑
DATASET=${1:?usage: bash scripts/train_act.sh <dataset_repo_id>}
lerobot-train \
  --policy.type=act \
  --dataset.repo_id="${DATASET}" \
  --output_dir=outputs/train/act \
  --batch_size=8 \
  --steps=20000 \
  --policy.device=cuda
