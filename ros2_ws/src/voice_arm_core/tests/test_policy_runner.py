"""策略推理：未加载 checkpoint 时必须零动作回退，且不抛异常。"""
import numpy as np

from voice_arm.policy.runner import PolicyRunner


def _frames(h: int = 48, w: int = 64) -> dict:
    return {
        "front": np.zeros((h, w, 3), dtype=np.uint8),
        "wrist": np.zeros((h, w, 3), dtype=np.uint8),
    }


def test_zero_fallback_without_checkpoint():
    runner = PolicyRunner(action_chunk=4, dof=6)
    out = runner.predict(_frames(), "pick up the green cube")
    assert out.shape == (4, 6)
    assert np.all(out == 0.0)
    assert out.dtype == np.float32


def test_bad_checkpoint_does_not_raise():
    """路径不存在时只记录警告，保持零动作，不能阻止系统启动。"""
    runner = PolicyRunner(checkpoint="/nonexistent/checkpoint", action_chunk=8, dof=6)
    out = runner.predict(_frames(), "pick up the green cube")
    assert out.shape == (8, 6)
    assert np.all(out == 0.0)


def test_action_chunk_and_dof_respected():
    runner = PolicyRunner(action_chunk=16, dof=6)
    out = runner.predict(_frames(), "place the object in the right area")
    assert out.shape[0] == 16
    assert out.shape[1] == 6
