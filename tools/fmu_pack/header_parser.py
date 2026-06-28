"""user_model.h 解析器

从 user_model.h 提取 3 个固定结构体（UserModelParameterT / UserModelInputT / UserModelOutputT）
及其字段（名+类型），校验 3 个回调存在。

设计：纯正则（pycparser 是 overkill）。
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---- 解析结果 ----

@dataclass
class FieldInfo:
    """单个字段信息"""
    name: str
    c_type: str       # C 类型原文，如 "double", "int", "char[64]"
    fmi_type: str     # FMI 类型: "Real" / "Integer" / "Boolean" / "String"
    causality: str    # "parameter" / "input" / "output"


@dataclass
class ParsedModel:
    """解析结果"""
    parameter_fields: list[FieldInfo] = field(default_factory=list)
    input_fields:     list[FieldInfo] = field(default_factory=list)
    output_fields:    list[FieldInfo] = field(default_factory=list)
    has_init: bool = False
    has_step: bool = False
    has_terminate: bool = False

    def all_fields(self) -> list[FieldInfo]:
        return self.parameter_fields + self.input_fields + self.output_fields


# ---- C 类型 → FMI 类型映射 ----

_TYPE_MAP = {
    "double":     "Real",
    "float":      "Real",
    "int":        "Integer",
    "int32_t":    "Integer",
    "int16_t":    "Integer",
    "int8_t":     "Integer",
    "long":       "Integer",
    "short":      "Integer",
    "fmi2Boolean":"Boolean",
    "bool":       "Boolean",
    "char":       "String",  # 假设是 char[N]
}


def c_type_to_fmi(c_type: str) -> str:
    """C 类型 → FMI 类型"""
    base = c_type.strip().rstrip("]").split("[")[0].strip()
    base = base.replace("const", "").strip()
    # char[] → String
    if c_type.strip().startswith("char") and "[" in c_type:
        return "String"
    return _TYPE_MAP.get(base, "Real")  # 未知类型默认 Real


# ---- 正则模式 ----

# 去掉 /* */ 和 // 注释
_RE_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_RE_LINE_COMMENT  = re.compile(r"//[^\n]*")

# typedef struct [opt_name] { body } TypeName;
_RE_STRUCT = re.compile(
    r"typedef\s+struct(\s+\w+)?\s*\{\s*([^}]*?)\s*\}\s*(\w+)\s*;",
    re.MULTILINE | re.DOTALL,
)

# 单个字段: "  type  name  ;" 或 "  type  name  = init  ;"
# type 可以包含 const, *, 空格
_RE_FIELD = re.compile(
    r"^\s*(?:const\s+)?([\w\s\*]+?)\s+(\w+)\s*(?:\[[^\]]*\])?\s*(?:=\s*[^;]+)?\s*;",
    re.MULTILINE,
)

# 三个回调声明
_RE_INIT       = re.compile(r"\bint\s+model_init\s*\(")
_RE_STEP       = re.compile(r"\bint\s+model_step\s*\(")
_RE_TERMINATE  = re.compile(r"\bvoid\s+model_terminate\s*\(")


# ---- 解析函数 ----

def _strip_comments(text: str) -> str:
    """去掉 C 注释"""
    text = _RE_BLOCK_COMMENT.sub("", text)
    text = _RE_LINE_COMMENT.sub("", text)
    return text


def _parse_struct_body(body: str) -> list[tuple[str, str]]:
    """解析结构体体，返回 [(name, c_type), ...]"""
    fields = []
    for m in _RE_FIELD.finditer(body):
        c_type = m.group(1).strip()
        name = m.group(2).strip()
        if c_type in ("return", "if", "for", "while"):
            continue
        fields.append((name, c_type))
    return fields


def _make_field_info(name: str, c_type: str, causality: str) -> FieldInfo:
    return FieldInfo(
        name=name,
        c_type=c_type,
        fmi_type=c_type_to_fmi(c_type),
        causality=causality,
    )


def parse_user_model_h(path: Path) -> ParsedModel:
    """解析 user_model.h

    提取:
      - 3 个固定结构体 (UserModelParameterT / UserModelInputT / UserModelOutputT) 的字段
      - 3 个回调的存在性

    注: v2 起不再解析 MODEL_STEP_SIZE（FMU 不在内部切分 importer dt）。

    Raises:
      ParseError: 结构体缺失或字段格式异常
    """
    text = path.read_text(encoding="utf-8")
    text = _strip_comments(text)

    result = ParsedModel()

    # 1. 找三个结构体
    struct_map = {
        "UserModelParameterT": ("parameter", result.parameter_fields),
        "UserModelInputT":     ("input",     result.input_fields),
        "UserModelOutputT":    ("output",    result.output_fields),
    }

    found_structs = set()
    for m in _RE_STRUCT.finditer(text):
        type_name = m.group(3)
        if type_name not in struct_map:
            continue
        found_structs.add(type_name)
        body = m.group(2)
        causality, field_list = struct_map[type_name]
        for name, c_type in _parse_struct_body(body):
            field_list.append(_make_field_info(name, c_type, causality))

    missing = set(struct_map.keys()) - found_structs
    if missing:
        raise ParseError(
            f"user_model.h 缺少结构体: {', '.join(sorted(missing))}\n"
            f"需要: {', '.join(struct_map.keys())}"
        )

    # 2. 校验三个回调
    result.has_init      = bool(_RE_INIT.search(text))
    result.has_step      = bool(_RE_STEP.search(text))
    result.has_terminate = bool(_RE_TERMINATE.search(text))
    if not (result.has_init and result.has_step and result.has_terminate):
        missing_cb = []
        if not result.has_init:      missing_cb.append("model_init")
        if not result.has_step:      missing_cb.append("model_step")
        if not result.has_terminate: missing_cb.append("model_terminate")
        raise ParseError(
            f"user_model.h 缺少回调声明: {', '.join(missing_cb)}"
        )

    return result


class ParseError(Exception):
    pass
