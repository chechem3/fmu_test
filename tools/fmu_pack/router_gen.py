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

模板: tools/fmu_pack/templates/fmi2_router.h.j2
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader


# ---- Jinja2 环境 ----
_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)
_ROUTER_TEMPLATE = _env.get_template("fmi2_router.h.j2")


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
    model_cfg = config.get("model", {})
    state_type = model_cfg.get("state_type", f"{fmi['modelIdentifier']}_State")

    content = _ROUTER_TEMPLATE.render(
        model_identifier=fmi["modelIdentifier"],
        state_type=state_type,
        variables=config.get("variables", []),
    )

    output_path = Path(output_dir) / "fmi2_router.h"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path
