#!/usr/bin/env python3
"""
Manga Video Automation - Main Entry Point

Usage:
    python run.py --manga "Berserk" --chapter 1
    python run.py --manga "Chainsaw Man"  # Uses first available chapter
    python run.py --search "One Piece"    # Just search, don't build video
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.manga_recap import MangaRecapPipeline
from config.settings import OUTPUT_DIR, OPENROUTER_API_KEY


def check_environment():
    """Check required environment variables"""
    if not OPENROUTER_API_KEY:
        print("ERROR: OPENROUTER_API_KEY not set")
        print("Please create a .env file with your API key")
        print("See env.example for reference")
        return False
    return True


async def search_only(title: str):
    """Just search for manga without building video"""
    pipeline = MangaRecapPipeline()

    print(f"Searching for '{title}'...\n")
    results = await pipeline.search_manga(title)

    if not results:
        print("No results found")
        return

    print("Results:")
    print("-" * 60)
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['title']}")
        print(f"   Status: {r['status']}")
        print(f"   ID: {r['id']}")

        # Get chapter count
        chapters = await pipeline.get_available_chapters(r['id'])
        print(f"   Available chapters: {len(chapters)}")
        print()


async def run_pipeline(manga_title: str, chapter: str = None):
    """Run the full pipeline"""
    pipeline = MangaRecapPipeline()

    output_name = f"{manga_title.replace(' ', '_')}_recap.mp4"
    result = await pipeline.run(
        manga_title=manga_title,
        chapter_number=chapter,
        output_name=output_name
    )

    if result:
        print(f"\nVideo saved to: {result}")
    else:
        print("\nPipeline failed")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Create manga recap videos automatically"
    )
    parser.add_argument(
        "--manga", "-m",
        type=str,
        help="Manga title to search for"
    )
    parser.add_argument(
        "--chapter", "-c",
        type=str,
        default=None,
        help="Chapter number to use (default: first available)"
    )
    parser.add_argument(
        "--search", "-s",
        type=str,
        help="Search for manga without building video"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help=f"Output directory (default: {OUTPUT_DIR})"
    )

    args = parser.parse_args()

    # Check environment
    if not check_environment():
        sys.exit(1)

    # Run appropriate command
    if args.search:
        asyncio.run(search_only(args.search))
    elif args.manga:
        asyncio.run(run_pipeline(args.manga, args.chapter))
    else:
        parser.print_help()
        print("\nExamples:")
        print('  python run.py --search "Berserk"')
        print('  python run.py --manga "Berserk" --chapter 1')
        print('  python run.py -m "Chainsaw Man"')


if __name__ == "__main__":
    main()
