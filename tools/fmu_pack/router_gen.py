"""VR 路由头生成器 —— 从 fmu.yaml 生成 fmi2_router.h

生成内容:
  1. valueReference 枚举 (typedef enum { VR_TAU = 1, VR_U = 2, ... })
  2. getReal 路由函数 (static inline, switch-case 分发)
  3. setReal 路由函数 (static inline, 仅 input/parameter 可写)

设计要点:
  - 路由函数使用用户定义的状态结构体类型（通过 model.state_type 指定）
  - 路由函数声明为 static inline，避免链接冲突
  - output 变量不出现在 setReal 路由中（FMI 规范: output 只读）
  - 生成的枚举与 modelDescription.xml 中的 valueReference 一一对应
"""

from pathlib import Path
from typing import Any


def generate_router_header(config: dict[str, Any], output_dir: Path) -> Path:
    """生成 fmi2_router.h，包含 vr ↔ 字段偏移的静态路由表

    路由表采用 switch-case 结构，编译器会优化为跳转表。
    每个变量的 name 直接映射为状态结构体的同名字段。

    Args:
        config: fmu.yaml 解析后的配置字典
        output_dir: 头文件输出目录（通常是项目 include/ 目录）

    Returns:
        生成的 fmi2_router.h 文件路径
    """
    fmi = config["fmi"]
    variables: list[dict] = config["variables"]
    mi = fmi["modelIdentifier"]  # 模型标识符，用于命名前缀
    model_cfg = config.get("model", {})
    # 用户模型的状态结构体类型名，默认 {modelIdentifier}_State
    state_type = model_cfg.get("state_type", f"{mi}_State")

    # ---- 构建 valueReference 枚举 ----
    enum_lines: list[str] = []
    enum_lines.append(f"/* {mi} 变量 valueReference 枚举 —— 由 fmu-pack 自动生成 */")
    enum_lines.append("typedef enum {")

    vr_cases_get: list[str] = []  # getReal 的 case 分支
    vr_cases_set: list[str] = []  # setReal 的 case 分支

    for var in variables:
        name = var["name"]
        vr = var["vr"]
        vtype = var.get("type", "Real")
        causality = var.get("causality", "local")

        # 首期只支持 Real 类型变量
        if vtype != "Real":
            continue

        # 枚举项: VR_<NAME> = <vr>
        enum_name = f"VR_{name.upper()}"
        enum_lines.append(f"    {enum_name} = {vr},  /* {causality} */")

        # getReal 路由: 从状态结构体读取字段值
        vr_cases_get.append(f"        case {enum_name}: value[i] = state->{name}; break;")

        # setReal 路由: 仅 input 和 parameter 可写入
        if causality in ("input", "parameter"):
            vr_cases_set.append(f"        case {enum_name}: state->{name} = value[i]; break;")

    enum_lines.append(f"    VR_COUNT = {len(variables)}")
    enum_lines.append(f"}} {mi}_VR;")
    enum_lines.append("")

    # ---- 组装完整头文件 ----
    # 路由函数直接使用用户模型的结构体类型（state_type），不自行定义结构体
    header = f"""#ifndef FMI2_ROUTER_H_
#define FMI2_ROUTER_H_

/* ============================================================
 * fmi2_router.h —— VR 路由表（由 fmu-pack 自动生成，勿手动编辑）
 * 模型: {mi}
 * 变量数: {len(variables)}
 * 状态类型: {state_type}
 * ============================================================ */

#include "fmi2TypesPlatform.h"
#include "user_model.h"

/* ---- valueReference 枚举 ---- */
{chr(10).join(enum_lines)}

/* ---- getReal 路由（内联函数） ---- */
static inline void {mi}_route_getReal({state_type}* state,
                                       const fmi2ValueReference vr[],
                                       size_t nvr,
                                       fmi2Real value[]) {{
    for (size_t i = 0; i < nvr; i++) {{
        switch (vr[i]) {{
{chr(10).join(vr_cases_get)}
            default: break;
        }}
    }}
}}

/* ---- setReal 路由（内联函数） ---- */
static inline void {mi}_route_setReal({state_type}* state,
                                       const fmi2ValueReference vr[],
                                       size_t nvr,
                                       const fmi2Real value[]) {{
    for (size_t i = 0; i < nvr; i++) {{
        switch (vr[i]) {{
{chr(10).join(vr_cases_set) if vr_cases_set else '            default: break;'}
            default: break;
        }}
    }}
}}

#endif /* FMI2_ROUTER_H_ */
"""

    output_path = output_dir / "fmi2_router.h"
    output_path.write_text(header, encoding="utf-8")
    return output_path
