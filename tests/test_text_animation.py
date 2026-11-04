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


def test_new_installs_default_to_scroll_left():
    from custom_components.ipixel_color.const import DEFAULT_TEXT_ANIMATION

    assert DEFAULT_TEXT_ANIMATION == "1 Scroll left"


# --- migration from the old Text Animation number -------------------------

import sys
import types
from types import SimpleNamespace

import pytest


@pytest.fixture
def select_mod(monkeypatch):
    """Import select.py with the few extra HA stubs it needs."""
    import homeassistant.helpers.restore_state as rs

    monkeypatch.setattr(rs, "async_get", lambda hass: None, raising=False)
    sel = types.ModuleType("homeassistant.components.select")
    sel.SelectEntity = type("SelectEntity", (), {})
    monkeypatch.setitem(sys.modules, "homeassistant.components.select", sel)
    for name, attrs in {
        "homeassistant.helpers.entity_platform": {"AddEntitiesCallback": object},
        "homeassistant.config_entries": {"ConfigEntry": object},
    }.items():
        if name not in sys.modules:
            monkeypatch.setitem(sys.modules, name, types.SimpleNamespace(**attrs))
    sys.modules.pop("custom_components.ipixel_color.select", None)
    import custom_components.ipixel_color.select as mod

    return mod


def _fake_entity(mod):
    ent = SimpleNamespace(hass=object())
    ent._old_number_entity_id = lambda: "number.panel_text_animation"
    return ent


def _stored(value):
    return SimpleNamespace(state=SimpleNamespace(state=value))


def test_migration_uses_new_accessor(select_mod, monkeypatch):
    data = SimpleNamespace(async_get_stored_state=lambda eid: _stored("3"))
    monkeypatch.setattr(select_mod, "async_get_restore_data", lambda hass: data)
    cls = select_mod.iPIXELTextAnimationSelect
    assert cls._migrate_from_number(_fake_entity(select_mod)) == ("3 Scroll up", True)


def test_migration_falls_back_to_last_states(select_mod, monkeypatch):
    data = SimpleNamespace(last_states={"number.panel_text_animation": _stored("2.0")})
    monkeypatch.setattr(select_mod, "async_get_restore_data", lambda hass: data)
    cls = select_mod.iPIXELTextAnimationSelect
    assert cls._migrate_from_number(_fake_entity(select_mod)) == ("2 Scroll right", True)


def test_unreadable_restore_data_keeps_old_entity(select_mod, monkeypatch):
    monkeypatch.setattr(select_mod, "async_get_restore_data", lambda hass: SimpleNamespace())
    cls = select_mod.iPIXELTextAnimationSelect
    assert cls._migrate_from_number(_fake_entity(select_mod)) == (None, False)
