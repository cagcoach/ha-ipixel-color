"""Text rendering for iPIXEL Color displays."""
from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Any, Tuple

from PIL import Image, ImageDraw, ImageFont

from ..color import hex_to_rgb

_LOGGER = logging.getLogger(__name__)

# Minimum font size to try
MIN_FONT_SIZE = 4
MARGIN_THRESHOLD = 64  # Pixel brightness threshold for margin detection


def _get_font_path(font_name: str) -> str | None:
    """Get path to font file from fonts/ folder.
    
    Args:
        font_name: Font filename (with or without extension)
        
    Returns:
        Full path to font file if found, None otherwise
    """
    # Add common font extensions if not present
    if not any(font_name.lower().endswith(ext) for ext in ['.ttf', '.otf', '.woff', '.woff2']):
        font_name += '.ttf'
    
    # Look in fonts/ folder relative to this module
    fonts_dir = Path(__file__).parent.parent / 'fonts'
    font_path = fonts_dir / font_name
    
    if font_path.exists():
        return str(font_path)
    
    _LOGGER.warning("Font %s not found in %s", font_name, fonts_dir)
    return None


def render_text_to_png(text: str, width: int, height: int, antialias: bool = True, font_size: float | None = None, font: str | None = None, line_spacing: int = 0, text_color: str = "ffffff", bg_color: str = "000000") -> bytes:
    """Render text to PNG image data with color gradient mapping.

    Args:
        text: Text to render (supports multiline with \n)
        width: Display width in pixels
        height: Display height in pixels
        antialias: Enable antialiasing for smoother text (default: True)
        font_size: Fixed font size in pixels (can be fractional), or None for auto-sizing (default: None)
        font: Font name from fonts/ folder, or None for default (default: None)
        line_spacing: Additional spacing between lines in pixels (default: 0)
        text_color: Foreground/text color in hex format (e.g., 'ffffff') (default: white)
        bg_color: Background color in hex format (e.g., '000000') (default: black)

    Returns:
        PNG image data as bytes

    Note:
        Uses linear interpolation to map grayscale values to colors:
        - 0 (black) → bg_color
        - 255 (white) → text_color
        - Intermediate values → interpolated colors
    """
    # Create image with device dimensions
    # Use 'L' mode (grayscale) for non-antialiased to get sharper pixels
    if not antialias:
        img = Image.new('1', (width, height), 0)  # 1-bit pixels, black background
    else:
        img = Image.new('RGB', (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Process multiline text
    lines = text.split('\n') if '\n' in text else [text]
    
    # Get font - either fixed size or auto-optimized
    if font_size is not None:
        font_obj = get_fixed_font(font_size, font)
    else:
        font_obj = get_optimal_font(draw, lines, width, height, font, line_spacing)
    
    # Create temporary image to measure actual content bounds
    temp_img = Image.new('L', (width, height), 0)  # Grayscale for easier analysis
    temp_draw = ImageDraw.Draw(temp_img)
    
    # Draw all text to measure actual content area and calculate per-line bounds
    temp_y = 0
    line_data = []
    for line in lines:
        bbox = temp_draw.textbbox((0, 0), line, font=font_obj)
        line_width = bbox[2] - bbox[0]
        line_height = bbox[3] - bbox[1]
        
        # Draw line on temporary image
        temp_draw.text((0, temp_y), line, font=font_obj, fill=255)
        
        # Calculate this specific line's content bounds
        line_temp_img = Image.new('L', (width, line_height * 2), 0)
        line_temp_draw = ImageDraw.Draw(line_temp_img)
        line_temp_draw.text((0, 0), line, font=font_obj, fill=255)
        line_bounds = _calculate_content_bounds(line_temp_img)
        
        if line_bounds:
            l_left, l_top, l_right, l_bottom = line_bounds
        else:
            l_left, l_top, l_right, l_bottom = 0, 0, line_width, line_height
            
        line_data.append({
            'text': line,
            'width': line_width, 
            'height': line_height,
            'y_pos': temp_y,
            'content_left': l_left,
            'content_top': l_top,
            'content_right': l_right,
            'content_bottom': l_bottom,
            'content_width': l_right - l_left,
            'content_height': l_bottom - l_top
        })
        temp_y += line_height + line_spacing  # Add line spacing between lines
    
    # Calculate actual content bounds for the entire block
    content_bounds = _calculate_content_bounds(temp_img)
    if content_bounds:
        content_left, content_top, content_right, content_bottom = content_bounds
        content_width = content_right - content_left
        content_height = content_bottom - content_top
        
        # Center the entire block vertically
        y_offset = (height - content_height) // 2 - content_top
    else:
        # Fallback to traditional centering if no content found
        total_height = sum(data['height'] for data in line_data)
        if len(lines) > 1:
            total_height += line_spacing * (len(lines) - 1)
        y_offset = (height - total_height) // 2
    
    # Draw each line with corrected positioning
    current_y = y_offset
    for i, (line, data) in enumerate(zip(lines, line_data)):
        # Calculate horizontal position for this specific line using pre-calculated bounds
        if 'content_left' in data:
            # Center based on actual content width, accounting for left margin
            x = (width - data['content_width']) // 2 - data['content_left']
        else:
            # Fallback if no bounds data
            x = (width - data['width']) // 2
        
        # For the first line, adjust y position to account for top margin
        if i == 0 and 'content_top' in data:
            # Adjust for the first line's top margin
            adjusted_y = current_y
        else:
            adjusted_y = current_y
        
        # Draw the line with appropriate fill color
        if not antialias:
            draw.text((x, adjusted_y), line, font=font_obj, fill=1)  # 1 for white in 1-bit mode
        else:
            draw.text((x, adjusted_y), line, font=font_obj, fill=(255, 255, 255))
        
        # Move to next line position
        current_y += data['height'] + line_spacing  # Add line spacing between lines
    
    # Parse hex colors to RGB tuples using utility function
    try:
        bg_r, bg_g, bg_b = hex_to_rgb(bg_color)
        text_r, text_g, text_b = hex_to_rgb(text_color)
    except (ValueError, IndexError):
        _LOGGER.error("Invalid color format. Using defaults (white text, black background)")
        bg_r, bg_g, bg_b = 0, 0, 0
        text_r, text_g, text_b = 255, 255, 255

    # Apply color gradient mapping using linear interpolation
    # Convert grayscale image to RGB with gradient mapping
    if not antialias:
        # For 1-bit images, convert to grayscale first
        grayscale_img = img.point(lambda x: 255 if x else 0).convert('L')
    else:
        # For RGB images, convert to grayscale
        grayscale_img = img.convert('L')

    # Create RGB image with interpolated colors
    rgb_img = Image.new('RGB', (width, height))
    pixels_gray = grayscale_img.load()
    pixels_rgb = rgb_img.load()

    for y in range(height):
        for x in range(width):
            # Get grayscale value (0-255)
            gray_value = pixels_gray[x, y]

            # Linear interpolation: t = gray_value / 255.0
            # color = bg_color * (1-t) + text_color * t
            t = gray_value / 255.0

            r = int(bg_r * (1 - t) + text_r * t)
            g = int(bg_g * (1 - t) + text_g * t)
            b = int(bg_b * (1 - t) + text_b * t)

            pixels_rgb[x, y] = (r, g, b)

    # Convert to PNG bytes
    png_buffer = io.BytesIO()
    rgb_img.save(png_buffer, format='PNG')
    return png_buffer.getvalue()


def _calculate_content_bounds(img: Image.Image) -> tuple[int, int, int, int] | None:
    """Calculate actual content bounds by analyzing pixels.
    
    Args:
        img: Grayscale image with text content
        
    Returns:
        Tuple of (left, top, right, bottom) bounds or None if no content
    """
    width, height = img.size
    pixels = img.load()
    
    # Find top boundary (first row with bright pixels)
    top = None
    for y in range(height):
        for x in range(width):
            if pixels[x, y] > MARGIN_THRESHOLD:
                top = y
                break
        if top is not None:
            break
    
    if top is None:
        return None  # No content found
    
    # Find bottom boundary (last row with bright pixels)
    bottom = None
    for y in range(height - 1, -1, -1):
        for x in range(width):
            if pixels[x, y] > MARGIN_THRESHOLD:
                bottom = y + 1  # +1 because we want inclusive bounds
                break
        if bottom is not None:
            break
    
    # Find left boundary (first column with bright pixels)
    left = None
    for x in range(width):
        for y in range(top, bottom):
            if pixels[x, y] > MARGIN_THRESHOLD:
                left = x
                break
        if left is not None:
            break
    
    # Find right boundary (last column with bright pixels)
    right = None
    for x in range(width - 1, -1, -1):
        for y in range(top, bottom):
            if pixels[x, y] > MARGIN_THRESHOLD:
                right = x + 1  # +1 because we want inclusive bounds
                break
        if right is not None:
            break
    
    if left is None or right is None:
        return None
    
    _LOGGER.debug("Content bounds: left=%d, top=%d, right=%d, bottom=%d (content: %dx%d)", 
                 left, top, right, bottom, right - left, bottom - top)
    
    return left, top, right, bottom


def get_fixed_font(size: float, font_name: str | None = None) -> ImageFont.FreeTypeFont:
    """Get font with fixed size.
    
    Args:
        size: Font size in pixels (can be fractional)
        font_name: Optional font name from fonts/ folder
        
    Returns:
        Font object with the specified size
    """
    try:
        # Try to load custom font from fonts/ folder first
        if font_name:
            font_path = _get_font_path(font_name)
            if font_path:
                try:
                    return ImageFont.truetype(font_path, size)
                except Exception as e:
                    _LOGGER.warning("Could not load custom font %s: %s", font_name, e)
        
        # Use default font if custom font failed or not specified
        return ImageFont.load_default()
    except Exception as e:
        _LOGGER.warning("Error loading font size %.1f: %s, using default", size, e)
        return ImageFont.load_default()


def get_optimal_font(draw: ImageDraw.Draw, lines: list[str], 
                     max_width: int, max_height: int, font_name: str | None = None, line_spacing: int = 0) -> ImageFont.FreeTypeFont:
    """Find the largest font size that fits all text within dimensions.
    
    Args:
        draw: ImageDraw object for text measurement
        lines: List of text lines to render
        max_width: Maximum width in pixels
        max_height: Maximum height in pixels
        font_name: Optional font name from fonts/ folder
        line_spacing: Additional spacing between lines in pixels
        
    Returns:
        Optimal font for the text
    """
    # Compute theoretical optimal size based on text proportions
    # Start with a baseline font to measure proportions
    baseline_size = 100.0
    baseline_font = get_fixed_font(baseline_size, font_name)
    
    # Find the longest line to determine width constraint
    longest_line = max(lines, key=len) if lines else ""
    
    # Measure baseline dimensions
    bbox = draw.textbbox((0, 0), longest_line, font=baseline_font)
    baseline_width = bbox[2] - bbox[0]
    baseline_line_height = bbox[3] - bbox[1]
    
    # Calculate total height with line spacing
    total_baseline_height = baseline_line_height * len(lines)
    if len(lines) > 1:
        total_baseline_height += line_spacing * (len(lines) - 1)
    
    # Calculate theoretical optimal size based on proportions
    width_ratio = max_width / baseline_width if baseline_width > 0 else 1.0
    height_ratio = max_height / total_baseline_height if total_baseline_height > 0 else 1.0
    theoretical_size = baseline_size * min(width_ratio, height_ratio)
    
    # Clamp to reasonable range
    theoretical_size = max(1.0, min(theoretical_size, min(max_height, max_width)))
    
    _LOGGER.debug("Theoretical optimal size: %.1f (width_ratio: %.2f, height_ratio: %.2f)",
                 theoretical_size, width_ratio, height_ratio)
    
    # Try sizes around the theoretical optimal with fine increments
    best_font = None
    best_size = 0.0
    
    # Test 3 iterations with refinement
    test_ranges = [
        (theoretical_size * 0.7, theoretical_size * 1.3, 2.0),  # Coarse: ±30% with 2.0 step
        (best_size - 2.0, best_size + 2.0, 0.5),                # Medium: ±2 with 0.5 step  
        (best_size - 0.5, best_size + 0.5, 0.1),                # Fine: ±0.5 with 0.1 step
    ]
    
    for iteration, (start, end, step) in enumerate(test_ranges):
        if iteration > 0 and best_size == 0:
            break  # Skip refinement if no valid size found
            
        current_start = max(1.0, start if iteration == 0 else start)
        current_end = min(min(max_height, max_width), end if iteration == 0 else end)
        
        size = current_start
        while size <= current_end:
            try:
                # Try to load font at this size
                font = None
                if font_name:
                    font_path = _get_font_path(font_name)
                    if font_path:
                        try:
                            font = ImageFont.truetype(font_path, size)
                        except Exception as e:
                            _LOGGER.debug("Custom font %s failed at size %.1f: %s", font_name, size, e)
                
                # Use default font if custom font failed or not specified
                if font is None:
                    font = ImageFont.load_default()
                
                # Check if all lines fit within dimensions
                fits = True
                total_height = 0
                
                for line in lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    
                    # Check if line fits horizontally
                    if text_width > max_width:
                        fits = False
                        break
                        
                    total_height += text_height
                
                # Add line spacing to total height
                if len(lines) > 1:
                    total_height += line_spacing * (len(lines) - 1)
                
                # Check if all lines fit vertically
                if total_height > max_height:
                    fits = False
                
                if fits and size > best_size:
                    best_size = size
                    best_font = font
                    _LOGGER.debug("Iteration %d: Found better size: %.1f (total height: %d/%d)", 
                                iteration + 1, size, total_height, max_height)
                    
            except Exception as e:
                _LOGGER.debug("Font size %.1f failed: %s", size, e)
            
            size += step
    
    # Return best font found
    if best_font:
        _LOGGER.debug("Using optimal font size: %.1f", best_size)
        return best_font
    
    # Fallback to minimum font size
    _LOGGER.warning("Using fallback font - text may not fit optimally")
    return get_fixed_font(1.0, font_name)