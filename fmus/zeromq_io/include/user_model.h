/* ============================================================
 * user_model.h —— zeromq_io 用户模型接口
 *
 * 三个固定结构体（causality 分组，工具按字段声明顺序分配 VR）:
 *   UserModelParameterT —— 可读可写 (causality=parameter)
 *   UserModelInputT     —— 可读可写 (causality=input)
 *   UserModelOutputT    —— 只读     (causality=output)
 *
 * model_step 的 dt 由 importer 透传；FMU 不在内部切分
 * ============================================================ */

#ifndef USER_MODEL_H_
#define USER_MODEL_H_

/* ---- 通道数（编译期常量）---- */
#define N_CHANNELS 4

/* ---- 三个固定结构体 ---- */

/* ZMQ 端点配置（FMI String，即 char[]，按 cJSON 约定留 64 字节） */
typedef struct {
    char sub_endpoint[64];   /* SUB 连接的对端，默认 "tcp://localhost:5556" */
    char pub_endpoint[64];   /* PUB 绑定的本端，默认 "tcp://*:5555" */
} UserModelParameterT;

/* 4 通道输入：JSON {"x":[v0,v1,v2,v3]} */
typedef struct {
    double x0;
    double x1;
    double x2;
    double x3;
} UserModelInputT;

/* 4 通道输出：JSON {"y":[v0+1,v1+1,v2+1,v3+1]} */
typedef struct {
    double y0;
    double y1;
    double y2;
    double y3;
} UserModelOutputT;

/* ---- 三个回调（用户实现，见 user_model.c）---- */
int  model_init(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out);
int  model_step(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out,
                double t, double dt);
void model_terminate(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out);

#endif /* USER_MODEL_H_ */