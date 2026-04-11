#!/usr/bin/env python3
"""
Verify compressed/decompressed LUT tables against originals.

Compares reconstructed tables with original .txt files and reports any mismatches.
"""

import os
import argparse
from decompress import decompress_all

TABLE_FILES = [
    "log2.txt",
    "pow2.txt",
    "recp.txt",
    "sqrt1_to_2.txt",
    "sqrt2_to_4.txt",
    "rsqrt1_to_2.txt",
    "rsqrt2_to_4.txt",
]

FUNC_NAME_MAP = {
    "log2.txt": "log2",
    "pow2.txt": "pow2",
    "recp.txt": "recp",
    "sqrt1_to_2.txt": "sqrt1_to_2",
    "sqrt2_to_4.txt": "sqrt2_to_4",
    "rsqrt1_to_2.txt": "rsqrt1_to_2",
    "rsqrt2_to_4.txt": "rsqrt2_to_4",
}


def parse_table(filepath):
    """Parse a .txt file and return data as list of rows."""
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


def main():
    parser = argparse.ArgumentParser(description="Verify compressed LUT tables")
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
    print(f"LUT VERIFICATION ({args.algo.upper()})")
    print("=" * 70)

    # Get decompressed data
    reconstructed = decompress_all(args.algo, args.seg_size)

    all_passed = True
    total_original = 0
    total_matched = 0

    for table_file in TABLE_FILES:
        if not os.path.exists(table_file):
            print(f"WARNING: {table_file} not found, skipping")
            continue

        func_name = FUNC_NAME_MAP[table_file]
        original_data = parse_table(table_file)
        recon_data = reconstructed[func_name]["data"]
        n_entries = len(original_data)

        total_original += n_entries * 3  # 3 columns per entry

        # Compare
        mismatches = []
        for i in range(n_entries):
            for j in range(3):
                if original_data[i][j] != recon_data[i][j]:
                    mismatches.append((i, j, original_data[i][j], recon_data[i][j]))

        if mismatches:
            all_passed = False
            print(f"\n{table_file} ({func_name}): FAILED")
            print(f"  {len(mismatches)} mismatches found:")
            for idx, col, orig, recon in mismatches[:10]:  # Show first 10
                print(f"    Row {idx}, Col C{col}: expected {orig:08X}, got {recon:08X}")
            if len(mismatches) > 10:
                print(f"    ... and {len(mismatches) - 10} more")
        else:
            matched = n_entries * 3
            total_matched += matched
            print(f"\n{table_file} ({func_name}): PASSED ({n_entries} entries, 3 columns)")

    print("\n" + "=" * 70)
    if all_passed:
        print(f"VERIFICATION PASSED")
        print(f"All {total_original} values match original tables.")
    else:
        print(f"VERIFICATION FAILED")
        print(f"Matched: {total_matched}/{total_original} values")

    return all_passed


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
