#!/usr/bin/env python3
"""
Show detailed segmented diff-of-diffs cost breakdown per segment.
"""

import math
from compress import parse_table, compress_column_segmented, compute_segmented_cost, bit_cost

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


def show_segment_breakdown(column, col_name, seg_size=32):
    """Show detailed cost breakdown per segment."""
    n = len(column)
    segments = compress_column_segmented(column, seg_size)
    total_cost = compute_segmented_cost(segments)
    orig_cost = n * bit_cost(column)

    print(f"\n  {col_name}: {orig_cost} -> {total_cost} bits ({100*(orig_cost-total_cost)/orig_cost:.1f}% savings)")
    print(f"  Segmentation: {seg_size} entries/segment, {len(segments)} segments")

    for i, seg in enumerate(segments):
        anchor_bits = bit_cost([seg["anchor"]])
        diff_bits = bit_cost([seg["first_diff"]]) if seg["first_diff"] or len(seg["dods"]) > 0 else 0
        dod_bw = bit_cost(seg["dods"]) if seg["dods"] else 0
        dod_cost = dod_bw * len(seg["dods"]) if seg["dods"] else 0
        seg_cost = anchor_bits + diff_bits + dod_cost

        # Show DoD stats
        if seg["dods"]:
            min_dod = min(seg["dods"])
            max_dod = max(seg["dods"])
        else:
            min_dod = max_dod = 0

        print(f"    Segment {i} (indices {i*seg_size}-{min((i+1)*seg_size-1, n-1)}): "
              f"{seg_cost:3d} bits = anchor({anchor_bits}b) + diff({diff_bits}b) + DoD({dod_bw}b x {len(seg['dods'])})")
        print(f"             DoD range: [{min_dod:+d}, {max_dod:+d}]")


def main():
    print("=" * 80)
    print("SEGMENTED DIFF-OF-DIFFS - DETAILED COST BREAKDOWN")
    print("=" * 80)

    grand_total_orig = 0
    grand_total_compressed = 0

    for table_file in TABLE_FILES:
        func_name, _, data = parse_table(table_file)
        print(f"\n{'='*80}")
        print(f"{table_file} ({func_name}): {len(data)} entries")
        print(f"{'='*80}")

        table_orig = 0
        table_compressed = 0

        for col_idx, col_name in enumerate(COLUMN_NAMES):
            column = [row[col_idx] for row in data]
            segments = compress_column_segmented(column, 32)
            seg_cost = compute_segmented_cost(segments)
            orig_cost = len(column) * bit_cost(column)

            table_orig += orig_cost
            table_compressed += seg_cost

            show_segment_breakdown(column, col_name, seg_size=32)

        grand_total_orig += table_orig
        grand_total_compressed += table_compressed

        print(f"\n  TABLE TOTAL: {table_orig} -> {table_compressed} bits ({100*(table_orig-table_compressed)/table_orig:.1f}% savings)")

    print(f"\n{'='*80}")
    print("GRAND TOTAL")
    print(f"{'='*80}")
    print(f"  Original:   {grand_total_orig} bits")
    print(f"  Compressed: {grand_total_compressed} bits")
    print(f"  Savings: {100*(grand_total_orig-grand_total_compressed)/grand_total_orig:.1f}%")


if __name__ == "__main__":
    main()
