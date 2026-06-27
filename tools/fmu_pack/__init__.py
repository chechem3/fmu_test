"""FMU 打包工具 —— 把用户 C 模型封装为 FMI 2.0 Co-Simulation FMU

本包实现从 fmu.yaml 配置 + C 源码 → 标准 .fmu 文件的完整流水线:
  1. 配置加载与校验 (config.py)
  2. VR 路由头生成   (router_gen.py)
  3. XML 模板渲染    (xml_gen.py)
  4. XSD schema 校验 (validator.py)
  5. 编译器驱动构建   (builder.py)
  6. ZIP 组装打包    (packager.py)
"""

__version__ = "0.1.0"
