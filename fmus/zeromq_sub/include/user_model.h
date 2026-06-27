/* ============================================================
 * user_model.h —— ZeroMQ 订阅 FMU 用户模型接口
 *
 * 三个回调（统一前缀 model_*，状态用 void*）:
 *   void* model_init(void);
 *   int   model_step(void* state, double t, double dt);
 *   void  model_terminate(void* state);
 *
 * 状态结构体名 {state_type} = ZmqSubState
 * router (fmi2_router.h) cast void* 到 ZmqSubState*
 * ============================================================ */

#ifndef USER_MODEL_H_
#define USER_MODEL_H_

/* ---- 状态结构体 ---- */
typedef struct {
    double gain;        /* 输出增益，parameter */
    double y;           /* 输出 = raw_value * gain */
    double raw_value;   /* 从 ZMQ 接收的原始值 */
    int has_new_data;   /* 上一步是否有新数据 */

    void* zmq_ctx;      /* ZMQ context (opaque) */
    void* zmq_sock;     /* ZMQ SUB socket (opaque) */
} ZmqSubState;

/* ---- 三个回调 ---- */
void* model_init(void);
int   model_step(void* state, double t, double dt);
void  model_terminate(void* state);

#endif /* USER_MODEL_H_ */
