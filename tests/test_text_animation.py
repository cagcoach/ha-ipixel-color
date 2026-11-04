"""Tests for the text animation select options."""
from __future__ import annotations

from custom_components.ipixel_color.const import (
    TEXT_ANIMATION_OPTIONS,
    text_animation_option,
    text_animation_value,
)


def test_options_show_number_then_name():
    assert TEXT_ANIMATION_OPTIONS[0] == "0 Static"
    assert TEXT_ANIMATION_OPTIONS[1] == "1 Scroll left"
    assert TEXT_ANIMATION_OPTIONS[7] == "7 Snowflake"
    assert len(TEXT_ANIMATION_OPTIONS) == 8


def test_value_round_trips():
    for value in range(8):
        assert text_animation_value(text_animation_option(value)) == value


def test_bad_values_fall_back_to_static():
    assert text_animation_value(None) == 0
    assert text_animation_value("unknown") == 0
    assert text_animation_value("9 Nope") == 0
    assert text_animation_option(42) == "0 Static"
