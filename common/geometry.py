
# Minimal geometry helpers auto-installed by Stealth Golf

def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

def length(vx, vy):
    return (vx * vx + vy * vy) ** 0.5

def normalize(vx, vy):
    l = length(vx, vy)
    return (0.0, 0.0) if l == 0 else (vx / l, vy / l)

def seg_intersect(p1, p2, p3, p4):
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

def ray_rect_nearest_hit(ox, oy, dirx, diry, rect):
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

def los_blocked(ox, oy, tx, ty, walls):
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
