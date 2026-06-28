/* ============================================================
 * user_model.c —— zeromq_io 实现
 *
 * 4 通道 ZMQ 数据桥：每步 SUB 收最新 JSON → +1 → PUB 发 JSON
 * ============================================================ */

#include "user_model.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "zmq.h"
#include "cJSON.h"

#ifdef _WIN32
#include <windows.h>
#define ZMQ_SLEEP_MS(ms) Sleep(ms)
#else
#include <unistd.h>
#define ZMQ_SLEEP_MS(ms) usleep((ms) * 1000)
#endif

/* ---- 模块级 ZMQ 资源（adapter 只传 3 个 struct 指针，无法放 zmq handle）---- */
static void* g_ctx  = NULL;
static void* g_sub  = NULL;
static void* g_pub  = NULL;
static int   g_sockets_ready = 0;  /* 标记：是否已按当前 endpoint 建好 socket */

/* ---- 内部工具 ---- */

/* 收 SUB 队列（不阻塞，drain 到空）；无消息返回 NULL */
static char* recv_latest_json(void* sub) {
    char* latest = NULL;
    while (1) {
        zmq_msg_t msg;
        zmq_msg_init(&msg);
        int rc = zmq_msg_recv(&msg, sub, ZMQ_DONTWAIT);
        if (rc < 0) {
            zmq_msg_close(&msg);
            break;  /* EAGAIN：队列已空 */
        }
        free(latest);  /* 释放上一帧 */
        size_t len = zmq_msg_size(&msg);
        latest = (char*)malloc(len + 1);
        if (!latest) {
            zmq_msg_close(&msg);
            return NULL;
        }
        memcpy(latest, zmq_msg_data(&msg), len);
        latest[len] = '\0';
        zmq_msg_close(&msg);
    }
    return latest;
}

/* 解析 {"x":[v0,v1,v2,v3]} → in->x0..x3
   成功返回 0；格式错返回 -1 */
static int parse_input(const char* json_str, UserModelInputT* in) {
    cJSON* root = cJSON_Parse(json_str);
    if (!root) return -1;
    cJSON* x_arr = cJSON_GetObjectItemCaseSensitive(root, "x");
    if (!cJSON_IsArray(x_arr) || cJSON_GetArraySize(x_arr) != N_CHANNELS) {
        cJSON_Delete(root);
        return -1;
    }
    in->x0 = cJSON_GetArrayItem(x_arr, 0)->valuedouble;
    in->x1 = cJSON_GetArrayItem(x_arr, 1)->valuedouble;
    in->x2 = cJSON_GetArrayItem(x_arr, 2)->valuedouble;
    in->x3 = cJSON_GetArrayItem(x_arr, 3)->valuedouble;
    cJSON_Delete(root);
    return 0;
}

/* 生成 {"y":[v0+1,v1+1,v2+1,v3+1]} → 返回 malloc 的字符串，调用方 free */
static char* make_output(const UserModelOutputT* out) {
    cJSON* root  = cJSON_CreateObject();
    cJSON* y_arr = cJSON_AddArrayToObject(root, "y");
    cJSON_AddItemToArray(y_arr, cJSON_CreateNumber(out->y0));
    cJSON_AddItemToArray(y_arr, cJSON_CreateNumber(out->y1));
    cJSON_AddItemToArray(y_arr, cJSON_CreateNumber(out->y2));
    cJSON_AddItemToArray(y_arr, cJSON_CreateNumber(out->y3));
    char* s = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    return s;
}

/* 设置 int socket 选项；失败返回 -1 */
static int set_int_opt(void* sock, int opt, int val) {
    return zmq_setsockopt(sock, opt, &val, sizeof(val));
}

/* ---- 三个回调 ---- */

