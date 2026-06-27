"""FMI 2.0 适配层代码生成器

从 fmu.yaml 生成完整的 fmi2_adapter.c:
  - 30+ 个 FMI 2.0 导出函数
  - 状态机 (instantiated → initMode → stepMode → terminated)
  - 回调调用: {prefix}_init / _step / _terminate
  - 路由调用: {modelIdentifier}_route_getReal / _setReal

模板: tools/fmu_pack/templates/fmi2_adapter.c.j2
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
_ADAPTER_TEMPLATE = _env.get_template("fmi2_adapter.c.j2")


# ---- user_model.h 骨架模板（小，留在 Python 里）----
# 用户模型统一用 model_init / model_step / model_terminate 三个回调，
# 状态用 void* opaque（状态结构体在 .h 中定义，router 需要 cast）
USER_MODEL_H_TEMPLATE = """/* ============================================================
 * user_model.h —— 用户模型接口
 *
 * 三个回调约定（所有 FMU 统一使用 model_* 前缀，状态用 void*）:
 *   void* model_init(void);                                 // 用户 malloc 状态
 *   int   model_step(void* state, double t, double dt);   // 单步推进
 *   void  model_terminate(void* state);                     // 用户 free 状态
 *
 * 状态结构体名字必须与 fmu.yaml 的 model.state_type 一致（这里是 {state_type}）。
 * router (fmi2_router.h) 会 cast void* 到该类型。
 * ============================================================ */

#ifndef USER_MODEL_H_
#define USER_MODEL_H_

/* ---- 状态结构体: 用户填充字段 ---- */
typedef struct {{
    /* TODO: 在此声明你的模型状态字段 */
    /* 示例:
     * double tau;
     * double u, y;
     */
}} {state_type};

/* ---- 三个回调（用户实现，见 user_model.c） ---- */
void* model_init(void);
int   model_step(void* state, double t, double dt);
void  model_terminate(void* state);

#endif /* USER_MODEL_H_ */
"""

# ---- user_model.c 骨架模板（小，留在 Python 里）----
USER_MODEL_C_TEMPLATE = """/* ============================================================
 * user_model.c —— 用户模型实现
 * 由 fmu-pack init 生成骨架，用户填充
 *
 * 状态结构体 {state_type} 定义在 user_model.h
 * ============================================================ */

#include "user_model.h"
#include <stdlib.h>

void* model_init(void) {{
    {state_type}* s = ({state_type}*)malloc(sizeof({state_type}));
    if (!s) return NULL;
    /* TODO: 初始化字段（可选的默认参数等） */
    return s;
}}

int model_step(void* state, double t, double dt) {{
    (void)t;
    (void)dt;
    if (!state) return -1;
    {state_type}* s = ({state_type}*)state;
    /* TODO: 单步推进逻辑 */
    return 0;
}}

void model_terminate(void* state) {{
    if (!state) return;
    /* TODO: 释放动态分配的资源（如果有） */
    free(state);
}}
"""


def _resolve_prefix(config: dict[str, Any]) -> str:
    """获取回调前缀，未指定时默认用 modelIdentifier"""
    model = config.get("model", {})
    prefix = model.get("prefix")
    if not prefix:
        prefix = config["fmi"].get("modelIdentifier", "model")
    return prefix


def _resolve_state_type(config: dict[str, Any]) -> str:
    """获取状态类型名，未指定时默认用 {ModelIdentifier}State"""
    model = config.get("model", {})
    state_type = model.get("state_type")
    if not state_type:
        mi = config["fmi"].get("modelIdentifier", "Model")
        state_type = f"{mi}State"
    return state_type


def generate_adapter(config: dict[str, Any], output_path: Path) -> Path:
    """生成 fmi2_adapter.c

    注意: 适配层模板是字节级通用的（不包含 model_identifier/state_type/prefix），
    所有 FMU 项目的 fmi2_adapter.c 完全一致。
    config 参数仅为保持接口一致，实际不用于渲染。

    Args:
        config: fmu.yaml 解析后的配置字典（未使用）
        output_path: 输出文件路径（通常是 <项目>/src/fmi2_adapter.c）

    Returns:
        写入的文件路径
    """
    # 模板无项目占位符，直接渲染
    content = _ADAPTER_TEMPLATE.render()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path


def generate_user_model_h(config: dict[str, Any], output_path: Path) -> Path:
    """生成 user_model.h 骨架（统一使用 model_* 回调）"""
    content = USER_MODEL_H_TEMPLATE.format()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path


def generate_user_model_c(config: dict[str, Any], output_path: Path) -> Path:
    """生成 user_model.c 骨架（统一使用 model_* 回调）"""
    content = USER_MODEL_C_TEMPLATE.format(
        state_type=_resolve_state_type(config),
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path
