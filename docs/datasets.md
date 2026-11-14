# 公开数据集

> 用于在没有真机数据时验证训练流程与语言条件。

---

## 一、推荐清单

### 1. 官方 SO-101（SmolVLA 论文用）

**`lerobot/svla_so101_pickplace`**

| 项 | 值 |
|:---|:---|
| episodes | 50 |
| frames | 11,939 |
| fps | 30 |
| 相机 | `observation.images.up` + `side`（2 路） |
| 任务数 | 1（固定指令） |
| 体积 | 259 MB |
| 格式 | LeRobot **v2.1** |
| 许可 | Apache-2.0 |

**用途**：验证环境与训练流程，**不能验证语言条件**（单任务）。

### 2. 三色多任务（推荐优先用）

**`geonmin-kim/SO101-lv4-3color-cube-mat-to-mat-no-human-reset-v1`**

| 项 | 值 |
|:---|:---|
| 机器人 | SO-101 |
| 格式 | LeRobot **v3.0** ✅ |
| 相机 | `top` + `wrist`（2 路）✅ |
| 颜色 | **3 色方块** ✅ |
| 任务 | **multi-task** ✅ |
| 体积 | 1.05 GB |
| 许可 | Apache-2.0 |

**用途**：**可以验证语言条件**——不同颜色指令是否产生不同动作。

### 3. 其他可参考

| 数据集 | 特点 |
|:---|:---|
| `dreamscale-labs/so101-pick-place` | 通用抓放 |
| `shilpitha-03/so101_cube_in_box` | 方块进盒 |
| `Bapt120/so101_cup1` ~ `cup8` | 杯子系列 |
| `MarkoBrie/so101_banana` | 单物体 |
| `lerobot/svla_so100_pickplace` | SO-100 版（旧） |

---

## 二、下载

国内建议设置镜像：

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

首次加载会自动缓存到 `~/.cache/huggingface/lerobot/`：

```python
from lerobot.datasets import LeRobotDataset

ds = LeRobotDataset("geonmin-kim/SO101-lv4-3color-cube-mat-to-mat-no-human-reset-v1")
print("episodes:", ds.num_episodes)
print("fps:", ds.fps)
print("features:", list(ds.features))
```

**1 GB 数据，首次下载约 5–15 分钟**（取决于网络）。

---

## 三、v2.1 → v3.0 转换

官方那个是 v2.1，训练前可能需要转换：

```bash
python -m lerobot.scripts.convert_dataset_v21_to_v30 \
  --repo-id=lerobot/svla_so101_pickplace
```

**建议直接用三色那个（本来就是 v3.0），省一步。**

---

## 四、能验证什么、不能验证什么

| 项 | 官方 SO-101 | 三色多任务 | 你的真机 |
|:---|:---:|:---:|:---:|
| 训练流程 | ✅ | ✅ | — |
| 语言条件 | ❌ 单任务 | ✅ | 待测 |
| 相机位置一致 | ❌ | ❌ | ✅ |
| 物体一致 | ❌ | ❌ | ✅ |
| 视觉域一致 | ❌ | ❌ | ✅ |

**结论：能证明「方法可行」，不能替代「你的数据」。**

---

## 五、建议使用顺序

```
第 1 步：官方 SO-101 数据集 → 跑通训练（1 天）
        → 确认 lerobot 能装、能训、loss 下降

第 2 步：三色多任务 → 训练 + 语言条件验证（2 天）
        → check_language_conditioning.py
        → 拿到 effective / no_effect 结论

第 3 步：MuJoCo 自采数据 → 验证 sim 域内的语言条件（3 天）

第 4 步：真机 20 条微调（1 月）
```

**第 2 步是关键**——它能在没有真机、没有自采数据时，直接回答「语言条件能不能生效」。
