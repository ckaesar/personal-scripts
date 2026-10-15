# coding=utf-8
"""把标准输出/标准错误切换成 UTF-8 的公共模块（被各脚本调用，不直接运行）

服务器上 locale 常常是 ascii（LANG/LC_ALL 未设置），此时 python 的 stdout 编码也是 ascii，
脚本一打印中文就会抛 UnicodeEncodeError。入口脚本在打印前调用 enable() 即可避免。
"""

import io
import sys


def enable():
    """把 stdout / stderr 都换成按 utf-8 编码的输出流"""
    for name in ("stdout", "stderr"):
        setattr(sys, name, _as_utf8(getattr(sys, name)))


def _as_utf8(stream):
    """返回同一个输出流的 utf-8 版本

    Python 3.7+ 的标准流可以直接改编码；老版本（3.6 及更早）没有 reconfigure，
    改用底层二进制 buffer 重新包一层。
    """
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")
        return stream

    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        return stream

    stream.flush()
    return io.TextIOWrapper(buffer, encoding="utf-8",
                            line_buffering=getattr(stream, "line_buffering", False))
