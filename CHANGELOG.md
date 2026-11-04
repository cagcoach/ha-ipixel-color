# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Move to `pypixelcolor` 0.5.0. Its built-in text font is now GNU Unifont (SIL OFL 1.1, includes CJK); 0.5.0 dropped CUSONG, SIMSUN and VCR_OSD_MONO because they were not freely licensed. Text mode uses Unifont when no font is selected or the selected file is missing.
- Text mode now finds the selected font in every font location (this integration's `fonts/`, pypixelcolor's, and system font folders), not only `fonts/`.
- Per-height font metrics in a `<font>.json` file next to the font are still honoured. pypixelcolor 0.5 stopped reading them, so the integration now does.
- Text rendering runs in an executor instead of on the event loop.

 - 2026-11-04

### Fixed
- Pin `pypixelcolor` to 0.4.0. Version 0.5.0 (2026-09-08) removed the CUSONG, SIMSUN and VCR_OSD_MONO fonts that text mode uses by default, so fresh installs pulled an incompatible library.
- `manifest.json` version now matches the release (was still 0.1.0).
- Device info (panel size, type) failed on local BlueZ adapters with "Notify acquired", so panels were treated as 64x16. Notifications are now subscribed once per connection and shared by all commands.
- The 64x16 fallback is no longer kept after a failed device-info query; it is retried after the next reconnect.
- Long payloads are written in acknowledged chunks sized to the connection MTU (max 244 bytes), so long text no longer gets dropped through Bluetooth proxies (upstream #28, #12).
- Commands are serialized so chunks from two entities never interleave.
- The panel reconnects automatically after a dropped link (from upstream PR #44 by @arcdrake22).
- Clock sync uses Home Assistant's configured time zone instead of the host's (upstream PR #32).

### Added
- Font size option in text mode (upstream PR #35).
- Options flow to override the panel size the firmware reports (upstream PR #38).
- Local brand icons in `custom_components/ipixel_color/brand/` for Home Assistant 2026.3 and newer (from upstream PR #47 by @frenck).
- Unit tests and a GitHub Actions workflow that runs them.
- HACS and Hassfest validation, automatic GitHub releases on a manifest version bump, and Dependabot.

### Changed
- Minimum Home Assistant version is now 2024.12.
- Pillow is no longer listed as a requirement (it ships with Home Assistant).
- Documentation and issue tracker now point to this fork.

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