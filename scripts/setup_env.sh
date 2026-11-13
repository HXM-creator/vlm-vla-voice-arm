#!/usr/bin/env bash
# 一键环境安装 / 检查。不自动 sudo 安装 ROS2，只做检测与提示。
#
# 用法：
#   bash scripts/setup_env.sh              # 只装核心依赖并检查
#   bash scripts/setup_env.sh --train      # 额外装 lerobot + torch
#   bash scripts/setup_env.sh --audio      # 额外装音频依赖
#   bash scripts/setup_env.sh --check      # 只检查，不安装
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORE_DIR="$ROOT_DIR/ros2_ws/src/voice_arm_core"
WITH_TRAIN=0
WITH_AUDIO=0
CHECK_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --train) WITH_TRAIN=1 ;;
    --audio) WITH_AUDIO=1 ;;
    --check) CHECK_ONLY=1 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "未知参数：$arg" >&2; exit 1 ;;
  esac
done

ok()   { printf "  \033[32m[OK]\033[0m   %s\n" "$1"; }
warn() { printf "  \033[33m[WARN]\033[0m %s\n" "$1"; }
fail() { printf "  \033[31m[FAIL]\033[0m %s\n" "$1"; }

echo "== 系统 =="
if [ -f /etc/os-release ]; then
  . /etc/os-release
  echo "  $PRETTY_NAME"
  if [ "${VERSION_ID:-}" != "22.04" ]; then
    warn "推荐 Ubuntu 22.04；其他版本可能缺 ROS2 Humble 的 apt 包"
  else
    ok "Ubuntu 22.04"
  fi
else
  warn "无法识别系统（不是 Linux？ROS2 部分将不可用）"
fi

echo "== Python =="
if command -v python3 >/dev/null 2>&1; then
  PYV=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
  echo "  python3 $PYV"
  case "$PYV" in
    3.10|3.11) ok "版本可用" ;;
    *) warn "ROS2 Humble 官方配套是 3.10" ;;
  esac
else
  fail "未找到 python3"
fi

echo "== ROS2 =="
if [ -n "${ROS_DISTRO:-}" ]; then
  ok "已 source：$ROS_DISTRO"
elif [ -d /opt/ros/humble ]; then
  warn "已安装但未 source：source /opt/ros/humble/setup.bash"
else
  fail "未安装 ROS2 Humble（参考 docs/setup.md 第 1 节）"
fi

echo "== 模型文件 =="
SCENE="$CORE_DIR/voice_arm/sim/assets/scene.xml"
if [ -f "$SCENE" ]; then
  ok "scene.xml 存在"
else
  fail "缺少 $SCENE"
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
  echo
  echo "只检查模式，退出。"
  exit 0
fi

echo "== 安装核心依赖 =="
python3 -m pip install -q -e "$CORE_DIR" -i https://pypi.tuna.tsinghua.edu.cn/simple && ok "voice_arm_core 已安装"

echo "== 安装仿真依赖 =="
python3 -m pip install -q "mujoco>=3.0" -i https://pypi.tuna.tsinghua.edu.cn/simple && ok "mujoco 已安装"

if [ "$WITH_TRAIN" -eq 1 ]; then
  echo "== 安装训练依赖（较大，几分钟）=="
  python3 -m pip install -q torch torchvision -i https://pypi.tuna.tsinghua.edu.cn/simple && ok "torch"
  python3 -m pip install -q "lerobot>=0.4" && ok "lerobot"
fi

if [ "$WITH_AUDIO" -eq 1 ]; then
  echo "== 安装音频依赖 =="
  python3 -m pip install -q "sounddevice>=0.4" "soundfile>=0.12" "edge-tts>=6.1" \
    -i https://pypi.tuna.tsinghua.edu.cn/simple && ok "sounddevice / soundfile / edge-tts"
  python3 -m pip install -q "openwakeword>=0.6" && ok "openwakeword"
  python3 -m pip install -q "funasr>=1.1" && ok "funasr"
fi

echo "== 环境自检 =="
python3 "$ROOT_DIR/scripts/doctor.py" || true

echo
echo "下一步："
echo "  python3 scripts/record_sim.py --episodes 2 --duration 2     # 采数据"
echo "  python3 scripts/replay_sim.py --steps 50                    # 回放"
echo "  make test                                                    # 37 个测试"
echo
echo "ROS2 节点："
echo "  cd ros2_ws && colcon build --symlink-install && source install/setup.bash"
echo "  ros2 launch voice_arm_bringup sim.launch.py"
