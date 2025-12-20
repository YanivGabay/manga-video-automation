#!/usr/bin/env python3
"""
Debug script - analyzes chapter and outputs narration for review
Does NOT create video, just shows AI analysis results

Usage:
    python tests/test_narration.py                # Default: gemini, 10 pages
    python tests/test_narration.py --model gemini # Use Gemini 2.5 Flash
    python tests/test_narration.py --model gpt4o  # Use GPT-4o-mini
    python tests/test_narration.py --pages 20     # Analyze 20 pages
"""
import asyncio
import sys
import json
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.manga_recap import MangaRecapPipeline
from tests.utils import create_test_run_dir

# Model mapping
MODELS = {
    "gpt4o": "openai/gpt-4o-mini",
    "gemini": "google/gemini-2.5-flash"
}


async def test_narration(max_pages: int = 10, model_key: str = "gemini"):
    """Analyze a chapter and output narration for review"""
    model = MODELS.get(model_key, MODELS["gemini"])

    # Create unique output directory for this test run
    output_dir = create_test_run_dir(f"narration_{model_key}")

    print("=" * 60)
    print(f"NARRATION DEBUG TEST - {model_key.upper()}")
    print(f"Model: {model}")
    print(f"Output: {output_dir}")
    print("=" * 60)

    pipeline = MangaRecapPipeline(output_dir=output_dir)

    # Use Chainsaw Man
    manga_title = "Chainsaw Man"

    print(f"\n[1/5] Searching for '{manga_title}'...")
    results = await pipeline.search_manga(manga_title)

    if not results:
        print("ERROR: No manga found")
        return

    manga = results[0]
    print(f"  Title: {manga['title']}")
    print(f"  Status: {manga['status']}")
    print(f"  Genres: {', '.join(manga.get('genres', []))}")

    # Get enhanced manga info from AI
    print(f"\n[2/5] Getting manga background from AI...")
    manga_info_prompt = f"""Give me a brief background on the manga "{manga['title']}".
Include:
- Main character names and brief descriptions
- Basic premise/plot setup (first few chapters)
- Tone and style

Keep it concise (150 words max). This will help narrate chapter recaps.
Respond in plain text, not JSON."""

    ai_background = await pipeline.ai.generate_text(manga_info_prompt, model=model, max_tokens=500)
    print(f"  AI Background:\n{ai_background[:300]}...")

    print(f"\n[3/5] Getting chapters...")
    chapters = await pipeline.get_available_chapters(manga["id"])

    if not chapters:
        print("ERROR: No chapters available")
        return

    chapter = chapters[0]
    print(f"  Chapter {chapter['chapter']}: {chapter['pages']} pages")

    print(f"\n[4/5] Downloading pages...")
    pages = await pipeline.download_chapter(chapter["id"])

    if not pages:
        print("ERROR: Failed to download pages")
        return

    # Limit pages for testing
    test_pages = pages[:max_pages]
    print(f"  Downloaded {len(pages)} pages, using {len(test_pages)} for test")

    # Build manga context with AI-enhanced description
    manga_context = {
        "title": manga["title"],
        "description": ai_background,  # Use AI background instead of MangaDex description
        "genres": manga.get("genres", []),
        "chapter_number": chapter["chapter"]
    }

    print(f"\n[5/5] Analyzing with AI (model: {model_key})...")
    analysis = await pipeline.ai.analyze_chapter(test_pages, manga_context, model=model)

    # Output results for review
    print("\n" + "=" * 60)
    print("NARRATION RESULTS - Review each page")
    print("=" * 60)

    for page in analysis["pages"]:
        page_num = page["page_number"]
        file_path = Path(page["file_path"])
        description = page.get("description", "N/A")
        narration = page.get("narration", "N/A")
        mood = page.get("mood", "N/A")
        duration = page.get("suggested_duration", 4)

        print(f"\n--- Page {page_num} ---")
        print(f"File: {file_path.name}")
        print(f"Mood: {mood}")
        print(f"Duration: {duration}s")
        print(f"AI Description: {description}")
        print(f"Narration: {narration}")

    # Save full results to JSON for detailed review
    output_file = output_dir / "results.json"
    with open(output_file, "w") as f:
        json.dump({
            "model": model,
            "manga": manga_context,
            "pages": analysis["pages"],
            "stats": {
                "total_pages": analysis["total_pages"],
                "dominant_mood": analysis["dominant_mood"],
                "total_duration": analysis["total_duration"]
            }
        }, f, indent=2)

    print(f"\n" + "=" * 60)
    print(f"Model: {model_key} ({model})")
    print(f"Full results saved to: {output_file}")
    print(f"Total duration: {analysis['total_duration']:.1f}s")
    print(f"Dominant mood: {analysis['dominant_mood']}")
    print("=" * 60)

    # Print page paths so user can view images
    print(f"\nPage image paths (open to compare with narration):")
    for page in analysis["pages"][:5]:
        print(f"  Page {page['page_number']}: {page['file_path']}")

    return output_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test narration generation")
    parser.add_argument("--model", choices=["gpt4o", "gemini"], default="gemini",
                        help="Model to use: gemini (default) or gpt4o")
    parser.add_argument("--pages", type=int, default=10,
                        help="Number of pages to analyze (default: 10)")
    args = parser.parse_args()

    asyncio.run(test_narration(args.pages, args.model))
