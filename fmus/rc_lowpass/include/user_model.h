/* ============================================================
 * user_model.h —— 用户模型接口
 *
 * 三个固定结构体（causality 分组，工具按字段声明顺序分配 VR）:
 *   UserModelParameterT —— 可读可写 (causality=parameter)
 *   UserModelInputT     —— 可读可写 (causality=input)
 *   UserModelOutputT    —— 只读     (causality=output)
 *
 * 三个回调（用户实现）:
 *   int  model_init(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out);
 *   int  model_step(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out,
 *                   double t, double dt);
 *   void model_terminate(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out);
 *
 * model_step 的 dt 由 importer 透传；FMU 不在内部切分
 * ============================================================ */

#ifndef USER_MODEL_H_
#define USER_MODEL_H_

/* ---- 三个固定结构体（用户填充字段）---- */
typedef struct {
    double tau;   /* 时间常数（秒） */
} UserModelParameterT;

typedef struct {
    double u;     /* 输入信号 */
} UserModelInputT;

typedef struct {
    double y;     /* 滤波后输出 */
} UserModelOutputT;

/* ---- 三个回调（用户实现，见 user_model.c）---- */
int  model_init(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out);
int  model_step(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out,
                double t, double dt);
void model_terminate(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out);

#endif /* USER_MODEL_H_ */
