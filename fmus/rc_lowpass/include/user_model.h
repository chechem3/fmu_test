/**
 * user_model.h —— RC 低通滤波器用户模型接口
 *
 * 用户模型不感知 FMI，只暴露纯 C 回调结构体。
 * 适配层通过此接口驱动模型。
 */

#ifndef USER_MODEL_H_
#define USER_MODEL_H_

/* ---- 模型状态结构体 ---- */
typedef struct {
    double tau;  /* 时间常数，parameter */
    double u;    /* 输入信号 */
    double y;    /* 输出信号 */
} RcState;

/* ---- 模型回调 ---- */

/**
 * 初始化模型状态
 * @param state  模型实例
 * @return 0=成功
 */
int rc_init(RcState* state);

/**
 * 单步推进（欧拉法）
 *   dy/dt = (u - y) / tau
 * @param state  模型实例
 * @param t      当前时间（通信点）
 * @param dt     步长
 * @return 0=成功
 */
int rc_step(RcState* state, double t, double dt);

/**
 * 销毁模型（释放资源）
 * @param state  模型实例
 */
void rc_terminate(RcState* state);

#endif /* USER_MODEL_H_ */
