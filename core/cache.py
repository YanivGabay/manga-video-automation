"""
Manga caching system for storing series context and chapter summaries.
Builds up knowledge over time for better narration.
"""
import json
from pathlib import Path
from typing import Optional
from datetime import datetime


class MangaCache:
    """Cache manga context and chapter data for reuse across sessions."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path(__file__).parent.parent / "manga_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_manga_dir(self, manga_id: str) -> Path:
        """Get the cache directory for a specific manga."""
        manga_dir = self.cache_dir / manga_id
        manga_dir.mkdir(parents=True, exist_ok=True)
        return manga_dir

    def _get_chapters_dir(self, manga_id: str) -> Path:
        """Get the chapters subdirectory for a manga."""
        chapters_dir = self._get_manga_dir(manga_id) / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)
        return chapters_dir

    # ==================== Context Methods ====================

    def has_context(self, manga_id: str) -> bool:
        """Check if we have cached context for a manga."""
        context_file = self._get_manga_dir(manga_id) / "context.json"
        return context_file.exists()

    def get_context(self, manga_id: str) -> Optional[dict]:
        """Load cached manga context."""
        context_file = self._get_manga_dir(manga_id) / "context.json"
        if not context_file.exists():
            return None

        with open(context_file, "r") as f:
            return json.load(f)

    def save_context(self, manga_id: str, context: dict) -> None:
        """Save manga context to cache."""
        context_file = self._get_manga_dir(manga_id) / "context.json"

        # Add metadata
        context["_cached_at"] = datetime.now().isoformat()
        context["_manga_id"] = manga_id

        with open(context_file, "w") as f:
            json.dump(context, f, indent=2)

    def update_context(self, manga_id: str, updates: dict) -> None:
        """Update existing context with new data."""
        context = self.get_context(manga_id) or {}
        context.update(updates)
        context["_updated_at"] = datetime.now().isoformat()
        self.save_context(manga_id, context)

    # ==================== Chapter Methods ====================

    def has_chapter(self, manga_id: str, chapter_number: str) -> bool:
        """Check if we have cached data for a chapter."""
        chapter_file = self._get_chapters_dir(manga_id) / f"ch_{chapter_number}.json"
        return chapter_file.exists()

    def get_chapter(self, manga_id: str, chapter_number: str) -> Optional[dict]:
        """Load cached chapter data."""
        chapter_file = self._get_chapters_dir(manga_id) / f"ch_{chapter_number}.json"
        if not chapter_file.exists():
            return None

        with open(chapter_file, "r") as f:
            return json.load(f)

    def save_chapter(self, manga_id: str, chapter_number: str, data: dict) -> None:
        """Save chapter data to cache."""
        chapter_file = self._get_chapters_dir(manga_id) / f"ch_{chapter_number}.json"

        data["_cached_at"] = datetime.now().isoformat()
        data["_chapter_number"] = chapter_number

        with open(chapter_file, "w") as f:
            json.dump(data, f, indent=2)

        # Also update the chapter summaries in context
        if "summary" in data:
            self._add_chapter_summary(manga_id, chapter_number, data["summary"])

    def _add_chapter_summary(self, manga_id: str, chapter_number: str, summary: str) -> None:
        """Add a chapter summary to the context's chapter_summaries list."""
        context = self.get_context(manga_id) or {}

        summaries = context.get("chapter_summaries", [])

        # Remove existing summary for this chapter if present
        summaries = [s for s in summaries if s.get("chapter") != chapter_number]

        # Add new summary
        summaries.append({
            "chapter": chapter_number,
            "summary": summary
        })

        # Sort by chapter number
        summaries.sort(key=lambda x: float(x["chapter"]) if x["chapter"].replace(".", "").isdigit() else 0)

        context["chapter_summaries"] = summaries
        self.save_context(manga_id, context)

    def get_previous_summaries(self, manga_id: str, current_chapter: str, limit: int = 3) -> list[dict]:
        """Get summaries of chapters BEFORE the given chapter number (excludes current)."""
        context = self.get_context(manga_id)
        if not context:
            return []

        summaries = context.get("chapter_summaries", [])

        try:
            chapter_num = float(current_chapter)
        except ValueError:
            return []

        # Get chapters strictly before this one (not equal to)
        previous = [s for s in summaries if float(s["chapter"]) < chapter_num]

        # Return the most recent ones (up to limit)
        return previous[-limit:]

    def get_all_chapters(self, manga_id: str) -> list[str]:
        """Get list of all cached chapter numbers for a manga."""
        chapters_dir = self._get_chapters_dir(manga_id)
        chapters = []

        for f in chapters_dir.glob("ch_*.json"):
            chapter_num = f.stem.replace("ch_", "")
            chapters.append(chapter_num)

        # Sort numerically
        chapters.sort(key=lambda x: float(x) if x.replace(".", "").isdigit() else 0)
        return chapters

    # ==================== Alias Methods (for automation compatibility) ====================

    def get_manga_context(self, manga_id: str) -> Optional[dict]:
        """Alias for get_context."""
        return self.get_context(manga_id)

    def save_manga_context(self, manga_id: str, context: dict) -> None:
        """Alias for save_context."""
        self.save_context(manga_id, context)

    def save_chapter_summary(self, manga_id: str, chapter_number: int, summary: str) -> None:
        """Save just a chapter summary (convenience method)."""
        self.save_chapter(manga_id, str(chapter_number), {"summary": summary})

    def get_chapter_summaries_text(self, manga_id: str, last_n: int = 3) -> str:
        """
        Get formatted text of recent chapter summaries for AI prompts.

        Returns string like:
        PREVIOUS CHAPTERS:
        Chapter 148: Summary text here...
        Chapter 149: Summary text here...
        """
        context = self.get_context(manga_id)
        if not context:
            return ""

        summaries = context.get("chapter_summaries", [])
        if not summaries:
            return ""

        recent = summaries[-last_n:]
        if not recent:
            return ""

        lines = ["PREVIOUS CHAPTERS:"]
        for s in recent:
            lines.append(f"Chapter {s['chapter']}: {s['summary']}")

        return "\n".join(lines)

    # ==================== Utility Methods ====================

    def list_cached_manga(self) -> list[dict]:
        """List all manga in the cache with basic info."""
        manga_list = []

        for manga_dir in self.cache_dir.iterdir():
            if manga_dir.is_dir() and (manga_dir / "context.json").exists():
                context = self.get_context(manga_dir.name)
                if context:
                    manga_list.append({
                        "id": manga_dir.name,
                        "title": context.get("title", "Unknown"),
                        "chapters_cached": len(self.get_all_chapters(manga_dir.name))
                    })

        return manga_list

    def clear_manga_cache(self, manga_id: str) -> None:
        """Clear all cached data for a manga."""
        import shutil
        manga_dir = self._get_manga_dir(manga_id)
        if manga_dir.exists():
            shutil.rmtree(manga_dir)


# Quick test
if __name__ == "__main__":
    cache = MangaCache()

    # Test saving context
    test_id = "test-manga-123"
    cache.save_context(test_id, {
        "title": "Test Manga",
        "description": "A test manga for caching",
        "genres": ["Action", "Comedy"]
    })

    # Test loading context
    context = cache.get_context(test_id)
    print(f"Loaded context: {context}")

    # Test chapter saving
    cache.save_chapter(test_id, "1", {
        "summary": "The hero begins their journey",
        "pages": 10
    })

    cache.save_chapter(test_id, "2", {
        "summary": "The hero meets a companion",
        "pages": 12
    })

    # Test getting previous summaries
    prev = cache.get_previous_summaries(test_id, "3")
    print(f"Previous summaries: {prev}")

    # Cleanup
    cache.clear_manga_cache(test_id)
    print("Test passed!")
