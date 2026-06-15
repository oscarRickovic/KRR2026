#!/usr/bin/env python3
"""
visualise.py — 3D visualiser for non-rectangular tetracube puzzles.

Usage:
    python visualise.py <solution_file> [t_shape|l_shape|general_shape]

Examples:
    python visualise.py sol_t.txt t_shape
    python visualise.py sol_l.txt l_shape
    python visualise.py sol_general.txt general_shape
    python visualise.py sol_t2.txt t_shape        # N=2 auto-detected from file

Controls:
    Radio buttons : toggle between Puzzle view (hints only) and Solution view
    Next / Prev   : add or remove one piece at a time

num_copies (N) is auto-detected from the numCopies(N) atom in the solution.
"""

import sys
import os
import re
import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.widgets import Button, RadioButtons
from matplotlib.lines import Line2D

def t_shape_cells(num_copies=1):
    """T-shape: bar {0..3}×{4..5} + stem {1..2}×{0..3}, depth 2*num_copies."""
    cells = set()
    depth = 2 * num_copies
    for x in range(4):
        for y in range(4, 6):
            for z in range(depth):
                cells.add((x, y, z))
    for x in range(1, 3):
        for y in range(4):
            for z in range(depth):
                cells.add((x, y, z))
    return cells

def l_shape_cells(num_copies=1):
    """L-shape: 4×5 minus top-right 2×2 corner, depth 2*num_copies."""
    cells = set()
    depth = 2 * num_copies
    for x in range(4):
        for y in range(5):
            for z in range(depth):
                if not (x >= 2 and y >= 3):
                    cells.add((x, y, z))
    return cells

def general_shape_cells(num_copies=1):
    """Plus/Cross: 4×3 body + top/bottom 2×1 arms, depth 2*num_copies."""
    cells = set()
    depth = 2 * num_copies
    for x in range(4):
        for y in range(1, 4):
            for z in range(depth):
                cells.add((x, y, z))
    for x in range(1, 3):
        for z in range(depth):
            cells.add((x, 4, z))
    for x in range(1, 3):
        for z in range(depth):
            cells.add((x, 0, z))
    return cells

SHAPE_CELLS = {
    "t_shape":       t_shape_cells,
    "l_shape":       l_shape_cells,
    "general_shape": general_shape_cells,
}

SHAPE_LABELS = {
    "t_shape":       "T-Shape",
    "l_shape":       "L-Shape",
    "general_shape": "Plus/Cross Shape",
}

COLORS = {
    "I":        "#e74c3c",
    "T":        "#3498db",
    "L":        "#2ecc71",
    "Pyramid":  "#9b59b6",
    "O":        "#f39c12",
    "N":        "#f1c40f",
    "Z":        "#1abc9c",
    "Z_mirror": "#e91e63",
}

_ORIENTATIONS = [
    [1, 2, 3],  [1, 3, -2],  [1, -2, -3], [1, -3, 2],
    [-1, 2, -3],[-1, -3, -2],[-1, -2, 3], [-1, 3, 2],
    [2, 1, -3], [2, -3, -1], [2, -1, 3],  [2, 3, 1],
    [-2, 1, 3], [-2, 3, -1], [-2, -1, -3],[-2, -3, 1],
    [3, 1, 2],  [3, 2, -1],  [3, -1, -2], [3, -2, 1],
    [-3, 1, -2],[-3, -2, -1],[-3, -1, 2], [-3, 2, 1],
]

def _normalize(shape):
    mx = min(x for x, y, z in shape)
    my = min(y for x, y, z in shape)
    mz = min(z for x, y, z in shape)
    return sorted((x - mx, y - my, z - mz) for x, y, z in shape)

def _apply_orientation(shape, ori):
    rotated = []
    for x, y, z in shape:
        coords = [x, y, z]
        rx = coords[abs(ori[0]) - 1] * (1 if ori[0] > 0 else -1)
        ry = coords[abs(ori[1]) - 1] * (1 if ori[1] > 0 else -1)
        rz = coords[abs(ori[2]) - 1] * (1 if ori[2] > 0 else -1)
        rotated.append((rx, ry, rz))
    return rotated

def get_all_rotations(shape):
    seen = []
    for ori in _ORIENTATIONS:
        rotated = _normalize(_apply_orientation(shape, ori))
        if rotated not in seen:
            seen.append(rotated)
    return seen

