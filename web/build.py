"""网页版构建脚本

将内置数据集（郑州 / 北京 / 示例）注入模板 template.html，生成可直接双击打开的
自包含网页 index.html。之所以要把数据内嵌进 HTML，是因为浏览器通过 file:// 协议
打开本地文件时，fetch() 读取同目录 JSON 会被同源策略拦截；内嵌后无需服务器即可运行。

使用方法：
    python web/build.py
"""

from __future__ import annotations

import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE), "data")

DATASETS = {
    "zhengzhou": os.path.join(DATA_DIR, "zhengzhou_metro.json"),
    "beijing": os.path.join(DATA_DIR, "beijing_metro.json"),
    "sample": os.path.join(DATA_DIR, "metro.json"),
}

PLACEHOLDER = "__DATASETS_JSON__"


def main() -> None:
    with open(os.path.join(BASE, "template.html"), "r", encoding="utf-8") as f:
        html = f.read()

    bundled = {}
    for key, path in DATASETS.items():
        with open(path, "r", encoding="utf-8") as f:
            bundled[key] = json.load(f)

    # JSON 序列化结果本身就是合法的 JavaScript 对象字面量
    blob = json.dumps(bundled, ensure_ascii=False)
    assert PLACEHOLDER in html, "模板中未找到占位符"
    html = html.replace(PLACEHOLDER, blob, 1)

    out = os.path.join(BASE, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(out) / 1024
    print(f"已生成：{out}")
    print(f"文件大小：{size_kb:.0f} KB")
    for key, data in bundled.items():
        n = len(data.get("stations", []))
        print(f"  内置 {key}: {data.get('name', key)}")


if __name__ == "__main__":
    main()
