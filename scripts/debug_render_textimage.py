#!/usr/bin/env python3
"""Render a 96x16 textimage payload for local debugging."""
from __future__ import annotations

import argparse
import importlib.util
import types
import sys
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
            "custom_components.ipixel_color.display.text_renderer",
            PACKAGE_ROOT / "display" / "text_renderer.py",
        ),
    ):
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)

    return sys.modules[
        "custom_components.ipixel_color.display.text_renderer"
    ].render_text_to_png


def main() -> int:
    """Render TEST/TEST and validate image dimensions."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=96)
    parser.add_argument("--height", type=int, default=16)
    parser.add_argument("--font", default="5x5.ttf")
    parser.add_argument("--font-size", type=float, default=7.0)
    parser.add_argument("--line-spacing", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    render_text_to_png = _load_renderer()

    png_data = render_text_to_png(
        "TEST\nTEST",
        args.width,
        args.height,
        antialias=False,
        font_size=args.font_size,
        font=args.font,
        line_spacing=args.line_spacing,
    )

    output = args.output or REPO_ROOT / "debug_textimage_96x16.png"
    output.write_bytes(png_data)

    with Image.open(output) as image:
        rendered_width, rendered_height = image.size
        raw_rgb_payload = len(image.convert("RGB").tobytes())

    expected_pixels = args.width * args.height
    expected_rgb_payload = expected_pixels * 3
    assert (rendered_width, rendered_height) == (args.width, args.height)
    assert raw_rgb_payload == expected_rgb_payload

    print(f"rendered={rendered_width}x{rendered_height}")
    print(f"pixels={expected_pixels}")
    print(f"raw_rgb_payload={raw_rgb_payload}")
    print(f"png_payload={len(png_data)}")
    print(f"output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
