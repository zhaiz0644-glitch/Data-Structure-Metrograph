"""图形界面模块（UI）

基于 Tkinter 实现，与图结构（Graph）和算法引擎（Solver）解耦：
- 左侧画布可视化站点网络，支持鼠标滚轮缩放、按住左键拖拽平移、点击站点选点、
  悬停查看站名与途经线路。
- 顶部工具栏提供算法选择、起终点下拉框、搜索、动画与站名开关。
- 右侧面板展示路径站点清单、距离、耗时与搜索效率。
- 支持动态增删站点 / 区间，以及加载 / 保存数据文件。
"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from graph import Graph, Station
from solver import Solver, SearchResult
from data_loader import load_graph, save_json


# 兜底线路配色（数据文件未提供 lines 字段时使用）
LINE_COLORS = ["#e74c3c", "#3498db", "#27ae60", "#e67e22", "#8e44ad",
               "#16a085", "#c0392b", "#2c3e50", "#f39c12", "#2980b9"]

STATION_R = 8            # 站点圆点半径
SELECT_R = 12            # 起终点选中标记半径
PATH_WIDTH = 5           # 高亮路径线宽
LABEL_THRESHOLD = 250    # 站点数超过此值时默认不显示站名（郑州 233 默认显示，北京 411 默认关闭）


class MetroApp(tk.Tk):
    def __init__(self, graph: Graph, data_path: str = ""):
        super().__init__()
        self.title("城市交通路径导航系统")
        self.geometry("1220x720")
        self.minsize(960, 600)

        self.graph = graph
        self.solver = Solver(graph)
        self.data_path = data_path

        # 交互状态（起终点以站名存储，搜索时再转为内部编号）
        self.start_name = tk.StringVar()
        self.end_name = tk.StringVar()
        self.algorithm = tk.StringVar(value="dijkstra")
        self.animate = tk.BooleanVar(value=True)
        self.show_names = tk.BooleanVar(value=len(graph.stations) <= LABEL_THRESHOLD)
        self.pick_start = True

        # 视野（viewport）：中心世界坐标 + 缩放（像素/公里）
        self.view_cx = 0.0
        self.view_cy = 0.0
        self.view_scale = 1.0

        # 拖拽 / 悬停状态
        self._drag_start = (0, 0)
        self._drag_moved = False
        self._pan_origin = (0.0, 0.0)
        self._hover_sid = None

        # 动画与结果状态
        self._anim_jobs: list[str] = []
        self._animating = False
        self._current_result: SearchResult | None = None

        self.line_colors = self._build_line_colors()
        self._fitted = False

        self._build_widgets()
        self._bind_canvas()
        self._sync_combobox()
        self.redraw()

    # ------------------------------------------------------------------ 界面搭建
    def _build_widgets(self) -> None:
        toolbar = ttk.Frame(self, padding=(10, 8))
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(toolbar, text="算法:").pack(side=tk.LEFT)
        for key, (_, label) in Solver.ALGORITHMS.items():
            ttk.Radiobutton(toolbar, text=label, variable=self.algorithm,
                            value=key).pack(side=tk.LEFT, padx=(2, 8))

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        ttk.Label(toolbar, text="起点:").pack(side=tk.LEFT)
        self.start_box = ttk.Combobox(toolbar, textvariable=self.start_name, width=18, state="readonly")
        self.start_box.pack(side=tk.LEFT, padx=(2, 8))

        ttk.Label(toolbar, text="终点:").pack(side=tk.LEFT)
        self.end_box = ttk.Combobox(toolbar, textvariable=self.end_name, width=18, state="readonly")
        self.end_box.pack(side=tk.LEFT, padx=(2, 8))

        ttk.Button(toolbar, text="搜索路径", command=self.on_search).pack(side=tk.LEFT, padx=(6, 2))
        ttk.Checkbutton(toolbar, text="动画演示", variable=self.animate).pack(side=tk.LEFT, padx=8)
        ttk.Checkbutton(toolbar, text="显示站名", variable=self.show_names,
                        command=self.redraw).pack(side=tk.LEFT, padx=8)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Button(toolbar, text="重置视图", command=self.on_reset_view).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="加载数据…", command=self.on_load).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="保存数据…", command=self.on_save).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="添加站点", command=self.on_add_station).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="删除站点", command=self.on_remove_station).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="添加区间", command=self.on_add_edge).pack(side=tk.LEFT, padx=2)

        main = ttk.Frame(self)
        main.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(main, bg="#f7f9fc", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 6), pady=(0, 6))

        panel = ttk.Frame(main, width=290)
        panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 10), pady=(0, 6))
        panel.pack_propagate(False)

        ttk.Label(panel, text="路径站点清单", font=("", 11, "bold")).pack(anchor=tk.W, pady=(4, 2))
        self.path_list = tk.Listbox(panel, height=14, font=("Microsoft YaHei", 10))
        self.path_list.pack(fill=tk.BOTH, expand=True)

        self.info_text = tk.Text(panel, height=8, font=("Microsoft YaHei", 10), state=tk.DISABLED)
        self.info_text.pack(fill=tk.X, pady=(6, 0))

        self.status = tk.StringVar(value="滚轮缩放、按住左键拖拽平移、点击站点选起终点（先起点后终点）。")
        ttk.Label(self, textvariable=self.status, relief=tk.SUNKEN, anchor=tk.W,
                  padding=(8, 3)).pack(side=tk.BOTTOM, fill=tk.X)

    def _bind_canvas(self) -> None:
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<MouseWheel>", self._on_wheel)          # Windows / macOS
        self.canvas.bind("<Button-4>", lambda e: self._zoom_at(e.x, e.y, 1.25))   # Linux
        self.canvas.bind("<Button-5>", lambda e: self._zoom_at(e.x, e.y, 0.8))
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Configure>", self._on_configure)

    # ------------------------------------------------------------------ 视野与坐标
    def _pos(self, sid: str) -> tuple[float, float]:
        """站点世界坐标 -> 画布坐标。"""
        s = self.graph.get_station(sid)
        cw = max(self.canvas.winfo_width(), 100)
        ch = max(self.canvas.winfo_height(), 100)
        return (cw / 2 + (s.x - self.view_cx) * self.view_scale,
                ch / 2 + (s.y - self.view_cy) * self.view_scale)

    def _fit_view(self) -> None:
        """根据数据范围自动调整视野，使整张图居中铺满画布。"""
        sts = list(self.graph.stations.values())
        if not sts:
            return
        xs = [s.x for s in sts]
        ys = [s.y for s in sts]
        span_x = max(max(xs) - min(xs), 1e-6)
        span_y = max(max(ys) - min(ys), 1e-6)
        cw = max(self.canvas.winfo_width(), 400)
        ch = max(self.canvas.winfo_height(), 300)
        margin = 44
        self.view_scale = min((cw - 2 * margin) / span_x, (ch - 2 * margin) / span_y)
        self.view_cx = (min(xs) + max(xs)) / 2
        self.view_cy = (min(ys) + max(ys)) / 2

    def _zoom_at(self, x: float, y: float, factor: float) -> None:
        """以画布坐标 (x, y) 为锚点缩放。"""
        cw = max(self.canvas.winfo_width(), 100)
        ch = max(self.canvas.winfo_height(), 100)
        wx = self.view_cx + (x - cw / 2) / self.view_scale
        wy = self.view_cy + (y - ch / 2) / self.view_scale
        self.view_scale = max(0.3, min(self.view_scale * factor, 800.0))
        self.view_cx = wx - (x - cw / 2) / self.view_scale
        self.view_cy = wy - (y - ch / 2) / self.view_scale
        self.redraw()

    def _station_at(self, x: float, y: float) -> str | None:
        """返回画布坐标 (x, y) 附近的站点编号，无则返回 None。"""
        best, best_d = None, STATION_R + 6
        for sid in self.graph.stations:
            px, py = self._pos(sid)
            d = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
            if d < best_d:
                best, best_d = sid, d
        return best

    def _name_to_id(self, name: str) -> str | None:
        """站点名称 -> 内部编号（站名唯一）。"""
        for sid, s in self.graph.stations.items():
            if s.name == name:
                return sid
        return None

    def _gen_station_id(self) -> str:
        """为新添加的站点自动生成一个不重复的编号。"""
        i = 1
        while f"U{i:03d}" in self.graph.stations:
            i += 1
        return f"U{i:03d}"

    # ------------------------------------------------------------------ 绘图
    def _build_line_colors(self) -> dict[str, str]:
        lines = sorted({l for nbrs in self.graph.adj.values() for (_, _, l) in nbrs if l})
        colors = {}
        for i, line in enumerate(lines):
            colors[line] = self.graph.line_colors.get(line) or LINE_COLORS[i % len(LINE_COLORS)]
        return colors

    def _station_r(self) -> int:
        n = len(self.graph.stations)
        return 5 if n > 200 else (6 if n > 60 else STATION_R)

    def _edge_w(self) -> int:
        return 2 if len(self.graph.stations) > 200 else 3

    def redraw(self) -> None:
        """整图重绘：边、站点、站名、起终点标记与高亮路径。"""
        self.canvas.delete("all")
        if not self.graph.stations:
            return
        r = self._station_r()
        ew = self._edge_w()

        # 1. 边
        drawn = set()
        for sid, nbrs in self.graph.adj.items():
            x1, y1 = self._pos(sid)
            for (nid, w, line) in nbrs:
                key = tuple(sorted((sid, nid)))
                if key in drawn:
                    continue
                drawn.add(key)
                x2, y2 = self._pos(nid)
                color = self.line_colors.get(line, "#95a5a6")
                self.canvas.create_line(x1, y1, x2, y2, fill=color, width=ew, capstyle=tk.ROUND)

        # 2. 站点与站名
        for sid in self.graph.stations:
            x, y = self._pos(sid)
            self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                    fill="#ffffff", outline="#34495e", width=1)
            if self.show_names.get():
                self.canvas.create_text(x, y - r - 3, text=self.graph.get_station(sid).name,
                                        font=("Microsoft YaHei", 7), fill="#2c3e50")

        # 3. 起终点标记与高亮路径
        self._mark_selected()
        if self._current_result and self._current_result.success and not self._animating:
            self._draw_path_lines(self._current_result)

        # 4. 悬停高亮
        if self._hover_sid and self._hover_sid in self.graph.stations:
            x, y = self._pos(self._hover_sid)
            self.canvas.create_oval(x - 11, y - 11, x + 11, y + 11,
                                    outline="#f39c12", width=3, tags="hover")

    def _mark_selected(self) -> None:
        for name, color in ((self.start_name.get(), "#27ae60"), (self.end_name.get(), "#e74c3c")):
            sid = self._name_to_id(name)
            if sid is not None:
                x, y = self._pos(sid)
                self.canvas.create_oval(x - SELECT_R, y - SELECT_R, x + SELECT_R, y + SELECT_R,
                                        outline=color, width=3)

    def _draw_path_lines(self, result: SearchResult) -> None:
        for i in range(len(result.path) - 1):
            a, b = result.path[i], result.path[i + 1]
            x1, y1 = self._pos(a)
            x2, y2 = self._pos(b)
            self.canvas.create_line(x1, y1, x2, y2, fill="#c0392b", width=PATH_WIDTH,
                                    capstyle=tk.ROUND, joinstyle=tk.ROUND)

    # ------------------------------------------------------------------ 事件处理
    def _on_press(self, event) -> None:
        self._drag_start = (event.x, event.y)
        self._drag_moved = False
        self._pan_origin = (self.view_cx, self.view_cy)

    def _on_drag(self, event) -> None:
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        if abs(dx) < 3 and abs(dy) < 3:
            return
        self._drag_moved = True
        self.view_cx = self._pan_origin[0] - dx / self.view_scale
        self.view_cy = self._pan_origin[1] - dy / self.view_scale
        self.redraw()

    def _on_release(self, event) -> None:
        if not self._drag_moved:
            self._select_station(event.x, event.y)

    def _on_configure(self, event) -> None:
        # 首次获得真实尺寸时自动适配视野；之后仅重绘
        if not self._fitted and event.width > 100 and event.height > 100:
            self._fit_view()
            self._fitted = True
        self.redraw()

    def _on_wheel(self, event) -> None:
        self._zoom_at(event.x, event.y, 1.25 if event.delta > 0 else 0.8)

    def _on_motion(self, event) -> None:
        sid = self._station_at(event.x, event.y)
        if sid == self._hover_sid:
            return
        self._hover_sid = sid
        if sid is not None:
            s = self.graph.get_station(sid)
            lines = sorted({l for (_, _, l) in self.graph.neighbors(sid) if l})
            self.status.set(f"{s.name}（{'、'.join(lines)}）" if lines else s.name)
        else:
            self.status.set("滚轮缩放、按住左键拖拽平移、点击站点选起终点（先起点后终点）。")

    def _select_station(self, x: float, y: float) -> None:
        sid = self._station_at(x, y)
        if sid is None:
            return
        name = self.graph.get_station(sid).name
        if self.pick_start:
            self.start_name.set(name)
            self.pick_start = False
            self.status.set(f"已选起点：{name}，请再点击选择终点。")
        else:
            self.end_name.set(name)
            self.pick_start = True
            self.status.set(f"已选终点：{name}，可点击“搜索路径”。")
        self.redraw()

    def on_search(self) -> None:
        self._cancel_animation()
        start_name, end_name = self.start_name.get(), self.end_name.get()
        if not start_name or not end_name:
            messagebox.showwarning("提示", "请先选择起点和终点。")
            return
        if start_name == end_name:
            messagebox.showinfo("提示", "起点与终点相同，无需搜索。")
            return
        start = self._name_to_id(start_name)
        end = self._name_to_id(end_name)
        if start is None or end is None:
            messagebox.showwarning("提示", "起点或终点不存在，请重新选择。")
            return

        t0 = time.perf_counter()
        result = self.solver.solve(start, end, self.algorithm.get())
        elapsed_ms = (time.perf_counter() - t0) * 1000

        self._current_result = result
        self._show_result(result, elapsed_ms)
        if self.animate.get() and result.success:
            self._animate(result)
        else:
            self.redraw()

    def _show_result(self, result: SearchResult, elapsed_ms: float) -> None:
        self.path_list.delete(0, tk.END)
        if result.success:
            for i, sid in enumerate(result.path, 1):
                self.path_list.insert(tk.END, f"{i:>2}. {self.graph.get_station(sid).name}")
        else:
            self.path_list.insert(tk.END, "（无可达路径）")

        algo_name = Solver.ALGORITHMS[self.algorithm.get()][1]
        info = (f"算法：{algo_name}\n"
                f"程序耗时：{elapsed_ms:.3f} ms\n"
                f"路径权重：{result.total_weight:.2f}\n"
                f"经过站数：{len(result.path)}\n"
                f"扩展节点数：{result.visited_count}\n"
                f"{result.message if result.message else '搜索成功'}\n")
        self.info_text.configure(state=tk.NORMAL)
        self.info_text.delete("1.0", tk.END)
        self.info_text.insert("1.0", info)
        self.info_text.configure(state=tk.DISABLED)

        if result.success:
            names = " → ".join(self.graph.get_station(i).name for i in result.path)
            self.status.set(f"路径：{names}")
        else:
            self.status.set(result.message)

    # ------------------------------------------------------------------ 动画
    def _animate(self, result: SearchResult) -> None:
        """先逐步点亮搜索扩展过的节点，再逐段画出最终路径。"""
        self._cancel_animation()
        self._animating = True
        self.redraw()
        order = result.visit_order
        total = len(order)
        batch = max(1, total // 140)              # 大图时每帧点亮多个节点
        colors = ["#d6eaf8", "#aed6f1", "#85c1e9", "#5dade2"]
        step = max(1, total // 4)
        r = self._station_r()

        def light(i: int):
            if i >= total:
                self._draw_path_stepwise(result, 0)
                return
            for sid in order[i:i + batch]:
                if sid in self.graph.stations:
                    x, y = self._pos(sid)
                    c = colors[min(i // step, len(colors) - 1)]
                    self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=c,
                                            outline="#34495e", width=1, tags="visited")
            self._anim_jobs.append(self.after(16, light, i + batch))

        self._anim_jobs.append(self.after(0, light, 0))

    def _draw_path_stepwise(self, result: SearchResult, i: int) -> None:
        self.canvas.delete("visited")
        if i >= len(result.path) - 1:
            self._animating = False
            self.redraw()
            return
        a, b = result.path[i], result.path[i + 1]
        x1, y1 = self._pos(a)
        x2, y2 = self._pos(b)
        self.canvas.create_line(x1, y1, x2, y2, fill="#c0392b", width=PATH_WIDTH,
                                capstyle=tk.ROUND, joinstyle=tk.ROUND, tags="pathanim")
        delay = max(25, min(150, 2500 // max(1, len(result.path) - 1)))
        self._anim_jobs.append(self.after(delay, self._draw_path_stepwise, result, i + 1))

    def _cancel_animation(self) -> None:
        for job in self._anim_jobs:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self._anim_jobs.clear()
        self._animating = False
        self.canvas.delete("visited")
        self.canvas.delete("pathanim")

    # ------------------------------------------------------------------ 数据管理
    def _reload(self, graph: Graph, path: str = "") -> None:
        self._cancel_animation()
        self.graph = graph
        self.solver = Solver(graph)
        self.data_path = path
        self.line_colors = self._build_line_colors()
        self.start_name.set("")
        self.end_name.set("")
        self.pick_start = True
        self._current_result = None
        self.show_names.set(len(graph.stations) <= LABEL_THRESHOLD)
        self._sync_combobox()
        self._fit_view()
        self.redraw()
        self.status.set(f"已加载 {len(graph)} 个站点、{graph.edge_count()} 条区间。")

    def on_reset_view(self) -> None:
        self._fit_view()
        self.redraw()

    def on_load(self) -> None:
        path = filedialog.askopenfilename(
            title="选择数据文件",
            filetypes=[("数据文件", "*.json *.txt"), ("JSON 文件", "*.json"), ("文本文件", "*.txt")])
        if not path:
            return
        try:
            g = load_graph(path)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("加载失败", f"无法加载文件：\n{e}")
            return
        self._reload(g, path)

    def on_save(self) -> None:
        if not self.graph.stations:
            messagebox.showwarning("提示", "当前没有可保存的数据。")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("JSON 文件", "*.json")])
        if not path:
            return
        try:
            save_json(self.graph, path)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("保存失败", f"{e}")
            return
        messagebox.showinfo("完成", f"已保存到：\n{path}")

    def on_add_station(self) -> None:
        name = simpledialog.askstring("添加站点", "站点名称：", parent=self)
        if not name:
            return
        if self._name_to_id(name) is not None:
            messagebox.showerror("错误", f"站点 {name} 已存在。")
            return
        x = simpledialog.askfloat("添加站点", "横坐标 x（km，东为正）：", parent=self)
        y = simpledialog.askfloat("添加站点", "纵坐标 y（km，北为负）：", parent=self)
        if x is None or y is None:
            return
        self.graph.add_station(Station(self._gen_station_id(), name, x, y))
        self._sync_combobox()
        self.redraw()

    def on_remove_station(self) -> None:
        if not self.graph.stations:
            return
        name = simpledialog.askstring("删除站点", "要删除的站点名称：", parent=self)
        if not name:
            return
        sid = self._name_to_id(name)
        if sid is None:
            messagebox.showerror("错误", "站点不存在。")
            return
        self.graph.remove_station(sid)
        if self.start_name.get() == name:
            self.start_name.set("")
        if self.end_name.get() == name:
            self.end_name.set("")
        self._sync_combobox()
        self.redraw()

    def on_add_edge(self) -> None:
        na = simpledialog.askstring("添加区间", "起点名称：", parent=self)
        nb = simpledialog.askstring("添加区间", "终点名称：", parent=self)
        w = simpledialog.askfloat("添加区间", "距离权重：", parent=self)
        line = simpledialog.askstring("添加区间", "线路名：", parent=self) or ""
        if not na or not nb or w is None:
            return
        a, b = self._name_to_id(na), self._name_to_id(nb)
        if a is None or b is None:
            messagebox.showerror("错误", "起点或终点名称不存在。")
            return
        try:
            self.graph.add_edge(a, b, w, line)
        except ValueError as e:
            messagebox.showerror("错误", str(e))
            return
        self.line_colors = self._build_line_colors()
        self.redraw()

    def _sync_combobox(self) -> None:
        names = sorted(s.name for s in self.graph.stations.values())
        for box in (self.start_box, self.end_box):
            box["values"] = names
        if self.start_name.get() and self._name_to_id(self.start_name.get()) is None:
            self.start_name.set("")
        if self.end_name.get() and self._name_to_id(self.end_name.get()) is None:
            self.end_name.set("")
