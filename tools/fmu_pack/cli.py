"""CLI 入口 —— fmu-pack 命令行工具

v2 重构：无 fmu.yaml
  - FMU 名称 = 顶层目录名（Path(dir).name）
  - 变量定义在 user_model.h（3 个固定结构体 + 3 个回调）
  - VR 工具按字段声明顺序自动分配
  - GUID 存到 build/.fmu-guid
"""

import argparse
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

from .header_parser import (
    parse_user_model_h, ParseError, ParsedModel,
)
from .adapter_gen import generate_adapter
from .xml_gen import render_model_description
from .validator import validate_xml
from .builder import build_platform
from .packager import assemble_fmu

from jinja2 import Environment, FileSystemLoader


# ---- Jinja2 环境（user_model.h / .c / README / test 模板）----
_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)
_README_TEMPLATE = _env.get_template("README.md.j2")
_TEST_TEMPLATE   = _env.get_template("my_fmu_test.py.j2")

# ---- user_model.h / .c 模板（内联，因小）----
USER_MODEL_H_TEMPLATE = """/* ============================================================
 * user_model.h —— 用户模型接口
 *
 * 三个固定结构体（causality 分组，工具按字段声明顺序分配 VR）:
 *   UserModelParameterT —— 可读可写 (causality=parameter)
 *   UserModelInputT     —— 可读可写 (causality=input)
 *   UserModelOutputT    —— 只读     (causality=output)
 *
 * 三个回调（用户实现）:
 *   int  model_init(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out);
 *   int  model_step(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out,
 *                   double t, double dt);
 *   void model_terminate(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out);
 *
 * 可选 #define MODEL_STEP_SIZE 0.001  定义内部定步长
 * ============================================================ */

#ifndef USER_MODEL_H_
#define USER_MODEL_H_

/* ---- 三个固定结构体（用户填充字段）---- */
typedef struct {
    /* TODO: 参数字段，类型可以是 double / int / bool / char[N] */
} UserModelParameterT;

typedef struct {
    /* TODO: 输入字段 */
} UserModelInputT;

typedef struct {
    /* TODO: 输出字段 */
} UserModelOutputT;

/* ---- 三个回调（用户实现，见 user_model.c）---- */
int  model_init(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out);
int  model_step(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out,
                double t, double dt);
void model_terminate(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out);

#endif /* USER_MODEL_H_ */
"""

USER_MODEL_C_TEMPLATE = """/* ============================================================
 * user_model.c —— 用户模型实现
 * 由 fmu-pack init 生成骨架，用户填充三个回调
 * ============================================================ */

#include "user_model.h"

int model_init(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out) {
    (void)p; (void)in; (void)out;
    /* TODO: 初始化字段（如 p->tau = 1.0;） */
    return 0;
}

int model_step(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out,
               double t, double dt) {
    (void)t; (void)dt;
    (void)p; (void)in; (void)out;
    /* TODO: 单步推进逻辑（如 out->y += dt * (in->u - out->y) / p->tau;） */
    return 0;
}

void model_terminate(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out) {
    (void)p; (void)in; (void)out;
    /* TODO: 释放动态分配资源（无 malloc 可留空） */
}
"""

# ---- 默认 CMakeLists.txt 模板 ----
CMAKE_TEMPLATE = """# CMakeLists.txt —— {model_identifier} FMU
# 由 fmu-pack init 生成；项目可手动修改
cmake_minimum_required(VERSION 3.20)
project({model_identifier} C)

include_directories("${{CMAKE_SOURCE_DIR}}/include")
include_directories("${{CMAKE_SOURCE_DIR}}/../../third_party/fmi2/include")

# 工具生成的 fmi2_adapter.c 在 build/ 下
include_directories("${{CMAKE_SOURCE_DIR}}/build")

add_library({model_identifier} SHARED
    src/user_model.c
    build/fmi2_adapter.c
)

set_target_properties({model_identifier} PROPERTIES
    PREFIX ""
    SUFFIX ".dll"
)

if(WIN32)
    target_compile_definitions({model_identifier} PRIVATE
        "FMI2_Export=__declspec(dllexport)"
    )
    if(MINGW)
        # 静态链接 C/C++ 运行时，让 FMU 自包含
        target_link_options({model_identifier} PRIVATE
            "-static-libgcc" "-static-libstdc++" "-static"
        )
    endif()
endif()
"""


# ---- 工具函数 ----

