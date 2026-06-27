/* ============================================================
 * fmi2_adapter.c —— 由 fmu-pack 自动生成，勿手动编辑
 * 模型:     MyModel
 * 状态类型: ModelState
 * 回调前缀: model
 *
 * 改 fmu.yaml 后运行 fmu-pack build 重新生成此文件
 * ============================================================ */

#include "fmi2Functions.h"
#include "fmi2_router.h"
#include "user_model.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---- 适配层内部状态机 ---- */
typedef enum {
    STATE_INSTANTIATED,
    STATE_INIT_MODE,
    STATE_STEP_MODE,
    STATE_TERMINATED,
} FmuState;

typedef struct {
    ModelState model;             /* 用户模型状态 */
    FmuState state;                  /* FMI 状态机 */
    fmi2Real t_start;                /* 仿真起始时间 */
    fmi2Real t_current;              /* 当前通信点时间 */
    fmi2String instance_name;        /* 实例名 */
    fmi2CallbackFunctions callbacks; /* importer 回调 */
    fmi2Boolean logging_on;          /* 日志开关 */
} ModelInstance;

/* ---- 日志辅助 ---- */
static void log_msg(ModelInstance* inst, fmi2Status status,
                    const char* category, const char* msg) {
    if (inst && inst->callbacks.logger && inst->logging_on) {
        inst->callbacks.logger(
            inst->callbacks.componentEnvironment,
            inst->instance_name, status, category, msg);
    }
}

/* ================================================================
 * FMI 2.0 公共函数声明（C 链接符号导出）
 * ================================================================ */

FMI2_Export fmi2GetTypesPlatformTYPE fmi2GetTypesPlatform;
FMI2_Export fmi2GetVersionTYPE       fmi2GetVersion;
FMI2_Export fmi2SetDebugLoggingTYPE  fmi2SetDebugLogging;
FMI2_Export fmi2InstantiateTYPE      fmi2Instantiate;
FMI2_Export fmi2FreeInstanceTYPE     fmi2FreeInstance;
FMI2_Export fmi2SetupExperimentTYPE  fmi2SetupExperiment;
FMI2_Export fmi2EnterInitializationModeTYPE fmi2EnterInitializationMode;
FMI2_Export fmi2ExitInitializationModeTYPE  fmi2ExitInitializationMode;
FMI2_Export fmi2TerminateTYPE        fmi2Terminate;
FMI2_Export fmi2ResetTYPE            fmi2Reset;
FMI2_Export fmi2GetRealTYPE          fmi2GetReal;
FMI2_Export fmi2GetIntegerTYPE       fmi2GetInteger;
FMI2_Export fmi2GetBooleanTYPE       fmi2GetBoolean;
FMI2_Export fmi2GetStringTYPE        fmi2GetString;
FMI2_Export fmi2SetRealTYPE          fmi2SetReal;
FMI2_Export fmi2SetIntegerTYPE       fmi2SetInteger;
FMI2_Export fmi2SetBooleanTYPE       fmi2SetBoolean;
FMI2_Export fmi2SetStringTYPE        fmi2SetString;
FMI2_Export fmi2GetFMUstateTYPE            fmi2GetFMUstate;
FMI2_Export fmi2SetFMUstateTYPE            fmi2SetFMUstate;
FMI2_Export fmi2FreeFMUstateTYPE           fmi2FreeFMUstate;
FMI2_Export fmi2SerializedFMUstateSizeTYPE fmi2SerializedFMUstateSize;
FMI2_Export fmi2SerializeFMUstateTYPE      fmi2SerializeFMUstate;
FMI2_Export fmi2DeSerializeFMUstateTYPE    fmi2DeSerializeFMUstate;
FMI2_Export fmi2GetDirectionalDerivativeTYPE fmi2GetDirectionalDerivative;

/* ---- Co-Simulation 函数声明 ---- */
FMI2_Export fmi2SetRealInputDerivativesTYPE  fmi2SetRealInputDerivatives;
FMI2_Export fmi2GetRealOutputDerivativesTYPE fmi2GetRealOutputDerivatives;
FMI2_Export fmi2DoStepTYPE     fmi2DoStep;
FMI2_Export fmi2CancelStepTYPE fmi2CancelStep;
FMI2_Export fmi2GetStatusTYPE        fmi2GetStatus;
FMI2_Export fmi2GetRealStatusTYPE    fmi2GetRealStatus;
FMI2_Export fmi2GetIntegerStatusTYPE fmi2GetIntegerStatus;
FMI2_Export fmi2GetBooleanStatusTYPE fmi2GetBooleanStatus;
FMI2_Export fmi2GetStringStatusTYPE  fmi2GetStringStatus;

