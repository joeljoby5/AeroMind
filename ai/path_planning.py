"""A* path planning on a 2D occupancy grid built from a local metric projection of lat/lon.

* ~10 m cells, 8-connected moves, octile-distance heuristic, no diagonal corner-cutting.
* Obstacles are circles inflated by a safety radius before being rasterised.
* The raw cell path is smoothed: collinear points are dropped and line-of-sight shortcuts are taken
  wherever the straight segment still clears every inflated obstacle (removes the grid staircase).
* Returns ``PathResult(path=None, reason=...)`` when no route exists.

If the straight line start -> goal clears every inflated obstacle, that line is returned directly
(it is what A* would converge to, without the grid staircase).
"""
from __future__ import annotations

import heapq
import math
from collections.abc import Sequence

import numpy as np

from ai.geo import LocalFrame
from ai.types import Obstacle, PathResult

SQRT2 = math.sqrt(2.0)
_MOVES = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
          (1, 1, SQRT2), (1, -1, SQRT2), (-1, 1, SQRT2), (-1, -1, SQRT2)]


def _segment_clear(a, b, circles, safety) -> bool:
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    seg_sq = vx * vx + vy * vy
    for cx, cy, r in circles:
        t = 0.0 if seg_sq == 0 else max(0.0, min(1.0, ((cx - ax) * vx + (cy - ay) * vy) / seg_sq))
        if math.hypot(ax + t * vx - cx, ay + t * vy - cy) < r + safety:
            return False
    return True


def _los_clear(a, b, circles, safety) -> bool:
    """Segment a->b keeps the required clearance from every obstacle. An endpoint already inside an
    obstacle's safety ring may only move away from it (clearance never drops below its own)."""
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    seg_sq = vx * vx + vy * vy
    for cx, cy, r in circles:
        need = min(r + safety, math.hypot(ax - cx, ay - cy) - 1e-6, math.hypot(bx - cx, by - cy) - 1e-6)
        t = 0.0 if seg_sq == 0 else max(0.0, min(1.0, ((cx - ax) * vx + (cy - ay) * vy) / seg_sq))
        if math.hypot(ax + t * vx - cx, ay + t * vy - cy) < need:
            return False
    return True


def _shortcut(pts, circles, safety):
    """Greedy string-pulling: from each anchor jump to the farthest visible point."""
    out, i = [pts[0]], 0
    while i < len(pts) - 1:
        j = len(pts) - 1
        while j > i + 1 and not _los_clear(pts[i], pts[j], circles, safety):
            j -= 1
        out.append(pts[j])
        i = j
    return out