_BASE_SHAPES = {
    "I":        [(0,0,0),(0,0,1),(0,0,2),(0,0,3)],
    "T":        [(0,0,0),(0,0,1),(0,0,2),(0,1,1)],
    "L":        [(0,0,0),(0,0,1),(0,0,2),(0,1,0)],
    "Pyramid":  [(0,0,0),(0,0,1),(0,1,0),(1,0,0)],
    "O":        [(0,0,0),(0,0,1),(0,1,0),(0,1,1)],
    "N":        [(0,0,0),(0,0,1),(0,1,1),(0,1,2)],
    "Z":        [(0,0,0),(0,0,1),(0,1,0),(1,1,0)],
    "Z_mirror": [(0,0,0),(0,0,1),(0,1,0),(1,0,1)],
}

ALL_ROTATIONS = {name: get_all_rotations(shape)
                 for name, shape in _BASE_SHAPES.items()}

def _cube_faces(x, y, z):
    return [
        [(x,y,z),   (x+1,y,z),   (x+1,y+1,z),   (x,y+1,z)  ],
        [(x,y,z+1), (x+1,y,z+1), (x+1,y+1,z+1), (x,y+1,z+1)],
        [(x,y,z),   (x,y,z+1),   (x,y+1,z+1),   (x,y+1,z)  ],
        [(x+1,y,z), (x+1,y,z+1), (x+1,y+1,z+1), (x+1,y+1,z)],
        [(x,y,z),   (x+1,y,z),   (x+1,y,z+1),   (x,y,z+1)  ],
        [(x,y+1,z), (x+1,y+1,z), (x+1,y+1,z+1), (x,y+1,z+1)],
    ]

def draw_unit_cube(ax, pos, color, alpha=0.78):
    faces = _cube_faces(*pos)
    poly = Poly3DCollection(faces, alpha=alpha)
    poly.set_facecolor(color)
    poly.set_edgecolor("black")
    ax.add_collection3d(poly)

def draw_shape_outline(ax, cells):
    for cell in cells:
        faces = _cube_faces(*cell)
        poly = Poly3DCollection(faces, alpha=0.18)
        poly.set_facecolor("lightsteelblue")
        poly.set_edgecolor((0.2, 0.2, 0.4, 0.35))
        ax.add_collection3d(poly)

def parse_solution(text):
    """
    Parse clingo output text.
    Returns (assign, full_pos, hint_pos, hints, num_copies):
        assign     : {pid(int) -> type_name(str)}
        full_pos   : {pid(int) -> (R,X,Y,Z)}
        hint_pos   : {pid(int) -> (R,X,Y,Z)}
        hints      : set of int pids
        num_copies : int (from numCopies atom, default 1)
    """
    assign = {}
    full_pos = {}
    hint_pos = {}
    hints = set()
    num_copies = 1

    m = re.search(r'Answer: \d+\n(.*)', text)
    if not m:
        return assign, full_pos, hint_pos, hints, num_copies

    for token in m.group(1).split():
        ma = re.match(r'numCopies\((\d+)\)', token)
        if ma:
            num_copies = int(ma.group(1))
            continue

        ma = re.match(r'assignType\((\d+),"([^"]+)"\)', token)
        if ma:
            assign[int(ma.group(1))] = ma.group(2)
            continue

        ma = re.match(r'fullPosition\((\d+),(\d+),(\d+),(\d+),(\d+)\)', token)
        if ma:
            p, r, x, y, z = map(int, ma.groups())
            full_pos[p] = (r, x, y, z)
            continue

        ma = re.match(r'hintPosition\((\d+),(\d+),(\d+),(\d+),(\d+)\)', token)
        if ma:
            p, r, x, y, z = map(int, ma.groups())
            hint_pos[p] = (r, x, y, z)
            continue

        ma = re.match(r'hint\((\d+)\)', token)
        if ma:
            hints.add(int(ma.group(1)))

    return assign, full_pos, hint_pos, hints, num_copies

