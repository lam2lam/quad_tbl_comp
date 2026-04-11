# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lossless table compression algorithm for 7 lookup tables (LUTs) used to approximate elementary functions using quadratic equations. The compression must support O(1) random access.

### Target Functions (7 tables total)
- `log2.txt` - logarithm base 2
- `pow2.txt` - 2^x
- `recp.txt` - reciprocal (1/x)
- `sqrt1_to_2.txt` - square root for range [1,2)
- `sqrt2_to_4.txt` - square root for range [2,4)
- `rsqrt1_to_2.txt` - reciprocal square root for range [1,2)
- `rsqrt2_to_4.txt` - reciprocal square root for range [2,4)

### Data Format
- Files contain header metadata (WIDTH_C0=26, WIDTH_C1=16, WIDTH_C2=10)
- Data rows start after `---` separator line
- Each row has 3 hex columns: C0 (26-bit), C1 (16-bit), C2 (10-bit)
- SIGN fields indicate coefficient signs

## Implemented Scripts

### analyze.py
Compares all compression algorithms and segmentations. Run with:
```
python3 analyze.py
```
Outputs analysis_results.py with per-column statistics.

### compress.py
Compresses tables using specified algorithm:
```
python3 compress.py --algo dod   # Diff-of-diffs (O(n), 59.4% savings)
python3 compress.py --algo g4    # Group-of-4 (O(1), 33.0% savings)
```
Outputs: `compressed_luts.py` (dod) or `compressed_luts_g4.py` (g4)

### decompress.py
Decompresses tables back to original form:
```
python3 decompress.py --algo dod
python3 decompress.py --algo g4
```

### verify.py
Regression test - compares decompressed data against original tables:
```
python3 verify.py --algo dod   # Should pass
python3 verify.py --algo g4    # Should pass
```

## Compression Algorithms

### 1. Diff-of-Diffs (O(n)) - RECOMMENDED
Best compression (59.4% savings). Store:
- Anchor: col[0]
- First diff: col[1] - col[0]
- Diff-of-diffs for remaining: (col[i+1]-col[i]) - (col[i]-col[i-1])

Total: 10,710 bits vs 26,368 original

### 2. Group-of-4 (O(1))
For hardware requiring true O(1) random access. For each group of 4:
- Anchor: col[4*i] (full value)
- Diff: col[4*i+1] - col[4*i]
- DoD2: (col[4*i+2]-col[4*i+1]) - (col[4*i+1]-col[4*i])
- DoD3: (col[4*i+3]-col[4*i+1]) - (col[4*i+1]-col[4*i])

Total: 17,664 bits vs 26,368 original (33.0% savings)
Requires 2 adders in series for worst-case access.

### 3. Linear Approximation
Analyzed but not implemented - M/B table overhead makes it worse than diff-of-diffs for this data.

## Cost Model
```
original_cost = N * ceil(log2(max(column)))
compressed_cost = sum of bit_widths for all stored values
```

## Key Files
- `specs.md` - Full specification and requirements
- `*.txt` - Input LUT data files (7 total)
- `compressed_luts.py` - Diff-of-diffs compressed output
- `compressed_luts_g4.py` - Group-of-4 compressed output
