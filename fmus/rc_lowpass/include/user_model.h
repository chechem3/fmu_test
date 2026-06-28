/* ============================================================
 * user_model.h —— RC 低通滤波器
 *
 * 数学模型: dy/dt = (u - y) / tau
 *           y(0) = 0
 * 离散化:   y_{k+1} = y_k + dt * (u_k - y_k) / tau
 * ============================================================ */

#ifndef USER_MODEL_H_
#define USER_MODEL_H_

/* 内部定步长（10ms） */
#define MODEL_STEP_SIZE 0.01

/* ---- 3 个固定结构体（causality 分组）---- */
typedef struct {
    double tau;   /* parameter: 时间常数 */
} UserModelParameterT;

typedef struct {
    double u;     /* input: 输入信号 */
} UserModelInputT;

typedef struct {
    double y;     /* output: 滤波后输出 */
} UserModelOutputT;

/* ---- 3 个回调 ---- */
int  model_init(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out);
int  model_step(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out,
                double t, double dt);
void model_terminate(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out);

#endif /* USER_MODEL_H_ */
