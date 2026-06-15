#!/usr/bin/env python3
"""
random_puzzle.py
────────────────
Single script that generates a random connected 3D polycube, then solves
the tetracube packing puzzle with Clingo and launches the interactive 3D
visualiser.

The --copies N flag scales the puzzle: N copies of each tetracube are used
(N*8 pieces total) and the generated shape contains N*32 cells.

Two shape-generation modes are available:

  Mode 2d (default):
    Grows a random 16-cell polyomino in XY and extrudes to depth 2*N.
    Produces slab-like shapes (every z-layer identical).  Such shapes are
    decomposable: a solution for the depth-2 base stacks N times, so once
    the base footprint is packable the shape is solvable for all N.

  Mode 3d (--mode 3d):
    Grows a random N*32-cell polycube freely in ±x, ±y, ±z, so its layers
    differ and no stacking decomposition exists.  Free 3D polycubes are
    almost never packable at any N (empirically well under 1% — see
    benchmark_3d.py), so this mode relies on retrying many random shapes
    (up to MAX_TRIES) until a satisfiable one is found.

Usage:
    python random_puzzle.py                          # N=1, random seed
    python random_puzzle.py --copies 2               # N=2, 64 cells, 16 pieces
    python random_puzzle.py --seed 42 --copies 2     # fixed seed, N=2
    python random_puzzle.py --mode 3d --copies 1     # true 3D, N=1
    python random_puzzle.py --no-vis                 # solve only, no GUI
"""

import os
import sys
import random
import subprocess
import tempfile
import argparse
import time

HERE = os.path.dirname(os.path.abspath(__file__))

def _neighbors_3d(cell):
    x, y, z = cell
    return {
        (x+1,y,z),(x-1,y,z),
        (x,y+1,z),(x,y-1,z),
        (x,y,z+1),(x,y,z-1),
    }

def _neighbors_2d(cell):
    x, y = cell
    return {(x+1,y),(x-1,y),(x,y+1),(x,y-1)}

def generate_3d_polycube(target, seed=None):
    """
    Grow a random connected 3D polycube with `target` cells using the Eden model.
    Returns a frozenset of (x, y, z) triples normalised so min coords = 0.
    """
    rng = random.Random(seed)
    start = (4, 4, 1)
    shape = {start}
    frontier = _neighbors_3d(start) - shape

    while len(shape) < target:
        if not frontier:
            return generate_3d_polycube(target, rng.randint(0, 10**9))
        cell = rng.choice(sorted(frontier))
        shape.add(cell)
        frontier.discard(cell)
        frontier |= (_neighbors_3d(cell) - shape)

    return _normalise_3d(shape)

def generate_extruded_polyomino(num_copies=1, seed=None):
    """
    Grow a random 16-cell 2D polyomino and extrude to depth 2*num_copies.
    Produces exactly 32*num_copies cells.
    """
    rng = random.Random(seed)
    start = (4, 4)
    shape = {start}
    frontier = _neighbors_2d(start) - shape

    while len(shape) < 16:
        if not frontier:
            return generate_extruded_polyomino(num_copies, rng.randint(0, 10**9))
        cell = rng.choice(sorted(frontier))
        shape.add(cell)
        frontier.discard(cell)
        frontier |= (_neighbors_2d(cell) - shape)

    depth = 2 * num_copies
    cells_3d = set()
    for x, y in shape:
        for z in range(depth):
            cells_3d.add((x, y, z))
    return _normalise_3d(cells_3d)

def _normalise_3d(cells):
    min_x = min(c[0] for c in cells)
    min_y = min(c[1] for c in cells)
    min_z = min(c[2] for c in cells)
    return frozenset((x-min_x, y-min_y, z-min_z) for x,y,z in cells)

def print_shape_ascii(cells_3d):
    max_z = max(z for x,y,z in cells_3d)
    max_x = max(x for x,y,z in cells_3d)
    max_y = max(y for x,y,z in cells_3d)
    n_cells = len(cells_3d)
    print(f"\n  3D polycube — {n_cells} cells, bounding box "
          f"{max_x+1}×{max_y+1}×{max_z+1}:")
    for z in range(max_z + 1):
        layer = {(x, y) for x, y, zz in cells_3d if zz == z}
        n = len(layer)
        print(f"\n  Layer z={z}  ({n} cells):")
        for y in range(max_y, -1, -1):
            row = "  " + "".join(
                "X " if (x, y) in layer else ". "
                for x in range(max_x + 1)
            )
            print(row)
    print()

def cells_to_asp(cells_3d, comment=""):
    lines = [f"% Auto-generated random polycube — {len(cells_3d)} cells"]
    if comment:
        lines.append(f"% {comment}")
    for x, y, z in sorted(cells_3d):
        lines.append(f"cell({x},{y},{z}).")
    return "\n".join(lines) + "\n"

def run_clingo(shape_file, hints, clingo_seed, num_copies=1, timeout=60):
    puzzle_file = os.path.join(HERE, "puzzle.lp")
    tetras_file = os.path.join(HERE, "tetracubes.lp")
    cmd = [
        "clingo",
        shape_file, puzzle_file, tetras_file,
        "-c", f"num_hints={hints}",
        "-c", f"num_copies={num_copies}",
        f"--seed={clingo_seed}",
        "--models=1",
    ]
    t0 = time.perf_counter()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        print("ERROR: 'clingo' not found.  Install: sudo apt install gringo")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        return False, "", time.perf_counter() - t0
    elapsed = time.perf_counter() - t0
    output = result.stdout
    sat = "SATISFIABLE" in output and "UNSATISFIABLE" not in output
    return sat, output, elapsed

