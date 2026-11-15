# 仿真→真机链路映射与执行顺序

本文档记录一次**完整的仿真链路演练**，目的是在真机到货前把每一步的依赖、bug、通过标准都摸清，
这样真机上只需要替换硬件层，其余步骤直接照做。

最后更新：2026-11-15（Ubuntu 22.04 + RTX 4060 实测）

---

## 1. 链路映射表

| # | 环节 | 仿真（已在 Ubuntu 实测） | 真机（待做） | 关键文件 |
|:--|:---|:---|:---|:---|
| 0 | 环境自检 | `python3 scripts/doctor.py` | 同一份脚本，`ROS2` 与 `mujoco` 项会变 | `scripts/doctor.py` |
| 1 | 采集 | `scripts/record_sim.py` → LeRobotDataset v3 | `lerobot-record` + 真实相机/舵机 | `scripts/record_sim.py` |
| 2 | 训练 | `lerobot-train --policy.type=act` | 完全相同，只换 `--dataset.root` | — |
| 3 | 推理 | `SimRobot` + `PolicyRunner` | `RealRobot`（实现 7 个方法） | `robot/sim.py` / `robot/real.py` |
| 4 | 回放/评测 | `scripts/replay_sim.py` | 直接驱动真臂，看抓取成功率 | `scripts/replay_sim.py` |
| 5 | 语言条件 | `check_language_conditioning.py` | 同脚本，换 `--sim-xml` 为空 | 同名 |
| 6 | 可视化 | `render_replay_video.py` + 看板 | 摄像机录像 + 同一看板 | `dashboard/index.html` |

**结论：除第 3 环的 `real.py`，其余 6 个环节的代码、命令、数据格式在仿真与真机之间完全共用。**

---

## 2. 执行顺序（可直接照做）

### 阶段 0：环境自检

```bash
bash scripts/setup_env.sh --check
python3 scripts/doctor.py          # 期望末行「环境可用」
python3 -m pytest -q               # 期望 37 passed（不要用 make test，见 B1）
```

### 阶段 1：采集

```bash
export MUJOCO_GL=egl              # 无显示/EGL 环境必需
python3 scripts/record_sim.py \
  --episodes 30 --fps 30 --duration 6 \
  --task "pick up the green cube" \
  --output outputs/datasets/sim_green --repo-id local/sim_green --format lerobot \
  --sim-xml ros2_ws/src/voice_arm_core/voice_arm/sim/assets/scene.xml

python3 scripts/check_dataset.py --path outputs/datasets/sim_green
```

**通过标准**：`[OK]`，`total_frames` = episodes × fps × duration，相机为 `observation.images.front/wrist`。

> ⚠️ **当前 `record_sim.py` 的演示是随机目标 + 余弦插值**，与方块位置无关。
> 它能验证「格式与流程」，**不能用来训练抓取**。要做抓取必须先把演示换成基于 IK 的抓取轨迹。

### 阶段 2：训练

```bash
lerobot-train --policy.type=act \
  --dataset.repo_id=local/sim_green \
  --dataset.root=$PWD/outputs/datasets/sim_green \
  --dataset.video_backend=pyav \
  --output_dir=outputs/train/act_green \
  --policy.push_to_hub=false \
  --batch_size=8 --steps=5000 --policy.device=cuda
```

**通过标准**：`Training` 进度条正常前进；结束时生成 `checkpoints/000500/pretrained_model`。
**实测速度**：CPU 1.4 s/step（batch 2）；4060 上 batch 4 约 0.2–0.5 s/step。

### 阶段 3–4：推理与回放

```bash
CKPT=outputs/train/act_green/checkpoints/000500/pretrained_model

python3 scripts/replay_sim.py --checkpoint $CKPT --steps 200 \
  --sim-xml ros2_ws/src/voice_arm_core/voice_arm/sim/assets/scene.xml \
  --output outputs/replay
cat outputs/replay/summary.txt
```

**通过标准**：`action_std` 非零（实测 0.30–0.73）；`action_std=0` 说明 checkpoint 未加载。

### 阶段 5：语言条件

```bash
python3 scripts/check_language_conditioning.py --checkpoint $CKPT \
  --instructions "pick up the green cube" "pick up the blue cube" "pick up the red cube" \
  --steps 50 \
  --sim-xml ros2_ws/src/voice_arm_core/voice_arm/sim/assets/scene.xml
```

**通过标准**：判定 `effective`（实测平均距离 0.0135–0.0145，阈值 0.01）。
`inconclusive` = 策略未加载；`no_effect` = 数据设计问题（颜色与位置是否绑定、task 是否每条不同）。

### 阶段 6：可视化

