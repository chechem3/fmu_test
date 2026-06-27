# zmqsub

> FMI 2.0 Co-Simulation FMU，由 [fmu-pack](../../tools/fmu_pack/) 自动生成

## 功能

ZeroMQ 订阅 FMU。通过 ZMQ SUB socket 接收外部发布端的浮点数据，
作为 FMU 的输入信号并通过 FMI 接口暴露给仿真器。

**核心行为**:
```
1. 实例化时: 创建 ZMQ context + SUB socket, 连接到 tcp://localhost:5555
2. 每个 doStep:
   a. 非阻塞轮询 ZMQ (timeout=0)
   b. 若有新消息到达: 解析为 double
   c. y = received_value × gain
3. 终止时: 关闭 socket, 销毁 context
```

**典型场景**: 实时仿真与外部数据源（如 OPC UA 网关、MATLAB/Simulink、Python 脚本）联动。

## 变量

| name | vr | type | causality | start | 说明 |
|------|----|------|-----------|-------|------|
| `gain`        | 1 | Real | parameter (tunable) | 1.0 | 输出增益 |
| `y`           | 2 | Real | output     | —     | 处理后输出 = raw_value × gain |
| `raw_value`   | 3 | Real | local      | —     | 从 ZMQ 接收的原始值 |
| `has_new_data` | 4 | Real | output     | —     | 上一步是否有新数据（0/1） |

## 依赖

- [ZeroMQ 4.3.5 静态库](../../third_party/zeromq/) — 已编译为 `libzmq.a`
- 外部 ZMQ PUB 端点（默认 `tcp://localhost:5555`，可在 `user_model.c` 修改）

## 构建

```bash
# 从项目根目录运行
fmu-pack build --xsd ../../third_party/fmi2/schema/fmi2ModelDescription.xsd
```

产物: `dist/zmqsub.fmu`

## 使用示例

1. 启动 ZMQ 发布端（外部程序）：
   ```python
   import zmq, time
   ctx = zmq.Context()
   pub = ctx.socket(zmq.PUB)
   pub.bind("tcp://*:5555")
   while True:
       pub.send_string(str(time.time()))  # 发送时间戳
       time.sleep(0.1)
   ```

2. 在仿真器（如 FMPy）中加载 `zmqsub.fmu`，观察 `y` 变化。

## 项目结构

```
zeromq_sub/
├── CMakeLists.txt         # 构建配置（含 ZeroMQ 静态链接）
├── fmu.yaml               # 模型描述（用户编辑）
├── README.md              # 本文件
├── include/
│   └── user_model.h       # ZmqSubState 结构体 + 三个回调（用户编辑）
├── src/
│   ├── user_model.c       # ZMQ SUB socket 实现（用户编辑）
│   └── fmi2_adapter.c     # FMI 2.0 适配层（自动生成，勿编辑）
└── test/
    └── my_fmu_test.py     # 测试脚本（自动生成）
```

## AI 交互实现逻辑

本 FMU 由 **fmu-pack** 工具链自动生成，用户**不写任何 FMI 2.0 样板代码**。

### 用户编写的文件（3 个）

| 文件 | 内容 |
|------|------|
| `fmu.yaml` | 声明变量、ZeroMQ 链接依赖 |
| `include/user_model.h` | 状态结构体 `ZmqSubState`（含 ZMQ 句柄） |
| `src/user_model.c` | ZMQ 初始化、轮询、解析；三个回调: `zmqsub_init / _step / _terminate` |

### 工具自动生成

| 文件 | 来源 |
|------|------|
| `src/fmi2_adapter.c` | 模板: `tools/fmu_pack/templates/fmi2_adapter.c.j2` |
| `include/fmi2_router.h` | 模板: `tools/fmu_pack/templates/fmi2_router.h.j2` |
| `build/modelDescription.xml` | 从 fmu.yaml 渲染 |
| `CMakeLists.txt` | 含 `LINKER_LANGUAGE CXX`（libzmq.a 是 C++ 库） |

### 关键技术点

**静态链接 ZeroMQ**: `libzmq.a` 嵌入 `zmqsub.dll`，importer 只需加载一个 DLL。

**C/C++ 混编**:
- `user_model.c` 是 C 源文件，调用 C++ 库
- CMake `project(zmqsub C CXX)` + `LINKER_LANGUAGE CXX` 强制用 g++ 链接
- `ZMQ_STATIC` 宏避免 `__imp_` 前缀

**`fmi2DoStep` 非阻塞轮询**: 适配层在每次步进时调 `zmq_poll(timeout=0)`，
不阻塞 importer 的仿真循环。

### AI 协作建议

让 AI 帮你实现类似 ZMQ/REST/MQTT 等外部数据源 FMU 时，给它：

1. `fmu.yaml` 变量定义
2. 数据源 API（C 头文件或 ABI）
3. 三个回调的协议逻辑

`fmu-pack` 负责 FMI 样板；你（或 AI）只关心数据收发。
