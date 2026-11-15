# 技能编排设计（做到 L1）

> 定位：LLM 只做「指令 → 技能调用」的转换；指代不明时单独调用 VLM 确认，
> LLM 本身不看图、不规划动作、不做失败决策。

---

## 一、能力分级

| 级别 | 能力 | 例子 | 关键实现 | 工作量 | 预期成功率 |
|:--:|:---|:---|:---|:--:|:--:|
| **L0** | 顺序切分 | 「先抓红的，再抓蓝的」 | 连接词切句 + LLM 兜底 | 3–5 天 | 95%+ |
| **L1** | L0 + 参数填充 + 指代消解 | 「把左边那个放到右边」 | 调用 VLM 确认指代 | +1 周 | 80% |
| L2 | 条件分支 | 「如果左边有红的就拿红的」 | 调度器支持 if/else | 2–3 周 | 60% |
| L3 | 开放式规划 | 「把桌子收拾干净」 | 任务知识库 + 状态查询 | 4–6 周 | 30% |
| L4 | 动态重规划 | 失败后自己换策略 | 闭环反馈 + 重规划 | 研究级 | 不可控 |

**本项目做到 L1。**

---

## 二、为什么只做到 L1

| 原因 | 说明 |
|:---|:---|
| **演示稳定性** | L1 预期 80%，L2 预期 60%，L3 只有 30%。答辩现场十次错三次以上很难看 |
| **边界清晰** | L1 能一句话说清「做什么、不做什么」，L2 以上边界模糊，答辩追问难答 |
| **与已有能力匹配** | VLM 做语义确认、VLA 做动作执行，L1 正好是这两层的组合，不需要新增模型 |
| **时间成本** | L1 约 1–2 周；L2 起每级翻倍，而论文周期只剩 5 个月 |

**L2 以上不是「难」，是「不值得」。**

---

## 三、L1 的架构

```
语音 → ASR → 文本
              ↓
      LLM（只切分 + 提参数）
  口语 → 技能调用数组（可能含模糊指代）
              ↓
    ┌─────────┴─────────┐
    │ 指代是否明确？      │
    └────┬──────────┬───┘
      明确 │          │ 模糊
         ↓          ↓
    直接入队    VLM 消解（看画面确认）
                    ↓
              补全参数后入队
                    ↓
            技能调度器（顺序队列）
                    ↓
            VLA 技能（pick / place / move）
                    ↓
                机械臂 → 语音反馈
```

**关键：LLM 仍然不看图。** 指代消解由 VLM 单独完成，两者职责不重叠。

---

## 四、L1 的三种能力

### 4.1 顺序切分（L0）

```
输入：「先抓红的放到左边，再抓蓝的放到右边」
输出：[pick(red), place(left), pick(blue), place(right)]
```

**实现**：连接词（然后 / 再 / 接着 / 之后）切句，每句单独解析。LLM 兜底处理不规则表述。

### 4.2 参数填充

| 输入 | 提取 | 说明 |
|:---|:---|:---|
| 「抓红色的」 | `pick(target=red)` | 颜色 |
| 「放到右边」 | `place(region=right)` | 区域 |
| 「拿最左边的东西」 | `pick(ordinal=leftmost)` | 序数 |

### 4.3 指代消解（L1 的核心）

```
输入：「把左边那个放到右边」
LLM 输出：{skill: "pick", params: {ordinal: "leftmost"}, ambiguous: true}
                ↓
VLM 看画面：「画面左侧是一个绿色方块」
                ↓
补全：{skill: "pick", params: {target: "green"}}
                ↓
入队执行
```

**触发条件**：参数里只有位置/序数，没有颜色或形状。

**VLM 只回答一个问题**：「画面左侧是什么颜色/形状」。不做定位、不给坐标。

---

## 五、数据结构

### 5.1 技能调用

```json
{
  "skill": "pick",
  "params": {"target": "green", "ordinal": null},
  "raw": "把左边那个",
  "ambiguous": false
}
```

