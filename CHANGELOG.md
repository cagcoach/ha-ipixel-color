# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- All `ipixel_color.*` actions (`send_mdi_icon`, `send_text`, `send_layout`, `send_test_pattern`,
  `send_image_file`) are now registered once at integration setup (`async_setup` in
  `__init__.py`, via the new `services.py`) instead of per-config-entry inside `text.py`'s
  `async_setup_entry`, per Home Assistant's own guidance
  (https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-setup/).
  Previously, an action only existed in Home Assistant's service registry once a specific
  device's config entry had finished loading - automations validated before that (typically
  during Home Assistant startup) could be briefly flagged with "unknown action", even though
  the action worked correctly moments later once setup completed. The entity methods
  themselves (`async_send_mdi_icon`, etc.) are unchanged; only where and how they're
  registered changed, using `homeassistant.helpers.service.async_register_platform_entity_service`.
- `send_layout`'s word-wrap now falls back to splitting character-by-character when a single
  space-free "word" (e.g. a long digit string or ID with no natural spaces) is wider than the
  available width on its own. Previously such text was kept whole and allowed to overflow
  past the panel edge instead of wrapping to a new line.
- `send_layout`'s text `align` ('right'/'center') now actually anchors the corresponding edge
  or center of the text block at `x` (e.g. `align: right` makes the text's right edge land at
  `x`, extending leftward). Previously `align` only affected how multiple `\n`-separated lines
  aligned relative to each other within the block, leaving single-line text always anchored by
  its left edge regardless of `align` - so e.g. a right-aligned single line at `x=32` could run
  off the panel's edge instead of ending at `x=32` as expected.

### Added

