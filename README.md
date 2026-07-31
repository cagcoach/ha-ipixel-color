# iPIXEL Color - Home Assistant Integration

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/A4747U9)

A Home Assistant custom integration for iPIXEL Color LED matrix displays via Bluetooth.
These displays have been recently available as B.K. Light LED Pixel Board from Action and thus get increasing popularity.

## Features

- **Multiple Display Modes**: Text Image (PIL rendering), Native Text, and Clock modes
- **RGB Color Support**: Separate text and background colors via RGB light entities
- **Clock Display**: 9 different clock styles with automatic time synchronization
- **Rich Text Display**: Custom fonts, sizes, multiline text with `\n`, antialiasing
- **MDI Icons**: Render and display any Material Design Icon, fetched on demand
- **Custom Layouts**: Compose up to 4 MDI icons, an image/GIF, and/or up to 4 independent text elements at independent positions on the panel, with left/right/center alignment, optional (synchronized) scrolling and/or blinking, and forced/automatic line wrapping that preserves exact spacing when disabled
- **Send Existing Images/GIFs**: Display any image or animated GIF file readable by Home Assistant
- **Template Support**: Use Home Assistant variables like `{{ states('sensor.temperature') }}°C`
- **Font Management**: Load TTF/OTF fonts from `fonts/` folder
- **Brightness Control**: Adjustable display brightness (1-100)
- **Auto/Manual Updates**: Choose automatic updates or manual refresh
- **State Persistence**: Settings preserved across HA restarts
- **Bluetooth Proxy Support**: Compatible with Bluetooth proxy devices
- **Auto-discovery**: Finds iPIXEL devices automatically via Bluetooth

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on the three dots in the top right corner
3. Select **Custom repositories**
4. Add the repository URL: `https://github.com/cagcoach/ha-ipixel-color`
5. Select **Integration** as the category
6. Click **Add**
7. Search for "iPIXEL Color" in HACS and install it
8. Restart Home Assistant
9. Add the integration via Settings → Devices & Services → Add Integration

### Manual Installation

1. Copy `custom_components/ipixel_color` to your HA `custom_components` directory
2. Restart Home Assistant
3. Add integration via Settings → Devices & Services → Add Integration

### Optional: Custom Fonts

Place `.ttf`/`.otf` font files in the `fonts/` folder within the integration directory for additional font options.
Bundled pixel fonts (`3x5-de.ttf`, `5x5.ttf`, `7x5.ttf`) are good defaults for small matrices; `3x5-de` is the smallest.

## Entities

Once configured, you'll get these entities:

**Display Control:**

- `select.{device}_mode` - Display mode (textimage, text, clock)
- `text.{device}_display` - Enter text with templates and `\n` for newlines
- `switch.{device}_power` - Turn display on/off
- `number.{device}_brightness` - Display brightness level (1-100)

**Text Appearance:**

- `select.{device}_font` - Choose from available fonts
- `number.{device}_font_size` - Font size (0=auto, supports decimals like 12.5)
- `number.{device}_line_spacing` - Spacing between lines (0-20px)
- `switch.{device}_antialiasing` - Smooth vs sharp text
- `light.{device}_text_color` - RGB text color
- `light.{device}_background_color` - RGB background color

**Clock Mode:**

- `select.{device}_clock_style` - Clock style (0-8)
- `switch.{device}_clock_24h_format` - 24-hour time format
- `switch.{device}_clock_show_date` - Show date below time

**Update Control:**

- `switch.{device}_auto_update` - Auto-update on changes
- `button.{device}_update_display` - Manual refresh

**Device Info:**

- `sensor.{device}_width` - Display width in pixels
- `sensor.{device}_height` - Display height in pixels
- `sensor.{device}_device_type` - Device model information

## Template Examples

```jinja2
Time: {{ now().strftime('%H:%M') }}
Temp: {{ states('sensor.temperature') | round(1) }}°C
{% if is_state('sun.sun', 'above_horizon') %}Day{% else %}Night{% endif %}
```

## Quick Start

**Text Mode:**

1. Select mode: `textimage` (for RGB colors) or `text` (native)
2. Set text: `"Hello\nWorld"`
3. Choose text and background colors using light entities
4. Select font and size (or use auto-sizing)
5. Toggle auto-update ON or use manual update button

**Clock Mode:**

1. Select mode: `clock`
2. Choose clock style (0-8)
3. Set 24-hour format and date display preferences
4. Time syncs automatically

**Templates:**