```bash
python3 scripts/render_replay_video.py --checkpoint $CKPT --steps 200 \
  --sim-xml ros2_ws/src/voice_arm_core/voice_arm/sim/assets/scene.xml
python3 scripts/export_dashboard.py
xdg-open outputs/dashboard/index.html
```

---

## 3. 本次演练发现的 bug（均已修复）

| # | 现象 | 根因 | 修复 | 影响面 |
|:--|:---|:---|:---|:---|
| B1 | `make test` 报 `python: 未找到` | Makefile 硬编码 `python`，Ubuntu 只有 `python3` | **待修**：`PYTHON ?= python3` | 所有 Linux 用户，README 第一步就断 |
| B2 | `Could not load libtorchcodec` | torchcodec 需 FFmpeg 5–8，Ubuntu 22.04 只有 4.4 | 加 `--dataset.video_backend=pyav` | 所有 Ubuntu 22.04 训练 |
| B3 | `Either one of a dataset metadata or a sim env must be provided` | `make_policy(cfg, ds_meta=None)` | 从 `train_config.json` 构造 `LeRobotDatasetMetadata` | ACT 推理全链路 |
| B4 | 推理报 `'observation.images.wrist'` | 相机键硬编码 `camera1`/`camera2` | 按 `input_features` 动态映射 | 换数据集必踩 |
| B5 | 推理缺 `observation.state` | `predict()` 签名无 state | 新增 `state` 入参 | ACT 推理 |
| B6 | `can't convert cuda:0 tensor to numpy` | 未 `.cpu()` | `action.detach().cpu().numpy()` | GPU 推理 |
| B7 | `cannot import name 'LeRobotDataset'` | lerobot 0.4.4 改了导出路径 | 改从 `lerobot.datasets.lerobot_dataset` 导入 | 采集写 lerobot 格式 |
| B8 | `camera "front_cam" does not exist` | MJCF 里 `ncam=0`，模型没有相机 | 在 scene/模型里定义两路 camera | 仿真渲染 |
| B9 | 渲染一片棕色 | `MjData` 未 `mj_forward`，`xpos` 全 0 | `_load_mujoco` 末尾补一次 forward | 首次渲染 |
| B10 | `gladLoadGL error` | 默认 GLFW 后端不可用 | `export MUJOCO_GL=egl` | 无显示/EGL 环境 |
| B11 | 场景里没有可抓物体 | `scene.xml` 只有地面和机械臂 | 加三个彩色方块 + freejoint | 抓取验证 |
| B12 | `wrist_cam` 拍到夹爪外壳 | 相机在夹爪内部 | 外移到指尖外 0.17 m | 腕部视角 |
| B13 | 采出的视频臂变青色、地面变棕色 | `SimRobot` 输出 BGR，lerobot 数据集约定 RGB，直接透传导致通道反转 | 写入数据集前 `[:, :, ::-1]` 转 RGB | 所有 lerobot 格式采集 |
| B14 | 夹爪闭合抬起了，方块却留在原地 | `SimRobot` 只 `mj_forward` 不 `mj_step`，没有接触力 | 闭合时刻记录方块相对夹爪偏移，之后每帧把方块 qpos 搬到夹爪 | 仿真抓取演示 |
| B15 | 动作数值在 ±0.5 左右，关节被压住 | **跳过 lerobot 的 pre/post processor**，输出停在归一化空间 | 按 checkpoint 加载 `policy_preprocessor/postprocessor.json`，pre → select_action → post | 所有 ACT 推理 |

### 单位约定与跨数据集复用

这是最容易踩、且**不报错**的一个坑，单独列一节。

| 层 | 单位 | 依据 |
|:---|:---|:---|
| `RobotInterface`（仿真/真机接口） | **弧度** | `AGENTS.md` 冻结契约 |
| 真机硬件（舵机） | **度** | 转换只在 `RealRobot` 一处 |
| 公开数据集（geonmin-kim 等） | **度** | 实测动作跨度 171.5，mean -84.67 |
| 自采仿真数据 | **弧度** | 实测跨度 1.29，mean 0.75 |

**数值差 57 倍**（180/π）。直接拿公开数据集的 checkpoint 驱动仿真，关节会被打到限位
而且不报错——只会表现为“动作很怪”。

`PolicyRunner` 的处理顺序（缺一不可）：

```
原始图像/弧度 state
   ↓ _to_batch（BGR→RGB、按 input_features 映射相机名）
   ↓ pre processor（AddBatchDimension → Device → Normalizer）
policy.select_action
   ↓ post processor（Unnormalizer → Device）      ← 漏掉这步会得到归一化空间的数
度（若训练数据用度）
   ↓ deg2rad（_output_unit == "deg" 时）
弧度（交给 SimRobot / RealRobot）
```

