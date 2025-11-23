# iPIXEL Color - Home Assistant Integration

A Home Assistant custom integration for iPIXEL Color LED matrix displays via Bluetooth.

## Features

- **Rich Text Display**: Custom fonts, sizes, multiline text with `\n`
- **Template Support**: Use Home Assistant variables like `{{ states('sensor.temperature') }}°C`
- **Font Management**: Load TTF/OTF fonts from `fonts/` folder
- **Auto/Manual Updates**: Choose automatic updates or manual refresh
- **State Persistence**: Settings preserved across HA restarts
- **Auto-discovery**: Finds iPIXEL devices automatically

## Installation

1. Copy `custom_components/ipixel_color` to your HA `custom_components` directory
2. Create `fonts/` folder for custom fonts (optional)
3. Restart Home Assistant
4. Add integration via Settings → Devices & Services → Add Integration

## Entities

Once configured, you'll get these entities:

- `text.{device}_display` - Enter text with templates and `\n` for newlines
- `sensor.{device}_style` - **Unified style control** (font, size, antialiasing, spacing)
- `number.{device}_brightness` - Display brightness level (1-100)
- `switch.{device}_auto_update` - Auto-update on changes
- `button.{device}_update_display` - Manual refresh
- `switch.{device}_power` - Turn display on/off

### Style Entity Features

The new unified `style` entity combines all text formatting options:
- **Attributes**: font, font_size, antialias, line_spacing
- **Presets**: default, large, pixel, smooth, compact
- **Services**: `ipixel_color.apply_style` and `ipixel_color.apply_style_preset`

## Template Examples

```jinja2
Time: {{ now().strftime('%H:%M') }}
Temp: {{ states('sensor.temperature') | round(1) }}°C
{% if is_state('sun.sun', 'above_horizon') %}Day{% else %}Night{% endif %}
```

## Quick Start

1. Set text: `"Hello\nWorld"`
2. Apply a style preset or customize via the style entity
3. Toggle auto-update ON or use manual update button
4. Templates update automatically with sensor changes

### Using Style Presets

```yaml
service: ipixel_color.apply_style_preset
target:
  entity_id: sensor.ipixel_style
data:
  preset: pixel  # Options: default, large, pixel, smooth, compact
```

### Custom Style

```yaml
service: ipixel_color.apply_style
target:
  entity_id: sensor.ipixel_style
data:
  style:
    font: "5x5.ttf"
    font_size: 12
    antialias: false
    line_spacing: 2
```

## Font Management

- Place `.ttf`/`.otf` files in `fonts/` folder
- Restart HA to see new fonts in dropdown
- Recommended: pixel fonts like 5x5.ttf, 7x7.ttf

## Troubleshooting

- Enable debug logging: `custom_components.ipixel_color: debug`
- Check auto-update is ON or use manual update button
- Verify templates in Developer Tools → Template
- Ensure device is in Bluetooth range

## Status

| Feature | Status |
|---------|--------|
| ✅ Text Display | Complete |
| ✅ Custom Fonts | Complete |  
| ✅ Templates | Complete |
| ✅ State Persistence | Complete |
| ✅ Brightness Control | Complete |
| ❌ Colors/Images | Planned |

## Technical

- Requires: Home Assistant 2024.1+ and HACS

## Acknowledgments

This Home Assistant integration is built upon the protocol implementations from:

- **[ipixel-ctrl](https://github.com/sdolphin-JP/ipixel-ctrl)** - Python implementation of the iPIXEL protocol by sdolphin-JP, which provided the foundation for device communication and command structure
- **[go-ipxl](https://github.com/yyewolf/go-ipxl)** - Go implementation by yyewolf that helped understand brightness control and additional protocol details
- **[pypixelcolor](https://github.com/lucagoc/pypixelcolor)** - Advanced Python library by lucagoc with comprehensive API design, clock mode, and additional device features

Special thanks to sdolphin-JP, yyewolf, and lucagoc for their work in reverse engineering and documenting the iPIXEL Color protocol.

## License

This project is licensed under the GNU General Public License v3.0 - see the LICENSE file for details.