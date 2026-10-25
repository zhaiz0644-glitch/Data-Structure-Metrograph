"""算法引擎模块（Solver）

实现三种路径搜索算法，统一返回 SearchResult 对象：
- dijkstra：最快路径（加权最短路），使用优先队列（最小堆）。
- bfs：最少换乘 / 最少经过站数（基于层级搜索的无权最短路，每条边权重视为 1）。
- astar：启发式搜索，f(n) = g(n) + h(n)，启发函数 h(n) 取两站坐标间的欧几里得距离。

复杂度（设 V 为站点数、E 为区间数）：
- Dijkstra：时间 O((V+E) log V)，空间 O(V)
- BFS：时间 O(V+E)，空间 O(V)
- A*：最坏情况退化为 Dijkstra，实际因启发函数引导而扩展更少节点
"""

from __future__ import annotations

import heapq
import math
from collections import deque
from dataclasses import dataclass, field

from graph import Graph


@dataclass
class SearchResult:
    """一次搜索的统一结果"""
    path: list[str]            # 站点 ID 序列（起点 -> 终点）
    total_weight: float        # 路径总权重（Dijkstra/A* 为距离；BFS 为站段数）
    visited_count: int         # 搜索过程中实际扩展的节点数，用于对比算法效率
    visit_order: list[str] = field(default_factory=list)  # 扩展顺序，用于动画演示
    message: str = ""          # 失败原因（如两站不连通）

    @property
    def success(self) -> bool:
        return len(self.path) > 0


def _reconstruct(prev: dict, target: str) -> list[str]:
    """由前驱表回溯出完整路径"""
    path = []
    cur = target
    while cur is not None:
        path.append(cur)
        cur = prev.get(cur)
    path.reverse()
    return path


def euclidean(g: Graph, a: str, b: str) -> float:
    """欧几里得距离启发函数 h(n)：站点坐标间的直线距离"""
    sa, sb = g.get_station(a), g.get_station(b)
    return math.hypot(sa.x - sb.x, sa.y - sb.y)


def dijkstra(g: Graph, start: str, target: str) -> SearchResult:
    """Dijkstra：非负加权图上求单源最短路径（最快路径）。"""
    dist = {start: 0.0}
    prev = {start: None}
    visited = set()
    visit_order: list[str] = []
    pq = [(0.0, start)]                 # 优先队列（最小堆）：(当前估计距离, 站点)

    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        visit_order.append(u)
        if u == target:
            return SearchResult(_reconstruct(prev, target), d, len(visit_order), visit_order)

        # 松弛（Relaxation）：尝试用 u 更新其邻居的距离估计值
        for v, w, _ in g.neighbors(u):
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))

    return SearchResult([], 0.0, len(visit_order), visit_order, "两站不连通，无法到达")


def bfs(g: Graph, start: str, target: str) -> SearchResult:
    """BFS：层级搜索，求经过站数最少的路径（每条边权重视为 1）。"""
    prev = {start: None}
    visited = {start}
    visit_order: list[str] = []
    q = deque([start])

    while q:
        u = q.popleft()
        visit_order.append(u)
        if u == target:
            path = _reconstruct(prev, target)
            return SearchResult(path, float(len(path) - 1), len(visit_order), visit_order)

        for v, _, _ in g.neighbors(u):
            if v not in visited:
                visited.add(v)
                prev[v] = u
                q.append(v)

    return SearchResult([], 0.0, len(visit_order), visit_order, "两站不连通，无法到达")


def astar(g: Graph, start: str, target: str, heuristic=euclidean) -> SearchResult:
    """A*：f(n) = g(n) + h(n)，其中 g(n) 为已走距离，h(n) 为到终点的直线距离。"""
    dist = {start: 0.0}
    prev = {start: None}
    visited = set()
    visit_order: list[str] = []
    # 堆中元素：(f 值, g 值, 站点)，以 f 值为优先级
    pq = [(heuristic(g, start, target), 0.0, start)]

    while pq:
        f, g_cost, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        visit_order.append(u)
        if u == target:
            return SearchResult(_reconstruct(prev, target), g_cost, len(visit_order), visit_order)

        for v, w, _ in g.neighbors(u):
            nd = g_cost + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd + heuristic(g, v, target), nd, v))

    return SearchResult([], 0.0, len(visit_order), visit_order, "两站不连通，无法到达")


class Solver:
    """统一的算法引擎入口，将具体算法与上层调用解耦。"""

    # 算法标识 -> (实现函数, 界面显示名称)
    ALGORITHMS = {
        "dijkstra": (dijkstra, "Dijkstra（最快路径）"),
        "bfs": (bfs, "BFS（最少换乘/最少站数）"),
        "astar": (astar, "A*（启发式搜索）"),
    }

    def __init__(self, graph: Graph):
        self.graph = graph

    def solve(self, start: str, target: str, algorithm: str = "dijkstra") -> SearchResult:
        """按算法标识执行搜索，返回 SearchResult。"""
        if start not in self.graph.stations or target not in self.graph.stations:
            return SearchResult([], 0.0, 0, [], "起点或终点不存在")
        if algorithm not in self.ALGORITHMS:
            raise ValueError(f"未知算法: {algorithm}")
        func, _ = self.ALGORITHMS[algorithm]
        return func(self.graph, start, target)
