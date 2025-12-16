#!/usr/bin/env python3
"""Generate a countdown timer GIF."""

import argparse
import sys

from formatter import parse_duration
from gif_builder import build_timer_gif


def main():
    parser = argparse.ArgumentParser(description="Generate a countdown timer GIF")
    parser.add_argument("duration", help="Duration: 30s, 5m, 2:30, or seconds")
    parser.add_argument("-o", "--output", default="timer.gif", help="Output file")
    parser.add_argument("-s", "--font-size", type=int, default=72, help="Font size")
    parser.add_argument("-f", "--font", help="Path to font file")
    parser.add_argument("-W", "--width", type=int, help="Image width")
    parser.add_argument("-H", "--height", type=int, help="Image height")

    args = parser.parse_args()

    try:
        seconds = parse_duration(args.duration)
    except ValueError:
        print(f"Error: Invalid duration '{args.duration}'", file=sys.stderr)
        sys.exit(1)

    if seconds <= 0:
        print("Error: Duration must be positive", file=sys.stderr)
        sys.exit(1)

    frame_count = build_timer_gif(
        seconds,
        args.output,
        font_size=args.font_size,
        font_path=args.font,
        width=args.width,
        height=args.height
    )

    print(f"Created {args.output} ({frame_count} frames, {seconds}s)")


if __name__ == "__main__":
    main()
