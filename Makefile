SHELL := /bin/bash
WS := ros2_ws

.PHONY: help build test lint clean sim real setup

help:
	@echo "make build   # colcon build"
	@echo "make test    # 跑核心库单元测试（不需要 ROS2）"
	@echo "make sim     # 启动仿真节点组"
	@echo "make real    # 启动真机节点组"

build:
	cd $(WS) && colcon build --symlink-install

test:
	cd $(WS)/src/voice_arm_core && python -m pytest -q

lint:
	ruff check $(WS)/src

sim: build
	source $(WS)/install/setup.bash && ros2 launch voice_arm_bringup sim.launch.py

real: build
	source $(WS)/install/setup.bash && ros2 launch voice_arm_bringup real.launch.py

clean:
	rm -rf $(WS)/build $(WS)/install $(WS)/log
