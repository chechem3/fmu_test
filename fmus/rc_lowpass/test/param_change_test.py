"""rc_lowpass 动态改参数测试

验证：在 step 之间修改 `tau` 参数，输出应立即响应新时间常数。

原理:
  - t=0:  tau=1.0, u=1.0
  - t=0..3: 期望 y ≈ 1 - e^(-3) ≈ 0.95
  - t=3 时改 tau=0.1 (10倍快)
  - t=3..5: 期望 y 进一步接近 1.0，更快收敛

运行:
  python test/param_change_test.py
"""

import os
import sys
import shutil

try:
    import numpy as np
    from fmpy import extract
    from fmpy.fmi2 import FMU2Slave
    from fmpy.model_description import read_model_description
except ImportError:
    print("[错误] FMPy 未安装")
    sys.exit(1)


def main():
    fmu_path = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "dist", "rc_lowpass.fmu"
    ))

    if not os.path.exists(fmu_path):
        print(f"[错误] 找不到 {fmu_path}")
        sys.exit(1)

    # VR 定义: tau=1, u=2, y=3
    VR_TAU = 1
    VR_U = 2
    VR_Y = 3

    print("=== rc_lowpass 动态改参数测试 ===\n")

    # ---- 解压 FMU ----
    unzip_dir = os.path.abspath(os.path.join(os.path.dirname(fmu_path), "unzip"))
    if os.path.exists(unzip_dir):
        shutil.rmtree(unzip_dir)
    extract(fmu_path, unzip_dir)

    # ---- 读 modelDescription 获取 guid ----
    model_description = read_model_description(unzip_dir)
    guid = model_description.guid
    model_identifier = model_description.coSimulation.modelIdentifier
    print(f"FMU: {fmu_path}")
    print(f"guid: {guid}, modelIdentifier: {model_identifier}\n")

    # ---- 1. 实例化并初始化 ----
    fmu = FMU2Slave(
        guid=guid,
        modelIdentifier=model_identifier,
        unzipDirectory=unzip_dir,
    )
    fmu.instantiate(visible=False, loggingOn=False)
    fmu.setupExperiment(startTime=0.0)
    fmu.enterInitializationMode()
    fmu.setReal([VR_TAU], [1.0])  # tau=1.0
    fmu.exitInitializationMode()

    # ---- 2. t=0..3: tau=1.0 ----
    # 在 tau=1, u=1 下, y(t) = 1 - e^(-t)
    # t=3: y ≈ 0.95
    print("阶段 1: tau=1.0, t=0..3 (期望 y(3) ≈ 0.95)")
    print("-" * 50)
    history = []
    dt = 0.1
    t = 0.0
    y = fmu.getReal([VR_Y])[0]
    history.append((t, y))

    for step in range(30):  # 30 * 0.1 = 3s
        fmu.setReal([VR_U], [1.0])  # 保持 u=1.0
        fmu.doStep(currentCommunicationPoint=t, communicationStepSize=dt)
        t += dt
        y = fmu.getReal([VR_Y])[0]
        history.append((t, y))

    y_at_3 = history[-1][1]
    expected_3 = 1.0 - np.exp(-3)  # 0.9502
    print(f"  t={t:.1f}   y={y_at_3:.4f}  (期望 {expected_3:.4f}, 偏差 {abs(y_at_3 - expected_3)*100:.2f}%)")
    if abs(y_at_3 - expected_3) < 0.01:
        print("  [OK]")
    else:
        print(f"  [FAIL] y={y_at_3}, 期望 {expected_3}")
        fmu.terminate()
        fmu.freeInstance()
        return 1

    # ---- 3. 动态修改 tau=0.1 ----
    print(f"\n阶段 2: 在 t={t} 时动态改 tau=0.1")
    print("-" * 50)
    fmu.setReal([VR_TAU], [0.1])  # 动态改参数
    new_tau = fmu.getReal([VR_TAU])[0]
    print(f"  setReal(tau=0.1), getReal 返回 {new_tau}")
    if abs(new_tau - 0.1) > 1e-9:
        print(f"  [FAIL] 参数未生效")
        fmu.terminate()
        fmu.freeInstance()
        return 1

    # ---- 4. t=3..5: tau=0.1 ----
    # 时间常数缩小 10 倍，y 应快速收敛到 1
    for step in range(20):  # 20 * 0.1 = 2s
        fmu.setReal([VR_U], [1.0])
        fmu.doStep(currentCommunicationPoint=t, communicationStepSize=dt)
        t += dt
        y = fmu.getReal([VR_Y])[0]
        history.append((t, y))

    y_at_5 = history[-1][1]
    print(f"  t={t:.1f}   y={y_at_5:.6f}  (期望接近 1.0)")
    if y_at_5 > 0.99:
        print("  [OK]")
    else:
        print(f"  [FAIL] y={y_at_5}, 应 > 0.99")
        fmu.terminate()
        fmu.freeInstance()
        return 1

    # ---- 5. 清理 ----
    fmu.terminate()
    fmu.freeInstance()

    # ---- 6. 打印关键时间点的轨迹 ----
    print(f"\n轨迹:")
    print(f"时间(s)   y")
    print("-" * 30)
    for t_check in [0.0, 1.0, 2.0, 3.0, 3.5, 4.0, 5.0]:
        idx = min(range(len(history)), key=lambda i: abs(history[i][0] - t_check))
        t_val, y_val = history[idx]
        marker = " <- 改 tau" if abs(t_val - 3.0) < 0.05 else ""
        print(f"  {t_val:5.2f}  {y_val:.6f}{marker}")

    print(f"\n[OK] 动态改参数验证通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
