#!/usr/bin/env python3
"""
Analyze compression algorithms for LUT tables.
Compares diff-of-diffs, group-of-4, and linear approximation algorithms.
"""

import math
import os
from dataclasses import dataclass
from typing import List, Tuple, Optional

TABLE_FILES = [
    "log2.txt",
    "pow2.txt",
    "recp.txt",
    "sqrt1_to_2.txt",
    "sqrt2_to_4.txt",
    "rsqrt1_to_2.txt",
    "rsqrt2_to_4.txt",
]

COLUMN_NAMES = ["C0", "C1", "C2"]
ORIGINAL_WIDTHS = [26, 16, 10]


def parse_table(filepath: str) -> Tuple[str, List[List[int]]]:
    """Parse a .txt file, return (function_name, list of [c0, c1, c2] rows)."""
    with open(filepath, "r") as f:
        lines = f.readlines()

    # Find separator
    sep_idx = 0
    for i, line in enumerate(lines):
        if "---" in line:
            sep_idx = i + 1
            break

    # Extract function name from header
    func_name = "unknown"
    for line in lines[:sep_idx - 1]:
        if "# Function:" in line:
            func_name = line.split("# Function:")[1].split(",")[0].strip()
            break

    # Parse data rows
    data = []
    for line in lines[sep_idx:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        row = [int(p.strip(), 16) for p in parts]
        data.append(row)

    return func_name, data


def bit_cost(values: List[int]) -> int:
    """Compute bits required to store a list of signed integers."""
    if not values:
        return 0
    max_abs = max(abs(v) for v in values)
    if max_abs == 0:
        return 1
    return math.ceil(math.log2(max_abs + 1))


def get_valid_segmentations(n: int, min_seg: int = 8) -> List[List[int]]:
    """
    Get all valid segmentations of n entries.
    Segments must be 2^N sized and at least min_seg entries.
    Returns list of segment sizes.
    """
    # For n=64: possible uniform segment sizes are 64, 32, 16, 8
    # For n=128: 128, 64, 32, 16, 8
    result = []
    seg_size = n
    while seg_size >= min_seg:
        if n % seg_size == 0:
            result.append([seg_size] * (n // seg_size))
        seg_size //= 2
    return result


def compute_diff_of_diffs_cost(column: List[int]) -> int:
    """
    Compute cost for diff-of-diffs algorithm (no segmentation).
    Store: col[0], col[1]-col[0], (col[i+1]-col[i])-(col[i]-col[i-1]) for i>=2
    Total cost = 1*anchor_bits + 1*diff_bits + (N-2)*dod_bits
    """
    if len(column) == 0:
        return 0
    if len(column) == 1:
        return bit_cost([column[0]])

    # Anchor bits (store 1 value)
    anchor_bits = bit_cost([column[0]])

    # First diff bits (store 1 value)
    diff1 = column[1] - column[0]
    diff_bits = bit_cost([diff1])

    # Diff of diffs bits (store N-2 values at same bit-width)
    diffs_of_diffs = []
    for i in range(2, len(column)):
        d1 = column[i] - column[i - 1]
        d0 = column[i - 1] - column[i - 2]
        dod = d1 - d0
        diffs_of_diffs.append(dod)

    if diffs_of_diffs:
        dod_bit_width = bit_cost(diffs_of_diffs)
        dod_total = dod_bit_width * len(diffs_of_diffs)
    else:
        dod_total = 0

    return anchor_bits + diff_bits + dod_total


def compute_segmented_dod_cost(column: List[int], seg_size: int) -> int:
    """
    Compute cost for segmented diff-of-diffs algorithm.
    Each segment has its own anchor and first_diff.
    """
    n = len(column)
    total_cost = 0

    for seg_start in range(0, n, seg_size):
        seg_end = min(seg_start + seg_size, n)
        segment = column[seg_start:seg_end]

        if len(segment) == 0:
            continue
        elif len(segment) == 1:
            total_cost += bit_cost([segment[0]])
        else:
            anchor_bits = bit_cost([segment[0]])
            diff_bits = bit_cost([segment[1] - segment[0]])

            dods = []
            for i in range(2, len(segment)):
                d1 = segment[i] - segment[i-1]
                d0 = segment[i-1] - segment[i-2]
                dods.append(d1 - d0)

            if dods:
                dod_bw = bit_cost(dods)
                dod_cost = dod_bw * len(dods)
            else:
                dod_cost = 0

            total_cost += anchor_bits + diff_bits + dod_cost

    return total_cost


def compute_group_of_4_cost(column: List[int], seg_sizes: List[int]) -> int:
    """
    Compute cost for group-of-4 algorithm.
    Per group of 4: store full[0], diff[1], dod[2], dod[3]
    Within each segment, compute max bit-width for each category.
    """
    total_cost = 0

    for seg_size in seg_sizes:
        for seg_start in range(0, len(column), seg_size):
            seg_end = min(seg_start + seg_size, len(column))
            segment = column[seg_start:seg_end]

            # Collect all values for each category in this segment
            anchors = []
            diffs1 = []
            dods2 = []
            dods3 = []

            # Process in groups of 4
            for g in range(0, len(segment), 4):
                group = segment[g : g + 4]
                if len(group) == 0:
                    continue

                # Anchor: full value
                anchors.append(group[0])

                if len(group) >= 2:
                    # Diff for index 1
                    diff1 = group[1] - group[0]
                    diffs1.append(diff1)

                if len(group) >= 3:
                    # Diff-of-diff for index 2
                    d2 = group[2] - group[1]
                    d1 = group[1] - group[0]
                    dod2 = d2 - d1
                    dods2.append(dod2)

                if len(group) == 4:
                    # Diff-of-diff for index 3
                    d3 = group[3] - group[1]
                    d1 = group[1] - group[0]
                    dod3 = d3 - d1
                    dods3.append(dod3)

            # Compute cost for this segment
            if anchors:
                anchor_bits = bit_cost(anchors) * len(anchors)
                total_cost += anchor_bits
            if diffs1:
                diff_bits = bit_cost(diffs1) * len(diffs1)
                total_cost += diff_bits
            if dods2:
                dod2_bits = bit_cost(dods2) * len(dods2)
                total_cost += dod2_bits
            if dods3:
                dod3_bits = bit_cost(dods3) * len(dods3)
                total_cost += dod3_bits

    return total_cost


def find_best_line(group: List[int]) -> Tuple[float, float, List[int]]:
    """
    Find mx+b that minimizes max error for the group.
    x ranges from 0 to len(group)-1.
    Returns (m, b, residues).

    For hardware, we want the line that minimizes max(abs(residue)).
    This is a Chebyshev approximation problem.
    Simplified: use endpoints to define line, then compute residues.
    """
    n = len(group)
    if n == 0:
        return (0, 0, [])
    if n == 1:
        return (0, group[0], [0])

    # Use first and last points to define line
    x0, x1 = 0, n - 1
    y0, y1 = group[0], group[-1]

    if x1 == x0:
        m = 0
    else:
        m = (y1 - y0) / (x1 - x0)

    b = y0 - m * x0

    # Compute residues
    residues = []
    for i, y in enumerate(group):
        approx = m * i + b
        residue = round(y - approx)
        residues.append(residue)

    return (m, b, residues)


def compute_linear_approx_cost(
    column: List[int], group_size: int, seg_sizes: List[int]
) -> Tuple[int, int, int]:
    """
    Compute cost for linear approximation algorithm.
    group_size: G (2, 4, or 8)
    Returns (m_bits, b_bits, residue_bits).
    """
    m_values = []
    b_values = []
    all_residues = []
    num_groups = 0

    for seg_size in seg_sizes:
        for seg_start in range(0, len(column), seg_size):
            seg_end = min(seg_start + seg_size, len(column))
            segment = column[seg_start:seg_end]

            # Process in groups of G
            for g in range(0, len(segment), group_size):
                group = segment[g : g + group_size]
                if len(group) == 0:
                    continue

                m, b, residues = find_best_line(group)
                m_values.append(m)
                b_values.append(b)
                all_residues.extend(residues)
                num_groups += 1

    # Cost for M and B tables: each group stores its own m, b
    # Each M and B value stored at the bit-width of the max across all groups
    if m_values:
        m_bit_width = bit_cost([round(x) for x in m_values])
        b_bit_width = bit_cost([round(x) for x in b_values])
        m_cost = m_bit_width * num_groups
        b_cost = b_bit_width * num_groups
    else:
        m_cost = 0
        b_cost = 0

    # Residue cost: all residues stored at the bit-width of max residue across all groups
    if all_residues:
        residue_bit_width = bit_cost(all_residues)
        residue_cost = residue_bit_width * len(all_residues)
    else:
        residue_cost = 0

    return (m_cost, b_cost, residue_cost)


def compute_original_cost(column: List[int], col_idx: int) -> int:
    """Compute original uncompressed cost: N entries * bit_width."""
    n = len(column)
    bit_width = bit_cost(column)
    return n * bit_width


@dataclass
class ColumnResult:
    func: str
    col: str
    n_entries: int
    original_bits: int
    diff_of_diffs_bits: int
    segmented_dod_bits: int
    segmented_dod_size: int
    group_of_4_bits: Optional[int]
    group_of_4_seg: Optional[str]
    linear_g2_bits: Optional[int]
    linear_g2_seg: Optional[str]
    linear_g4_bits: Optional[int]
    linear_g4_seg: Optional[str]
    linear_g8_bits: Optional[int]
    linear_g8_seg: Optional[str]
    best_algo: str
    best_bits: int


def analyze_column(func: str, col: str, column: List[int]) -> ColumnResult:
    """Analyze a single column with all algorithms."""
    n = len(column)
    col_idx = COLUMN_NAMES.index(col)
    original_bits = compute_original_cost(column, col_idx)
    dod_bits = compute_diff_of_diffs_cost(column)

    # Segmented diff-of-diffs (try segment sizes 32, 16, 8)
    best_seg_dod_bits = dod_bits  # Default to no segmentation
    best_seg_dod_size = n
    for seg_size in [32, 16, 8]:
        if n % seg_size == 0:
            cost = compute_segmented_dod_cost(column, seg_size)
            if cost < best_seg_dod_bits:
                best_seg_dod_bits = cost
                best_seg_dod_size = seg_size

    # Group of 4
    best_g4_bits = None
    best_g4_seg = None
    segs = get_valid_segmentations(n)
    for seg_sizes in segs:
        cost = compute_group_of_4_cost(column, seg_sizes)
        if best_g4_bits is None or cost < best_g4_bits:
            best_g4_bits = cost
            best_g4_seg = "x".join(map(str, seg_sizes))

    # Linear approximation for G=2,4,8
    linear_results = {}
    for g in [2, 4, 8]:
        if n % g != 0:
            linear_results[g] = (None, None)
            continue
        best_bits = None
        best_seg = None
        for seg_sizes in segs:
            if any(s % g != 0 for s in seg_sizes):
                continue
            m_bits, b_bits, residue_bits = compute_linear_approx_cost(
                column, g, seg_sizes
            )
            if m_bits is not None:
                total = m_bits + b_bits + residue_bits
                if best_bits is None or total < best_bits:
                    best_bits = total
                    best_seg = "x".join(map(str, seg_sizes))
        linear_results[g] = (best_bits, best_seg)

    # Determine best
    candidates = [
        ("diff-of-diffs", dod_bits),
        ("seg-dod-" + str(best_seg_dod_size), best_seg_dod_bits) if best_seg_dod_size != n else ("seg-dod", best_seg_dod_bits),
        ("group-of-4", best_g4_bits),
        ("linear-G2", linear_results[2][0]),
        ("linear-G4", linear_results[4][0]),
        ("linear-G8", linear_results[8][0]),
    ]

    best_algo = "diff-of-diffs"
    best_bits = dod_bits
    for name, bits in candidates:
        if bits is not None and bits < best_bits:
            best_algo = name
            best_bits = bits

    return ColumnResult(
        func=func,
        col=col,
        n_entries=n,
        original_bits=original_bits,
        diff_of_diffs_bits=dod_bits,
        segmented_dod_bits=best_seg_dod_bits,
        segmented_dod_size=best_seg_dod_size,
        group_of_4_bits=best_g4_bits,
        group_of_4_seg=best_g4_seg,
        linear_g2_bits=linear_results[2][0],
        linear_g2_seg=linear_results[2][1],
        linear_g4_bits=linear_results[4][0],
        linear_g4_seg=linear_results[4][1],
        linear_g8_bits=linear_results[8][0],
        linear_g8_seg=linear_results[8][1],
        best_algo=best_algo,
        best_bits=best_bits,
    )


def main():
    print("=" * 120)
    print("LUT COMPRESSION ANALYSIS")
    print("=" * 120)

    all_results = []

    for table_file in TABLE_FILES:
        if not os.path.exists(table_file):
            print(f"WARNING: {table_file} not found, skipping")
            continue

        func_name, data = parse_table(table_file)
        print(f"\n{table_file} ({func_name}): {len(data)} entries")

        for col_idx, col_name in enumerate(COLUMN_NAMES):
            column = [row[col_idx] for row in data]
            result = analyze_column(func_name, col_name, column)
            all_results.append(result)

            print(
                f"  {col_name}: orig={result.original_bits:4d} bits, "
                f"dod={result.diff_of_diffs_bits:4d}, "
                f"seg-dod-{result.segmented_dod_size}={result.segmented_dod_bits:4d}, "
                f"g4={result.group_of_4_bits} ({result.group_of_4_seg}), "
                f"lin-G2={result.linear_g2_bits} ({result.linear_g2_seg}), "
                f"lin-G4={result.linear_g4_bits} ({result.linear_g4_seg}), "
                f"lin-G8={result.linear_g8_bits} ({result.linear_g8_seg})"
            )
            print(
                f"    => BEST: {result.best_algo} @ {result.best_bits} bits "
                f"(savings: {result.original_bits - result.best_bits} bits, "
                f"{100*(result.original_bits - result.best_bits)/result.original_bits:.1f}%)"
            )

    # Summary
    print("\n" + "=" * 120)
    print("SUMMARY")
    print("=" * 120)

    total_orig = sum(r.original_bits for r in all_results)
    total_dod = sum(r.diff_of_diffs_bits for r in all_results)
    total_seg_dod = sum(r.segmented_dod_bits for r in all_results)
    total_g4 = sum(r.group_of_4_bits for r in all_results if r.group_of_4_bits is not None)
    total_lin2 = sum(r.linear_g2_bits for r in all_results if r.linear_g2_bits is not None)
    total_lin4 = sum(r.linear_g4_bits for r in all_results if r.linear_g4_bits is not None)
    total_lin8 = sum(r.linear_g8_bits for r in all_results if r.linear_g8_bits is not None)

    print(f"\nTotal bits across all 21 columns:")
    print(f"  Original:      {total_orig:6d} bits")
    print(f"  Diff-of-diffs: {total_dod:6d} bits ({100*(total_orig-total_dod)/total_orig:.1f}% savings)")
    print(f"  Segmented DoD: {total_seg_dod:6d} bits ({100*(total_orig-total_seg_dod)/total_orig:.1f}% savings)")
    print(f"  Group-of-4:    {total_g4:6d} bits ({100*(total_orig-total_g4)/total_orig:.1f}% savings)")
    print(f"  Linear G=2:    {total_lin2:6d} bits ({100*(total_orig-total_lin2)/total_orig:.1f}% savings)")
    print(f"  Linear G=4:    {total_lin4:6d} bits ({100*(total_orig-total_lin4)/total_orig:.1f}% savings)")
    print(f"  Linear G=8:    {total_lin8:6d} bits ({100*(total_orig-total_lin8)/total_orig:.1f}% savings)")

    # Best algorithm per column
    print("\n" + "=" * 120)
    print("BEST ALGORITHM PER COLUMN")
    print("=" * 120)

    algo_counts = {}
    for r in all_results:
        algo = r.best_algo
        algo_counts[algo] = algo_counts.get(algo, 0) + 1
        print(f"{r.func}/{r.col}: {algo} ({r.best_bits} bits)")

    print("\nAlgorithm selection counts:")
    for algo, count in sorted(algo_counts.items()):
        print(f"  {algo}: {count} columns")

    # Save results for downstream scripts
    print("\n" + "=" * 120)
    print("Saving analysis results to analysis_results.py...")
    print("=" * 120)

    with open("analysis_results.py", "w") as f:
        f.write("# Auto-generated by analyze.py\n\n")
        f.write("RESULTS = [\n")
        for r in all_results:
            f.write(f"    {{\n")
            f.write(f"        'func': '{r.func}',\n")
            f.write(f"        'col': '{r.col}',\n")
            f.write(f"        'n_entries': {r.n_entries},\n")
            f.write(f"        'best_algo': '{r.best_algo}',\n")
            f.write(f"        'best_bits': {r.best_bits},\n")
            f.write(f"        'original_bits': {r.original_bits},\n")
            f.write(f"    }},\n")
        f.write("]\n")

    print("Done.")


if __name__ == "__main__":
    main()
