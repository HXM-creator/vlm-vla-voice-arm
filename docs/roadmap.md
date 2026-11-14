# 6 周路线图（2026-11-15 → 2027-01-01）

目标：一月前完成「仿真可抓取 + 语言条件达标 + VLM 联调」，真机到货后只做替换。

---

## 1. 现状盘点（全部为实测结论）

| 项 | 状态 | 证据 |
|:---|:---:|:---|
| 单元测试 | ✅ | 37 passed（`python3 -m pytest -q`，4.3 s） |
| 仿真渲染 | ✅ | MuJoCo 3.17 + EGL，双相机 640×480，场景含三色方块 |
| 采集（格式） | ✅ | 自采 3 条 → LeRobotDataset v3，`check_dataset [OK]` |
| 采集（语义） | ❌ | **演示是随机轨迹**，与方块位置无关 |
| 训练 | ✅ | ACT 52M，自采数据 10 步可训；公开数据集 500 步完成 |
| 推理 | ✅ | 修好 ds_meta / 相机映射 / state 后 `action_std=0.30–0.73` |
| 语言条件 | ✅ | 公开数据集判定 `effective`（0.0135–0.0145） |
| 可视化 | ✅ | 离线看板 + 双相机 mp4 |
| VLM 联调 | ❌ | 未跑（API Key 已配） |
| 真机 | ❌ | 等硬件 |

代码量 3192 行，模块边界清晰（`app / audio / policy / robot / sim / utils / vlm`）。

---

## 2. 参考基准

> 社区项目调研的完整结论（可直接借鉴的参数、27 条排错清单、不建议照搬的部分）
> 见 [reference.md](reference.md)。

### 2.1 成功复现的数据集（geonmin-kim）

| 项 | 值 |
|:---|:---|
| 规模 | 246 episodes / 79,145 帧 / 30 fps |
| 相机 | `observation.images.top` + `observation.images.wrist`，480×640 |
| 动作/状态 | 6 维，关节顺序 `shoulder_pan → gripper` |
| 任务 | **6 条**，`Move the {color} cube from the {left|right} mat to the {left|right} mat.` |
| 位置交叉设计 | 通过 left/right mat 强制「颜色与位置不绑定」 |

**结论**：字段与我们的项目完全一致；差异只在任务模板（它是搬运，我们是抓取）和采集方式（它遥操作，我们 IK 生成）。

### 2.2 LeRobot 官方流程

`lerobot-record`（采）→ `lerobot-train`（训）→ `lerobot-eval`（评）。我们只替换第 1 步的实现（仿真 IK 代替主臂遥操作），数据格式与后两步完全对齐。

---

## 3. 架构设计

### 3.0 ROS2 层的位置（重要）

ROS2 不是"另一条链路"，而是**同一套核心逻辑的多进程外壳**：

```
ROS2 节点（薄壳，238 行）          核心库（3192 行）
─────────────────────────         ─────────────────
audio_node      ────┐             voice_arm/audio/
vlm_node        ────┤             voice_arm/vlm/
policy_node     ────┼──调用──────> voice_arm/policy/
robot_node      ────┤             voice_arm/robot/
orchestrator    ────┘             voice_arm/app/
```

| 什么时候 | 用 ROS2 吗 | 原因 |
|:---|:---:|:---|
| 采集 / 训练 / 评测脚本 | ❌ | 直接调核心库，少一层进程开销与调试难度 |
| 阶段 4 编排器联调 | ✅ | 4 个进程靠话题解耦，语音不能阻塞控制环 |
| 阶段 5 真机 | ✅ | `real.launch.py`，`params.yaml` 切 `backend: real` |
| 答辩演示 | ✅ | `ros2 topic hz` 可直接证明 30 Hz |

**当前空白**：3 个包定义齐全、colcon 已装，但**从未 `colcon build`**。
必须尽早验证，否则问题会积压到 W4。

### 3.1 新增

| 模块 | 职责 | 状态 |
|:---|:---|:---|
| `voice_arm/sim/kinematics.py` | 数值 IK（阻尼最小二乘），末端 → 5 个臂关节 | ✅ 已建 70 行 |
| `voice_arm/sim/scene.py` | 方块位置随机化 + 颜色/位置交叉约束 | ⬜ 待建 |

### 3.2 改动

| 文件 | 改动 |
|:---|:---|
| `scripts/record_sim.py` | 用「IK 抓取轨迹」替换随机目标；按 `--task` 颜色选目标方块 |
| `Makefile` | `PYTHON ?= python3` |
| `scripts/setup_env.sh` | 导出 `MUJOCO_GL=egl` |

### 3.3 不动

`robot/interface.py`、`msg/*.msg`、相机名 `front/wrist`、关节顺序 —— 三个冻结契约全部保持不变。

### 3.4 抓取轨迹设计

```
q_start ──余弦──> q_above（方块上方 8 cm）
                 └─线性─> q_grasp（方块中心）
                          └─夹爪 0 → 1.5（闭合）
                                   └─余弦─> q_lift（上方 12 cm）
```

时间配比（单条 6 s @ 30 fps = 180 帧）：

| 段 | 帧数 | 夹爪 |
|:---|--:|--:|
| 接近 | 0–59 | 0（张开） |
| 下降 | 60–89 | 0 |
| 闭合 | 90–104 | 0 → 1.5 |
| 抬起 | 105–149 | 1.5 |
| 保持 | 150–179 | 1.5（便于训练对齐） |

