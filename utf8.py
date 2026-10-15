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

    Python 3.7+ 的标准流可以直接改编码；老版本（如 CentOS 自带的 3.6）没有 reconfigure，
    只能把底层的二进制 buffer 重新包一层。注意必须用 detach() 摘下来，直接取 stream.buffer
    的话，旧包装对象被回收时会连 buffer 一起关掉（ValueError: I/O operation on closed file）。
    """
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")
        return stream

    if not hasattr(stream, "detach"):
        return stream

    line_buffering = getattr(stream, "line_buffering", False)
    buffer = stream.detach()
    return io.TextIOWrapper(buffer, encoding="utf-8", line_buffering=line_buffering)
