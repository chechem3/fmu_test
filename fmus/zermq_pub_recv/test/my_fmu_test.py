"""MyModel FMU 测试脚本

使用 FMPy 加载并仿真生成的 FMU。

前置条件:
  pip install fmpy

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
        "..", "dist", "MyModel.fmu"
    )

    if not os.path.exists(fmu_path):
        print(f"[错误] 找不到 {fmu_path}")
        print("请先运行 fmu-pack build 生成 FMU")
        sys.exit(1)

    print(f"=== MyModel FMU 测试 ===")
    print(f"FMU: {fmu_path}")
    print()

    # ---- 仿真配置 ----
    # FMPy 0.3 API:
    #   output: 要记录输出的变量名列表
    #   input:  numpy 结构化数组
    #           dtype=[('time', float), (var_name, float), ...]
    # 详见: https://github.com/CATIA-Systems/FMPy/blob/master/fmpy/simulation.py

    # TODO: 根据 fmu.yaml 的 variables 配置 input 和 output
    # 示例: 给 input 'u' 一个阶跃信号（t=0 起 u=1.0）
    #
    # input_signal = np.array(
    #     [(0.0, 1.0), (10.0, 1.0)],
    #     dtype=[("time", np.float64), ("u", np.float64)],
    # )

    # 找出所有 input 变量，构造空输入信号（用 start 值）
    input_names = ["u", ]
    if input_names:
        dtype = [("time", np.float64)] + [(n, np.float64) for n in input_names]
        input_signal = np.array(
            [(0.0,) + tuple([0.0] * len(input_names))],
            dtype=dtype,
        )
    else:
        input_signal = None

    output_vars = ["y"]

    result = simulate_fmu(
        fmu_path,
        start_time=0,
        stop_time=10,
        step_size=0.1,
        output=output_vars,
        input=input_signal,
    )

    # 打印关键时间点的输出
    print("时间(s)   " + "  ".join(f"{v:>10s}" for v in output_vars))
    print("-" * (20 + 12 * len(output_vars)))
    for t_check in [0.0, 1.0, 2.0, 5.0, 10.0]:
        idx = int(np.abs(result["time"] - t_check).argmin())
        values = "  ".join(f"{result[v][idx]:10.4f}" for v in output_vars)
        print(f"{t_check:6.1f}    {values}")

    # ---- 验证 ----
    # TODO: 根据模型物理含义验证结果
    # 例如 RC 低通: t=5τ 后 y 应接近 1-1/e^5 ≈ 0.993
    #
    # if output_vars and len(result) > 0:
    #     final_value = result[output_vars[0]][-1]
    #     print(f"\n最终值: {output_vars[0]} = {final_value}")

    return 0


if __name__ == "__main__":
    sys.exit(main())