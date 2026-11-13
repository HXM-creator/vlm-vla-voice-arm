#!/usr/bin/env bash
# 下载 SO-101 的 MuJoCo/URDF 模型到本地，不纳入版本控制。
# 用法：bash scripts/download_sim_model.sh [目标目录]
set -euo pipefail

DEST=${1:-ros2_ws/src/voice_arm_core/voice_arm/sim/assets}
SRC=/tmp/so101_model_src

mkdir -p "$DEST"

if [ ! -d "$SRC" ]; then
  echo ">> 克隆模型仓库..."
  git clone --depth 1 \
    https://github.com/s0um0r0y/LeRobot-Object-Manipulation-VLM.git "$SRC"
fi

echo ">> 复制 SO-101 模型..."
cp -r "$SRC"/pybullet_sim/lerobot_URDF/* "$DEST"/

echo ">> 完成，模型位于 $DEST"
ls "$DEST" | head -20

cat <<'EOF'

下一步：
  1. 在 params.yaml 里把 sim_xml 指向场景文件，例如
     ros2_ws/src/voice_arm_core/voice_arm/sim/assets/scene.xml
  2. 确认 XML 里的相机名（front_cam / wrist_cam）与 camera_map 一致
  3. 若 XML 引用了绝对路径，改成相对路径

注意：模型文件约 15 MB，已在 .gitignore 中排除，不要提交。
EOF
