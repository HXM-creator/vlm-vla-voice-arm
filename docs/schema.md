# VLM 指令 Schema

## 结构

```json
{
  "action": "pick_place",
  "target": {"color": "green", "shape": "cube", "ordinal": "leftmost", "description": "左边的绿色方块"},
  "destination": {"region": "right", "relative_to": null},
  "reply": "好的，我把绿色的方块放到右边",
  "confidence": 0.92,
  "need_clarify": false,
  "clarify_question": null
}
```

## 字段约束

| 字段 | 取值 | 必填 |
|---|---|---|
| `action` | pick_place / pick / place / stop | 是 |
| `target.color` | red / green / blue / any | 否 |
| `target.shape` | cube / cylinder / any | 否 |
| `target.ordinal` | leftmost / rightmost / middle / any | 否 |
| `target.description` | 自由文本 | 与结构化字段二选一 |
| `destination.region` | left / right / center / any | 是 |
| `reply` | 中文短句 | 是 |
| `confidence` | 0.0–1.0 | 是 |
| `need_clarify` | true / false | 是 |
| `clarify_question` | 字符串 | need_clarify 为真时必填 |

## 降级规则

1. 目标不唯一 → 追问。
2. 置信度 < 0.6 → 追问。
3. JSON 解析失败 → 重试一次，仍失败播报“我没听明白”。
4. 目标不存在 → 播报“我没有看到”。
5. 超出能力 → 播报“这个我还做不到”。