- Templates update automatically with sensor changes when auto-update is ON

## Services (MDI Icons, Custom Layouts, Direct Text)

These are `ipixel_color.*` actions, callable from Developer Tools → Actions or from any
automation/script. Unlike the `text.{device}_display` entity above (tied to the mode/color/font
entities and auto-update), these render and send an image directly, independent of the
panel's currently selected mode.

> **Templates:** `text`/`icon` fields in these services do **not** resolve Home Assistant
> templates themselves (unlike `text.{device}_display`, which explicitly re-renders templates
> server-side). A template like `{{ states('sensor.temperature') }}°C` works fine when the
> service is called from an automation or script - Home Assistant's own automation engine
> renders templates in the `data:` block before the service is called. It will **not** render
> if typed literally into the test field under Developer Tools → Actions (same caveat as `\n`
> typed there). These services are also **one-shot**: unlike `text.{device}_display` with
> auto-update, they don't re-render on their own when the underlying sensor changes - trigger
> the automation again (e.g. on the sensor's `state_changed`) to refresh the panel.

### `ipixel_color.send_mdi_icon`

Renders any [Material Design Icon](https://pictogrammers.com/library/mdi/) (fetched on
demand, no need to pre-install anything) and shows it centered on the panel.

```yaml
action: ipixel_color.send_mdi_icon
target:
  entity_id: text.living_room_display
data:
  icon: "mdi:weather-sunny"
  color: [255, 204, 0]
  bg_color: [0, 0, 0]
  scale: 100          # 1-100, percentage of the panel's shorter side
  save_slot: 0        # 0 = don't save, >=1 = save to that device memory slot
```

### `ipixel_color.send_text`

Sends text using pypixelcolor's native renderer (device-side animation/scroll), with its own
parameters each call - independent of the panel's currently selected text/effect/colors, so
it's safe to call from automations without disturbing manual use of the panel.

```yaml
action: ipixel_color.send_text
target:
  entity_id: text.living_room_display
data:
  text: "{{ states('sensor.temperature') }}°C"
  color: [255, 255, 255]
  bg_color: [0, 0, 0]     # omit for a transparent background
  font: "CUSONG"          # or "SIMSUN", "VCR_OSD_MONO"
  animation: 0            # 0-7; pypixelcolor itself rejects 3/4 on non-32x32 panels
  speed: 80               # 0-100
  rainbow_mode: 0         # 0-9, 0 = disabled
```

### `ipixel_color.send_layout`

Composes up to 4 independent MDI icons, a static image/GIF-first-frame, and/or up to 4
independent text elements - each positioned by its own top-left (x, y) corner in pixels -
onto a single canvas sent as one image. Useful for e.g. an icon on the left with a value next
to it, several status icons in a row, or several labels stacked with their own sizes/fonts/colors.

**Single icon and single text** - use the flat fields, same as before:

```yaml
action: ipixel_color.send_layout
target:
  entity_id: text.living_room_display
data:
  icon: "mdi:weather-sunny"
  icon_x: 0
  icon_y: 0
  icon_size: 16          # square icon size in pixels; omitted = panel's shorter side
  icon_color: [255, 204, 0]
  image_path: "/config/www/logo.png"  # optional: any image/GIF file readable by HA
  image_x: 40                          # (only its first frame is used, if animated)
  image_y: 0
  image_width: 16                     # optional: resize
  image_height: 16
  text: "21°C"
  text_x: 18
  text_y: 4
  text_size: 8           # font size in pixels, can be fractional (e.g. 7.5)
  text_font: "7x5"        # "3x5-de" (smallest), "5x5", "7x5", "Lepidos" (3x7), "OpenSans-Light", "WP7xn"
  text_color: [255, 255, 255]
  text_wrap: true         # auto word-wrap at the panel's right edge
  text_line_spacing: 1    # extra pixels between wrapped/forced lines
  text_scroll: false      # see below
  bg_color: [0, 0, 0]
  save_slot: 0
```

`icon`, `image_path` and `text` are all optional independently - use any combination, or just
one of them.

**Multiple texts** (up to 4) - use `texts` instead of the flat `text`/`text_x`/... fields
(YAML-only, not practical from the Developer Tools UI form). If given, `texts` takes priority
over the flat fields:

```yaml
action: ipixel_color.send_layout
target:
  entity_id: text.living_room_display
data:
  texts:
    - text: "Living room"
      x: 0
      y: 0
      size: 6
    - text: "21°C"
      x: 0
      y: 8
      size: 8
      color_hex: "ffcc00"
      scroll: true   # see below - this one scrolls, the one above stays static
```

Each item accepts: `text` (required), `x`, `y`, `size`, `font`, `color_hex`, `wrap`, `align`,
`scroll`, `line_spacing`, `blink`, `blink_interval_ms` - same meaning as the single-text fields
above (and below), just per item.

**Alignment:** `align` (or `text_align` for the single-text form) changes what `x`/`y` anchor:
`left` (default) anchors the text's left edge at `x` (unchanged from before); `right` anchors
its right edge at `x` (the text extends leftward from there); `center` anchors its horizontal
center at `x`. With multiple `\n`-separated lines of different widths, each line is also
aligned within the block itself the same way. Only static (non-scrolling) text is anchored
this way - scrolling text always anchors its left edge at `x` and moves rightward through the
available space, since a moving block has no fixed edge to anchor mid-scroll.

```yaml
# Right-align a value so it always ends flush at x=32, regardless of length
texts:
  - text: "12345"
    x: 32
    y: 4
    align: "right"
    wrap: false
```

**Preserving exact spacing:** word-wrap (`wrap`/`text_wrap: true`) reflows text and does not
preserve exact spacing between words. If you need leading/trailing/internal spaces exactly as
given (e.g. for manual alignment via spaces in the text itself), set `wrap: false` -
`send_layout` measures text by its font advance width, so spaces contribute to the layout
instead of being invisibly trimmed.

**Blinking:** set `blink: true` (plus optional `blink_interval_ms`, default 500) on any icon or
text item to make it blink on/off continuously - independent of, and combinable with,
scrolling text. Multiple blinking and/or scrolling elements are kept in sync with each other
(same least-common-multiple mechanism as multi-text scrolling, below).

```yaml
action: ipixel_color.send_layout
target:
  entity_id: text.living_room_display
data:
  icons:
    - icon: "mdi:water-alert"
      x: 0
      y: 0
      size: 16
      blink: true
      blink_interval_ms: 300
  texts:
    - text: "ALARM"
      x: 16
      y: 4
      size: 8
      blink: true
      blink_interval_ms: 300
```

**Multiple icons** (up to 4) - use `icons` instead of the flat `icon`/`icon_x`/... fields
(YAML-only). If given, `icons` takes priority over the flat fields. Icons are always static
(no scrolling):

```yaml
action: ipixel_color.send_layout
target:
  entity_id: text.living_room_display
data:
  icons:
    - icon: "mdi:weather-sunny"
      x: 0
      y: 0
      size: 16
      color_hex: "ffcc00"
    - icon: "mdi:water-percent"
      x: 16
      y: 0
      size: 16
      color_hex: "3399ff"
```

Each item accepts: `icon` (required), `x`, `y`, `size`, `color_hex`, `blink`, `blink_interval_ms`.
Icons never scroll, but can blink (see below).

Forcing a line break regardless of `wrap`/`text_wrap`: use `\n` in any text (works whether
typed literally into a GUI text field or as a real newline from YAML), e.g.
`text: "Living room\n21°C"`.

**Scrolling text:** set `wrap: false` (or `text_wrap: false` for the single-text form) and
`scroll: true` (or `text_scroll: true`) to make text too wide for the available space scroll
continuously (looping marquee GIF) instead of being clipped. No effect if the text already
fits - it's sent as a plain static image in that case. If more than one text in `texts`
scrolls, they're kept in sync with each other (their loops realign together, computed via the
least common multiple of their individual cycle lengths, capped to avoid runaway frame
counts on awkward combinations).

