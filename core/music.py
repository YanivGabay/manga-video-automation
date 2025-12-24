"""
Music fetcher for royalty-free background music
Supports Freesound API and local music files
"""
import httpx
import os
from pathlib import Path
from typing import Optional
import sys
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import OUTPUT_DIR

# Freesound API settings
FREESOUND_API_BASE = "https://freesound.org/apiv2"


class MusicFetcher:
    def __init__(self, freesound_api_key: Optional[str] = None):
        self.api_key = freesound_api_key or os.getenv("FREESOUND_API_KEY", "")
        self.local_music_dir = OUTPUT_DIR.parent / "music"
        self.local_music_dir.mkdir(exist_ok=True)

    async def search_freesound(
        self,
        query: str,
        min_duration: int = 60,
        max_duration: int = 300
    ) -> list[dict]:
        """Search Freesound for music tracks"""
        if not self.api_key:
            print("Warning: No Freesound API key set")
            return []

        params = {
            "query": query,
            "token": self.api_key,
            "fields": "id,name,duration,previews,tags,avg_rating",
            "filter": f"duration:[{min_duration} TO {max_duration}]",
            "sort": "rating_desc",
            "page_size": 10
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{FREESOUND_API_BASE}/search/text/",
                params=params
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for sound in data.get("results", []):
                results.append({
                    "id": sound["id"],
                    "name": sound["name"],
                    "duration": sound["duration"],
                    "preview_url": sound.get("previews", {}).get("preview-hq-mp3"),
                    "tags": sound.get("tags", []),
                    "rating": sound.get("avg_rating", 0)
                })
            return results

    async def download_preview(
        self,
        sound_id: int,
        preview_url: str,
        output_path: Optional[Path] = None
    ) -> Path:
        """Download a preview MP3 from Freesound (no OAuth needed for previews)"""
        if output_path is None:
            output_path = self.local_music_dir / f"freesound_{sound_id}.mp3"

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(preview_url)
            response.raise_for_status()
            output_path.write_bytes(response.content)

        return output_path

    async def get_music_for_mood(self, mood: str) -> Optional[Path]:
        """Get a music track matching the mood"""
        # Map moods to search queries
        mood_queries = {
            "tense": "suspense tension dramatic",
            "action": "action epic battle intense",
            "sad": "sad emotional melancholy piano",
            "comedic": "funny comedy upbeat quirky",
            "romantic": "romantic love gentle soft",
            "dark": "dark ominous horror ambient",
            "happy": "happy upbeat cheerful positive",
            "mysterious": "mystery suspense ambient",
            "epic": "epic orchestral cinematic",
            "calm": "calm peaceful ambient relaxing"
        }

        query = mood_queries.get(mood, "ambient background music")

        # First check for local music files
        local_file = self._find_local_music(mood)
        if local_file:
            print(f"Using local music: {local_file.name}")
            return local_file

        # Search Freesound
        if self.api_key:
            print(f"Searching Freesound for: {query}")
            results = await self.search_freesound(query)

            if results:
                best = results[0]
                print(f"Found: {best['name']} ({best['duration']:.1f}s)")

                if best.get("preview_url"):
                    return await self.download_preview(
                        best["id"],
                        best["preview_url"]
                    )

        print("No music found - video will be silent")
        return None

    def _find_local_music(self, mood: str) -> Optional[Path]:
        """Find local music file matching mood - uses Kevin MacLeod CC BY 4.0 tracks"""
        if not self.local_music_dir.exists():
            return None

        # Map moods to local file prefixes/names
        mood_to_file = {
            "action": ["action_", "Volatile", "epic_", "Heroic"],
            "tense": ["dark_", "Darkest", "action_"],
            "dark": ["dark_", "Darkest"],
            "epic": ["epic_", "Heroic", "action_"],
            "sad": ["Dreams", "Inspired"],
            "romantic": ["Dreams", "Inspired", "Wholesome"],
            "happy": ["Wholesome", "Inspired"],
            "comedic": ["Wholesome"],
            "calm": ["Dreams", "Inspired"],
            "mysterious": ["dark_", "Dreams"],
        }

        search_patterns = mood_to_file.get(mood, [])

        # Look for files matching mood patterns
        for ext in ["mp3", "wav", "m4a", "ogg"]:
            for f in self.local_music_dir.glob(f"*.{ext}"):
                for pattern in search_patterns:
                    if pattern.lower() in f.name.lower():
                        return f

        # Fallback to any music file
        for ext in ["mp3", "wav", "m4a", "ogg"]:
            files = list(self.local_music_dir.glob(f"*.{ext}"))
            if files:
                import random
                return random.choice(files)

        return None

    def list_local_music(self) -> list[Path]:
        """List all local music files"""
        files = []
        for ext in ["mp3", "wav", "m4a", "ogg"]:
            files.extend(self.local_music_dir.glob(f"*.{ext}"))
        return files


# Quick test
if __name__ == "__main__":
    import asyncio

    async def test():
        fetcher = MusicFetcher()

        print(f"Local music directory: {fetcher.local_music_dir}")
        print(f"Local files: {fetcher.list_local_music()}")

        if fetcher.api_key:
            print("\nSearching Freesound...")
            results = await fetcher.search_freesound("ambient cinematic")
            for r in results[:3]:
                print(f"  {r['name']} - {r['duration']:.1f}s")
        else:
            print("\nNo FREESOUND_API_KEY set, skipping API test")

    asyncio.run(test())
