import math
import pygame

# --------------------------- Utility functions ---------------------------

def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

def length(vx, vy):
    return math.hypot(vx, vy)

def normalize(vx, vy):
    l = length(vx, vy)
    return (0.0, 0.0) if l == 0 else (vx / l, vy / l)

# --------------------------- Level definitions --------------------------

# Simplified level data extracted from the original JSON files. Each level
# provides the world size, starting ball position, hole position and a list of
# rectangular wall colliders.
LEVELS = [
    {
        "world": (1400, 2200),
        "start": (900, 440),
        "hole": (960, 500, 22),
        "walls": [
            (280, 160, 100, 540),
            (400, 600, 600, 100),
            (380, 600, 20, 100),
            (520, 220, 60, 380),
            (280, 40, 100, 120),
            (380, 40, 660, 80),
            (1040, 40, 80, 660),
            (1000, 600, 40, 100),
            (280, 700, 840, 20),
            (280, 0, 840, 40),
            (1120, 0, 20, 720),
        ],
    },
    {
        "world": (1400, 2200),
        "start": (1140, 1840),
        "hole": (560, 1840, 22),
        "walls": [
            (480, 1920, 780, 80),
            (420, 1700, 60, 300),
            (500, 1680, 700, 60),
            (420, 1680, 80, 60),
            (1200, 1680, 60, 240),
        ],
    },
    {
        "world": (1400, 2200),
        "start": (580, 380),
        "hole": (940, 860, 22),
        "walls": [
            (80, 580, 100, 440),
            (80, 260, 80, 20),
            (100, 320, 80, 260),
            (80, 300, 20, 280),
            (80, 180, 100, 160),
            (80, 100, 560, 80),
            (500, 440, 20, 180),
            (380, 580, 280, 80),
            (680, 100, 20, 380),
            (640, 100, 120, 80),
            (680, 100, 100, 560),
            (660, 580, 20, 80),
            (360, 580, 20, 80),
            (740, 100, 20, 520),
            (680, 660, 100, 120),
            (680, 940, 100, 160),
            (80, 1020, 100, 180),
            (600, 1100, 180, 100),
            (100, 1100, 520, 100),
            (780, 1160, 340, 40),
            (780, 1100, 340, 60),
            (780, 580, 340, 80),
            (1020, 660, 100, 440),
        ],
    },
    {
        "world": (1400, 2200),
        "start": (240, 220),
        "hole": (260, 1000, 22),
        "walls": [
            (60, 200, 60, 900),
            (60, 120, 340, 80),
            (400, 120, 60, 440),
            (400, 620, 60, 340),
            (400, 1020, 60, 80),
            (60, 1100, 400, 80),
            (440, 620, 40, 340),
            (460, 1020, 100, 20),
            (460, 540, 100, 20),
            (540, 560, 20, 460),
        ],
    },
]


def load_level(index):
    data = LEVELS[index % len(LEVELS)]
    world_w, world_h = data["world"]
    start = data["start"]
    hole = data["hole"]
    walls = data["walls"]
    return world_w, world_h, start, hole, walls

# ------------------------------ Game Objects ----------------------------

class Ball:
    def __init__(self, x, y, r=14):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.r = r
        self.in_motion = False

    def apply_impulse(self, ix, iy):
        self.vx += ix
        self.vy += iy
        if ix or iy:
            self.in_motion = True

    def update(self, dt, colliders):
        self.x += self.vx * dt
        self.y += self.vy * dt

        for rx, ry, rw, rh in colliders:
            cx, cy, r = self.x, self.y, self.r
            closest_x = clamp(cx, rx, rx + rw)
            closest_y = clamp(cy, ry, ry + rh)
            dx = cx - closest_x
            dy = cy - closest_y
            d2 = dx * dx + dy * dy
            if d2 < r * r:
                d = math.sqrt(d2) if d2 > 0 else 0
                if d == 0:
                    nx, ny = 0, -1
                    push = r
                else:
                    nx, ny = dx / d, dy / d
                    push = r - d
                self.x += nx * push
                self.y += ny * push
                vn = self.vx * nx + self.vy * ny
                if vn < 0:
                    self.vx -= 1.8 * vn * nx
                    self.vy -= 1.8 * vn * ny

        speed = length(self.vx, self.vy)
        if speed < 5:
            self.vx = self.vy = 0.0
            self.in_motion = False
        else:
            fric = 0.985
            self.vx *= fric
            self.vy *= fric

