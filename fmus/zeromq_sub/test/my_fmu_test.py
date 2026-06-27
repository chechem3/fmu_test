"""zmqsub FMU 测试脚本

zmqsub 的数据来自 ZMQ socket（不是 FMI input），所以 input=None。
若无外部 ZMQ PUB 端，y 将保持 0（无新数据）。

运行:
  python test/my_fmu_test.py
"""

import os
import sys

try:
    from fmpy import simulate_fmu
    import numpy as np
except ImportError:
    print("[错误] FMPy 或 numpy 未安装")
    print("请运行: pip install fmpy numpy")
    sys.exit(1)


def main():
    fmu_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "dist", "zmqsub.fmu"
    )

    if not os.path.exists(fmu_path):
        print(f"[错误] 找不到 {fmu_path}")
        print("请先运行 fmu-pack build 生成 FMU")
        sys.exit(1)

    print(f"=== zmqsub FMU 测试 ===")
    print(f"FMU: {fmu_path}")
    print(f"提示: 无 ZMQ PUB 端时，y 保持为 0")
    print(f"      启动 PUB 端: python -c \"import zmq,time;")
    print(f"        c=zmq.Context();s=c.socket(zmq.PUB);s.bind('tcp://*:5555')\"")
    print()

    result = simulate_fmu(
        fmu_path,
        start_time=0,
        stop_time=5,
        step_size=0.1,
        output=["y", "has_new_data", "raw_value"],
        input=None,  # zmqsub 数据来自 ZMQ socket，不走 FMI input
    )

    # 打印关键时间点的输出
    print("时间(s)   y          raw_value   has_new_data")
    print("-" * 55)
    for t_check in [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]:
        idx = int(np.abs(result["time"] - t_check).argmin())
        y_val = result["y"][idx]
        raw_val = result["raw_value"][idx]
        has_new = result["has_new_data"][idx]
        print(f"{t_check:6.1f}    {y_val:9.4f}   {raw_val:9.4f}   {has_new:.0f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
