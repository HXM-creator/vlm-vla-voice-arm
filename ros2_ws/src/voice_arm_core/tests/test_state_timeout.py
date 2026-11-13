"""状态机超时行为：用假时钟，不真实等待。"""
import pytest

from voice_arm.app.state_machine import State, StateMachine, TIMEOUTS


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_timeout_returns_to_idle():
    clock = FakeClock()
    sm = StateMachine(State.THINKING, clock=clock)
    clock.advance(TIMEOUTS[State.THINKING] + 1)
    assert sm.tick() is True
    assert sm.state is State.IDLE


def test_no_timeout_within_window():
    clock = FakeClock()
    sm = StateMachine(State.THINKING, clock=clock)
    clock.advance(TIMEOUTS[State.THINKING] - 1)
    assert sm.tick() is False
    assert sm.state is State.THINKING


def test_idle_never_times_out():
    clock = FakeClock()
    sm = StateMachine(State.IDLE, clock=clock)
    clock.advance(10_000)
    assert sm.tick() is False
    assert sm.state is State.IDLE


def test_timeout_bypasses_transition_table():
    """EXECUTING 不能直接回 IDLE 之外的任意状态，但超时必须能强制回 IDLE。"""
    clock = FakeClock()
    sm = StateMachine(State.EXECUTING, clock=clock)
    clock.advance(TIMEOUTS[State.EXECUTING] + 1)
    assert sm.tick() is True
    assert sm.state is State.IDLE


def test_entering_state_resets_timer():
    clock = FakeClock()
    sm = StateMachine(State.IDLE, clock=clock)
    sm.transition(State.LISTENING)
    clock.advance(5)
    sm.transition(State.THINKING)
    assert sm.elapsed() == pytest.approx(0.0)
    clock.advance(5)
    assert sm.tick() is False  # THINKING 只过了 5 秒
