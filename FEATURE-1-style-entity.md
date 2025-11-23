# FEATURE-1: Style Entity Implementation

## Overview

Create a unified style control entity for iPIXEL Color integration that works similarly to Home Assistant's light entity, providing comprehensive text styling controls through both UI and automation interfaces.

## Requirements

### Core Functionality
The style entity should behave like a light entity but control text rendering parameters instead of lighting parameters:

- **Entity Type**: Custom entity with light-like behavior
- **Domain**: `ipixel_color` (custom domain)
- **Service**: `ipixel_color.set_style` (similar to `light.turn_on`)
- **UI Integration**: Rich controls in Home Assistant frontend
- **Automation Support**: Full service call support for automations

### Controllable Attributes

#### 1. Font Selection
- **Type**: Dropdown/Select
- **Source**: Dynamic list from `fonts/` directory
- **Supported Formats**: `.ttf`, `.otf`
- **Default**: `OpenSans-Light.ttf`
- **UI**: Dropdown selector

#### 2. Font Size
- **Type**: Number (float)
- **Range**: 4.0 - 72.0
- **Default**: 12.0
- **UI**: Slider or number input
- **Auto-sizing**: Smart font sizing for optimal display fit

#### 3. Antialiasing
- **Type**: Boolean toggle
- **Default**: `true`
- **UI**: Toggle switch
- **Effect**: Smooth vs. pixelated text rendering

#### 4. Line Spacing
- **Type**: Integer
- **Range**: 0 - 10
- **Default**: 1
- **UI**: Slider
- **Effect**: Vertical spacing between text lines

#### 5. Style Presets
- **Type**: Dropdown/Select
- **Options**: 
  - `default` - Balanced settings for general use
  - `large` - Large, readable text (7x5.ttf, size 8)
  - `pixel` - Retro pixel perfect (5x5.ttf, size 10, no antialiasing)
  - `smooth` - Smooth rendering (OpenSans, large size, antialiasing on)
  - `compact` - Maximum text density (3x5.ttf, size 6)
- **UI**: Preset selector
- **Behavior**: Applying preset updates all related attributes

## Technical Implementation

### Correct Home Assistant Architecture

Based on Home Assistant best practices research, the implementation follows the proper patterns:

#### Platform Structure
```
custom_components/ipixel_color/
├── __init__.py                 # Integration setup, platform registration
├── ipixel_color.py            # Custom platform file (matches domain name)
├── style_control.py           # Entity implementation
├── services.yaml              # Service definitions with rich UI selectors
└── manifest.json              # Domain declaration
```

#### Entity Architecture (Current Implementation in style_control.py)
```python
class iPIXELStyleControl(RestoreEntity):
    """Style control entity with light-like behavior following HA patterns."""
    
    # Entity properties (like light entity)
    _attr_should_poll = False
    _attr_supported_features = SUPPORT_STYLE_ALL
    
    # State representation
    @property
    def state(self) -> str:
        """Return current preset or 'custom' (like light brightness/color mode)."""
        return self._current_preset or "custom"
    
    @property
    def extra_state_attributes(self) -> dict:
        """Return all controllable parameters (like light attributes)."""
        return {
            "font": self._font,
            "font_size": self._font_size,
            "antialias": self._antialias,
            "line_spacing": self._line_spacing,
            "preset": self._current_preset,
            "available_fonts": self._get_available_fonts(),
            "available_presets": list(self._style_presets.keys()),
            "supported_features": self._attr_supported_features,
        }
    
    # Service method (like light.turn_on)
    async def async_set_style(self, **kwargs):
        """Set style parameters similar to light.turn_on with brightness, color, etc."""
```

#### Proper MRO (Method Resolution Order)
```python
# ✅ CORRECT - RestoreEntity first, inherits from Entity
class iPIXELStyleControl(RestoreEntity):
    
# ❌ INCORRECT - Multiple inheritance conflicts
class iPIXELStyleControl(Entity, RestoreEntity):  # MRO error
class iPIXELStyleControl(SensorEntity, RestoreEntity):  # Domain mismatch
```

#### Platform Registration (Current Implementation)
```python
# In __init__.py - PLATFORMS list includes custom domain
PLATFORMS: list[Platform] = [
    Platform.SWITCH, 
    Platform.TEXT, 
    Platform.SENSOR, 
    Platform.NUMBER, 
    Platform.BUTTON, 
    "ipixel_color"  # Custom platform matches domain name
]

# In ipixel_color.py - Custom platform setup
async def async_setup_entry(hass, entry, async_add_entities):
    """Set up iPIXEL Color style control entities."""
    async_add_entities([iPIXELStyleControl(hass, api, entry, address, name)])
```

