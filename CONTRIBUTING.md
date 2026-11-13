# 协作约定

## 分支

- `main` 受保护，不直接推送
- 功能分支命名：`feat/<模块>-<简述>`，例如 `feat/robot-real-driver`
- 修复分支：`fix/<简述>`

## 提交信息

```
<类型>: <一句话说明>

<可选：详细说明>
```

类型：`feat` / `fix` / `docs` / `refactor` / `test` / `chore`

## 不能改的东西

以下三项一旦确定，改动会影响已采集的数据，必须双方确认：

1. `robot/interface.py` 的 7 个方法签名
2. `voice_arm_interfaces/msg/*.msg` 的字段
3. 相机名（`front` / `wrist`）与关节顺序

## 本地检查

```bash
make test        # 核心库单元测试，不需要 ROS2
make build       # colcon 构建
```

装 pre-commit 后提交会自动跑 ruff 与大文件检查：

```bash
pip install pre-commit && pre-commit install
```
