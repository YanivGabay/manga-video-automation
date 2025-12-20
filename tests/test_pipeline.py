#!/usr/bin/env python3
"""
Test script - creates a sample manga video without uploading

Usage:
    python tests/test_pipeline.py              # Full pipeline test
    python tests/test_pipeline.py --components # Test individual components
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.manga_recap import MangaRecapPipeline
from tests.utils import create_test_run_dir


async def test_full_pipeline(max_pages: int = 10):
    """Test the complete pipeline with a real manga - creates actual video"""
    # Create unique output directory for this test run
    output_dir = create_test_run_dir("pipeline")

    print("=" * 60)
    print("MANGA VIDEO TEST")
    print(f"Output: {output_dir}")
    print("=" * 60)

    pipeline = MangaRecapPipeline(output_dir=output_dir)

    # Use Chainsaw Man - we know it has chapters available
    manga_title = "Chainsaw Man"

    print(f"\n[1/7] Searching for '{manga_title}'...")
    results = await pipeline.search_manga(manga_title)

    if not results:
        print("ERROR: No manga found")
        return False

    manga = results[0]
    print(f"  Found: {manga['title']} ({manga['status']})")
    print(f"  Genres: {', '.join(manga.get('genres', []))}")

    print(f"\n[2/7] Getting manga context (cached if available)...")
    context = await pipeline.get_manga_context(manga)
    print(f"  Got context ({len(context.get('description', ''))} chars)")

    print(f"\n[3/7] Getting chapters...")
    chapters = await pipeline.get_available_chapters(manga["id"])

    if not chapters:
        print("ERROR: No chapters available")
        return False

    # Use first chapter with pages
    chapter = chapters[0]
    print(f"  Using chapter {chapter['chapter']}: {chapter['pages']} pages")

    print(f"\n[4/7] Downloading pages...")
    pages = await pipeline.download_chapter(chapter["id"])

    if not pages:
        print("ERROR: Failed to download pages")
        return False

    # Limit pages for testing
    test_pages = pages[:max_pages]
    print(f"  Downloaded {len(pages)} pages, using {len(test_pages)} for test")

    # Build manga context for narration
    manga_context = {
        "title": context["title"],
        "description": context.get("description", ""),
        "genres": context.get("genres", []),
        "chapter_number": chapter["chapter"]
    }

    # Get previous chapter summaries for continuity
    previous_summaries = pipeline.get_previous_chapter_summaries(manga["id"], chapter["chapter"])
    if previous_summaries:
        print(f"  Using context from {len(previous_summaries.splitlines())-1} previous chapter(s)")

    print(f"\n[5/7] Analyzing pages with AI (skipping meta pages)...")
    analysis = await pipeline.ai.analyze_chapter(
        test_pages,
        manga_context=manga_context,
        previous_summaries=previous_summaries
    )
    print(f"  Story pages: {analysis['total_pages']}")
    print(f"  Mood: {analysis['dominant_mood']}")
    print(f"  Duration: {analysis['total_duration']:.1f}s")

    # Save analysis results for debugging
    import json
    analysis_file = output_dir / "analysis.json"
    with open(analysis_file, "w") as f:
        json.dump(analysis, f, indent=2)
    print(f"  Analysis saved to: {analysis_file}")

    # Save chapter data for future context
    print(f"  Saving chapter summary to cache...")
    await pipeline.save_chapter_data(manga["id"], chapter["chapter"], analysis, manga["title"])

    print(f"\n[6/7] Getting background music...")
    music = await pipeline.get_music(analysis["dominant_mood"])
    if music:
        print(f"  Music: {music.name}")
    else:
        print("  No music (video will be silent)")

    print(f"\n[7/7] Building video...")
    video_path = pipeline.video.build_manga_video(
        pages_data=analysis["pages"],
        music_path=music,
        output_name="manga_video.mp4"
    )

    if video_path and video_path.exists():
        size_mb = video_path.stat().st_size / (1024 * 1024)
        print(f"\n" + "=" * 60)
        print(f"SUCCESS!")
        print(f"Video: {video_path}")
        print(f"Size: {size_mb:.2f} MB")
        print(f"Duration: ~{analysis['total_duration']:.0f}s")
        print("=" * 60)
        return True
    else:
        print("ERROR: Video creation failed")
        return False


async def test_components():
    """Test individual components"""
    print("Testing individual components...\n")

    # Test MangaDex
    print("[MangaDex] Testing search...")
    from core.mangadex import MangaDexClient
    mangadex = MangaDexClient()
    results = await mangadex.search_manga("Berserk", limit=3)
    print(f"  Found {len(results)} results")
    for r in results:
        print(f"    - {r['title']}")

    # Test OpenRouter
    print("\n[OpenRouter] Testing text generation...")
    from core.openrouter import OpenRouterClient
    ai = OpenRouterClient()
    response = await ai.generate_text("Say 'test successful' in 3 words")
    print(f"  Response: {response[:50]}...")

    # Test Freesound
    print("\n[Freesound] Testing music search...")
    from core.music import MusicFetcher
    music = MusicFetcher()
    if music.api_key:
        results = await music.search_freesound("ambient", min_duration=30, max_duration=120)
        print(f"  Found {len(results)} tracks")
        for r in results[:3]:
            print(f"    - {r['name']} ({r['duration']:.1f}s)")
    else:
        print("  Skipped (no API key)")

    print("\nAll component tests passed!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test manga video pipeline")
    parser.add_argument("--components", action="store_true",
                        help="Test individual components only")
    parser.add_argument("--pages", type=int, default=10,
                        help="Number of pages to process (default: 10)")
    args = parser.parse_args()

    if args.components:
        asyncio.run(test_components())
    else:
        success = asyncio.run(test_full_pipeline(max_pages=args.pages))
        sys.exit(0 if success else 1)