#### Service Registration (Current Implementation)
```python
# In ipixel_color.py - Platform-level service registration
from homeassistant.helpers import entity_platform

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up entities and register services."""
    # Add entities
    async_add_entities([iPIXELStyleControl(hass, api, entry, address, name)])
    
    # Register entity service (like light.turn_on)
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "set_style",  # Creates ipixel_color.set_style
        {
            "font": str,
            "font_size": float,
            "antialias": bool,
            "line_spacing": int,
            "preset": str,
        },
        "async_set_style",  # Entity method to call
    )
```

### Service Implementation
```yaml
# services.yaml - Rich UI Controls
set_style:
  name: Set Style
  description: Configure text style parameters
  target:
    entity:
      domain: ipixel_color
  fields:
    font:
      name: Font
      description: Font filename from fonts/ directory
      example: "5x5.ttf"
      selector:
        select:
          options: [] # Dynamically populated
    font_size:
      name: Font Size
      description: Font size in points
      example: 12.0
      selector:
        number:
          min: 4.0
          max: 72.0
          step: 0.5
    antialias:
      name: Antialiasing
      description: Enable smooth text rendering
      example: true
      selector:
        boolean:
    line_spacing:
      name: Line Spacing
      description: Vertical spacing between lines
      example: 1
      selector:
        number:
          min: 0
          max: 10
          step: 1
    preset:
      name: Preset
      description: Apply predefined style preset
      example: "pixel"
      selector:
        select:
          options:
            - "default"
            - "large" 
            - "pixel"
            - "smooth"
            - "compact"
```

### Frontend Card Integration

The entity should provide rich UI controls in Home Assistant frontend:

#### Lovelace Card Support
```yaml
type: entities
entities:
  - entity: ipixel_color.ipixel_style
    name: Text Style
    controls:
      - type: font-selector
        attribute: font
      - type: slider
        attribute: font_size
        min: 4
        max: 72
      - type: toggle
        attribute: antialias
      - type: slider
        attribute: line_spacing
        min: 0
        max: 10
      - type: preset-selector
        attribute: preset
```

#### Device Controls Page
When users navigate to the device page, they should see:
- **Style Section**: Dedicated section for text styling
- **Live Preview**: Visual preview of current settings
- **Quick Presets**: One-click preset buttons
- **Advanced Controls**: Expandable section for fine-tuning

### Automation Integration

#### Service Call Examples

**Set Individual Parameters:**
```yaml
service: ipixel_color.set_style
target:
  entity_id: ipixel_color.ipixel_style
data:
  font: "5x5.ttf"
  font_size: 12
  antialias: false
  line_spacing: 2
```

**Apply Preset:**
```yaml
service: ipixel_color.set_style
target:
  entity_id: ipixel_color.ipixel_style
data:
  preset: pixel
```

**Mix Preset with Custom:**
```yaml
service: ipixel_color.set_style
target:
  entity_id: ipixel_color.ipixel_style
data:
  preset: pixel
  line_spacing: 3  # Override spacing from preset
```

#### Template Usage
```yaml
# Conditional styling based on time
service: ipixel_color.set_style
target:
  entity_id: ipixel_color.ipixel_style
data:
  preset: >
    {% if now().hour < 8 or now().hour > 20 %}
      compact
    {% elif is_state('sun.sun', 'above_horizon') %}
      smooth
    {% else %}
      default
    {% endif %}
```

## State Management

### Persistence
- **RestoreEntity**: Maintain state across Home Assistant restarts
- **Default Values**: Sensible defaults if no previous state
- **State Attributes**: All current parameters exposed as attributes

### State Representation
```python
# Entity state
state = "pixel"  # Current preset name or "custom"

# Entity attributes
attributes = {
    "font": "5x5.ttf",
    "font_size": 10.0,
    "antialias": False,
    "line_spacing": 1,
    "preset": "pixel",
    "supported_fonts": ["OpenSans-Light.ttf", "5x5.ttf", "7x5.ttf", "3x5-de.ttf"],
    "friendly_name": "iPIXEL Style Control"
}
```

## Integration Points

