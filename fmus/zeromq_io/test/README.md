# zeromq_io test/

`zeromq_io` FMU 的测试工具集。按用途分三类：

## 1. 端到端测试（正常使用）

### `test_user_model.py`（**主测试入口**）
- **做什么**：启动 `mock_publisher`（ZMQ PUB）+ `mock_subscriber`（ZMQ SUB）作子进程，用 FMPy 仿真 FMU，验证 y = x + 1
- **何时跑**：每次改 user_model.c / CMakeLists.txt 后必跑
- **依赖**：`fmpy`、`pyzmq`（见项目根 `requirements.txt`）
- **运行**：
  ```bash
  python test/test_user_model.py
  ```
- **断言**：
  1. FMPy 输出 y 终值非零（说明 model_step 被调用）
  2. y 终值符合等差结构（y[i] = x[i] + 1）
  3. subscriber 收到的每条 y 消息都符合等差结构
  4. 前 100 条 sub 消息至少有 1 条匹配 pub 的 x（即 y[i] - 1 能反推回某条 pub x[i]）

### `mock_publisher.py`
- **做什么**：ZMQ PUB 5556，周期发 `{"x":[c, 2c, 3c, 4c], "seq": N}`
- **何时用**：被 `test_user_model.py` 作为子进程调用
- **单独运行**（调试用）：
  ```bash
  python test/mock_publisher.py --port 5556 --duration 5 --period 0.1 --log /tmp/pub.log
  ```

### `mock_subscriber.py`
- **做什么**：ZMQ SUB 5555，收 `{"y":[...]}`，断言等差并写日志
- **何时用**：被 `test_user_model.py` 作为子进程调用
- **单独运行**（调试用）：
  ```bash
  python test/mock_subscriber.py --port 5555 --timeout 5 --log /tmp/sub.log
  ```

---

## 2. 隔离测试（debug 用，不进 CI）

### `test_standalone.c`
- **做什么**：独立 C 程序，直接链 `third_party/zeromq/lib/libzmq.a`，验证 libzmq 静态库本身能不能正常 pub/sub
- **何时用**：怀疑 libzmq 编译坏了（`-DBUILD_SHARED=OFF` 没生效、符号错、ABI 不兼容等）
- **编译**：
  ```bash
  gcc -DZMQ_STATIC -o /tmp/test_sub.exe test/test_standalone.c \
      -I third_party/zeromq/include \
      third_party/zeromq/lib/libzmq.a \
      -lws2_32 -liphlpapi -lpthread -lstdc++ \
      -static-libgcc -static-libstdc++ -static
  ```
- **运行**（需 2 个终端 / 后台 + 前台）：
  ```bash
  # 终端 1
  /tmp/test_sub.exe sub
  # 终端 2
  /tmp/test_sub.exe pub
  ```
- **预期**：sub 收到 5 条 `{"x":[c,2c,3c,4c]}`，exit

**典型用途**：排除"libzmq 编译问题" vs "FMU 内部问题"。

### `test_fmu_direct.c`
- **做什么**：用 Windows `LoadLibrary` + `GetProcAddress` 直接加载 FMU DLL，调用 `model_init` / `model_step` / `model_terminate`，绕过 FMPy
- **何时用**：怀疑 FMPy 加载 DLL 行为异常；想精确控制 init/step 时序
- **编译**：
  ```bash
  gcc -o /tmp/test_direct.exe test/test_fmu_direct.c -I fmus/zeromq_io/include
  ```
- **运行**：
  ```bash
  # 需要先 build 出 DLL
  python run_fmu_pack.py build fmus/zeromq_io
  /tmp/test_direct.exe
  ```
- **预期**：
  - 现代码**会失败** `GetProcAddress("model_init")`，因为 v2 FMU 不导出 `model_xxx`（仅导出 `fmi2DoStep` 等 FMI 2.0 入口）
  - 这是一个**已知限制**，不是 bug；要直接调 model_xxx 需要改 user_model.c 加 `FMI2_Export`

**典型用途**：诊断"DLL 是否被正确加载 + 符号导出是否正常"。

---

## 3. 故障排查指引

遇到"FMU 收不到 ZMQ 消息"时，按下面顺序排查：

| 症状 | 怀疑 | 验证 |
|---|---|---|
| y 始终 = [1,1,1,1] | FMU 的 SUB 完全没收到 | 看 netstat 5556 有没有 LISTENING；看 FMU 端日志里 `lazy_init` 的 rc |
| y 非零但等于初始值 | FMPy 的 `start_values` 没生效 | 检查 XML 是否有 `initial="exact"`；检查 model_init 后 inst->p.sub_endpoint 是否被 setString 覆盖 |
| y 正确但 subscriber 收不到 | FMU 的 PUB 没绑定 | 看 netstat 5555 有没有 LISTENING；用 `test_standalone.c pub` 单独测 |
| subscriber 收到 0 条且 y 也错 | ZMQ bind 还在 lazy 阶段 | 在 user_model.c `lazy_init` 末尾加 `Sleep(500)`；或确认 model_step 在 `model_init` 之后有足够时间 |
| `__imp_*` 链接错误 | zmq.h 默认 `__declspec(dllimport)` | CMakeLists 加 `target_compile_definitions(... ZMQ_STATIC)` |
| 找不到 `select` / `WSAFDIsSet` | 缺 Winsock 库 | 链 `-lws2_32` |
| 找不到 `if_nametoindex` | 缺 IP helper 库 | 链 `-liphlpapi` |
| 找不到 `pthread_*` | 缺 pthread | 链 `-lpthread`（MinGW） |
| undefined reference `__cxx_*` | libzmq 是 C++ 编译的 | 链 `-lstdc++` 且 `project(... C CXX)` |

---

## 4. 时间线

本目录的 5 个文件来自 v2 工具链 + 端到端测试建立：

| 文件 | 来源 |
|---|---|
| `test_user_model.py` | `fmu-pack init` 生成骨架后用户填入端到端编排逻辑 |
| `mock_publisher.py` | 用户手写（模拟外部 PUB 源） |
| `mock_subscriber.py` | 用户手写（模拟外部 SUB 消费端 + 断言） |
| `test_standalone.c` | debug 阶段排查 libzmq 编译问题，保留作回归测试 |
| `test_fmu_direct.c` | debug 阶段排查 DLL 加载问题，保留作 debug 工具 |