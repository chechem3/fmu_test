/* ============================================================
 * user_model.h —— 用户模型接口
 *
 * 三个回调约定（必须实现）:
 *   int  model_init(ModelState* state);
 *   int  model_step(ModelState* state, double t, double dt);
 *   void model_terminate(ModelState* state);
 * ============================================================ */

#ifndef USER_MODEL_H_
#define USER_MODEL_H_

/* ---- 状态结构体: 用户填充 ---- */
typedef struct {
    /* TODO: 在此声明你的模型状态字段 */
    /* 示例:
     * double tau;
     * double u, y;
     */
} ModelState;

/* ---- 三个回调（用户实现） ---- */
int  model_init(ModelState* state);
int  model_step(ModelState* state, double t, double dt);
void model_terminate(ModelState* state);

#endif /* USER_MODEL_H_ */