### Auto-Update Integration
- **Trigger Updates**: Style changes should trigger display refresh if auto-update is enabled
- **Change Detection**: Monitor style attribute changes
- **Batch Updates**: Group multiple rapid changes to prevent flickering

### Text Entity Coordination
- **Shared State**: Style settings apply to current text content
- **Live Updates**: Style changes reflect immediately on display
- **Template Compatibility**: Style changes work with templated text

### Font Management
- **Dynamic Discovery**: Scan `fonts/` directory at startup
- **Hot Reload**: Support adding new fonts without restart
- **Validation**: Verify font files are readable
- **Fallback**: Graceful handling of missing fonts

## User Experience Goals

### Ease of Use
1. **One-Click Presets**: Common styles accessible with single click
2. **Visual Feedback**: Immediate preview of style changes
3. **Smart Defaults**: Sensible default values for new users
4. **Progressive Disclosure**: Basic controls visible, advanced hidden until needed

### Power User Features
1. **Fine Control**: Precise adjustment of all parameters
2. **Automation Ready**: Full service call support
3. **Template Support**: Dynamic styling based on conditions
4. **State Persistence**: Remember user preferences

### Consistency
1. **HA Design Language**: Follow Home Assistant UI patterns
2. **Light Entity Pattern**: Familiar interaction model
3. **Standard Services**: Consistent service naming and parameters
4. **Icon Integration**: Appropriate entity and service icons

## Success Criteria

### Functional Requirements
- [ ] Entity appears in Home Assistant device page
- [ ] All style parameters controllable via UI
- [ ] Service calls work from automations and scripts
- [ ] Presets apply correctly and update all relevant attributes
- [ ] State persists across Home Assistant restarts
- [ ] Font discovery works and updates when fonts added
- [ ] Style changes trigger display updates when auto-update enabled

### User Experience Requirements  
- [ ] UI controls are intuitive and responsive
- [ ] Presets provide meaningful style variations
- [ ] Style changes are visually apparent on display
- [ ] Entity integrates well with Home Assistant frontend
- [ ] Service calls provide helpful validation and error messages
- [ ] Documentation clearly explains usage patterns

### Technical Requirements
- [ ] No method resolution order (MRO) conflicts
- [ ] Proper entity lifecycle management
- [ ] Efficient state updates without excessive API calls
- [ ] Graceful error handling for invalid parameters
- [ ] Memory-efficient font caching
- [ ] Thread-safe state management

## Current Implementation Status

### ✅ What's Already Correct

Based on the research, the current implementation **already follows Home Assistant best practices**:

1. **Domain Registration**: `ipixel_color` domain properly declared in `manifest.json`
2. **Platform Structure**: `ipixel_color.py` platform file matches domain name
3. **Entity Implementation**: `style_control.py` uses proper `RestoreEntity` inheritance
4. **Service Registration**: Platform-level service registration in `ipixel_color.py`
5. **Rich UI Controls**: Comprehensive `services.yaml` with selectors
6. **State Management**: Proper `extra_state_attributes` for frontend integration

### ⚠️ Current Issues to Fix

1. **MRO Conflict**: Already resolved - `iPIXELStyleControl(RestoreEntity)` ✅
2. **Platform Loading**: Need to ensure `ipixel_color.py` loads without conflicts
3. **Service Schema**: Minor improvements for better validation

### 🎯 Architecture Validation

The implementation **correctly achieves the goal**:
- ✅ Entity: `ipixel_color.device_style` 
- ✅ Service: `ipixel_color.set_style`
- ✅ Multiple Parameters: font, size, antialiasing, spacing, presets
- ✅ Light-like Behavior: Supported features, rich attributes
- ✅ UI Integration: Frontend controls via `extra_state_attributes`

## Implementation Plan

### Phase 1: Fix Current Issues (In Progress)
1. Create `iPIXELStyleControl` entity class
2. Implement basic state management
3. Add service registration
4. Test entity creation and basic functionality

### Phase 2: UI Integration
1. Add frontend controls and selectors
2. Implement preset system
3. Add dynamic font discovery
4. Test UI responsiveness and validation

### Phase 3: Integration
1. Connect with auto-update system
2. Add text entity coordination
3. Implement state persistence
4. Add comprehensive error handling

### Phase 4: Polish
1. Add visual previews and feedback
2. Optimize performance and memory usage
3. Add comprehensive documentation
4. Test edge cases and error conditions