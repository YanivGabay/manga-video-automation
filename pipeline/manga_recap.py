"""
Manga Recap Pipeline
Downloads manga chapter, analyzes it, and creates a video
"""
import asyncio
import json
from pathlib import Path
from typing import Optional
import sys
sys.path.append(str(Path(__file__).parent.parent))

from config.settings import OUTPUT_DIR
from core.mangadex import MangaDexClient
from core.openrouter import OpenRouterClient
from core.music import MusicFetcher
from core.video import VideoBuilder
from core.cache import MangaCache
from core.tts import NarrationGenerator


class MangaRecapPipeline:
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.mangadex = MangaDexClient()
        self.ai = OpenRouterClient()
        self.music = MusicFetcher()
        self.video = VideoBuilder(output_dir=self.output_dir)
        self.cache = MangaCache()
        self.tts = NarrationGenerator(voice="guy", rate="+0%")

    async def search_manga(self, title: str) -> list[dict]:
        """Search for manga by title"""
        print(f"Searching for '{title}'...")
        results = await self.mangadex.search_manga(title)
        return results

    async def get_manga_context(self, manga: dict) -> dict:
        """Get manga context - from cache or use MangaDex data.

        Uses the MangaDex description directly (spoiler-free by nature).
        Previous chapter summaries provide continuity as we process chapters.

        Args:
            manga: Dict with id, title, description, genres from MangaDex

        Returns:
            Context dict with title, description, genres, etc.
        """
        manga_id = manga["id"]

        # Check cache first
        if self.cache.has_context(manga_id):
            print(f"  Using cached context for '{manga['title']}'")
            return self.cache.get_context(manga_id)

        # Use MangaDex description directly - no AI generation needed
        # MangaDex descriptions are naturally spoiler-free and include main character names
        print(f"  Caching context for '{manga['title']}'...")

        context = {
            "title": manga["title"],
            "description": manga.get("description", ""),
            "genres": manga.get("genres", []),
            "chapter_summaries": []
        }

        # Save to cache
        self.cache.save_context(manga_id, context)
        print(f"  Context cached for future use")

        return context

    def get_previous_chapter_summaries(self, manga_id: str, chapter_number: str) -> str:
        """Get formatted previous chapter summaries for narration context."""
        summaries = self.cache.get_previous_summaries(manga_id, chapter_number, limit=3)

        if not summaries:
            return ""

        lines = ["Previously:"]
        for s in summaries:
            lines.append(f"- Chapter {s['chapter']}: {s['summary']}")

        return "\n".join(lines)

    async def generate_chapter_summary(self, manga_title: str, chapter_number: str, page_descriptions: list[str]) -> str:
        """Generate a brief story summary of the chapter from page descriptions."""
        pages_text = "\n".join([f"- {desc}" for desc in page_descriptions])

        prompt = f"""Based on these manga page descriptions from {manga_title} Chapter {chapter_number}, write a 2-3 sentence story summary:

{pages_text}

Focus on: What happened? Who was involved? What changed?
Write it as a brief story recap, not a list. Respond with just the summary."""

        summary = await self.ai.generate_text(prompt, max_tokens=400)
        return summary.strip()

    async def save_chapter_data(self, manga_id: str, chapter_number: str, analysis: dict, manga_title: str = "") -> None:
        """Save chapter analysis and generate summary for future context."""
        # Extract page descriptions for summary (actual story content, not narration)
        descriptions = [p.get("description", "") for p in analysis.get("pages", []) if p.get("description")]

        # Generate summary
        summary = await self.generate_chapter_summary(manga_title, chapter_number, descriptions)
        print(f"  Chapter summary: {summary[:100]}...")

        # Save chapter data
        chapter_data = {
            "summary": summary,
            "total_pages": analysis.get("total_pages", 0),
            "dominant_mood": analysis.get("dominant_mood", "unknown"),
            "duration": analysis.get("total_duration", 0)
        }

        self.cache.save_chapter(manga_id, chapter_number, chapter_data)

    async def get_available_chapters(self, manga_id: str) -> list[dict]:
        """Get list of available chapters for a manga"""
        print("Fetching chapters...")
        chapters = await self.mangadex.get_chapters(manga_id)
        return chapters

    async def download_chapter(self, chapter_id: str) -> list[Path]:
        """Download all pages from a chapter"""
        print(f"Downloading chapter {chapter_id}...")
        pages_dir = self.output_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)

        # Clean previous pages
        for f in pages_dir.glob("*"):
            f.unlink()

        pages = await self.mangadex.download_chapter(chapter_id, pages_dir)
        print(f"Downloaded {len(pages)} pages")
        return pages

    async def analyze_chapter(self, page_paths: list[Path]) -> dict:
        """Analyze all pages with AI vision"""
        print("Analyzing chapter with AI...")
        analysis = await self.ai.analyze_chapter(page_paths)

        # Save analysis
        analysis_path = self.output_dir / "chapter_analysis.json"
        with open(analysis_path, "w") as f:
            # Convert Path objects to strings for JSON
            serializable = {
                "pages": [
                    {**p, "file_path": str(p["file_path"])}
                    for p in analysis["pages"]
                ],
                "total_pages": analysis["total_pages"],
                "all_dialogue": analysis["all_dialogue"],
                "dominant_mood": analysis["dominant_mood"],
                "action_percentage": analysis["action_percentage"],
                "total_duration": analysis["total_duration"]
            }
            json.dump(serializable, f, indent=2)

        print(f"Chapter mood: {analysis['dominant_mood']}")
        print(f"Estimated video duration: {analysis['total_duration']:.1f}s")
        return analysis

    async def get_music(self, mood: str) -> Optional[Path]:
        """Get background music matching the mood"""
        print(f"Finding music for mood: {mood}...")
        music_path = await self.music.get_music_for_mood(mood)
        return music_path

    async def build_video(
        self,
        analysis: dict,
        music_path: Optional[Path] = None,
        output_name: str = "manga_recap.mp4",
        enable_tts: bool = True
    ) -> Optional[Path]:
        """Build the final video with optional voice narration"""
        # Generate voice narration if enabled
        if enable_tts:
            print("Generating voice narration...")
            narration_dir = self.output_dir / "narration"
            try:
                analysis["pages"] = await self.tts.generate_narration_audio(
                    pages_data=analysis["pages"],
                    output_dir=narration_dir,
                    use_mood_voice=True,
                    consistent_voice=True
                )
                print(f"  Voice narration generated for {sum(1 for p in analysis['pages'] if p.get('narration_audio'))} pages")
            except ImportError as e:
                print(f"  TTS not available: {e}")
                print("  Continuing without voice narration...")
            except Exception as e:
                print(f"  TTS failed: {e}")
                print("  Continuing without voice narration...")

        print("Building video...")
        video_path = self.video.build_manga_video(
            pages_data=analysis["pages"],
            music_path=music_path,
            output_name=output_name
        )
        return video_path

    async def run(
        self,
        manga_title: str,
        chapter_number: Optional[str] = None,
        output_name: str = "manga_recap.mp4"
    ) -> Optional[Path]:
        """
        Run the complete pipeline.

        1. Search for manga
        2. Select chapter
        3. Download pages
        4. Analyze with AI
        5. Get music
        6. Build video
        """
        print("=" * 60)
        print("MANGA RECAP PIPELINE")
        print("=" * 60)

        # Step 1: Search manga
        results = await self.search_manga(manga_title)
        if not results:
            print(f"No manga found for '{manga_title}'")
            return None

        manga = results[0]
        print(f"Selected: {manga['title']}")

        # Step 2: Get chapters
        chapters = await self.get_available_chapters(manga["id"])
        if not chapters:
            print("No chapters available")
            return None

        # Select chapter
        if chapter_number:
            chapter = next(
                (c for c in chapters if c["chapter"] == chapter_number),
                chapters[0]
            )
        else:
            chapter = chapters[0]

        print(f"Using chapter {chapter['chapter']}: {chapter.get('title', 'Untitled')}")

        # Step 3: Download pages
        pages = await self.download_chapter(chapter["id"])
        if not pages:
            print("Failed to download pages")
            return None

        # Step 4: Analyze with AI
        analysis = await self.analyze_chapter(pages)

        # Step 5: Get music
        music_path = await self.get_music(analysis["dominant_mood"])

        # Step 6: Build video
        video_path = await self.build_video(analysis, music_path, output_name)

        if video_path:
            print("=" * 60)
            print(f"SUCCESS! Video created: {video_path}")
            print("=" * 60)

        return video_path


# Quick test
if __name__ == "__main__":
    async def test():
        pipeline = MangaRecapPipeline()

        # Just test search
        results = await pipeline.search_manga("Berserk")
        for r in results[:3]:
            print(f"  {r['title']} - {r['id']}")

    asyncio.run(test())
