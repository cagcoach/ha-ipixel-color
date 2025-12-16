"""Time formatting utilities."""


def format_time(seconds):
    """Format seconds into display string.

    - Up to 9:59: shows M:SS (e.g., "5:32")
    - Above 9:59: shows Xm (e.g., "14m")
    """
    if seconds < 0:
        seconds = 0

    minutes = seconds // 60
    secs = seconds % 60

    if minutes <= 9:
        return f"{minutes}:{secs:02d}"
    else:
        return f"{minutes}m"


def parse_duration(duration_str):
    """Parse duration string into seconds.

    Accepts: 30s, 5m, 2:30, or plain number (seconds)
    """
    duration_str = duration_str.lower().strip()

    if duration_str.endswith("s"):
        return int(duration_str[:-1])
    elif duration_str.endswith("m"):
        return int(duration_str[:-1]) * 60
    elif ":" in duration_str:
        parts = duration_str.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    else:
        return int(duration_str)
