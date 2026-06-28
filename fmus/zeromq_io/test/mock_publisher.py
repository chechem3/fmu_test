"""mock_publisher.py —— ZMQ 模拟输入源

绑定 PUB socket 在 SUB_PORT（默认 5556），周期性发送
`{"x":[c, 2c, 3c, 4c]}` （c = 1, 2, 3, ...），
每条消息还附带 `seq` 字段方便测试关联。

运行:
    python test/mock_publisher.py [--port 5556] [--duration 5] [--period 0.1]

可选 --log FILE 把每条发送写入日志（测试用）。
"""

import argparse
import json
import sys
import time

import zmq


def main() -> int:
    parser = argparse.ArgumentParser(description="ZMQ mock publisher for zeromq_io FMU test")
    parser.add_argument("--port", type=int, default=5556, help="PUB 绑定端口")
    parser.add_argument("--duration", type=float, default=5.0, help="运行时长（秒）")
    parser.add_argument("--period", type=float, default=0.1, help="发送间隔（秒）")
    parser.add_argument("--log", type=str, default=None, help="可选：把每条发送写入此文件")
    args = parser.parse_args()

    ctx = zmq.Context.instance()
    pub = ctx.socket(zmq.PUB)
    bind_endpoint = f"tcp://127.0.0.1:{args.port}"
    pub.bind(bind_endpoint)
    print(f"[mock_publisher] PUB bound on {bind_endpoint}, duration={args.duration}s, period={args.period}s")

    log_fh = open(args.log, "w", encoding="utf-8") if args.log else None

    t_end = time.time() + args.duration
    seq = 0
    while time.time() < t_end:
        # seq += 1
        # x = [float(seq), float(seq * 2), float(seq * 3), float(seq * 4)]
        x = [2, 2, 2, 2]
        msg = {"x": x, "seq": seq}
        body = json.dumps(msg)
        pub.send_string(body)
        if log_fh:
            log_fh.write(body + "\n")
            log_fh.flush()
        time.sleep(args.period)

    if log_fh:
        log_fh.close()
    pub.close()
    ctx.term()
    print(f"[mock_publisher] sent {seq} messages, exit")
    return 0


if __name__ == "__main__":
    sys.exit(main())