/* ================================================================
 * 实现
 * ================================================================ */

const char* fmi2GetTypesPlatform(void) {
    return fmi2TypesPlatform;
}

const char* fmi2GetVersion(void) {
    return fmi2Version;
}

fmi2Status fmi2SetDebugLogging(fmi2Component c, fmi2Boolean loggingOn,
                                size_t nCategories, const fmi2String categories[]) {
    ModelInstance* inst = (ModelInstance*)c;
    if (!inst) return fmi2Error;
    inst->logging_on = loggingOn;
    (void)nCategories;
    (void)categories;
    return fmi2OK;
}

fmi2Component fmi2Instantiate(fmi2String instanceName, fmi2Type fmuType,
                               fmi2String fmuGUID, fmi2String fmuResourceLocation,
                               const fmi2CallbackFunctions* functions,
                               fmi2Boolean visible, fmi2Boolean loggingOn) {
    (void)fmuGUID;
    (void)fmuResourceLocation;
    (void)visible;

    if (fmuType != fmi2CoSimulation) {
        if (functions && functions->logger) {
            functions->logger(functions->componentEnvironment,
                              instanceName, fmi2Error, "logStatusError",
                              "仅支持 Co-Simulation 模式");
        }
        return NULL;
    }

    ModelInstance* inst = (ModelInstance*)calloc(1, sizeof(ModelInstance));
    if (!inst) return NULL;

    inst->instance_name = instanceName;
    inst->state = STATE_INSTANTIATED;
    inst->logging_on = loggingOn;

    if (functions) {
        inst->callbacks = *functions;
    }

    /* 调用用户模型 init 回调 */
    if (model_init(&inst->model) != 0) {
        log_msg(inst, fmi2Error, "logStatusError",
                "fmi2Instantiate: 模型初始化失败");
        free(inst);
        return NULL;
    }

    log_msg(inst, fmi2OK, "logStatusOK", "fmi2Instantiate: FMU 已实例化");
    return (fmi2Component)inst;
}

void fmi2FreeInstance(fmi2Component c) {
    ModelInstance* inst = (ModelInstance*)c;
    if (!inst) return;
    model_terminate(&inst->model);
    free(inst);
}

fmi2Status fmi2SetupExperiment(fmi2Component c, fmi2Boolean toleranceDefined,
                                fmi2Real tolerance, fmi2Real startTime,
                                fmi2Boolean stopTimeDefined, fmi2Real stopTime) {
    ModelInstance* inst = (ModelInstance*)c;
    if (!inst) return fmi2Error;
    if (inst->state != STATE_INSTANTIATED) {
        log_msg(inst, fmi2Error, "logStatusError",
                "fmi2SetupExperiment: 状态错误");
        return fmi2Error;
    }
    inst->t_start = startTime;
    inst->t_current = startTime;
    (void)toleranceDefined;
    (void)tolerance;
    (void)stopTimeDefined;
    (void)stopTime;
    return fmi2OK;
}

fmi2Status fmi2EnterInitializationMode(fmi2Component c) {
    ModelInstance* inst = (ModelInstance*)c;
    if (!inst) return fmi2Error;
    if (inst->state != STATE_INSTANTIATED) return fmi2Error;
    inst->state = STATE_INIT_MODE;
    return fmi2OK;
}

fmi2Status fmi2ExitInitializationMode(fmi2Component c) {
    ModelInstance* inst = (ModelInstance*)c;
    if (!inst) return fmi2Error;
    if (inst->state != STATE_INIT_MODE) return fmi2Error;
    inst->state = STATE_STEP_MODE;
    return fmi2OK;
}

fmi2Status fmi2Terminate(fmi2Component c) {
    ModelInstance* inst = (ModelInstance*)c;
    if (!inst) return fmi2Error;
    inst->state = STATE_TERMINATED;
    return fmi2OK;
}

