#!/usr/bin/env bash
set -euo pipefail
# 真机评估：统计抓放成功率
MODEL=${1:?usage: bash scripts/eval.sh <model_repo_id>}
lerobot-rollout \
  --strategy.type=episodic \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM0 \
  --policy.path="${MODEL}" \
  --display_data=true
