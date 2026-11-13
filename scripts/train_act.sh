#!/usr/bin/env bash
# ACT 基线训练：8 GB 显存可跑
set -euo pipefail

DATASET=${1:-}
if [ -z "$DATASET" ]; then
  echo "用法：bash scripts/train_act.sh <dataset_repo_id>" >&2
  echo "示例：bash scripts/train_act.sh local/sim_demo" >&2
  exit 1
fi

if ! command -v lerobot-train >/dev/null 2>&1; then
  echo "未找到 lerobot-train，安装：pip install 'lerobot>=0.4'" >&2
  exit 1
fi

echo ">> 数据集：$DATASET"
echo ">> 输出：outputs/train/act"
echo ">> 批大小 8，步数 20000（8 GB 显存的建议起点）"

lerobot-train \
  --policy.type=act \
  --dataset.repo_id="$DATASET" \
  --output_dir=outputs/train/act \
  --batch_size=8 \
  --steps=20000 \
  --policy.device=cuda
