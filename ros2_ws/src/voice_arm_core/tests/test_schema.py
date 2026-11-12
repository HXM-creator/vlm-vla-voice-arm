import pytest

from voice_arm.vlm.schema import Action, SchemaError, validate


def test_valid_command():
    cmd = validate({
        "action": "pick_place",
        "target": {"color": "green", "ordinal": "leftmost"},
        "destination": {"region": "right"},
        "reply": "好的",
        "confidence": 0.9,
        "need_clarify": False,
        "target_present": True,
        "position_hint": "left",
    })
    assert cmd.action is Action.PICK_PLACE
    assert cmd.target.color == "green"
    assert cmd.destination.region == "right"
    assert cmd.target_present is True
    assert cmd.position_hint == "left"


def test_invalid_action():
    with pytest.raises(SchemaError):
        validate({"action": "fly", "destination": {"region": "left"}})


def test_missing_target_constraint():
    with pytest.raises(SchemaError):
        validate({"action": "pick", "target": {}, "destination": {"region": "any"}})


def test_confidence_range():
    with pytest.raises(SchemaError):
        validate({
            "action": "pick", "target": {"color": "red"},
            "destination": {"region": "left"}, "confidence": 1.5,
        })


def test_invalid_position_hint():
    with pytest.raises(SchemaError):
        validate({
            "action": "pick", "target": {"color": "red"},
            "destination": {"region": "left"}, "position_hint": "up",
        })


def test_to_vla_instruction_template():
    cmd = validate({
        "action": "pick",
        "target": {"color": "green", "shape": "cube"},
        "destination": {"region": "any"},
        "position_hint": "right",
        "reply": "好的，右边的绿色方块",
    })
    assert cmd.to_vla_instruction() == "pick up the green cube"
    # 方位与回复不能进入 VLA 指令
    assert "right" not in cmd.to_vla_instruction()
    assert "好的" not in cmd.to_vla_instruction()


def test_to_vla_instruction_any():
    cmd = validate({
        "action": "pick",
        "target": {"color": "any", "shape": "any", "description": "桌子上的东西"},
        "destination": {"region": "any"},
    })
    assert cmd.to_vla_instruction() == "pick up the object"
