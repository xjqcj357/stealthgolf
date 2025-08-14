# stealth_golf_kivy_loadlevel.py
# Game variant that loads a level from JSON (level.json) if present; otherwise falls back to built-in level.
# Place your JSON next to this script as "level.json" (or modify LEVEL_PATH).
#
import json, os
from math import sin, cos, atan2, sqrt, radians, pi
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Rectangle, Line, Triangle, PushMatrix, PopMatrix, Translate, Mesh
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from common.geometry import (
    clamp,
    length,
    normalize,
    seg_intersect,
    ray_rect_nearest_hit,
    los_blocked,
)

LEVEL_PATH = "level.json"  # change to your file name if desired

try:
    Window.size = (480, 800)
except Exception:
    pass

class Ball:
    def __init__(self, x, y, r=14):
        self.x, self.y = x, y
        self.vx, self.vy = 0.0, 0.0
        self.r = r
        self.color = (0.95, 0.95, 0.95)
        self.smoke_timer = 0.0
        self.in_motion = False
    def apply_impulse(self, ix, iy):
        self.vx += ix; self.vy += iy; self.in_motion = True
    def update(self, dt, walls):
        self.x += self.vx * dt; self.y += self.vy * dt
        # collisions
        for rx, ry, rw, rh in walls:
            cx, cy, r = self.x, self.y, self.r
            closest_x = clamp(cx, rx, rx + rw)
            closest_y = clamp(cy, ry, ry + rh)
            dx = cx - closest_x; dy = cy - closest_y
            d2 = dx*dx + dy*dy
            if d2 < r*r:
                d = d2 ** 0.5 if d2 > 0 else 0.0
                if d == 0.0:
                    left = abs(cx - rx); right = abs((rx + rw) - cx)
                    bottom = abs(cy - ry); top = abs((ry + rh) - cy)
                    m = min(left, right, bottom, top)
                    px, py = (-(r),0) if m==left else ((r),0) if m==right else (0, -(r)) if m==bottom else (0, r)
                else:
                    nx, ny = dx/d, dy/d
                    push = r - d
                    px, py = nx*push, ny*push
                self.x += px; self.y += py
                if d2 > 0:
                    nx, ny = normalize(px, py)
                    vn = self.vx*nx + self.vy*ny
                    if vn < 0:
                        self.vx -= 1.8 * vn * nx
                        self.vy -= 1.8 * vn * ny
        speed = length(self.vx, self.vy)
        if speed < 5:
            self.vx = self.vy = 0.0; self.in_motion = False
        else:
            fric = 0.985; self.vx *= fric; self.vy *= fric
        if self.smoke_timer > 0:
            self.smoke_timer = max(0.0, self.smoke_timer - dt)

