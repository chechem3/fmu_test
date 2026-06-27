# MyModel

> FMI 2.0 Co-Simulation FMU，由 [fmu-pack](../../tools/fmu_pack/) 自动生成

## 功能

<!-- TODO: 描述此 FMU 的物理含义 / 数学模型 / 输入输出关系 -->
<!-- 示例: 一阶 RC 低通滤波器，时间常数 tau，输入 u，输出 y -->

## 变量

| name | vr | type | causality | start | 说明 |
|------|----|------|-----------|-------|------|
| `tau` | 1 | Real | parameter (fixed) | 1.0 | <!-- TODO --> |
| `u` | 2 | Real | input | — | <!-- TODO --> |
| `y` | 3 | Real | output | — | <!-- TODO --> |

## 构建

```bash
# 从项目根目录运行
fmu-pack build --xsd ../../third_party/fmi2/schema/fmi2ModelDescription.xsd
```

产物: `dist/MyModel.fmu`

## 测试

```bash
pip install fmpy
python test/my_fmu_test.py
```

## 项目结构

```
MyModel/
├── CMakeLists.txt         # 构建配置
├── fmu.yaml               # 模型描述（用户编辑）
├── README.md              # 本文件
├── include/
│   └── user_model.h       # 状态结构体 + 三个回调声明（用户编辑）
├── src/
│   ├── user_model.c       # 三个回调实现（用户编辑）
│   └── fmi2_adapter.c     # FMI 2.0 适配层（自动生成，勿编辑）
└── test/
    └── my_fmu_test.py     # 测试脚本（自动生成，用户填充）
```

## AI 交互实现逻辑

本 FMU 由 **fmu-pack** 工具链自动生成，用户**不写任何 FMI 2.0 样板代码**。
设计目标是：让 AI（如 Claude）能基于最小上下文帮用户生成可工作的 FMU。

### 用户编写的文件（3 个）

| 文件 | 内容 |
|------|------|
| `fmu.yaml` | 声明变量、参数、平台、链接 |
| `include/user_model.h` | 定义状态结构体 |
| `src/user_model.c` | 实现三个回调: `model_init / _step / _terminate` |

### 工具自动生成（每次 build 重新生成）

| 文件 | 来源 |
|------|------|
| `src/fmi2_adapter.c` | 模板: `tools/fmu_pack/templates/fmi2_adapter.c.j2` |
| `include/fmi2_router.h` | 模板: `tools/fmu_pack/templates/fmi2_router.h.j2` |
| `build/modelDescription.xml` | 从 fmu.yaml 渲染 |

### 适配层职责

`fmi2_adapter.c` 实现：
- 30+ 个 FMI 2.0 导出函数（`fmi2Instantiate` / `fmi2DoStep` / `fmi2GetReal` ...）
- 状态机: `instantiated` → `initMode` → `stepMode` → `terminated`
- 路由调用: `{prefix}_init` / `{prefix}_step` / `{prefix}_terminate` / `{model_identifier}_route_getReal` / `{model_identifier}_route_setReal`
- 未实现功能统一返回 `fmi2Error`

### AI 协作建议

让 AI 帮你实现一个新 FMU 时，给它的最小信息：

1. `fmu.yaml` 的目标结构（变量、参数）
2. 状态结构体字段
3. `init / step / terminate` 三个回调的物理逻辑

AI 不需要知道 FMI 2.0 的 30+ 函数或 state machine 细节。

### 改 fmu.yaml 后

直接 `fmu-pack build`，adapter 和 router 会自动重新生成。