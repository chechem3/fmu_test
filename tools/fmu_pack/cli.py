"""CLI 入口 —— fmu-pack 命令行工具

子命令:
  init         生成完整 FMU 项目骨架（fmu.yaml + fmi2_adapter.c + user_model + CMake）
  validate     校验 fmu.yaml 配置 + 渲染 XML 并做 XSD 校验
  build        完整构建流程: 校验 → 生成代码 → 编译 → 打包
  gen-adapter  仅重新生成 fmi2_adapter.c（fmu.yaml 改了之后用）
  gen-router   仅生成 VR 路由头文件
  inspect      查看 .fmu 内部结构（文件列表 + 变量信息）
  clean        清理 build/ 和 dist/ 目录

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
from typing import Any

from .config import load_config, validate_config
from .adapter_gen import (
    generate_adapter, generate_user_model_h, generate_user_model_c,
    _resolve_prefix, _resolve_state_type,
)
from .router_gen import generate_router_header
from .xml_gen import render_model_description
from .validator import validate_xml
from .builder import build_platform
from .packager import assemble_fmu
from jinja2 import Environment, FileSystemLoader


# ---- Jinja2 环境（用于 README / test 模板）----
_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)
_README_TEMPLATE = _env.get_template("README.md.j2")
_TEST_TEMPLATE = _env.get_template("my_fmu_test.py.j2")


def generate_readme(config: dict[str, Any], output_path: Path) -> Path:
    """生成 README.md"""
    content = _README_TEMPLATE.render(
        model_identifier=config["fmi"]["modelIdentifier"],
        prefix=_resolve_prefix(config),
        state_type=_resolve_state_type(config),
        variables=config.get("variables", []),
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path


def generate_test_script(config: dict[str, Any], output_path: Path) -> Path:
    """生成 test/my_fmu_test.py"""
    content = _TEST_TEMPLATE.render(
        model_identifier=config["fmi"]["modelIdentifier"],
        variables=config.get("variables", []),
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path


# ---- 默认 CMakeLists.txt 模板 ----

CMAKE_TEMPLATE = """# CMakeLists.txt —— {model_identifier} FMU
# 由 fmu-pack init 生成，用户可手动修改以满足项目特定需求
cmake_minimum_required(VERSION 3.20)
project({model_identifier} C)

# ---- 头文件路径 ----
include_directories("${{CMAKE_SOURCE_DIR}}/include")
include_directories("${{CMAKE_SOURCE_DIR}}/../../third_party/fmi2/include")
{extra_includes}

# ---- 源文件 ----
set(SOURCES
    src/user_model.c
    src/fmi2_adapter.c
)

# ---- 共享库 ----
add_library({model_identifier} SHARED ${{SOURCES}})

# 输出文件名: 去掉 lib 前缀
set_target_properties({model_identifier} PROPERTIES
    PREFIX ""
    SUFFIX ".dll"
)

# Windows: 导出 FMI 符号
if(WIN32)
    target_compile_definitions({model_identifier} PRIVATE
        "FMI2_Export=__declspec(dllexport)"
    )
endif()

