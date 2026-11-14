#!/bin/bash
# 夜间无人值守：采集 → 训练 → 评估 → 生成看板
#
# 用法：
#   cd ~/vlm-vla-voice-arm
#   nohup bash scripts/night_run.sh > /dev/null 2>&1 &
#
# 早上看：
#   tail -50 outputs/night/night_*.log
#   xdg-open outputs/dashboard/index.html
set -uo pipefail

cd "$(dirname "$0")/.."
ROOT=$PWD
STAMP=$(date +%Y%m%d_%H%M)
LOG_DIR="$ROOT/outputs/night"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/night_$STAMP.log"

# 所有输出同时写日志
exec > >(tee -a "$LOG") 2>&1

echo "================ 夜间任务 $STAMP ================"
echo "开始：$(date)"

fail() {
    echo ""
    echo "!!!!!!!! 失败于：$1"
    echo "结束：$(date)"
    echo "日志：$LOG"
    exit 1
}

# ---------- 0. 防休眠 ----------
INHIBIT_PID=""
if command -v systemd-inhibit >/dev/null 2>&1; then
    systemd-inhibit --what=idle:sleep --who=voice-arm-night \
        --why="long running training" sleep infinity &
    INHIBIT_PID=$!
    echo "已阻止系统休眠（pid=$INHIBIT_PID）"
else
    echo "警告：没有 systemd-inhibit，系统可能中途休眠，请手动关闭自动休眠"
fi
cleanup() { [ -n "$INHIBIT_PID" ] && kill "$INHIBIT_PID" 2>/dev/null; }
trap cleanup EXIT

# ---------- 1. 前置检查 ----------
echo ""
echo ">>> [1/5] 前置检查"
MUJOCO_GL=egl python3 scripts/preflight.py || fail "preflight"
MUJOCO_GL=egl python3 scripts/smoke_test.py --skip-inference || fail "smoke_test"

# ---------- 2. 采集 150 条（3 色 × 50）----------
echo ""
echo ">>> [2/5] 采集 150 条（约 20 分钟）"
DATA="$ROOT/outputs/datasets/v1_all"
rm -rf "$DATA"
MUJOCO_GL=egl python3 scripts/record_sim.py \
    --episodes 50 --fps 30 --duration 3 \
    --tasks "pick up the green cube|pick up the blue cube|pick up the red cube" \
    --output "$DATA" --repo-id local/v1_all --format lerobot \
    --sim-xml "$ROOT/ros2_ws/src/voice_arm_core/voice_arm/sim/assets/scene.xml" \
    || fail "采集"

python3 scripts/check_dataset.py --path "$DATA" || fail "数据集校验"

# ---------- 3. 训练 ----------
echo ""
echo ">>> [3/5] 训练 15000 步（约 1.5-2 小时）"
export HF_HUB_OFFLINE=1
lerobot-train \
    --policy.type=act \
    --dataset.repo_id=local/v1_all \
    --dataset.root="$DATA" \
    --dataset.video_backend=pyav \
    --output_dir="$ROOT/outputs/train/act_v1" \
    --policy.push_to_hub=false \
    --policy.n_action_steps=10 \
    --batch_size=4 \
    --steps=15000 \
    --save_freq=5000 \
    --policy.device=cuda \
    || fail "训练（8GB 显存用 batch 4 更稳）"

CKPT=$(ls -d "$ROOT"/outputs/train/act_v1/checkpoints/*/pretrained_model 2>/dev/null | tail -1)
[ -n "$CKPT" ] && [ -d "$CKPT" ] || fail "找不到 checkpoint"
echo "checkpoint: $CKPT"

# ---------- 4. 评估 ----------
echo ""
echo ">>> [4/5] 回放 + 语言条件（约 10 分钟）"
SIM="$ROOT/ros2_ws/src/voice_arm_core/voice_arm/sim/assets/scene.xml"

MUJOCO_GL=egl python3 scripts/replay_sim.py \
    --checkpoint "$CKPT" --steps 200 --sim-xml "$SIM" \
    --output "$ROOT/outputs/replay_v1" || fail "回放"

MUJOCO_GL=egl python3 scripts/check_language_conditioning.py \
    --checkpoint "$CKPT" \
    --instructions "pick up the green cube" "pick up the blue cube" "pick up the red cube" \
    --steps 50 --sim-xml "$SIM" \
    --output "$ROOT/outputs/lang_check_v1" || fail "语言条件"

MUJOCO_GL=egl python3 scripts/render_replay_video.py \
    --checkpoint "$CKPT" --steps 200 --sim-xml "$SIM" \
    --output "$ROOT/outputs/replay_v1/rollout.mp4" || fail "录制视频"

# ---------- 5. 看板 ----------
echo ""
echo ">>> [5/5] 生成看板"
python3 scripts/export_dashboard.py || fail "看板导出"

# ---------- 摘要 ----------
echo ""
echo "================ 结果摘要 ================"
echo "--- 回放 ---"
cat "$ROOT/outputs/replay_v1/summary.txt" 2>/dev/null

echo ""
echo "--- 语言条件 ---"
LANG_JSON=$(ls -t "$ROOT"/outputs/lang_check_v1/lang_check_*.json 2>/dev/null | head -1)
if [ -n "$LANG_JSON" ]; then
    python3 -c "
import json,sys
d=json.load(open('$LANG_JSON'))
print('判定:', d.get('verdict'))
for c in d.get('comparisons', []):
    print(f\"  {c['pair'][0]} vs {c['pair'][1]}: 平均距离 {c['mean_distance']:.5f}\")
"
fi

echo ""
echo "--- 产出 ---"
echo "数据:     $DATA"
echo "模型:     $CKPT"
echo "视频:     $ROOT/outputs/replay_v1/rollout.mp4"
echo "看板:     $ROOT/outputs/dashboard/index.html"
echo "日志:     $LOG"
echo ""
echo "结束：$(date)"
echo "================ 全部完成 ================"
