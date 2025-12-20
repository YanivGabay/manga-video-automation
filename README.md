# Manga Video Automation

Automatically generate video recaps of manga chapters with AI-powered narration, Ken Burns effects, and styled subtitles.

## Features

- **MangaDex Integration** - Fetch manga metadata and chapter pages directly from MangaDex API
- **AI Narration** - Uses Gemini 2.5 Flash (via OpenRouter) to analyze pages and generate contextual narration
- **Ken Burns Effects** - Gentle zoom animations without cropping (letterbox/pillarbox padding)
- **Styled Subtitles** - ASS format subtitles with semi-transparent background boxes
- **Background Music** - Mood-matched music from Freesound
- **Smart Caching** - Caches manga context and chapter summaries for continuity
- **Meta Page Detection** - Automatically skips cover pages and credits

## How It Works

```
1. Search manga on MangaDex
2. Download chapter pages
3. Skip meta pages (covers, credits)
4. AI analyzes each page → generates descriptions
5. AI generates short narration from descriptions
6. FFmpeg builds video with Ken Burns effects
7. Add subtitles and background music
8. Save chapter summary for future context
```

## Installation

```bash
# Clone the repo
git clone https://github.com/YanivGabay/MangaVideoAutomation.git
cd MangaVideoAutomation

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy env example and add your API keys
cp env.example .env
```

## Configuration

Create a `.env` file with:

```env
OPENROUTER_API_KEY=your_openrouter_api_key
FREESOUND_API_KEY=your_freesound_api_key  # Optional, for background music
```

Get your API keys:
- [OpenRouter](https://openrouter.ai/) - For AI vision/text models
- [Freesound](https://freesound.org/apiv2/apply) - For background music (optional)

## Usage

### Run the test pipeline

```bash
# Test with first 10 pages
python tests/test_pipeline.py

# Test full chapter
python tests/test_pipeline.py --pages 100
```

### Use in code

```python
import asyncio
from pipeline.manga_recap import MangaRecapPipeline

async def main():
    pipeline = MangaRecapPipeline()

    # Search for manga
    results = await pipeline.search_manga("Chainsaw Man")
    manga = results[0]

    # Get context (cached after first run)
    context = await pipeline.get_manga_context(manga)

    # Get chapters
    chapters = await pipeline.get_available_chapters(manga["id"])

    # Download and process
    pages = await pipeline.download_chapter(chapters[0]["id"])
    analysis = await pipeline.ai.analyze_chapter(pages, manga_context=context)

    # Build video
    video_path = pipeline.video.build_manga_video(
        pages_data=analysis["pages"],
        output_name="chapter_recap.mp4"
    )

asyncio.run(main())
```

## Project Structure

```
MangaVideoAutomation/
├── config/
│   └── settings.py      # Configuration and env loading
├── core/
│   ├── cache.py         # Manga context and chapter caching
│   ├── effects.py       # Ken Burns and subtitle effects
│   ├── mangadex.py      # MangaDex API client
│   ├── music.py         # Freesound music fetcher
│   ├── openrouter.py    # AI analysis and narration
│   └── video.py         # FFmpeg video building
├── pipeline/
│   └── manga_recap.py   # Main pipeline orchestrator
├── tests/
│   ├── test_pipeline.py # Full pipeline test
│   ├── test_narration.py# Narration-only test
│   └── utils.py         # Test utilities
├── .env                 # Your API keys (not committed)
├── env.example          # Example env file
├── requirements.txt     # Python dependencies
└── run.py              # CLI entry point
```

## Requirements

- Python 3.10+
- FFmpeg (must be installed and in PATH)

## License

MIT