def _remove_collinear(cells: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if len(cells) <= 2:
        return cells
    out = [cells[0]]
    for prev, cur, nxt in zip(cells, cells[1:], cells[2:]):
        if (cur[0] - prev[0], cur[1] - prev[1]) != (nxt[0] - cur[0], nxt[1] - cur[1]):
            out.append(cur)
    out.append(cells[-1])
    return out


class AStarPlanner:
    """`PathPlanner` implementation."""

    def __init__(self, cell_m: float = 10.0, safety_m: float = 12.0, max_cells: int = 600) -> None:
        self.cell_m, self.safety_m, self.max_cells = cell_m, safety_m, max_cells

    def plan(
        self,
        start: tuple[float, float],
        goal: tuple[float, float],
        obstacles: Sequence[Obstacle],
    ) -> PathResult:
        cell, safety = self.cell_m, self.safety_m
        frame = LocalFrame(*start)  # start is the local origin and sits on the cell lattice
        gx, gy = frame.to_xy(*goal)
        circles = [(*frame.to_xy(o.lat, o.lon), o.radius_m) for o in obstacles]

        if math.hypot(gx, gy) < 1e-6:
            return PathResult([start], "ok", 0.0)
        for cx, cy, r in circles:
            if math.hypot(cx, cy) <= r:
                return PathResult(None, "start position is inside an obstacle")
            if math.hypot(gx - cx, gy - cy) <= r:
                return PathResult(None, "goal is inside an obstacle")
        if _segment_clear((0.0, 0.0), (gx, gy), circles, safety):
            return PathResult([start, goal], "ok", math.hypot(gx, gy))

        # ---- build the grid (bounding box of start/goal + a detour margin) ----
        margin = 2 * max([r + safety for _, _, r in circles] + [safety]) + 6 * cell
        xmin = math.floor((min(0.0, gx) - margin) / cell) * cell
        ymin = math.floor((min(0.0, gy) - margin) / cell) * cell
        nx = int(math.ceil((max(0.0, gx) + margin - xmin) / cell)) + 1
        ny = int(math.ceil((max(0.0, gy) + margin - ymin) / cell)) + 1
        if nx > self.max_cells or ny > self.max_cells:
            return PathResult(None, "planning area too large")
        xs = xmin + np.arange(nx) * cell
        ys = ymin + np.arange(ny) * cell
        gxx, gyy = np.meshgrid(xs, ys, indexing="ij")  # shape (nx, ny)

        blocked = np.zeros((nx, ny), dtype=bool)
        body = np.zeros((nx, ny), dtype=bool)
        for cx, cy, r in circles:
            d = np.hypot(gxx - cx, gyy - cy)
            blocked |= d <= r + safety
            body |= d <= r

        def to_idx(x: float, y: float) -> tuple[int, int]:
            return (min(max(int(round((x - xmin) / cell)), 0), nx - 1),
                    min(max(int(round((y - ymin) / cell)), 0), ny - 1))

        start_i, goal_i = to_idx(0.0, 0.0), to_idx(gx, gy)
        # Endpoints may sit inside the safety ring (not the obstacle itself): open an escape zone.
        for px, py in ((0.0, 0.0), (gx, gy)):
            near = np.hypot(gxx - px, gyy - py) <= safety + 2 * cell
            blocked &= ~(near & ~body)
        if blocked[start_i] or blocked[goal_i]:
            return PathResult(None, "start or goal is blocked by an obstacle")

        # ---- A* ----
        def h(i: int, j: int) -> float:
            dx, dy = abs(i - goal_i[0]), abs(j - goal_i[1])
            return (dx + dy) + (SQRT2 - 2.0) * min(dx, dy)

        g_cost = {start_i: 0.0}
        parent: dict[tuple[int, int], tuple[int, int]] = {}
        heap = [(h(*start_i), 0.0, start_i)]
        closed = set()
        found = False
        while heap:
            _, g, cur = heapq.heappop(heap)
            if cur in closed:
                continue
            if cur == goal_i:
                found = True
                break
            closed.add(cur)
            ci, cj = cur
            for di, dj, step in _MOVES:
                ni, nj = ci + di, cj + dj
                if not (0 <= ni < nx and 0 <= nj < ny) or blocked[ni, nj] or (ni, nj) in closed:
                    continue
                if di and dj and (blocked[ci + di, cj] or blocked[ci, cj + dj]):
                    continue  # no cutting corners
                ng = g + step
                if ng < g_cost.get((ni, nj), math.inf):
                    g_cost[(ni, nj)] = ng
                    parent[(ni, nj)] = cur
                    heapq.heappush(heap, (ng + h(ni, nj), ng, (ni, nj)))
        if not found:
            return PathResult(None, "no route: obstacles block every path to the goal")

        cells = [goal_i]
        while cells[-1] != start_i:
            cells.append(parent[cells[-1]])
        cells.reverse()
        cells = _remove_collinear(cells)

        pts = [(xmin + i * cell, ymin + j * cell) for i, j in cells]
        pts[0], pts[-1] = (0.0, 0.0), (gx, gy)  # exact endpoints
        pts = _shortcut(pts, circles, safety)
        length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
        path = [start] + [frame.to_latlon(x, y) for x, y in pts[1:-1]] + [goal]
        return PathResult(path, "ok", length)


def plan_path(start, goal, obstacles: Sequence[Obstacle] = (), **kwargs) -> PathResult:
    return AStarPlanner(**kwargs).plan(start, goal, obstacles)
