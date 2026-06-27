#ifndef FMI2_ROUTER_H_
#define FMI2_ROUTER_H_

/* ============================================================
 * fmi2_router.h —— VR 路由表（由 fmu-pack 自动生成，勿手动编辑）
 * 模型: zmqsub
 * 变量数: 4
 * 状态类型: ZmqSubState
 * ============================================================ */

#include "fmi2TypesPlatform.h"
#include "user_model.h"

/* ---- valueReference 枚举 ---- */
/* zmqsub 变量 valueReference 枚举 —— 由 fmu-pack 自动生成 */
typedef enum {
    VR_GAIN = 1,  /* parameter */
    VR_Y = 2,  /* output */
    VR_RAW_VALUE = 3,  /* local */
    VR_HAS_NEW_DATA = 4,  /* output */
    VR_COUNT = 4
} zmqsub_VR;


/* ---- getReal 路由（内联函数） ---- */
static inline void zmqsub_route_getReal(ZmqSubState* state,
                                       const fmi2ValueReference vr[],
                                       size_t nvr,
                                       fmi2Real value[]) {
    for (size_t i = 0; i < nvr; i++) {
        switch (vr[i]) {
        case VR_GAIN: value[i] = state->gain; break;
        case VR_Y: value[i] = state->y; break;
        case VR_RAW_VALUE: value[i] = state->raw_value; break;
        case VR_HAS_NEW_DATA: value[i] = state->has_new_data; break;
            default: break;
        }
    }
}

/* ---- setReal 路由（内联函数） ---- */
static inline void zmqsub_route_setReal(ZmqSubState* state,
                                       const fmi2ValueReference vr[],
                                       size_t nvr,
                                       const fmi2Real value[]) {
    for (size_t i = 0; i < nvr; i++) {
        switch (vr[i]) {
        case VR_GAIN: state->gain = value[i]; break;
            default: break;
        }
    }
}

#endif /* FMI2_ROUTER_H_ */
