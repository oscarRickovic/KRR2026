#!/usr/bin/env python3
"""
verify.py — Independently verify an ASP tetracube solution.

Checks (without trusting clingo):
  1. Correct number of pieces: 8*num_copies, each type used exactly num_copies times
  2. All rotation IDs are within valid range per piece type
  3. All piece cells lie within the declared shape cell set
  4. No two pieces share a cell (no overlap)
  5. Full coverage: every cell covered, total = 32*num_copies
  6. Hint piece IDs are a valid subset of placed IDs

num_copies is auto-detected from the solution file (numCopies(N) atom).
It can also be overridden with --copies N.

Usage:
    python verify.py sol_t.txt t_shape
    python verify.py sol_l.txt l_shape
    python verify.py sol_general.txt general_shape
    python verify.py sol_t2.txt t_shape --copies 2
"""

import sys
import re
import argparse

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
    """Plus/Cross: 4×3 main body + top/bottom 2×1 arms, depth 2*num_copies."""
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

_ORIENTATIONS = [
    [1,2,3],[1,3,-2],[1,-2,-3],[1,-3,2],
    [-1,2,-3],[-1,-3,-2],[-1,-2,3],[-1,3,2],
    [2,1,-3],[2,-3,-1],[2,-1,3],[2,3,1],
    [-2,1,3],[-2,3,-1],[-2,-1,-3],[-2,-3,1],
    [3,1,2],[3,2,-1],[3,-1,-2],[3,-2,1],
    [-3,1,-2],[-3,-2,-1],[-3,-1,2],[-3,2,1],
]

def _normalize(shape):
    mx = min(x for x,y,z in shape)
    my = min(y for x,y,z in shape)
    mz = min(z for x,y,z in shape)
    return sorted((x-mx, y-my, z-mz) for x,y,z in shape)

def _get_all_rotations(shape):
    seen = []
    for ori in _ORIENTATIONS:
        rotated = []
        for x, y, z in shape:
            coords = [x, y, z]
            rx = coords[abs(ori[0])-1] * (1 if ori[0]>0 else -1)
            ry = coords[abs(ori[1])-1] * (1 if ori[1]>0 else -1)
            rz = coords[abs(ori[2])-1] * (1 if ori[2]>0 else -1)
            rotated.append((rx, ry, rz))
        r = _normalize(rotated)
        if r not in seen:
            seen.append(r)
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

ALL_ROTATIONS = {name: _get_all_rotations(s) for name, s in _BASE_SHAPES.items()}

def parse_solution(text):
    """
    Parse clingo output. Returns (assign, full_pos, hints, num_copies).
      assign    : {pid -> type_name}
      full_pos  : {pid -> (R, X, Y, Z)}
      hints     : set of pid ints
      num_copies: int (from numCopies/1 atom, default 1)
    """
    assign   = {}
    full_pos = {}
    hints    = set()
    num_copies = 1

    m = re.search(r'Answer: \d+\n(.*)', text)
    if not m:
        return assign, full_pos, hints, num_copies

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
        ma = re.match(r'hint\((\d+)\)', token)
        if ma:
            hints.add(int(ma.group(1)))

    return assign, full_pos, hints, num_copies

PASS = "\033[92m  PASS\033[0m"
FAIL = "\033[91m  FAIL\033[0m"

