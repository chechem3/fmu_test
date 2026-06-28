"""modelDescription.xml 渲染 —— 从 ParsedModel 生成

不再依赖 fmu.yaml；VR 按字段声明顺序自动分配。
"""

from typing import Any
from datetime import datetime, timezone

from jinja2 import Environment, BaseLoader

from .header_parser import ParsedModel, FieldInfo


XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription
  fmiVersion="2.0"
  modelName="{{ model_identifier }}"
  guid="{{ guid }}"
  generationTool="{{ generation_tool }}"
  generationDateAndTime="{{ generation_time }}"
  variableNamingConvention="flat"
  numberOfEventIndicators="0">

  <CoSimulation
    modelIdentifier="{{ model_identifier }}"
    canHandleVariableCommunicationStepSize="false"
    canInterpolateInputs="true"
    maxOutputDerivativeOrder="0"
    canRunAsynchronuously="false"
    canBeInstantiatedOnlyOncePerProcess="false"
    canNotUseMemoryManagementFunctions="true"
    canGetAndSetFMUstate="false"
    canSerializeFMUstate="false"
    providesDirectionalDerivative="false" />

  <ModelVariables>
{% for v in all_vars %}
    <ScalarVariable
      name="{{ v.name }}"
      valueReference="{{ v.vr }}"
      causality="{{ v.causality }}"
{% if v.variability %}
      variability="{{ v.variability }}"
{% endif %}
{% if v.initial %}
      initial="{{ v.initial }}"
{% endif %}
{% if v.start is defined and v.start is not none %}
      description="start={{ v.start }}"
{% endif %}>
      <{{ v.fmi_type }}{% if v.start is defined and v.start is not none %} start="{{ v.start }}"{% endif %} />
    </ScalarVariable>
{% endfor %}
  </ModelVariables>

  <ModelStructure>
    <Outputs>
{% for idx in outputs_indices %}
      <Unknown index="{{ idx }}" />
{% endfor %}
    </Outputs>
{% if derivatives_indices %}
    <Derivatives>
{% for idx in derivatives_indices %}
      <Unknown index="{{ idx }}" />
{% endfor %}
    </Derivatives>
{% endif %}
  </ModelStructure>

</fmiModelDescription>
"""


_env = Environment(loader=BaseLoader())


def _fmi_type_default(fmi_type: str, causality: str):
    """返回该类型/因果的默认 start 值（字符串）"""
    if causality == "output":
        return None
    if fmi_type in ("Real",):
        return "0.0"
    if fmi_type in ("Integer",):
        return "0"
    if fmi_type in ("Boolean",):
        return "false"
    if fmi_type in ("String",):
        return ""
    return None


def _field_to_var(f: FieldInfo, vr: int):
    """FieldInfo + VR → XML variable 字典"""
    return {
        "name": f.name,
        "vr": vr,
        "causality": f.causality,
        "fmi_type": f.fmi_type,
        "variability": "fixed" if f.causality == "parameter" else None,
        # parameters 默认 initial=exact（允许 start_value 在 init 前被覆盖）
        "initial": "exact" if f.causality == "parameter" else None,
        "start": _fmi_type_default(f.fmi_type, f.causality),
    }


def render_model_description(
    model_identifier: str,
    guid: str,
    parsed: ParsedModel,
    generation_tool: str = "fmu-pack 0.1.0",
) -> str:
    """从 ParsedModel 渲染 modelDescription.xml

    VR 分配: UserModelParameterT 字段先（1..N），然后 UserModelInputT，最后 UserModelOutputT
    """
    all_vars = []
    vr = 1
    for f in parsed.parameter_fields:
        all_vars.append(_field_to_var(f, vr))
        vr += 1
    for f in parsed.input_fields:
        all_vars.append(_field_to_var(f, vr))
        vr += 1
    for f in parsed.output_fields:
        all_vars.append(_field_to_var(f, vr))
        vr += 1

    # ModelStructure Outputs 索引（1-based，按 all_vars 顺序）
    outputs_indices = [i + 1 for i, v in enumerate(all_vars) if v["causality"] == "output"]

    tpl = _env.from_string(XML_TEMPLATE)
    return tpl.render(
        model_identifier=model_identifier,
        guid=guid,
        generation_tool=generation_tool,
        generation_time=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        all_vars=all_vars,
        outputs_indices=outputs_indices,
        derivatives_indices=[],  # 暂不支持
    )
