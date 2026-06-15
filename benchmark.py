#!/usr/bin/env python3
"""
benchmark.py — Performance comparison across shapes and num_copies values.

Measures clingo solving time across difficulty levels (num_hints 0..7)
for T-shape and L-shape at num_copies ∈ {1, 2} and produces a comparison
plot showing how puzzle complexity scales with the number of tetracube copies.

Usage:
    cd KRR2026
    python benchmark.py
"""

import subprocess
import time
import statistics
import os
import sys
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLINGO     = "clingo"
PUZZLE_LP  = os.path.join(SCRIPT_DIR, "puzzle.lp")
TETRAS_LP  = os.path.join(SCRIPT_DIR, "tetracubes.lp")

T_SHAPE_LP = os.path.join(SCRIPT_DIR, "t_shape.lp")
L_SHAPE_LP = os.path.join(SCRIPT_DIR, "l_shape.lp")

CONFIGS = [
    ("T-Shape (N=1)", T_SHAPE_LP, 1),
    ("L-Shape (N=1)", L_SHAPE_LP, 1),
    ("T-Shape (N=2)", T_SHAPE_LP, 2),
    ("L-Shape (N=2)", L_SHAPE_LP, 2),
]

HINTS_RANGE = list(range(8))
NUM_RUNS    = 5
SEED        = 42
TIMEOUT     = 300

DIFFICULTY  = {0: "Harder", 1: "Hard", 2: "Hard",
               3: "Medium", 4: "Medium", 5: "Easy",
               6: "Easy",  7: "Very Easy"}

COLORS_CFG = {
    "T-Shape (N=1)": "#3498db",
    "L-Shape (N=1)": "#e74c3c",
    "T-Shape (N=2)": "#2980b9",
    "L-Shape (N=2)": "#c0392b",
}
LINESTYLE_CFG = {
    "T-Shape (N=1)": "-",
    "L-Shape (N=1)": "-",
    "T-Shape (N=2)": "--",
    "L-Shape (N=2)": "--",
}

def run_once(shape_file, num_hints, seed, num_copies=1):
    """Run clingo once and return (wall_time_seconds, satisfiable)."""
    cmd = [
        CLINGO,
        shape_file, PUZZLE_LP, TETRAS_LP,
        "-c", f"num_hints={num_hints}",
        "-c", f"num_copies={num_copies}",
        f"--seed={seed}",
        "--models=1",
    ]
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=TIMEOUT,
            cwd=SCRIPT_DIR,
        )
        elapsed = time.perf_counter() - start
        sat = b"SATISFIABLE" in proc.stdout
        return elapsed, sat
    except subprocess.TimeoutExpired:
        return TIMEOUT, False

def benchmark_config(label, shape_file, num_copies):
    """Benchmark one (shape, num_copies) pair across all hint levels."""
    results = {}
    n_pieces = 8 * num_copies
    n_cells  = 32 * num_copies
    print(f"\n{'='*60}")
    print(f"  {label}   ({n_pieces} pieces, {n_cells} cells)")
    print(f"{'='*60}")

    for nh in HINTS_RANGE:
        diff = DIFFICULTY[nh]
        print(f"  num_hints={nh}  ({diff})")
        times = []
        for run in range(NUM_RUNS):
            t, sat = run_once(shape_file, nh, SEED + run, num_copies)
            status = "SAT" if sat else ("TIMEOUT" if t >= TIMEOUT else "UNSAT/ERR")
            print(f"    run {run+1}/{NUM_RUNS}: {t:.3f}s  [{status}]")
            times.append(t)
        avg = statistics.mean(times)
        print(f"    → avg {avg:.3f}s")
        results[nh] = times

    return results

