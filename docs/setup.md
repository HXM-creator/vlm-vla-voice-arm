# 环境搭建（Ubuntu 22.04 + ROS 2 Humble）

## 1. 安装 ROS2 Humble

```bash
sudo apt install software-properties-common
sudo add-apt-repository universe
sudo apt update && sudo apt install curl -y

sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
  http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update
sudo apt install ros-humble-desktop python3-colcon-common-extensions -y
```

国内网络慢可用清华镜像替换 `packages.ros.org`。

## 2. 安装项目依赖

```bash
sudo apt install python3-numpy python3-yaml python3-opencv -y
pip install -e "ros2_ws/src/voice_arm_core[dev]"
```

训练依赖（可选）：

```bash
pip install torch torchvision lerobot
```

## 3. 构建工作空间

```bash
cd ros2_ws
colcon build --symlink-install
source install/setup.bash
```

建议写进 `~/.bashrc`：

```bash
source /opt/ros/humble/setup.bash
source ~/vlm-vla-voice-arm/ros2_ws/install/setup.bash
```

## 4. 验证

```bash
# 单元测试（不需要 source ROS2）
make test

# 启动仿真
make sim

# 另开终端检查话题
ros2 topic list
ros2 topic hz /robot/joint_command
```

## 5. 串口权限（真机）

```bash
sudo usermod -aG dialout $USER
```

重新登录后生效。

## 6. 环境变量

```bash
export DEEPSEEK_API_KEY="sk-..."
```

不要写进代码或提交到仓库。


## 7. 仿真环境（可选）

仿真不依赖真机，用来在硬件到货前跑通链路。

```bash
pip install "mujoco>=3.0"
```

模型已随仓库提供，位于 `ros2_ws/src/voice_arm_core/voice_arm/sim/assets/`，无需下载。

模型下载后，把 `params.yaml` 里的 `sim_xml` 指向场景文件：

```yaml
robot_node:
  ros__parameters:
    sim_xml: ros2_ws/src/voice_arm_core/voice_arm/sim/assets/scene.xml
```

验证：

```bash
make sim
ros2 topic hz /robot/status
```

若日志出现「mujoco 未安装」或「模型不存在」，会回退到合成图像，不报错。

### 相机名对应

接口相机名 `front` / `wrist` 与 MuJoCo XML 里的相机名可能不同，映射在
`robot/sim.py` 的 `DEFAULT_CAMERA_MAP` 中：

```python
DEFAULT_CAMERA_MAP = {"front": "front_cam", "wrist": "wrist_cam"}
```

模型里的相机名请用 `python -c "import mujoco; m=mujoco.MjModel.from_xml_path('...'); print([mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_CAMERA, i) for i in range(m.ncam)])"` 查。