def _load_guid(project_dir: Path) -> str:
    """加载 GUID：build/.fmu-guid 存在则用，否则生成并写入"""
    guid_file = project_dir / "build" / ".fmu-guid"
    if guid_file.exists():
        return guid_file.read_text(encoding="utf-8").strip()
    guid = str(uuid.uuid4())
    guid_file.parent.mkdir(parents=True, exist_ok=True)
    guid_file.write_text(guid, encoding="utf-8")
    return guid


def _write_if_absent(path: Path, content: str, force: bool, label: str) -> bool:
    """如果 path 不存在（或 force=True）则写入"""
    if path.exists() and not force:
        print(f"[跳过] {path} 已存在（用 --force 覆盖）")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"[OK] 已生成 {label}: {path}")
    return True


# ---- 子命令实现 ----

def cmd_init(args: argparse.Namespace) -> int:
    """生成完整 FMU 项目骨架（v2：无 fmu.yaml）"""
    target_dir = Path(args.directory or ".")
    target_dir.mkdir(parents=True, exist_ok=True)
    force = getattr(args, "force", False)

    _write_if_absent(
        target_dir / "include" / "user_model.h",
        USER_MODEL_H_TEMPLATE, force, "user_model.h",
    )
    _write_if_absent(
        target_dir / "src" / "user_model.c",
        USER_MODEL_C_TEMPLATE, force, "user_model.c",
    )
    _write_if_absent(
        target_dir / "CMakeLists.txt",
        CMAKE_TEMPLATE.format(model_identifier=target_dir.name),
        force, "CMakeLists.txt",
    )

    # 立即生成 build/ 下的 fmi2_adapter.c 和 modelDescription.xml（基于默认骨架）
    parsed = parse_user_model_h(target_dir / "include" / "user_model.h")
    build_dir = target_dir / "build"
    build_dir.mkdir(exist_ok=True)
    generate_adapter(parsed, build_dir / "fmi2_adapter.c")
    guid = _load_guid(target_dir)
    xml = render_model_description(target_dir.name, guid, parsed)
    (build_dir / "modelDescription.xml").write_text(xml, encoding="utf-8")
    print(f"[OK] 已生成 build/fmi2_adapter.c (骨架)")
    print(f"[OK] 已生成 build/modelDescription.xml")

    print(f"\n项目骨架生成完成: {target_dir}")
    print("下一步:")
    print("  1. 编辑 include/user_model.h: 给 3 个结构体添加字段")
    print("  2. 编辑 src/user_model.c: 实现 3 个回调")
    print("  3. 运行 fmu-pack build 构建 FMU")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    """完整构建流程：解析 user_model.h → 生成代码 → 编译 → 打包"""
    project_dir = Path(args.directory or ".").resolve()
    if not (project_dir / "include" / "user_model.h").exists():
        print(f"[错误] 找不到 {project_dir}/include/user_model.h")
        print("先运行 fmu-pack init <dir> 生成骨架")
        return 2

    # 1. 解析 user_model.h
    try:
        parsed = parse_user_model_h(project_dir / "include" / "user_model.h")
    except ParseError as e:
        print(f"[错误] 解析 user_model.h 失败: {e}")
        return 2

    model_identifier = project_dir.name
    print(f"[1/6] user_model.h 解析通过 (params={len(parsed.parameter_fields)}, "
          f"inputs={len(parsed.input_fields)}, outputs={len(parsed.output_fields)}, "
          f"step_size={parsed.model_step_size})")

    # 2. 生成 fmi2_adapter.c
    build_dir = project_dir / "build"
    build_dir.mkdir(exist_ok=True)
    generate_adapter(parsed, build_dir / "fmi2_adapter.c")
    print(f"[2/6] build/fmi2_adapter.c 已生成")

    # 3. 渲染 modelDescription.xml
    guid = _load_guid(project_dir)
    xml = render_model_description(model_identifier, guid, parsed)
    xml_path = build_dir / "modelDescription.xml"
    xml_path.write_text(xml, encoding="utf-8")
    print(f"[3/6] build/modelDescription.xml 已生成")

    # 4. XSD 校验（可选）
    xsd_path = Path(args.xsd) if args.xsd else None
    if xsd_path and xsd_path.exists():
        ok, msg = validate_xml(xml, xsd_path)
        if not ok:
            print(f"[XSD 校验失败] {msg}")
            return 3
        print("[4/6] XSD 校验通过")
    else:
        print("[4/6] 跳过 XSD 校验（未提供 xsd）")

    # 5. 编译
    platforms: list[str] = args.platform.split(",") if args.platform else ["win64"]
    binaries: dict[str, Path] = {}
    for plat in platforms:
        plat = plat.strip()
        print(f"[5/6] 构建平台: {plat}")
        result = build_platform(model_identifier, project_dir, plat, build_dir)
        if result:
            binaries[plat] = result
            print(f"      产物: {result}")
        else:
            print(f"      [失败] {plat} 构建出错")
            return 4

    # 6. 打包
    dist_dir = project_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    fmu_path = assemble_fmu(model_identifier, guid, binaries, xml_path, project_dir, dist_dir)
    if fmu_path:
        print(f"[6/6] FMU 已生成: {fmu_path}")
    else:
        print("[6/6] FMU 打包失败")
        return 5

    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """清理 build/ dist/ 目录"""
    project_dir = Path(args.directory or ".")
    for d in ["build", "dist"]:
        target = project_dir / d
        if target.exists():
            shutil.rmtree(target)
            print(f"[OK] 已删除 {target}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """校验 user_model.h + 渲染 XML + XSD 校验"""
    project_dir = Path(args.directory or ".").resolve()
    h_path = project_dir / "include" / "user_model.h"
    if not h_path.exists():
        print(f"[错误] 找不到 {h_path}")
        return 1

    try:
        parsed = parse_user_model_h(h_path)
    except ParseError as e:
        print(f"[错误] {e}")
        return 2

    print("[OK] user_model.h 解析通过")
    for f in parsed.all_fields():
        print(f"  {f.causality:10s} {f.fmi_type:10s} {f.name} ({f.c_type})")

    guid = _load_guid(project_dir)
    xml = render_model_description(project_dir.name, guid, parsed)

    xsd_path = Path(args.xsd) if args.xsd else None
    if xsd_path and xsd_path.exists():
        ok, msg = validate_xml(xml, xsd_path)
        if not ok:
            print(f"[XSD 校验失败] {msg}")
            return 3
        print("[OK] XSD 校验通过")
    else:
        print("[提示] 未提供 XSD，跳过 schema 校验")
    return 0


def cmd_gen_adapter(args: argparse.Namespace) -> int:
    """仅重新生成 build/fmi2_adapter.c（不编译）"""
    project_dir = Path(args.directory or ".").resolve()
    h_path = project_dir / "include" / "user_model.h"
    if not h_path.exists():
        print(f"[错误] 找不到 {h_path}")
        return 1
    parsed = parse_user_model_h(h_path)
    build_dir = project_dir / "build"
    build_dir.mkdir(exist_ok=True)
    generate_adapter(parsed, build_dir / "fmi2_adapter.c")
    print(f"[OK] 已生成 {build_dir / 'fmi2_adapter.c'}")
    return 0


# ---- CLI 入口 ----

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fmu-pack",
        description="FMI 2.0 FMU 打包工具 —— 把 C 模型封装为标准 FMU",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="生成完整 FMU 项目骨架")
    p_init.add_argument("directory", nargs="?", help="目标目录（默认当前目录）")
    p_init.add_argument("--force", action="store_true", help="覆盖已存在文件")

    p_val = sub.add_parser("validate", help="校验 user_model.h + XSD")
    p_val.add_argument("directory", nargs="?", help="项目目录")
    p_val.add_argument("--xsd", help="fmi2ModelDescription.xsd 路径")

    p_build = sub.add_parser("build", help="完整构建 FMU")
    p_build.add_argument("directory", nargs="?", help="项目目录")
    p_build.add_argument("--platform", "-p", help="目标平台（默认 win64）")
    p_build.add_argument("--xsd", help="fmi2ModelDescription.xsd 路径")

    p_ga = sub.add_parser("gen-adapter", help="仅重新生成 fmi2_adapter.c")
    p_ga.add_argument("directory", nargs="?", help="项目目录")

    p_clean = sub.add_parser("clean", help="清理 build/ dist/")
    p_clean.add_argument("directory", nargs="?", help="项目目录")

    args = parser.parse_args()

    handlers = {
        "init": cmd_init,
        "validate": cmd_validate,
        "build": cmd_build,
        "gen-adapter": cmd_gen_adapter,
        "clean": cmd_clean,
    }

    handler = handlers.get(args.command)
    if handler:
        # 把 directory 作为第一个位置参数传给 handler
        sys.exit(handler(args))


if __name__ == "__main__":
    main()
