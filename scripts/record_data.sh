#!/usr/bin/env bash
set -euo pipefail
# 主从遥操作采集（真机就绪后使用）
# 用法: bash scripts/record_data.sh <任务描述> <条数>
TASK=${1:-"把绿色方块放到右边"}
EPISODES=${2:-50}

lerobot-record \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM0 \
  --robot.cameras="{ front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30}}" \
  --teleop.type=so101_leader \
  --teleop.port=/dev/ttyACM1 \
  --dataset.num_episodes="${EPISODES}" \
  --dataset.single_task="${TASK}" \
  --display_data=true