class Agent:
    def __init__(self, ax, ay, bx, by, speed=70, fov_deg=55, cone_len=220):
        self.ax, self.ay = ax, ay
        self.bx, self.by = bx, by
        self.x, self.y = ax, ay
        self.dir = 1
        self.patrol_speed = speed
        self.chase_speed = speed * 1.35
        self.fov_half = radians(fov_deg/2.0)
        self.cone_len = cone_len
        self.look_dirx, self.look_diry = normalize(bx-ax, by-ay)
        self.chasing = False
        self.ray_steps = 64
    def _angle_dir(self):
        from math import atan2
        return atan2(self.look_diry, self.look_dirx)
    def update(self, dt, ball, walls):
        from math import cos
        hidden = ball.smoke_timer > 0.0
        ball_visible = False
        if not hidden:
            dx, dy = (ball.x - self.x, ball.y - self.y)
            dist = length(dx, dy)
            if dist <= self.cone_len:
                vxn, vyn = normalize(dx, dy)
                ang_ok = (vxn*self.look_dirx + vyn*self.look_diry) >= cos(self.fov_half + 1e-6)
                if ang_ok and not los_blocked(self.x, self.y, ball.x, ball.y, walls):
                    ball_visible = True
        self.chasing = ball_visible
        if self.chasing:
            vx, vy = ball.x - self.x, ball.y - self.y
            dist = length(vx, vy)
            if dist > 1e-3:
                vxn, vyn = vx/dist, vy/dist
                self.x += vxn * self.chase_speed * dt
                self.y += vyn * self.chase_speed * dt
                self.look_dirx, self.look_diry = vxn, vyn
        else:
            tx = self.bx if self.dir > 0 else self.ax
            ty = self.by if self.dir > 0 else self.ay
            vx, vy = tx - self.x, ty - self.y
            dist = length(vx, vy)
            step = self.patrol_speed * dt
            if dist <= step:
                self.x, self.y = tx, ty; self.dir *= -1
                if self.dir > 0:
                    self.look_dirx, self.look_diry = normalize(self.bx-self.ax, self.by-self.ay)
                else:
                    self.look_dirx, self.look_diry = normalize(self.ax-self.bx, self.ay-self.by)
            else:
                vxn, vyn = (vx/dist, vy/dist) if dist else (0, 0)
                self.x += vxn * step; self.y += vyn * step
                self.look_dirx, self.look_diry = vxn, vyn
        return length(ball.x - self.x, ball.y - self.y) <= (ball.r + 10)
    def compute_flashlight_polygon(self, walls):
        from math import cos, sin
        base_ang = self._angle_dir()
        start_ang = base_ang + self.fov_half
        end_ang   = base_ang - self.fov_half
        pts = []
        for i in range(self.ray_steps + 1):
            t = i / float(self.ray_steps)
            ang = start_ang + (end_ang - start_ang) * t
            dx, dy = cos(ang), sin(ang)
            hit_pt = None; nearest_d2 = None
            tx = self.x + dx * self.cone_len; ty = self.y + dy * self.cone_len
            for rect in walls:
                pt = ray_rect_nearest_hit(self.x, self.y, dx, dy, rect)
                if pt is not None:
                    d2 = (pt[0] - self.x)**2 + (pt[1] - self.y)**2
                    if nearest_d2 is None or d2 < nearest_d2:
                        nearest_d2 = d2; hit_pt = pt
            if hit_pt is None:
                pts.append((tx, ty))
            else:
                if nearest_d2 is not None and nearest_d2 > (self.cone_len*self.cone_len):
                    pts.append((tx, ty))
                else:
                    pts.append(hit_pt)
        return pts

