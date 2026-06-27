#ifndef FMI2_ROUTER_H_
#define FMI2_ROUTER_H_

/* ============================================================
 * fmi2_router.h —— VR 路由表（由 fmu-pack 自动生成，勿手动编辑）
 * 状态类型: ZmqSubState
 * 变量数:   4
 * ============================================================ */

#include "fmi2TypesPlatform.h"
#include "user_model.h"

/* ---- valueReference 枚举 ---- */
typedef enum {
    VR_GAIN = 1,  /* parameter */
    VR_Y = 2,  /* output */
    VR_RAW_VALUE = 3,  /* local */
    VR_HAS_NEW_DATA = 4,  /* output */
    VR_COUNT = 4
} ModelVR;


/* ---- getReal 路由（内联函数，固定名 model_route_getReal）---- */
static inline void model_route_getReal(void* state,
                                       const fmi2ValueReference vr[],
                                       size_t nvr,
                                       fmi2Real value[]) {
    ZmqSubState* s = (ZmqSubState*)state;
    for (size_t i = 0; i < nvr; i++) {
        switch (vr[i]) {
        case VR_GAIN: value[i] = s->gain; break;
        case VR_Y: value[i] = s->y; break;
        case VR_RAW_VALUE: value[i] = s->raw_value; break;
        case VR_HAS_NEW_DATA: value[i] = s->has_new_data; break;
            default: break;
        }
    }
}

/* ---- setReal 路由（内联函数，固定名 model_route_setReal）---- */
static inline void model_route_setReal(void* state,
                                       const fmi2ValueReference vr[],
                                       size_t nvr,
                                       const fmi2Real value[]) {
    ZmqSubState* s = (ZmqSubState*)state;
    for (size_t i = 0; i < nvr; i++) {
        switch (vr[i]) {
        case VR_GAIN: s->gain = value[i]; break;
            default: break;
        }
    }
}

#endif /* FMI2_ROUTER_H_ */