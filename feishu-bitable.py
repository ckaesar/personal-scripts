# coding=utf-8
import sys

import feishu_bitable as fb


def main():
    args = sys.argv[1:]
    if not args:
        print("用法：")
        print("  python feishu-bitable.py <多维表格链接> [列名1 列名2 ...]")
        print("  python feishu-bitable.py <app_token> <table_id> [列名1 列名2 ...]")
        print("示例：")
        print("  python feishu-bitable.py \"https://xxx.feishu.cn/wiki/PoqXwHD95iU3VSkkxuEc0vL9nrb?table=tblzxBcMpwY6KEQm\" 股票代码")
        print("说明：凭证读取自同目录的 feishu-config.json；链接里带 view 参数时只读该视图；不传列名时输出全部列")
        return

    view_id = ""
    if args[0].startswith("http"):
        app_token, table_id, view_id = fb.parse_table_url(args[0])
        field_names = args[1:]
    elif len(args) >= 2:
        app_token, table_id, field_names = args[0], args[1], args[2:]
    else:
        print("参数不足：需要「表格链接」或「app_token + table_id」")
        return

    if not app_token or not table_id:
        print("没能从参数中解析出 app_token 和 table_id，请检查链接或直接传入 <app_token> <table_id>")
        return

    try:
        app_id, app_secret = fb.load_config()
        token = fb.get_tenant_access_token(app_id, app_secret)
        columns = fb.list_fields(token, app_token, table_id)

        if field_names:
            # 传错列名时给出提示，避免只拿到空结果
            unknown = [name for name in field_names if name not in columns]
            if unknown:
                print("列名不存在：" + ", ".join(unknown))
                print("表格可用列：" + ", ".join(columns))
                return
        else:
            field_names = columns

        records = fb.search_records(token, app_token, table_id, field_names, view_id)
    except RuntimeError as e:
        print(e)
        return

    print("\t".join(field_names))
    for one in records:
        print("\t".join(fb.format_value(one.get(name)) for name in field_names))

    print("共 " + str(len(records)) + " 条记录", file=sys.stderr)


if __name__ == "__main__":
    main()
