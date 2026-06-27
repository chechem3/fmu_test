/**
 * user_model.h —— ZeroMQ 订阅 FMU 用户模型接口
 *
 * 通过 ZeroMQ SUB socket 接收外部数据，作为 FMU 的输入信号。
 * 适配层在 doStep 中调用 zmq_poll + zmq_recv 获取最新值。
 */

#ifndef USER_MODEL_H_
#define USER_MODEL_H_

/* ---- 模型状态结构体 ---- */
typedef struct {
    double gain;       /* 增益系数，parameter */
    double y;          /* 输出 = 接收值 * gain */
    double raw_value;  /* 从 ZMQ 收到的原始值 */
    int has_new_data;  /* 是否有新数据到达 */

    /* ZeroMQ 资源（不透明指针） */
    void* zmq_ctx;     /* ZMQ context */
    void* zmq_sock;    /* ZMQ SUB socket */
} ZmqSubState;

/* ---- 模型回调 ---- */

/**
 * 初始化模型状态和 ZeroMQ 连接
 * @param state  模型实例
 * @return 0=成功, -1=失败
 */
int zmqsub_init(ZmqSubState* state);

/**
 * 检查 ZeroMQ 是否有新数据到达（非阻塞）
 * 如果有新数据，解析为 double 存入 state->raw_value
 * @param state  模型实例
 * @param t      当前时间（通信点）
 * @param dt     步长
 * @return 0=成功
 */
int zmqsub_step(ZmqSubState* state, double t, double dt);

/**
 * 销毁模型，关闭 ZeroMQ 连接
 * @param state  模型实例
 */
void zmqsub_terminate(ZmqSubState* state);

#endif /* USER_MODEL_H_ */
