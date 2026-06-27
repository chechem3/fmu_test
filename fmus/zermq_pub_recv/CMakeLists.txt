# CMakeLists.txt —— MyModel FMU
# 由 fmu-pack init 生成，用户可手动修改以满足项目特定需求
cmake_minimum_required(VERSION 3.20)
project(MyModel C)

# ---- 头文件路径 ----
include_directories("${CMAKE_SOURCE_DIR}/include")
include_directories("${CMAKE_SOURCE_DIR}/../../third_party/fmi2/include")


# ---- 源文件 ----
set(SOURCES
    src/user_model.c
    src/fmi2_adapter.c
)

# ---- 共享库 ----
add_library(MyModel SHARED ${SOURCES})

# 输出文件名: 去掉 lib 前缀
set_target_properties(MyModel PROPERTIES
    PREFIX ""
    SUFFIX ".dll"
)

# Windows: 导出 FMI 符号
if(WIN32)
    target_compile_definitions(MyModel PRIVATE
        "FMI2_Export=__declspec(dllexport)"
    )

    # 静态链接 C/C++ 运行时，避免 FMU 依赖 libgcc_s_seh-1.dll / libstdc++-6.dll
    # 这些 DLL 在 FMPy 提取 FMU 的 temp 目录中找不到
    if(MINGW)
        target_link_options(MyModel PRIVATE
            "-static-libgcc"
            "-static-libstdc++"
            "-static"
        )
    endif()
endif()



