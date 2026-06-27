"""XSD schema 校验

使用 lxml 对渲染后的 modelDescription.xml 做 FMI 2.0 XSD schema 校验。

校验流程:
  1. 解析 XML 字符串 → etree 文档对象
  2. 解析 XSD 文件 → XMLSchema 对象
  3. 调用 assertValid 做全量校验

错误类型:
  - XMLSyntaxError: XML 格式错误（标签未闭合等）
  - XMLSchemaParseError: XSD 文件本身解析失败
  - DocumentInvalid: XML 不符合 schema 约束
"""

from pathlib import Path
from lxml import etree


def validate_xml(xml_str: str, xsd_path: Path) -> tuple[bool, str]:
    """用 FMI 2.0 XSD 校验 modelDescription.xml

    Args:
        xml_str: modelDescription.xml 的字符串内容
        xsd_path: fmi2ModelDescription.xsd 文件路径

    Returns:
        (ok, message) —— ok=True 表示校验通过，message 为错误描述或 "OK"
    """
    # 步骤 1: 解析 XML 字符串
    try:
        xml_doc = etree.fromstring(xml_str.encode("utf-8"))
    except etree.XMLSyntaxError as e:
        return False, f"XML 语法错误: {e}"

    # 步骤 2: 解析 XSD schema 文件
    try:
        xsd_doc = etree.parse(str(xsd_path))
        schema = etree.XMLSchema(xsd_doc)
    except etree.XMLSchemaParseError as e:
        return False, f"XSD 解析错误: {e}"

    # 步骤 3: 执行 schema 校验
    try:
        schema.assertValid(xml_doc)
        return True, "OK"
    except etree.DocumentInvalid as e:
        return False, f"XSD 校验失败: {e}"