{extra_setup}
{extra_links}
"""


def _default_cmake(config: dict, project_dir: Path) -> str:
    """生成默认 CMakeLists.txt 字符串"""
    mi = config["fmi"]["modelIdentifier"]
    model = config.get("model", {})
    link_cfg = model.get("link", {})

    extra_includes: list[str] = []
    extra_setup: list[str] = []
    extra_links: list[str] = []
    has_cxx_lib = False

    for lib_name, lib_spec in link_cfg.items():
        if not isinstance(lib_spec, dict):
            continue
        inc_path = lib_spec.get("include")
        if inc_path:
            p = (project_dir / inc_path).resolve()
            extra_includes.append(
                f'include_directories("{p.as_posix()}")'
            )

        lib_dir = lib_spec.get("lib_dir")
        libs = lib_spec.get("libs", [])
        lib_files: list[str] = []
        if lib_dir:
            p = (project_dir / lib_dir).resolve()
            for lib in libs:
                for ext in [".a", ".lib"]:
                    candidate = p / f"lib{lib}{ext}"
                    if candidate.exists():
                        lib_files.append(f'"{candidate.as_posix()}"')
                        break

        if lib_files:
            extra_links.append(
                f"target_link_libraries({mi} PRIVATE {' '.join(lib_files)})"
            )
        if "ws2_32" in libs or "iphlpapi" in libs:
            # Windows 系统库
            pass

        if lib_name == "zeromq":
            extra_setup.append(f"target_compile_definitions({mi} PRIVATE ZMQ_STATIC)")
            extra_setup.append(f"set_target_properties({mi} PROPERTIES LINKER_LANGUAGE CXX)")
            has_cxx_lib = True

    # Windows 系统库
    win_sys_libs = []
    if link_cfg:
        win_sys_libs = ["ws2_32", "iphlpapi"]
    if win_sys_libs:
        extra_links.append(
            f"target_link_libraries({mi} PRIVATE {' '.join(win_sys_libs)})"
        )

    if has_cxx_lib:
        # 改 project() 声明为 C CXX
        # 通过在 extra_setup 里加 message 提示
        extra_setup.append(
            f'# C++ static library detected, set LINKER_LANGUAGE CXX above'
        )

    return CMAKE_TEMPLATE.format(
        model_identifier=mi,
        extra_includes="\n".join(extra_includes),
        extra_setup="\n".join(extra_setup),
        extra_links="\n".join(extra_links),
    )


def cmd_init(args: argparse.Namespace) -> int:
    """生成完整 FMU 项目骨架

    生成以下文件（已存在则跳过）:
      - fmu.yaml              (项目配置)
      - src/fmi2_adapter.c    (FMI 2.0 适配层，自动生成)
      - include/user_model.h  (用户模型头，用户填充)
      - src/user_model.c      (用户模型实现，用户填充)
      - CMakeLists.txt        (构建配置)
      - README.md             (项目说明 + AI 交互逻辑)
      - test/my_fmu_test.py   (测试脚本)

    --force 选项覆盖已存在文件
    """
    target_dir = Path(args.directory or ".")
    target_dir.mkdir(parents=True, exist_ok=True)
    force = getattr(args, "force", False)

    if (target_dir / "fmu.yaml").exists() and not force:
        # fmu.yaml 已存在：使用现有配置
        print(f"[信息] fmu.yaml 已存在，使用现有配置")
        config = load_config(target_dir / "fmu.yaml")
    else:
        # 生成新 fmu.yaml 模板
        yaml_template = """# FMU 2.0 模型描述文件（由 fmu-pack init 生成）
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
  prefix: "model"
  state_type: "ModelState"
  sources: ["src/user_model.c"]

