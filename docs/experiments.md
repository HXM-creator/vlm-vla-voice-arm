# 仿真验证流程

本文档回答两个问题：**仿真能验证到什么程度**，以及**上真机前必须按什么顺序跑通**。

---

## 1. 仿真的边界

### 能验证（结论可信）

| 项目 | 原因 |
|:---|:---|
| 接口契约（7 个方法） | 与真机同一套抽象，签名与单位一致 |
| 状态机与超时 | 纯逻辑，与硬件无关 |
| 数据格式与字段 | LeRobotDataset v3 同一套 schema |
| 训练 / 推理流程 | 与真机共用同一脚本 |
| 控制频率与线程时序 | 编排器与执行线程一致 |
| **语言条件是否生效** | 固定场景换指令，看动作是否不同 |
| 多类物体的数据配比 | 采集脚本可控制 |

### 不能验证（真机必须重测）

| 项目 | 原因 |
|:---|:---|
| 真实图像分布 | 合成图无真实纹理、反光与阴影 |
| 舵机延迟与丢步 | 仿真没有电机动力学与总线延迟 |
| 手眼外参 | 仿真相机是理想成像 |
| 抓取物理 | 接触、摩擦、形变在仿真里是近似 |
| USB 带宽与掉设备 | 纯硬件问题 |
| 语音噪声下的识别率 | 需要真实麦克风与环境 |
| 30 Hz 能否长期稳定 | 需要真机连续跑 30 分钟 |

**一句话：**
仿真能证明「逻辑对、格式对、流程对」，不能证明「抓得住」。抓取成功率只能在真机上测。

---

## 2. 五个阶段

### 阶段 0：冒烟测试（不需要任何硬件与模型）

```bash
make test
```

**通过标准：** 37 个测试全部通过。
**失败排查：** 缺 numpy 或 pytest；检查 `pip install -e "ros2_ws/src/voice_arm_core[dev]"`。

---

### 阶段 1：仿真数据采集

```bash
# 无 MuJoCo 模型：合成图像，验证格式与流程
python scripts/record_sim.py --episodes 5 --fps 30 --duration 6 \
    --task "pick up the green cube" --output outputs/datasets/sim_demo

# 有 MuJoCo 模型：真实渲染
bash scripts/download_sim_model.sh
python scripts/record_sim.py --sim-xml ros2_ws/src/voice_arm_core/voice_arm/sim/assets/scene.xml ...

# 校验
python scripts/check_dataset.py --path outputs/datasets/sim_demo
```

**通过标准：** `check_dataset.py` 输出 `[OK]`，两路相机存在，`state` 为 6 维。
**失败排查：** 字段缺失看 `meta.json`；相机数量不对看 `SimRobot.cameras`。

---

### 阶段 2：训练与回放

```bash
bash scripts/train_act.sh <dataset_repo_id>
python scripts/replay_sim.py --checkpoint outputs/train/act/checkpoints/last --steps 200
```

**通过标准：**
- 训练无 OOM（ACT 在 8 GB 上约 2–6 GB）
- 回放 `summary.txt` 里 `actual_fps` 接近目标值
- `action_std` 不为 0（说明策略真的在输出动作，不是零动作回退）

**失败排查：**
- `action_std=0` → checkpoint 没加载成功，看日志里的 `policy loaded from`
- OOM → `batch_size` 降到 4 或 2

---

### 阶段 3：语言条件验证（最关键）

```bash
python scripts/check_language_conditioning.py \
    --checkpoint outputs/train/act/checkpoints/last \
    --instructions "pick up the green cube" "pick up the blue cube" \
    --steps 50
```

**三种判定：**

| 判定 | 含义 | 下一步 |
|:---|:---|:---|
| `effective` | 不同指令产生不同动作 | 数据设计成立，扩到 250 条 |
| `no_effect` | 动作几乎相同 | **停止加量**，先查数据设计 |
| `inconclusive` | 动作为全零 | checkpoint 未加载，先修训练 |

**`no_effect` 的排查顺序：**
1. 采集时颜色与位置是否绑定（红的总在左边）
2. 每条 episode 的 `task` 是否为真实指令，不是统一一条
3. 推理时的模板是否与训练完全一致

---

### 阶段 4：语音 + VLM 端到端

前提：有 `DEEPSEEK_API_KEY`、麦克风、音箱。

```bash
export DEEPSEEK_API_KEY="sk-..."

# 先单独测 VLM，确认延迟与 JSON 合法性
python -m voice_arm.vlm.client --image desk.jpg --text "把绿色的方块抓起来"

# 再跑编排器
python -m voice_arm.app.orchestrator --config ros2_ws/src/voice_arm_bringup/config/params.yaml
```

**通过标准：**
- VLM 单次 < 15 秒，JSON 可解析
- 说一句指令，状态机走完 `LISTENING → THINKING → EXECUTING → FEEDBACK → IDLE`
- 语音播报能听到

**失败排查：**
- VLM 超时 → 检查网络与 `timeout_s`
- 状态卡在 THINKING → 看 VLM 日志里的解析错误
- 无声音 → 先跑 `python -c "from voice_arm.audio import TTS; TTS().speak('测试')"`

---

### 阶段 5：真机迁移

只替换两处，其余代码不动：

1. `real.py` 实现 7 个方法（度 → 弧度）
2. `params.yaml` 里 `backend: real`、`port`、`camera_index`

**真机必须重测的项：**
- 标定（零位、方向、限位、夹爪行程）
- 相机曝光与对焦锁定
- 30 Hz 连续 30 分钟不掉线
- 抓取成功率

---

## 3. 环境清单

| 组件 | 版本 | 用途 | 是否必需 |
|:---|:---|:---|:---:|
| Ubuntu | 22.04 | ROS2 Humble 配套 | 必需 |
| Python | 3.10 | ROS2 Humble 配套 | 必需 |
| ROS2 | Humble | 节点通信 | 必需（跑 launch 时） |
| numpy | ≥1.24 | 数值计算 | 必需 |
| mujoco | ≥3.0 | 仿真渲染 | 可选（不装用合成图） |
| lerobot | ≥0.4 | 数据集与训练 | 阶段 2 起必需 |
| torch | ≥2.1 | 训练与推理 | 阶段 2 起必需 |
| opencv-python | ≥4.8 | 相机与编码 | 阶段 4 起必需 |
| openWakeWord | ≥0.6 | 唤醒词 | 阶段 4 必需 |
| funasr | ≥1.1 | 中文识别 | 阶段 4 必需 |
| edge-tts | ≥6.1 | 语音合成 | 阶段 4 必需 |
| 麦克风 / 音箱 | — | 语音链路 | 阶段 4 必需 |

---

## 4. 当前状态

| 阶段 | 状态 | 说明 |
|:---|:---:|:---|
| 0 冒烟测试 | ✅ | 37 个测试通过 |
| 1 数据采集 | ⚠️ | 合成图跑通；MuJoCo 模型未接入本机 |
| 2 训练与回放 | ❌ | 未跑（本机无 lerobot 与 checkpoint） |
| 3 语言条件 | ⚠️ | 脚本跑通，判定为 inconclusive（无策略） |
| 4 语音 + VLM | ❌ | 未跑（无 API Key 与音频设备） |
| 5 真机 | ❌ | 等硬件 |

**结论：代码与单测就绪，端到端尚未验证。**
阶段 1 之后的每一步都需要在 Ubuntu 环境里实际跑一次，当前只在 Windows 上完成了逻辑与格式验证。