fmi2Status fmi2Reset(fmi2Component c) {
    ModelInstance* inst = (ModelInstance*)c;
    if (!inst) return fmi2Error;
    /* 重置模型到初始状态 */
    model_terminate(&inst->model);
    model_init(&inst->model);
    inst->state = STATE_INSTANTIATED;
    inst->t_current = inst->t_start;
    return fmi2OK;
}

/* ---- get/set Real: 通过路由表分发 ---- */

fmi2Status fmi2GetReal(fmi2Component c, const fmi2ValueReference vr[],
                        size_t nvr, fmi2Real value[]) {
    ModelInstance* inst = (ModelInstance*)c;
    if (!inst) return fmi2Error;
    if (inst->state == STATE_TERMINATED) return fmi2Error;
    MyModel_route_getReal(&inst->model, vr, nvr, value);
    return fmi2OK;
}

fmi2Status fmi2SetReal(fmi2Component c, const fmi2ValueReference vr[],
                        size_t nvr, const fmi2Real value[]) {
    ModelInstance* inst = (ModelInstance*)c;
    if (!inst) return fmi2Error;
    if (inst->state == STATE_TERMINATED) return fmi2Error;
    MyModel_route_setReal(&inst->model, vr, nvr, value);
    return fmi2OK;
}

/* ---- 未实现的 get/set (返回 fmi2Error) ---- */

fmi2Status fmi2GetInteger(fmi2Component c, const fmi2ValueReference vr[],
                           size_t nvr, fmi2Integer value[]) {
    (void)c; (void)vr; (void)nvr; (void)value;
    return fmi2Error;
}

fmi2Status fmi2GetBoolean(fmi2Component c, const fmi2ValueReference vr[],
                           size_t nvr, fmi2Boolean value[]) {
    (void)c; (void)vr; (void)nvr; (void)value;
    return fmi2Error;
}

fmi2Status fmi2GetString(fmi2Component c, const fmi2ValueReference vr[],
                          size_t nvr, fmi2String value[]) {
    (void)c; (void)vr; (void)nvr; (void)value;
    return fmi2Error;
}

fmi2Status fmi2SetInteger(fmi2Component c, const fmi2ValueReference vr[],
                           size_t nvr, const fmi2Integer value[]) {
    (void)c; (void)vr; (void)nvr; (void)value;
    return fmi2Error;
}

fmi2Status fmi2SetBoolean(fmi2Component c, const fmi2ValueReference vr[],
                           size_t nvr, const fmi2Boolean value[]) {
    (void)c; (void)vr; (void)nvr; (void)value;
    return fmi2Error;
}

fmi2Status fmi2SetString(fmi2Component c, const fmi2ValueReference vr[],
                          size_t nvr, const fmi2String value[]) {
    (void)c; (void)vr; (void)nvr; (void)value;
    return fmi2Error;
}

/* ---- FMU state: 未实现 ---- */

fmi2Status fmi2GetFMUstate(fmi2Component c, fmi2FMUstate* FMUstate) {
    (void)c; (void)FMUstate;
    return fmi2Error;
}

fmi2Status fmi2SetFMUstate(fmi2Component c, fmi2FMUstate FMUstate) {
    (void)c; (void)FMUstate;
    return fmi2Error;
}

fmi2Status fmi2FreeFMUstate(fmi2Component c, fmi2FMUstate* FMUstate) {
    (void)c; (void)FMUstate;
    return fmi2Error;
}

fmi2Status fmi2SerializedFMUstateSize(fmi2Component c, fmi2FMUstate FMUstate,
                                       size_t* size) {
    (void)c; (void)FMUstate; (void)size;
    return fmi2Error;
}

fmi2Status fmi2SerializeFMUstate(fmi2Component c, fmi2FMUstate FMUstate,
                                  fmi2Byte serializedState[], size_t size) {
    (void)c; (void)FMUstate; (void)serializedState; (void)size;
    return fmi2Error;
}

fmi2Status fmi2DeSerializeFMUstate(fmi2Component c,
                                    const fmi2Byte serializedState[],
                                    size_t size, fmi2FMUstate* FMUstate) {
    (void)c; (void)serializedState; (void)size; (void)FMUstate;
    return fmi2Error;
}

