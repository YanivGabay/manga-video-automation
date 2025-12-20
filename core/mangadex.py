"""
MangaDex API client for fetching manga chapters and pages
"""
import httpx
from pathlib import Path
from typing import Optional
import sys
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import MANGADEX_API_BASE, MANGADEX_USER_AGENT, OUTPUT_DIR


class MangaDexClient:
    def __init__(self):
        self.base_url = MANGADEX_API_BASE
        self.headers = {"User-Agent": MANGADEX_USER_AGENT}

    async def search_manga(self, title: str, limit: int = 10) -> list[dict]:
        """Search for manga by title"""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url}/manga",
                params={
                    "title": title,
                    "limit": limit,
                    "includes[]": ["tag"]
                },
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for manga in data.get("data", []):
                attrs = manga["attributes"]
                titles = attrs["title"]
                title_en = titles.get("en") or list(titles.values())[0]

                # Get description
                descriptions = attrs.get("description", {})
                desc_en = descriptions.get("en", "")

                # Get genres/tags
                genres = []
                for tag in attrs.get("tags", []):
                    tag_name = tag["attributes"]["name"].get("en", "")
                    if tag_name:
                        genres.append(tag_name)

                results.append({
                    "id": manga["id"],
                    "title": title_en,
                    "status": attrs["status"],
                    "description": desc_en,
                    "genres": genres[:5]  # Limit to top 5 genres
                })
            return results

    async def get_chapters(
        self,
        manga_id: str,
        language: str = "en",
        limit: int = 100
    ) -> list[dict]:
        """Get chapters for a manga"""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url}/manga/{manga_id}/feed",
                params={
                    "translatedLanguage[]": language,
                    "limit": limit,
                    "order[chapter]": "asc"
                },
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json()

            chapters = []
            for ch in data.get("data", []):
                attrs = ch["attributes"]
                if attrs["pages"] > 0:  # Only chapters with pages
                    chapters.append({
                        "id": ch["id"],
                        "chapter": attrs["chapter"],
                        "title": attrs["title"],
                        "pages": attrs["pages"]
                    })
            return chapters

    async def get_chapter_images(self, chapter_id: str) -> list[str]:
        """Get image URLs for a chapter"""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url}/at-home/server/{chapter_id}",
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json()

            base_url = data["baseUrl"]
            chapter_hash = data["chapter"]["hash"]
            images = data["chapter"]["data"]

            return [
                f"{base_url}/data/{chapter_hash}/{img}"
                for img in images
            ]

    async def download_chapter(
        self,
        chapter_id: str,
        output_dir: Optional[Path] = None
    ) -> list[Path]:
        """Download all pages from a chapter"""
        if output_dir is None:
            output_dir = OUTPUT_DIR / "pages"
        output_dir.mkdir(parents=True, exist_ok=True)

        image_urls = await self.get_chapter_images(chapter_id)
        downloaded = []

        async with httpx.AsyncClient(timeout=60) as client:
            for i, url in enumerate(image_urls):
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()

                ext = url.split(".")[-1]
                file_path = output_dir / f"page_{i+1:03d}.{ext}"
                file_path.write_bytes(response.content)
                downloaded.append(file_path)
                print(f"  Downloaded page {i+1}/{len(image_urls)}")

        return downloaded


# Quick test
if __name__ == "__main__":
    import asyncio

    async def test():
        client = MangaDexClient()

        # Search for a manga
        print("Searching for 'Berserk'...")
        results = await client.search_manga("Berserk", limit=3)
        for r in results:
            print(f"  {r['title']} ({r['status']}) - {r['id']}")

        if results:
            manga_id = results[0]["id"]
            print(f"\nGetting chapters for {results[0]['title']}...")
            chapters = await client.get_chapters(manga_id, limit=5)
            for ch in chapters[:5]:
                print(f"  Ch {ch['chapter']}: {ch['pages']} pages")

    asyncio.run(test())
