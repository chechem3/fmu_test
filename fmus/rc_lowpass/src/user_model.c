/* ============================================================
 * user_model.c —— RC 低通滤波器实现
 *
 * 欧拉法: y_{k+1} = y_k + dt * (u_k - y_k) / tau
 * ============================================================ */

#include "user_model.h"

int model_init(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out) {
    p->tau = 1.0;   /* 默认 1 秒时间常数 */
    in->u  = 0.0;
    out->y = 0.0;
    return 0;
}

int model_step(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out,
               double t, double dt) {
    (void)t;
    if (dt <= 0.0) return 0;
    if (p->tau <= 0.0) return -1;  /* 避免除零 */
    /* 欧拉前向: y += dt * (u - y) / tau */
    out->y += dt * (in->u - out->y) / p->tau;
    return 0;
}

void model_terminate(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out) {
    (void)p; (void)in; (void)out;
    /* 无动态分配，无需释放 */
}
