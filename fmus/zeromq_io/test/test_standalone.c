/* 独立 ZMQ 收发测试（不依赖 FMU/FMPy）
   用法和 mock_publisher.py + FMU 一样 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <zmq.h>

int main(int argc, char** argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s sub|pub\n", argv[0]);
        return 1;
    }
    void* ctx = zmq_ctx_new();
    if (strcmp(argv[1], "sub") == 0) {
        void* sub = zmq_socket(ctx, ZMQ_SUB);
        int rcvto = 5000;
        zmq_setsockopt(sub, ZMQ_RCVTIMEO, &rcvto, sizeof(rcvto));
        int linger = 0;
        zmq_setsockopt(sub, ZMQ_LINGER, &linger, sizeof(linger));
        zmq_setsockopt(sub, ZMQ_SUBSCRIBE, "", 0);
        int rc = zmq_connect(sub, "tcp://localhost:5556");
        fprintf(stderr, "[standalone sub] connect rc=%d errno=%d\n", rc, zmq_errno());
        int n = 0;
        while (1) {
            zmq_msg_t m; zmq_msg_init(&m);
            rc = zmq_msg_recv(&m, sub, 0);
            if (rc < 0) {
                fprintf(stderr, "[standalone sub] recv timeout, rc=%d errno=%d\n", rc, zmq_errno());
                break;
            }
            char buf[256] = {0};
            memcpy(buf, zmq_msg_data(&m), zmq_msg_size(&m) < 255 ? zmq_msg_size(&m) : 255);
            fprintf(stderr, "[standalone sub] msg #%d: %s\n", ++n, buf);
            zmq_msg_close(&m);
            if (n >= 5) break;
        }
        zmq_close(sub);
    } else {
        void* pub = zmq_socket(ctx, ZMQ_PUB);
        int sndto = 0;
        zmq_setsockopt(pub, ZMQ_SNDTIMEO, &sndto, sizeof(sndto));
        int linger2 = 0;
        zmq_setsockopt(pub, ZMQ_LINGER, &linger2, sizeof(linger2));
        int rc = zmq_bind(pub, "tcp://*:5556");
        fprintf(stderr, "[standalone pub] bind rc=%d errno=%d\n", rc, zmq_errno());
        for (int i = 0; i < 5; i++) {
            char buf[64];
            snprintf(buf, sizeof(buf), "{\"x\":[%d,%d,%d,%d]}", i+1, (i+1)*2, (i+1)*3, (i+1)*4);
            zmq_msg_t m; zmq_msg_init_size(&m, strlen(buf));
            memcpy(zmq_msg_data(&m), buf, strlen(buf));
            zmq_msg_send(&m, pub, 0);
            zmq_msg_close(&m);
            fprintf(stderr, "[standalone pub] sent %s\n", buf);
            zmq_sleep(1);
        }
        zmq_close(pub);
    }
    zmq_ctx_term(ctx);
    return 0;
}