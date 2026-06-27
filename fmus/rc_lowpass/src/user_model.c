/**
 * user_model.c —— RC 低通滤波器实现
 *
 * 数学模型:
 *   dy/dt = (u - y) / tau
 *   y(0) = 0
 *
 * 离散化（欧拉法）:
 *   y_{k+1} = y_k + dt * (u_k - y_k) / tau
 */

#include "user_model.h"
#include <stdlib.h>

int rc_init(RcState* state) {
    if (!state) return -1;
    /* tau 默认 1.0，u 和 y 初始为 0 */
    state->tau = 1.0;
    state->u   = 0.0;
    state->y   = 0.0;
    return 0;
}

int rc_step(RcState* state, double t, double dt) {
    (void)t;  /* 自治系统，不显式依赖 t */
    if (!state) return -1;
    if (dt <= 0.0) return 0;

    /* 欧拉前向: y += dt * (u - y) / tau */
    double dydt = (state->u - state->y) / state->tau;
    state->y += dt * dydt;
    return 0;
}

void rc_terminate(RcState* state) {
    (void)state;
    /* 无动态分配，无需释放 */
}