def make_plots(all_results):
    """Produce a 2-panel comparison figure."""
    fig = plt.figure(figsize=(16, 7))
    gs  = gridspec.GridSpec(1, 2, figure=fig)

    ax_bar  = fig.add_subplot(gs[0])
    ax_line = fig.add_subplot(gs[1])

    xtick_labels = [f"h={h}\n({DIFFICULTY[h]})" for h in HINTS_RANGE]
    x     = np.arange(len(HINTS_RANGE))
    n_cfg = len(all_results)
    width = 0.18

    for idx, (label, results) in enumerate(all_results.items()):
        avgs   = [statistics.mean(results[h]) for h in HINTS_RANGE]
        offset = (idx - (n_cfg - 1) / 2) * width
        color  = COLORS_CFG[label]
        ls     = LINESTYLE_CFG[label]

        bars = ax_bar.bar(x + offset, avgs, width,
                          label=label, color=color, alpha=0.80)
        for bar, v in zip(bars, avgs):
            if v > 0.005:
                ax_bar.text(bar.get_x() + bar.get_width()/2, v + 0.001,
                            f"{v:.2f}", ha="center", va="bottom", fontsize=5)

        ax_line.plot(HINTS_RANGE, avgs, f"o{ls}",
                     label=label, color=color, linewidth=2)

    ax_bar.set_xticks(x)
    ax_bar.set_xticklabels(xtick_labels, fontsize=7)
    ax_bar.set_ylabel("Time (s)")
    ax_bar.set_title("Average Solving Time by Difficulty and N")
    ax_bar.legend(fontsize=8)
    ax_bar.grid(axis="y", linestyle="--", alpha=0.4)

    ax_line.set_xticks(HINTS_RANGE)
    ax_line.set_xticklabels(xtick_labels, fontsize=7)
    ax_line.set_ylabel("Time (s)")
    ax_line.set_title("Avg Time vs Hints Revealed (solid=N=1, dashed=N=2)")
    ax_line.legend(fontsize=8)
    ax_line.grid(linestyle="--", alpha=0.4)
    ax_line.invert_xaxis()

    fig.suptitle(
        "KRR2026 — Tetracube Puzzle Benchmark\n"
        "T-Shape vs L-Shape, N=1 (32 cells) vs N=2 (64 cells)\n"
        f"(clingo, {NUM_RUNS} runs/config, seed={SEED})",
        fontsize=12,
    )
    plt.tight_layout()

    out = os.path.join(SCRIPT_DIR, "benchmark_results.png")
    plt.savefig(out, dpi=150)
    print(f"\nPlot saved to: {out}")
    plt.show()

def print_summary(all_results):
    print("\n" + "="*80)
    print(f"{'SUMMARY':^80}")
    print("="*80)
    header = f"{'Hints':>6}  {'Difficulty':^12}"
    for label in all_results:
        header += f"  {label:^16}"
    print(header)
    print("-"*80)

    for nh in HINTS_RANGE:
        row = f"{nh:>6}  {DIFFICULTY[nh]:^12}"
        for label, results in all_results.items():
            avg = statistics.mean(results[nh])
            row += f"  {avg:>12.3f}s    "
        print(row)

    print("="*80)

    labels = list(all_results)
    if len(labels) >= 4:
        print("\nSlowdown factor N=2 vs N=1 (per difficulty):")
        for nh in HINTS_RANGE:
            t_n1 = statistics.mean(all_results["T-Shape (N=1)"][nh])
            t_n2 = statistics.mean(all_results["T-Shape (N=2)"][nh])
            factor = t_n2 / t_n1 if t_n1 > 0 else float("inf")
            print(f"  T-shape  hints={nh}: N=1={t_n1:.3f}s  N=2={t_n2:.3f}s  "
                  f"factor={factor:.1f}×")

def main():
    print("KRR2026 — Tetracube Puzzle Benchmark")
    print(f"Configurations : {[c[0] for c in CONFIGS]}")
    print(f"Hints range    : {HINTS_RANGE}")
    print(f"Runs/config    : {NUM_RUNS}")
    print(f"Seed           : {SEED}")
    print(f"Timeout        : {TIMEOUT}s per run")

    all_results = {}
    for label, shape_file, num_copies in CONFIGS:
        all_results[label] = benchmark_config(label, shape_file, num_copies)

    print_summary(all_results)
    make_plots(all_results)

if __name__ == "__main__":
    main()
