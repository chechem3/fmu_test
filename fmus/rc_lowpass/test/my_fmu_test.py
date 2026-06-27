"""rc_lowpass FMU 测试脚本

验证 RC 低通滤波器的阶跃响应：
- t=0 输入 u 阶跃到 1.0
- t=10 (5 个时间常数后)，输出 y 应接近 1.0

运行:
  python test/my_fmu_test.py
"""

import os
import sys

try:
    from fmpy import simulate_fmu
except ImportError:
    print("[错误] FMPy 未安装")
    print("请运行: pip install fmpy")
    sys.exit(1)

import numpy as np


def main():
    fmu_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "dist", "rc_lowpass.fmu"
    )

    if not os.path.exists(fmu_path):
        print(f"[错误] 找不到 {fmu_path}")
        print("请先运行 fmu-pack build 生成 FMU")
        sys.exit(1)

    print(f"=== rc_lowpass FMU 测试 ===")
    print(f"FMU: {fmu_path}")
    print(f"输入: 阶跃信号 u=1.0 (t=0..10)")
    print(f"仿真: t=0..10, dt=0.1")
    print()

    # FMPy 0.3 input 格式: numpy 结构化数组
    # dtype 必须有 'time' 字段，每个输入变量一个字段
    input_signal = np.array(
        [(0.0, 1.0), (10.0, 1.0)],
        dtype=[("time", np.float64), ("u", np.float64)],
    )

    result = simulate_fmu(
        fmu_path,
        start_time=0,
        stop_time=10,
        step_size=0.1,
        output=["y"],
        input=input_signal,
    )

    # 打印关键时间点的输出
    print("时间(s)   y")
    print("-" * 25)
    for t_check in [0.0, 1.0, 2.0, 5.0, 10.0]:
        # 找最近的时间点（FMPy 0.3 的 SimulationResult 是 numpy 结构化数组）
        idx = int(np.abs(result["time"] - t_check).argmin())
        y_val = result["y"][idx]
        print(f"{t_check:6.1f}    {y_val:.6f}")

    # 验证: 5 个时间常数后 (t=5*tau=5)，y 应接近 1-1/e ≈ 0.993
    final_y = result["y"][-1]
    expected = 1.0 - 1.0 / 2.71828  # 5 个 tau 后的解析解
    print()
    print(f"最终值 y(10) = {final_y:.6f}")
    print(f"解析解 y(5τ) = {expected:.6f} (5 个时间常数后)")
    if abs(final_y - expected) < 0.01:
        print("[OK] 通过")
    else:
        print(f"[WARN] 偏差 {(final_y - expected) * 100:.2f}%")

    return 0


if __name__ == "__main__":
    sys.exit(main())
