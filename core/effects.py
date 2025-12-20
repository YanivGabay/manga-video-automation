"""
Visual effects for manga video creation
Ken Burns, filters, and transformations
"""
import random
from dataclasses import dataclass
from typing import Literal


@dataclass
class KenBurnsEffect:
    """Ken Burns effect parameters for a single clip"""
    start_zoom: float  # Starting zoom level (1.0 = no zoom)
    end_zoom: float    # Ending zoom level
    start_x: float     # Starting X position (0-1, 0.5 = center)
    start_y: float     # Starting Y position (0-1, 0.5 = center)
    end_x: float       # Ending X position
    end_y: float       # Ending Y position
    duration: float    # Duration in seconds

    def to_ffmpeg_filter(self, width: int, height: int) -> str:
        """Generate FFmpeg zoompan filter string"""
        # Calculate pixel positions
        # zoompan works with zoom factor and x/y offsets

        # For zoompan: z is zoom factor, x/y are top-left corner offsets
        # We need to convert our center-based coordinates to top-left

        fps = 30
        total_frames = int(self.duration * fps)

        # Zoom interpolation
        zoom_expr = f"zoom+({self.end_zoom}-{self.start_zoom})/{total_frames}"

        # Position interpolation (accounting for zoom)
        # x = (center_x * width) - (width / zoom / 2)
        start_px_x = self.start_x * width
        start_px_y = self.start_y * height
        end_px_x = self.end_x * width
        end_px_y = self.end_y * height

        x_expr = f"if(eq(on,1),{start_px_x}-(iw/zoom/2),x+({end_px_x}-{start_px_x})/{total_frames})"
        y_expr = f"if(eq(on,1),{start_px_y}-(ih/zoom/2),y+({end_px_y}-{start_px_y})/{total_frames})"

        return (
            f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':"
            f"d={total_frames}:s={width}x{height}:fps={fps}"
        )


def generate_ken_burns(
    duration: float,
    style: Literal["zoom_in", "zoom_out", "pan_left", "pan_right", "random"] = "random"
) -> KenBurnsEffect:
    """Generate Ken Burns effect parameters"""

    if style == "random":
        style = random.choice(["zoom_in", "zoom_out", "pan_left", "pan_right"])

    # Base parameters
    center = 0.5
    zoom_min = 1.0
    zoom_max = 1.2
    pan_offset = 0.1

    if style == "zoom_in":
        return KenBurnsEffect(
            start_zoom=zoom_min,
            end_zoom=zoom_max,
            start_x=center + random.uniform(-0.05, 0.05),
            start_y=center + random.uniform(-0.05, 0.05),
            end_x=center,
            end_y=center,
            duration=duration
        )

    elif style == "zoom_out":
        return KenBurnsEffect(
            start_zoom=zoom_max,
            end_zoom=zoom_min,
            start_x=center,
            start_y=center,
            end_x=center + random.uniform(-0.05, 0.05),
            end_y=center + random.uniform(-0.05, 0.05),
            duration=duration
        )

    elif style == "pan_left":
        return KenBurnsEffect(
            start_zoom=zoom_max * 0.95,
            end_zoom=zoom_max * 0.95,
            start_x=center + pan_offset,
            start_y=center,
            end_x=center - pan_offset,
            end_y=center,
            duration=duration
        )

    elif style == "pan_right":
        return KenBurnsEffect(
            start_zoom=zoom_max * 0.95,
            end_zoom=zoom_max * 0.95,
            start_x=center - pan_offset,
            start_y=center,
            end_x=center + pan_offset,
            end_y=center,
            duration=duration
        )


def get_filter_for_mood(mood: str) -> str:
    """Get FFmpeg filter based on mood"""
    filters = {
        "tense": "eq=contrast=1.1:brightness=-0.02:saturation=0.9",
        "action": "eq=contrast=1.15:brightness=0.02:saturation=1.1",
        "sad": "eq=contrast=0.95:brightness=-0.05:saturation=0.7",
        "comedic": "eq=contrast=1.0:brightness=0.03:saturation=1.1",
        "romantic": "eq=contrast=0.95:brightness=0.02:saturation=1.2,colorbalance=rs=0.1:gs=-0.05:bs=-0.1",
        "dark": "eq=contrast=1.2:brightness=-0.1:saturation=0.6",
        "happy": "eq=contrast=1.05:brightness=0.05:saturation=1.15",
    }
    return filters.get(mood, "eq=contrast=1.0:brightness=0.0:saturation=1.0")


def wrap_text(text: str, max_chars: int = 42) -> str:
    """Wrap text to multiple lines for better readability.

    Args:
        text: The text to wrap
        max_chars: Maximum characters per line (default 42 for subtitle readability)

    Returns:
        Text with \\N line breaks for ASS format
    """
    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
        word_length = len(word)
        # +1 for space between words
        if current_length + word_length + (1 if current_line else 0) <= max_chars:
            current_line.append(word)
            current_length += word_length + (1 if len(current_line) > 1 else 0)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_length = word_length

    if current_line:
        lines.append(" ".join(current_line))

    # Limit to 2 lines max for readability
    if len(lines) > 2:
        # Combine into 2 lines
        mid = len(lines) // 2
        lines = [" ".join(lines[:mid+1]), " ".join(lines[mid+1:])]

    return "\\N".join(lines)


def generate_subtitle_style() -> str:
    """Generate ASS subtitle style for manga narration.

    Style features:
    - Modern font (Arial Bold as fallback-safe choice)
    - Semi-transparent dark rounded background box
    - White text (#FAFAFA) with black outline
    - Drop shadow for depth
    - Bottom-center positioning
    - Good size for mobile viewing
    """
    # ASS color format: &HAABBGGRR (alpha, blue, green, red)
    # PrimaryColour: Off-white text (#FAFAFA = &H00FAFAFA)
    # OutlineColour: Black outline
    # BackColour: Semi-transparent black background (BorderStyle=3 enables box)
    # Shadow: 2px for subtle depth

    return """[Script Info]
Title: Manga Narration
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,52,&H00FAFAFA,&H000000FF,&H00000000,&HC0000000,-1,0,0,0,100,100,0,0,3,3,2,2,60,60,100,1
Style: Narration,Arial,48,&H00FAFAFA,&H000000FF,&H00000000,&HC0000000,-1,0,0,0,100,100,1,0,3,3,2,2,80,80,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def format_time_ass(seconds: float) -> str:
    """Format seconds to ASS timestamp (H:MM:SS.cc)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def create_subtitle_event(
    start: float,
    end: float,
    text: str,
    style: str = "Narration",
    fade_in_ms: int = 300,
    fade_out_ms: int = 200
) -> str:
    """Create a single ASS subtitle event with fade animation and text wrapping.

    Args:
        start: Start time in seconds
        end: End time in seconds
        text: Subtitle text
        style: ASS style name
        fade_in_ms: Fade in duration in milliseconds
        fade_out_ms: Fade out duration in milliseconds

    Returns:
        ASS dialogue line
    """
    start_ts = format_time_ass(start)
    end_ts = format_time_ass(end)

    # Escape special characters
    text = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

    # Wrap text for better readability (max 42 chars per line, 2 lines max)
    text = wrap_text(text)

    # Add fade effect: \fad(fade_in_ms, fade_out_ms)
    fade_effect = f"{{\\fad({fade_in_ms},{fade_out_ms})}}"

    return f"Dialogue: 0,{start_ts},{end_ts},{style},,0,0,0,,{fade_effect}{text}"
