"""Tests for the text-mode sizes a panel can draw."""
from __future__ import annotations

from custom_components.ipixel_color.const import text_mode_sizes


def test_20_row_panel_only_offers_16():
    assert text_mode_sizes(20) == [16]


def test_32_row_panel_offers_16_and_32():
    assert text_mode_sizes(32) == [16, 32]


def test_64_row_panel_offers_multiples_of_16():
    assert text_mode_sizes(64) == [16, 32, 48, 64]


def test_unknown_or_tiny_height_falls_back_to_16():
    assert text_mode_sizes(None) == [16]
    assert text_mode_sizes(8) == [16]
