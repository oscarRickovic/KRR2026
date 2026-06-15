#!/usr/bin/env python3
"""
generate_report_figures.py
─────────────────────────
Generates all 3D figures for the KRR2026 final report.

Figures produced (saved in ./figures/):
  fig_tetracubes_3d.png   — 8 tetracubes rendered in 3D
  fig_shapes_empty_3d.png — T-shape, L-shape, Plus/Cross ghost volumes
  fig_shape_scaling.png   — T-shape N=1 vs N=2 (depth doubling)
  fig_solution_t.png      — T-shape solution
  fig_solution_l.png      — L-shape solution
  fig_solution_cross.png  — Plus/Cross solution
  fig_random_shapes.png   — random polycube examples with solutions
  fig_performance.png     — solve time vs N chart (N=1..7)

Run from KRR2026/:
    python3 generate_report_figures.py
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.lines import Line2D
import numpy as np
import subprocess, os, re, time, random, tempfile

HERE    = os.path.dirname(os.path.abspath(__file__))
FIGURES = os.path.join(HERE, 'figures')
os.makedirs(FIGURES, exist_ok=True)

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

ROTATIONS_DEF = { "I":3, "T":12, "L":24, "Pyramid":8, "O":3, "N":12, "Z":12, "Z_mirror":12 }

_BASE = {
    "I":        [(0,0,0),(0,0,1),(0,0,2),(0,0,3)],
    "T":        [(0,0,0),(0,0,1),(0,0,2),(0,1,1)],
    "L":        [(0,0,0),(0,0,1),(0,0,2),(0,1,0)],
    "Pyramid":  [(0,0,0),(0,0,1),(0,1,0),(1,0,0)],
    "O":        [(0,0,0),(0,0,1),(0,1,0),(0,1,1)],
    "N":        [(0,0,0),(0,0,1),(0,1,1),(0,1,2)],
    "Z":        [(0,0,0),(0,0,1),(0,1,0),(1,1,0)],
    "Z_mirror": [(0,0,0),(0,0,1),(0,1,0),(1,0,1)],
}

_ORI = [
    [1,2,3],[1,3,-2],[1,-2,-3],[1,-3,2],
    [-1,2,-3],[-1,-3,-2],[-1,-2,3],[-1,3,2],
    [2,1,-3],[2,-3,-1],[2,-1,3],[2,3,1],
    [-2,1,3],[-2,3,-1],[-2,-1,-3],[-2,-3,1],
    [3,1,2],[3,2,-1],[3,-1,-2],[3,-2,1],
    [-3,1,-2],[-3,-2,-1],[-3,-1,2],[-3,2,1],
]

def _norm(shape):
    mx,my,mz = min(x for x,y,z in shape),min(y for x,y,z in shape),min(z for x,y,z in shape)
    return sorted((x-mx,y-my,z-mz) for x,y,z in shape)

def _get_rotations(shape):
    seen = []
    for ori in _ORI:
        rot = []
        for x,y,z in shape:
            c=[x,y,z]
            rot.append((c[abs(ori[0])-1]*(1 if ori[0]>0 else -1),
                        c[abs(ori[1])-1]*(1 if ori[1]>0 else -1),
                        c[abs(ori[2])-1]*(1 if ori[2]>0 else -1)))
        r = _norm(rot)
        if r not in seen: seen.append(r)
    return seen

ALL_ROT = {n: _get_rotations(s) for n,s in _BASE.items()}

def _faces(x, y, z):
    return [
        [(x,y,z),(x+1,y,z),(x+1,y+1,z),(x,y+1,z)],
        [(x,y,z+1),(x+1,y,z+1),(x+1,y+1,z+1),(x,y+1,z+1)],
        [(x,y,z),(x,y,z+1),(x,y+1,z+1),(x,y+1,z)],
        [(x+1,y,z),(x+1,y,z+1),(x+1,y+1,z+1),(x+1,y+1,z)],
        [(x,y,z),(x+1,y,z),(x+1,y,z+1),(x,y,z+1)],
        [(x,y+1,z),(x+1,y+1,z),(x+1,y+1,z+1),(x,y+1,z+1)],
    ]

def draw_cube(ax, pos, color, alpha=0.85, edge_alpha=1.0):
    poly = Poly3DCollection(_faces(*pos), alpha=alpha)
    poly.set_facecolor(color)
    poly.set_edgecolor((0,0,0,edge_alpha))
    ax.add_collection3d(poly)

def draw_ghost(ax, cells, color='lightsteelblue', alpha=0.18):
    for cell in cells:
        poly = Poly3DCollection(_faces(*cell), alpha=alpha)
        poly.set_facecolor(color)
        poly.set_edgecolor((0.3,0.3,0.5,0.25))
        ax.add_collection3d(poly)

def setup_ax(ax, cells, title="", elev=30, azim=215):
    xs = [c[0] for c in cells]; ys = [c[1] for c in cells]; zs = [c[2] for c in cells]
    xr,yr,zr = max(xs)-min(xs)+1, max(ys)-min(ys)+1, max(zs)-min(zs)+1
    ax.set_xlim(min(xs)-.3, max(xs)+1.3)
    ax.set_ylim(min(ys)-.3, max(ys)+1.3)
    ax.set_zlim(min(zs)-.3, max(zs)+1.3)
    ax.set_box_aspect([xr, yr, max(zr*2.5, 1)])
    ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel('X', fontsize=7, labelpad=1)
    ax.set_ylabel('Y', fontsize=7, labelpad=1)
    ax.set_zlabel('Z', fontsize=7, labelpad=1)
    ax.tick_params(labelsize=6)
    if title: ax.set_title(title, fontsize=9, pad=4)

def parse_sol(text):
    assign, full_pos, num_copies = {}, {}, 1
    m = re.search(r'Answer: \d+\n(.*)', text)
    if not m: return assign, full_pos, num_copies
    for tok in m.group(1).split():
        ma = re.match(r'numCopies\((\d+)\)', tok)
        if ma: num_copies = int(ma.group(1)); continue
        ma = re.match(r'assignType\((\d+),"([^"]+)"\)', tok)
        if ma: assign[int(ma.group(1))] = ma.group(2); continue
        ma = re.match(r'fullPosition\((\d+),(\d+),(\d+),(\d+),(\d+)\)', tok)
        if ma:
            p,r,x,y,z = map(int,ma.groups()); full_pos[p]=(r,x,y,z)
    return assign, full_pos, num_copies

def render_solution(ax, assign, full_pos, shape_cells, show_ghost=True,
                    elev=30, azim=215, title=""):
    if show_ghost: draw_ghost(ax, shape_cells)
    for pid,(r,ox,oy,oz) in full_pos.items():
        tn = assign[pid]
        for dx,dy,dz in ALL_ROT[tn][r-1]:
            draw_cube(ax,(ox+dx,oy+dy,oz+dz), COLORS[tn])
    setup_ax(ax, shape_cells, title, elev, azim)

def legend_handles():
    return [Line2D([0],[0],marker='s',color='w',markerfacecolor=COLORS[t],
                   markersize=9,label=t) for t in COLORS]

def t_cells(n=1):
    c=set()
    for x in range(4):
        for y in range(4,6):
            for z in range(2*n): c.add((x,y,z))
    for x in range(1,3):
        for y in range(4):
            for z in range(2*n): c.add((x,y,z))
    return c

def l_cells(n=1):
    c=set()
    for x in range(4):
        for y in range(5):
            for z in range(2*n):
                if not(x>=2 and y>=3): c.add((x,y,z))
    return c

def cross_cells(n=1):
    c=set()
    for x in range(4):
        for y in range(1,4):
            for z in range(2*n): c.add((x,y,z))
    for x in range(1,3):
        for z in range(2*n):
            c.add((x,4,z)); c.add((x,0,z))
    return c

def solve(shape_lp, n, seed=42, hints=0, timeout=60):
    cmd = ["clingo", shape_lp,
           os.path.join(HERE,"puzzle.lp"), os.path.join(HERE,"tetracubes.lp"),
           "-c", f"num_copies={n}", "-c", f"num_hints={hints}",
           f"--seed={seed}", "--models=1"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout
    except subprocess.TimeoutExpired:
        return ""

def time_solve(shape_lp, n, seeds=(43,44,45)):
    times = []
    for s in seeds:
        t0=time.perf_counter()
        out = solve(shape_lp, n, seed=s, hints=0)
        t1=time.perf_counter()
        if "SATISFIABLE" in out: times.append(t1-t0)
    return sum(times)/len(times) if times else None

def eden_polyomino(n_cells=16, seed=None):
    rng=random.Random(seed)
    start=(4,4); s={start}; fr={(start[0]+dx,start[1]+dy) for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]}-s
    while len(s)<n_cells:
        if not fr: return eden_polyomino(n_cells, rng.randint(0,10**9))
        c=rng.choice(sorted(fr)); s.add(c); fr.discard(c)
        fr|={(c[0]+dx,c[1]+dy) for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]}-s
    mx=min(x for x,y in s); my=min(y for x,y in s)
    return frozenset((x-mx,y-my) for x,y in s)

def extrude(poly2d, depth=2):
    return frozenset((x,y,z) for x,y in poly2d for z in range(depth))

def cells_to_lp(cells):
    return "\n".join(f"cell({x},{y},{z})." for x,y,z in sorted(cells))

def random_shape_solve(seed, n=1):
    poly = eden_polyomino(16, seed=seed)
    cells = extrude(poly, 2*n)
    lp = cells_to_lp(cells)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lp', delete=False,
                                     dir=HERE) as fp:
        fp.write(lp); fname=fp.name
    out = solve(fname, n, seed=seed+100, hints=0)
    os.unlink(fname)
    if "SATISFIABLE" in out and "UNSATISFIABLE" not in out:
        return cells, out
    return None, None

def fig_tetracubes():
    print("  Generating: fig_tetracubes_3d.png")
    order = ["I","T","L","Pyramid","O","N","Z","Z_mirror"]
    labels = {"Z_mirror": "Z-mirror"}

    fig = plt.figure(figsize=(16, 7))
    for i, name in enumerate(order):
        ax = fig.add_subplot(2, 4, i+1, projection='3d')
        cells = _BASE[name]
        for (x,y,z) in cells:
            draw_cube(ax,(x,y,z), COLORS[name], alpha=0.88)
        all_c = cells
        xs=[c[0] for c in all_c]; ys=[c[1] for c in all_c]; zs=[c[2] for c in all_c]
        pad=0.4
        ax.set_xlim(min(xs)-pad, max(xs)+1+pad)
        ax.set_ylim(min(ys)-pad, max(ys)+1+pad)
        ax.set_zlim(min(zs)-pad, max(zs)+1+pad)
        span = max(max(xs)-min(xs)+1, max(ys)-min(ys)+1, max(zs)-min(zs)+1)
        ax.set_box_aspect([span,span,span])
        ax.view_init(elev=28, azim=45)
        ax.set_xticks([]); ax.set_yticks([]); ax.set_zticks([])
        ax.set_xlabel(''); ax.set_ylabel(''); ax.set_zlabel('')
        display = labels.get(name, name)
        rot = ROTATIONS_DEF[name]
        ax.set_title(f"{display}\n({rot} rotation{'s' if rot>1 else ''})",
                     fontsize=10, fontweight='bold', color=COLORS[name])

    fig.suptitle("The 8 Standard Tetracubes", fontsize=14, fontweight='bold', y=1.01)
    plt.tight_layout(pad=1.0)
    plt.savefig(os.path.join(FIGURES,'fig_tetracubes_3d.png'), dpi=150, bbox_inches='tight')
    plt.close()

def fig_empty_shapes():
    print("  Generating: fig_shapes_empty_3d.png")
    shapes = [("T-Shape\n(32 cells)", t_cells(1)),
              ("L-Shape\n(32 cells)", l_cells(1)),
              ("Plus/Cross\n(32 cells)", cross_cells(1))]
    ghost_colors = ['#3498db','#e74c3c','#9b59b6']

    fig = plt.figure(figsize=(15, 5))
    for i,(title,cells) in enumerate(shapes):
        ax = fig.add_subplot(1,3,i+1,projection='3d')
        draw_ghost(ax, cells, color=ghost_colors[i], alpha=0.35)
        setup_ax(ax, cells, title, elev=32, azim=210)
    fig.suptitle("Target Volume Configurations (N=1, depth=2)", fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES,'fig_shapes_empty_3d.png'), dpi=150, bbox_inches='tight')
    plt.close()

def fig_scaling():
    print("  Generating: fig_shape_scaling.png")
    fig = plt.figure(figsize=(14, 5))
    pairs = [("T-Shape  N=1\n(8 pieces · 32 cells · depth 2)", t_cells(1), '#3498db'),
             ("T-Shape  N=2\n(16 pieces · 64 cells · depth 4)", t_cells(2), '#2980b9'),
             ("L-Shape  N=1\n(8 pieces · 32 cells · depth 2)", l_cells(1), '#e74c3c'),
             ("L-Shape  N=2\n(16 pieces · 64 cells · depth 4)", l_cells(2), '#c0392b')]
    for i,(title,cells,col) in enumerate(pairs):
        ax = fig.add_subplot(1,4,i+1,projection='3d')
        draw_ghost(ax, cells, color=col, alpha=0.38)
        setup_ax(ax, cells, title, elev=32, azim=210)
    fig.suptitle("Volume Scaling with num_copies (N)", fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES,'fig_shape_scaling.png'), dpi=150, bbox_inches='tight')
    plt.close()

def fig_solution(sol_file, cells_fn, outname, title):
    print(f"  Generating: {outname}")
    with open(sol_file) as f: text = f.read()
    assign, full_pos, nc = parse_sol(text)
    if not full_pos: print(f"    WARNING: no solution in {sol_file}"); return

    cells = cells_fn(nc)
    fig = plt.figure(figsize=(8, 6))
    ax  = fig.add_subplot(111, projection='3d')
    render_solution(ax, assign, full_pos, cells, show_ghost=True,
                    elev=30, azim=215, title=title)
    ax.legend(handles=legend_handles(), loc='upper right', fontsize=7,
              ncol=2, framealpha=0.7)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES, outname), dpi=150, bbox_inches='tight')
    plt.close()

def fig_random():
    print("  Generating: fig_random_shapes.png")
    seeds = [77, 143, 256, 512]
    found = []
    for s in seeds:
        cells, out = random_shape_solve(s, n=1)
        if out:
            assign, full_pos, nc = parse_sol(out)
            if full_pos:
                found.append((cells, assign, full_pos, f"Random (seed={s})"))
        if len(found) >= 3: break

    if not found:
        print("    WARNING: could not generate random shapes"); return

    n = len(found)
    fig = plt.figure(figsize=(5*n+1, 5))
    for i,(cells,assign,full_pos,title) in enumerate(found):
        ax = fig.add_subplot(1,n,i+1,projection='3d')
        render_solution(ax, assign, full_pos, cells, show_ghost=True,
                        elev=30, azim=215, title=title)

    fig.legend(handles=legend_handles(), loc='lower center',
               ncol=4, fontsize=8, bbox_to_anchor=(0.5,-0.02))
    fig.suptitle("Random 32-Cell Polycube Puzzles (Extruded 2D, depth=2)",
                 fontsize=12, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES,'fig_random_shapes.png'), dpi=150, bbox_inches='tight')
    plt.close()

TIMING = {
    "T-Shape": {
        1: 0.030, 2: 0.174, 3: 0.441, 4: 0.837,
        5: 1.673, 6: 2.819, 7: 3.986,
    },
    "L-Shape": {
        1: 0.030, 2: 0.158, 3: 0.413, 4: 0.892,
        5: 1.855, 6: 3.679, 7: 6.012,
    },
}

def fig_performance():
    print("  Generating: fig_performance.png")
    ns = list(range(1,8))
    cells_n = [32*n for n in ns]
    pieces_n = [8*n  for n in ns]

    fig = plt.figure(figsize=(16,6))
    gs  = gridspec.GridSpec(1,3,figure=fig,wspace=0.35)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])
    ax3 = fig.add_subplot(gs[2])

    colors = {"T-Shape":"#3498db","L-Shape":"#e74c3c"}
    markers= {"T-Shape":"o","L-Shape":"s"}

    for label,data in TIMING.items():
        times = [data[n] for n in ns]
        ax1.plot(ns,times,f"{markers[label]}-",color=colors[label],
                 linewidth=2,markersize=6,label=label)
        ax2.plot(ns,times,f"{markers[label]}-",color=colors[label],
                 linewidth=2,markersize=6,label=label)
        ax1.annotate(f"{times[-1]:.2f}s",xy=(7,times[-1]),
                     xytext=(6.5,times[-1]+0.1),fontsize=7,color=colors[label])

    t_times = [TIMING["T-Shape"][n] for n in ns]
    log_n = np.log(ns); log_t = np.log(t_times)
    coeff = np.polyfit(log_n, log_t, 1)
    exp = coeff[0]
    ns_fine = np.linspace(1,7,100)
    ax2.plot(ns_fine, np.exp(coeff[1])*ns_fine**coeff[0],'--',
             color='gray',linewidth=1.2,label=f'fit ∝ N^{exp:.2f}')

    ax1.set_xlabel("num_copies (N)", fontsize=10)
    ax1.set_ylabel("Avg solve time (s)", fontsize=10)
    ax1.set_title("Solve Time vs N  (linear scale)", fontsize=11)
    ax1.legend(fontsize=9); ax1.grid(alpha=0.3)
    ax1.set_xticks(ns)
    twin1 = ax1.twiny()
    twin1.set_xlim(ax1.get_xlim())
    twin1.set_xticks(ns)
    twin1.set_xticklabels([f"{32*n}" for n in ns], fontsize=7)
    twin1.set_xlabel("Total cells", fontsize=8)

    ax2.set_xlabel("num_copies (N)", fontsize=10)
    ax2.set_ylabel("Avg solve time (s, log)", fontsize=10)
    ax2.set_title(f"Solve Time vs N  (log scale,\nT-shape fit: N^{exp:.2f})", fontsize=11)
    ax2.set_yscale('log'); ax2.legend(fontsize=9); ax2.grid(alpha=0.3, which='both')
    ax2.set_xticks(ns)

    w=0.35
    x=np.arange(len(ns))
    t_avgs = [TIMING["T-Shape"][n] for n in ns]
    l_avgs = [TIMING["L-Shape"][n] for n in ns]
    bars_t = ax3.bar(x-w/2, t_avgs, w, label="T-Shape", color=colors["T-Shape"], alpha=0.85)
    bars_l = ax3.bar(x+w/2, l_avgs, w, label="L-Shape", color=colors["L-Shape"], alpha=0.85)
    ax3.set_xlabel("num_copies (N)", fontsize=10)
    ax3.set_ylabel("Avg solve time (s)", fontsize=10)
    ax3.set_title("T-Shape vs L-Shape\nSolve Time by N", fontsize=11)
    ax3.set_xticks(x); ax3.set_xticklabels([str(n) for n in ns])
    ax3.legend(fontsize=9); ax3.grid(axis='y',alpha=0.3)
    for bar,v in zip(bars_t,t_avgs):
        if v>0.3: ax3.text(bar.get_x()+bar.get_width()/2,v+0.05,
                            f"{v:.2f}",ha='center',va='bottom',fontsize=6)
    for bar,v in zip(bars_l,l_avgs):
        if v>0.3: ax3.text(bar.get_x()+bar.get_width()/2,v+0.05,
                            f"{v:.2f}",ha='center',va='bottom',fontsize=6)

    fig.suptitle(
        "KRR2026 — Tetracube Puzzle Complexity: Solve Time vs num_copies (N=1..7)\n"
        "Hardest difficulty (0 hints), avg of 3 random seeds",
        fontsize=12, fontweight='bold', y=1.02
    )
    plt.savefig(os.path.join(FIGURES,'fig_performance.png'), dpi=150, bbox_inches='tight')
    plt.close()

def main():
    print("Generating all report figures...\n")

    fig_tetracubes()
    fig_empty_shapes()
    fig_scaling()

    for sol, cells_fn, out, title in [
        ("sol_t.txt",       t_cells,     "fig_solution_t.png",
         "T-Shape Solution  (N=1, 8 pieces, 32 cells)"),
        ("sol_l.txt",       l_cells,     "fig_solution_l.png",
         "L-Shape Solution  (N=1, 8 pieces, 32 cells)"),
        ("sol_general.txt", cross_cells, "fig_solution_cross.png",
         "Plus/Cross Solution  (N=1, 8 pieces, 32 cells)"),
    ]:
        sol_path = os.path.join(HERE, sol)
        if os.path.exists(sol_path):
            fig_solution(sol_path, cells_fn, out, title)
        else:
            print(f"  SKIP {out}: {sol} not found (run clingo first)")

    fig_random()
    fig_performance()

    print(f"\nAll figures saved to {FIGURES}/")

if __name__ == "__main__":
    main()