# ------------------------------ Main game -------------------------------

def main():
    level_index = 0
    world_w, world_h, start, hole, walls = load_level(level_index)

    pygame.init()
    view_size = (480, 800)
    screen = pygame.display.set_mode(view_size)
    pygame.display.set_caption("Stealth Golf (pygame)")
    clock = pygame.time.Clock()

    ball = Ball(*start)
    aiming = False
    aim_start = (0, 0)
    aim_current = (0, 0)
    win = False

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif win and event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                level_index = (level_index + 1) % len(LEVELS)
                world_w, world_h, start, hole, walls = load_level(level_index)
                ball = Ball(*start)
                win = False
            elif (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and not ball.in_motion
                and not win
            ):
                aiming = True
                ax, ay = event.pos
                cam_x = clamp(ball.x - view_size[0] / 2, 0, world_w - view_size[0])
                cam_y = clamp(ball.y - view_size[1] / 2, 0, world_h - view_size[1])
                aim_start = (ax + cam_x, ay + cam_y)
                aim_current = aim_start
            elif event.type == pygame.MOUSEMOTION and aiming:
                mx, my = event.pos
                cam_x = clamp(ball.x - view_size[0] / 2, 0, world_w - view_size[0])
                cam_y = clamp(ball.y - view_size[1] / 2, 0, world_h - view_size[1])
                aim_current = (mx + cam_x, my + cam_y)
            elif (
                event.type == pygame.MOUSEBUTTONUP
                and event.button == 1
                and aiming
            ):
                aiming = False
                mx, my = event.pos
                cam_x = clamp(ball.x - view_size[0] / 2, 0, world_w - view_size[0])
                cam_y = clamp(ball.y - view_size[1] / 2, 0, world_h - view_size[1])
                end = (mx + cam_x, my + cam_y)
                ix = (aim_start[0] - end[0]) * 3.0
                iy = (aim_start[1] - end[1]) * 3.0
                ball.apply_impulse(ix, iy)

        ball.update(dt, walls)

        if length(ball.x - hole[0], ball.y - hole[1]) <= ball.r + hole[2]:
            win = True

        cam_x = clamp(ball.x - view_size[0] / 2, 0, world_w - view_size[0])
        cam_y = clamp(ball.y - view_size[1] / 2, 0, world_h - view_size[1])

        screen.fill((20, 20, 20))

        for rx, ry, rw, rh in walls:
            pygame.draw.rect(screen, (70, 70, 70), pygame.Rect(rx - cam_x, ry - cam_y, rw, rh))

        pygame.draw.circle(screen, (40, 160, 40), (int(hole[0] - cam_x), int(hole[1] - cam_y)), hole[2])
        pygame.draw.circle(screen, (230, 230, 230), (int(ball.x - cam_x), int(ball.y - cam_y)), ball.r)

        if aiming:
            pygame.draw.line(
                screen,
                (255, 0, 0),
                (aim_start[0] - cam_x, aim_start[1] - cam_y),
                (aim_current[0] - cam_x, aim_current[1] - cam_y),
                2,
            )

        if win:
            font = pygame.font.SysFont(None, 48)
            text = font.render("You win!", True, (255, 255, 255))
            rect = text.get_rect(center=(view_size[0] // 2, view_size[1] // 2))
            screen.blit(text, rect)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
