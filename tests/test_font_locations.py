"""User fonts in <config>/fonts are found first."""
from __future__ import annotations

from custom_components.ipixel_color import fonts


def test_config_fonts_dir_is_first_and_searched(tmp_path):
    (tmp_path / "Mine.ttf").write_bytes(b"x")
    fonts.set_config_fonts_dir(tmp_path)
    try:
        locations = fonts.get_font_locations()
        assert locations[0] == tmp_path
        assert "Mine.ttf" in fonts.get_available_fonts(locations)
        assert fonts.get_font_path("Mine.ttf", locations) == tmp_path / "Mine.ttf"
    finally:
        fonts.set_config_fonts_dir(None)


def test_missing_config_fonts_dir_is_skipped(tmp_path):
    fonts.set_config_fonts_dir(tmp_path / "absent")
    try:
        assert tmp_path / "absent" not in fonts.get_font_locations()
    finally:
        fonts.set_config_fonts_dir(None)
