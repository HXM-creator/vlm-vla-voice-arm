import pytest

from voice_arm.app.state_machine import InvalidTransition, State, StateMachine


def test_normal_flow():
    sm = StateMachine()
    for nxt in [State.LISTENING, State.THINKING, State.EXECUTING,
                State.FEEDBACK, State.IDLE]:
        sm.transition(nxt)
    assert sm.state is State.IDLE


def test_clarify_branch():
    sm = StateMachine(State.THINKING)
    sm.transition(State.CONFIRMING)
    sm.transition(State.LISTENING)
    assert sm.state is State.LISTENING


def test_invalid_transition():
    sm = StateMachine(State.IDLE)
    with pytest.raises(InvalidTransition):
        sm.transition(State.EXECUTING)
