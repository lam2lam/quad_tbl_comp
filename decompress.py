#!/usr/bin/env python3
"""
Decompress LUT tables from diff-of-diffs or group-of-4 format.

Reconstructs original tables from compressed data.
"""

import argparse


def decompress_column_dod(col_data, n_entries):
    """
    Decompress a single column from diff-of-diffs format (no segmentation).
    """
    if n_entries == 0:
        return []

    anchor = col_data["anchor"]
    first_diff = col_data["first_diff"]
    dods = col_data["dods"]

    result = [anchor]

    if n_entries >= 2:
        col1 = anchor + first_diff
        result.append(col1)

    for i in range(len(dods)):
        prev_diff = result[i + 1] - result[i]
        next_val = result[i + 1] + prev_diff + dods[i]
        result.append(next_val)

    return result


def decompress_column_seg_dod(col_data, n_entries):
    """
    Decompress a single column from segmented diff-of-diffs format.
    """
    segments = col_data["segments"]
    seg_size = col_data.get("seg_size", 32)

    result = []
    for seg in segments:
        anchor = seg["anchor"]
        first_diff = seg["first_diff"]
        dods = seg["dods"]

        seg_result = [anchor]
        if len(dods) >= 1:  # Has at least 2 entries
            col1 = anchor + first_diff
            seg_result.append(col1)

        for i in range(len(dods)):
            prev_diff = seg_result[i + 1] - seg_result[i]
            next_val = seg_result[i + 1] + prev_diff + dods[i]
            seg_result.append(next_val)

        result.extend(seg_result)

    return result[:n_entries]


def decompress_column_g4(col_data, n_entries):
    """
    Decompress a single column from group-of-4 format.

    For each group:
      - col[4*i] = anchors[i]
      - col[4*i+1] = col[4*i] + diffs[i]
      - col[4*i+2] = col[4*i+1] + (diffs[i] + dods2[j])
      - col[4*i+3] = col[4*i+1] + (diffs[i] + dods3[j])
    """
    if n_entries == 0:
        return []

    anchors = col_data["anchors"]
    diffs = col_data["diffs"]
    dods2 = col_data["dods2"]
    dods3 = col_data["dods3"]

    result = []

    for i in range(len(anchors)):
        anchor = anchors[i]
        result.append(anchor)

        if i < len(diffs):
            diff = diffs[i]
            col1 = anchor + diff
            result.append(col1)

            if i < len(dods2):
                dod2 = dods2[i]
                col2 = col1 + diff + dod2
                result.append(col2)

                if i < len(dods3):
                    dod3 = dods3[i]
                    col3 = col1 + diff + dod3
                    result.append(col3)

    return result[:n_entries]


def decompress_all(algo="dod", seg_size=32):
    """Decompress all tables and return reconstructed data."""
    if algo == "g4":
        from compressed_luts_g4 import COMPRESSED_LUTS_G4 as COMPRESSED_LUTS
    elif algo == "seg-dod":
        from compressed_luts_seg32 import COMPRESSED_LUTS_SEG as COMPRESSED_LUTS
    else:
        from compressed_luts import COMPRESSED_LUTS

    reconstructed = {}

    for func_name, func_data in COMPRESSED_LUTS.items():
        n_entries = func_data["n_entries"]
        columns = func_data["columns"]

        # Decompress each column
        if algo == "g4":
            c0 = decompress_column_g4(columns["C0"], n_entries)
            c1 = decompress_column_g4(columns["C1"], n_entries)
            c2 = decompress_column_g4(columns["C2"], n_entries)
        elif algo == "seg-dod":
            c0 = decompress_column_seg_dod(columns["C0"], n_entries)
            c1 = decompress_column_seg_dod(columns["C1"], n_entries)
            c2 = decompress_column_seg_dod(columns["C2"], n_entries)
        else:
            c0 = decompress_column_dod(columns["C0"], n_entries)
            c1 = decompress_column_dod(columns["C1"], n_entries)
            c2 = decompress_column_dod(columns["C2"], n_entries)

        # Combine into rows
        data = []
        for i in range(n_entries):
            data.append([c0[i], c1[i], c2[i]])

        reconstructed[func_name] = {
            "n_entries": n_entries,
            "data": data,
        }

    return reconstructed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Decompress LUT tables")
    parser.add_argument(
        "--algo",
        choices=["dod", "seg-dod", "g4"],
        default="dod",
        help="Compression algorithm used: dod, seg-dod, or g4",
    )
    parser.add_argument(
        "--seg-size",
        type=int,
        default=32,
        help="Segment size for seg-dod (default: 32)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print(f"LUT DECOMPRESSION ({args.algo.upper()})")
    print("=" * 70)

    reconstructed = decompress_all(args.algo, args.seg_size)

    for func_name, func_data in reconstructed.items():
        n = func_data["n_entries"]
        data = func_data["data"]

        print(f"\n{func_name}: {n} entries")
        print("  First 8 rows:")
        for i in range(min(8, n)):
            print(f"    [{i:3d}] C0={data[i][0]:08X}, C1={data[i][1]:04X}, C2={data[i][2]:04X}")
        if n > 8:
            print(f"  ... ({n - 8} more rows)")
        print(f"  Last row:")
        print(f"    [{n-1:3d}] C0={data[n-1][0]:08X}, C1={data[n-1][1]:04X}, C2={data[n-1][2]:04X}")

    print(f"\n{'='*70}")
    print("Decompression complete.")
    print(f"Run verify.py --algo {args.algo} to compare against original tables.")
