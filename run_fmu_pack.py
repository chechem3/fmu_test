#!/usr/bin/env python3
"""fmu-pack 运行入口 —— 直接调用 Python 脚本，无需 pip install

用法:
  python run_fmu_pack.py init [dir]
  python run_fmu_pack.py build --config fmus/rc_lowpass/fmu.yaml --xsd third_party/fmi2/schema/fmi2ModelDescription.xsd
  python run_fmu_pack.py inspect fmus/rc_lowpass/dist/rc_lowpass.fmu
"""

import sys
from pathlib import Path

# 将 tools/ 加入 Python 搜索路径
_project_root = Path(__file__).resolve().parent
_tools_dir = _project_root / "tools"
if str(_tools_dir) not in sys.path:
    sys.path.insert(0, str(_tools_dir))

from fmu_pack.cli import main

if __name__ == "__main__":
    main()
