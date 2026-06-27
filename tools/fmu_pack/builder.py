"""编译器构建驱动 —— 调用系统编译器生成共享库

当前策略:
  - 不使用 CMake（减少依赖），直接调用编译器命令行
  - Windows: 优先 MSVC (cl)，回退 MinGW (gcc)
  - Linux/macOS: 占位（当前环境无法交叉编译）

构建产物:
  - win64:   <modelIdentifier>.dll
  - linux64: <modelIdentifier>.so   (需在 Linux 环境)
  - darwin64:<modelIdentifier>.dylib (需在 macOS 环境)

关键编译选项:
  - FMI2_Export 宏: Windows 上设为 __declspec(dllexport) 导出符号
  - -O2: 优化级别
  - -shared: 生成共享库
"""

import subprocess
import shutil
from pathlib import Path
from typing import Any


def _find_third_party_dir(project_dir: Path, subpath: str) -> Path | None:
    """向上搜索 third_party/<subpath> 目录

    Args:
        project_dir: 项目目录（fmu.yaml 所在目录）
        subpath: third_party 下的子路径，如 "fmi2/include"

    Returns:
        目录路径，找不到返回 None
    """
    d = project_dir.resolve()
    for _ in range(5):
        candidate = d / "third_party" / subpath
        if candidate.is_dir():
            return candidate
        if d.parent == d:
            break
        d = d.parent
    return None


def build_platform(
    config: dict[str, Any],
    project_dir: Path,
    platform: str,
    build_dir: Path,
) -> Path | None:
    """为指定平台构建共享库

    构建步骤:
      1. 收集源文件（用户模型 + 适配层）
      2. 定位 FMI 头文件目录
      3. 解析 model.link 中的外部库依赖
      4. 根据平台选择编译器并执行编译

    Args:
        config: fmu.yaml 配置
        project_dir: 项目根目录
        platform: 目标平台 (win64/linux64/darwin64)
        build_dir: 构建输出目录

    Returns:
        产物路径，失败返回 None
    """
    project_dir = project_dir.resolve()
    build_dir = build_dir.resolve()

    fmi = config["fmi"]
    model = config.get("model", {})
    mi = fmi["modelIdentifier"]  # DLL 基名
    sources: list[str] = model.get("sources", [])

    # 适配层源文件必须存在（提供 fmi2* 导出符号）
    adapter_src = project_dir / "src" / "fmi2_adapter.c"
    if not adapter_src.exists():
        print(f"      [错误] 缺少适配层源文件: {adapter_src}")
        return None

    # 收集源文件（全部转为绝对路径，避免 cwd 问题）
    src_paths: list[Path] = []
    for s in sources:
        sp = (project_dir / s).resolve()
        if sp.exists():
            src_paths.append(sp)
        else:
            print(f"      [警告] 源文件不存在: {sp}")

    src_paths.append(adapter_src.resolve())

    # 平台构建子目录: build/win64/, build/linux64/, ...
    plat_build_dir = build_dir / platform
    plat_build_dir.mkdir(parents=True, exist_ok=True)

    # FMI 2.0 头文件目录（向上搜索，支持子项目结构）
    fmi2_include = _find_third_party_dir(project_dir, "fmi2/include")
    if fmi2_include is None:
        print("      [错误] 找不到 third_party/fmi2/include")
        return None
    # 用户项目头文件目录（包含 user_model.h 和生成的 fmi2_router.h）
    user_include = project_dir.resolve() / "include"

    # 解析外部库依赖（model.link 字段）
    link_cfg: dict[str, Any] = model.get("link", {})
    extra_includes: list[Path] = []
    extra_libs: list[str] = []
    extra_lib_dirs: list[Path] = []

    for lib_name, lib_spec in link_cfg.items():
        # lib_spec 可以是字符串路径或 {include, lib, libs} 字典
        if isinstance(lib_spec, str):
            # 简单形式: "zeromq" → 自动查找 third_party/zeromq/
            tp_dir = _find_third_party_dir(project_dir, lib_name)
            if tp_dir:
                inc = tp_dir / "include"
                if inc.is_dir():
                    extra_includes.append(inc)
                lib = tp_dir / "lib"
                if lib.is_dir():
                    extra_lib_dirs.append(lib)
                    # 扫描 .a 文件
                    for a in lib.glob("*.a"):
                        extra_libs.append(a.stem[3:] if a.stem.startswith("lib") else a.stem)
        elif isinstance(lib_spec, dict):
            inc_path = lib_spec.get("include")
            if inc_path:
                p = (project_dir / inc_path).resolve()
                if p.is_dir():
                    extra_includes.append(p)
            lib_dir = lib_spec.get("lib_dir")
            if lib_dir:
                p = (project_dir / lib_dir).resolve()
                if p.is_dir():
                    extra_lib_dirs.append(p)
            libs = lib_spec.get("libs", [])
            extra_libs.extend(libs)

    # 根据平台分发到对应构建函数
    if platform == "win64":
        return _build_windows(src_paths, mi, fmi2_include, user_include,
                              plat_build_dir, extra_includes, extra_lib_dirs, extra_libs)
    elif platform == "linux64":
        return _build_linux(src_paths, mi, fmi2_include, user_include, plat_build_dir)
    elif platform == "darwin64":
        return _build_macos(src_paths, mi, fmi2_include, user_include, plat_build_dir)
    else:
        print(f"      [错误] 不支持的平台: {platform}")
        return None


