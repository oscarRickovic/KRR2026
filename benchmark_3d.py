#!/usr/bin/env python3
"""
benchmark_3d.py — Timing for the NON-decomposable 3D polycube mode.

Contrast with benchmark.py (T/L slabs). Slab shapes are a fixed 16-cell XY
footprint extruded to depth 2N, so a solution at N=1 stacks to any N (easy,
decomposable). The 3D mode grows a free polycube of 32N cells with the Eden
model: layers differ, no stacking decomposition exists, and many instances
are UNSAT. This measures that harder, general family.

For each N and shape seed we generate one polycube and run clingo ONCE
(num_hints=0, max difficulty), recording SAT/UNSAT and wall-clock solve time.
"""

import statistics
import random
import os
import tempfile

import random_puzzle as RP

HERE = os.path.dirname(os.path.abspath(__file__))
NS = [1, 2, 3]
PER_CALL_TIMEOUT = 30
TARGET_SAT = 5
MAX_ATTEMPTS = 400

def bench_one(num_copies, shape_seed, clingo_seed):
    cells = RP.generate_3d_polycube(32 * num_copies, seed=shape_seed)
    asp = RP.cells_to_asp(cells, f"3d N={num_copies} seed={shape_seed}")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".lp", delete=False,
                                     prefix="bench3d_", dir=HERE) as fp:
        fp.write(asp)
        shape_file = fp.name
    try:
        sat, _out, elapsed = RP.run_clingo(
            shape_file, hints=0, clingo_seed=clingo_seed,
            num_copies=num_copies, timeout=PER_CALL_TIMEOUT)
    finally:
        os.unlink(shape_file)
    timed_out = (not sat) and elapsed >= PER_CALL_TIMEOUT - 1
    return sat, elapsed, timed_out

def main():
    print(f"\n{'='*78}")
    print("  3D POLYCUBE BENCHMARK (non-decomposable, num_hints=0)")
    print(f"  collect {TARGET_SAT} SAT per N, max {MAX_ATTEMPTS} attempts, "
          f"timeout {PER_CALL_TIMEOUT}s")
    print(f"{'='*78}\n")
    print(f"{'N':>2} {'cells':>6} {'attempts':>9} {'#SAT':>5} {'SATrate':>8} "
          f"{'#TO':>4} {'SAT mean(s)':>12} {'SAT max(s)':>11} {'UNSAT mean(s)':>14}")
    print("-" * 78)
    rng = random.Random(2026)
    for N in NS:
        sat_times, unsat_times = [], []
        n_to = 0
        attempts = 0
        while len(sat_times) < TARGET_SAT and attempts < MAX_ATTEMPTS:
            attempts += 1
            sat, t, to = bench_one(N, shape_seed=rng.randint(0, 10**9),
                                   clingo_seed=rng.randint(0, 10**9))
            if sat:
                sat_times.append(t)
            else:
                unsat_times.append(t)
                if to:
                    n_to += 1
        n_sat = len(sat_times)
        rate = n_sat / attempts if attempts else float("nan")
        sm = statistics.mean(sat_times) if sat_times else float("nan")
        sx = max(sat_times) if sat_times else float("nan")
        um = statistics.mean(unsat_times) if unsat_times else float("nan")
        print(f"{N:>2} {32*N:>6} {attempts:>9} {n_sat:>5} {rate:>8.2%} {n_to:>4} "
              f"{sm:>12.3f} {sx:>11.3f} {um:>14.3f}")
    print()

if __name__ == "__main__":
    main()