| 字段 | 类型 | 取值 |
|:---|:---|:---|
| `skill` | string | `pick` / `place` / `move` |
| `params.target` | string? | `red` / `green` / `blue` |
| `params.region` | string? | `left` / `right` / `center` |
| `params.ordinal` | string? | `leftmost` / `rightmost` |
| `raw` | string | 原始子句 |
| `ambiguous` | bool | 需要 VLM 消解时为 true |

### 5.2 LLM 输出

```json
{
  "calls": [
    {"skill": "pick",  "params": {"ordinal": "leftmost"}, "raw": "左边那个", "ambiguous": true},
    {"skill": "place", "params": {"region": "right"},      "raw": "放到右边", "ambiguous": false}
  ],
  "need_clarify": false,
  "clarify_question": null
}
```

**校验规则：**

- `calls` 非空，长度 ≤ 6
- `skill` 在枚举内
- `ambiguous=true` 时，`params` 必须含 `ordinal` 或 `region`
- 解析失败 → 重试一次 → 仍失败语音道歉

---

## 六、调度器

### 6.1 状态

```
IDLE → LISTENING → THINKING → RESOLVING → QUEUED → EXECUTING → FEEDBACK → IDLE
                                  │                    │
                                  └─ 指代消解           └─ 逐条出队
```

| 状态 | 行为 |
|:---|:---|
| THINKING | 调 LLM 拿 `calls` |
| RESOLVING | 对 `ambiguous=true` 的调用调 VLM 补全 |
| QUEUED | 队列就绪 |
| EXECUTING | 执行队首，完成后出队 |
| FEEDBACK | 播报结果 |

### 6.2 失败处理

| 情况 | 处理 |
|:---|:---|
| 单个技能失败 | 重试 1 次；仍失败则跳过并记录 |
| 指代消解失败 | 追问「你说的是哪个？」 |
| 队列超时 | 单技能 15 s，整体 60 s |
| 全部失败 | 播报「没做成」，回 IDLE |

**不做动态重规划。**

---

## 七、组合泛化

技能参数化：

```
pick(green)   ← 训练过
pick(blue)    ← 训练过
place(left)   ← 训练过
place(right)  ← 训练过
```

因此：

```
pick(green) → place(right)   ← 未训练过的组合，由两个已训练技能串联
```

**这就是「未训练组合成功率 ≥50%」的依据**：泛化来自调度器，不是模型学会了组合。

**前提**：技能要覆盖参数空间（三色 × 两区域），数据采集按参数分层。

---

## 八、三组对比实验

| 组 | 内容 | 样本 | 指标 |
|:--:|:---|:--:|:---|
| A | 单技能：`pick(red)`、`pick(blue)`、`place(left)`、`place(right)` | 各 20 次 | ≥70% |
| B | 已训练组合：训练集出现过的顺序 | 20 次 | — |
| C | **未训练组合**：训练集未出现的顺序 | 20 次 | ≥50% |

**控制点**：训练集只出现部分组合，测试集包含未出现的组合。

**记录**：`组合类型 / 成功与否 / 耗时 / 失败原因`，写入 `outputs/experiments/*.json`。

---

## 九、与现有代码的关系

| 模块 | 现状 | 改动 |
|:---|:---|:---|
| `vlm/client.py` | 输出单条 `Command` | 改为输出 `calls` 数组 |
| `vlm/schema.py` | `Command` 单任务 | 新增 `SkillCall`、`Plan` |
| `app/state_machine.py` | 六状态 | 加 `RESOLVING`、`QUEUED` |
| `app/orchestrator.py` | 单任务 | 加队列、指代消解分支 |
| `policy/runner.py` | 单技能 | 按 `skill` 选择语言条件 |

**`RobotInterface` 的 7 个方法不动。**

---

## 十、边界声明（写进论文）

> 本文的「任务分解」指**按时间顺序的指令切分与参数补全**，
> 不包含条件分支（if/else）、开放式规划与动态重规划。
>
> 指代消解由视觉语言模型单独完成，语言模型本身不处理图像。

**这样写的好处**：答辩时被问「能处理多复杂的指令」，边界是明确的，不会显得能力不足。
