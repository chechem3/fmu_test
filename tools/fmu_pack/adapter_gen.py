"""fmi2_adapter.c 代码生成器

从 ParsedModel 生成适配层：
  - VR 枚举（按 user_model.h 字段声明顺序）
  - get/set 路由（Real/Integer/Boolean/String 全部类型）
  - 调用 model_init / model_step / model_terminate
  - v2 起：FMU 不在内部切分 importer dt（由 importer 决定步长）
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from .header_parser import ParsedModel, FieldInfo


_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)
_ADAPTER_TEMPLATE = _env.get_template("fmi2_adapter.c.j2")


def _split_by_fmi_type(parsed: ParsedModel) -> dict[str, list[FieldInfo]]:
    """按 FMI 类型分组"""
    real = []
    integer = []
    boolean = []
    string = []
    for f in parsed.all_fields():
        if f.fmi_type == "Real":
            real.append(f)
        elif f.fmi_type == "Integer":
            integer.append(f)
        elif f.fmi_type == "Boolean":
            boolean.append(f)
        elif f.fmi_type == "String":
            string.append(f)
    return {"real": real, "integer": integer, "boolean": boolean, "string": string}


def generate_adapter(parsed: ParsedModel, output_path: Path) -> Path:
    """生成 fmi2_adapter.c

    Args:
        parsed: 解析后的用户模型（来自 header_parser.parse_user_model_h）
        output_path: 输出文件路径

    Returns:
        写入的文件路径
    """
    groups = _split_by_fmi_type(parsed)

    content = _ADAPTER_TEMPLATE.render(
        parameter_fields=parsed.parameter_fields,
        input_fields=parsed.input_fields,
        output_fields=parsed.output_fields,
        n_param=len(parsed.parameter_fields),
        n_input=len(parsed.input_fields),
        n_output=len(parsed.output_fields),
        real_fields=groups["real"],
        integer_fields=groups["integer"],
        boolean_fields=groups["boolean"],
        string_fields=groups["string"],
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path
