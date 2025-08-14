"""
Common geometry utilities for Stealth Golf.
"""

from __future__ import annotations

from typing import Iterable, Tuple, Optional


def clamp(v: float, lo: float, hi: float) -> float:
    """Clamp *v* to the inclusive range [lo, hi]."""
    return lo if v < lo else hi if v > hi else v


def length(vx: float, vy: float) -> float:
    """Return the Euclidean length of a 2-D vector."""
    return (vx * vx + vy * vy) ** 0.5


def normalize(vx: float, vy: float) -> Tuple[float, float]:
    """Return the unit vector of (vx, vy) or (0, 0) if zero length."""
    l = length(vx, vy)
    return (0.0, 0.0) if l == 0 else (vx / l, vy / l)


def seg_intersect(p1: Tuple[float, float], p2: Tuple[float, float],
                  p3: Tuple[float, float], p4: Tuple[float, float]) -> Tuple[bool, float, float, float, float]:
    """Return intersection data for segment p1-p2 with segment p3-p4."""
    x1, y1 = p1; x2, y2 = p2; x3, y3 = p3; x4, y4 = p4
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-9:
        return (False, 0, 0, 0, 0)
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    u = ((x1 - x3) * (y1 - y2) - (y1 - y3) * (x1 - x2)) / den
    if 0 <= t <= 1 and 0 <= u <= 1:
        ix = x1 + t * (x2 - x1); iy = y1 + t * (y2 - y1)
        return (True, t, u, ix, iy)
    return (False, 0, 0, 0, 0)


def ray_rect_nearest_hit(ox: float, oy: float, dirx: float, diry: float,
                         rect: Tuple[float, float, float, float]) -> Optional[Tuple[float, float]]:
    """Return nearest hit point of a ray and axis-aligned rectangle or ``None``."""
    rx, ry, rw, rh = rect
    farx = ox + dirx * 99999
    fary = oy + diry * 99999
    best_t = None
    best_pt = None
    edges = [
        ((rx, ry), (rx + rw, ry)),
        ((rx + rw, ry), (rx + rw, ry + rh)),
        ((rx + rw, ry + rh), (rx, ry + rh)),
        ((rx, ry + rh), (rx, ry)),
    ]
    for a, b in edges:
        hit, t, u, ix, iy = seg_intersect((ox, oy), (farx, fary), a, b)
        if hit and (best_t is None or t < best_t):
            best_t = t
            best_pt = (ix, iy)
    return best_pt


def los_blocked(ox: float, oy: float, tx: float, ty: float,
                walls: Iterable[Tuple[float, float, float, float]]) -> bool:
    """Return ``True`` if line of sight from (ox, oy) to (tx, ty) is blocked."""
    for rx, ry, rw, rh in walls:
        edges = [
            ((rx, ry), (rx + rw, ry)),
            ((rx + rw, ry), (rx + rw, ry + rh)),
            ((rx + rw, ry + rh), (rx, ry + rh)),
            ((rx, ry + rh), (rx, ry)),
        ]
        for a, b in edges:
            hit, t, u, ix, iy = seg_intersect((ox, oy), (tx, ty), a, b)
            if hit and 0 < t < 1 - 1e-6:
                return True
    return False
