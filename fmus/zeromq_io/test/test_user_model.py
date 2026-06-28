"""zeromq_io FMU 端到端测试

流程：
  1. 启动 mock_subscriber 子进程（先连 SUB，等消息）
  2. 启动 mock_publisher 子进程（在 PUB 上发输入数据）
  3. 等 ZMQ 套接字就绪（约 500ms）
  4. 用 FMPy 仿真 zeromq_io FMU
  5. 关闭 publisher，等待 subscriber 收完剩余消息
  6. 验证：FMPy 仿真期间至少有一些 step 被调用（通过输出值非零判断）

前置条件:
  pip install fmpy pyzmq

运行:
  python test/test_user_model.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def find_fmu() -> Path:
    """定位已构建的 FMU"""
    candidates = [
        Path(__file__).resolve().parent.parent / "dist" / "zeromq_io.fmu",
        Path("fmus/zeromq_io/dist/zeromq_io.fmu"),
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        "找不到 zeromq_io.fmu，请先运行 `python run_fmu_pack.py build fmus/zeromq_io`"
    )


def main() -> int:
    fmu_path = find_fmu()
    test_dir = Path(__file__).resolve().parent
    print(f"[test] FMU: {fmu_path}")
    print(f"[test] test dir: {test_dir}")

    # 临时目录：放日志
    tmp_dir = Path(tempfile.mkdtemp(prefix="zeromq_io_test_"))
    pub_log = tmp_dir / "publisher.log"
    sub_log = tmp_dir / "subscriber.log"
    print(f"[test] tmp dir: {tmp_dir}")

    # 仿真参数
    sub_port = 5555
    pub_port = 5556
    duration = 5.0
    step_size = 0.1

    # ---- 启动 subscriber（先连 SUB 监听，等 publisher 上线）----
    subscriber = subprocess.Popen(
        [
            sys.executable,
            str(test_dir / "mock_subscriber.py"),
            "--port", str(sub_port),
            "--timeout", str(duration + 2.0),  # 比仿真稍长，确保收完
            "--log", str(sub_log),
        ],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    time.sleep(0.3)  # 等 SUB connect

    # ---- 启动 publisher（发输入）----
    publisher = subprocess.Popen(
        [
            sys.executable,
            str(test_dir / "mock_publisher.py"),
            "--port", str(pub_port),
            "--duration", str(duration),
            "--period", str(step_size),
            "--log", str(pub_log),
        ],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )

    # 等 ZMQ 套接字就绪：PUB bind + SUB connect + slow joiner 防护
    time.sleep(2.0)

    # ---- FMPy 仿真 ----
    try:
        from fmpy import simulate_fmu
    except ImportError:
        print("[错误] FMPy 未安装，请运行: pip install fmpy")
        publisher.kill(); subscriber.kill()
        shutil.rmtree(tmp_dir)
        return 1

    print(f"[test] start FMPy simulation: duration={duration}s, step_size={step_size}s")
    result = simulate_fmu(
        str(fmu_path),
        start_time=0,
        stop_time=duration,
        step_size=step_size,
        # 输入来自 ZMQ，importer 的 input 参数对 zeromq_io 无效，置 None
        output=["y0", "y1", "y2", "y3"],
        # 通过 fmi2SetReal 把端口传给 FMU（VR 1=sub_endpoint, 2=pub_endpoint）
        start_values={
            "sub_endpoint": f"tcp://127.0.0.1:{pub_port}",
            "pub_endpoint": f"tcp://*:{sub_port}",
        },
    )

    # ---- 等待 publisher 跑完 ----
    pub_rc = publisher.wait(timeout=duration + 2)
    if pub_rc != 0:
        print(f"[WARN] publisher exit code {pub_rc}")
        if publisher.stdout:
            print(publisher.stdout.read())

    # ---- 等待 subscriber 收完（recv timeout 触发后退出）----
    sub_rc = subscriber.wait(timeout=duration + 5)
    if sub_rc != 0:
        print(f"[WARN] subscriber exit code {sub_rc}")

    if subscriber.stdout:
        sub_stdout = subscriber.stdout.read()
        if sub_stdout:
            print("---- subscriber stdout ----")
            print(sub_stdout)
    if publisher.stdout:
        pub_stdout = publisher.stdout.read()
        if pub_stdout:
            print("---- publisher stdout ----")
            print(pub_stdout)

    # ---- 验证 ----
    print("\n=== 验证 ===")

    # 1. FMPy 输出 y* 终值非零（说明 model_step 被调用过）
    if len(result["y0"]) == 0:
        print("[FAIL] FMPy 没有产生任何输出")
        return 1
    final_y = [result[f"y{i}"][-1] for i in range(4)]
    print(f"FMPy final y: {final_y}")
    if all(v == 0.0 for v in final_y):
        print("[FAIL] FMPy 输出全 0，FMU 未被调用")
        return 1
    if all(v == 1.0 for v in final_y):
        print("[FAIL] FMPy 输出全 1（x 收到 0 → y=0+1），FMU 未收到 ZMQ 输入")
        return 1

    # 2. FMPy 输出 y[i] 应该是等差数列（y[i] = x[i]+1, x = [c, 2c, 3c, 4c]）
    d = final_y[1] - final_y[0]
    is_linear = all(abs((final_y[i] - final_y[0]) - i * d) < 1e-6 for i in range(4))
    if not is_linear:
        print(f"[FAIL] FMPy 输出 y 不符合等差结构: {final_y}")
        return 1
    if d <= 0:
        print(f"[FAIL] FMPy 输出 y 公差 d={d} <= 0，FMU 未收到非零 x")
        return 1
    print(f"[OK] FMPy 输出 y 符合等差结构，公差 d = {d}")

    # 3. subscriber 收到的消息数 > 0
    if not sub_log.exists():
        print(f"[WARN] subscriber 日志文件 {sub_log} 不存在")
        return 1
    sub_lines = [ln for ln in sub_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    print(f"subscriber 收到 {len(sub_lines)} 条消息")
    if len(sub_lines) == 0:
        print("[FAIL] subscriber 没收到任何消息")
        return 1

    # 4. subscriber 日志里每条 y 都是等差数列
    bad_count = 0
    for ln in sub_lines:
        try:
            msg = json.loads(ln)
            y = msg["y"]
            d_local = y[1] - y[0]
            if not all(abs((y[i] - y[0]) - i * d_local) < 1e-6 for i in range(4)):
                bad_count += 1
        except Exception:
            bad_count += 1
    if bad_count > 0:
        print(f"[FAIL] subscriber 日志里 {bad_count}/{len(sub_lines)} 条消息结构异常")
        return 1
    print(f"[OK] subscriber 日志里 {len(sub_lines)} 条消息全部符合等差结构")

    # 5. y[i] = x[i] + 1 严格关联验证：
    #    把 pub_log 和 sub_log 按到达时间排，匹配 seq；
    #    验证至少一条消息的 x[i]+1 == y[i]
    if not pub_log.exists():
        print("[FAIL] publisher 日志不存在")
        return 1
    pub_msgs = []
    for ln in pub_log.read_text(encoding="utf-8").splitlines():
        try:
            pub_msgs.append(json.loads(ln))
        except Exception:
            pass
    sub_msgs = []
    for ln in sub_log.read_text(encoding="utf-8").splitlines():
        try:
            sub_msgs.append(json.loads(ln))
        except Exception:
            pass
    if not pub_msgs:
        print("[FAIL] publisher 没发任何消息")
        return 1
    if not sub_msgs:
        print("[FAIL] subscriber 没收到任何消息")
        return 1
    print(f"[INFO] pub 发了 {len(pub_msgs)} 条，sub 收了 {len(sub_msgs)} 条")

    # 把 pub_msgs 按 seq 索引；验证每条 sub_msg 的 y 是否等于某个 pub x + 1
    # 由于 CONFLATE，sub 收到的消息数会远大于 pub（每个 FMU step 都发一次），
    # 关联方式：每个 sub y 找最近的 pub x（即 y[i] - 1 应当匹配某个 pub x[i]）
    pub_by_x = {}
    for m in pub_msgs:
        x = m["x"]
        pub_by_x[tuple(x)] = m
    matched = 0
    unmatched = 0
    for m in sub_msgs[:100]:  # 只检查前 100 条
        y = m["y"]
        x_expected = tuple(v - 1.0 for v in y)
        if x_expected in pub_by_x:
            matched += 1
        else:
            unmatched += 1
    print(f"[INFO] 前 100 条 sub 消息：{matched} 条匹配 pub x，{unmatched} 条不匹配")
    if matched == 0:
        print("[FAIL] 没有一条 sub 消息的 y[i]-1 能匹配任何 pub x（FMU 未收到 ZMQ 输入）")
        return 1
    if matched < len(sub_msgs[:100]) * 0.8:
        print(f"[WARN] 匹配率 {matched}/{len(sub_msgs[:100])} 偏低（可能 CONFLATE 漂移）")

    print("\n[PASS] 所有验证通过")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())