def verify(sol_file, shape_name, copies_override=None):
    print(f"\n{'='*62}")
    print(f"  Verifying: {sol_file}  [{shape_name}]")
    print(f"{'='*62}")

    with open(sol_file) as fh:
        content = fh.read()

    if "SATISFIABLE" not in content:
        print(f"{FAIL}  Solution file does not contain a SATISFIABLE result.")
        return False

    assign, full_pos, hints, num_copies = parse_solution(content)

    if copies_override is not None:
        num_copies = copies_override

    n_pieces  = 8 * num_copies
    n_cells   = 32 * num_copies

    print(f"\n  num_copies = {num_copies}  →  {n_pieces} pieces,  {n_cells} cells")

    valid_cells = SHAPE_CELLS[shape_name](num_copies)
    all_ok = True

    type_counts = {}
    for t in assign.values():
        type_counts[t] = type_counts.get(t, 0) + 1
    expected_types = set(_BASE_SHAPES)
    count_ok = (len(full_pos) == n_pieces)
    dist_ok  = (set(type_counts.keys()) == expected_types and
                all(c == num_copies for c in type_counts.values()))
    ok = count_ok and dist_ok
    print(f"\n[1] Correct pieces: {n_pieces} placed, each type used {num_copies}×")
    print(f"    Found {len(full_pos)} pieces; type counts: "
          f"{ {t: type_counts.get(t,0) for t in sorted(expected_types)} }")
    print(PASS if ok else FAIL)
    all_ok &= ok

    print(f"\n[2] Rotation IDs in valid range")
    rot_ok = True
    for pid, (r, x, y, z) in sorted(full_pos.items()):
        type_name = assign.get(pid)
        max_r = len(ALL_ROTATIONS.get(type_name, []))
        if r < 1 or r > max_r:
            print(f"    {FAIL} piece {pid} ({type_name}): rotation {r} out of 1..{max_r}")
            rot_ok = False
        else:
            print(f"    piece {pid:3d} ({type_name:8s}): rotation {r:2d} / {max_r:2d}  OK")
    print(PASS if rot_ok else FAIL)
    all_ok &= rot_ok

    piece_cells = {}
    for pid, (r, ox, oy, oz) in full_pos.items():
        type_name = assign[pid]
        shape = ALL_ROTATIONS[type_name][r - 1]
        piece_cells[pid] = {(ox+dx, oy+dy, oz+dz) for dx, dy, dz in shape}

    print(f"\n[3] All piece cells lie within the {shape_name} cell set")
    bounds_ok = True
    for pid, cells in sorted(piece_cells.items()):
        out = cells - valid_cells
        if out:
            print(f"    {FAIL} piece {pid} ({assign[pid]}): {len(out)} cell(s) outside: {sorted(out)}")
            bounds_ok = False
        else:
            print(f"    piece {pid:3d} ({assign[pid]:8s}): all 4 cells inside  OK")
    print(PASS if bounds_ok else FAIL)
    all_ok &= bounds_ok

    print(f"\n[4] No overlapping cells between pieces")
    overlap_ok = True
    pids = sorted(piece_cells)
    for i in range(len(pids)):
        for j in range(i + 1, len(pids)):
            p1, p2 = pids[i], pids[j]
            shared = piece_cells[p1] & piece_cells[p2]
            if shared:
                print(f"    {FAIL} pieces {p1} ({assign[p1]}) and {p2} ({assign[p2]}) "
                      f"share {len(shared)} cell(s): {sorted(shared)}")
                overlap_ok = False
    n_pairs = len(pids) * (len(pids) - 1) // 2
    if overlap_ok:
        print(f"    No overlaps found across all {n_pairs} pairs")
    print(PASS if overlap_ok else FAIL)
    all_ok &= overlap_ok

    print(f"\n[5] Full coverage — every cell covered exactly once")
    all_occupied = set()
    for cells in piece_cells.values():
        all_occupied |= cells
    uncovered = valid_cells - all_occupied
    coverage_ok = (len(uncovered) == 0 and len(all_occupied) == n_cells)
    print(f"    Valid cells     : {len(valid_cells)}")
    print(f"    Occupied cells  : {len(all_occupied)}")
    print(f"    Uncovered cells : {len(uncovered)}")
    if uncovered:
        print(f"    Missing: {sorted(uncovered)}")
    print(PASS if coverage_ok else FAIL)
    all_ok &= coverage_ok

    print(f"\n[6] Hint pieces are valid placed piece IDs")
    hint_ok = hints.issubset(set(full_pos.keys()))
    print(f"    {len(hints)} hints: IDs {sorted(hints)} → "
          f"types {[assign.get(h,'?') for h in sorted(hints)]}")
    print(PASS if hint_ok else FAIL)
    all_ok &= hint_ok

    print(f"\n{'='*62}")
    if all_ok:
        print(f"\033[92m  ALL CHECKS PASSED — solution is correct!\033[0m")
    else:
        print(f"\033[91m  SOME CHECKS FAILED — solution is invalid.\033[0m")
    print(f"{'='*62}\n")

    return all_ok

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sol_file",   help="Clingo solution file (e.g. sol_t.txt)")
    parser.add_argument("shape_name", help=f"Shape name: {list(SHAPE_CELLS)}")
    parser.add_argument("--copies", type=int, default=None,
                        help="Override num_copies (auto-detected from solution by default)")
    args = parser.parse_args()

    if args.shape_name not in SHAPE_CELLS:
        print(f"Unknown shape '{args.shape_name}'. Choose: {list(SHAPE_CELLS)}")
        sys.exit(1)

    ok = verify(args.sol_file, args.shape_name, copies_override=args.copies)
    sys.exit(0 if ok else 1)
