#ifndef FMI2_ROUTER_H_
#define FMI2_ROUTER_H_

/* ============================================================
 * fmi2_router.h —— VR 路由表（由 fmu-pack 自动生成，勿手动编辑）
 * 状态类型: RcState
 * 变量数:   3
 * ============================================================ */

#include "fmi2TypesPlatform.h"
#include "user_model.h"

/* ---- valueReference 枚举 ---- */
typedef enum {
    VR_TAU = 1,  /* parameter */
    VR_U = 2,  /* input */
    VR_Y = 3,  /* output */
    VR_COUNT = 3
} ModelVR;


/* ---- getReal 路由（内联函数，固定名 model_route_getReal）---- */
static inline void model_route_getReal(void* state,
                                       const fmi2ValueReference vr[],
                                       size_t nvr,
                                       fmi2Real value[]) {
    RcState* s = (RcState*)state;
    for (size_t i = 0; i < nvr; i++) {
        switch (vr[i]) {
        case VR_TAU: value[i] = s->tau; break;
        case VR_U: value[i] = s->u; break;
        case VR_Y: value[i] = s->y; break;
            default: break;
        }
    }
}

/* ---- setReal 路由（内联函数，固定名 model_route_setReal）---- */
static inline void model_route_setReal(void* state,
                                       const fmi2ValueReference vr[],
                                       size_t nvr,
                                       const fmi2Real value[]) {
    RcState* s = (RcState*)state;
    for (size_t i = 0; i < nvr; i++) {
        switch (vr[i]) {
        case VR_TAU: s->tau = value[i]; break;
        case VR_U: s->u = value[i]; break;
            default: break;
        }
    }
}

#endif /* FMI2_ROUTER_H_ */