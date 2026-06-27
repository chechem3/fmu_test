# CMakeLists.txt —— rc_lowpass FMU
# 纯 C 项目，无外部依赖
cmake_minimum_required(VERSION 3.20)
project(rc_lowpass C)

# ---- 头文件路径 ----
# FMI 2.0 头文件（相对于仓库根目录）
include_directories("${CMAKE_SOURCE_DIR}/../../third_party/fmi2/include")
# 项目自己的头文件
include_directories("${CMAKE_SOURCE_DIR}/include")

# ---- 源文件 ----
set(SOURCES
    src/user_model.c
    src/fmi2_adapter.c
)

# ---- 共享库 ----
add_library(rc_lowpass SHARED ${SOURCES})

# 输出: rc_lowpass.dll（去掉 lib 前缀）
set_target_properties(rc_lowpass PROPERTIES
    PREFIX ""
    SUFFIX ".dll"
)

# Windows: 导出 FMI 符号
if(WIN32)
    target_compile_definitions(rc_lowpass PRIVATE
        "FMI2_Export=__declspec(dllexport)"
    )
endif()
