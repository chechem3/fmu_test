# CMakeLists.txt —— zeromq_io FMU
# 用户自行维护的 CMake 配置：在 fmu-pack init 生成的骨架上扩展
# 扩展点：
#   - 链接 cJSON 静态库（third_party/cjson）
#   - 链接 libzmq 静态库（third_party/zeromq）
#   - 链接 pthread / stdc++（libzmq 运行时依赖）

cmake_minimum_required(VERSION 3.20)
project(zeromq_io C CXX)  # libzmq 是 C++ 编译产物，需要 CXX ABI

include_directories("${CMAKE_SOURCE_DIR}/include")
include_directories("${CMAKE_SOURCE_DIR}/../../third_party/fmi2/include")
include_directories("${CMAKE_SOURCE_DIR}/../../third_party/zeromq/include")
include_directories("${CMAKE_SOURCE_DIR}/../../third_party/cjson/include")

# 工具生成的 fmi2_adapter.c 在 build/ 下
include_directories("${CMAKE_SOURCE_DIR}/build")

# 静态库路径
set(ZEROMQ_LIB "${CMAKE_SOURCE_DIR}/../../third_party/zeromq/lib/libzmq.a")
set(CJSON_LIB   "${CMAKE_SOURCE_DIR}/../../third_party/cjson/lib/libcjson.a")

add_library(zeromq_io SHARED
    src/user_model.c
    build/fmi2_adapter.c
)

# 链接顺序：用户对象 → cJSON → libzmq（被 libzmq 依赖的 pthread/stdc++ 放最后）
target_link_libraries(zeromq_io PRIVATE
    "${CJSON_LIB}"
    "${ZEROMQ_LIB}"
)

set_target_properties(zeromq_io PROPERTIES
    PREFIX ""
    SUFFIX ".dll"
)

if(WIN32)
    target_compile_definitions(zeromq_io PRIVATE
        "FMI2_Export=__declspec(dllexport)"
        # zmq.h 在 _WIN32 下默认 __declspec(dllimport)；静态链接需定义 ZMQ_STATIC
        "ZMQ_STATIC"
    )
    if(MINGW)
        # 静态链接 C/C++ 运行时，让 FMU 自包含
        target_link_options(zeromq_io PRIVATE
            "-static-libgcc" "-static-libstdc++" "-static"
        )
        # libzmq 编译时依赖 pthread / stdc++ ABI；Winsock 用于 select()
        target_link_libraries(zeromq_io PRIVATE
            pthread
            stdc++
            ws2_32
            iphlpapi
        )
    endif()
endif()