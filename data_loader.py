"""数据加载与保存模块

支持两种数据格式：
- JSON：结构化，便于程序之间交换（推荐）。
- TXT：以注释行（# 开头）与逗号分隔的表格行表示，便于手工编辑。

JSON 结构示例：
{
  "name": "示例城市地铁网络",
  "stations": [{"id": "S01", "name": "西苑站", "x": 5, "y": 20}],
  "edges":    [{"from": "S01", "to": "S02", "weight": 7.0, "line": "1号线"}]
}

TXT 结构示例（# 为注释）：
# 站点: station, 编号, 名称, 横坐标, 纵坐标
station, S01, 西苑站, 5, 20
# 区间: edge, 起点, 终点, 距离, 线路名
edge, S01, S02, 7.0, 1号线
"""

from __future__ import annotations

import json

from graph import Graph, Station


def load_graph(path: str) -> Graph:
    """根据文件扩展名自动选择加载器。"""
    if path.lower().endswith(".json"):
        return load_json(path)
    return load_txt(path)


def load_json(path: str) -> Graph:
    g = Graph()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for s in data["stations"]:
        g.add_station(Station(str(s["id"]), s["name"], float(s["x"]), float(s["y"])))
    for e in data.get("edges", []):
        g.add_edge(str(e["from"]), str(e["to"]), float(e["weight"]), str(e.get("line", "")))
    g.line_colors = {str(k): str(v) for k, v in data.get("lines", {}).items()}
    return g


def load_txt(path: str) -> Graph:
    g = Graph()
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if not parts:
                continue
            tag = parts[0].lower()
            if tag == "station" and len(parts) >= 5:
                g.add_station(Station(parts[1], parts[2], float(parts[3]), float(parts[4])))
            elif tag == "edge" and len(parts) >= 4:
                line_id = parts[4] if len(parts) > 4 else ""
                g.add_edge(parts[1], parts[2], float(parts[3]), line_id)
    return g


def save_json(graph: Graph, path: str) -> None:
    """将图导出为 JSON 文件（用于“保存数据”扩展功能）。"""
    stations = [
        {"id": s.id, "name": s.name, "x": s.x, "y": s.y}
        for s in graph.stations.values()
    ]
    seen = set()
    edges = []
    for sid, neighbors in graph.adj.items():
        for (nid, w, line) in neighbors:
            key = tuple(sorted((sid, nid)))
            if key in seen:
                continue
            seen.add(key)
            edges.append({"from": sid, "to": nid, "weight": w, "line": line})
    data = {"name": "城市地铁网络", "stations": stations, "edges": edges,
            "lines": graph.line_colors}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
