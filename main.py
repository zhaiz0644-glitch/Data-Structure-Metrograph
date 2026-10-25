"""城市交通路径导航系统 —— 程序入口

运行方式：
    python main.py                              # 默认加载郑州地铁数据（中等规模）
    python main.py data/metro.json              # 加载示例小网络
    python main.py data/beijing_metro.json      # 加载北京地铁完整数据
    python main.py data/zhengzhou_metro.json    # 加载郑州地铁数据
    python main.py <任意 .txt 或 .json>          # 加载指定数据文件

依赖：仅使用 Python 标准库（tkinter、heapq、json、math、collections 等），无需额外安装。
"""

from __future__ import annotations

import os
import sys

from data_loader import load_graph
from ui import MetroApp


def main() -> None:
    base = os.path.dirname(os.path.abspath(__file__))
    default_path = os.path.join(base, "data", "zhengzhou_metro.json")

    path = sys.argv[1] if len(sys.argv) > 1 else default_path
    if not os.path.exists(path):
        print(f"未找到数据文件：{path}，将回退到郑州地铁数据。")
        path = default_path

    graph = load_graph(path)
    app = MetroApp(graph, data_path=path)
    app.mainloop()


if __name__ == "__main__":
    main()
