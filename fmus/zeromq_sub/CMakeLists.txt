# CMakeLists.txt —— zmqsub FMU
# C 源码 + ZeroMQ C++ 静态库
cmake_minimum_required(VERSION 3.20)
project(zmqsub C CXX)

# ---- 头文件路径 ----
# FMI 2.0 头文件
include_directories("${CMAKE_SOURCE_DIR}/../../third_party/fmi2/include")
# 项目自己的头文件
include_directories("${CMAKE_SOURCE_DIR}/include")
# ZeroMQ 头文件
include_directories("${CMAKE_SOURCE_DIR}/../../third_party/zeromq/include")

# ---- 源文件 ----
set(SOURCES
    src/user_model.c
    src/fmi2_adapter.c
)

# ---- 共享库 ----
add_library(zmqsub SHARED ${SOURCES})

# 输出: zmqsub.dll（去掉 lib 前缀）
# LINKER_LANGUAGE CXX: libzmq.a 是 C++ 库，必须用 C++ 链接器
set_target_properties(zmqsub PROPERTIES
    PREFIX ""
    SUFFIX ".dll"
    LINKER_LANGUAGE CXX
)

# Windows: 导出 FMI 符号
if(WIN32)
    target_compile_definitions(zmqsub PRIVATE
        "FMI2_Export=__declspec(dllexport)"
    )
endif()

# 静态链接 ZeroMQ 时需要此宏，避免 __imp_ 前缀
target_compile_definitions(zmqsub PRIVATE ZMQ_STATIC)

# ---- 外部库链接 ----
# 静态链接 libzmq.a（ZeroMQ 代码嵌入 DLL，无需外部 ZeroMQ 依赖）
# 同时静态链接 C++ 运行时（-static-libgcc/-static-libstdc++），
# 避免依赖 libgcc_s_seh-1.dll / libstdc++-6.dll / libwinpthread-1.dll
# （这些 DLL 在 FMPy 提取 FMU 的 temp 目录中找不到）
target_link_libraries(zmqsub PRIVATE
    "${CMAKE_SOURCE_DIR}/../../third_party/zeromq/lib/libzmq.a"
    ws2_32
    iphlpapi
)

# Windows: 静态链接 C++ 运行时，让 FMU 自包含
if(WIN32 AND MINGW)
    target_link_options(zmqsub PRIVATE
        "-static-libgcc"
        "-static-libstdc++"
        "-static"
    )
endif()
