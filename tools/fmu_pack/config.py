"""fmu.yaml 配置加载与校验

fmu.yaml 是 FMU 打包工具的核心配置文件，定义:
  - fmi:     FMI 版本、类型、模型标识符、GUID
  - variables: 变量列表（name, vr, type, causality, start, variability）
  - model:   模型源码、积分器类型、状态结构体类型
  - platforms: 目标平台列表

校验规则（FMI 2.0 规范约束）:
  1. vr 唯一，正整数，≥ 1
  2. causality=output 不能有 start
  3. causality=parameter 必须有 variability=fixed|tunable|discrete
  4. modelIdentifier 匹配 [A-Za-z_][A-Za-z0-9_]*
  5. guid 一旦生成就不可变（工具首次生成后写回 fmu.yaml）
"""

import uuid
import re
from pathlib import Path
from typing import Any

import yaml


def load_config(path: Path) -> dict[str, Any]:
    """加载 fmu.yaml，自动处理 guid 生成与固化

    GUID 策略:
      - 若 guid 为 "auto" 或空 → 生成 UUIDv4 并写回文件
      - 若 guid 已有值 → 保持不变（保证 importer 能识别同一 FMU）
      - 写回使用 yaml.safe_dump 保持格式可读
    """
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 自动生成 GUID —— 只在首次运行时触发
    fmi = config.setdefault("fmi", {})
    guid = fmi.get("guid", "auto")
    if guid == "auto" or not guid:
        new_guid = str(uuid.uuid4())
        fmi["guid"] = new_guid
        # 写回 yaml，保证 guid 不可变（后续构建不再重新生成）
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"[提示] 已生成 GUID: {new_guid}，已写回 {path}")

    return config


def validate_config(config: dict[str, Any]) -> list[str]:
    """校验 fmu.yaml 配置，返回错误列表

    校验项:
      - fmi 节存在性
      - fmi.version 必须为 "2.0"
      - fmi.kind 必须为 CoSimulation 或 ModelExchange
      - modelIdentifier 命名合法性
      - guid 非空
      - variables 列表非空
      - 每个变量的 vr 唯一性、类型、causality 合法性
      - output 变量不设 start
      - parameter 变量必须有 variability
      - model.sources 非空
    """
    errors: list[str] = []

    # ---- fmi 元信息校验 ----
    fmi = config.get("fmi", {})
    if not fmi:
        errors.append("缺少 fmi 配置节")
        return errors

    # fmiVersion: 首期只支持 2.0
    version = fmi.get("version", "")
    if version != "2.0":
        errors.append(f"fmi.version 必须为 '2.0'，当前: {version}")

    # kind: 首期只支持 CoSimulation
    kind = fmi.get("kind", "")
    if kind not in ("CoSimulation", "ModelExchange"):
        errors.append(f"fmi.kind 必须为 CoSimulation 或 ModelExchange，当前: {kind}")

    # modelIdentifier: 将用作 DLL 基名，必须符合 C 标识符规范
    mi = fmi.get("modelIdentifier", "")
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", mi):
        errors.append(f"modelIdentifier '{mi}' 不合法，必须匹配 [A-Za-z_][A-Za-z0-9_]*")

    # guid: importer 用它区分 FMU 实例，不能为空
    guid = fmi.get("guid", "")
    if not guid or guid == "auto":
        errors.append("guid 未生成，请重新运行（工具会自动生成）")

    # ---- 变量校验 ----
    variables: list[dict] = config.get("variables", [])
    if not variables:
        errors.append("variables 列表为空")
        return errors

    vr_set: set[int] = set()  # 用于检测 vr 重复
    for i, var in enumerate(variables):
        name = var.get("name", f"#{i}")

        # vr 必须存在且为正整数
        vr = var.get("vr")
        if vr is None:
            errors.append(f"变量 '{name}' 缺少 vr")
            continue
        if not isinstance(vr, int) or vr < 1:
            errors.append(f"变量 '{name}' 的 vr={vr} 必须是 ≥1 的正整数")
        if vr in vr_set:
            errors.append(f"变量 '{name}' 的 vr={vr} 重复")
        vr_set.add(vr)

        # type: 首期只支持 Real
        vtype = var.get("type", "")
        if vtype not in ("Real", "Integer", "Boolean", "String"):
            errors.append(f"变量 '{name}' 的 type='{vtype}' 不合法")

        # causality: FMI 2.0 定义的 6 种
        causality = var.get("causality", "local")
        if causality not in ("parameter", "calculatedParameter", "input", "output", "local", "independent"):
            errors.append(f"变量 '{name}' 的 causality='{causality}' 不合法")

        # FMI 2.0 规则: output 不能有 start（由模型计算得出）
        if causality == "output" and "start" in var:
            errors.append(f"变量 '{name}' causality=output 不能设置 start")

        # FMI 2.0 规则: parameter 必须有 variability
        if causality == "parameter":
            variability = var.get("variability", "")
            if variability not in ("fixed", "tunable", "discrete"):
                errors.append(f"变量 '{name}' causality=parameter 必须设置 variability=fixed|tunable|discrete")

    # ---- 模型配置校验 ----
    model = config.get("model", {})
    if not model.get("sources"):
        errors.append("model.sources 为空，至少需要一个 C 源文件")

    return errors
