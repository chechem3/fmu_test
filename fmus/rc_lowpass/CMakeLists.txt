# CMakeLists.txt —— rc_lowpass FMU
# 由 fmu-pack init 生成；项目可手动修改
cmake_minimum_required(VERSION 3.20)
project(rc_lowpass C)

include_directories("${CMAKE_SOURCE_DIR}/include")
include_directories("${CMAKE_SOURCE_DIR}/../../third_party/fmi2/include")

# 工具生成的 fmi2_adapter.c 在 build/ 下
include_directories("${CMAKE_SOURCE_DIR}/build")

add_library(rc_lowpass SHARED
    src/user_model.c
    build/fmi2_adapter.c
)

set_target_properties(rc_lowpass PROPERTIES
    PREFIX ""
    SUFFIX ".dll"
)

if(WIN32)
    target_compile_definitions(rc_lowpass PRIVATE
        "FMI2_Export=__declspec(dllexport)"
    )
    if(MINGW)
        # 静态链接 C/C++ 运行时，让 FMU 自包含
        target_link_options(rc_lowpass PRIVATE
            "-static-libgcc" "-static-libstdc++" "-static"
        )
    endif()
endif()
