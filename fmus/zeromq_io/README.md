# zeromq_io

> FMI 2.0 Co-Simulation FMU：ZeroMQ 数据桥，4 通道 +1 透传

> 此文件由 `fmu-pack init` 生成一次后由用户自行维护；后续 `fmu-pack build` 不会覆写。
> 如果改了 `user_model.h`（增删字段），需手动更新下方「变量表」和 `test/test_user_model.py`。

## 功能

把外部 ZeroMQ 网络的数据接入 FMU，并把 FMU 输出广播回 ZMQ 网络，**作为仿真器与外部系统（如 SCADA、HIL、Python 脚本）的实时数据桥**。

**逻辑模型**：纯代数 pass-through，4 通道独立 +1：

```
y[i] = x[i] + 1,   i = 0..3
```

每个 `fmi2DoStep` 周期：
1. 从 SUB socket 非阻塞读取**最新**一帧 JSON（多余帧丢弃，靠 `ZMQ_CONFLATE`）
2. 解析 `{"x":[v0,v1,v2,v3]}`，写入 `in->x0..x3`
3. 计算 `y[i] = x[i] + 1`，写入 `out->y0..y3`
4. 把 `{"y":[u0,u1,u2,u3]}` 推送到 PUB socket

> **无状态 / 无积分**：本 FMU 不维护时间累积状态，每步只做"读 → +1 → 发"。
> 若需要 RC 低通这类积分行为，请用 `fmus/rc_lowpass` 或在 `model_step` 内加状态变量。

## 变量

| name       | vr | type   | causality           | start  | 说明 |
|------------|----|--------|---------------------|--------|------|
| `sub_endpoint` | 1 | String | parameter (fixed)  | `tcp://localhost:5556` | SUB 连接的对端（外部 PUB 在跑） |
| `pub_endpoint` | 2 | String | parameter (fixed)  | `tcp://*:5555`         | PUB 绑定的本端端口（外部 SUB 来连） |
| `x0`        | 3  | Real   | input               | 0.0    | 输入通道 0 |
| `x1`        | 4  | Real   | input               | 0.0    | 输入通道 1 |
| `x2`        | 5  | Real   | input               | 0.0    | 输入通道 2 |
| `x3`        | 6  | Real   | input               | 0.0    | 输入通道 3 |
| `y0`        | 7  | Real   | output              | —      | 输出通道 0 = x0 + 1 |
| `y1`        | 8  | Real   | output              | —      | 输出通道 1 = x1 + 1 |
| `y2`        | 9  | Real   | output              | —      | 输出通道 2 = x2 + 1 |
| `y3`        | 10 | Real   | output              | —      | 输出通道 3 = x3 + 1 |

**通道数固定 4**：编译期常量 `N_CHANNELS = 4`，要扩到 N 路就在 `user_model.h` 里加 `x4..x{N-1}` / `y4..y{N-1}` 字段，并在 `model_step` 里把循环边界改成 `N_CHANNELS`（同步改 `user_model.c`）。**不要在 v2 adapter 范围里用 `double x[N]` 数组字段**——adapter 只对每个字段分配 1 个 VR，数组首元素之外写入不到。

## ZMQ 通信约定

### 拓扑

```
┌──────────────┐    PUB    ┌──────────────┐    SUB    ┌────────────┐
│  外部源        │ ───────► │  zeromq_io    │ ───────► │  外部消费    │
│  (Python/sim) │ tcp:5556  │   FMU (.dll)  │ tcp:5555 │ (Python/HMI)│
└──────────────┘           └──────────────┘           └────────────┘
                            ▲
                            │ fmi2SetReal / fmi2GetReal
                            │
                       ┌─────────┐
                       │ FMPy    │
                       │importer │
                       └─────────┘
```

- **FMU 的 PUB 绑 `pub_endpoint`**（默认 `tcp://*:5555`，等外部 SUB 来连）
- **FMU 的 SUB 连 `sub_endpoint`**（默认 `tcp://localhost:5556`，主动连外部 PUB）

