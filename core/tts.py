"""
TTS integration using easy-edge-tts
Converts narration text to speech audio for manga videos
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Map manga video moods to easy-edge-tts moods
MOOD_MAPPING = {
    "action": "dramatic",
    "tense": "suspense",
    "comedic": "happy",
    "sad": "sad",
    "romantic": "heartwarming",
    "mysterious": "mysterious",
    "neutral": "neutral",
}


class NarrationGenerator:
    """
    Generate voice narration for manga video pages.

    Uses easy-edge-tts for free, high-quality Microsoft Edge voices.
    Supports mood-based voice selection to match the manga's tone.
    """

    def __init__(self, voice: str = "guy", rate: str = "+0%"):
        """
        Initialize the narration generator.

        Args:
            voice: Default voice to use (e.g., "guy", "aria", "jenny")
            rate: Speech rate adjustment (e.g., "+10%", "-10%")
        """
        self.default_voice = voice
        self.rate = rate
        self._rotator = None
        self._tts_class = None

    def _ensure_imports(self):
        """Lazy import easy-edge-tts to avoid import errors if not installed."""
        if self._tts_class is None:
            try:
                from easy_edge_tts import EdgeTTS, VoiceRotator
                self._tts_class = EdgeTTS
                self._rotator = VoiceRotator()
            except ImportError:
                raise ImportError(
                    "easy-edge-tts not installed. Run: pip install easy-edge-tts"
                )

    async def generate_audio(
        self,
        text: str,
        output_path: Path,
        voice: Optional[str] = None,
        rate: Optional[str] = None
    ) -> dict:
        """
        Generate audio file from text.

        Args:
            text: Text to convert to speech
            output_path: Where to save the audio file
            voice: Voice to use (defaults to self.default_voice)
            rate: Speech rate (defaults to self.rate)

        Returns:
            Dict with audio_path and duration
        """
        self._ensure_imports()

        voice = voice or self.default_voice
        rate = rate or self.rate

        tts = self._tts_class(voice=voice)
        result = await tts.generate(text, output_path, rate=rate)

        return {
            "audio_path": str(result.audio_path),
            "duration": result.duration,
            "voice": result.voice
        }

    async def generate_narration_audio(
        self,
        pages_data: list[dict],
        output_dir: Path,
        use_mood_voice: bool = True,
        consistent_voice: bool = True
    ) -> list[dict]:
        """
        Generate audio for each page's narration.

        Args:
            pages_data: List of page dicts with "narration" and "mood" keys
            output_dir: Directory to save audio files
            use_mood_voice: Whether to select voice based on page mood
            consistent_voice: Use same voice for entire video (recommended)

        Returns:
            Updated pages_data with narration_audio paths added
        """
        self._ensure_imports()

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Determine dominant mood for consistent voice selection
        if consistent_voice and use_mood_voice:
            moods = [p.get("mood", "neutral") for p in pages_data]
            dominant_mood = max(set(moods), key=moods.count)
            mapped_mood = MOOD_MAPPING.get(dominant_mood, "neutral")
            chapter_tts = self._rotator.get_tts_for_mood(mapped_mood)
            logger.info(f"Using voice {chapter_tts.voice} for mood '{dominant_mood}'")
        else:
            chapter_tts = self._tts_class(voice=self.default_voice)

        narration_count = 0
        for i, page in enumerate(pages_data):
            narration = page.get("narration", "").strip()
            if not narration:
                page["narration_audio"] = None
                page["narration_duration"] = 0.0
                continue

            # Generate audio for this page
            audio_path = output_dir / f"narration_{i:03d}.mp3"

            try:
                if consistent_voice:
                    result = await chapter_tts.generate(narration, audio_path, rate=self.rate)
                else:
                    # Per-page mood voice selection
                    mood = page.get("mood", "neutral")
                    mapped_mood = MOOD_MAPPING.get(mood, "neutral")
                    tts = self._rotator.get_tts_for_mood(mapped_mood)
                    result = await tts.generate(narration, audio_path, rate=self.rate)

                page["narration_audio"] = str(result.audio_path)
                page["narration_duration"] = result.duration
                narration_count += 1
                logger.debug(f"Generated narration {i}: {result.duration:.1f}s")

            except Exception as e:
                logger.error(f"Failed to generate narration for page {i}: {e}")
                page["narration_audio"] = None
                page["narration_duration"] = 0.0

        logger.info(f"Generated {narration_count} narration audio files")
        return pages_data

    async def concatenate_narration(
        self,
        pages_data: list[dict],
        output_path: Path,
        gap_duration: float = 0.3
    ) -> Optional[Path]:
        """
        Concatenate all narration audio files into one track.

        Adds silence gaps between narrations to match video timing.

        Args:
            pages_data: Pages with narration_audio and suggested_duration
            output_path: Where to save the combined audio
            gap_duration: Silence between narrations (seconds)

        Returns:
            Path to combined audio file, or None if no narrations
        """
        import subprocess

        # Collect narration files that exist
        audio_files = []
        timings = []
        current_time = 0.0

        for page in pages_data:
            page_duration = page.get("suggested_duration", 4.0)
            narration_audio = page.get("narration_audio")

            if narration_audio and Path(narration_audio).exists():
                audio_files.append(narration_audio)
                timings.append({
                    "start": current_time,
                    "file": narration_audio,
                    "page_duration": page_duration
                })

            current_time += page_duration

        if not audio_files:
            logger.warning("No narration audio files to concatenate")
            return None

        # Use FFmpeg to concatenate with proper timing
        # Create a filter that places each audio at the right time
        total_duration = current_time

        # Build FFmpeg command for mixing audio at correct times
        inputs = []
        filter_parts = []

        for i, timing in enumerate(timings):
            inputs.extend(["-i", timing["file"]])
            delay_ms = int(timing["start"] * 1000)
            filter_parts.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")

        # Mix all delayed audio streams
        mix_inputs = "".join(f"[a{i}]" for i in range(len(timings)))
        filter_parts.append(f"{mix_inputs}amix=inputs={len(timings)}:duration=longest[out]")

        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                logger.info(f"Created combined narration: {output_path}")
                return output_path
            else:
                logger.error(f"FFmpeg error: {result.stderr}")
                return None
        except Exception as e:
            logger.error(f"Failed to concatenate narration: {e}")
            return None
