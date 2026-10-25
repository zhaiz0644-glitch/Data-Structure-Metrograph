"""图数据结构模块（Graph）

将城市地铁 / 公交网络抽象为图 G = (V, E)：
- 顶点（Station）：表示站点，包含 ID、名称、二维坐标（坐标既用于 A* 的
  欧几里得启发函数，也用于界面可视化）。
- 边（Edge）：表示相邻站点之间的一个线路区间，包含距离权重与所属线路 ID。

存储结构选择【邻接表】：
城市交通图是典型的稀疏图（|E| 远小于 |V|^2），邻接表比邻接矩阵更省空间，
且遍历某个站点的全部邻居时只需 O(degree) 时间，非常适合 Dijkstra / A*
这类需要反复松弛邻居的操作。
"""

from __future__ import annotations


class Station:
    """站点（图顶点）"""

    def __init__(self, station_id: str, name: str, x: float, y: float):
        self.id = station_id   # 唯一标识
        self.name = name       # 站名
        self.x = float(x)      # 横坐标（km），用于启发函数与绘图
        self.y = float(y)      # 纵坐标（km）

    def __repr__(self) -> str:
        return f"Station({self.id}, {self.name}, ({self.x}, {self.y}))"


class Edge:
    """线路区间（图的边）"""

    def __init__(self, start_id: str, end_id: str, weight: float, line_id: str):
        self.start_id = start_id
        self.end_id = end_id
        self.weight = float(weight)   # 距离 / 时间权重
        self.line_id = line_id        # 所属线路，用于“最少换乘”与可视化着色

    def __repr__(self) -> str:
        return f"Edge({self.start_id}->{self.end_id}, w={self.weight}, line={self.line_id})"


class Graph:
    """无向带权图，采用邻接表存储"""

    def __init__(self):
        self.stations: dict[str, Station] = {}   # id -> Station
        self.adj: dict[str, list] = {}           # id -> [(neighbor_id, weight, line_id), ...]
        self.line_colors: dict[str, str] = {}    # 线路名 -> 颜色（可选，来自数据文件的 lines 字段）

    # ---------- 基础操作 ----------
    def add_station(self, station: Station) -> None:
        if station.id in self.stations:
            raise ValueError(f"站点编号重复: {station.id}")
        self.stations[station.id] = station
        self.adj.setdefault(station.id, [])

    def add_edge(self, start_id: str, end_id: str, weight: float, line_id: str = "") -> None:
        if start_id not in self.stations or end_id not in self.stations:
            raise ValueError(f"边引用了不存在的站点: {start_id} 或 {end_id}")
        if float(weight) < 0:
            raise ValueError("边权重不能为负数")
        # 地铁 / 公交线路可双向通行，视为无向图：两个方向都加入邻接表
        self.adj[start_id].append((end_id, float(weight), line_id))
        self.adj[end_id].append((start_id, float(weight), line_id))

    def remove_station(self, station_id: str) -> None:
        """删除站点及其所有关联边（用于“动态增删”扩展功能）"""
        if station_id not in self.stations:
            raise ValueError(f"站点不存在: {station_id}")
        self.stations.pop(station_id)
        self.adj.pop(station_id, None)
        # 清除其它站点邻接表中指向该站点的边
        for nid in self.adj:
            self.adj[nid] = [(v, w, l) for (v, w, l) in self.adj[nid] if v != station_id]

    # ---------- 查询操作 ----------
    def neighbors(self, station_id: str) -> list:
        """返回某站点的全部邻居列表 [(neighbor_id, weight, line_id), ...]"""
        return self.adj.get(station_id, [])

    def get_station(self, station_id: str) -> Station | None:
        return self.stations.get(station_id)

    def all_station_ids(self) -> list[str]:
        return list(self.stations.keys())

    def edge_count(self) -> int:
        return sum(len(v) for v in self.adj.values()) // 2  # 无向图，双向各存一份

    def __len__(self) -> int:
        return len(self.stations)

    def __repr__(self) -> str:
        return f"Graph({len(self.stations)} 个站点, {self.edge_count()} 条区间)"
