# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-11-04

### Fixed
- Pin `pypixelcolor` to 0.4.0. Version 0.5.0 (2026-09-08) removed the CUSONG, SIMSUN and VCR_OSD_MONO fonts that text mode uses by default, so fresh installs pulled an incompatible library.
- `manifest.json` version now matches the release (was still 0.1.0).

### Added
- Local brand icons in `custom_components/ipixel_color/brand/` for Home Assistant 2026.3 and newer (from upstream PR #47 by @frenck).

### Changed
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