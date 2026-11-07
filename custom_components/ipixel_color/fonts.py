"""Font location utilities for iPIXEL Color integration."""
from __future__ import annotations

import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

# <config>/fonts, set at setup. It survives HACS updates, which replace this
# integration's own folder (and its fonts/) wholesale.
_config_fonts_dir: Path | None = None


def set_config_fonts_dir(path: str | Path | None) -> None:
    """Register Home Assistant's <config>/fonts folder as a font location."""
    global _config_fonts_dir
    _config_fonts_dir = Path(path) if path else None


def get_font_locations() -> list[Path]:
    """Get list of font directories sorted by priority.

    Priority order:
    1. User fonts in Home Assistant's <config>/fonts folder
    2. Fonts bundled in this integration's fonts/ folder
    3. Fonts from pypixelcolor package
    4. System fonts (Linux standard locations)

    Returns:
        List of Path objects for font directories that exist
    """
    locations = []

    # 1st priority: user fonts in <config>/fonts (persistent across updates)
    if _config_fonts_dir is not None and _config_fonts_dir.is_dir():
        locations.append(_config_fonts_dir)
        _LOGGER.debug("Added config fonts directory: %s", _config_fonts_dir)

    # 2nd priority: fonts bundled with this integration
    custom_fonts_dir = Path(__file__).parent / "fonts"
    if custom_fonts_dir.exists() and custom_fonts_dir.is_dir():
        locations.append(custom_fonts_dir)
        _LOGGER.debug("Added custom fonts directory: %s", custom_fonts_dir)

    # 2nd priority: pypixelcolor package fonts
    try:
        import pypixelcolor
        pypixelcolor_fonts_dir = Path(pypixelcolor.__file__).parent / "fonts"
        if pypixelcolor_fonts_dir.exists() and pypixelcolor_fonts_dir.is_dir():
            locations.append(pypixelcolor_fonts_dir)
            _LOGGER.debug("Added pypixelcolor fonts directory: %s", pypixelcolor_fonts_dir)
    except (ImportError, AttributeError) as e:
        _LOGGER.debug("Could not locate pypixelcolor fonts: %s", e)

    # 3rd priority: System fonts (Linux standard locations)
    system_font_paths = [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path.home() / ".fonts",
        Path.home() / "fonts",
        Path.home() / "homeassistant/fonts",
        Path.home() / ".local/share/fonts",
    ]

    for font_path in system_font_paths:
        if font_path.exists() and font_path.is_dir():
            locations.append(font_path)
            _LOGGER.debug("Added system fonts directory: %s", font_path)

    if not locations:
        _LOGGER.warning("No font directories found!")

    return locations


def get_font_path(font_name: str, locations: list[Path] | None = None) -> Path | None:
    """Find font file in available font locations.

    Args:
        font_name: Font filename (with or without extension)
        locations: Optional list of font directories to search (uses get_font_locations() if None)

    Returns:
        Path to font file if found, None otherwise
    """
    # Add common font extensions if not present
    if not any(font_name.lower().endswith(ext) for ext in ['.ttf', '.otf', '.woff', '.woff2']):
        font_name += '.ttf'

    # Get font locations if not provided
    if locations is None:
        locations = get_font_locations()

    # Search each location in priority order
    for location in locations:
        font_path = location / font_name
        if font_path.exists() and font_path.is_file():
            _LOGGER.debug("Found font %s in %s", font_name, location)
            return font_path

        # Also search subdirectories (common for system fonts)
        for subfont_path in location.rglob(font_name):
            if subfont_path.is_file():
                _LOGGER.debug("Found font %s in %s", font_name, subfont_path.parent)
                return subfont_path

    _LOGGER.warning("Font %s not found in any location", font_name)
    return None


def get_available_fonts(locations: list[Path] | None = None) -> list[str]:
    """Get list of available font filenames from all locations.

    Args:
        locations: Optional list of font directories to search (uses get_font_locations() if None)

    Returns:
        Sorted list of unique font filenames
    """
    if locations is None:
        locations = get_font_locations()

    fonts = set()

    # Scan each location for fonts
    for location in locations:
        try:
            # Scan for TTF fonts
            for font_file in location.glob("*.ttf"):
                fonts.add(font_file.name)

            # Scan for OTF fonts
            for font_file in location.glob("*.otf"):
                fonts.add(font_file.name)

            # Also check subdirectories (for system fonts)
            for font_file in location.rglob("*.ttf"):
                if font_file.is_file():
                    fonts.add(font_file.name)

            for font_file in location.rglob("*.otf"):
                if font_file.is_file():
                    fonts.add(font_file.name)

        except (OSError, PermissionError) as e:
            _LOGGER.debug("Could not scan directory %s: %s", location, e)

    # Ensure we have at least a default font
    if not fonts:
        fonts.add("OpenSans-Light.ttf")

    _LOGGER.debug("Found %d unique fonts across all locations", len(fonts))
    return sorted(list(fonts))
