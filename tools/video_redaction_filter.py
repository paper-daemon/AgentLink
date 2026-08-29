#!/usr/bin/env python3
"""Validate static video redaction regions and emit a reviewable FFmpeg command."""

from __future__ import annotations

import argparse
import json
import math
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Region:
    start: float
    end: float
    x: int
    y: int
    width: int
    height: int
    blur: int = 10


class PlanError(ValueError):
    pass


def finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlanError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise PlanError(f"{name} must be finite")
    return number


def positive_int(value: object, name: str, *, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PlanError(f"{name} must be an integer")
    minimum = 0 if allow_zero else 1
    if value < minimum:
        comparator = "zero or greater" if allow_zero else "greater than zero"
        raise PlanError(f"{name} must be {comparator}")
    return value


def parse_region(raw: object, index: int) -> Region:
    if not isinstance(raw, dict):
        raise PlanError(f"region {index} must be an object")

    start = finite_number(raw.get("start"), f"region {index}.start")
    end = finite_number(raw.get("end"), f"region {index}.end")
    if start < 0:
        raise PlanError(f"region {index}.start must be zero or greater")
    if end <= start:
        raise PlanError(f"region {index}.end must be later than start")

    x = positive_int(raw.get("x"), f"region {index}.x", allow_zero=True)
    y = positive_int(raw.get("y"), f"region {index}.y", allow_zero=True)
    width = positive_int(raw.get("width"), f"region {index}.width")
    height = positive_int(raw.get("height"), f"region {index}.height")
    blur = positive_int(raw.get("blur", 10), f"region {index}.blur")
    max_blur = min(width, height) // 2
    if max_blur < 1:
        raise PlanError(f"region {index} must be at least 2x2 pixels for blur redaction")
    if blur > max_blur:
        raise PlanError(
            f"region {index}.blur must be at most half the smaller crop dimension ({max_blur})"
        )

    return Region(start=start, end=end, x=x, y=y, width=width, height=height, blur=blur)


def parse_plan(raw: object) -> list[Region]:
    if not isinstance(raw, dict):
        raise PlanError("plan must be a JSON object")
    regions_raw = raw.get("regions")
    if not isinstance(regions_raw, list) or not regions_raw:
        raise PlanError("plan.regions must be a non-empty array")
    return [parse_region(item, index) for index, item in enumerate(regions_raw, start=1)]


def ff_number(value: float) -> str:
    return format(value, ".6f").rstrip("0").rstrip(".") or "0"


def build_filter_complex(regions: list[Region]) -> tuple[str, str]:
    """Return (filter_complex, final_video_label)."""
    current = "0:v"
    parts: list[str] = []

    for index, region in enumerate(regions):
        base = f"base{index}"
        crop = f"crop{index}"
        blurred = f"blur{index}"
        output = f"v{index}"
        parts.append(f"[{current}]split=2[{base}][{crop}]")
        parts.append(
            f"[{crop}]crop={region.width}:{region.height}:{region.x}:{region.y},"
            f"boxblur=luma_radius={region.blur}:luma_power=1[{blurred}]"
        )
        enable = f"between(t,{ff_number(region.start)},{ff_number(region.end)})"
        parts.append(
            f"[{base}][{blurred}]overlay={region.x}:{region.y}:enable='{enable}'[{output}]"
        )
        current = output

    return ";".join(parts), current


def build_command(input_path: Path, output_path: Path, regions: list[Region]) -> str:
    filter_complex, final_label = build_filter_complex(regions)
    args = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(input_path),
        "-filter_complex",
        filter_complex,
        "-map",
        f"[{final_label}]",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-preset",
        "medium",
        "-c:a",
        "copy",
        str(output_path),
    ]
    return " ".join(shlex.quote(arg) for arg in args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a static video-redaction plan and emit an FFmpeg blur command."
    )
    parser.add_argument("plan", type=Path, help="JSON plan containing a non-empty regions array")
    parser.add_argument("--input", required=True, type=Path, help="input video path")
    parser.add_argument("--output", required=True, type=Path, help="output video path")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        raw = json.loads(args.plan.read_text(encoding="utf-8"))
        regions = parse_plan(raw)
    except (OSError, UnicodeError, json.JSONDecodeError, PlanError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    command = build_command(args.input, args.output, regions)
    if args.json:
        print(
            json.dumps(
                {
                    "region_count": len(regions),
                    "input": str(args.input),
                    "output": str(args.output),
                    "command": command,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