可用参数覆盖自动判断：

```python
PolicyRunner(checkpoint=..., action_unit="rad")   # auto | rad | deg
```

**跨数据集复用的边界**：格式对齐后代码不用改，但模型不能互换——仿真训的拿去真机跑，
图像分布差距（合成渲染 vs 真实光照纹理）会让成功率归零。

### 尚未修复

| # | 问题 | 建议 |
|:--|:---|:---|
| U1 | `record_sim.py` 演示是随机轨迹 | 换数值 IK 抓取轨迹，否则永远学不会抓 |
| U2 | pytest 报 `Unknown config option: pythonpath` | 升 pytest 或改用 `conftest.py` 注入路径 |
| U3 | `MUJOCO_GL=egl` 只写在个人 `~/.bashrc` | 写进 `setup_env.sh` 与 `docs/setup.md` |

---

## 4. 环境依赖清单

| 组件 | 必需性 | 实测状态 | 备注 |
|:---|:---|:---|:---|
| Python 3.10 | 必需 | ✅ | ROS2 Humble 配套 |
| numpy | 必需 | ✅ | **注意：NumPy 2.x 会让系统 `python3-matplotlib` 崩** |
| OpenCV | 必需 | ✅ 4.5.4 | 视频合成用 `mp4v`，不需要 ffmpeg |
| mujoco | 阶段 1 起必需 | ✅ 3.17.0 | `MUJOCO_GL=egl` |
| PyAV | 训练视频解码必需 | ✅ 15.1.0 | 替代 torchcodec |
| torch | 训练必需 | ✅ 2.10.0+cu128 | — |
| lerobot | 训练必需 | ✅ 0.4.4 | 注意导出路径变化（B7） |
| ROS2 Humble | 节点通信必需 | ✅ 已装 | 跑脚本不需要 source |
| ffmpeg 命令 | ❌ 不需要 | 未装 | 用 PyAV / OpenCV |
| matplotlib | ❌ 不需要 | 坏（NumPy 2.x） | 看板改用纯 SVG |
| DeepSeek API | 阶段 4 必需 | ✅ 已配 | 15 s 超时、JSON 容错 |

---

## 6. 策略能力边界（重要）

`lerobot` 各策略对语言指令的支持**不一样**，选错策略会让语言条件永远无法成立。

| 策略 | 是否读 `task` | 实测 |
|:---|:---:|:---|
| **ACT** | **❌ 0 行** | 数据集有 task 字段，但 `forward` 完全不使用 |
| Diffusion | ❌ 0 行 | 同上 |
| VQ-BeT | ❌ 0 行 | 同上 |
| **SmolVLA** | ✅ 6 行 | 有 tokenizer + 语言编码 |
| **π0** | ✅ 6 行 | 同上 |

**排查方法**：

```bash
grep -c -E 'batch\["task"\]|batch\.get\("task"\)|tokenizer' \
  ~/.local/lib/python3.10/site-packages/lerobot/policies/<name>/*.py
```

**我们踩过的坑**：用 ACT 训 150 条三色数据、15000 步，动作学会了
（`action_std=1.25`），但三种指令的动作距离只有 **0.00016**——语言完全无效。
不是数据问题，是 ACT 架构不支持。

**推论**：做语言条件任务必须用 SmolVLA 或 π0。ACT 只能做**单任务**
（指令固定，模型只学"看图做动作"）。

**另一个更正**：用公开数据集（geonmin-kim）测出的 `effective`（0.0135）
是假象——该数据集里颜色与位置绑定，加上 ACT 的 VAE 采样随机性，
并非模型理解语言。

---

## 7. 真机迁移 checklist（到货后照做）

| # | 步骤 | 验证方式 |
|:--|:---|:---|
| 1 | `sudo usermod -aG dialout $USER`，重新登录 | `ls -l /dev/ttyACM*` |
| 2 | 实现 `robot/real.py` 的 7 个方法（**度→弧度只在这里转换**） | `python3 -m pytest -q` |
| 3 | `params.yaml` 改 `backend: real` + `port` + `camera_index` | `doctor.py` |
| 4 | 标定：零位、方向、限位、夹爪行程 | 手动小幅动作逐个确认 |
| 5 | 相机曝光/对焦锁定 | 连续拍 10 帧，亮度方差小 |
| 6 | 30 Hz 连续跑 30 分钟不掉线 | `ros2 topic hz /robot/status` |
| 7 | 真机采集 → 训练 → 测抓取成功率 | 只能真机，仿真无法替代 |

**不要做的事**：把真机数据和仿真数据混在一起训练（图像分布差异过大），除非先做域随机化。
