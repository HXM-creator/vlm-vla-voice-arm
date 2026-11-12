"""VLM 输出指令的结构定义与校验。"""
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

    return Command(
        action=action,
        target=target,
        destination=dest,
        reply=raw.get("reply", ""),
        confidence=conf,
        need_clarify=bool(raw.get("need_clarify", False)),
        clarify_question=raw.get("clarify_question"),
    )
