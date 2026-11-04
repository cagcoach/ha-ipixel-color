"""Tests for resolving text-mode fonts against pypixelcolor 0.5."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pypixelcolor")

from pypixelcolor.lib.font_config import UNIFONT_PATH, FontConfig  # noqa: E402

from custom_components.ipixel_color.device.text import (  # noqa: E402
    BUILTIN_FONT,
    make_text_command,
    resolve_text_font,
)

FONTS = Path(__file__).parent.parent / "custom_components" / "ipixel_color" / "fonts"


def test_missing_or_unset_font_uses_builtin():
    assert resolve_text_font(None, 16) == BUILTIN_FONT
    assert resolve_text_font("CUSONG", 16) == BUILTIN_FONT
    assert resolve_text_font("/nope/CUSONG.ttf", 16) == BUILTIN_FONT


def test_pypixelcolor_unifont_file_uses_builtin_tuning():
    assert resolve_text_font(UNIFONT_PATH, 16) == BUILTIN_FONT


def test_sidecar_json_metrics_are_applied():
    cfg = resolve_text_font(str(FONTS / "7x5.ttf"), 32)
    assert isinstance(cfg, FontConfig)
    assert cfg.font_size == 25
    assert cfg.offset == (0, 2)
    assert cfg.pixel_threshold == 85
    assert cfg.var_width is True


def test_closest_height_metrics_are_used():
    cfg = resolve_text_font(str(FONTS / "7x5.ttf"), 20)
    assert cfg.font_size == 16  # 16 is closer to 20 than 24


def test_font_without_json_gets_04_defaults(tmp_path):
    font = tmp_path / "Plain.ttf"
    font.write_bytes((FONTS / "5x5.ttf").read_bytes())
    cfg = resolve_text_font(str(font), 16)
    assert cfg.font_size == 16
    assert cfg.offset == (0, 0)
    assert cfg.pixel_threshold == 70


def test_bad_json_falls_back_to_defaults(tmp_path):
    font = tmp_path / "Odd.ttf"
    font.write_bytes((FONTS / "5x5.ttf").read_bytes())
    (tmp_path / "Odd.json").write_text(json.dumps({"metrics": "nope"}))
    cfg = resolve_text_font(str(font), 16)
    assert cfg.pixel_threshold == 70


@pytest.mark.parametrize("font", [None, str(FONTS / "7x5.ttf"), str(FONTS / "OpenSans-Light.ttf")])
def test_text_command_builds_with_05(font):
    commands = make_text_command("HomeAssistant!", font=font, animation=1, rainbow_mode=1, char_height=16)
    assert commands and all(isinstance(c, (bytes, bytearray)) for c in commands)
