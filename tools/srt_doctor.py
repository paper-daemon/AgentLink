#!/usr/bin/env python3
"""Conservative structural QA for SubRip (.srt) subtitle files."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

TIMING_RE = re.compile(
    r"^(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2},\d{3})$"
)
INDEX_RE = re.compile(r"^[0-9]+$")
HTML_TAG_RE = re.compile(r"<[^>]+>")
ASS_TAG_RE = re.compile(r"\{\\[^}]+\}")


@dataclass(frozen=True)
class Cue:
    number: int
    start_ms: int
    end_ms: int
    text: str
    block: int


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    block: int | None = None
    cue: int | None = None


def timestamp_ms(value: str) -> int:
    """Convert an SRT timestamp into integer milliseconds."""
    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", value)
    if not match:
        raise ValueError(f"invalid SRT timestamp: {value}")
    hours, minutes, seconds, millis = map(int, match.groups())
    if minutes > 59 or seconds > 59:
        raise ValueError(f"invalid SRT timestamp: {value}")
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def visible_character_count(text: str) -> int:
    """Approximate visible characters after stripping common subtitle markup."""
    text = HTML_TAG_RE.sub("", text)
    text = ASS_TAG_RE.sub("", text)
    return len(re.sub(r"\s+", "", text))


def parse_srt(source: str) -> tuple[list[Cue], list[Finding]]:
    """Parse SRT text while retaining malformed blocks as findings."""
    normalized = source.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        return [], [Finding("EMPTY_FILE", "subtitle file contains no cues")]

    blocks = re.split(r"\n\s*\n", normalized.strip())
    cues: list[Cue] = []
    findings: list[Finding] = []

    for block_number, block in enumerate(blocks, start=1):
        lines = block.split("\n")
        if len(lines) < 2:
            findings.append(Finding("MALFORMED_BLOCK", "cue block needs an index and timing line", block_number))
            continue

        raw_index = lines[0].strip()
        if not INDEX_RE.fullmatch(raw_index):
            findings.append(Finding("INVALID_INDEX", f"invalid cue index: {raw_index!r}", block_number))
            continue
        try:
            cue_number = int(raw_index)
        except ValueError:
            findings.append(Finding("INVALID_INDEX", f"cue index is too large to parse safely", block_number))
            continue

        timing = TIMING_RE.fullmatch(lines[1].strip())
        if not timing:
            findings.append(Finding("INVALID_TIMING", f"invalid timing line: {lines[1].strip()!r}", block_number, cue_number))
            continue

        try:
            start_ms = timestamp_ms(timing.group("start"))
            end_ms = timestamp_ms(timing.group("end"))
        except ValueError as exc:
            findings.append(Finding("INVALID_TIMESTAMP", str(exc), block_number, cue_number))
            continue

        text = "\n".join(lines[2:]).strip()
        if not text:
            findings.append(Finding("EMPTY_TEXT", "cue has no subtitle text", block_number, cue_number))

        if end_ms <= start_ms:
            findings.append(Finding("NON_POSITIVE_DURATION", "cue end must be later than cue start", block_number, cue_number))

        cues.append(Cue(cue_number, start_ms, end_ms, text, block_number))

    return cues, findings


def inspect_cues(
    cues: list[Cue],
    *,
    max_cps: float | None = None,
    max_duration_seconds: float | None = None,
) -> list[Finding]:
    """Check cue ordering, overlap, duplicates, and optional pacing thresholds."""
    findings: list[Finding] = []
    seen_numbers: set[int] = set()
    previous: Cue | None = None

    for cue in cues:
        if cue.number in seen_numbers:
            findings.append(Finding("DUPLICATE_INDEX", f"cue index {cue.number} appears more than once", cue.block, cue.number))
        seen_numbers.add(cue.number)

        if previous is not None:
            if cue.start_ms < previous.start_ms:
                findings.append(Finding("NON_MONOTONIC_START", f"cue starts before cue {previous.number}", cue.block, cue.number))
            if cue.start_ms < previous.end_ms and previous.start_ms < cue.end_ms:
                findings.append(Finding("OVERLAP", f"cue overlaps cue {previous.number}", cue.block, cue.number))

        duration_ms = cue.end_ms - cue.start_ms
        if duration_ms > 0 and max_duration_seconds is not None:
            if duration_ms > max_duration_seconds * 1000:
                findings.append(
                    Finding(
                        "LONG_DURATION",
                        f"cue duration {duration_ms / 1000:.3f}s exceeds {max_duration_seconds:g}s threshold",
                        cue.block,
                        cue.number,
                    )
                )

        if duration_ms > 0 and max_cps is not None and cue.text:
            cps = visible_character_count(cue.text) / (duration_ms / 1000)
            if cps > max_cps:
                findings.append(
                    Finding(
                        "HIGH_CPS",
                        f"cue reading rate {cps:.2f} chars/s exceeds {max_cps:g} threshold",
                        cue.block,
                        cue.number,
                    )
                )

        previous = cue

    return findings


def inspect_srt(
    source: str,
    *,
    max_cps: float | None = None,
    max_duration_seconds: float | None = None,
) -> tuple[list[Cue], list[Finding]]:
    """Run parsing plus conservative structural and optional pacing checks."""
    cues, findings = parse_srt(source)
    findings.extend(inspect_cues(cues, max_cps=max_cps, max_duration_seconds=max_duration_seconds))
    return cues, findings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check SubRip (.srt) subtitles for structural QA issues.")
    parser.add_argument("path", type=Path, help="SRT file to inspect")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--max-cps", type=float, help="optional maximum visible characters per second")
    parser.add_argument("--max-duration", type=float, help="optional maximum cue duration in seconds")
    return parser


def validate_positive_finite(value: float | None, option: str) -> None:
    if value is not None and (not math.isfinite(value) or value <= 0):
        raise SystemExit(f"{option} must be a finite number greater than zero")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validate_positive_finite(args.max_cps, "--max-cps")
    validate_positive_finite(args.max_duration, "--max-duration")

    try:
        source = args.path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        print(f"ERROR: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2

    cues, findings = inspect_srt(source, max_cps=args.max_cps, max_duration_seconds=args.max_duration)

    if args.json:
        print(
            json.dumps(
                {
                    "path": str(args.path),
                    "cue_count": len(cues),
                    "finding_count": len(findings),
                    "findings": [asdict(item) for item in findings],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif not findings:
        print(f"OK: {len(cues)} cue(s), no findings")
    else:
        print(f"FOUND: {len(findings)} issue(s) across {len(cues)} parsed cue(s)")
        for finding in findings:
            location = []
            if finding.block is not None:
                location.append(f"block={finding.block}")
            if finding.cue is not None:
                location.append(f"cue={finding.cue}")
            suffix = f" ({', '.join(location)})" if location else ""
            print(f"[{finding.code}]{suffix} {finding.message}")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
