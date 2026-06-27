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
 */

#include "user_model.h"

/* 静态链接 ZeroMQ 时需定义此宏，避免 __imp_ 前缀 */
#define ZMQ_STATIC
#include <zmq.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* ---- ZMQ 配置 ---- */
/* 发布端地址，可按需修改 */
#define ZMQ_ENDPOINT "tcp://localhost:5555"
/* 订阅主题，空字符串表示接收所有消息 */
#define ZMQ_TOPIC ""

int zmqsub_init(ZmqSubState* state) {
    if (!state) return -1;

    /* 初始化默认值 */
    state->gain = 1.0;
    state->y = 0.0;
    state->raw_value = 0.0;
    state->has_new_data = 0;
    state->zmq_ctx = NULL;
    state->zmq_sock = NULL;

    /* 创建 ZMQ context */
    state->zmq_ctx = zmq_ctx_new();
    if (!state->zmq_ctx) {
        fprintf(stderr, "[zmqsub] zmq_ctx_new 失败\n");
        return -1;
    }

    /* 创建 SUB socket */
    state->zmq_sock = zmq_socket(state->zmq_ctx, ZMQ_SUB);
    if (!state->zmq_sock) {
        fprintf(stderr, "[zmqsub] zmq_socket 失败\n");
        zmq_ctx_destroy(state->zmq_ctx);
        state->zmq_ctx = NULL;
        return -1;
    }

    /* 设置订阅主题 */
    int rc = zmq_setsockopt(state->zmq_sock, ZMQ_SUBSCRIBE, ZMQ_TOPIC, strlen(ZMQ_TOPIC));
    if (rc != 0) {
        fprintf(stderr, "[zmqsub] zmq_setsockopt SUBSCRIBE 失败\n");
        zmq_close(state->zmq_sock);
        zmq_ctx_destroy(state->zmq_ctx);
        state->zmq_sock = NULL;
        state->zmq_ctx = NULL;
        return -1;
    }

    /* 连接到发布端 */
    rc = zmq_connect(state->zmq_sock, ZMQ_ENDPOINT);
    if (rc != 0) {
        fprintf(stderr, "[zmqsub] zmq_connect(%s) 失败: %s\n",
                ZMQ_ENDPOINT, zmq_strerror(zmq_errno()));
        zmq_close(state->zmq_sock);
        zmq_ctx_destroy(state->zmq_ctx);
        state->zmq_sock = NULL;
        state->zmq_ctx = NULL;
        return -1;
    }

    printf("[zmqsub] 已连接到 %s，订阅主题 '%s'\n", ZMQ_ENDPOINT, ZMQ_TOPIC);
    return 0;
}

int zmqsub_step(ZmqSubState* state, double t, double dt) {
    (void)t;
    (void)dt;
    if (!state) return -1;

    state->has_new_data = 0;

    /* 非阻塞轮询 ZMQ socket */
    zmq_pollitem_t items[] = { { state->zmq_sock, 0, ZMQ_POLLIN, 0 } };
    int rc = zmq_poll(items, 1, 0);  /* timeout=0 立即返回 */
    if (rc < 0) {
        fprintf(stderr, "[zmqsub] zmq_poll 错误\n");
        return -1;
    }

    if (items[0].revents & ZMQ_POLLIN) {
        /* 有数据到达，接收消息 */
        char buf[256];
        int n = zmq_recv(state->zmq_sock, buf, sizeof(buf) - 1, 0);
        if (n > 0) {
            buf[n] = '\0';
            /* 尝试解析为 double */
            char* endptr = NULL;
            double val = strtod(buf, &endptr);
            if (endptr != buf) {
                state->raw_value = val;
                state->has_new_data = 1;
            }
        }
    }

    /* 输出 = 接收值 * gain */
    state->y = state->raw_value * state->gain;
    return 0;
}

void zmqsub_terminate(ZmqSubState* state) {
    if (!state) return;

    if (state->zmq_sock) {
        zmq_close(state->zmq_sock);
        state->zmq_sock = NULL;
    }
    if (state->zmq_ctx) {
        zmq_ctx_destroy(state->zmq_ctx);
        state->zmq_ctx = NULL;
    }
}
