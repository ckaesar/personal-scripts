# coding=utf-8
"""把服务器上 ascii 编码环境造成的两类问题统一修掉（被各脚本调用，不直接运行）

1. 输出：服务器 locale 常常是 ascii（LANG/LC_ALL 未设置），python 的 stdout 编码也是 ascii，
   脚本一打印中文就抛 UnicodeEncodeError。
2. 入参：同样的 locale 下，命令行里的中文会被解码成代理字符（\\udce8…），打印或拼进请求都会失败。

入口脚本在打印前调用 enable() 即可避免。
"""

import io
import sys


def enable():
    """修好 stdout / stderr 的编码和中文命令行参数"""
    for name in ("stdout", "stderr"):
        setattr(sys, name, _as_utf8(getattr(sys, name)))
    _fix_argv()


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


def _fix_argv():
    """把命令行参数里被解码坏的中文按 utf-8 还原

    locale 是 ascii 时（如 CentOS 7 未设 LANG），python 3.6 拿到的 argv 是代理字符，
    例如「贵州茅台」变成 '\\udce8\\udcb4\\udcb5…'，直接打印会报 surrogates not allowed。
    """
    argv = []
    for one in sys.argv:
        try:
            one.encode("utf-8")
        except UnicodeEncodeError:
            one = one.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
        argv.append(one)
    sys.argv = argv
