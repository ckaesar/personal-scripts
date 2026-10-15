# coding=utf-8
"""把标准输出/标准错误切换成 UTF-8 的公共模块（被各脚本调用，不直接运行）

服务器上 locale 常常是 ascii（LANG/LC_ALL 未设置），此时 python 的 stdout 编码也是 ascii，
脚本一打印中文就会抛 UnicodeEncodeError。入口脚本在打印前调用 enable() 即可避免。
"""

import sys


def enable():
    """把 stdout / stderr 的编码改成 utf-8（不支持改编码的输出流会跳过）"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
