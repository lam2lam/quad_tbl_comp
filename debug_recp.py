#!/usr/bin/env python3
"""
Debug script to show actual compressed values for recp table.
"""

import math

def parse_table(filepath):
    with open(filepath, "r") as f:
        lines = f.readlines()
    sep_idx = 0
    for i, line in enumerate(lines):
        if "---" in line:
            sep_idx = i + 1
            break
    data = []
    for line in lines[sep_idx:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        row = [int(p.strip(), 16) for p in parts]
        data.append(row)
    return data

def bit_cost(values):
    if not values:
        return 0
    max_abs = max(abs(v) for v in values)
    if max_abs == 0:
        return 1
    return math.ceil(math.log2(max_abs + 1))

def show_diff_of_diffs(column, col_name):
    print(f"\n{'='*60}")
    print(f"DIFF-OF-DIFFS for {col_name}")
    print(f"{'='*60}")

    n = len(column)
    print(f"\nOriginal values (first 16):")
    for i in range(min(16, n)):
        print(f"  [{i:3d}] = {column[i]:08X} ({column[i]})")

    # Anchor
    anchor = column[0]
    print(f"\nAnchor (stored): {anchor:08X} -> {bit_cost([anchor])} bits")

    # First diff
    diff1 = column[1] - column[0]
    print(f"First diff: {diff1:+d} -> {bit_cost([diff1])} bits")

    # Diff of diffs
    dods = []
    for i in range(2, n):
        d1 = column[i] - column[i-1]
        d0 = column[i-1] - column[i-2]
        dod = d1 - d0
        dods.append(dod)

    print(f"\nDiff-of-diffs statistics:")
    print(f"  Count: {len(dods)}")
    print(f"  Min: {min(dods):+d}")
    print(f"  Max: {max(dods):+d}")
    print(f"  Bit width: {bit_cost(dods)} bits per value")
    print(f"  Total: {bit_cost(dods) * len(dods)} bits for all DoD values")

    # First 16 DoD values
    print(f"\nFirst 16 diff-of-diff values:")
    for i in range(min(16, len(dods))):
        print(f"  [{i+2:3d}] = {dods[i]:+d}")

    # Total cost
    total = bit_cost([anchor]) + bit_cost([diff1]) + bit_cost(dods) * len(dods)
    print(f"\nTOTAL COST: {total} bits")
    print(f"  Anchor: {bit_cost([anchor])} bits (1 value)")
    print(f"  First diff: {bit_cost([diff1])} bits (1 value)")
    print(f"  DoD: {bit_cost(dods)} bits × {len(dods)} values = {bit_cost(dods) * len(dods)} bits")

def show_group_of_4(column, col_name):
    print(f"\n{'='*60}")
    print(f"GROUP-OF-4 for {col_name}")
    print(f"{'='*60}")

    n = len(column)

    anchors = []
    diffs1 = []
    dods2 = []
    dods3 = []

    for g in range(0, n, 4):
        group = column[g:g+4]
        if len(group) == 0:
            continue
        anchors.append(group[0])
        if len(group) >= 2:
            diffs1.append(group[1] - group[0])
        if len(group) >= 3:
            d2 = group[2] - group[1]
            d1 = group[1] - group[0]
            dods2.append(d2 - d1)
        if len(group) == 4:
            d3 = group[3] - group[1]
            d1 = group[1] - group[0]
            dods3.append(d3 - d1)

    print(f"\nAnchors (first 8): {anchors[:8]}")
    print(f"  Bit width: {bit_cost(anchors)}")
    print(f"Diffs (first 8): {diffs1[:8]}")
    print(f"  Bit width: {bit_cost(diffs1)}")
    print(f"DoD2 (first 8): {dods2[:8]}")
    print(f"  Bit width: {bit_cost(dods2)}")
    print(f"DoD3 (first 8): {dods3[:8]}")
    print(f"  Bit width: {bit_cost(dods3)}")

    total = (bit_cost(anchors) * len(anchors) +
             bit_cost(diffs1) * len(diffs1) +
             bit_cost(dods2) * len(dods2) +
             bit_cost(dods3) * len(dods3))
    print(f"\nTOTAL COST: {total} bits")

def find_best_line(group):
    n = len(group)
    if n == 0:
        return (0, 0, [])
    if n == 1:
        return (0, group[0], [0])

    x0, x1 = 0, n - 1
    y0, y1 = group[0], group[-1]
    m = (y1 - y0) / (x1 - x0)
    b = y0 - m * x0

    residues = []
    for i, y in enumerate(group):
        approx = m * i + b
        residue = round(y - approx)
        residues.append(residue)

    return (m, b, residues)

def show_linear_g8(column, col_name):
    print(f"\n{'='*60}")
    print(f"LINEAR G=8 for {col_name}")
    print(f"{'='*60}")

    n = len(column)
    G = 8
    num_groups = n // G

    m_values = []
    b_values = []
    all_residues = []

    print(f"\nPer-group M, B, and residues:")

    for grp in range(num_groups):
        start = grp * G
        group = column[start:start+G]
        m, b, residues = find_best_line(group)
        m_values.append(m)
        b_values.append(b)
        all_residues.extend(residues)

        if grp < 4:  # Show first 4 groups
            print(f"\nGroup {grp} (indices {start}-{start+G-1}):")
            print(f"  M = {m:.6f}, B = {b:.6f}")
            print(f"  Original: {[f'{x:04X}' for x in group]}")
            print(f"  Approx:   {[f'{round(m*i+b):04X}' for i in range(G)]}")
            print(f"  Residues: {residues}")
            print(f"  Residue bit width: {bit_cost(residues)}")

    # Show remaining groups summary
    if num_groups > 4:
        print(f"\n... ({num_groups - 4} more groups)")

    # M and B statistics
    m_ints = [round(x) for x in m_values]
    b_ints = [round(x) for x in b_values]

    print(f"\nM values (rounded): {m_ints}")
    print(f"  Bit width: {bit_cost(m_ints)}")
    print(f"B values (rounded): {b_ints}")
    print(f"  Bit width: {bit_cost(b_ints)}")
    print(f"Residues: min={min(all_residues)}, max={max(all_residues)}")
    print(f"  Bit width: {bit_cost(all_residues)}")

    # Total cost
    m_cost = bit_cost(m_ints) * num_groups
    b_cost = bit_cost(b_ints) * num_groups
    residue_cost = bit_cost(all_residues) * n  # Each residue stored at same bit width

    print(f"\nTOTAL COST: {m_cost + b_cost + residue_cost} bits")
    print(f"  M table: {bit_cost(m_ints)} bits × {num_groups} groups = {m_cost} bits")
    print(f"  B table: {bit_cost(b_ints)} bits × {num_groups} groups = {b_cost} bits")
    print(f"  Residues: {bit_cost(all_residues)} bits × {n} values = {residue_cost} bits")

# Main
print("RECP TABLE DEBUG ANALYSIS")
print("="*60)

data = parse_table("recp.txt")
print(f"Total entries: {len(data)}")

for col_idx, col_name in enumerate(["C0", "C1", "C2"]):
    column = [row[col_idx] for row in data]
    show_diff_of_diffs(column, col_name)
    show_group_of_4(column, col_name)
    show_linear_g8(column, col_name)
    print("\n" + "="*70)