def launch_with_cells(cells_3d, sol_file, no_vis, num_copies):
    if no_vis:
        print("\n  --no-vis: skipping visualiser.")
        return

    cell_list = sorted(cells_3d)
    vis_path  = os.path.join(HERE, "visualise.py")

    wrapper = f"""
import sys, os
sys.path.insert(0, {repr(HERE)})
import visualise as V

def _random_cells(num_copies=1):
    return {set(cell_list)!r}

V.SHAPE_CELLS["random_shape"]  = _random_cells
V.SHAPE_LABELS["random_shape"] = "Random 3D Polycube"

with open({repr(sol_file)}) as fh:
    content = fh.read()

assign, full_pos, hint_pos, hints, nc = V.parse_solution(content)
if not full_pos:
    print("No answer set found in", {repr(sol_file)})
    sys.exit(1)

vis = V.PuzzleVisualiser(assign, full_pos, hint_pos, hints, "random_shape",
                         num_copies=nc, cells_override=_random_cells())
V.plt.show()
"""
    with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False,
            prefix="_vis_wrapper_", dir=HERE) as fp:
        fp.write(wrapper)
        wrapper_path = fp.name

    env = os.environ.copy()
    if "QT_QPA_PLATFORM" not in env:
        env["QT_QPA_PLATFORM"] = "wayland"
    try:
        subprocess.run([sys.executable, wrapper_path], env=env)
    finally:
        os.unlink(wrapper_path)

MAX_TRIES = 50

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--seed",       type=int,   default=None,
                        help="Master random seed (default: random)")
    parser.add_argument("--hints",      type=int,   default=5,
                        help="Hint pieces revealed (default: 5)")
    parser.add_argument("--copies",     type=int,   default=1,
                        help="Number of times each tetracube is used (default: 1). "
                             "N copies → 8N pieces, 32N cells.")
    parser.add_argument("--mode",       choices=["3d","2d"], default="2d",
                        help="Shape mode: '2d' = extruded polyomino (default), "
                             "'3d' = true 3D polycube")
    parser.add_argument("--show-shape", action="store_true",
                        help="Print ASCII art of the generated shape")
    parser.add_argument("--no-vis",     action="store_true",
                        help="Skip the visualiser")
    args = parser.parse_args()

    num_copies  = args.copies
    n_pieces    = 8 * num_copies
    n_cells     = 32 * num_copies

    if args.seed is None:
        master_seed = random.randint(0, 10**9)
    else:
        master_seed = args.seed

    mode_label = "True 3D polycube" if args.mode == "3d" else "Extruded 2D polyomino"
    print(f"\n{'='*62}")
    print(f"  Random Tetracube Puzzle — {mode_label}")
    print(f"  Master seed  : {master_seed}")
    print(f"  num_copies   : {num_copies}  ({n_pieces} pieces, {n_cells} cells)")
    print(f"  Hints        : {args.hints}")
    print(f"{'='*62}\n")

    rng = random.Random(master_seed)

    for attempt in range(1, MAX_TRIES + 1):
        shape_seed  = rng.randint(0, 10**9)
        clingo_seed = rng.randint(0, 10**9)

        if args.mode == "3d":
            cells = generate_3d_polycube(n_cells, seed=shape_seed)
        else:
            cells = generate_extruded_polyomino(num_copies, seed=shape_seed)

        max_x = max(c[0] for c in cells)
        max_y = max(c[1] for c in cells)
        max_z = max(c[2] for c in cells)
        print(f"[Attempt {attempt}/{MAX_TRIES}]  shape_seed={shape_seed}  "
              f"bbox={max_x+1}×{max_y+1}×{max_z+1}  cells={len(cells)}")

        if args.show_shape:
            print_shape_ascii(cells)

        asp = cells_to_asp(cells, f"mode={args.mode} num_copies={num_copies} "
                                   f"shape_seed={shape_seed}")
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".lp", delete=False,
                prefix="rand_shape_", dir=HERE) as fp:
            fp.write(asp)
            shape_file = fp.name

        sol_file = os.path.join(HERE, "sol_random.txt")

        print(f"  Solving ...", end="", flush=True)
        sat, output, elapsed = run_clingo(shape_file, args.hints, clingo_seed,
                                          num_copies=num_copies)
        print(f"  {elapsed:.3f}s")

        os.unlink(shape_file)

        if sat:
            print(f"\n  SATISFIABLE — solution found!\n")

            with open(sol_file, "w") as fh:
                fh.write(output)

            shape_save = os.path.join(HERE, "random_shape.lp")
            with open(shape_save, "w") as fh:
                fh.write(asp)

            print(f"  Solution → sol_random.txt")
            print(f"  Shape    → random_shape.lp")
            print(f"\n  Bounding box : {max_x+1} × {max_y+1} × {max_z+1}")
            print(f"  Cells        : {len(cells)} (= {num_copies} × 8 tetracubes × 4 cubes)")

            if args.show_shape:
                print_shape_ascii(cells)

            launch_with_cells(cells, sol_file, args.no_vis, num_copies)
            return

        else:
            print(f"  UNSATISFIABLE — trying another shape ...\n")

    print(f"\nERROR: No solvable shape found in {MAX_TRIES} attempts.")
    print("Try a different seed or increase --copies.")
    sys.exit(1)

if __name__ == "__main__":
    main()
