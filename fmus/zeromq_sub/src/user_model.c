/**
 * user_model.c —— ZeroMQ 订阅 FMU 实现
 *
 * 功能:
 *   1. 初始化时创建 ZMQ SUB socket，连接到外部 PUB 端点
 *   2. 每个 doStep 中非阻塞轮询 ZMQ，接收数据
 *   3. 输出 = 接收值 * gain
 *
 * ZMQ 端点配置（可修改）:
 *   ZMQ_ENDPOINT: 发布端地址，默认 "tcp://localhost:5555"
 *   ZMQ_TOPIC:    订阅主题，默认 ""（接收所有消息）
 *
 * 状态结构体 ZmqSubState 定义在 user_model.h
 */

#include "user_model.h"

/* 静态链接 ZeroMQ 时需定义此宏，避免 __imp_ 前缀 */
#define ZMQ_STATIC
#include <zmq.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* ---- ZMQ 配置 ---- */
#define ZMQ_ENDPOINT "tcp://localhost:5555"
#define ZMQ_TOPIC ""

void* model_init(void) {
    ZmqSubState* s = (ZmqSubState*)malloc(sizeof(ZmqSubState));
    if (!s) return NULL;
    s->gain = 1.0;
    s->y = 0.0;
    s->raw_value = 0.0;
    s->has_new_data = 0;
    s->zmq_ctx = NULL;
    s->zmq_sock = NULL;

    /* 创建 ZMQ context */
    s->zmq_ctx = zmq_ctx_new();
    if (!s->zmq_ctx) {
        fprintf(stderr, "[zmqsub] zmq_ctx_new 失败\n");
        free(s);
        return NULL;
    }

    /* 创建 SUB socket */
    s->zmq_sock = zmq_socket(s->zmq_ctx, ZMQ_SUB);
    if (!s->zmq_sock) {
        fprintf(stderr, "[zmqsub] zmq_socket 失败\n");
        zmq_ctx_destroy(s->zmq_ctx);
        free(s);
        return NULL;
    }

    /* 设置订阅主题 */
    int rc = zmq_setsockopt(s->zmq_sock, ZMQ_SUBSCRIBE, ZMQ_TOPIC, strlen(ZMQ_TOPIC));
    if (rc != 0) {
        fprintf(stderr, "[zmqsub] zmq_setsockopt SUBSCRIBE 失败\n");
        zmq_close(s->zmq_sock);
        zmq_ctx_destroy(s->zmq_ctx);
        free(s);
        return NULL;
    }

    /* 连接到发布端 */
    rc = zmq_connect(s->zmq_sock, ZMQ_ENDPOINT);
    if (rc != 0) {
        fprintf(stderr, "[zmqsub] zmq_connect(%s) 失败: %s\n",
                ZMQ_ENDPOINT, zmq_strerror(zmq_errno()));
        zmq_close(s->zmq_sock);
        zmq_ctx_destroy(s->zmq_ctx);
        free(s);
        return NULL;
    }

    printf("[zmqsub] 已连接到 %s，订阅主题 '%s'\n", ZMQ_ENDPOINT, ZMQ_TOPIC);
    return s;
}

int model_step(void* state, double t, double dt) {
    (void)t;
    (void)dt;
    if (!state) return -1;
    ZmqSubState* s = (ZmqSubState*)state;

    s->has_new_data = 0;

    /* 非阻塞轮询 ZMQ socket */
    zmq_pollitem_t items[] = { { s->zmq_sock, 0, ZMQ_POLLIN, 0 } };
    int rc = zmq_poll(items, 1, 0);
    if (rc < 0) {
        fprintf(stderr, "[zmqsub] zmq_poll 错误\n");
        return -1;
    }

    if (items[0].revents & ZMQ_POLLIN) {
        char buf[256];
        int n = zmq_recv(s->zmq_sock, buf, sizeof(buf) - 1, 0);
        if (n > 0) {
            buf[n] = '\0';
            char* endptr = NULL;
            double val = strtod(buf, &endptr);
            if (endptr != buf) {
                s->raw_value = val;
                s->has_new_data = 1;
            }
        }
    }

    s->y = s->raw_value * s->gain;
    return 0;
}

void model_terminate(void* state) {
    if (!state) return;
    ZmqSubState* s = (ZmqSubState*)state;
    if (s->zmq_sock) {
        zmq_close(s->zmq_sock);
        s->zmq_sock = NULL;
    }
    if (s->zmq_ctx) {
        zmq_ctx_destroy(s->zmq_ctx);
        s->zmq_ctx = NULL;
    }
    free(s);
}
