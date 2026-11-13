"""编排器：指令 -> VLM -> EXECUTING -> FEEDBACK 的线程协作。"""
import time

import pytest

from voice_arm.app.state_machine import State
from voice_arm.app.orchestrator import Orchestrator
from voice_arm.policy.runner import PolicyRunner
from voice_arm.robot.sim import SimRobot


def _cfg(action_chunk: int = 2) -> dict:
    return {
        "robot": {"backend": "sim", "dof": 6, "image_size": [64, 80],
                  "cameras": ["front", "wrist"]},
        "policy": {"action_chunk": action_chunk, "checkpoint": ""},
    }


def _wait_state(orch: Orchestrator, target: State, timeout_s: float = 3.0) -> State:
    deadline = time.monotonic() + timeout_s
    state = orch.sm.state
    while time.monotonic() < deadline:
        state = orch.run_once()
        if state is target:
            return state
        time.sleep(0.01)
    return state


def test_instruction_reaches_executing():
    orch = Orchestrator(SimRobot(image_size=(64, 80)),
                        PolicyRunner(action_chunk=2, dof=6), _cfg())
    orch.start()
    try:
        orch.submit_instruction("把绿色的方块放到右边")
        assert _wait_state(orch, State.EXECUTING) is State.EXECUTING
    finally:
        orch.stop()


def test_executes_then_returns_to_idle():
    orch = Orchestrator(SimRobot(image_size=(64, 80)),
                        PolicyRunner(action_chunk=2, dof=6), _cfg())
    orch.start()
    try:
        orch.submit_instruction("把绿色的方块放到右边")
        assert _wait_state(orch, State.FEEDBACK) is State.FEEDBACK
        assert _wait_state(orch, State.IDLE) is State.IDLE
    finally:
        orch.stop()


def test_multiple_instructions_do_not_crash():
    """连续下发多条指令，队列与线程不应异常。"""
    orch = Orchestrator(SimRobot(image_size=(64, 80)),
                        PolicyRunner(action_chunk=1, dof=6), _cfg(1))
    orch.start()
    try:
        for i in range(5):
            orch.submit_instruction(f"指令 {i}")
        time.sleep(0.2)
        for _ in range(50):
            orch.run_once()
            time.sleep(0.01)
    finally:
        orch.stop()
    assert orch.sm.state in set(State)


def test_stop_is_idempotent():
    orch = Orchestrator(SimRobot(image_size=(64, 80)),
                        PolicyRunner(action_chunk=1, dof=6), _cfg(1))
    orch.start()
    orch.stop()
    orch.stop()  # 不应抛异常