```yaml
action: ipixel_color.send_layout
target:
  entity_id: text.living_room_display
data:
  text: "This message is too long to fit and will scroll"
  text_x: 0
  text_wrap: false
  text_scroll: true
  scroll_step: 2        # pixels moved per animation frame, shared by every scrolling text
  scroll_frame_ms: 80    # duration of each frame, in ms
  scroll_gap: 16         # blank pixels between the end of one pass and the next
```

> **Native vs. composed scrolling:** `ipixel_color.send_text` (below) scrolls text natively
> on the device - lighter and faster, but it always takes over the *entire* panel as a single
> string; it cannot be combined with an icon, an image, or other text, because the device
> protocol has no concept of a sub-region. Scrolling text *within* a `send_layout` composition
> is only achievable by generating the animation frames ourselves (as above), which is
> inherently heavier to transfer - expect it to take longer to load than a native
> `send_text` call, though it plays back smoothly once loaded.
>
> GIF sending (used by scrolling text, and by `send_image_file` below) is a newer code path
> than static images - if you hit `cur12k_no_answer: no ack from device` in the logs, or the
> panel just takes a long time to update, the device needs more time/data than for a static
> image. In practice, `scroll_step` is the one lever that reliably helps: doubling it roughly
> halves both the frame count and the transferred bytes (measured: a single long scrolling
> word at `scroll_step: 2` produced a 69-frame/13KB GIF; at `scroll_step: 4`, ~35 frames/6.4KB)
> - at the cost of a choppier motion. `send_layout` already merges identical consecutive
> frames and uses a small quantized color palette to keep GIFs as small as it can, but for a
> single long word filling most of the available width, there typically aren't any identical
> frames to merge, so `scroll_step` remains the main thing to adjust if a scroll is too slow
> to load. The BLE ACK timeout for image/GIF sends is already set higher (25s) than
> pypixelcolor's small-command default (8s) to give the device room to process bigger GIFs.

