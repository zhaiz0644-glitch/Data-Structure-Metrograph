"""地铁数据导入脚本（通用）

将高德地图的地铁 JSON 转换为本项目使用的数据格式，支持任意城市。

数据来源（高德地图地铁接口）：
    http://map.amap.com/service/subway?_1469083453978&srhdata=<adcode>_drw_<城市拼音>.json
    例如：北京 1100_drw_beijing.json；郑州 4101_drw_zhengzhou.json

使用方法：
    python scripts/import_metro.py <输入json> <输出json>
    例如：
    python scripts/import_metro.py scripts/amap_beijing.json data/beijing_metro.json
    python scripts/import_metro.py scripts/amap_zhengzhou.json data/zhengzhou_metro.json

转换要点：
1. 站点按名称去重（换乘站在多条线路中名称与坐标一致）。
2. 经纬度通过等距圆柱投影转换为以城市质心为原点的局部千米坐标 (x, y)：
     x = (lng - lng0) * 111.32 * cos(lat0)
     y = (lat0 - lat) * 110.57
   其中 y 取 (lat0 - lat) 使“北 = 较小的 y”，与画布坐标（向下增大）约定一致；
   边权重取相邻站点的欧几里得距离，保证 A* 的 h(n) <= 真实路径长度（可采纳）。
3. 线路顺序即站点顺序，相邻站点构成一条边。
"""

from __future__ import annotations

import json
import math
import sys

# 线路配色：优先使用高德数据自带颜色 cl（如 "B35A1F"），这里提供兜底调色板
FALLBACK_COLORS = [
    "#c23a30", "#0072bc", "#f5a623", "#009944", "#8e44ad",
    "#e74c3c", "#16a085", "#2980b9", "#d35400", "#2c3e50",
    "#27ae60", "#f39c12", "#8e44ad", "#1abc9c", "#c0392b",
    "#34495e", "#7f8c8d", "#e67e22", "#9b59b6", "#3498db",
    "#2ecc71", "#e74c3c", "#f1c40f", "#1abc9c", "#95a5a6",
    "#e67e22", "#2980b9", "#c0392b",
]


def re_full_hex(s: str) -> bool:
    return len(s) == 6 and all(c in "0123456789abcdefABCDEF" for c in s)


def norm_name(name: str) -> str:
    """归一化站名。

    高德数据中部分换乘站会带“方向 / 终点 / 线路”括号后缀，
    例如郑州的“南四环(贾河)”“南四环(郑州航空港站)”实为同一站“南四环”，
    “新郑机场(郑许线)”即“新郑机场”。去掉括号后缀才能正确合并换乘站。
    """
    name = name.strip()
    for ch in ("(", "（"):
        idx = name.find(ch)
        if idx > 0:
            return name[:idx].strip()
    return name


def parse_amap(raw: dict) -> dict:
    """解析高德地铁 JSON，返回 {stations, edges, lines, ...} 中间结构。"""
    lines_raw = raw["l"]

    # 1) 收集站点（按名称去重），记录首次出现的顺序
    order = []                       # 站点名称（首次出现顺序）
    coord = {}                       # name -> (lng, lat)
    for ln in lines_raw:
        for st in ln["st"]:
            name = norm_name(st["n"])
            lng, lat = (float(v) for v in st["sl"].split(","))
            if name not in coord:
                coord[name] = (lng, lat)
                order.append(name)

    # 2) 投影中心取所有站点质心
    lngs = [coord[n][0] for n in order]
    lats = [coord[n][1] for n in order]
    lng0, lat0 = sum(lngs) / len(lngs), sum(lats) / len(lats)
    cos_lat0 = math.cos(math.radians(lat0))
    km_per_deg_lng = 111.32 * cos_lat0
    km_per_deg_lat = 110.57

    def project(lng, lat):
        # y 取 (lat0 - lat)：使“北 = 较小的 y”，与画布坐标（向下增大）约定一致
        return (round((lng - lng0) * km_per_deg_lng, 4),
                round((lat0 - lat) * km_per_deg_lat, 4))

    # 3) 站点 ID 按首次出现顺序编号
    station_id = {name: f"B{i + 1:03d}" for i, name in enumerate(order)}

    # 4) 构建边：每条线路内相邻站点相连（按 (小, 大) 去重）
    seen_edges = set()
    edges = []
    line_colors = {}
    for idx, ln in enumerate(lines_raw):
        line_name = ln["ln"]
        color = ln.get("cl", "")
        line_colors[line_name] = ("#" + color) if re_full_hex(color) else FALLBACK_COLORS[idx % len(FALLBACK_COLORS)]

        sts = ln["st"]
        for a, b in zip(sts, sts[1:]):
            na, nb = norm_name(a["n"]), norm_name(b["n"])
            if na == nb:
                continue  # 连续重复的换乘站（如“新郑机场|新郑机场”），跳过避免自环
            key = tuple(sorted((station_id[na], station_id[nb])))
            if key in seen_edges:
                continue
            seen_edges.add(key)
            xa, ya = project(*coord[na])
            xb, yb = project(*coord[nb])
            w = round(math.hypot(xa - xb, ya - yb), 3)
            edges.append({"from": key[0], "to": key[1], "weight": w, "line": line_name})

    stations = [
        {"id": station_id[n], "name": n, "x": project(*coord[n])[0], "y": project(*coord[n])[1]}
        for n in order
    ]

    return {
        "city": raw.get("s", "地铁网络"),
        "stations": stations,
        "edges": edges,
        "lines": line_colors,
        "n_lines": len(lines_raw),
        "n_stations": len(stations),
        "n_edges": len(edges),
    }


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src, out = sys.argv[1], sys.argv[2]

    with open(src, encoding="utf-8") as f:
        raw = json.load(f)

    result = parse_amap(raw)
    data = {
        "name": f"{result['city']}（{result['n_lines']} 条线路 / {result['n_stations']} 个站点）",
        "lines": result["lines"],
        "stations": result["stations"],
        "edges": result["edges"],
    }

    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    print(f"城市     : {result['city']}")
    print(f"线路数   : {result['n_lines']}")
    print(f"站点数   : {result['n_stations']}")
    print(f"区间数   : {result['n_edges']}")
    print(f"输出文件 : {out}")


if __name__ == "__main__":
    main()
