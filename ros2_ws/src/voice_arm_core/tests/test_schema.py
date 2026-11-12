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
    })
    assert cmd.action is Action.PICK_PLACE
    assert cmd.target.color == "green"
    assert cmd.destination.region == "right"


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
