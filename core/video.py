"""
Video builder using FFmpeg
Assembles manga pages with effects, subtitles, and music
"""
import subprocess
import json
from pathlib import Path
from typing import Optional
import sys
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import (
    OUTPUT_DIR, VIDEO_WIDTH, VIDEO_HEIGHT, FPS,
    DEFAULT_PAGE_DURATION, MUSIC_VOLUME
)
from .effects import (
    generate_ken_burns, get_filter_for_mood,
    generate_subtitle_style, create_subtitle_event
)


class VideoBuilder:
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.width = VIDEO_WIDTH
        self.height = VIDEO_HEIGHT
        self.fps = FPS

    def create_clip_from_image(
        self,
        image_path: Path,
        duration: float,
        output_path: Path,
        mood: str = "neutral",
        ken_burns_style: str = "random"
    ) -> bool:
        """Create a video clip from a single image with gentle Ken Burns effect.

        Uses subtle zoom only - no cropping, preserves full manga page.
        """
        total_frames = int(duration * self.fps)

        # Gentle zoom: start at 1.0 (full image), end at 1.05 (5% zoom)
        # This ensures we never crop the image
        # zoom starts slightly zoomed out, slowly zooms to fit

        # Build FFmpeg command
        # 1. Scale to fit frame with padding (letterbox/pillarbox)
        # 2. Apply very gentle zoom (zoom OUT to IN, so we start seeing full image)
        # 3. Keep centered so no cropping occurs
        filter_complex = (
            f"[0:v]scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:black,"
            f"zoompan=z='1+on/{total_frames}*0.03':"  # Gentle 3% zoom over duration
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"  # Stay centered
            f"d={total_frames}:s={self.width}x{self.height}:fps={self.fps},"
            f"format=yuv420p"
        )

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-filter_complex", filter_complex,
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            str(output_path)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            print(f"Timeout creating clip from {image_path}")
            return False
        except Exception as e:
            print(f"Error creating clip: {e}")
            return False

    def concatenate_clips(
        self,
        clip_paths: list[Path],
        output_path: Path
    ) -> bool:
        """Concatenate multiple video clips into one"""

        # Create concat file
        concat_file = self.output_dir / "concat_list.txt"
        with open(concat_file, "w") as f:
            for clip in clip_paths:
                f.write(f"file '{clip.absolute()}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            concat_file.unlink()  # Clean up
            return result.returncode == 0
        except Exception as e:
            print(f"Error concatenating clips: {e}")
            return False

    def add_music(
        self,
        video_path: Path,
        music_path: Path,
        output_path: Path,
        volume: float = MUSIC_VOLUME
    ) -> bool:
        """Add background music to video"""

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(music_path),
            "-filter_complex",
            f"[1:a]volume={volume},aloop=loop=-1:size=2e+09[a];[a]atrim=0:$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {video_path})[music]",
            "-map", "0:v",
            "-map", "[music]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_path)
        ]

        # Simpler approach - just mix the audio
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-stream_loop", "-1",
            "-i", str(music_path),
            "-filter_complex", f"[1:a]volume={volume}[a]",
            "-map", "0:v",
            "-map", "[a]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return result.returncode == 0
        except Exception as e:
            print(f"Error adding music: {e}")
            return False

    def add_subtitles(
        self,
        video_path: Path,
        subtitle_path: Path,
        output_path: Path
    ) -> bool:
        """Burn subtitles into video"""

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", f"ass={subtitle_path}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "copy",
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return result.returncode == 0
        except Exception as e:
            print(f"Error adding subtitles: {e}")
            return False

    def create_subtitles_file(
        self,
        dialogues: list[dict],
        output_path: Path
    ) -> Path:
        """
        Create ASS subtitle file from dialogue list.

        dialogues: list of {"start": float, "end": float, "text": str}
        """
        content = generate_subtitle_style()

        for d in dialogues:
            content += create_subtitle_event(
                d["start"],
                d["end"],
                d["text"]
            ) + "\n"

        output_path.write_text(content)
        return output_path

    def build_manga_video(
        self,
        pages_data: list[dict],
        music_path: Optional[Path] = None,
        output_name: str = "manga_video.mp4"
    ) -> Optional[Path]:
        """
        Build complete manga video from analyzed pages.

        pages_data: list of {
            "file_path": str,
            "suggested_duration": float,
            "mood": str,
            "dialogue": list[str]
        }
        """
        print(f"Building video from {len(pages_data)} pages...")

        # Step 1: Create individual clips
        clips = []
        current_time = 0.0
        all_dialogues = []

        for i, page in enumerate(pages_data):
            print(f"  Processing page {i+1}/{len(pages_data)}...")

            duration = page.get("suggested_duration", DEFAULT_PAGE_DURATION)
            mood = page.get("mood", "neutral")
            image_path = Path(page["file_path"])
            clip_path = self.output_dir / f"clip_{i:03d}.mp4"

            success = self.create_clip_from_image(
                image_path=image_path,
                duration=duration,
                output_path=clip_path,
                mood=mood
            )

            if success:
                clips.append(clip_path)

                # Collect narration for subtitles
                narration = page.get("narration", "")
                if narration:
                    all_dialogues.append({
                        "start": current_time,
                        "end": current_time + duration,
                        "text": narration
                    })

                current_time += duration
            else:
                print(f"  Warning: Failed to create clip for page {i+1}")

        if not clips:
            print("Error: No clips created")
            return None

        # Step 2: Concatenate clips
        print("Concatenating clips...")
        concat_path = self.output_dir / "concat_temp.mp4"
        if not self.concatenate_clips(clips, concat_path):
            print("Error: Failed to concatenate clips")
            return None

        # Step 3: Add subtitles if we have dialogues
        current_video = concat_path
        subs_video = None
        subs_path = None
        if all_dialogues:
            print("Adding subtitles...")
            subs_path = self.output_dir / "subtitles.ass"
            self.create_subtitles_file(all_dialogues, subs_path)

            subs_video = self.output_dir / "with_subs.mp4"
            if self.add_subtitles(current_video, subs_path, subs_video):
                current_video = subs_video

        # Step 4: Add music if provided
        final_path = self.output_dir / output_name
        if music_path and music_path.exists():
            print("Adding background music...")
            if self.add_music(current_video, music_path, final_path):
                # Clean up all temp files
                self._cleanup_temp_files(clips, concat_path, subs_video, subs_path)
                print(f"Video created: {final_path}")
                return final_path

        # No music - just rename
        current_video.rename(final_path)
        self._cleanup_temp_files(clips, concat_path, subs_video, subs_path)

        print(f"Video created: {final_path}")
        return final_path

    def _cleanup_temp_files(self, clips: list[Path], *other_files: Path):
        """Clean up temporary files"""
        for clip in clips:
            if clip and clip.exists():
                clip.unlink()
        for f in other_files:
            if f and f.exists():
                f.unlink()


# Quick test
if __name__ == "__main__":
    builder = VideoBuilder()
    print(f"Output directory: {builder.output_dir}")
    print(f"Video dimensions: {builder.width}x{builder.height}")
    print(f"FPS: {builder.fps}")
