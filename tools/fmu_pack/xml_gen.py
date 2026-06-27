"""modelDescription.xml 模板渲染

使用 Jinja2 内联模板从 fmu.yaml 配置生成符合 FMI 2.0 规范的 modelDescription.xml。

模板变量:
  - fmi.version / fmi.kind / fmi.modelIdentifier / fmi.guid / fmi.generationTool
  - variables: 变量列表（name, vr, type, causality, variability, start, unit）
  - outputs: causality=output 的变量索引（用于 ModelStructure/Outputs）
  - derivatives: 参与导数的变量索引（仅 ModelExchange）
  - initial_unknowns: initial=approx 的变量索引
  - generation_time: UTC 时间戳

FMI 2.0 XML 不使用命名空间前缀，属性直接写在元素上。
"""

from typing import Any

from jinja2 import Environment, BaseLoader

# Jinja2 内联模板 —— 避免外部文件依赖，所有模板逻辑集中在此
XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription
  fmiVersion="{{ fmi.version }}"
  modelName="{{ fmi.modelIdentifier }}"
  guid="{{ fmi.guid }}"
  generationTool="{{ fmi.generationTool }}"
  generationDateAndTime="{{ generation_time }}"
  variableNamingConvention="flat"
  numberOfEventIndicators="0">

  {% if fmi.kind == "CoSimulation" %}
  <CoSimulation
    modelIdentifier="{{ fmi.modelIdentifier }}"
    canHandleVariableCommunicationStepSize="true"
    canInterpolateInputs="true"
    maxOutputDerivativeOrder="0"
    canRunAsynchronuously="false"
    canBeInstantiatedOnlyOncePerProcess="false"
    canNotUseMemoryManagementFunctions="true"
    canGetAndSetFMUstate="false"
    canSerializeFMUstate="false"
    providesDirectionalDerivative="false" />
  {% elif fmi.kind == "ModelExchange" %}
  <ModelExchange modelIdentifier="{{ fmi.modelIdentifier }}" />
  {% endif %}

  {% if variables %}
  <ModelVariables>
  {% for v in variables %}
    <ScalarVariable
      name="{{ v.name }}"
      valueReference="{{ v.vr }}"
      {% if v.causality %}causality="{{ v.causality }}"{% endif %}
      {% if v.variability %}variability="{{ v.variability }}"{% endif %}
      {% if v.initial %}initial="{{ v.initial }}"{% endif %}>
      {% if v.type == "Real" %}
      <Real{% if v.start is defined and v.start is not none %} start="{{ v.start }}"{% endif %}{% if v.unit is defined %} unit="{{ v.unit }}"{% endif %} />
      {% elif v.type == "Integer" %}
      <Integer{% if v.start is defined and v.start is not none %} start="{{ v.start }}"{% endif %} />
      {% elif v.type == "Boolean" %}
      <Boolean{% if v.start is defined and v.start is not none %} start="{{ v.start }}"{% endif %} />
      {% elif v.type == "String" %}
      <String{% if v.start is defined and v.start is not none %} start="{{ v.start }}"{% endif %} />
      {% endif %}
    </ScalarVariable>
  {% endfor %}
  </ModelVariables>
  {% endif %}

  <ModelStructure>
    {% if outputs %}
    <Outputs>
      {% for idx in outputs %}
      <Unknown index="{{ idx }}" />
      {% endfor %}
    </Outputs>
    {% endif %}
    {% if derivatives %}
    <Derivatives>
      {% for idx in derivatives %}
      <Unknown index="{{ idx }}" />
      {% endfor %}
    </Derivatives>
    {% endif %}
    {% if initial_unknowns %}
    <InitialUnknowns>
      {% for idx in initial_unknowns %}
      <Unknown index="{{ idx }}" />
      {% endfor %}
    </InitialUnknowns>
    {% endif %}
  </ModelStructure>

</fmiModelDescription>
"""

# 全局 Jinja2 环境，使用 BaseLoader 从字符串加载模板
_env = Environment(loader=BaseLoader())


def render_model_description(config: dict[str, Any]) -> str:
    """从配置渲染 modelDescription.xml 字符串

    计算 ModelStructure 索引:
      - Outputs: 所有 causality=output 的变量（1-based 序号）
      - Derivatives: causality=local 且标记了 derivative 的变量
      - InitialUnknowns: initial=approx 的 output/local 变量

    Args:
        config: fmu.yaml 解析后的配置字典

    Returns:
        完整的 modelDescription.xml 字符串
    """
    from datetime import datetime, timezone

    fmi = config["fmi"]
    variables: list[dict] = config.get("variables", [])

    # 计算 ModelStructure 索引（FMI 规范要求 1-based）
    outputs: list[int] = []
    derivatives: list[int] = []
    initial_unknowns: list[int] = []

    for i, v in enumerate(variables, start=1):
        causality = v.get("causality", "local")
        if causality == "output":
            outputs.append(i)
        if causality == "local" and v.get("derivative"):
            derivatives.append(i)
        if causality in ("output", "local") and v.get("initial") == "approx":
            initial_unknowns.append(i)

    template = _env.from_string(XML_TEMPLATE)
    return template.render(
        fmi=fmi,
        variables=variables,
        outputs=outputs if outputs else None,
        derivatives=derivatives if derivatives else None,
        initial_unknowns=initial_unknowns if initial_unknowns else None,
        # 生成时间使用 UTC，符合 FMI 规范要求
        generation_time=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
