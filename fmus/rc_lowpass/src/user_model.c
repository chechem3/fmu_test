/**
 * user_model.c —— RC 低通滤波器实现
 *
 * 数学模型:
 *   dy/dt = (u - y) / tau
 *   y(0) = 0
 *
 * 离散化（欧拉法）:
 *   y_{k+1} = y_k + dt * (u_k - y_k) / tau
 *
 * 状态结构体 RcState 定义在 user_model.h
 * 路由层 (fmi2_router.h) cast void* 到 RcState*
 */

#include "user_model.h"
#include <stdlib.h>

void* model_init(void) {
    RcState* s = (RcState*)malloc(sizeof(RcState));
    if (!s) return NULL;
    s->tau = 1.0;
    s->u   = 0.0;
    s->y   = 0.0;
    return s;
}

int model_step(void* state, double t, double dt) {
    (void)t;  /* 自治系统，不显式依赖 t */
    if (!state) return -1;
    if (dt <= 0.0) return 0;

    RcState* s = (RcState*)state;
    /* 欧拉前向: y += dt * (u - y) / tau */
    double dydt = (s->u - s->y) / s->tau;
    s->y += dt * dydt;
    return 0;
}

void model_terminate(void* state) {
    free(state);
}