platforms: ["win64"]
"""
        yaml_path = target_dir / "fmu.yaml"
        yaml_path.write_text(yaml_template, encoding="utf-8")
        print(f"[OK] 已生成 {yaml_path}")
        config = load_config(yaml_path)

    # ---- 生成 fmi2_adapter.c（自动生成）----
    adapter_path = target_dir / "src" / "fmi2_adapter.c"
    if adapter_path.exists() and not force:
        print(f"[跳过] {adapter_path} 已存在（用 --force 覆盖）")
    else:
        generate_adapter(config, adapter_path)
        print(f"[OK] 已生成 {adapter_path}")

    # ---- 生成 user_model.h 骨架（仅在不存在时）----
    h_path = target_dir / "include" / "user_model.h"
    if h_path.exists() and not force:
        print(f"[跳过] {h_path} 已存在（用 --force 覆盖）")
    else:
        generate_user_model_h(config, h_path)
        print(f"[OK] 已生成 {h_path}")

    # ---- 生成 user_model.c 骨架（仅在不存在时）----
    c_path = target_dir / "src" / "user_model.c"
    if c_path.exists() and not force:
        print(f"[跳过] {c_path} 已存在（用 --force 覆盖）")
    else:
        generate_user_model_c(config, c_path)
        print(f"[OK] 已生成 {c_path}")

    # ---- 生成 CMakeLists.txt（仅在不存在时）----
    cmake_path = target_dir / "CMakeLists.txt"
    if cmake_path.exists() and not force:
        print(f"[跳过] {cmake_path} 已存在（用 --force 覆盖）")
    else:
        cmake_content = _default_cmake(config, target_dir)
        cmake_path.write_text(cmake_content, encoding="utf-8")
        print(f"[OK] 已生成 {cmake_path}")

    # ---- 生成 README.md（项目说明）----
    readme_path = target_dir / "README.md"
    if readme_path.exists() and not force:
        print(f"[跳过] {readme_path} 已存在（用 --force 覆盖）")
    else:
        generate_readme(config, readme_path)
        print(f"[OK] 已生成 {readme_path}")

    # ---- 生成 test/my_fmu_test.py（测试脚本）----
    test_path = target_dir / "test" / "my_fmu_test.py"
    if test_path.exists() and not force:
        print(f"[跳过] {test_path} 已存在（用 --force 覆盖）")
    else:
        generate_test_script(config, test_path)
        print(f"[OK] 已生成 {test_path}")

    print(f"\n项目骨架生成完成: {target_dir}")
    print("下一步:")
    print("  1. 编辑 fmu.yaml 声明你的变量")
    print("  2. 在 include/user_model.h 定义状态结构体")
    print("  3. 在 src/user_model.c 实现 init/step/terminate")
    print("  4. 运行 fmu-pack build 构建 FMU")
    print("  5. 运行 python test/my_fmu_test.py 测试")
    return 0


def cmd_gen_adapter(args: argparse.Namespace) -> int:
    """重新生成 fmi2_adapter.c

    用于 fmu.yaml 改动后，重新生成适配层（不编译）。
    """
    config_path = Path(args.config or "fmu.yaml")
    if not config_path.exists():
        print(f"[错误] 找不到 {config_path}")
        return 1

    config = load_config(config_path)
    project_dir = config_path.parent
    adapter_path = project_dir / "src" / "fmi2_adapter.c"
    generate_adapter(config, adapter_path)
    print(f"[OK] 已生成 {adapter_path}")
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
    """完整构建流程: 校验 → 生成代码 → 编译 → 打包

    七步流水线:
      1. 加载并校验 fmu.yaml
      2. 生成 fmi2_adapter.c（自动生成，永远与 fmu.yaml 同步）
      3. 生成 VR 路由头 fmi2_router.h
      4. 渲染 modelDescription.xml
      5. XSD schema 校验
      6. 调用编译器构建各平台共享库
      7. 组装 ZIP 打包为 .fmu
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
    print("[1/7] fmu.yaml 校验通过")

    project_dir = config_path.parent

    # 2. 生成 fmi2_adapter.c —— 永远从 fmu.yaml 重新生成（自动同步）
    adapter_path = generate_adapter(config, project_dir / "src" / "fmi2_adapter.c")
    print(f"[2/7] fmi2_adapter.c 已生成: {adapter_path}")

    # 3. 生成 VR 路由头
    include_dir = project_dir / "include"
    include_dir.mkdir(parents=True, exist_ok=True)
    router_h = generate_router_header(config, include_dir)
    print(f"[3/7] 路由头已生成: {router_h}")

    # 4. 渲染 modelDescription.xml
    xml_str = render_model_description(config)
    build_dir = project_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    xml_path = build_dir / "modelDescription.xml"
    xml_path.write_text(xml_str, encoding="utf-8")
    print(f"[4/7] modelDescription.xml 已渲染")

    # 5. XSD 校验
    xsd_path = Path(args.xsd) if args.xsd else None
    if xsd_path and xsd_path.exists():
        ok, msg = validate_xml(xml_str, xsd_path)
        if not ok:
            print(f"[XSD 校验失败] {msg}")
            return 3
        print("[5/7] XSD 校验通过")
    else:
        print("[5/7] 跳过 XSD 校验（未提供 xsd）")

    # 6. 构建
    platforms: list[str] = args.platform.split(",") if args.platform else config.get("platforms", ["win64"])
    binaries: dict[str, Path] = {}
    for plat in platforms:
        plat = plat.strip()
        print(f"[6/7] 构建平台: {plat}")
        result = build_platform(config, project_dir, plat, build_dir)
        if result:
            binaries[plat] = result
            print(f"      产物: {result}")
        else:
            print(f"      [失败] {plat} 构建出错")
            return 4

    # 7. 打包 FMU
    dist_dir = project_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    fmu_path = assemble_fmu(config, binaries, xml_path, project_dir, dist_dir)
    if fmu_path:
        print(f"[7/7] FMU 已生成: {fmu_path}")
    else:
        print("[7/7] FMU 打包失败")
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

    # init —— 生成完整项目骨架
    p_init = sub.add_parser("init", help="生成完整 FMU 项目骨架")
    p_init.add_argument("directory", nargs="?", help="目标目录（默认当前目录）")
    p_init.add_argument("--force", action="store_true", help="覆盖已存在文件")

    # validate —— 校验配置 + 可选 XSD 校验
    p_val = sub.add_parser("validate", help="校验 fmu.yaml + XSD")
    p_val.add_argument("--config", "-c", help="fmu.yaml 路径")
    p_val.add_argument("--xsd", help="fmi2ModelDescription.xsd 路径")

    # build —— 完整构建流水线
    p_build = sub.add_parser("build", help="完整构建 FMU")
    p_build.add_argument("--config", "-c", help="fmu.yaml 路径")
    p_build.add_argument("--platform", "-p", help="目标平台，逗号分隔（默认取 fmu.yaml 中的 platforms）")
    p_build.add_argument("--xsd", help="fmi2ModelDescription.xsd 路径")

    # gen-adapter —— 仅重新生成 fmi2_adapter.c
    p_ga = sub.add_parser("gen-adapter", help="仅重新生成 fmi2_adapter.c")
    p_ga.add_argument("--config", "-c", help="fmu.yaml 路径")

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
        "gen-adapter": cmd_gen_adapter,
        "gen-router": cmd_gen_router,
        "inspect": cmd_inspect,
        "clean": cmd_clean,
    }

    handler = handlers.get(args.command)
    if handler:
        sys.exit(handler(args))


if __name__ == "__main__":
    main()
