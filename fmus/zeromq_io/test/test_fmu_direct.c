/* 直接 LoadLibrary 加载 FMU DLL，调用 model_init / model_step，
   不通过 FMPy，看 ZMQ 消息流是否正常。 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

typedef struct { double x0,x1,x2,x3; } InT;
typedef struct { double y0,y1,y2,y3; } OutT;
typedef struct { char a[64], b[64]; } ParamT;

int main(void) {
    HMODULE dll = LoadLibraryA("D:/Programs/20260625_FMILearn/fmu_test/fmus/zeromq_io/build/win64/zeromq_io.dll");
    if (!dll) { fprintf(stderr, "LoadLibrary failed: %lu\n", GetLastError()); return 1; }

    int (*init)(ParamT*, InT*, OutT*) = (int(*)(ParamT*,InT*,OutT*))GetProcAddress(dll, "model_init");
    int (*step)(ParamT*, InT*, OutT*, double, double) = (int(*)(ParamT*,InT*,OutT*,double,double))GetProcAddress(dll, "model_step");
    void (*term)(ParamT*, InT*, OutT*) = (void(*)(ParamT*,InT*,OutT*))GetProcAddress(dll, "model_terminate");
    if (!init || !step || !term) {
        fprintf(stderr, "GetProcAddress failed\n");
        return 1;
    }

    ParamT p = {{0}};
    InT in = {0};
    OutT out = {0};
    int rc = init(&p, &in, &out);
    fprintf(stderr, "[direct] init rc=%d\n", rc);

    for (int i = 0; i < 50; i++) {
        rc = step(&p, &in, &out, i*0.1, 0.1);
        if (i < 5 || i % 10 == 0) {
            fprintf(stderr, "[direct] step #%d rc=%d in={%.1f,%.1f,%.1f,%.1f} out={%.1f,%.1f,%.1f,%.1f}\n",
                i, rc, in.x0, in.x1, in.x2, in.x3, out.y0, out.y1, out.y2, out.y3);
        }
        Sleep(100);
    }

    term(&p, &in, &out);
    FreeLibrary(dll);
    return 0;
}