class StealthGolf(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.view_w, self.view_h = Window.size
        # Load or fallback
        if os.path.exists(LEVEL_PATH):
            with open(LEVEL_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = self._fallback_level()
        self.world_w = int(data.get("world",{}).get("w", 1400))
        self.world_h = int(data.get("world",{}).get("h", 2200))
        self.walls = [tuple(r) for r in data.get("walls",[])]
        self.decor = list(data.get("decor", []))
        self.start_pos = tuple(data.get("start", [240,220]))
        hole = data.get("hole", {"cx":1240,"cy":2020,"r":22})
        self.hole = (int(hole["cx"]), int(hole["cy"]), int(hole.get("r",22)))
        self.ball = Ball(*self.start_pos)
        self.agents = [Agent(a["a"][0],a["a"][1], a["b"][0],a["b"][1],
                             speed=a.get("speed",80),
                             fov_deg=a.get("fov_deg",60),
                             cone_len=a.get("cone_len",260)) for a in data.get("agents", [])]

        # Input/aim
        self.aiming=False; self.aim_touch_id=None
        self.aim_start=(0,0); self.aim_current=(0,0)
        self.max_shot=1000.0; self.mode_idx=0; self.modes=["Normal","Smoke"]
        self.caught=False; self.win=False; self.message_timer=0.0
        self.drop_total=1.2; self.drop_timer=0.0

        Clock.schedule_interval(self.update, 1.0/60.0)

    def _fallback_level(self):
        # Minimal empty level if no file found
        return {"world":{"w":1400,"h":2200},
                "start":[240,220],
                "hole":{"cx":1240,"cy":2020,"r":22},
                "walls":[(0,0,1400,40),(0,0,40,2200),(1360,0,40,2200),(0,2160,1400,40)],
                "decor":[],
                "agents":[{"a":[300,600],"b":[1000,600],"speed":90}]}

    # Input
    def on_touch_down(self, touch):
        if self.caught or self.win:
            if not self.win or (self.win and self.drop_timer <= 0):
                self._reset_to_start()
            return True
        if touch.x > self.width - 140 and touch.y > self.height - 80:
            self.mode_idx = (self.mode_idx + 1) % len(self.modes); return True
        wx, wy = self.screen_to_world(touch.x, touch.y)
        if length(wx - self.ball.x, wy - self.ball.y) <= self.ball.r + 36 and not self.ball.in_motion:
            self.aiming=True; self.aim_touch_id=touch.uid; self.aim_start=(wx,wy); self.aim_current=(wx,wy); return True
        return False
    def on_touch_move(self, touch):
        if self.aiming and touch.uid == self.aim_touch_id:
            wx, wy = self.screen_to_world(touch.x, touch.y); self.aim_current=(wx,wy); return True
        return False
    def on_touch_up(self, touch):
        if self.aiming and touch.uid == self.aim_touch_id:
            sx, sy = self.aim_start; cx, cy = self.aim_current
            ix, iy = (sx - cx), (sy - cy)
            power = length(ix, iy)
            if power > self.max_shot:
                ix, iy = normalize(ix, iy); ix*=self.max_shot; iy*=self.max_shot
            scale = 1.90  # 2x-powered swing
            self.ball.apply_impulse(ix*scale, iy*scale)
            if self.modes[self.mode_idx] == "Smoke":
                self.ball.smoke_timer = 2.6
            self.aiming=False; self.aim_touch_id=None; return True
        return False

    def update(self, dt):
        if self.drop_timer > 0:
            self.drop_timer = max(0.0, self.drop_timer - dt)
            if self.drop_timer == 0.0: self._next_level()
        else:
            self.ball.update(dt, self.walls)
            for a in self.agents:
                caught = a.update(dt, self.ball, self.walls)
                if caught and not self.win:
                    self.caught = True; self.message_timer = 2.5
            # hole
            cx, cy, hr = self.hole
            if not self.win and length(self.ball.x - cx, self.ball.y - cy) <= (hr - 2):
                self.win = True; self.drop_timer = self.drop_total; self.message_timer = 2.0
                self.ball.vx = self.ball.vy = 0.0; self.ball.in_motion = False
        self._update_camera(); self.draw()

    def _update_camera(self):
        bx, by = self.ball.x, self.ball.y
        desired_cx = bx - self.width*0.5
        desired_cy = by - self.height*0.28
        self.cam_x = clamp(desired_cx, 0, self.world_w - self.width)
        self.cam_y = clamp(desired_cy, 0, self.world_h - self.height)
    def screen_to_world(self, sx, sy): return (sx + self.cam_x, sy + self.cam_y)

    def draw(self):
        self.canvas.clear()
        with self.canvas:
            PushMatrix(); Translate(-self.cam_x, -self.cam_y, 0)
            # BG
            Color(0.08,0.09,0.11,1); Rectangle(pos=(0,0), size=(self.world_w, self.world_h))
            # Grid
            Color(0.12,0.13,0.16,1); grid=60
            for x in range(0, self.world_w, grid): Rectangle(pos=(x,0), size=(2,self.world_h))
            for y in range(0, self.world_h, grid): Rectangle(pos=(0,y), size=(self.world_w,2))
            # Decor
            for d in self.decor:
                kind = d.get("kind","")
                rx,ry,rw,rh = d.get("rect",[0,0,0,0])
                if kind=="elevator":
                    Color(0.18,0.2,0.24,1); Rectangle(pos=(rx,ry), size=(rw,rh))
                    Color(0.26,0.28,0.32,1); Rectangle(pos=(rx + rw/2 - 2, ry + 10), size=(4, rh - 20))
                elif kind=="rug":
                    Color(0.13,0.25,0.18,0.6); Rectangle(pos=(rx,ry), size=(rw,rh))
            # Walls
            Color(0.25,0.28,0.33,1)
            for rx,ry,rw,rh in self.walls: Rectangle(pos=(rx,ry), size=(rw,rh))
            # Lights (occluded)
            for a in self.agents:
                pts = a.compute_flashlight_polygon(self.walls)
                verts=[(a.x,a.y,0,0)] + [(x,y,0,0) for (x,y) in pts]
                idx=[]; 
                for i in range(1,len(verts)-1): idx.extend([0,i,i+1])
                Color(1,1,0.65, 0.18 if not a.chasing else 0.35)
                Mesh(vertices=sum(([vx,vy,0,0] for vx,vy,_,_ in verts), []), indices=idx, mode='triangles')
            # Agents
            for a in self.agents:
                Color(0.9,0.2,0.2, 1.0 if not a.chasing else 0.9)
                Rectangle(pos=(a.x-8,a.y-8), size=(16,16))
            # Hole
            cx,cy,hr=self.hole
            Color(0.1,0.5,0.15,1); Ellipse(pos=(cx-(hr+6), cy-(hr+6)), size=((hr+6)*2,(hr+6)*2))
            Color(0.02,0.02,0.02,1); Ellipse(pos=(cx-hr, cy-hr), size=(hr*2,hr*2))
            # Ball
            Color(*((0.35,0.35,0.38,1) if self.ball.smoke_timer>0 else (0.95,0.95,0.95,1)))
            Ellipse(pos=(self.ball.x-14, self.ball.y-14), size=(28,28))
            # Aim line
            if self.aiming:
                sx, sy = self.aim_start; cx2, cy2 = self.aim_current
                Color(0.9,0.9,1.0,0.7); Line(points=[self.ball.x,self.ball.y,cx2,cy2], width=2)
            PopMatrix()
            # UI overlay
            Color(0.18,0.18,0.2,0.8); Rectangle(pos=(self.width - 140, self.height - 60), size=(130, 48))
            Color(1,1,1,1); Line(rectangle=(self.width - 140, self.height - 60, 130, 48), width=1.2)

        self._labels()

    def _labels(self):
        if not hasattr(self, "mode_label"):
            self.mode_label = Label(text="", font_size=16, color=(1,1,1,1), size_hint=(None,None), size=(120,30), pos=(self.width - 132, self.height - 50))
            self.add_widget(self.mode_label)
        self.mode_label.text = "Mode: [b]{}[/b]".format(["Normal","Smoke"][self.mode_idx]); self.mode_label.markup=True
        if not hasattr(self, "banner"):
            self.banner = Label(text="", font_size=20, color=(1,1,1,1), size_hint=(None,None), size=(self.width,40), pos=(10, self.height - 90))
            self.add_widget(self.banner)
        if self.caught and self.message_timer > 0:
            self.banner.text = "[b]Caught![/b] Tap to restart."; self.banner.markup=True
            self.message_timer = max(0.0, self.message_timer - 1/60)
        elif self.win and self.drop_timer > 0:
            self.banner.text = "Dropping to next level..."; self.banner.markup=True
        elif self.win and self.drop_timer <= 0 and self.message_timer > 0:
            self.banner.text = "[b]Level complete![/b] (Next level WIP) • Tap to restart."; self.banner.markup=True
            self.message_timer = max(0.0, self.message_timer - 1/60)
        else:
            self.banner.text = ""

    def _reset_to_start(self):
        self.ball.x, self.ball.y = self.start_pos
        self.ball.vx = self.ball.vy = 0.0
        self.ball.smoke_timer = 0.0
        self.caught = False; self.win=False; self.drop_timer=0.0; self.message_timer=0.0
        for a in self.agents:
            a.x,a.y = a.ax,a.ay; a.dir=1; a.chasing=False; a.look_dirx, a.look_diry = normalize(a.bx-a.ax, a.by-a.ay)

    def _next_level(self):
        self.drop_timer = 0.0; self.message_timer = 3.0

class StealthGolfApp(App):
    def build(self):
        return StealthGolf()

if __name__ == "__main__":
    StealthGolfApp().run()
