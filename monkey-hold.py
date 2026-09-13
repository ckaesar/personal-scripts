# coding=utf-8
"""持仓表视图的快捷查询，复用通用脚本 monkey-bitable.py"""
import importlib.util
import os

# 目标多维表格：持仓表（指定视图）
URL = "https://my.feishu.cn/wiki/PoqXwHD95iU3VSkkxuEc0vL9nrb?table=tblpyRBAhEwCBTh9&view=vewNi5QA33"

SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monkey-bitable.py")


def load_monkey():
    """加载通用脚本 monkey-bitable.py（文件名带连字符，不能直接 import）"""
    spec = importlib.util.spec_from_file_location("monkey_bitable", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    monkey = load_monkey()

    try:
        codes = monkey.get_codes(URL, monkey.DEFAULT_FIELD)
    except RuntimeError as e:
        print(e)
        return

    if not codes:
        print("没有读取到股票代码（列名：" + monkey.DEFAULT_FIELD + "）")
        return

    monkey.print_quotes(codes)


if __name__ == "__main__":
    main()
