"""FMU ZIP 组装与打包

将编译产物、XML 描述文件、可选资源组装为符合 FMI 2.0 规范的 .fmu 文件。

.fmu 本质是一个 ZIP 文件，内部结构:
  modelDescription.xml          —— 必选，根目录
  binaries/<platform>/<mi>.dll  —— 二进制型 FMU 必选
  resources/                    —— 可选，额外资源文件
  documentation/                —— 可选，文档（index.html 等）

FMI 2.0 平台目录名约定:
  win64    → binaries/win64/<mi>.dll
  linux64  → binaries/linux64/<mi>.so
  darwin64 → binaries/darwin64/<mi>.dylib

ZIP 规范要求:
  - 路径分隔符必须为正斜杠 /
  - 压缩方法为 deflate (8) 或 store (0)
  - 不使用加密
"""

import zipfile
import hashlib
from pathlib import Path
from typing import Any


def assemble_fmu(
    model_identifier: str,
    guid: str,
    binaries: dict[str, Path],
    xml_path: Path,
    project_dir: Path,
    dist_dir: Path,
) -> Path | None:
    """将二进制 + XML + 资源组装为 .fmu

    组装顺序:
      1. modelDescription.xml → ZIP 根目录
      2. 各平台二进制 → binaries/<plat>/<mi>.<ext>
      3. resources/ 目录（可选）→ ZIP 内 resources/
      4. documentation/ 目录（可选）→ ZIP 内 documentation/
      5. 生成 SHA256 校验文件

    Args:
        model_identifier: FMU 名称（= 顶层目录名）
        guid: FMU GUID（来自 build/.fmu-guid）
        binaries: {platform: dll_path} 各平台编译产物
        xml_path: modelDescription.xml 文件路径
        project_dir: 项目根目录（用于查找 resources/ documentation/）
        dist_dir: 产物输出目录

    Returns:
        .fmu 文件路径，失败返回 None
    """
    mi = model_identifier
    fmu_name = f"{mi}.fmu"
    fmu_path = dist_dir / fmu_name

    # FMI 2.0 平台目录名映射（必须严格匹配，否则 importer 找不到库）
    plat_dirs = {
        "win64": "binaries/win64",
        "linux64": "binaries/linux64",
        "darwin64": "binaries/darwin64",
    }

    # 使用 ZIP_DEFLATED 压缩（FMI 规范允许的方法 8）
    with zipfile.ZipFile(fmu_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. modelDescription.xml —— 必须放在 ZIP 根目录
        zf.write(xml_path, "modelDescription.xml")

        # 2. 二进制文件 —— 按平台放入对应子目录
        for plat, dll_path in binaries.items():
            plat_dir = plat_dirs.get(plat)
            if plat_dir is None:
                print(f"      [警告] 未知平台 {plat}，跳过")
                continue
            if not dll_path.exists():
                print(f"      [警告] 二进制不存在: {dll_path}")
                continue
            # ZIP 内路径使用正斜杠（FMI 规范要求）
            arcname = f"{plat_dir}/{dll_path.name}"
            zf.write(dll_path, arcname)

        # 3. resources/ —— 可选资源目录（模型运行时可能需要的文件）
        resources_dir = project_dir / "resources"
        if resources_dir.is_dir():
            for f in resources_dir.rglob("*"):
                if f.is_file():
                    # 路径分隔符统一为正斜杠
                    arcname = "resources/" + str(f.relative_to(resources_dir)).replace("\\", "/")
                    zf.write(f, arcname)

        # 4. documentation/ —— 可选文档目录
        doc_dir = project_dir / "documentation"
        if doc_dir.is_dir():
            for f in doc_dir.rglob("*"):
                if f.is_file():
                    arcname = "documentation/" + str(f.relative_to(doc_dir)).replace("\\", "/")
                    zf.write(f, arcname)

    # 5. 生成 SHA256 校验文件 —— 便于验证 FMU 完整性
    sha = hashlib.sha256()
    with open(fmu_path, "rb") as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    manifest_path = dist_dir / f"{mi}.fmu.sha256"
    manifest_path.write_text(f"{sha.hexdigest()}  {fmu_name}\n")

    return fmu_path