int model_init(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out) {
    /* 默认端点（仅当参数未设置时使用） */
    if (p->sub_endpoint[0] == '\0') {
        strncpy(p->sub_endpoint, "DEFAULT_NOT_SET", sizeof(p->sub_endpoint) - 1);
    }
    if (p->pub_endpoint[0] == '\0') {
        strncpy(p->pub_endpoint, "DEFAULT_NOT_SET", sizeof(p->pub_endpoint) - 1);
    }
    /* 输入/输出初始值 */
    in->x0 = in->x1 = in->x2 = in->x3 = 0.0;
    out->y0 = out->y1 = out->y2 = out->y3 = 0.0;

    /* ZMQ socket 不在此创建，留到首次 model_step 时按当前 endpoint 建。
       这样 FMPy 可以在 fmi2EnterInitializationMode 阶段通过 setString 注入 endpoint。*/
    return 0;
}

int model_step(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out,
               double t, double dt) {
    (void)t; (void)dt;

    /* 懒初始化 ZMQ socket（首次 step 时按当前 endpoint 建） */
    if (!g_sockets_ready) {
        g_ctx = zmq_ctx_new();
        if (!g_ctx) return -1;
        g_sub = zmq_socket(g_ctx, ZMQ_SUB);
        g_pub = zmq_socket(g_ctx, ZMQ_PUB);
        if (!g_sub || !g_pub) return -2;
        if (set_int_opt(g_sub, ZMQ_RCVTIMEO, 0) != 0) return -3;
        if (set_int_opt(g_pub, ZMQ_SNDTIMEO, 0) != 0) return -3;
        if (set_int_opt(g_sub, ZMQ_LINGER,  0) != 0) return -3;
        if (set_int_opt(g_pub, ZMQ_LINGER,  0) != 0) return -3;
        if (set_int_opt(g_sub, ZMQ_CONFLATE, 1) != 0) return -3;
        if (zmq_setsockopt(g_sub, ZMQ_SUBSCRIBE, "", 0) != 0) return -3;
        if (zmq_connect(g_sub, p->sub_endpoint) != 0) return -4;
        if (zmq_bind(g_pub, p->pub_endpoint) != 0) return -5;
        g_sockets_ready = 1;
        /* ZMQ bind 是 lazy 的：zmq_bind() 返回后内部 I/O 线程还没启动并注册 socket。
           不 sleep 一下立即 recv/send 会全部 EAGAIN。先等 500ms 确保 socket 在 OS 层 LISTENING。*/
        ZMQ_SLEEP_MS(500);
    }

    /* 1. 收最新一帧 JSON（非阻塞 drain） */
    char* json = recv_latest_json(g_sub);
    if (json) {
        if (parse_input(json, in) != 0) {
            free(json);
            return -1;
        }
        free(json);
    }

    /* 2. 计算 y[i] = x[i] + 1 */
    out->y0 = in->x0 + 1.0;
    out->y1 = in->x1 + 1.0;
    out->y2 = in->x2 + 1.0;
    out->y3 = in->x3 + 1.0;

    /* 3. PUB 发 JSON */
    char* out_json = make_output(out);
    if (!out_json) return -2;

    zmq_msg_t msg;
    zmq_msg_init_size(&msg, strlen(out_json));
    memcpy(zmq_msg_data(&msg), out_json, strlen(out_json));
    int rc = zmq_msg_send(&msg, g_pub, ZMQ_DONTWAIT);
    zmq_msg_close(&msg);
    free(out_json);

    return (rc < 0) ? -3 : 0;
}

void model_terminate(UserModelParameterT* p, UserModelInputT* in, UserModelOutputT* out) {
    (void)p; (void)in; (void)out;
    /* 顺序：close socket → term ctx */
    if (g_sub) { zmq_close(g_sub); g_sub = NULL; }
    if (g_pub) { zmq_close(g_pub); g_pub = NULL; }
    if (g_ctx) { zmq_ctx_term(g_ctx); g_ctx = NULL; }  /* 会阻塞直到 socket 全关 */
    g_sockets_ready = 0;
}