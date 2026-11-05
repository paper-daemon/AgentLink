# CSV Doctor

[![CSV Doctor video preview](https://paper-daemon.github.io/agentlink-continuity/tool-videos/csv-quality.jpg)](https://paper-daemon.github.io/agentlink-continuity/tools.html#csv-quality)

> 🎬 [22-second test-log video](https://paper-daemon.github.io/agentlink-continuity/tools.html#csv-quality) · [Direct MP4](https://paper-daemon.github.io/agentlink-continuity/tool-videos/csv-quality.mp4). This is a test demonstration, not client data or a production import.

A zero-dependency, report-first CLI for spotting common CSV/TSV data-quality problems before they become spreadsheet or import bugs.

## What it checks

- UTF-8 / UTF-8 BOM / CP932 decoding
- delimiter detection for comma, tab, semicolon, and pipe
- fully blank data rows
- exact duplicate data rows
- inconsistent column counts compared with the header

The input file is never modified.

## Quick start

```bash
cd tools/csv-doctor
python csv_doctor.py sample.csv
```

Example output:

```json
{
  "encoding": "utf-8",
  "delimiter": ",",
  "rows_total": 5,
  "columns_expected": 3,
  "blank_rows": [4],
  "duplicate_rows": [{"row": 5, "first_seen_row": 2}],
  "inconsistent_rows": [],
  "issues": 2
}
```

## Optional cleaned copy

```bash
python csv_doctor.py input.csv --clean-out cleaned.csv
```

The cleaned copy removes only fully blank data rows and exact duplicate data rows. Structural mismatches such as inconsistent column counts are reported but not guessed or silently rewritten.

The cleaned output is written as UTF-8 with BOM for broad spreadsheet compatibility.

## CI mode

```bash
python csv_doctor.py input.csv --strict
```

`--strict` returns exit code `2` when the report contains issues, making the tool usable in simple CI/data-import checks.

## Tests

```bash
cd tools/csv-doctor
python -m unittest -v test_csv_doctor.py
```

The initial release includes coverage for clean CSV, blank/duplicate/inconsistent rows, tab-delimited files, CP932 input, and safe cleaned-copy behavior.

## Scope

CSV Doctor is deliberately conservative. It does not guess how malformed rows should be repaired, infer business meaning, modify the source file, upload data, or make network calls.
