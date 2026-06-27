/* ============================================================
 * user_model.h —— RC 低通滤波器用户模型接口
 *
 * 三个回调（统一前缀 model_*，状态用 void*）:
 *   void* model_init(void);
 *   int   model_step(void* state, double t, double dt);
 *   void  model_terminate(void* state);
 *
 * 状态结构体名 {state_type} = RcState
 * router (fmi2_router.h) cast void* 到 RcState*
 * ============================================================ */

#ifndef USER_MODEL_H_
#define USER_MODEL_H_

/* ---- 状态结构体 ---- */
typedef struct {
    double tau;  /* 时间常数，parameter */
    double u;    /* 输入信号 */
    double y;    /* 输出信号 */
} RcState;

/* ---- 三个回调 ---- */
void* model_init(void);
int   model_step(void* state, double t, double dt);
void  model_terminate(void* state);

#endif /* USER_MODEL_H_ */
