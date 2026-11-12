"""VLM 输出指令的结构定义与校验。

字段去向：
- 进入 VLA 输入：target.color / target.shape（拼成 "pick up the green cube"）
- 仅用于控制流：action / confidence / need_clarify / target_present
- 仅用于语音播报与日志：reply / position_hint / target.description
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Action(str, Enum):
    PICK_PLACE = "pick_place"
    PICK = "pick"
    PLACE = "place"
    STOP = "stop"


COLORS = {"red", "green", "blue", "any"}
SHAPES = {"cube", "cylinder", "any"}
ORDINALS = {"leftmost", "rightmost", "middle", "any"}
REGIONS = {"left", "right", "center", "any"}
POSITION_HINTS = {"left", "center", "right", "unknown"}


@dataclass
class Target:
    color: str = "any"
    shape: str = "any"
    ordinal: str = "any"
    description: str | None = None


@dataclass
class Destination:
    region: str = "any"
    relative_to: str | None = None


@dataclass
class Command:
    action: Action
    target: Target = field(default_factory=Target)
    destination: Destination = field(default_factory=Destination)
    reply: str = ""
    confidence: float = 0.0
    need_clarify: bool = False
    clarify_question: str | None = None
    target_present: bool = True
    position_hint: str = "unknown"

    def to_vla_instruction(self) -> str:
        """拼出进入 VLA 的固定模板。position_hint 与 reply 不参与。"""
        if self.action is Action.STOP:
            return "stop"
        if self.action is Action.PLACE:
            return f"place the object in the {self.destination.region} area"
        color = "" if self.target.color == "any" else self.target.color + " "
        shape = "object" if self.target.shape == "any" else self.target.shape
        return f"pick up the {color}{shape}"


class SchemaError(ValueError):
    """指令不合法。"""


def validate(raw: dict[str, Any]) -> Command:
    """校验 VLM 返回的原始 JSON，返回 Command；不合法时抛 SchemaError。"""
    if not isinstance(raw, dict):
        raise SchemaError("root must be an object")

    try:
        action = Action(raw["action"])
    except (KeyError, ValueError) as exc:
        raise SchemaError(f"invalid or missing action: {exc}") from exc

    t = raw.get("target") or {}
    target = Target(
        color=t.get("color", "any"),
        shape=t.get("shape", "any"),
        ordinal=t.get("ordinal", "any"),
        description=t.get("description"),
    )
    if target.color not in COLORS:
        raise SchemaError(f"invalid target.color: {target.color}")
    if target.shape not in SHAPES:
        raise SchemaError(f"invalid target.shape: {target.shape}")
    if target.ordinal not in ORDINALS:
        raise SchemaError(f"invalid target.ordinal: {target.ordinal}")
    if not target.description and target.color == "any" and target.ordinal == "any":
        raise SchemaError("target needs description or a structured constraint")

    d = raw.get("destination") or {}
    dest = Destination(region=d.get("region", "any"), relative_to=d.get("relative_to"))
    if dest.region not in REGIONS:
        raise SchemaError(f"invalid destination.region: {dest.region}")

    conf = float(raw.get("confidence", 0.0))
    if not 0.0 <= conf <= 1.0:
        raise SchemaError("confidence must be within [0, 1]")

    hint = raw.get("position_hint", "unknown")
    if hint not in POSITION_HINTS:
        raise SchemaError(f"invalid position_hint: {hint}")

    return Command(
        action=action,
        target=target,
        destination=dest,
        reply=raw.get("reply", ""),
        confidence=conf,
        need_clarify=bool(raw.get("need_clarify", False)),
        clarify_question=raw.get("clarify_question"),
        target_present=bool(raw.get("target_present", True)),
        position_hint=hint,
    )
