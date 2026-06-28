"""README.md 与 test_user_model.py 生成器

从 ParsedModel 渲染：
  - <project_dir>/README.md            (FMU 功能描述文档)
  - <project_dir>/test/test_user_model.py  (FMPy 仿真测试脚本)

VR 分配规则与 xml_gen.render_model_description 完全一致：
parameter → input → output，从 1 起累加。
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .header_parser import FieldInfo, ParsedModel


_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)
_README_TEMPLATE = _env.get_template("README.md.j2")
_TEST_TEMPLATE   = _env.get_template("test_user_model.py.j2")


def _field_to_var(f: FieldInfo, vr: int) -> dict:
    """FieldInfo + VR → README/test 模板用字典

    字段名与 xml_gen._field_to_var 对齐（name/vr/causality/fmi_type/variability/start），
    便于未来把 VR 分配抽到 header_parser 后只改一处。
    """
    return {
        "name": f.name,
        "vr": vr,
        "type": f.fmi_type,        # README/test 模板用的是 v.type
        "causality": f.causality,
        "variability": "fixed" if f.causality == "parameter" else None,
        "start": _fmi_type_default(f.fmi_type, f.causality),
    }


def _fmi_type_default(fmi_type: str, causality: str):
    """返回该类型/因果的默认 start 值（字符串）。与 xml_gen._fmi_type_default 同步。"""
    if causality == "output":
        return None
    if fmi_type == "Real":
        return "0.0"
    if fmi_type == "Integer":
        return "0"
    if fmi_type == "Boolean":
        return "false"
    if fmi_type == "String":
        return ""
    return None


def build_variables(parsed: ParsedModel) -> list[dict]:
    """聚合 3 个结构体字段为带 VR 的统一字典列表（顺序：parameter → input → output）。

    VR 分配规则必须与 xml_gen.render_model_description 保持完全一致。
    """
    out: list[dict] = []
    vr = 1
    for grp in (parsed.parameter_fields, parsed.input_fields, parsed.output_fields):
        for f in grp:
            out.append(_field_to_var(f, vr))
            vr += 1
    return out


def generate_readme(parsed: ParsedModel, model_identifier: str, project_dir: Path) -> Path:
    """渲染并写入 <project_dir>/README.md"""
    out = project_dir / "README.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        _README_TEMPLATE.render(
            model_identifier=model_identifier,
            variables=build_variables(parsed),
        ),
        encoding="utf-8",
    )
    return out


def generate_test(parsed: ParsedModel, model_identifier: str, project_dir: Path) -> Path:
    """渲染并写入 <project_dir>/test/test_user_model.py"""
    out = project_dir / "test" / "test_user_model.py"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        _TEST_TEMPLATE.render(
            model_identifier=model_identifier,
            variables=build_variables(parsed),
            stop_time=10,
            step_size=0.1,
        ),
        encoding="utf-8",
    )
    return out