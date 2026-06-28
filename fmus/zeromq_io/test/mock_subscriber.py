"""mock_subscriber.py —— ZMQ 模拟输出消费端

连接 SUB socket 到 PUB_PORT（默认 5555），接收 FMU 发布的 `{"y":[...]}`
消息，每条消息：
  - 解析 y 数组
  - 断言 y[i] - y[0] == i * (y[1] - y[0])   （线性结构）
  - 把消息写入日志（可选）

运行:
    python test/mock_subscriber.py [--port 5555] [--timeout 5] [--log FILE]
"""

import argparse
import json
import sys
import time

import zmq


def is_linear_payload(y: list) -> bool:
    """检查 y 是否为 [a, a+d, a+2d, a+3d] 形式（等差数列）。
    真实 FMU 输出 y[i] = x[i] + 1，x 是 [c, 2c, 3c, 4c]，
    所以 y 应该是 [c+1, 2c+1, 3c+1, 4c+1]，公差 d=c。
    """
    if len(y) != 4:
        return False
    d = y[1] - y[0]
    return all(abs((y[i] - y[0]) - i * d) < 1e-6 for i in range(4))


def main() -> int:
    parser = argparse.ArgumentParser(description="ZMQ mock subscriber for zeromq_io FMU test")
    parser.add_argument("--port", type=int, default=5555, help="SUB 连接端口")
    parser.add_argument("--timeout", type=float, default=5.0, help="接收超时（秒）")
    parser.add_argument("--log", type=str, default=None, help="可选：把每条接收写入此文件")
    args = parser.parse_args()

    ctx = zmq.Context.instance()
    sub = ctx.socket(zmq.SUB)
    sub.setsockopt(zmq.RCVTIMEO, int(args.timeout * 1000))  # 毫秒
    sub.setsockopt_string(zmq.SUBSCRIBE, "")
    connect_endpoint = f"tcp://127.0.0.1:{args.port}"
    sub.connect(connect_endpoint)
    print(f"[mock_subscriber] SUB connected to {connect_endpoint}, timeout={args.timeout}s")

    log_fh = open(args.log, "w", encoding="utf-8") if args.log else None

    received = 0
    errors = 0
    while True:
        try:
            body = sub.recv_string()
        except zmq.error.Again:
            print(f"[mock_subscriber] recv timeout, exit")
            break

        received += 1
        try:
            msg = json.loads(body)
            y = msg["y"]
            if not is_linear_payload(y):
                errors += 1
                print(f"[mock_subscriber] WARN: msg {received} not linear: {y}")
            if log_fh:
                log_fh.write(body + "\n")
                log_fh.flush()
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            errors += 1
            print(f"[mock_subscriber] WARN: parse error on msg {received}: {e} body={body!r}")

    if log_fh:
        log_fh.close()
    sub.close()
    ctx.term()
    print(f"[mock_subscriber] received {received} messages, errors {errors}, exit")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())