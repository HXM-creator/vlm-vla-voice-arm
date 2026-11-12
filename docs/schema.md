# VLM 指令 Schema

## 结构

```json
{
  "action": "pick_place",
  "target": {
    "color": "green",
    "shape": "cube",
    "ordinal": "any",
    "description": "桌面上的绿色方块"
  },
  "destination": {
    "region": "right",
    "relative_to": null
  },
  "reply": "好的，我把绿色的方块放到右边",
  "confidence": 0.92,
  "need_clarify": false,
  "clarify_question": null,
  "target_present": true,
  "position_hint": "left"
}
```

## 字段约束

| 字段 | 取值 | 必填 | 去向 |
|:---|:---|:---:|:---|
| `action` | pick_place / pick / place / stop | 是 | 控制流 |
| `target.color` | red / green / blue / any | 否 | 拼入 VLA 指令 |
| `target.shape` | cube / cylinder / any | 否 | 拼入 VLA 指令 |
| `target.ordinal` | leftmost / rightmost / middle / any | 否 | 拼入 VLA 指令 |
| `target.description` | 自由文本 | 二选一 | 仅日志 |
| `destination.region` | left / right / center / any | 是 | 控制流 |
| `reply` | 中文短句 | 是 | 语音播报 |
| `confidence` | 0.0–1.0 | 是 | 控制流（低于阈值追问） |
| `need_clarify` | true / false | 是 | 控制流 |
| `clarify_question` | 字符串 | 条件必填 | 语音播报 |
| `target_present` | true / false | 是 | 控制流（false 不执行） |
| `position_hint` | left / center / right / unknown | 否 | **仅对话，不进 VLA** |

## VLA 实际收到的文本

VLM 的结构化字段会被拼成一句固定模板：

```
pick up the {color} {shape}
```

例如 `target.color = green`、`target.shape = cube` 时：

```
pick up the green cube
```

`position_hint` 与 `reply` **不进入** VLA 输入。

## 降级规则

| 情况 | 行为 |
|:---|:---|
| 目标不唯一 | `need_clarify = true`，追问 |
| 置信度 < 0.6 | 不执行，追问确认 |
| `target_present = false` | 播报"我没有看到……"，不执行 |
| JSON 解析失败 | 重试一次；仍失败播报"我没听明白" |
| 超出能力范围 | 播报"这个我还做不到"，保持待机 |
