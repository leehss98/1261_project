"""
Tkinter-based graphical visualisation for the integrated traffic simulation.

Launched when the user passes ``-G`` to ``integrated_simulation.py``.

Road layout (matches project spec, proportional scale):

  A ■──●(I00)──────────●(I01)──────────■ D(=I02)
        |                |                |
       ●(I10)──────────●(I11)──────────●(I12)
        |                |                |
  B ■──●(I20)──────────●(I21)──────────■ C(=I22)
  (=I20)                               (=I22)

Scale:
  - Inter-intersection distance = 0.5 mile → CELL = 240 px
  - A-to-I00 terminal distance  = 1/30 mile → A_EXT = CELL/15 ≈ 16 px
  - B=I20, C=I22, D=I02 (zero-length terminal segments; shown as squares AT the corner intersections)
  - Only A is an external node offset from I00
"""

import tkinter as tk
from typing import Dict, List, Optional, Tuple

from common_model import SEGMENTS, NODES, Direction, NodeType

# Stable colour palette indexed by vehicle number (car_N → index N-1).
VEHICLE_COLORS = [
    "#e6194B", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990",
    "#dcbeff", "#9A6324", "#800000", "#aaffc3", "#808000",
    "#ffd8b1", "#000075", "#a9a9a9", "#ffe119", "#000000",
]

_ARROW_CHAR = {"north": "^", "south": "v", "east": ">", "west": "<"}

# Intersections that double as terminal squares (B, C, D share their position).
_TERMINAL_INTERSECTIONS = {"I02": "D", "I20": "B", "I22": "C"}