fmi2Status fmi2GetDirectionalDerivative(fmi2Component c,
                                         const fmi2ValueReference vUnknown_ref[],
                                         size_t nUnknown,
                                         const fmi2ValueReference vKnown_ref[],
                                         size_t nKnown,
                                         const fmi2Real dvKnown[],
                                         fmi2Real dvUnknown[]) {
    (void)c;
    (void)vUnknown_ref; (void)nUnknown;
    (void)vKnown_ref; (void)nKnown;
    (void)dvKnown; (void)dvUnknown;
    return fmi2Error;
}

/* ---- Co-Simulation ---- */

fmi2Status fmi2SetRealInputDerivatives(fmi2Component c,
                                        const fmi2ValueReference vr[],
                                        size_t nvr,
                                        const fmi2Integer order[],
                                        const fmi2Real value[]) {
    (void)c; (void)vr; (void)nvr; (void)order; (void)value;
    return fmi2Error;
}

fmi2Status fmi2GetRealOutputDerivatives(fmi2Component c,
                                         const fmi2ValueReference vr[],
                                         size_t nvr,
                                         const fmi2Integer order[],
                                         fmi2Real value[]) {
    (void)c; (void)vr; (void)nvr; (void)order; (void)value;
    return fmi2Error;
}

fmi2Status fmi2DoStep(fmi2Component c,
                       fmi2Real currentCommunicationPoint,
                       fmi2Real communicationStepSize,
                       fmi2Boolean noSetFMUStatePriorToCurrentPoint) {
    ModelInstance* inst = (ModelInstance*)c;
    if (!inst) return fmi2Error;
    if (inst->state != STATE_STEP_MODE) {
        log_msg(inst, fmi2Error, "logStatusError",
                "fmi2DoStep: 状态错误，需在 stepMode 状态调用");
        return fmi2Error;
    }
    (void)noSetFMUStatePriorToCurrentPoint;

    /* 调用用户模型 step 回调 */
    int ret = model_step(&inst->model, currentCommunicationPoint, communicationStepSize);
    if (ret != 0) {
        log_msg(inst, fmi2Error, "logStatusError",
                "fmi2DoStep: 模型 step 返回错误");
        return fmi2Error;
    }

    inst->t_current = currentCommunicationPoint + communicationStepSize;

    if (inst->callbacks.stepFinished) {
        inst->callbacks.stepFinished(
            inst->callbacks.componentEnvironment, fmi2OK);
    }
    return fmi2OK;
}

fmi2Status fmi2CancelStep(fmi2Component c) {
    (void)c;
    return fmi2OK;
}

/* ---- 状态查询 ---- */

fmi2Status fmi2GetStatus(fmi2Component c, const fmi2StatusKind s,
                          fmi2Status* value) {
    ModelInstance* inst = (ModelInstance*)c;
    if (!inst || !value) return fmi2Error;
    switch (s) {
    case fmi2DoStepStatus:
        *value = (inst->state == STATE_STEP_MODE) ? fmi2OK : fmi2Error;
        break;
    case fmi2PendingStatus:
        *value = fmi2OK;
        break;
    case fmi2Terminated:
        *value = (inst->state == STATE_TERMINATED) ? fmi2True : fmi2False;
        break;
    default:
        *value = fmi2Error;
        break;
    }
    return fmi2OK;
}

fmi2Status fmi2GetRealStatus(fmi2Component c, const fmi2StatusKind s,
                              fmi2Real* value) {
    ModelInstance* inst = (ModelInstance*)c;
    if (!inst || !value) return fmi2Error;
    if (s == fmi2LastSuccessfulTime) {
        *value = inst->t_current;
        return fmi2OK;
    }
    *value = 0.0;
    return fmi2Error;
}

fmi2Status fmi2GetIntegerStatus(fmi2Component c, const fmi2StatusKind s,
                                 fmi2Integer* value) {
    (void)c; (void)s; (void)value;
    return fmi2Error;
}

fmi2Status fmi2GetBooleanStatus(fmi2Component c, const fmi2StatusKind s,
                                 fmi2Boolean* value) {
    (void)c; (void)s; (void)value;
    return fmi2Error;
}

fmi2Status fmi2GetStringStatus(fmi2Component c, const fmi2StatusKind s,
                                fmi2String* value) {
    (void)c; (void)s; (void)value;
    return fmi2Error;
}