### `ipixel_color.send_image_file`

Sends an existing image or GIF file, read from disk, as-is. Supports PNG, GIF (including
animated GIFs, sent frame-by-frame with their own durations), JPEG, BMP, TIFF, WEBP, and
HEIC/HEIF. The file must be in a location Home Assistant can read, such as `/config/www/`.

```yaml
action: ipixel_color.send_image_file
target:
  entity_id: text.living_room_display
data:
  file_path: "/config/www/my_animation.gif"
  resize_method: "crop"   # "crop" fills the panel and crops excess, "fit" pads with black
  save_slot: 0
```

### `ipixel_color.send_test_pattern`

Diagnostic only: sends a 4-quadrant colored pattern (red/green/blue/yellow) sized to the
panel, useful for verifying how the device's reported width/height maps onto the physical
panel when the two don't obviously match.

```yaml
action: ipixel_color.send_test_pattern
target:
  entity_id: text.living_room_display
```

## Font Management

- Place `.ttf`/`.otf` files in `fonts/` folder
- Restart HA to see new fonts in dropdown
- Recommended: pixel fonts like 5x5.ttf, 7x7.ttf
- The same bundled fonts (`3x5-de`, `5x5`, `7x5`, `Lepidos`, `OpenSans-Light`, `WP7xn`) are
  also available to `send_layout`'s `text_font` field
- `Lepidos` is a 3x7 pixel font (CC0/public domain, by SurrealEmber -
  https://surrealember.itch.io/lepidos), designed to be rendered at multiples of 16px
  (`text_size: 16`, `32`, ...) for crisp, correctly-proportioned glyphs
- Text rendering in `send_layout` thresholds to pure black/white (no anti-aliasing), so pixel
  fonts stay crisp regardless of size

## Troubleshooting

- Enable debug logging: `custom_components.ipixel_color: debug`
- Check auto-update is ON or use manual update button
- Verify templates in Developer Tools → Template
- Ensure device is in Bluetooth range
- For `send_mdi_icon`/`send_layout` failures, check that the device could reach
  `cdn.jsdelivr.net` (icons are fetched on demand, not bundled)
- For `send_layout` (scrolling text) or `send_image_file` failures with
  `cur12k_no_answer: no ack from device` in the logs, the GIF is likely too large/complex for
  the device to process in time - try a shorter message, fewer scroll frames
  (`text_scroll_step` higher), or a smaller source GIF file

## Status

| Feature | Status |
|---------|--------|
| ✅ Text Display (3 modes) | Complete |
| ✅ RGB Colors | Complete |
| ✅ Clock Mode (9 styles) | Complete |
| ✅ Custom Fonts | Complete |
| ✅ Templates | Complete |
| ✅ State Persistence | Complete |
| ✅ Brightness Control | Complete |
| ✅ MDI Icons | Complete |
| ✅ Custom Icon+Image+Text Layouts | Complete |
| ✅ Scrolling Text | Complete |
| ✅ Send Existing Image/GIF Files | Complete |
| 🔄 GIF Animations | Planned |
| 🔄 Animated Variable-Width Fonts | Planned |

## Technical

- Requires: Home Assistant 2024.1+ and HACS

## Acknowledgments

Special thanks to the authors of [pypixelcolor](https://github.com/lucagoc/pypixelcolor) for their excellent library that powers the core functionality of this integration. Their work in reverse-engineering the iPIXEL protocol has been invaluable.

## License

This project is licensed under the GNU General Public License v3.0 - see the LICENSE file for details.