class TrafficVisualization:
    """Renders the road grid, vehicles, lights, grants, and violations."""

    # --- Scale ---
    CELL: int = 240          # pixels per 0.5-mile inter-intersection gap
    MARGIN: int = 80         # canvas margin
    A_EXT: int = round(CELL / 15)   # 16 px for 1/30-mile A-to-I00 terminal

    # Derived intersection grid origins
    _GX0 = MARGIN + A_EXT   # x of column 0 (I00, I10, I20)
    _GY0 = MARGIN            # y of row 0    (I00, I01, I02)

    # Dual-lane half-gap
    LANE_GAP: int = 6

    # Node rendering sizes
    CIRCLE_RADIUS: int = 14
    SQUARE_HALF: int = 14
    VEHICLE_RADIUS: int = 7

    # Canvas / panel
    MAP_WIDTH: int = 680
    MAP_HEIGHT: int = 720
    PANEL_WIDTH: int = 320
    STEP_DELAY_MS: int = 100
    LOG_MAX_LINES: int = 28

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        total_w = self.MAP_WIDTH + self.PANEL_WIDTH
        self.canvas = tk.Canvas(
            root, width=total_w, height=self.MAP_HEIGHT, bg="#1a1a2e",
        )
        self.canvas.pack()

        self.node_positions: Dict[str, Tuple[float, float]] = \
            self._build_node_positions()
        self.prev_safety: Optional[dict] = None
        self.violation_log: List[str] = []

        self._draw_roads()
        self._draw_nodes()
        self._draw_panel_border()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_node_positions(self) -> Dict[str, Tuple[float, float]]:
        """Return pixel (x, y) for every node."""
        pos: Dict[str, Tuple[float, float]] = {}

        # 3×3 intersection grid
        for nid, node in NODES.items():
            if node.node_type == NodeType.INTERSECTION:
                row = int(nid[1])
                col = int(nid[2])
                pos[nid] = (
                    float(self._GX0 + col * self.CELL),
                    float(self._GY0 + row * self.CELL),
                )

        # A: 1/30-mile left of I00, same row
        pos["A"] = (float(self._GX0 - self.A_EXT), float(self._GY0))

        # B, C, D co-located with their paired intersections
        pos["B"] = pos["I20"]
        pos["C"] = pos["I22"]
        pos["D"] = pos["I02"]

        return pos

    # ------------------------------------------------------------------
    # Static drawing (called once at init)
    # ------------------------------------------------------------------

    def _draw_roads(self) -> None:
        """Draw dual-lane horizontal and vertical roads."""
        g = self.LANE_GAP
        w = 2
        color = "#4a6fa5"

        col_xs = [self._GX0 + c * self.CELL for c in range(3)]
        row_ys = [self._GY0 + r * self.CELL for r in range(3)]

        # Horizontal roads
        for i, ry in enumerate(row_ys):
            # Top road starts at A (x = MARGIN); others start at col 0.
            x_start = float(self.MARGIN) if i == 0 else float(col_xs[0])
            x_end   = float(col_xs[2])
            self.canvas.create_line(
                x_start, ry - g, x_end, ry - g,
                fill=color, width=w, tags="road",
            )
            self.canvas.create_line(
                x_start, ry + g, x_end, ry + g,
                fill=color, width=w, tags="road",
            )

        # Vertical roads (all span full row range)
        y_top = float(row_ys[0])
        y_bot = float(row_ys[2])
        for cx in col_xs:
            self.canvas.create_line(
                cx - g, y_top, cx - g, y_bot,
                fill=color, width=w, tags="road",
            )
            self.canvas.create_line(
                cx + g, y_top, cx + g, y_bot,
                fill=color, width=w, tags="road",
            )

    def _draw_nodes(self) -> None:
        """Draw circles for internal intersections, squares for terminals."""
        # Draw circles at the 6 non-terminal intersections
        circle_nodes = {nid for nid in NODES
                        if NODES[nid].node_type == NodeType.INTERSECTION
                        and nid not in _TERMINAL_INTERSECTIONS}
        for nid in circle_nodes:
            x, y = self.node_positions[nid]
            r = self.CIRCLE_RADIUS
            self.canvas.create_oval(
                x - r, y - r, x + r, y + r,
                fill="#2a4a7a", outline="#5588bb", width=2,
                tags="intersection_base",
            )

        # Draw squares at corner intersections (D=I02, B=I20, C=I22)
        for iid, label in _TERMINAL_INTERSECTIONS.items():
            x, y = self.node_positions[iid]
            s = self.SQUARE_HALF
            self.canvas.create_rectangle(
                x - s, y - s, x + s, y + s,
                fill="#2a4a7a", outline="#77bbee", width=2,
                tags="intersection_base",
            )
            self._draw_terminal_label(label, x, y)

        # Draw square for external terminal A
        ax, ay = self.node_positions["A"]
        s = self.SQUARE_HALF
        self.canvas.create_rectangle(
            ax - s, ay - s, ax + s, ay + s,
            fill="#3a6ea5", outline="#77bbee", width=2,
            tags="terminal",
        )
        self._draw_terminal_label("A", ax, ay - s - 10)

    def _draw_terminal_label(self, label: str, x: float, y: float) -> None:
        self.canvas.create_text(
            x, y, text=label, fill="#ffffff",
            font=("Consolas", 12, "bold"), tags="terminal",
        )

    def _draw_panel_border(self) -> None:
        x = self.MAP_WIDTH
        self.canvas.create_line(
            x, 0, x, self.MAP_HEIGHT, fill="#555577", width=2,
        )

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _lane_offset(self, direction: Direction) -> Tuple[float, float]:
        """Right-hand traffic: vehicles drive on the right side of the road."""
        g = float(self.LANE_GAP)
        if direction == Direction.EAST:
            return (0.0, g)
        elif direction == Direction.WEST:
            return (0.0, -g)
        elif direction == Direction.SOUTH:
            return (-g, 0.0)
        else:  # NORTH
            return (g, 0.0)

    def _segment_slot_to_pixel(self, segment_id: str, slot: int
                               ) -> Tuple[float, float]:
        seg = SEGMENTS.get(segment_id)
        if seg is None:
            return (0.0, 0.0)
        p1 = self.node_positions[seg.from_node]
        p2 = self.node_positions[seg.to_node]
        max_slot = max(seg.length_slots - 1, 1)
        t = slot / float(max_slot)
        dx, dy = self._lane_offset(seg.direction)
        return (
            p1[0] + t * (p2[0] - p1[0]) + dx,
            p1[1] + t * (p2[1] - p1[1]) + dy,
        )

    @staticmethod
    def _car_index(car_id: str) -> int:
        try:
            return int(car_id.split("_")[1]) - 1
        except (IndexError, ValueError):
            return 0

    @staticmethod
    def _car_label(car_id: str) -> str:
        try:
            return car_id.split("_")[1]
        except IndexError:
            return car_id

    # ------------------------------------------------------------------
    # Dynamic drawing (each step)
    # ------------------------------------------------------------------

    def update(self, step_result: dict) -> None:
        for tag in ("light", "vehicle", "grant", "violation", "info", "log"):
            self.canvas.delete(tag)

        self._detect_new_violations(step_result)
        self._draw_traffic_lights(step_result.get("lights", {}))
        self._draw_crossing_grants(step_result.get("crossing_grants", []))
        self._draw_vehicles(step_result.get("vehicles", {}))
        self._draw_violation_markers(step_result)
        self._draw_info_panel(step_result)
        self._draw_violation_log()

    # --- Traffic lights ---

    # Offsets for per-direction signal dots around intersection center
    _LIGHT_DOT_OFFSET = {
        "north": (0, -20),
        "south": (0, 20),
        "east":  (20, 0),
        "west":  (-20, 0),
    }
    _LIGHT_DOT_R = 5

    def _draw_traffic_lights(self, lights: Dict[str, Optional[str]]) -> None:
        for iid, direction in lights.items():
            pos = self.node_positions.get(iid)
            if pos is None:
                continue
            x, y = pos

            green_dir = direction if isinstance(direction, str) \
                else (direction.value if direction is not None else None)

            # Draw a small dot for each direction: green if active, red otherwise
            dr = self._LIGHT_DOT_R
            for d_str, (dx, dy) in self._LIGHT_DOT_OFFSET.items():
                cx, cy = x + dx, y + dy
                is_green = (green_dir == d_str)
                fill = "#00ff44" if is_green else "#cc2222"
                out  = "#00ff66" if is_green else "#881111"
                self.canvas.create_oval(
                    cx - dr, cy - dr, cx + dr, cy + dr,
                    fill=fill, outline=out, width=1, tags="light",
                )

            # Draw direction arrow for the green light
            if green_dir:
                adx, ady = self._LIGHT_DOT_OFFSET.get(green_dir, (0, 0))
                arrow = _ARROW_CHAR.get(green_dir, "")
                self.canvas.create_text(
                    x + adx, y + ady, text=arrow,
                    fill="#ffffff", font=("Consolas", 9, "bold"),
                    tags="light",
                )

    # --- Crossing grants ---

    def _draw_crossing_grants(self, grants) -> None:
        grant_list: list = []
        if isinstance(grants, dict):
            for (cid, iid), granted in grants.items():
                if granted:
                    grant_list.append({"car_id": cid, "intersection_id": iid})
        elif isinstance(grants, list):
            grant_list = [g for g in grants if g.get("granted")]

        for g in grant_list:
            iid = g.get("intersection_id", "")
            cid = g.get("car_id", "")
            pos = self.node_positions.get(iid)
            if pos is None:
                continue
            x, y = pos
            r = self.CIRCLE_RADIUS + 7
            self.canvas.create_oval(
                x - r, y - r, x + r, y + r,
                outline="#ffdd00", width=3, tags="grant",
            )
            self.canvas.create_text(
                x, y + r + 8, text=self._car_label(cid),
                fill="#ffdd00", font=("Consolas", 9, "bold"), tags="grant",
            )

    # --- Vehicles ---

    def _draw_vehicles(self, vehicles: Dict[str, dict]) -> None:
        r = self.VEHICLE_RADIUS
        for cid, v in vehicles.items():
            seg  = v.get("current_segment", "")
            slot = v.get("current_slot", 0)
            px, py = self._segment_slot_to_pixel(seg, slot)
            idx   = self._car_index(cid)
            color = VEHICLE_COLORS[idx % len(VEHICLE_COLORS)]
            self.canvas.create_oval(
                px - r, py - r, px + r, py + r,
                fill=color, outline="#ffffff", width=1, tags="vehicle",
            )
            self.canvas.create_text(
                px, py - r - 6, text=self._car_label(cid),
                fill=color, font=("Consolas", 9, "bold"), tags="vehicle",
            )

    # --- Violation markers on the map ---

    def _draw_violation_markers(self, step_result: dict) -> None:
        vehicles = step_result.get("vehicles", {})
        positions: Dict[Tuple[str, int], List[str]] = {}
        for cid, v in vehicles.items():
            if v.get("parked"):
                continue
            key = (v.get("current_segment", ""), v.get("current_slot", 0))
            positions.setdefault(key, []).append(cid)

        for (seg, slot), cids in positions.items():
            if len(cids) < 2:
                continue
            px, py = self._segment_slot_to_pixel(seg, slot)
            s = 12
            self.canvas.create_line(
                px - s, py - s, px + s, py + s,
                fill="#ff0000", width=3, tags="violation",
            )
            self.canvas.create_line(
                px + s, py - s, px - s, py + s,
                fill="#ff0000", width=3, tags="violation",
            )
            self.canvas.create_text(
                px, py + s + 8, text="CRASH",
                fill="#ff0000", font=("Consolas", 8, "bold"),
                tags="violation",
            )

    # --- Detect new violations for the log ---

    def _detect_new_violations(self, step_result: dict) -> None:
        sr   = step_result.get("safety_report", {})
        step = step_result.get("time_step", "?")
        if self.prev_safety is None:
            self.prev_safety = dict(sr)
            return

        checks = [
            ("collisions_i",              "Collision (i-group)"),
            ("collisions_v",              "Collision (v-group)"),
            ("red_light_violations_i",    "Red-light (i-group)"),
            ("red_light_violations_v",    "Red-light (v-group)"),
            ("u_turn_violations_i",       "U-turn (i-group)"),
            ("u_turn_violations_v",       "U-turn (v-group)"),
            ("right_turn_violations_i",   "Right-turn (i-group)"),
            ("right_turn_violations_v",   "Right-turn (v-group)"),
            ("simultaneous_green_violations", "Simultaneous green"),
            ("invalid_grant_violations",  "Invalid grant"),
        ]
        for key, label in checks:
            diff = sr.get(key, 0) - self.prev_safety.get(key, 0)
            if diff > 0:
                self.violation_log.append(
                    "Step {}: {} (+{})".format(step, label, diff)
                )
        self.prev_safety = dict(sr)

    # --- Side panel: stats ---

    def _draw_info_panel(self, step_result: dict) -> None:
        x0  = self.MAP_WIDTH + 16
        y   = 20
        gap = 22

        sr    = step_result.get("safety_report", {})
        tours = step_result.get("throughput", {}).get("completed_tours", 0)
        step  = step_result.get("time_step", 0)

        self.canvas.create_text(
            x0, y, anchor="nw", text="ECEN 723 Traffic Sim",
            fill="#ffffff", font=("Consolas", 12, "bold"), tags="info",
        )
        y += gap + 8

        def vrow(label, *vals):
            """Return (text, color) for a violation row."""
            nums = [str(v) for v in vals]
            text = "{:<14} {}".format(label, " / ".join(nums))
            has_nz = any(int(v) > 0 for v in nums if v.isdigit())
            return text, "#ff4444" if has_nz else "#cccccc"

        rows = [
            ("Step:  {}".format(step),  "#44ddff"),
            ("Tours: {}".format(tours), "#44ddff"),
            ("",                         None),
            ("-- Violations (i/v) --",  "#8888aa"),
        ]
        rows += [
            vrow("Collisions:",
                 sr.get("collisions_i", 0), sr.get("collisions_v", 0)),
            vrow("Red-light:",
                 sr.get("red_light_violations_i", 0),
                 sr.get("red_light_violations_v", 0)),
            vrow("U-turn:",
                 sr.get("u_turn_violations_i", 0),
                 sr.get("u_turn_violations_v", 0)),
            vrow("Right-turn:",
                 sr.get("right_turn_violations_i", 0),
                 sr.get("right_turn_violations_v", 0)),
            vrow("Wrong dir:",
                 sr.get("wrong_direction_violations_i", 0),
                 sr.get("illegal_direction_violations_v", 0)),
        ]
        rows += [
            ("Simul.green:  {}".format(sr.get("simultaneous_green_violations", 0)),
             "#ff4444" if sr.get("simultaneous_green_violations", 0) > 0 else "#cccccc"),
            ("Inv.grant:    {}".format(sr.get("invalid_grant_violations", 0)),
             "#ff4444" if sr.get("invalid_grant_violations", 0) > 0 else "#cccccc"),
        ]

        for text, color in rows:
            if not text:
                y += gap // 2
                continue
            self.canvas.create_text(
                x0, y, anchor="nw", text=text,
                fill=color or "#cccccc",
                font=("Consolas", 10), tags="info",
            )
            y += gap

        # Vehicle legend
        y += 8
        self.canvas.create_text(
            x0, y, anchor="nw", text="-- Vehicles --",
            fill="#8888aa", font=("Consolas", 10), tags="info",
        )
        y += gap
        for cid, v in step_result.get("vehicles", {}).items():
            idx   = self._car_index(cid)
            color = VEHICLE_COLORS[idx % len(VEHICLE_COLORS)]
            label = self._car_label(cid)
            target = v.get("current_target", "?")
            bcd = ("B" if v.get("visited_B") else "") + \
                  ("C" if v.get("visited_C") else "") + \
                  ("D" if v.get("visited_D") else "")
            self.canvas.create_text(
                x0, y, anchor="nw",
                text="{}: tgt={} vis={}".format(label, target, bcd or "-"),
                fill=color, font=("Consolas", 9), tags="info",
            )
            y += gap - 4

    # --- Side panel: violation log ---

    def _draw_violation_log(self) -> None:
        x0 = self.MAP_WIDTH + 16
        y  = self.MAP_HEIGHT - 30 - self.LOG_MAX_LINES * 16

        self.canvas.create_text(
            x0, y, anchor="nw", text="-- Violation Log --",
            fill="#8888aa", font=("Consolas", 10), tags="log",
        )
        y += 20
        for entry in self.violation_log[-self.LOG_MAX_LINES:]:
            self.canvas.create_text(
                x0, y, anchor="nw", text=entry,
                fill="#ff6666", font=("Consolas", 8), tags="log",
            )
            y += 16

    # ------------------------------------------------------------------
    # Completion overlay
    # ------------------------------------------------------------------

    def show_complete(self) -> None:
        cx = self.MAP_WIDTH // 2
        cy = self.MAP_HEIGHT // 2
        self.canvas.create_text(
            cx, cy, text="SIMULATION COMPLETE",
            fill="#ffdd00", font=("Consolas", 22, "bold"), tags="info",
        )


class GraphicalSimulationRunner:
    """Drives the simulation one step at a time via tkinter after() callbacks."""

    def __init__(self, sim, vis: TrafficVisualization,
                 num_steps: int, root: tk.Tk) -> None:
        self.sim          = sim
        self.vis          = vis
        self.num_steps    = num_steps
        self.root         = root
        self.current_step = 0
        self.last_result: Optional[dict] = None

    def start(self) -> None:
        self._tick()

    def _tick(self) -> None:
        if self.current_step >= self.num_steps:
            if self.last_result is not None:
                self.vis.show_complete()
            return
        self.last_result = self.sim.step()
        self.vis.update(self.last_result)
        self.current_step += 1
        self.root.after(self.vis.STEP_DELAY_MS, self._tick)