### 3.5 位置随机化（对应 architecture.md 铁律）

| 铁律 | 仿真实现 |
|:---|:---|
| 初始位置打散 | 方块 x∈[0.38, 0.48]、y∈[-0.10, 0.10] 随机，10×10 cm 区域 |
| 颜色与位置交叉 | 每条 episode 随机重排三色方块的位置，**禁止颜色固定在某侧** |
| 指令模板统一 | `pick up the {color} cube`，只允许 green / blue / red |
| 每类 50 条 | 3 色 × 50 = 150 条（比 250 条少，因为只有抓取、无搬运） |

---

## 4. 六周计划

### W1（11/15–11/21）仿真真抓取

- [ ] IK 收敛调试（目标误差 < 5 mm）
- [ ] `record_sim.py` 换成抓取轨迹
- [ ] 采 6 条（绿蓝红各 2），训练 2000 步
- [ ] 录视频，确认机械臂接近并夹起目标色方块
- **通过标准**：视频里能看出「接近 → 下降 → 闭合 → 抬起」

### W2（11/22–11/28）数据规模化

- [ ] `sim/scene.py` 随机化 + 颜色位置交叉
- [ ] 采集 150 条（3 色 × 50）
- [ ] `check_dataset` 全绿，统计位置分布

### W3（11/29–12/5）正式训练（云端算力）

- [ ] 训练 20000 步（云端 4090/A100，batch 64，约 2–3 h，成本 ≈¥10）
- [ ] 语言条件 ≥ 0.05（现在 0.014 只是刚过阈值）
- [ ] 失败时按 `experiments.md` 排查：颜色位置绑定 / task 字段 / 模板一致性

**策略选择**：本地 RTX 4060 只做冒烟（batch 4、500 步）；正式训练放云端。
显存不再是约束后，ACT 与 SmolVLA 都可选：

| 方案 | 模型 | 显存 | 成本 | 语言条件强度 |
|:---|:---|--:|--:|:---|
| A | ACT 52M | 8 GB | ¥10 | 中 |
| B | SmolVLA 500M | 16–24 GB | ¥60–120 | 强（自带 VLM backbone） |

SmolVLA **不能替代 VLM 层**（它不懂中文），但它对英文指令更敏感，语言条件的数据会更好看。

### 云端训练 SOP

```bash
# 1. 本地打包（1–2 GB，压缩后更小）
tar czf sim_data.tar.gz -C outputs/datasets sim_green

# 2. 云端锁版本（务必，否则参数前缀会变）
pip install "lerobot==0.4.4" "huggingface_hub==0.35.3" "hf_transfer==0.1.9"
pip install "mujoco>=3.0" av

# 3. 解压并训练（开断点续训，防止机器被回收）
tar xzf sim_data.tar.gz -C outputs/datasets/
lerobot-train --policy.type=act \
  --dataset.repo_id=local/sim_green \
  --dataset.root=$PWD/outputs/datasets/sim_green \
  --dataset.video_backend=pyav \
  --output_dir=outputs/train/act_cloud \
  --policy.n_action_steps=10 \
  --batch_size=64 --steps=20000 --policy.device=cuda \
  --save_freq=5000 --resume=true

# 4. 取回 checkpoint（ACT 198 MB / SmolVLA 约 2 GB）
ls outputs/train/act_cloud/checkpoints/*/pretrained_model
```

**四条注意事项**：
1. `--dataset.video_backend=pyav` 必须加（社区项目独立验证过同样的 torchcodec 问题）
2. `--policy.n_action_steps=10`（默认 100 太大，桌面抓取会开环跑偏）
3. `--save_freq=5000` + `--resume=true`，机器被回收也不白花钱
4. 数据用 `--dataset.root` 指定本地解压路径，避免训练时联网下载

### W4（12/6–12/12）VLM 联调

- [ ] `python -m voice_arm.vlm.client` 单次延迟 < 15 s、JSON 合法
- [ ] 三条不变量验证（不输出坐标、方位不进 VLA、回复不进 VLA）
- [ ] 编排器跑通 `LISTENING → THINKING → EXECUTING → FEEDBACK → IDLE`

### W5（12/13–12/19）工程债 + 文档

- [ ] Makefile / MUJOCO_GL / pytest 警告
- [ ] 更新 `docs/experiments.md` 的当前状态
- [ ] 论文素材：链路图、数据统计、语言条件对比曲线

### W6（12/20–1/1）缓冲 + 真机准备

- [ ] 补测试（IK、场景随机化）
- [ ] 真机 checklist 演练（串口权限、标定流程）
- [ ] 未完成项顺延，不挤占 W1–W4

---

## 5. 风险与止损

| 风险 | 概率 | 应对 |
|:---|:---:|:---|
| IK 在方块位置不可达 | 中 | 方块限制在 x∈[0.38,0.48]，该区域在臂展内；不可达时自动重采样位置 |
| 夹爪夹不住（摩擦不足） | 中 | 调 `friction`（现 1.2）与闭合角度；仍不行则改小方块尺寸 |
| 训练后语言条件仍 `no_effect` | 中 | 优先查「颜色与位置是否绑定」，这是最常见原因 |
| 真机提前到货 | 低 | W1–W3 可压缩到 2 周，优先做 `real.py` |

**止损线**：W3 结束时若语言条件仍 < 0.03，停止调参，改为「单一颜色 + 位置随机」，先保证能抓，语言条件放到下一轮。
