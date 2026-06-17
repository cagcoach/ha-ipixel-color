#!/usr/bin/env python3
"""Render the 96x16 weather clock layout for local debugging."""
from __future__ import annotations

import argparse
import importlib.util
import sys
import types
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "custom_components" / "ipixel_color"


def _load_renderer():
    """Load the renderer without requiring Home Assistant to be installed."""
    custom_components = types.ModuleType("custom_components")
    custom_components.__path__ = [str(REPO_ROOT / "custom_components")]
    sys.modules.setdefault("custom_components", custom_components)

    ipixel_package = types.ModuleType("custom_components.ipixel_color")
    ipixel_package.__path__ = [str(PACKAGE_ROOT)]
    sys.modules.setdefault("custom_components.ipixel_color", ipixel_package)

    display_package = types.ModuleType("custom_components.ipixel_color.display")
    display_package.__path__ = [str(PACKAGE_ROOT / "display")]
    sys.modules.setdefault("custom_components.ipixel_color.display", display_package)

    for module_name, module_path in (
        ("custom_components.ipixel_color.fonts", PACKAGE_ROOT / "fonts.py"),
        (
            "custom_components.ipixel_color.display.weather_clock_renderer",
            PACKAGE_ROOT / "display" / "weather_clock_renderer.py",
        ),
    ):
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)

    return sys.modules[
        "custom_components.ipixel_color.display.weather_clock_renderer"
    ].render_weather_clock_to_png


def main() -> int:
    """Render a sample weather clock layout."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", default="sunny")
    parser.add_argument("--temperature", type=float, default=24)
    parser.add_argument("--time", default="22:45")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    render_weather_clock_to_png = _load_renderer()
    png_data = render_weather_clock_to_png(
        width=96,
        height=16,
        condition=args.condition,
        temperature=args.temperature,
        hour_minute=args.time,
        weekday_index=5,
        day=18,
        month=5,
    )

    output = args.output or REPO_ROOT / "debug_weather_clock_96x16.png"
    output.write_bytes(png_data)

    with Image.open(output) as image:
        width, height = image.size
        raw_rgb_payload = len(image.convert("RGB").tobytes())

    assert (width, height) == (96, 16)
    assert raw_rgb_payload == 96 * 16 * 3

    print(f"rendered={width}x{height}")
    print(f"raw_rgb_payload={raw_rgb_payload}")
    print(f"png_payload={len(png_data)}")
    print(f"output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
