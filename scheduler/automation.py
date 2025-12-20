"""
Main automation orchestrator for manga video creation and upload
"""
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
import sys
sys.path.append(str(Path(__file__).parent.parent))

from .tracker import Tracker
from core.mangadex import MangaDexClient
from core.openrouter import OpenRouterClient
from core.video import VideoBuilder
from core.music import MusicFetcher
from core.cache import MangaCache
from upload.youtube import YouTubeUploader
from config.settings import OUTPUT_DIR


class MangaAutomation:
    """
    Orchestrates the full automation pipeline:
    1. Pick next manga from tracker (round-robin)
    2. Find next chapter to process
    3. Download pages
    4. AI analysis + narration
    5. Build video
    6. Upload to YouTube
    7. Update tracker
    """

    def __init__(self):
        self.tracker = Tracker()
        self.mangadex = MangaDexClient()
        self.ai = OpenRouterClient()
        self.video = VideoBuilder()
        self.music = MusicFetcher()
        self.cache = MangaCache()
        self.youtube = YouTubeUploader()

    async def run_daily(self) -> Optional[dict]:
        """
        Run the daily automation job.

        Returns:
            Upload result dict or None if nothing to upload
        """
        print("=" * 60)
        print(f"MANGA VIDEO AUTOMATION - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)

        # Load tracker
        print("\n[1/7] Loading tracker...")
        self.tracker.load()
        series_list = self.tracker.list_series()

        if not series_list:
            print("No series configured. Add series with: tracker.add_series(id, name)")
            return None

        print(f"  Tracking {len(series_list)} series")

        # Get next series (round-robin)
        print("\n[2/7] Selecting next series...")
        series = self.tracker.get_next_series()
        print(f"  Selected: {series['name']}")
        print(f"  Last chapter: {series['last_chapter_num'] or 'None'}")

        # Find next chapter
        print("\n[3/7] Finding next chapter...")
        next_chapter = await self._find_next_chapter(series)

        if not next_chapter:
            print(f"  No new chapters for {series['name']}")
            # Move to next series for tomorrow
            self.tracker.advance_index()
            self.tracker.save()
            return None

        chapter_num = next_chapter["chapter"]
        chapter_id = next_chapter["id"]
        print(f"  Found: Chapter {chapter_num}")

        # Download pages
        print("\n[4/7] Downloading chapter pages...")
        pages = await self.mangadex.download_chapter(chapter_id)
        print(f"  Downloaded {len(pages)} pages")

        # Get manga context (cached)
        print("\n[5/7] Getting manga context...")
        manga_context = self.cache.get_manga_context(series["mangadex_id"])
        if not manga_context:
            # Fetch and cache
            manga_info = await self.mangadex.get_manga(series["mangadex_id"])
            manga_context = {
                "title": series["name"],
                "genres": manga_info.get("genres", []),
                "description": manga_info.get("description", ""),
                "chapter_number": str(chapter_num)
            }
            self.cache.save_manga_context(series["mangadex_id"], manga_context)
        else:
            manga_context["chapter_number"] = str(chapter_num)

        # Get previous chapter summaries for continuity
        previous_summaries = self.cache.get_chapter_summaries_text(
            series["mangadex_id"],
            last_n=3
        )

        # AI analysis
        print("\n[6/7] Analyzing with AI...")
        analysis = await self.ai.analyze_chapter(
            pages,
            manga_context=manga_context,
            previous_summaries=previous_summaries
        )

        # Save chapter summary
        if analysis.get("pages"):
            summary = " ".join([
                p.get("narration", "")[:100]
                for p in analysis["pages"][:5]
            ])
            self.cache.save_chapter_summary(
                series["mangadex_id"],
                chapter_num,
                summary[:500]
            )

        # Get background music
        print("\n[7/7] Building video...")
        mood = analysis.get("dominant_mood", "neutral")
        music_path = await self.music.get_music_for_mood(mood)

        # Build video
        output_name = f"{series['name'].lower().replace(' ', '-')}-ch{chapter_num}.mp4"
        video_path = self.video.build_manga_video(
            pages_data=analysis["pages"],
            music_path=music_path,
            output_name=output_name
        )

        if not video_path:
            raise Exception("Failed to build video")

        # Prepare metadata
        title = f"{series['name']} Chapter {chapter_num} Recap"
        description = f"""Recap of {series['name']} Chapter {chapter_num}

{analysis.get('pages', [{}])[0].get('narration', '')}

#Manga #Anime #{series['name'].replace(' ', '')} #Recap #Shorts"""

        # Upload to YouTube
        print("\n[8/8] Uploading to YouTube...")
        result = self.youtube.upload(
            video_path=video_path,
            title=title,
            description=description,
            tags=[series['name'], f"chapter {chapter_num}", "manga recap"]
        )

        # Record upload and advance
        self.tracker.record_upload(
            mangadex_id=series["mangadex_id"],
            chapter_num=chapter_num,
            chapter_id=chapter_id,
            youtube_id=result["video_id"]
        )
        self.tracker.advance_index()
        self.tracker.save()

        print("\n" + "=" * 60)
        print("SUCCESS!")
        print(f"Video: {result['url']}")
        print("=" * 60)

        return result

    async def _find_next_chapter(self, series: dict) -> Optional[dict]:
        """Find the next chapter to process for a series"""
        last_chapter = series.get("last_chapter_num", 0)

        # Get available chapters
        chapters = await self.mangadex.get_chapters(
            series["mangadex_id"],
            language="en"
        )

        if not chapters:
            return None

        # Find next chapter after last processed
        for chapter in chapters:
            chapter_num = chapter.get("chapter")
            if chapter_num is None:
                continue

            try:
                num = float(chapter_num)
                if num > last_chapter:
                    return {
                        "id": chapter["id"],
                        "chapter": num
                    }
            except ValueError:
                continue

        return None

    async def add_series_by_name(self, name: str) -> bool:
        """Search for a manga and add it to the tracker"""
        print(f"Searching for '{name}'...")
        results = await self.mangadex.search_manga(name, limit=5)

        if not results:
            print("No results found")
            return False

        # Use first result
        manga = results[0]
        manga_id = manga["id"]
        # Title can be string or dict depending on MangaDex response
        title = manga.get("title", name)
        manga_title = title if isinstance(title, str) else title.get("en", name)

        self.tracker.load()
        self.tracker.add_series(manga_id, manga_title)
        self.tracker.save()

        print(f"Added: {manga_title} ({manga_id})")
        return True


# CLI entry point
async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Manga Video Automation")
    parser.add_argument("command", choices=["run", "add", "list", "status"])
    parser.add_argument("--name", "-n", help="Manga name to add")

    args = parser.parse_args()

    automation = MangaAutomation()

    if args.command == "run":
        await automation.run_daily()

    elif args.command == "add":
        if not args.name:
            print("Error: --name required")
            return
        await automation.add_series_by_name(args.name)

    elif args.command == "list":
        automation.tracker.load()
        series = automation.tracker.list_series()
        if series:
            print("Tracked series:")
            for i, s in enumerate(series):
                marker = "→" if i == automation.tracker.data.get("next_index", 0) else " "
                print(f" {marker} {s['name']} (ch {s['last_chapter_num'] or 0})")
        else:
            print("No series tracked")

    elif args.command == "status":
        automation.tracker.load()
        data = automation.tracker.data
        print(f"Series: {len(data.get('series', []))}")
        print(f"Total uploads: {len(data.get('uploads', []))}")
        if data.get('uploads'):
            last = data['uploads'][-1]
            print(f"Last upload: {last['manga']} ch{last['chapter']} ({last['uploaded_at'][:10]})")


if __name__ == "__main__":
    asyncio.run(main())
