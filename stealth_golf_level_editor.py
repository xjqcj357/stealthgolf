# stealth_golf_level_editor.py
# Kivy Level Editor (toolbar fix + keyboard shortcuts)
# - Always-visible toolbar using BoxLayout at the top (no manual positioning).
# - Keyboard shortcuts for rapid editing.
# - Door placement uses a two-step workflow: first drag out the door, then
#   drag a touchscreen area. A color picker lets you set the door color.
# - Same JSON schema as before (now extended with "doors"); compatible with
#   the loader game.
#
from math import cos, sin, atan2, sqrt, radians
import json, os
from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Ellipse, Line, PushMatrix, PopMatrix, Translate, Mesh
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.spinner import Spinner
from common.geometry import length, normalize, seg_intersect, ray_rect_nearest_hit

try:
    Window.size = (900, 1000)  # larger editor window
except Exception:
    pass

GRID = 20

def snap(v): return int(round(v / GRID)) * GRID

def floor_label(idx):
    return f"F{idx+1}" if idx >= 0 else f"B{-idx}"

def label_to_floor_index(label):
    if label.startswith("F") and label[1:].isdigit():
        return int(label[1:]) - 1
    if label.startswith("B") and label[1:].isdigit():
        return -int(label[1:])
    return 0

COLOR_MAP = {
    "red":   (0.8,0.0,0.0),
    "green": (0.0,0.6,0.0),
    "blue":  (0.0,0.0,0.8),
    "yellow":(0.8,0.8,0.0),
    "white": (1.0,1.0,1.0),
    "black": (0.0,0.0,0.0),
    "brown": (0.55,0.27,0.07),
}

# Scenery tool names and mapping to stored "kind" strings
SCENERY_KIND_MAP = {
    "Elevator": "elevator",
    "Rug": "rug",
    "Vent": "vent",
    "Plant": "plant",
    "Desk": "desk",
    "Chair": "chair",
    "Table": "table",
    "BlueScreen": "blue_screen_monitor",
}
SCENERY_TOOLS = tuple(SCENERY_KIND_MAP.keys())

