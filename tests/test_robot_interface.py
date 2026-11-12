import numpy as np
import pytest

from voice_arm.robot.interface import RobotInterface
from voice_arm.robot.sim import SimRobot


def test_sim_implements_interface():
    assert issubclass(SimRobot, RobotInterface)
    robot = SimRobot()
    assert robot.connect() is True


def test_joint_roundtrip():
    robot = SimRobot()
    robot.connect()
    q = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6], dtype=np.float32)
    robot.set_joint_positions(q)
    np.testing.assert_allclose(robot.get_joint_positions(), q)


def test_joint_shape_check():
    robot = SimRobot()
    with pytest.raises(ValueError):
        robot.set_joint_positions(np.zeros(3, dtype=np.float32))


def test_gripper_clip():
    robot = SimRobot()
    robot.set_gripper(1.5)
    assert robot.get_gripper_state() == 1.0


def test_frames_keys():
    frames = SimRobot().get_frames()
    assert set(frames) == {"front", "wrist"}
    assert frames["front"].ndim == 3
