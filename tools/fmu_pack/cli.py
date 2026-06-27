"""CLI 入口 —— fmu-pack 命令行工具

子命令:
  init        在当前目录生成 fmu.yaml 模板
  validate    校验 fmu.yaml 配置 + 渲染 XML 并做 XSD 校验
  build       完整构建流程: 校验 → 路由头 → 编译 → 打包
  gen-router  仅生成 VR 路由头文件
  inspect     查看 .fmu 内部结构（文件列表 + 变量信息）
  clean       清理 build/ 和 dist/ 目录

退出码:
  0  成功
  1  一般错误（文件已存在、找不到文件等）
  2  fmu.yaml 校验失败
  3  XML 渲染 / XSD 校验失败
  4  至少一个平台构建失败
  5  ZIP 打包失败 / 产物完整性校验失败
"""

import argparse
import sys
from pathlib import Path

from .config import load_config, validate_config
from .router_gen import generate_router_header
from .xml_gen import render_model_description
from .validator import validate_xml
from .builder import build_platform
from .packager import assemble_fmu


def cmd_init(args: argparse.Namespace) -> int:
    """在当前目录生成 fmu.yaml 模板

    模板包含一个 RC 低通滤波器的示例配置，用户可在此基础上修改。
    如果目标文件已存在则不会覆盖，返回 1。
    """
    target = Path(args.directory or ".") / "fmu.yaml"
    if target.exists():
        print(f"[错误] {target} 已存在，不会覆盖")
        return 1

    # fmu.yaml 模板内容，包含 fmi 元信息、变量定义、模型配置、目标平台
    template = """# FMU 2.0 模型描述文件（由 fmu-pack init 生成）
fmi:
  version: "2.0"
  kind: "CoSimulation"
  modelIdentifier: "MyModel"
  guid: "auto"
  generationTool: "fmu-pack 0.1.0"

variables:
  - { name: "tau", vr: 1, type: "Real", causality: "parameter", start: 1.0, variability: "fixed" }
  - { name: "u",   vr: 2, type: "Real", causality: "input" }
  - { name: "y",   vr: 3, type: "Real", causality: "output" }

model:
  step: "euler"
  sources: ["src/user_model.c"]

platforms: ["win64"]
"""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(template, encoding="utf-8")
    print(f"[OK] 已生成 {target}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """校验 fmu.yaml 配置并渲染 XML 做 XSD 校验

    流程:
      1. 加载 fmu.yaml（自动处理 GUID 生成）
      2. 校验配置字段合法性
      3. 渲染 modelDescription.xml
      4. 可选: 用 fmi2ModelDescription.xsd 做 schema 校验
    """
    config_path = Path(args.config or "fmu.yaml")
    if not config_path.exists():
        print(f"[错误] 找不到 {config_path}")
        return 2

    # 加载配置（自动生成 GUID 并写回）
    config = load_config(config_path)
    # 校验变量定义、类型、causality 等
    errs = validate_config(config)
    if errs:
        for e in errs:
            print(f"[校验失败] {e}")
        return 2

    print("[OK] fmu.yaml 校验通过")

    # 渲染 XML 并做 XSD 校验
    xml_str = render_model_description(config)
    xsd_path = Path(args.xsd) if args.xsd else None
    if xsd_path and xsd_path.exists():
        ok, msg = validate_xml(xml_str, xsd_path)
        if not ok:
            print(f"[XSD 校验失败] {msg}")
            return 3
        print("[OK] XSD 校验通过")
    else:
        print("[提示] 未提供 XSD，跳过 schema 校验")

    return 0


def cmd_build(args: argparse.Namespace) -> int:
    """完整构建流程: 校验 → 路由头 → 编译 → 打包

    六步流水线:
      1. 加载并校验 fmu.yaml
      2. 生成 VR 路由头 fmi2_router.h
      3. 渲染 modelDescription.xml
      4. XSD schema 校验
      5. 调用编译器构建各平台共享库
      6. 组装 ZIP 打包为 .fmu
    """
    config_path = Path(args.config or "fmu.yaml")
    if not config_path.exists():
        print(f"[错误] 找不到 {config_path}")
        return 2

    # 1. 加载 & 校验配置
    config = load_config(config_path)
    errs = validate_config(config)
    if errs:
        for e in errs:
            print(f"[校验失败] {e}")
        return 2
    print("[1/6] fmu.yaml 校验通过")

    # 2. 生成 VR 路由头 —— 将 fmu.yaml 中的变量映射为 C 枚举 + switch-case 路由
    project_dir = config_path.parent
    include_dir = project_dir / "include"
    include_dir.mkdir(parents=True, exist_ok=True)
    router_h = generate_router_header(config, include_dir)
    print(f"[2/6] 路由头已生成: {router_h}")

    # 3. 渲染 modelDescription.xml —— Jinja2 模板填充
    xml_str = render_model_description(config)
    build_dir = project_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    xml_path = build_dir / "modelDescription.xml"
    xml_path.write_text(xml_str, encoding="utf-8")
    print(f"[3/6] modelDescription.xml 已渲染")

    # 4. XSD 校验 —— 确保 XML 符合 FMI 2.0 schema
    xsd_path = Path(args.xsd) if args.xsd else None
    if xsd_path and xsd_path.exists():
        ok, msg = validate_xml(xml_str, xsd_path)
        if not ok:
            print(f"[XSD 校验失败] {msg}")
            return 3
        print("[4/6] XSD 校验通过")
    else:
        print("[4/6] 跳过 XSD 校验（未提供 xsd）")

    # 5. 构建 —— 逐平台编译共享库（当前仅支持 win64 本地构建）
    platforms: list[str] = args.platform.split(",") if args.platform else config.get("platforms", ["win64"])
    binaries: dict[str, Path] = {}
    for plat in platforms:
        plat = plat.strip()
        print(f"[5/6] 构建平台: {plat}")
        result = build_platform(config, project_dir, plat, build_dir)
        if result:
            binaries[plat] = result
            print(f"      产物: {result}")
        else:
            print(f"      [失败] {plat} 构建出错")
            return 4

    # 6. 打包 FMU —— 将 XML + 二进制 + 可选资源打包为 .fmu (ZIP)
    dist_dir = project_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    fmu_path = assemble_fmu(config, binaries, xml_path, project_dir, dist_dir)
    if fmu_path:
        print(f"[6/6] FMU 已生成: {fmu_path}")
    else:
        print("[6/6] FMU 打包失败")
        return 5

    return 0


def cmd_gen_router(args: argparse.Namespace) -> int:
    """仅生成 VR 路由头，不执行编译和打包

    适用于只修改了 fmu.yaml 变量定义，需要重新生成路由表但不需要重新编译的场景。
    """
    config_path = Path(args.config or "fmu.yaml")
    config = load_config(config_path)
    include_dir = config_path.parent / "include"
    include_dir.mkdir(parents=True, exist_ok=True)
    path = generate_router_header(config, include_dir)
    print(f"[OK] 路由头已生成: {path}")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    """列出 .fmu 内部结构

    显示内容:
      - ZIP 内各文件路径和大小
      - modelDescription.xml 关键字段: fmiVersion, modelName, guid, modelIdentifier
      - 所有 ScalarVariable 的 vr, name, causality, start
    """
    import zipfile

    fmu_path = Path(args.fmu)
    if not fmu_path.exists():
        print(f"[错误] 找不到 {fmu_path}")
        return 1

    with zipfile.ZipFile(fmu_path, "r") as zf:
        # 列出 ZIP 内所有文件
        print(f"=== {fmu_path.name} ===")
        for info in zf.infolist():
            size_kb = info.file_size / 1024
            print(f"  {info.filename:<50s} {size_kb:>8.1f} KB")

        # 解析 modelDescription.xml（FMI 2.0 不使用命名空间前缀）
        if "modelDescription.xml" in zf.namelist():
            from lxml import etree
            xml_bytes = zf.read("modelDescription.xml")
            root = etree.fromstring(xml_bytes)
            print(f"\n  fmiVersion: {root.get('fmiVersion')}")
            print(f"  modelName:  {root.get('modelName')}")
            print(f"  guid:       {root.get('guid')}")
            cs = root.find("CoSimulation")
            if cs is not None:
                print(f"  modelIdentifier: {cs.get('modelIdentifier')}")
            svars = root.findall(".//ScalarVariable")
            print(f"  variables:  {len(svars)}")
            for sv in svars:
                name = sv.get("name")
                vr = sv.get("valueReference")
                causality = sv.get("causality", "local")
                rt = sv.find("Real")
                start = rt.get("start") if rt is not None else None
                print(f"    vr={vr} name={name} causality={causality} start={start}")
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """清理 build/ 和 dist/ 目录

    删除所有中间产物和最终 FMU，回到干净状态。
    """
    import shutil
    project_dir = Path(args.directory or ".")
    for d in ["build", "dist"]:
        target = project_dir / d
        if target.exists():
            shutil.rmtree(target)
            print(f"[OK] 已删除 {target}")
    return 0


def main() -> None:
    """CLI 主入口 —— 解析子命令并分发到对应处理函数"""
    parser = argparse.ArgumentParser(
        prog="fmu-pack",
        description="FMI 2.0 FMU 打包工具 —— 把 C 模型封装为标准 FMU",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init —— 生成 fmu.yaml 模板
    p_init = sub.add_parser("init", help="生成 fmu.yaml 模板")
    p_init.add_argument("directory", nargs="?", help="目标目录（默认当前目录）")

    # validate —— 校验配置 + 可选 XSD 校验
    p_val = sub.add_parser("validate", help="校验 fmu.yaml + XSD")
    p_val.add_argument("--config", "-c", help="fmu.yaml 路径")
    p_val.add_argument("--xsd", help="fmi2ModelDescription.xsd 路径")

    # build —— 完整构建流水线
    p_build = sub.add_parser("build", help="完整构建 FMU")
    p_build.add_argument("--config", "-c", help="fmu.yaml 路径")
    p_build.add_argument("--platform", "-p", help="目标平台，逗号分隔（默认取 fmu.yaml 中的 platforms）")
    p_build.add_argument("--xsd", help="fmi2ModelDescription.xsd 路径")

    # gen-router —— 仅生成路由头
    p_gr = sub.add_parser("gen-router", help="仅生成 VR 路由头")
    p_gr.add_argument("--config", "-c", help="fmu.yaml 路径")

    # inspect —— 查看 FMU 内部结构
    p_ins = sub.add_parser("inspect", help="查看 .fmu 内部结构")
    p_ins.add_argument("fmu", help=".fmu 文件路径")

    # clean —— 清理构建产物
    p_clean = sub.add_parser("clean", help="清理 build/ dist/")
    p_clean.add_argument("directory", nargs="?", help="项目目录（默认当前目录）")

    args = parser.parse_args()

    # 子命令 → 处理函数映射表
    handlers = {
        "init": cmd_init,
        "validate": cmd_validate,
        "build": cmd_build,
        "gen-router": cmd_gen_router,
        "inspect": cmd_inspect,
        "clean": cmd_clean,
    }

    handler = handlers.get(args.command)
    if handler:
        sys.exit(handler(args))


if __name__ == "__main__":
    main()
