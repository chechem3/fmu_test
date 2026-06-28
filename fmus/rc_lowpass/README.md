# rc_lowpass

> FMI 2.0 Co-Simulation FMU，由 [fmu-pack](../../tools/fmu_pack/) 自动生成

<!-- ⚠️ 此文件由 fmu-pack 自动生成。
     「功能」段和变量表「说明」列是用户编辑区域；
     每次 `fmu-pack build` 会重新渲染整个文件，导致用户编辑丢失。
     建议：用 git 跟踪修改，build 后 `git diff` 同步你的修改。 -->

## 功能

<!-- TODO: 描述此 FMU 的物理含义 / 数学模型 / 输入输出关系 -->
<!-- 示例：一阶 RC 低通滤波器，时间常数 tau，输入 u，输出 y -->
<!--      连续方程：dy/dt = (u - y) / tau -->
<!--      离散化（欧拉）：y_{k+1} = y_k + dt * (u_k - y_k) / tau -->

## 变量

| name | vr | type | causality | start | 说明 |
|------|----|------|-----------|-------|------|
| `tau` | 1 | Real | parameter (fixed) | 0.0 | <!-- TODO --> |
| `u` | 2 | Real | input | 0.0 | <!-- TODO --> |
| `y` | 3 | Real | output | — | <!-- TODO --> |

## 构建

```bash
# 从项目根目录运行
fmu-pack build --xsd ../../third_party/fmi2/schema/fmi2ModelDescription.xsd
```

产物：`dist/rc_lowpass.fmu`

## 测试

```bash
pip install fmpy numpy
python test/test_user_model.py
```

## 项目结构

```
rc_lowpass/
├── CMakeLists.txt         # 构建配置（init 生成，可改）
├── README.md              # 本文件（init 生成，用户编辑）
├── include/
│   └── user_model.h       # 3 结构体 + 3 回调声明（用户编辑）
├── src/
│   └── user_model.c       # 3 回调实现（用户编辑）
└── test/
    └── test_user_model.py # FMPy 测试脚本（init 生成骨架，用户填断言）

# 工具自动生成（用户不编辑）
build/
├── fmi2_adapter.c         # 从 user_model.h 渲染
├── modelDescription.xml   # 从 user_model.h 渲染
├── .fmu-guid              # GUID 持久化
└── <platform>/rc_lowpass.dll  # 编译产物

dist/
└── rc_lowpass.fmu  # 最终 FMU
```

## 使用说明

### 用户只写 3 个回调

| 回调 | 作用 |
|------|------|
| `model_init` | 初始化 3 个结构体（默认参数 / 输入 / 输出） |
| `model_step` | 单步推进；dt 由 importer 透传，**FMU 不在内部切分** |
| `model_terminate` | 释放动态分配资源（无 malloc 可留空） |

### 工具自动处理的事

- VR 枚举：按 `parameter → input → output` 顺序，从 1 起累加
- get/set 路由：Real / Integer / Boolean / String 全部类型
- FMI 2.0 状态机：`instantiated → initMode → stepMode → terminated`
- 30+ 个 FMI 2.0 导出函数（`fmi2Instantiate` / `fmi2DoStep` / `fmi2GetReal` ...）
<!-- USER_EDITED_AT=1782617612 -->
