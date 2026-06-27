"""CMake 构建驱动 —— 调用项目自带的 CMakeLists.txt 做 out-of-source 构建

每个 FMU 项目自带 CMakeLists.txt（项目源文件的一部分，可版本管理）。
builder 只负责调用 cmake，不生成任何文件。

产物:
  - win64:   <modelIdentifier>.dll
  - linux64: <modelIdentifier>.so
  - darwin64:<modelIdentifier>.dylib
"""

import subprocess
from pathlib import Path
from typing import Any


def build_platform(
    config: dict[str, Any],
    project_dir: Path,
    platform: str,
    build_dir: Path,
) -> Path | None:
    """为指定平台构建共享库

    使用项目自带的 CMakeLists.txt 做 out-of-source 构建:
      cmake -S <project_dir> -B <build_dir>/<platform>
      cmake --build <build_dir>/<platform>

    Args:
        config: fmu.yaml 配置
        project_dir: 项目根目录（fmu.yaml 和 CMakeLists.txt 所在目录）
        platform: 目标平台 (win64/linux64/darwin64)
        build_dir: 构建输出根目录

    Returns:
        产物路径，失败返回 None
    """
    project_dir = project_dir.resolve()
    build_dir = build_dir.resolve()

    fmi = config["fmi"]
    mi = fmi["modelIdentifier"]

    # 检查 CMakeLists.txt 是否存在
    cmake_lists = project_dir / "CMakeLists.txt"
    if not cmake_lists.exists():
        print(f"      [错误] 缺少 CMakeLists.txt: {cmake_lists}")
        return None

    # out-of-source 构建目录
    plat_build_dir = build_dir / platform
    plat_build_dir.mkdir(parents=True, exist_ok=True)

    # 根据平台确定 generator 和产物后缀
    if platform == "win64":
        generator = "MinGW Makefiles"
        suffix = ".dll"
    elif platform == "linux64":
        generator = "Unix Makefiles"
        suffix = ".so"
    elif platform == "darwin64":
        generator = "Unix Makefiles"
        suffix = ".dylib"
    else:
        print(f"      [错误] 不支持的平台: {platform}")
        return None

    # ---- cmake 配置 ----
    configure_cmd = [
        "cmake", "-G", generator,
        "-DCMAKE_BUILD_TYPE=Release",
        "-S", str(project_dir),
        "-B", str(plat_build_dir),
    ]

    print(f"      [CMake] 配置中...")
    result = subprocess.run(
        configure_cmd, capture_output=True, text=True, cwd=str(project_dir)
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if stderr:
            print(f"      [CMake 配置失败] {stderr[:500]}")
        return None

    # ---- cmake 构建 ----
    build_cmd = [
        "cmake", "--build", str(plat_build_dir),
        "--config", "Release",
        "-j", "4",
    ]

    print(f"      [CMake] 构建中...")
    result = subprocess.run(
        build_cmd, capture_output=True, text=True, cwd=str(project_dir)
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if stderr:
            print(f"      [CMake 构建失败] {stderr[:800]}")
        stdout = result.stdout.strip()
        if stdout:
            print(f"      [CMake stdout] {stdout[:500]}")
        return None

    # ---- 查找产物 ----
    out_dll = plat_build_dir / f"{mi}{suffix}"
    if out_dll.exists():
        return out_dll

    # 有时 CMake 把产物放在子目录
    for candidate in plat_build_dir.rglob(f"{mi}{suffix}"):
        return candidate

    print(f"      [错误] 未找到产物 {mi}{suffix}")
    return None
