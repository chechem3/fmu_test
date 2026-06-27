/* ============================================================
 * user_model.c —— 用户模型实现
 * 由 fmu-pack init 生成骨架，用户填充
 * ============================================================ */

#include "user_model.h"

int model_init(ModelState* state) {
    if (!state) return -1;
    /* TODO: 初始化状态字段 */
    return 0;
}

int model_step(ModelState* state, double t, double dt) {
    (void)t;
    (void)dt;
    if (!state) return -1;
    /* TODO: 单步推进逻辑 */
    return 0;
}

void model_terminate(ModelState* state) {
    if (!state) return;
    /* TODO: 释放资源（无动态分配可留空） */
}
