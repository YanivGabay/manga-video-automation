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


def generate_subtitle_style() -> str:
    """Generate ASS subtitle style for manga narration.

    Style features:
    - Semi-transparent dark background box
    - White text with black outline
    - Bottom-center positioning
    - Good size for mobile viewing
    """
    # ASS color format: &HAABBGGRR (alpha, blue, green, red)
    # PrimaryColour: White text
    # OutlineColour: Black outline
    # BackColour: Semi-transparent black background (BorderStyle=3 enables box)

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
Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&HB0000000,-1,0,0,0,100,100,0,0,3,3,0,2,60,60,120,1
Style: Narration,Arial,44,&H00FFFFFF,&H000000FF,&H00000000,&HC0000000,-1,0,0,0,100,100,1,0,3,2,0,2,80,80,150,1

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
    style: str = "Narration"
) -> str:
    """Create a single ASS subtitle event"""
    start_ts = format_time_ass(start)
    end_ts = format_time_ass(end)
    # Escape special characters and handle newlines
    text = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    text = text.replace("\n", "\\N")
    return f"Dialogue: 0,{start_ts},{end_ts},{style},,0,0,0,,{text}"