> **为什么不反过来**：PUB 必须 bind / SUB 必须 connect，否则 `Slow joiner` 问题导致首条消息丢失。
> 如果要 PUB-connect-SUB-bind，外部需保证 PUB 先于 SUB 启动 100ms+。

### Socket 选项

| 选项 | 值 | 作用 |
|------|----|------|
| `ZMQ_CONFLATE` | 1 | SUB socket 只保留队列里**最新一条**消息；旧帧丢弃。适合"读最新输入"语义。 |
| `ZMQ_SNDTIMEO` | 0 | PUB send 非阻塞；下游慢时丢帧不阻塞仿真主线程。 |
| `ZMQ_LINGER` | 0 | terminate 时不等待未发完的消息。 |
| `ZMQ_RCVTIMEO` | 0 | SUB recv 非阻塞；本步没新消息就保持上一帧值。 |

### 消息格式

**外部 → FMU**（PUB，外部发）：
```json
{"x":[1.0, 2.0, 3.0, 4.0]}
```
- 字段 `x` 必须存在，元素个数必须等于 `N_CHANNELS`（4）
- 缺字段 / 元素数不对 → `model_step` 返回 `-1`，adapter 抛 `fmi2Error`

**FMU → 外部**（PUB，FMU 发）：
```json
{"y":[2.0, 3.0, 4.0, 5.0]}
```
- 每个步长结束发一次，元素是 `x[i] + 1`

### 解析器

C 端用 **cJSON**（单文件 ~3000 行，vendored 进 `src/cJSON.c`）做 JSON 解析。
或用更轻量的手写 parser（仅支持 `{"x":[...]}` 这一种格式，约 80 行）——首期用 cJSON 简单可靠。

## 构建

### 依赖

- libzmq 静态库：`third_party/zeromq/lib/libzmq.a`
- libzmq 头文件：`third_party/zeromq/include/zmq.h`
- cJSON（如选 cJSON）：vendored 到 `src/cJSON.{c,h}` 或用单文件 amalgamation

### CMake

`CMakeLists.txt`（**项目级**，与 RC 低通的 `C` project 不同，zeromq_io 需要 C++ runtime ABI）：

```cmake
cmake_minimum_required(VERSION 3.20)
project(zeromq_io C)

include_directories("${CMAKE_SOURCE_DIR}/include")
include_directories("${CMAKE_SOURCE_DIR}/../../third_party/fmi2/include")
include_directories("${CMAKE_SOURCE_DIR}/../../third_party/zeromq/include")
include_directories("${CMAKE_SOURCE_DIR}/build")

# 注意：libzmq 是 C++ 项目编译出来的 .a（带 C++ ABI），FMU 链接时需要 -lstdc++ -lpthread
add_library(zeromq_io SHARED
    src/user_model.c
    src/cJSON.c        # cJSON（如用）
    build/fmi2_adapter.c
)

target_link_libraries(zeromq_io PRIVATE
    "${CMAKE_SOURCE_DIR}/../../third_party/zeromq/lib/libzmq.a"
)

set_target_properties(zeromq_io PROPERTIES PREFIX "" SUFFIX ".dll")

if(WIN32)
    target_compile_definitions(zeromq_io PRIVATE "FMI2_Export=__declspec(dllexport)")
    if(MINGW)
        target_link_options(zeromq_io PRIVATE
            "-static-libgcc" "-static-libstdc++" "-static")
        target_link_libraries(zeromq_io PRIVATE stdc++ pthread)
    endif()
endif()
```

### 构建命令

```bash
fmu-pack build --xsd ../../third_party/fmi2/schema/fmi2ModelDescription.xsd
```

产物：`dist/zeromq_io.fmu`

## 测试

### 端到端测试拓扑

```
Python mock_publisher.py ── PUB tcp://*:5556 ──┐
                                              │ SUB
                                         zeromq_io FMU (FMPy 仿真)
                                              │ PUB
Python mock_subscriber.py ── SUB tcp://localhost:5555 ──┘
```

### 启动顺序

