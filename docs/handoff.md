# 换机器接续开发

从一台机器换到另一台（例如 Windows → Ubuntu），按本文档走。

---

## 1. 拿到代码

```bash
git clone git@github.com:HXM-creator/vlm-vla-voice-arm.git
cd vlm-vla-voice-arm
```

模型（16 MB）已在仓库里，不需要额外下载。

## 2. 恢复环境

```bash
bash scripts/setup_env.sh --check     # 看缺什么
bash scripts/setup_env.sh             # 装核心 + 仿真
bash scripts/setup_env.sh --train --audio   # 需要训练与语音时
python scripts/doctor.py              # 逐项确认
make test                             # 37 个测试
```

## 3. 读三份文档，恢复上下文

| 顺序 | 文档 | 作用 |
|:---:|:---|:---|
| 1 | `AGENTS.md` | 边界、冻结契约、代码约定 |
| 2 | `docs/decisions.md` | 为什么这么选（含被否掉的方案） |
| 3 | `docs/journal/` 最新一篇 | 上次做到哪、遗留什么问题 |

## 4. 确认当前进度

看 README 的「当前进度」表与 `docs/experiments.md` 的「当前状态」。
**两处都以仓库里的实际代码为准**，如果和本文档不一致，改文档。

## 5. 接着做

未完成项见 `docs/journal/` 最新一篇的「下一步」。
按 `docs/experiments.md` 的阶段顺序推进，不要跳步。

---

## 环境差异备忘

| 项目 | Windows（当前开发机） | Ubuntu 22.04（目标） |
|:---|:---|:---|
| 单元测试 | ✅ 可跑 | ✅ 可跑 |
| 仿真采集（合成图） | ✅ 可跑 | ✅ 可跑 |
| MuJoCo 渲染 | ⚠️ 可装但未验证 | ✅ |
| colcon / ROS2 节点 | ❌ | ✅ |
| 真机串口 | ❌ | ✅ |
| 音频采集 | ⚠️ | ✅ |

**结论：** Windows 上能写代码、跑测试、采合成数据；**端到端与真机必须在 Ubuntu**。

---

## 凭据与隐私

- `DEEPSEEK_API_KEY` 只放环境变量，**不写进任何文件**
- 数据、权重、视频已在 `.gitignore` 中排除
- 仓库是 public，提交前确认没有个人信息与本地绝对路径

---

## 附：Ubuntu 一步到位

```bash
# 1. 拿到代码
git clone git@github.com:HXM-creator/vlm-vla-voice-arm.git
cd vlm-vla-voice-arm

# 2. 镜像（国内必需）
export HF_ENDPOINT=https://hf-mirror.com
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 环境
bash scripts/setup_env.sh --check
bash scripts/setup_env.sh --train --audio
python scripts/doctor.py
make test

# 4. 验证仿真
python scripts/record_sim.py --episodes 2 --duration 2 \
  --sim-xml ros2_ws/src/voice_arm_core/voice_arm/sim/assets/scene.xml
python scripts/check_dataset.py --path outputs/datasets/sim_demo
```

## 附：无真机时的实验顺序

```bash
# ① 公开数据集验证训练流程
lerobot-train --policy.type=act \
  --dataset.repo_id=lerobot/svla_so101_pickplace \
  --output_dir=outputs/train/act_public --steps=5000 --batch_size=8

# ② 三色多任务验证语言条件
python scripts/check_language_conditioning.py \
  --checkpoint outputs/train/act_public/checkpoints/last \
  --instructions "pick up the green cube" "pick up the blue cube"

# ③ 仿真自采数据
python scripts/record_sim.py --episodes 200 \
  --sim-xml ros2_ws/src/voice_arm_core/voice_arm/sim/assets/scene.xml

# ④ 训练 + 回放
bash scripts/train_act.sh local/sim_multi
python scripts/replay_sim.py --checkpoint outputs/train/act/checkpoints/last --steps 200
```

## 附：常用镜像

| 用途 | 地址 |
|:---|:---|
| Python 包 | `https://pypi.tuna.tsinghua.edu.cn/simple` |
| HuggingFace | `https://hf-mirror.com` |
| GitHub clone | `https://gh-proxy.com/https://github.com/...` |
| ROS2 apt | 清华镜像替换 `packages.ros.org` |
