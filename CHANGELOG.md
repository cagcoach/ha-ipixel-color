# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Font size option in text mode (upstream PR #35).
- Options flow to override the panel size the firmware reports (upstream PR #38).
- Local brand icons in `custom_components/ipixel_color/brand/` for Home Assistant 2026.3 and newer (from upstream PR #47 by @frenck).
- Unit tests and a GitHub Actions workflow that runs them.
- HACS and Hassfest validation, automatic GitHub releases on a manifest version bump, and Dependabot.

### Changed
- Move to `pypixelcolor` 0.5.0. Its built-in text font is now GNU Unifont (SIL OFL 1.1, includes CJK); 0.5.0 dropped CUSONG, SIMSUN and VCR_OSD_MONO because they were not freely licensed. Text mode uses Unifont when no font is selected or the selected file is missing.
- Text mode now finds the selected font in every font location (this integration's `fonts/`, pypixelcolor's, and system font folders), not only `fonts/`.
- Per-height font metrics in a `<font>.json` file next to the font are still honoured. pypixelcolor 0.5 stopped reading them, so the integration now does.
- User fonts can go in `/config/fonts/`, which HACS updates don't touch. It is searched first, before the integration's bundled `fonts/`.
- Text rendering runs in an executor instead of on the event loop.
 - 2026-11-04
- Minimum Home Assistant version is now 2024.12.
- Pillow is no longer listed as a requirement (it ships with Home Assistant).
- Documentation and issue tracker now point to this fork.
- Text mode has its own **Text Size** dropdown that lists only the sizes the panel can draw (multiples of 16 up to the panel height: just 16 on a 20-row panel, 16 and 32 on a 32-row panel). Before, it used Font Size, which let you pick values like 10 or 20 that rendered the same as 16.
- Font Size is renamed **Image Font Size** and now applies only to textimage mode, where any size works. Its entity ID is unchanged.
- New installs start in `text` mode with the Unifont font (pypixelcolor 0.5's built-in), font size 16 (the smallest text mode renders), Text Rainbow 1 and the text "HomeAssistant!". Existing installs keep their restored settings.
- Text Animation is now a dropdown that names each effect ("0 Static", "1 Scroll left", "2 Scroll right", "3 Scroll up", "4 Scroll down", "5 Blink", "6 Fade", "7 Snowflake") instead of a 0-7 number, defaulting to "1 Scroll left" on new installs. The old number entity is removed and its value carried over; automations that set `number.<device>_text_animation` need to use `select.select_option` on the new select.
- MCU Version and WiFi Version sensors are disabled by default on new installs. pypixelcolor does not decode them, so they always showed "unknown". Existing installs keep them until you disable them on the device page.

### Fixed
- Pin `pypixelcolor` to 0.4.0. Version 0.5.0 (2026-09-08) removed the CUSONG, SIMSUN and VCR_OSD_MONO fonts that text mode uses by default, so fresh installs pulled an incompatible library.
- `manifest.json` version now matches the release (was still 0.1.0).
- Device info (panel size, type) failed on local BlueZ adapters with "Notify acquired", so panels were treated as 64x16. Notifications are now subscribed once per connection and shared by all commands.
- The 64x16 fallback is no longer kept after a failed device-info query; it is retried after the next reconnect.
- Long payloads are written in acknowledged chunks sized to the connection MTU (max 244 bytes), so long text no longer gets dropped through Bluetooth proxies (upstream #28, #12).
- Commands are serialized so chunks from two entities never interleave.
- The panel reconnects automatically after a dropped link (from upstream PR #44 by @arcdrake22).
- Clock sync uses Home Assistant's configured time zone instead of the host's (upstream PR #32).
- The font list was scanned inside the event loop at setup, which Home Assistant reports as a blocking call. It is now scanned in the executor.
- The power switch showed off after setup even though the panel was on. The panel cannot report its power state, so the switch now starts on and restores its last state after a Home Assistant restart.

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