class PuzzleVisualiser:
    def __init__(self, assign, full_pos, hint_pos, hints, shape_name,
                 num_copies=1, cells_override=None):
        self.assign     = assign
        self.full_pos   = full_pos
        self.hint_pos   = hint_pos
        self.hints      = hints
        self.shape_name = shape_name
        self.num_copies = num_copies

        if cells_override is not None:
            self.cells = cells_override
        else:
            self.cells = SHAPE_CELLS[shape_name](num_copies)

        self.all_pids  = sorted(full_pos.keys())
        self.hint_pids = sorted(hint_pos.keys())

        self.mode      = "Puzzle"
        self.num_shown = len(self.hint_pids)

        self.fig = plt.figure(figsize=(12, 9))
        self.ax  = self.fig.add_subplot(111, projection="3d")

        ax_prev  = plt.axes([0.70, 0.04, 0.09, 0.06])
        ax_next  = plt.axes([0.80, 0.04, 0.09, 0.06])
        ax_radio = plt.axes([0.02, 0.04, 0.17, 0.13])

        self.btn_prev = Button(ax_prev, "◀ Prev")
        self.btn_next = Button(ax_next, "Next ▶")
        self.radio    = RadioButtons(ax_radio, ("Puzzle", "Solution"))

        self.btn_prev.on_clicked(self._on_prev)
        self.btn_next.on_clicked(self._on_next)
        self.radio.on_clicked(self._on_toggle)

        self._redraw()

    def _on_prev(self, _):
        if self.num_shown > 0:
            self.num_shown -= 1
            self._redraw()

    def _on_next(self, _):
        if self.num_shown < self._max():
            self.num_shown += 1
            self._redraw()

    def _on_toggle(self, label):
        self.mode = label
        self.num_shown = self._max()
        self._redraw()

    def _max(self):
        return len(self.hint_pids) if self.mode == "Puzzle" else len(self.all_pids)

    def _active_pids(self):
        pool = self.hint_pids if self.mode == "Puzzle" else self.all_pids
        return pool[: self.num_shown]

    def _pos_map(self):
        return self.hint_pos if self.mode == "Puzzle" else self.full_pos

    def _redraw(self):
        self.ax.clear()

        xs = [c[0] for c in self.cells]
        ys = [c[1] for c in self.cells]
        zs = [c[2] for c in self.cells]
        x_min, x_max = min(xs), max(xs) + 1
        y_min, y_max = min(ys), max(ys) + 1
        z_min, z_max = min(zs), max(zs) + 1
        self.ax.set_xlim(x_min, x_max)
        self.ax.set_ylim(y_min, y_max)
        self.ax.set_zlim(z_min, z_max)
        self.ax.set_xlabel("X")
        self.ax.set_ylabel("Y")
        self.ax.set_zlabel("Z")

        self.ax.set_box_aspect([x_max - x_min, y_max - y_min, (z_max - z_min) * 3])
        self.ax.view_init(elev=45, azim=210)

        draw_shape_outline(self.ax, self.cells)

        pos_map = self._pos_map()
        for pid in self._active_pids():
            if pid not in pos_map or pid not in self.assign:
                continue
            type_name = self.assign[pid]
            r, ox, oy, oz = pos_map[pid]
            rotations = ALL_ROTATIONS.get(type_name, [])
            if r < 1 or r > len(rotations):
                print(f"Warning: rotation {r} out of range for {type_name}")
                continue
            shape = rotations[r - 1]
            color = COLORS.get(type_name, "gray")
            for dx, dy, dz in shape:
                draw_unit_cube(self.ax, (ox + dx, oy + dy, oz + dz), color)

        types_present = set(self.assign.values())
        legend_elements = [
            Line2D([0], [0], marker="s", color="w",
                   markerfacecolor=COLORS[t], markersize=11, label=t)
            for t in COLORS if t in types_present
        ]
        self.ax.legend(handles=legend_elements, loc="upper right", fontsize=8)

        shape_label = SHAPE_LABELS.get(self.shape_name, self.shape_name)
        copies_tag  = f"  [N={self.num_copies}]" if self.num_copies > 1 else ""
        self.ax.set_title(
            f"{shape_label}{copies_tag}  —  {self.mode}  "
            f"({self.num_shown}/{self._max()} pieces shown)",
            fontsize=12,
        )
        self.fig.canvas.draw_idle()

    def show(self):
        plt.show()

def _detect_shape(filename):
    f = os.path.basename(filename).lower()
    if "t_shape" in f or "sol_t" in f:
        return "t_shape"
    if "l_shape" in f or "sol_l" in f:
        return "l_shape"
    if "general" in f:
        return "general_shape"
    return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    sol_file   = sys.argv[1]
    shape_name = sys.argv[2] if len(sys.argv) > 2 else _detect_shape(sol_file)

    if shape_name not in SHAPE_CELLS:
        print(f"Could not determine shape. Specify one of: {list(SHAPE_CELLS)}")
        sys.exit(1)

    with open(sol_file) as fh:
        content = fh.read()

    assign, full_pos, hint_pos, hints, num_copies = parse_solution(content)

    if not full_pos:
        print("No SATISFIABLE answer set found in the solution file.")
        print("Make sure you ran clingo with --models=1 and the output was redirected.")
        sys.exit(1)

    n_pieces = 8 * num_copies
    print(f"Shape      : {SHAPE_LABELS.get(shape_name, shape_name)}")
    print(f"num_copies : {num_copies}  ({n_pieces} pieces, {32*num_copies} cells)")
    print(f"Pieces     : {len(full_pos)} placed")
    print(f"Hints      : {len(hints)} revealed — IDs {sorted(hints)}")
    print(f"Types      : { {pid: assign.get(pid) for pid in sorted(full_pos)} }")

    vis = PuzzleVisualiser(assign, full_pos, hint_pos, hints, shape_name, num_copies)
    vis.show()
