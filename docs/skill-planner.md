# 技能编排设计（最小拆句）

> 定位：LLM 只做「指令 → 技能调用」的转换，不参与视觉判断、动作规划与执行控制。
> 本文档定义职责边界、数据结构与实验设计。

---

## 一、定位

```
语音 → ASR → 文本
              ↓
      LLM（只做切分与转译）
  口语 → 技能调用数组
              ↓
      技能调度器（顺序队列）
              ↓
      VLA 技能（pick / place / move）
              ↓
          机械臂 → 语音反馈
```

**LLM 的三种职责，仅此而已：**

| 职责 | 说明 |
|:---|:---|
| 语义转译 | 「把绿的拿起来」→ `{"skill":"pick","target":"green"}` |
| 顺序切分 | 「先抓红的，再抓蓝的」→ 两个调用 |
| 参数归一 | 「左边」→ `{"skill":"place","region":"left"}` |

**LLM 不做：**

- 看图像
- 判断物体在哪
- 规划动作轨迹
- 决定失败后怎么办
- 处理条件分支（「如果……就……」）

---

## 二、数据结构

### 2.1 技能调用

```json
{
  "skill": "pick",
  "params": {"target": "green"},
  "raw": "把绿的拿起来"
}
```

| 字段 | 类型 | 取值 |
|:---|:---|:---|
| `skill` | string | `pick` / `place` / `move` |
| `params` | object | 见下表 |
| `raw` | string | 原始子句，用于日志与追问 |

### 2.2 技能参数

| 技能 | 参数 | 取值 |
|:---|:---|:---|
| `pick` | `target` | `red` / `green` / `blue` |
| `place` | `region` | `left` / `right` / `center` |
| `move` | `direction` | `left` / `right` / `up` / `down` |

### 2.3 LLM 输出（受 Schema 约束）

```json
{
  "calls": [
    {"skill": "pick",  "params": {"target": "red"},  "raw": "先抓红的"},
    {"skill": "place", "params": {"region": "left"}, "raw": "放到左边"},
    {"skill": "pick",  "params": {"target": "blue"}, "raw": "再抓蓝的"},
    {"skill": "place", "params": {"region": "right"},"raw": "放到右边"}
  ],
  "need_clarify": false,
  "clarify_question": null
}
```

**校验规则：**

- `calls` 非空，长度 ≤ 6（防失控）
- 每个 `skill` 在枚举内
- `params` 与技能匹配
- 解析失败 → 重试一次 → 仍失败则语音道歉

---

## 三、调度器

### 3.1 状态

```
IDLE → LISTENING → THINKING → QUEUED → EXECUTING → FEEDBACK → IDLE
                                    ↑        │
                                    └────────┘  逐条出队
```

| 状态 | 行为 |
|:---|:---|
| THINKING | 调 LLM，拿 `calls` |
| QUEUED | 队列非空，准备执行 |
| EXECUTING | 执行队首技能，完成后出队 |
| FEEDBACK | 全部完成或出错，播报 |

### 3.2 失败处理

| 情况 | 处理 |
|:---|:---|
| 单个技能失败 | 重试 1 次；仍失败则跳过，记录并在末尾播报 |
| 全部失败 | 播报「没做成」，回 IDLE |
| 队列超时 | 单技能 15 s 超时，整体 60 s |

**不做动态重规划**——这是明确的边界。

---

## 四、组合泛化原理

技能是**参数化**的：

```
pick(green)  ——训练过
pick(blue)   ——训练过
place(left)  ——训练过
place(right)——训练过
```

因此：

```
pick(green) → place(right)   ← 未训练过的组合，但由两个已训练技能串联而成
```

**这就是「未训练组合成功率 ≥50%」的依据**：不是模型学会了组合，而是调度器把两个独立技能按顺序执行。

**前提**：技能本身要能覆盖参数空间（三色 × 两区域），所以训练数据要按参数覆盖。

---

## 五、三组对比实验

| 组 | 内容 | 样本 | 指标 |
|:--:|:---|:--:|:---|
| A | 单技能：`pick(red)`、`pick(blue)`、`place(left)`、`place(right)` | 各 20 次 | 成功率 ≥70% |
| B | 已训练组合：训练数据中出现过的顺序 | 20 次 | 成功率 |
| C | **未训练组合**：训练数据中未出现的顺序 | 20 次 | 成功率 ≥50% |

**关键**：B 和 C 的区别必须在数据准备阶段严格控制——训练集里只能出现一部分组合。

**记录**：每次实验记录 `组合类型 / 成功与否 / 耗时 / 失败原因`，写入 `outputs/experiments/*.json`。

---

## 六、与现有代码的关系

| 模块 | 现状 | 改动 |
|:---|:---|:---|
| `vlm/client.py` | 输出单条 `Command` | 改为输出 `calls` 数组 |
| `vlm/schema.py` | `Command` 单任务 | 新增 `SkillCall` 与 `Plan` |
| `app/orchestrator.py` | 单任务状态机 | 增加队列与逐条执行 |
| `app/state_machine.py` | 六状态 | 加 `QUEUED` |
| `policy/runner.py` | 单技能 | 按 `skill` 参数选择模型或语言条件 |

**接口契约不变**：`RobotInterface` 的 7 个方法不动。

---

## 七、边界声明（写进论文）

> 本文的“任务分解”指**按时间顺序的指令切分**，不包含语义推理、条件分支与动态重规划。
> 复杂指令（如「如果左边有红的就拿红的，否则拿蓝的」）不在支持范围内。

**这样写的好处**：答辩时不会被追问「你的规划器能处理多复杂的情况」，因为边界已经声明。