- Bundled a new font, `Lepidos` (3x7 pixel font, CC0/public domain, by SurrealEmber -
  https://surrealember.itch.io/lepidos), designed to be rendered at multiples of 16px for
  crisp, correctly-proportioned glyphs.
- New service `ipixel_color.send_mdi_icon`: renders any Material Design Icon (fetched on
  demand from the jsDelivr mirror of `@mdi/svg`, no bundling required) and displays it
  centered on the panel, with configurable color, background color, size, and save slot.
- New service `ipixel_color.send_text`: sends text via pypixelcolor's native renderer
  (device animation/scroll/speed/rainbow), independent of the `text.{device}_display`
  entity's stored state - safe to call repeatedly from automations.
- New service `ipixel_color.send_layout`: composes up to 4 independent MDI icons, a static
  image/GIF-first-frame, and/or up to 4 independent text elements, each at independent (x, y)
  positions, onto a single canvas:
  - Up to 4 icons can be given via the new `icons` list field (YAML-only); the original flat
    `icon`/`icon_x`/... fields remain for a single icon and are ignored if `icons` is given.
    Icons never scroll, but can blink.
  - Text supports dynamic font sizing (any pixel size, including fractional), bundled pixel
    fonts (`3x5-de`, `5x5`, `7x5`, `Lepidos`, plus `OpenSans-Light` and `WP7xn`), automatic
    word-wrap at the panel's edge, forced line breaks via `\n` (works both as a real newline
    from YAML and as a literal backslash-n typed into a plain GUI text field), and
    left/right/center alignment (`align`/`text_align`) within the text's own block.
  - Text width is now measured via the font's advance metrics rather than its ink bounding
    box, so leading/trailing/internal spaces are preserved (useful for manual alignment via
    code) instead of being invisibly trimmed away. Word-wrapping still reflows text and does
    not preserve exact spacing - disable wrap if exact spacing matters.
  - Text too wide to fit can scroll continuously (looping marquee GIF, `scroll: true`)
    instead of being clipped, with configurable shared speed and loop gap.
  - Any icon or text can blink on/off (`blink: true`, `blink_interval_ms`), independent of and
    combinable with scrolling. Multiple scrolling and/or blinking elements are kept in sync
    with each other (their cycles realign together, via the least common multiple of their
    individual cycle lengths, capped to avoid runaway frame counts).
  - Up to 4 texts can be given via the new `texts` list field (YAML-only); the original flat
    `text`/`text_x`/... fields remain for a single text and are ignored if `texts` is given.
  - An existing image or GIF file (its first frame, if animated) can be inserted alongside
    the icons/text via `image_path`, with optional resizing.
  - Templates in `text`/`icon` resolve when the service is called from an automation/script
    (Home Assistant's own engine renders them before the call); they do not resolve if typed
    literally into the Developer Tools → Actions test field, and these services are one-shot
    (no auto-update on sensor changes) - see the README for details.
  - Native device-side text scrolling (`ipixel_color.send_text`, below) remains lighter/faster
    but always takes over the whole panel as a single string - it cannot be combined with an
    icon/image/other text, since the device protocol has no sub-region concept; scrolling
    *within* a layout composition is only achievable via generated GIF frames, which is
    inherently heavier to transfer than the native path. Measured: `scroll_step` is the one
    parameter that reliably reduces transfer size/time (doubling it roughly halves both frame
    count and bytes); frame deduplication and palette quantization were also added, though
    they mainly help short text with long pauses rather than a single long scrolling word.
  - The BLE ACK timeout for image/GIF sends (`send_mdi_icon`, `send_layout`,
    `send_test_pattern`, `send_image_file`) was raised from pypixelcolor's 8s default to 25s -
    a complex multi-frame GIF (e.g. several simultaneously-scrolling texts) can need more time
    for the device to process before it acknowledges, and would otherwise fail with
    `cur12k_no_answer: no ack from device` even though the transfer itself was fine.
- New service `ipixel_color.send_image_file`: sends an existing image or GIF file (read from
  disk, e.g. under `/config/www/`) as-is - PNG, GIF (including animated, frame-by-frame with
  original durations), JPEG, BMP, TIFF, WEBP, HEIC/HEIF.
- New diagnostic service `ipixel_color.send_test_pattern`: sends a 4-quadrant colored test
  image sized to the panel, to help verify how the device's reported width/height maps onto
  the physical panel.

### Changed

- `send_layout` text rendering now thresholds to pure black/white instead of using FreeType's
  default anti-aliasing, which was blurring the crisp square edges pixel-style fonts are
  meant to have on an LED matrix. Applies regardless of font or size.
- `bluetooth/client.py`: replaced the previous per-call `stop_notify`/`start_notify` churn
  with a single persistent Bluetooth notification subscription and a persistent `AckManager`
  for the whole connection lifetime, matching pypixelcolor's own reference
  `DeviceSession`/`Client`. The previous pattern (tearing down and re-enabling the ACK
  listener around every single command) was a likely source of dropped ACKs on real
  hardware, and caused a hard failure in `get_device_info()`
  (`Notifications are already enabled`).
- `get_device_info()` now goes through `BluetoothClient` instead of touching the raw `bleak`
  client/characteristics directly.
- `device/image.py`: `make_image_command()` now forwards `save_slot` through to
  pypixelcolor's `send_image_hex` (previously silently dropped), and returns the raw
  `SendPlan` object so callers can use the new chunked+ACK transport correctly for
  multi-byte image payloads.

### Dependencies

- Added `resvg_py` for SVG-to-PNG rasterization of MDI icons (self-contained wheel, no
  system-level SVG library dependency).

### Notes

- Tested against a real device (64x16 reported / 32x32 physical panel): `send_mdi_icon`,
  `send_text`, `send_layout` (static and scrolling), `send_image_file`, and
  `send_test_pattern` all confirmed working, including automatic text wrapping and forced
  line breaks. Large/complex GIFs may need a longer device-side processing time; see the
  README's troubleshooting section for `cur12k_no_answer` errors.

## [0.1.0] - 2024-11-19

### Added

- Initial release of iPIXEL Color Home Assistant integration
- Bluetooth auto-discovery of iPIXEL devices (`LED_BLE_*` pattern)
- Basic power on/off control via switch entity
- Manual device configuration as fallback
- Proper Home Assistant device registry integration
- Connection management with error handling
- Configuration flow with discovery and manual entry options
- English translations and UI strings

### Technical Details

- Implements core Bluetooth protocol commands based on reverse-engineered documentation
- Uses `bleak` library for cross-platform Bluetooth Low Energy communication
- Follows Home Assistant integration best practices
- Power commands: `[5, 0, 7, 1, 1]` (on) / `[5, 0, 7, 1, 0]` (off)
- Bluetooth UUIDs:
  - Write: `0000fa02-0000-1000-8000-00805f9b34fb`
  - Notify: `0000fa03-0000-1000-8000-00805f9b34fb`

### Limitations

- Only basic power control in this version
- No brightness, color, or image upload features yet
- Single switch entity per device

### Coming in Future Versions

- v0.2.0: Brightness control and basic light entity
- v0.3.0: RGB color control and display modes
- v0.4.0: Image/GIF upload and media player entity
- v1.0.0: Complete feature set and HACS submission