1. **先启动 Python mock_publisher.py**：在 5556 端口 PUB 周期发 `{"x":[...]}` 帧
2. **再启动 FMPy 仿真 `python test/test_user_model.py`**：通过 FMU 桥接
3. **Python mock_subscriber.py**：在 5555 端口收 `{"y":[...]}`，断言每个值 = x + 1

### FMPy 测试脚本

`test/test_user_model.py` 由 `fmu-pack init` 生成，但**用户需要在脚本里启动外部 publisher**：

```python
import subprocess, time, sys
# 启动外部 publisher（在另一个终端或后台）
p = subprocess.Popen([sys.executable, "test/mock_publisher.py"])

# 等 publisher 起来
time.sleep(0.5)

result = simulate_fmu(
    "dist/zeromq_io.fmu",
    start_time=0, stop_time=2, step_size=0.1,
    output=["y0", "y1", "y2", "y3"],
    # 不传 input —— FMU 的输入来自 ZMQ，不是 importer 的 input 数组
)

# 断言 y[i] 终值 ≈ 外部 publisher 最后发的 x[i] + 1
last_x = ...  # 从外部状态文件 / socket 读取
assert abs(result["y0"][-1] - (last_x[0] + 1)) < 1e-6
```

> **关键**：FMPy 的 `input` 参数对 zeromq_io **不适用**——输入走 ZMQ，不走 importer input。
> `simulate_fmu` 调用时 `input=None` 即可。

## 项目结构

```
zeromq_io/
├── CMakeLists.txt         # 构建配置（含 libzmq 链接）
├── README.md              # 本文件
├── include/
│   └── user_model.h       # 3 结构体 + 3 回调声明
├── src/
│   ├── user_model.c       # 3 回调实现（含 ZMQ SUB/PUB 逻辑 + cJSON 解析）
│   └── cJSON.c            # JSON 解析器（如选 cJSON）
└── test/
    ├── test_user_model.py # FMPy 测试脚本
    ├── mock_publisher.py  # 外部 ZMQ PUB 模拟器（提供测试输入）
    └── mock_subscriber.py # 外部 ZMQ SUB 监听器（断言测试输出）

# 工具自动生成
build/
├── fmi2_adapter.c         # 从 user_model.h 渲染
├── modelDescription.xml   # 从 user_model.h 渲染
├── .fmu-guid              # GUID 持久化
└── <platform>/zeromq_io.dll

dist/
└── zeromq_io.fmu
```

## 使用说明

### 用户只写 3 个回调

| 回调 | 作用 |
|------|------|
| `model_init` | 创建 zmq context、新建 SUB/PUB socket、解析 endpoint 参数、connect/bind、`ZMQ_CONFLATE` / `ZMQ_LINGER` 选项 |
| `model_step` | SUB recv（DONTWAIT） → cJSON 解析 → 写 `in->x0..x3` → 算 `out->y0..y3` → PUB send |
| `model_terminate` | close SUB/PUB socket、销毁 zmq context（注意 `zmq_ctx_term` 会阻塞到所有 socket 关闭） |

### 工具自动处理的事

- VR 枚举：按 `parameter → input → output` 顺序，从 1 起累加
- get/set 路由：Real / Integer / Boolean / **String**（sub_endpoint / pub_endpoint 是 char[64] → FMI String）
- FMI 2.0 状态机：`instantiated → initMode → stepMode → terminated`
- 30+ 个 FMI 2.0 导出函数

### 已知限制

1. **通道数固定 4**：扩到 N 路需改 `user_model.h` + `user_model.c`，并重新 `fmu-pack build`
2. **无消息时保持上帧值**：本步没收到新 JSON 时 `in->x*` 维持上次值；`out->y*` 也会跟着维持
3. **JSON 格式硬编码**：只支持 `{"x":[v0,v1,v2,v3]}` 这一个 schema；要做 topic / 多消息类型需扩 `model_step`
4. **没有时间戳 / 序号同步**：ZMQ 消息无时间戳，FMU 不知道输入是哪一时刻的；适合软实时仿真，硬实时需加 sequence number