class LevelCanvas(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # World
        self.world_w, self.world_h = 1400, 2200
        # Camera
        self.cam_x, self.cam_y = 0, 0
        # Data
        self.walls = []
        self.decor = []  # [{"kind":..., "rect":[x,y,w,h]}]
        self.agents = [] # [{"a":[x,y], "b":[x,y], "speed":..., "fov_deg":..., "cone_len":...}]
        self.doors = []  # [{"rect":..., "screen":..., "color":...}]
        self.floors = [self._new_floor()]
        self.current_floor = 0
        self._refresh_floor_refs()
        self.start = [240, 220]
        self.start_floor = 0
        self.hole = {"cx":1240, "cy":2020, "r":22}
        self.hole_floor = 0
        # Interaction
        self.tool = "Pan"
        self.dragging = False
        self.drag_start_world = None
        self.temp_rect = None
        self.temp_agent_a = None
        self.pending_door_rect = None
        self.door_color = "red"
        # Status label (bottom-left overlay inside canvas)
        self.status = None
        Clock.schedule_interval(self._tick, 1/60)

    def _new_floor(self):
        return {"walls": [], "decor": [], "agents": [], "stairs": [], "doors": []}

    def _refresh_floor_refs(self):
        f = self.floors[self.current_floor]
        self.walls = f["walls"]
        self.decor = f["decor"]
        self.agents = f["agents"]
        self.stairs = f["stairs"]
        self.doors = f.get("doors", [])

    # --- IO ---
    def save_json(self, path):
        data = {
            "world": {"w": self.world_w, "h": self.world_h},
            "start": self.start,
            "start_floor": self.start_floor,
            "hole": self.hole,
            "hole_floor": self.hole_floor,
            "floors": self.floors,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_json(self, path):
        if not os.path.exists(path):
            return False
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.world_w = int(data.get("world", {}).get("w", self.world_w))
        self.world_h = int(data.get("world", {}).get("h", self.world_h))
        self.start = list(map(int, data.get("start", self.start)))
        self.start_floor = int(data.get("start_floor", 0))
        self.hole = data.get("hole", self.hole)
        self.hole_floor = int(data.get("hole_floor", 0))
        if "floors" in data:
            self.floors = data["floors"]
            for f in self.floors:
                f.setdefault("doors", [])
        else:
            self.floors = [
                {
                    "walls": [tuple(map(int, r)) for r in data.get("walls", [])],
                    "decor": data.get("decor", []),
                    "agents": data.get("agents", []),
                    "stairs": data.get("ramps", []),
                    "doors": data.get("doors", []),
                }
            ]
        self.current_floor = self.start_floor
        self._refresh_floor_refs()
        return True

    # --- Transforms ---
    def screen_to_world(self, sx, sy): return (sx + self.cam_x, sy + self.cam_y)

    # --- Events ---
    def on_touch_down(self, touch):
        # If touch hits any child (e.g., toolbar lives outside this widget), it won't reach here.
        wx, wy = self.screen_to_world(touch.x, touch.y)
        wx, wy = snap(wx), snap(wy)

        if self.tool == "Pan":
            self.dragging = True
            self.drag_start_world = (touch.x, touch.y, self.cam_x, self.cam_y)
            return True

        if self.tool in ("Wall","StairUp","StairDown","Door") + SCENERY_TOOLS:
            self.dragging = True
            self.temp_rect = (wx, wy, 1, 1)
            return True

        if self.tool == "Agent":
            if self.temp_agent_a is None:
                self.temp_agent_a = (wx, wy)
            else:
                ax, ay = self.temp_agent_a
                agent = {"a":[ax,ay], "b":[wx,wy], "speed":80, "fov_deg":60, "cone_len":260}
                self.agents.append(agent)
                self.temp_agent_a = None
            return True

        if self.tool == "Start":
            self.start = [wx, wy]; self.start_floor = self.current_floor; return True

        if self.tool == "Hole":
            self.hole = {"cx": wx, "cy": wy, "r": 22}; self.hole_floor = self.current_floor; return True

        if self.tool == "Erase":
            # Erase decor first, then walls, then agents
            def inside_rect(r):
                x,y,w,h = r
                return (x <= wx <= x+w) and (y <= wy <= y+h)
            for i in reversed(range(len(self.decor))):
                if inside_rect(self.decor[i]["rect"]): self.decor.pop(i); return True
            for i in reversed(range(len(self.walls))):
                if inside_rect(self.walls[i]): self.walls.pop(i); return True
            for i in reversed(range(len(self.stairs))):
                if inside_rect(self.stairs[i]["rect"]): self.stairs.pop(i); return True
            for i in reversed(range(len(self.doors))):
                d = self.doors[i]
                if inside_rect(d["rect"]) or inside_rect(d["screen"]):
                    self.doors.pop(i); return True
            # agents: near segment
            def segdist2(ax,ay,bx,by,px,py):
                vx,vy = bx-ax, by-ay; wx2,wy2 = px-ax, py-ay
                c = vx*wx2 + vy*wy2; d = vx*vx + vy*vy
                t = 0 if d==0 else max(0,min(1,c/d))
                cx,cy = ax + t*vx, ay + t*vy
                dx,dy = px-cx, py-cy
                return dx*dx+dy*dy
            for i in reversed(range(len(self.agents))):
                A = self.agents[i]["a"]; B = self.agents[i]["b"]
                if segdist2(A[0],A[1],B[0],B[1], wx,wy) <= (20*20): self.agents.pop(i); return True
            return True

        return False

    def on_touch_move(self, touch):
        wx, wy = self.screen_to_world(touch.x, touch.y)
        wx, wy = snap(wx), snap(wy)

        if self.tool == "Pan" and self.dragging and self.drag_start_world:
            sx, sy, camx0, camy0 = self.drag_start_world
            dx = sx - touch.x; dy = sy - touch.y
            self.cam_x = int(camx0 + dx); self.cam_y = int(camy0 + dy)
            self.cam_x = max(0, min(self.cam_x, self.world_w - self.width))
            self.cam_y = max(0, min(self.cam_y, self.world_h - self.height))
            return True

        if self.tool in ("Wall","Elevator","Rug","Vent","Plant","Desk","Chair","Table","StairUp","StairDown","Door") and self.dragging and self.temp_rect:
            x0,y0,_,_ = self.temp_rect
            x1,y1 = wx, wy
            x = min(x0,x1); y = min(y0,y1)
            w = max(1, abs(x1-x0)); h = max(1, abs(y1-y0))
            self.temp_rect = (x,y,w,h); return True

        return False

    def on_touch_up(self, touch):
        if self.tool in ("Wall","StairUp","StairDown","Door") + SCENERY_TOOLS and self.dragging and self.temp_rect:
            x,y,w,h = self.temp_rect
            if w >= GRID and h >= GRID:
                if self.tool == "Wall":
                    self.walls.append((x,y,w,h))
                elif self.tool in SCENERY_TOOLS:
                    kind = SCENERY_KIND_MAP.get(self.tool, self.tool.lower())
                    self.decor.append({"kind":kind, "rect":[x,y,w,h]})
                elif self.tool == "Door":
                    if self.pending_door_rect is None:
                        self.pending_door_rect = [x,y,w,h]
                        self.temp_rect = None; self.dragging = False; return True
                    else:
                        door = {"rect": self.pending_door_rect, "screen": [x,y,w,h], "color": self.door_color}
                        self.doors.append(door)
                        self.pending_door_rect = None
                else:
                    direction = "up" if self.tool=="StairUp" else "down"
                    self.stairs.append({"dir":direction, "rect":[x,y,w,h], "target": self.current_floor + (1 if direction=="up" else -1)})
                    target = self.current_floor + (1 if direction=="up" else -1)
                    while target >= len(self.floors):
                        self.floors.append(self._new_floor())
                    dest = self.floors[target]
                    opp = "down" if direction=="up" else "up"
                    dest["stairs"].append({"dir":opp, "rect":[x,y,w,h], "target": self.current_floor})
            if hasattr(self.parent, '_update_floor_spinner'):
                self.parent._update_floor_spinner()
            self.temp_rect = None; self.dragging = False; return True

        if self.tool == "Pan":
            self.dragging = False; self.drag_start_world = None; return True

        return False

    # --- Draw ---
    def _tick(self, dt):
        self.draw()

    def draw(self):
        self.canvas.clear()
        with self.canvas:
            PushMatrix()
            Translate(-self.cam_x, -self.cam_y, 0)

            # Background
            Color(0.08, 0.09, 0.11, 1.0)
            Rectangle(pos=(0,0), size=(self.world_w, self.world_h))

            # Grid
            Color(0.12, 0.13, 0.16, 1.0)
            for x in range(0, self.world_w, GRID):
                Rectangle(pos=(x, 0), size=(1, self.world_h))
            for y in range(0, self.world_h, GRID):
                Rectangle(pos=(0, y), size=(self.world_w, 1))

            # Walls
            Color(0.25, 0.28, 0.33, 1.0)
            for rx,ry,rw,rh in self.walls:
                Rectangle(pos=(rx,ry), size=(rw,rh))

            # Decor
            for d in self.decor:
                kind = d["kind"]; rx,ry,rw,rh = d["rect"]
                if kind == "elevator":
                    Color(0.18, 0.2, 0.24, 1.0)
                    Rectangle(pos=(rx,ry), size=(rw,rh))
                    Color(0.26, 0.28, 0.32, 1.0)
                    Rectangle(pos=(rx + rw/2 - 2, ry + 10), size=(4, rh - 20))
                elif kind == "rug":
                    Color(0.13, 0.25, 0.18, 0.6)
                    Rectangle(pos=(rx,ry), size=(rw,rh))
                elif kind == "vent":
                    Color(0.75,0.75,0.78,1.0)
                    Rectangle(pos=(rx,ry), size=(rw,rh))
                    Color(0.6,0.6,0.62,1.0)
                    for i in range(4):
                        y = ry + (i+1)*rh/5
                        Line(points=[rx, y, rx+rw, y], width=1)
                elif kind == "plant":
                    Color(0.16,0.4,0.18,1.0)
                    Ellipse(pos=(rx,ry), size=(rw,rh))
                    Color(0.2,0.25,0.2,1.0)
                    Rectangle(pos=(rx + rw*0.35, ry), size=(rw*0.3, rh*0.25))
                elif kind == "desk":
                    Color(0.45,0.33,0.18,1.0)
                    Rectangle(pos=(rx,ry), size=(rw,rh))
                    Color(0.1,0.1,0.1,1.0)
                    Rectangle(pos=(rx+5, ry+rh-25), size=(40,20))
                    Color(0.2,0.2,0.2,1.0)
                    Rectangle(pos=(rx+5, ry+rh-35), size=(40,5))
                    Color(0.3,0.3,0.3,1.0)
                    Rectangle(pos=(rx+5, ry+10), size=(50,8))
                elif kind == "chair":
                    Color(0.25,0.25,0.3,1.0)
                    Rectangle(pos=(rx,ry), size=(rw,rh))
                    Color(0.15,0.15,0.2,1.0)
                    Rectangle(pos=(rx+rw*0.2, ry+rh*0.2), size=(rw*0.6, rh*0.6))
                elif kind == "table":
                    Color(0.4,0.3,0.2,1.0)
                    Rectangle(pos=(rx,ry), size=(rw,rh))
                    Color(0.3,0.22,0.15,1.0)
                    Line(rectangle=(rx,ry,rw,rh), width=1.2)
                elif kind == "blue_screen_monitor":
                    Color(0.1,0.1,0.1,1.0)
                    Rectangle(pos=(rx,ry), size=(rw,rh))
                    Color(0.2,0.4,0.9,1.0)
                    Rectangle(pos=(rx+5, ry+5), size=(rw-10, rh-10))

            # Doors
            for d in self.doors:
                rx,ry,rw,rh = d["rect"]
                sx,sy,sw,sh = d["screen"]
                r,g,b = COLOR_MAP.get(d.get("color","red"), (0.8,0,0))
                Color(r,g,b,1.0)
                Rectangle(pos=(rx,ry), size=(rw,rh))
                Color(r,g,b,0.3)
                Rectangle(pos=(sx,sy), size=(sw,sh))
                Color(1,1,1,0.8)
                Line(rectangle=(sx,sy,sw,sh), width=1.1)

            # Stairs
            for r in self.stairs:
                rx,ry,rw,rh = r["rect"]
                steps = 6
                if r["dir"] == "up":
                    Color(0.8,0.8,0.8,1.0)
                else:
                    Color(0.4,0.4,0.4,1.0)
                Rectangle(pos=(rx,ry), size=(rw,rh))
                Color(0.3,0.3,0.3,1.0)
                for i in range(steps):
                    y = ry + (i/steps)*rh
                    Line(points=[rx, y, rx+rw, y], width=1)

            # Agent paths + occluded cone preview
            for a in self.agents:
                ax,ay = a["a"]; bx,by = a["b"]
                # path
                Color(0.8, 0.4, 0.4, 1.0)
                Line(points=[ax,ay,bx,by], width=1.2)
                Color(0.9, 0.2, 0.2, 1.0)
                Rectangle(pos=(ax-6,ay-6), size=(12,12))
                Rectangle(pos=(bx-6,by-6), size=(12,12))
                # cone preview
                fov_half = radians(a.get("fov_deg",60)/2.0)
                cone_len = a.get("cone_len",260)
                dirx, diry = normalize(bx-ax, by-ay)
                base_ang = atan2(diry, dirx)
                start_ang = base_ang + fov_half
                end_ang = base_ang - fov_half
                steps = 48
                pts = []
                for i in range(steps+1):
                    t = i/steps
                    ang = start_ang + (end_ang - start_ang)*t
                    dx,dy = cos(ang), sin(ang)
                    hit_pt = None; nearest_d2=None
                    tx,ty = ax + dx*cone_len, ay + dy*cone_len
                    for rect in self.walls:
                        pt = ray_rect_nearest_hit(ax, ay, dx, dy, rect)
                        if pt is not None:
                            d2 = (pt[0]-ax)**2 + (pt[1]-ay)**2
                            if nearest_d2 is None or d2 < nearest_d2:
                                nearest_d2 = d2; hit_pt = pt
                    if hit_pt is None:
                        pts.append((tx,ty))
                    else:
                        if nearest_d2 is not None and nearest_d2 > (cone_len*cone_len):
                            pts.append((tx,ty))
                        else:
                            pts.append(hit_pt)
                Color(1.0, 1.0, 0.65, 0.16)
                verts = [(ax,ay,0,0)] + [(x,y,0,0) for (x,y) in pts]
                idx = []
                for i in range(1,len(verts)-1):
                    idx.extend([0,i,i+1])
                Mesh(vertices=sum(([vx,vy,0,0] for vx,vy,_,_ in verts), []), indices=idx, mode='triangles')

            # Start
            if self.current_floor == self.start_floor:
                Color(0.9, 0.9, 1.0, 1.0)
                Rectangle(pos=(self.start[0]-6, self.start[1]-6), size=(12,12))

            # Hole
            if self.current_floor == self.hole_floor:
                Color(0.1, 0.5, 0.15, 1.0)
                Ellipse(pos=(self.hole["cx"]-(self.hole["r"]+6), self.hole["cy"]-(self.hole["r"]+6)),
                        size=((self.hole["r"]+6)*2, (self.hole["r"]+6)*2))
                Color(0.02, 0.02, 0.02, 1.0)
                Ellipse(pos=(self.hole["cx"]-self.hole["r"], self.hole["cy"]-self.hole["r"]),
                        size=(self.hole["r"]*2, self.hole["r"]*2))

            # Drag preview
            if self.temp_rect is not None:
                Color(0.8, 0.8, 1.0, 0.25)
                rx,ry,rw,rh = self.temp_rect
                Rectangle(pos=(rx,ry), size=(rw,rh))
                Color(0.9, 0.9, 1.0, 0.8)
                Line(rectangle=(rx,ry,rw,rh), width=1.1)

            if self.pending_door_rect is not None:
                r,g,b = COLOR_MAP.get(self.door_color,(0.8,0,0))
                Color(r,g,b,0.5)
                rx,ry,rw,rh = self.pending_door_rect
                Rectangle(pos=(rx,ry), size=(rw,rh))

            PopMatrix()

            # Toolbar background strip drawn as overlay (for contrast behind buttons)
            Color(0.05, 0.05, 0.06, 1.0)
            Rectangle(pos=(0, self.height-52), size=(self.width, 52))

        # On-canvas status label
        if not self.status:
            self.status = Label(text="", font_size=14, color=(1,1,1,1), size_hint=(None,None), pos=(10, 8))
            self.add_widget(self.status)
        self.status.text = f"Floor {floor_label(self.current_floor)}  •  Tool: [b]{self.tool}[/b]  •  Grid: {GRID}px   (Ctrl+S=Save, Ctrl+O=Load, 1..9=Tools)"
        self.status.markup = True

class LevelEditorRoot(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Track which file is currently loaded/saved
        self.current_file = "stealth_level.json"
        # Canvas area
        self.canvas_view = LevelCanvas(size_hint=(1,1), pos_hint={"x":0,"y":0})
        self.add_widget(self.canvas_view)

        # Toolbar
        self.toolbar = BoxLayout(size_hint=(1,None), height=48, pos_hint={"x":0,"top":1})
        self.add_widget(self.toolbar)
        self._build_toolbar()

        # Keyboard shortcuts
        Window.bind(on_key_down=self._on_key_down)

    def _tool_button(self, name):
        b = Button(text=name, size_hint=(None,1), width=96)
        b.bind(on_release=lambda *_: self._select_tool(name))
        return b

    def _build_toolbar(self):
        self.toolbar.spacing = 4
        tools = ["Pan","Wall","Door","Agent","Start","Hole","StairUp","StairDown","Erase"]
        for t in tools:
            self.toolbar.add_widget(self._tool_button(t))

        self.scenery_spinner = Spinner(text="Scenery", values=SCENERY_TOOLS, size_hint=(None,1), width=150)
        self.scenery_spinner.bind(text=self._on_scenery_select)
        self.toolbar.add_widget(self.scenery_spinner)

        self.toolbar.add_widget(self._tool_button("Save"))

        self.load_spinner = Spinner(text="Load", values=(), size_hint=(None,1), width=160)
        self.load_spinner.bind(text=self._on_load_select)
        self.toolbar.add_widget(self.load_spinner)

        self.toolbar.add_widget(self._tool_button("Clear"))

        self.door_color_spinner = Spinner(text="red", values=("red","green","blue","yellow","white","black","brown"), size_hint=(None,1), width=100)
        self.door_color_spinner.bind(text=self._on_color_select)
        self.toolbar.add_widget(self.door_color_spinner)

        self.floor_spinner = Spinner(text="F1", values=(), size_hint=(None,1), width=100)
        self.floor_spinner.bind(text=self._on_floor_select)
        self.toolbar.add_widget(self.floor_spinner)

        self._update_load_spinner()
        self._update_floor_spinner()

    def _select_tool(self, name):
        if name in ("Save","Load","Clear"):
            if name == "Save":
                path = self.current_file or "stealth_level.json"
                self.canvas_view.save_json(path)
                self.current_file = path
                self.canvas_view.status.text = f"Saved to {path}"
                self._update_load_spinner()
            elif name == "Load":
                filename = self.load_spinner.text
                if filename != "Load":
                    ok = self.canvas_view.load_json(filename)
                    if ok:
                        self.current_file = filename
                    self.canvas_view.status.text = f"{'Loaded' if ok else 'No file found'}: {filename}"
                    self._update_floor_spinner()
            elif name == "Clear":
                self.canvas_view.floors = [self.canvas_view._new_floor()]
                self.canvas_view.current_floor = 0
                self.canvas_view.start = [240,220]
                self.canvas_view.start_floor = 0
                self.canvas_view.hole = {"cx":1240,"cy":2020,"r":22}
                self.canvas_view.hole_floor = 0
                self.canvas_view._refresh_floor_refs()
                self.canvas_view.status.text = "Cleared."
                self._update_floor_spinner()
            return
        self.canvas_view.tool = name
        # cancel in-progress operations
        self.canvas_view.temp_rect = None
        self.canvas_view.temp_agent_a = None
        self.canvas_view.pending_door_rect = None
        self.canvas_view.dragging = False

    # Keyboard shortcuts
    def _on_key_down(self, window, key, scancode, codepoint, modifiers):
        # Map by codepoint (characters)
        if 'ctrl' in modifiers and (codepoint == 's' or codepoint == 'S'):
            self._select_tool("Save"); return True
        if 'ctrl' in modifiers and (codepoint == 'o' or codepoint == 'O'):
            self._select_tool("Load"); return True
        if codepoint == 'c' or codepoint == 'C':
            self._select_tool("Clear"); return True

        # Number keys -> tools
        mapping = {
            '1':"Pan", '2':"Wall", '3':"Agent", '4':"Start",
            '5':"Hole", '6':"Door", '7':"StairUp", '8':"StairDown", '9':"Erase"
        }
        if codepoint in mapping:
            self._select_tool(mapping[codepoint]); return True
        return False

    def _find_levels(self):
        return sorted([f for f in os.listdir('.') if f.endswith('.json')])

    def _update_load_spinner(self):
        if hasattr(self, 'load_spinner'):
            self.load_spinner.values = self._find_levels()

    def _on_load_select(self, spinner, text):
        if text == "Load":
            return
        ok = self.canvas_view.load_json(text)
        if ok:
            self.current_file = text
        self.canvas_view.status.text = f"{'Loaded' if ok else 'No file found'}: {text}"

    def _on_scenery_select(self, spinner, text):
        if text == "Scenery":
            return
        self._select_tool(text)

    def _on_color_select(self, spinner, text):
        self.canvas_view.door_color = text
        self._update_floor_spinner()

    def _update_floor_spinner(self):
        if hasattr(self, 'floor_spinner'):
            vals = [floor_label(i) for i in range(len(self.canvas_view.floors))]
            self.floor_spinner.values = vals
            self.floor_spinner.text = floor_label(self.canvas_view.current_floor)

    def _on_floor_select(self, spinner, text):
        idx = label_to_floor_index(text)
        if 0 <= idx < len(self.canvas_view.floors):
            self.canvas_view.current_floor = idx
            self.canvas_view._refresh_floor_refs()
            self.canvas_view.status.text = f"Floor {text}"

class LevelEditorApp(App):
    def build(self):
        return LevelEditorRoot()

if __name__ == "__main__":
    LevelEditorApp().run()
