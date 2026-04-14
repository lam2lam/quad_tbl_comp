#!/usr/bin/env python3
"""
Compress LUT tables using diff-of-diffs or group-of-4 algorithm.

Diff-of-diffs (O(n)):
  - Store anchor (col[0])
  - Store first diff (col[1] - col[0])
  - Store diff-of-diffs for remaining values

Group-of-4 (O(1)):
  - For each group of 4: store anchor, diff, dod[2], dod[3]
  - Requires 2 adders in series for worst-case access
"""

import math
import os
import argparse

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


def parse_table(filepath):
    """Parse a .txt file, return (func_name, header_lines, data)."""
    with open(filepath, "r") as f:
        lines = f.readlines()

    sep_idx = 0
    for i, line in enumerate(lines):
        if "---" in line:
            sep_idx = i + 1
            break

    func_name = "unknown"
    header_lines = []
    for line in lines[:sep_idx - 1]:
        if "# Function:" in line:
            func_name = line.split("# Function:")[1].split(",")[0].strip()
        elif "=" in line:
            header_lines.append(line.strip())
        elif "SIGN" in line:
            header_lines.append(line.strip())

    data = []
    for line in lines[sep_idx:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        row = [int(p.strip(), 16) for p in parts]
        data.append(row)

    return func_name, header_lines, data


def bit_cost(values):
    """Compute bits required to store a list of signed integers."""
    if not values:
        return 0
    max_abs = max(abs(v) for v in values)
    if max_abs == 0:
        return 1
    return math.ceil(math.log2(max_abs + 1))


def compress_column(column):
    """
    Compress a column using diff-of-diffs without segmentation.
    Returns (anchor, first_diff, dod_list, dod_bit_width).
    """
    n = len(column)
    if n == 0:
        return (0, 0, [], 0)
    if n == 1:
        return (column[0], 0, [], bit_cost([column[0]]))

    anchor = column[0]
    first_diff = column[1] - column[0]

    dods = []
    for i in range(2, n):
        d1 = column[i] - column[i - 1]
        d0 = column[i - 1] - column[i - 2]
        dod = d1 - d0
        dods.append(dod)

    dod_bit_width = bit_cost(dods) if dods else 0

    return (anchor, first_diff, dods, dod_bit_width)


def compress_column_segmented(column, seg_size):
    """
    Compress a column using diff-of-diffs with segmentation.
    Each segment has its own anchor and first_diff.

    Returns list of segment data: [(anchor, first_diff, dods), ...]
    """
    n = len(column)
    if n == 0:
        return []

    segments = []
    for seg_start in range(0, n, seg_size):
        seg_end = min(seg_start + seg_size, n)
        segment = column[seg_start:seg_end]

        if len(segment) == 0:
            continue
        elif len(segment) == 1:
            segments.append({"anchor": segment[0], "first_diff": 0, "dods": []})
        else:
            anchor = segment[0]
            first_diff = segment[1] - segment[0]
            dods = []
            for i in range(2, len(segment)):
                d1 = segment[i] - segment[i-1]
                d0 = segment[i-1] - segment[i-2]
                dods.append(d1 - d0)
            segments.append({"anchor": anchor, "first_diff": first_diff, "dods": dods})

    return segments


def compute_segmented_cost(segments):
    """Compute total bit cost for segmented compression."""
    total = 0
    for seg in segments:
        anchor_bits = bit_cost([seg["anchor"]])
        diff_bits = bit_cost([seg["first_diff"]]) if seg["first_diff"] else 0
        if seg["dods"]:
            dod_bw = bit_cost(seg["dods"])
            dod_cost = dod_bw * len(seg["dods"])
        else:
            dod_cost = 0
        total += anchor_bits + diff_bits + dod_cost
    return total


def compress_column_g4(column):
    """
    Compress a column using group-of-4 algorithm (O(1) access).

    For each group of 4 elements:
      - anchor: col[4*n] (full value)
      - delta_2step: col[4*n+2] - col[4*n]
      - dod1: floor(delta_2step/2) - (col[4*n+1] - col[4*n])
      - dod3: floor(delta_2step/2) - (col[4*n+3] - col[4*n+2])

    Returns dict with anchors, deltas, dods and their bit widths.
    """
    n = len(column)
    if n == 0:
        return {"anchors": [], "delta_2step": [], "dod1": [], "dod3": [], "n_groups": 0}

    anchors = []
    delta_2step = []
    dod1 = []
    dod3 = []

    for g in range(0, n, 4):
        group = column[g : g + 4]
        if len(group) == 0:
            continue

        # Anchor: full value
        anchors.append(group[0])

        # delta_2step (if we have index 2)
        if len(group) >= 3:
            d2s = group[2] - group[0]
            delta_2step.append(d2s)

            # dod1 (if we have index 1)
            if len(group) >= 2:
                expected_delta = d2s // 2  # floor division
                actual_delta_1 = group[1] - group[0]
                dod1.append(expected_delta - actual_delta_1)

            # dod3 (if we have index 3)
            if len(group) == 4:
                expected_delta = d2s // 2  # floor division
                actual_delta_3 = group[3] - group[2]
                dod3.append(expected_delta - actual_delta_3)
        else:
            # Handle incomplete groups
            if len(group) >= 2:
                delta_2step.append(0)  # Placeholder
                dod1.append(0)

    return {
        "anchors": anchors,
        "delta_2step": delta_2step,
        "dod1": dod1,
        "dod3": dod3,
        "n_groups": len(anchors),
    }


def compress_dod():
    """Compress using diff-of-diffs algorithm."""
    compressed_data = {}
    total_original = 0
    total_compressed = 0

    for table_file in TABLE_FILES:
        if not os.path.exists(table_file):
            print(f"WARNING: {table_file} not found, skipping")
            continue

        func_name, header_lines, data = parse_table(table_file)
        print(f"\n{table_file} ({func_name}): {len(data)} entries")

        compressed_data[func_name] = {
            "n_entries": len(data),
            "columns": {},
        }

        for col_idx, col_name in enumerate(COLUMN_NAMES):
            column = [row[col_idx] for row in data]
            n = len(column)

            # Original cost: N * bit_width
            orig_bit_width = bit_cost(column)
            orig_cost = n * orig_bit_width
            total_original += orig_cost

            # Compress
            anchor, first_diff, dods, dod_bit_width = compress_column(column)

            # Compressed cost: anchor_bits + diff_bits + (N-2)*dod_bits
            anchor_bits = bit_cost([anchor])
            diff_bits = bit_cost([first_diff])
            dod_cost = dod_bit_width * len(dods) if dods else 0
            compressed_cost = anchor_bits + diff_bits + dod_cost
            total_compressed += compressed_cost

            compressed_data[func_name]["columns"][col_name] = {
                "anchor": anchor,
                "first_diff": first_diff,
                "dods": dods,
                "dod_bit_width": dod_bit_width,
            }

            print(
                f"  {col_name}: {orig_cost} -> {compressed_cost} bits "
                f"({100*(orig_cost-compressed_cost)/orig_cost:.1f}% savings)"
            )
            print(
                f"      anchor={anchor_bits}b, diff={diff_bits}b, "
                f"DoD={dod_bit_width}b x {len(dods)} values"
            )

    # Write compressed data to Python file
    output_file = "compressed_luts.py"
    print(f"\n{'='*70}")
    print(f"Writing compressed data to {output_file}...")

    with open(output_file, "w") as f:
        f.write("#!/usr/bin/env python3\n")
        f.write("# Auto-generated by compress.py --algo dod\n")
        f.write("# Diff-of-diffs compressed LUT data (O(n) access)\n\n")

        f.write("COMPRESSED_LUTS = {\n")
        for func_name, func_data in compressed_data.items():
            f.write(f"    '{func_name}': {{\n")
            f.write(f"        'n_entries': {func_data['n_entries']},\n")
            f.write(f"        'columns': {{\n")
            for col_name, col_data in func_data["columns"].items():
                f.write(f"            '{col_name}': {{\n")
                f.write(f"                'anchor': {col_data['anchor']},\n")
                f.write(f"                'first_diff': {col_data['first_diff']},\n")
                f.write(f"                'dods': {col_data['dods']},\n")
                f.write(f"                'dod_bit_width': {col_data['dod_bit_width']},\n")
                f.write(f"            }},\n")
            f.write(f"        }}\n")
            f.write(f"    }},\n")
        f.write("}\n\n")

        f.write(f"SUMMARY = {{'original_bits': {total_original}, 'compressed_bits': {total_compressed}}}\n")

    print(f"Done. Total: {total_original} -> {total_compressed} bits "
          f"({100*(total_original-total_compressed)/total_original:.1f}% savings)")


def compress_seg_dod(seg_size):
    """Compress using segmented diff-of-diffs algorithm."""
    compressed_data = {}
    total_original = 0
    total_compressed = 0

    for table_file in TABLE_FILES:
        if not os.path.exists(table_file):
            print(f"WARNING: {table_file} not found, skipping")
            continue

        func_name, header_lines, data = parse_table(table_file)
        print(f"\n{table_file} ({func_name}): {len(data)} entries")

        compressed_data[func_name] = {
            "n_entries": len(data),
            "seg_size": seg_size,
            "columns": {},
        }

        for col_idx, col_name in enumerate(COLUMN_NAMES):
            column = [row[col_idx] for row in data]
            n = len(column)

            # Original cost
            orig_bit_width = bit_cost(column)
            orig_cost = n * orig_bit_width
            total_original += orig_cost

            # Compress with segmentation
            segments = compress_column_segmented(column, seg_size)
            compressed_cost = compute_segmented_cost(segments)
            total_compressed += compressed_cost

            # Compute bit widths for reference
            all_anchors = [s["anchor"] for s in segments]
            all_diffs = [s["first_diff"] for s in segments if s["first_diff"] or len(s["dods"]) > 0]
            all_dods = []
            for s in segments:
                all_dods.extend(s["dods"])

            anchor_bits = bit_cost(all_anchors) if all_anchors else 0
            diff_bits = bit_cost(all_diffs) if all_diffs else 0
            dod_bw = bit_cost(all_dods) if all_dods else 0

            compressed_data[func_name]["columns"][col_name] = {
                "segments": segments,
                "seg_size": seg_size,
            }

            print(
                f"  {col_name}: {orig_cost} -> {compressed_cost} bits "
                f"({100*(orig_cost-compressed_cost)/orig_cost:.1f}% savings)"
            )
            print(
                f"      {len(segments)} segments: anchor={anchor_bits}b, diff={diff_bits}b, DoD={dod_bw}b"
            )

    # Write compressed data to Python file
    output_file = f"compressed_luts_seg{seg_size}.py"
    print(f"\n{'='*70}")
    print(f"Writing compressed data to {output_file}...")

    with open(output_file, "w") as f:
        f.write("#!/usr/bin/env python3\n")
        f.write(f"# Auto-generated by compress.py --algo seg-dod --seg-size {seg_size}\n")
        f.write(f"# Segmented diff-of-diffs compressed LUT data (seg={seg_size})\n\n")

        f.write("COMPRESSED_LUTS_SEG = {\n")
        for func_name, func_data in compressed_data.items():
            f.write(f"    '{func_name}': {{\n")
            f.write(f"        'n_entries': {func_data['n_entries']},\n")
            f.write(f"        'seg_size': {func_data['seg_size']},\n")
            f.write(f"        'columns': {{\n")
            for col_name, col_data in func_data["columns"].items():
                f.write(f"            '{col_name}': {{\n")
                f.write(f"                'seg_size': {col_data['seg_size']},\n")
                f.write(f"                'segments': {col_data['segments']},\n")
                f.write(f"            }},\n")
            f.write(f"        }}\n")
            f.write(f"    }},\n")
        f.write("}\n\n")

        f.write(f"SUMMARY = {{'original_bits': {total_original}, 'compressed_bits': {total_compressed}}}\n")

    print(f"Done. Total: {total_original} -> {total_compressed} bits "
          f"({100*(total_original-total_compressed)/total_original:.1f}% savings)")


def compress_g4():
    """Compress using group-of-4 algorithm."""
    compressed_data = {}
    total_original = 0
    total_compressed = 0

    for table_file in TABLE_FILES:
        if not os.path.exists(table_file):
            print(f"WARNING: {table_file} not found, skipping")
            continue

        func_name, header_lines, data = parse_table(table_file)
        print(f"\n{table_file} ({func_name}): {len(data)} entries")

        compressed_data[func_name] = {
            "n_entries": len(data),
            "columns": {},
        }

        for col_idx, col_name in enumerate(COLUMN_NAMES):
            column = [row[col_idx] for row in data]
            n = len(column)

            # Original cost: N * bit_width
            orig_bit_width = bit_cost(column)
            orig_cost = n * orig_bit_width
            total_original += orig_cost

            # Compress
            g4_data = compress_column_g4(column)

            # Compute bit widths
            anchor_bits = bit_cost(g4_data["anchors"]) if g4_data["anchors"] else 0
            delta_bits = bit_cost(g4_data["delta_2step"]) if g4_data["delta_2step"] else 0
            dod1_bits = bit_cost(g4_data["dod1"]) if g4_data["dod1"] else 0
            dod3_bits = bit_cost(g4_data["dod3"]) if g4_data["dod3"] else 0

            # Total cost
            compressed_cost = (
                anchor_bits * len(g4_data["anchors"]) +
                delta_bits * len(g4_data["delta_2step"]) +
                dod1_bits * len(g4_data["dod1"]) +
                dod3_bits * len(g4_data["dod3"])
            )
            total_compressed += compressed_cost

            compressed_data[func_name]["columns"][col_name] = {
                "anchors": g4_data["anchors"],
                "delta_2step": g4_data["delta_2step"],
                "dod1": g4_data["dod1"],
                "dod3": g4_data["dod3"],
                "anchor_bits": anchor_bits,
                "delta_bits": delta_bits,
                "dod1_bits": dod1_bits,
                "dod3_bits": dod3_bits,
            }

            print(
                f"  {col_name}: {orig_cost} -> {compressed_cost} bits "
                f"({100*(orig_cost-compressed_cost)/orig_cost:.1f}% savings)"
            )
            print(
                f"      anchors={anchor_bits}b x {len(g4_data['anchors'])}, "
                f"delta_2step={delta_bits}b x {len(g4_data['delta_2step'])}, "
                f"dod1={dod1_bits}b x {len(g4_data['dod1'])}, "
                f"dod3={dod3_bits}b x {len(g4_data['dod3'])}"
            )

    # Write compressed data to Python file
    output_file = "compressed_luts_g4.py"
    print(f"\n{'='*70}")
    print(f"Writing compressed data to {output_file}...")

    with open(output_file, "w") as f:
        f.write("#!/usr/bin/env python3\n")
        f.write("# Auto-generated by compress.py --algo g4\n")
        f.write("# Group-of-4 compressed LUT data (O(1) access)\n\n")

        f.write("COMPRESSED_LUTS_G4 = {\n")
        for func_name, func_data in compressed_data.items():
            f.write(f"    '{func_name}': {{\n")
            f.write(f"        'n_entries': {func_data['n_entries']},\n")
            f.write(f"        'columns': {{\n")
            for col_name, col_data in func_data["columns"].items():
                f.write(f"            '{col_name}': {{\n")
                f.write(f"                'anchors': {col_data['anchors']},\n")
                f.write(f"                'delta_2step': {col_data['delta_2step']},\n")
                f.write(f"                'dod1': {col_data['dod1']},\n")
                f.write(f"                'dod3': {col_data['dod3']},\n")
                f.write(f"                'anchor_bits': {col_data['anchor_bits']},\n")
                f.write(f"                'delta_bits': {col_data['delta_bits']},\n")
                f.write(f"                'dod1_bits': {col_data['dod1_bits']},\n")
                f.write(f"                'dod3_bits': {col_data['dod3_bits']},\n")
                f.write(f"            }},\n")
            f.write(f"        }}\n")
            f.write(f"    }},\n")
        f.write("}\n\n")

        f.write(f"SUMMARY = {{'original_bits': {total_original}, 'compressed_bits': {total_compressed}}}\n")

    print(f"Done. Total: {total_original} -> {total_compressed} bits "
          f"({100*(total_original-total_compressed)/total_original:.1f}% savings)")


def main():
    parser = argparse.ArgumentParser(description="Compress LUT tables")
    parser.add_argument(
        "--algo",
        choices=["dod", "seg-dod", "g4"],
        default="dod",
        help="Compression algorithm: dod (diff-of-diffs, O(n)), seg-dod (segmented, O(n)), or g4 (group-of-4, O(1))",
    )
    parser.add_argument(
        "--seg-size",
        type=int,
        default=32,
        choices=[8, 16, 32],
        help="Segment size for seg-dod (default: 32)",
    )
    args = parser.parse_args()

    print("=" * 70)
    if args.algo == "g4":
        print("LUT COMPRESSION - GROUP-OF-4 (O(1))")
        print("=" * 70)
        compress_g4()
    elif args.algo == "seg-dod":
        print(f"LUT COMPRESSION - SEGMENTED DIFF-OF-DIFFS (seg={args.seg_size})")
        print("=" * 70)
        compress_seg_dod(args.seg_size)
    else:
        print("LUT COMPRESSION - DIFF-OF-DIFFS (O(n))")
        print("=" * 70)
        compress_dod()


if __name__ == "__main__":
    main()