def _build_windows(
    src_paths: list[Path],
    mi: str,
    fmi2_include: Path,
    user_include: Path,
    build_dir: Path,
    extra_includes: list[Path] | None = None,
    extra_lib_dirs: list[Path] | None = None,
    extra_libs: list[str] | None = None,
) -> Path | None:
    """Windows 平台构建 —— 尝试 MSVC 和 MinGW

    编译器选择策略:
      1. 优先尝试 MSVC (cl.exe) —— 需要 Visual Studio 环境
      2. 回退 MinGW (gcc) —— 更常见于开源开发环境

    导出符号:
      MSVC: /DFMI2_Export="__declspec(dllexport)"
      MinGW: 默认所有符号可见，无需额外宏

    外部库链接:
      通过 extra_includes, extra_lib_dirs, extra_libs 参数传入。
      静态链接: 将 .a 文件直接链接进 DLL，避免 importer 找不到依赖。
    """
    if extra_includes is None:
        extra_includes = []
    if extra_lib_dirs is None:
        extra_lib_dirs = []
    if extra_libs is None:
        extra_libs = []

    fmi2_include = fmi2_include.resolve()
    user_include = user_include.resolve()
    build_dir = build_dir.resolve()

    # 构建 include 路径
    inc_parts = [f'-I"{fmi2_include}"', f'-I"{user_include}"']
    for inc in extra_includes:
        inc_parts.append(f'-I"{inc.resolve()}"')
    includes = " ".join(inc_parts)

    # 构建 lib 路径和库名
    lib_parts = []
    for ld in extra_lib_dirs:
        lib_parts.append(f'-L"{ld.resolve()}"')
    for lib in extra_libs:
        lib_parts.append(f"-l{lib}")
    # 链接 Windows 系统库
    lib_parts.extend(["-lws2_32", "-liphlpapi"])
    lib_flags = " ".join(lib_parts)

    # 如果有外部库，定义 ZMQ_STATIC 避免 __imp_ 前缀
    extra_defines = ""
    if extra_libs:
        extra_defines = " -DZMQ_STATIC"

    src_str = " ".join(f'"{p}"' for p in src_paths)

    # 按优先级尝试编译器
    for compiler, gflag in [("cl", "MSVC"), ("gcc", "MinGW")]:
        if shutil.which(compiler) is None:
            continue

        out_dll = build_dir / f"{mi}.dll"

        if compiler == "cl":
            # MSVC 编译命令
            msvc_includes = " ".join(f'/I"{inc.resolve()}"' for inc in [fmi2_include, user_include] + extra_includes)
            msvc_libs = " ".join(f'"{ld.resolve()}\\*.lib"' for ld in extra_lib_dirs)
            cmd = f'cl /nologo /LD /O2 {msvc_includes} /DFMI2_Export="__declspec(dllexport)" {src_str} {msvc_libs} /Fe:"{out_dll}"'
        else:
            # MinGW 编译: 静态链接外部库进 DLL
            # 如果有 C++ 外部库（如 ZeroMQ），用 g++ 链接但 gcc 编译
            if extra_libs:
                # 两步: gcc 编译 .c → .o, g++ 链接（ZeroMQ 是 C++ 库）
                obj_files: list[str] = []
                for sp in src_paths:
                    obj = build_dir / (sp.stem + ".o")
                    obj_files.append(str(obj))
                    compile_cmd = f'gcc -c -O2{extra_defines} {includes} "{sp}" -o "{obj}"'
                    subprocess.run(compile_cmd, shell=True, capture_output=True, text=True, cwd=str(build_dir))
                obj_str = " ".join(f'"{o}"' for o in obj_files)
                cmd = f'g++ -shared -O2 {obj_str} -o "{out_dll}" {lib_flags}'
            else:
                cmd = f'gcc -shared -O2 {includes} {src_str} -o "{out_dll}"'

        print(f"      [{gflag}] gcc -shared -O2 ... -o {out_dll}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=str(build_dir))
        if result.returncode == 0 and out_dll.exists():
            return out_dll
        else:
            stderr = result.stderr.strip()
            if stderr:
                print(f"      [{gflag} stderr] {stderr[:500]}")
            stdout = result.stdout.strip()
            if stdout:
                print(f"      [{gflag} stdout] {stdout[:500]}")

    print("      [错误] 未找到可用的 C 编译器（cl 或 gcc）")
    return None


def _build_linux(
    src_paths: list[Path],
    mi: str,
    fmi2_include: Path,
    user_include: Path,
    build_dir: Path,
) -> Path | None:
    """Linux gcc 构建（交叉编译占位）

    在 Windows 上无法直接构建 Linux .so。
    如需 linux64 产物，请在 Linux CI 环境中运行 fmu-pack build。
    """
    # 参数在当前平台下不使用，保留接口签名以便未来实现
    _ = (src_paths, mi, fmi2_include, user_include, build_dir)
    print("      [跳过] 当前环境无法构建 linux64")
    return None


def _build_macos(
    src_paths: list[Path],
    mi: str,
    fmi2_include: Path,
    user_include: Path,
    build_dir: Path,
) -> Path | None:
    """macOS clang 构建（交叉编译占位）

    在 Windows/Linux 上无法直接构建 macOS .dylib。
    如需 darwin64 产物，请在 macOS CI 环境中运行 fmu-pack build。
    """
    _ = (src_paths, mi, fmi2_include, user_include, build_dir)
    print("      [跳过] 当前环境无法构建 darwin64")
    return None
