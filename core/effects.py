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
    - Modern font (Arial Bold)
    - Gradient-like text with soft glow effect (using blur)
    - Double outline for depth (inner white glow + outer black)
    - Semi-transparent dark background box with blur
    - Bottom-center positioning
    - Optimized for 1080x1920 vertical video (mobile)
    """
    # ASS color format: &HAABBGGRR (alpha, blue, green, red)
    # Using BorderStyle=4 for opaque box, but we'll use 1 for outline+shadow
    # and apply blur via override tags for modern look
    #
    # We create multiple styles:
    # - NarrationGlow: Background glow layer (rendered first)
    # - Narration: Main text layer with outline

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
Style: Default,Arial,52,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,0,2,60,60,100,1
Style: Narration,Arial,50,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0.5,0,1,4,0,2,80,80,100,1
Style: NarrationGlow,Arial,50,&H00000000,&H000000FF,&H60000000,&H00000000,-1,0,0,0,100,100,0.5,0,1,8,0,2,80,80,100,1

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
    fade_in_ms: int = 200,
    fade_out_ms: int = 150
) -> str:
    """Create ASS subtitle events with glow effect and animations.

    Creates two dialogue lines:
    1. Background glow layer (blurred, semi-transparent)
    2. Main text layer with crisp outline

    Effects applied:
    - Fade in/out animation
    - Subtle blur on glow layer for soft shadow
    - Scale pop-in animation (102% -> 100%)

    Args:
        start: Start time in seconds
        end: End time in seconds
        text: Subtitle text
        style: ASS style name (base style, glow style auto-derived)
        fade_in_ms: Fade in duration in milliseconds
        fade_out_ms: Fade out duration in milliseconds

    Returns:
        Two ASS dialogue lines (glow layer + main layer)
    """
    start_ts = format_time_ass(start)
    end_ts = format_time_ass(end)

    # Escape special characters
    escaped_text = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

    # Wrap text for better readability (max 42 chars per line, 2 lines max)
    wrapped_text = wrap_text(escaped_text)

    # Animation effects
    # \fad - fade in/out
    # \blur - gaussian blur for soft glow
    # \t(\fscx\fscy) - scale animation (pop-in effect)
    # \bord - border/outline size

    # Glow layer: blurred background shadow for depth
    glow_effects = (
        f"{{\\fad({fade_in_ms},{fade_out_ms})"
        f"\\blur6"  # Heavy blur for soft glow
        f"\\bord8"  # Thick border that becomes the glow
        f"}}"
    )

    # Main text layer: crisp text with outline and subtle pop-in
    pop_duration = min(150, fade_in_ms)  # Pop animation duration
    main_effects = (
        f"{{\\fad({fade_in_ms},{fade_out_ms})"
        f"\\blur0.5"  # Very subtle blur for anti-aliasing
        f"\\fscx102\\fscy102"  # Start slightly larger
        f"\\t(0,{pop_duration},\\fscx100\\fscy100)"  # Animate to normal size
        f"}}"
    )

    # Layer 0 = glow (rendered behind), Layer 1 = main text (rendered on top)
    glow_line = f"Dialogue: 0,{start_ts},{end_ts},{style}Glow,,0,0,0,,{glow_effects}{wrapped_text}"
    main_line = f"Dialogue: 1,{start_ts},{end_ts},{style},,0,0,0,,{main_effects}{wrapped_text}"

    return f"{glow_line}\n{main_line}"
