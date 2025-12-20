"""
OpenRouter API client for vision and text generation
"""
import httpx
import base64
import json
import asyncio
from pathlib import Path
from typing import Optional
import sys
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import OPENROUTER_API_KEY, OPENROUTER_API_BASE, VISION_MODEL

MAX_RETRIES = 3
RETRY_DELAY = 10  # seconds between retries for rate limits


class OpenRouterClient:
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.api_base = OPENROUTER_API_BASE
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _encode_image(self, image_path: Path) -> str:
        """Encode image to base64"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _get_mime_type(self, image_path: Path) -> str:
        """Get MIME type from file extension"""
        ext = image_path.suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp"
        }
        return mime_types.get(ext, "image/jpeg")

    async def analyze_image(
        self,
        image_path: Path,
        prompt: str,
        model: Optional[str] = None
    ) -> str:
        """Analyze a single image with vision model"""
        model = model or VISION_MODEL
        image_data = self._encode_image(image_path)
        mime_type = self._get_mime_type(image_path)

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}"
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            "max_tokens": 1000
        }

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(
                        f"{self.api_base}/chat/completions",
                        headers=self.headers,
                        json=payload
                    )
                    if response.status_code == 429:
                        wait_time = RETRY_DELAY * (attempt + 1)
                        print(f"    Rate limited, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    response.raise_for_status()
                    result = response.json()
                    return result["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY * (attempt + 1)
                    print(f"    Rate limited, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise
        raise Exception("Max retries exceeded")

    async def is_story_page(self, image_path: Path, model: str = None) -> bool:
        """Check if a page is actual story content vs meta content (cover, credits, etc.)"""
        prompt = """Is this manga page actual STORY CONTENT or META CONTENT?

META CONTENT includes:
- Magazine covers (Weekly Shonen Jump, etc.)
- Title/credits pages with translator info
- "Support official release" disclaimers
- Author notes or announcements
- Chapter title pages with no story panels

STORY CONTENT includes:
- Actual manga panels with characters and action
- Dialogue and story progression
- Even if it's a dramatic single-panel page

Respond with ONLY one word: "story" or "meta"
"""
        response = await self.analyze_image(image_path, prompt, model=model)
        return "story" in response.lower()

    async def find_story_start(self, page_paths: list[Path], model: str = None, max_check: int = 5) -> int:
        """Find the index where actual story content begins.

        Scans the first few pages to skip meta content (covers, credits, etc.)

        Returns:
            Index of first story page (0-based)
        """
        model = model or VISION_MODEL
        pages_to_check = min(len(page_paths), max_check)

        print(f"  Scanning first {pages_to_check} pages to find story start...")

        for i in range(pages_to_check):
            is_story = await self.is_story_page(page_paths[i], model=model)
            page_type = "STORY" if is_story else "meta"
            print(f"    Page {i+1}: {page_type}")

            if is_story:
                return i

        # If no story page found in first max_check pages, start from 0
        print(f"    No clear story start found, starting from page 1")
        return 0

    async def analyze_manga_page(self, image_path: Path, model: str = None) -> dict:
        """Analyze a manga page - get basic info for context building"""
        prompt = """Analyze this manga page. Provide JSON with:
{
  "description": "What happens on this page? Include specific dialogue, numbers/amounts mentioned, and key details (2-3 sentences). Be specific - don't say 'sold organs', say which organs.",
  "mood": "emotional tone (tense, comedic, sad, action, dramatic, peaceful)",
  "panel_count": number of panels,
  "is_action_heavy": true/false
}

Respond ONLY with valid JSON."""

        response = await self.analyze_image(image_path, prompt, model=model)
        return self._parse_json_response(response, {
            "description": "A manga page",
            "mood": "neutral",
            "panel_count": 1,
            "is_action_heavy": False
        })

    def _parse_json_response(self, response: str, default: dict) -> dict:
        """Parse JSON from AI response with fallback"""
        try:
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            return json.loads(response.strip())
        except json.JSONDecodeError:
            return default

    async def analyze_chapter(
        self,
        page_paths: list[Path],
        manga_context: dict = None,
        model: str = None,
        skip_meta_pages: bool = True,
        previous_summaries: str = ""
    ) -> dict:
        """Analyze all pages and generate narration for each.

        Two-pass approach:
        1. First pass: Get brief description from each page
        2. Second pass: Generate chapter-aware narration for each page

        manga_context: {
            "title": str,
            "ai_background": str,
            "genres": list[str],
            "chapter_number": str
        }
        model: Override model for both vision and text generation
        skip_meta_pages: If True, detect and skip cover/credits pages
        previous_summaries: Formatted string of previous chapter summaries
        """
        model = model or VISION_MODEL

        # Find where story actually starts (skip covers, credits, etc.)
        start_index = 0
        if skip_meta_pages and len(page_paths) > 1:
            start_index = await self.find_story_start(page_paths, model=model)
            if start_index > 0:
                print(f"  Skipping {start_index} meta page(s), starting from page {start_index + 1}")

        story_pages = page_paths[start_index:]
        print(f"Analyzing {len(story_pages)} story pages with {model}...")

        # Pass 1: Get basic info from each page
        pages_data = []
        for i, page_path in enumerate(story_pages):
            print(f"  [1/2] Scanning page {i+1}/{len(story_pages)}...")
            page_info = await self.analyze_manga_page(page_path, model=model)
            page_info["page_number"] = i + 1
            page_info["original_page_number"] = start_index + i + 1
            page_info["file_path"] = str(page_path)
            pages_data.append(page_info)

        # Build chapter context summary
        chapter_context = "\n".join([
            f"Page {p['page_number']}: {p.get('description', 'Unknown')}"
            for p in pages_data
        ])

        # Pass 2: Generate narration for each page with chapter context
        print(f"  [2/2] Generating narration...")

        # Build manga context header
        manga_info = ""
        if manga_context:
            manga_info = f"""MANGA INFO:
Title: {manga_context.get('title', 'Unknown')}
Chapter: {manga_context.get('chapter_number', '1')}
Genres: {', '.join(manga_context.get('genres', []))}
Description: {manga_context.get('description', 'No description available')}
"""

        # Add previous chapter summaries if available
        if previous_summaries:
            manga_info += f"\n{previous_summaries}\n"

        narration_prompt = f"""{manga_info}
You are writing narration for a Chapter {manga_context.get('chapter_number', '1')} video recap. Viewers will see each manga page while hearing your narration.

Here's what happens on each page:
{chapter_context}

Write narration for each page (1-2 sentences, max 25 words).

Your narration should:
- Include the SPECIFIC details that make each page memorable (exact amounts, specific actions, what was said)
- Use character names from the description - never "a man" or "the character"
- Keep shocking or important details - don't generalize them away
- Match the tone of what's shown

Respond with JSON array:
[
  {{"page": 1, "narration": "...", "duration": 4}},
  {{"page": 2, "narration": "...", "duration": 4}},
  ...
]

Duration: 3-6 seconds based on content complexity.
Respond ONLY with JSON."""

        # Scale tokens based on number of pages (need ~100 tokens per page for narration)
        tokens_needed = max(2000, 100 * len(pages_data))
        narration_response = await self.generate_text(narration_prompt, model=model, max_tokens=tokens_needed)
        narrations = self._parse_json_response(narration_response, [])

        print(f"  Narration response: {len(narrations)} pages parsed (expected {len(pages_data)})")

        # Merge narrations into pages_data
        narration_map = {n["page"]: n for n in narrations} if isinstance(narrations, list) else {}

        for page in pages_data:
            page_num = page["page_number"]
            if page_num in narration_map:
                page["narration"] = narration_map[page_num].get("narration", "")
                page["suggested_duration"] = narration_map[page_num].get("duration", 4)
            else:
                page["narration"] = page.get("description", "")
                page["suggested_duration"] = 4

        # Calculate stats
        moods = [p.get("mood", "unknown") for p in pages_data]
        action_pages = sum(1 for p in pages_data if p.get("is_action_heavy", False))

        return {
            "pages": pages_data,
            "total_pages": len(page_paths),
            "dominant_mood": max(set(moods), key=moods.count) if moods else "unknown",
            "action_percentage": (action_pages / len(page_paths)) * 100 if page_paths else 0,
            "total_duration": sum(p.get("suggested_duration", 4) for p in pages_data)
        }

    async def generate_text(
        self,
        prompt: str,
        model: str = None,
        max_tokens: int = 1000
    ) -> str:
        """Generate text with a language model (with retry for rate limits)"""
        model = model or VISION_MODEL
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens
        }

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(
                        f"{self.api_base}/chat/completions",
                        headers=self.headers,
                        json=payload
                    )
                    if response.status_code == 429:
                        wait_time = RETRY_DELAY * (attempt + 1)
                        print(f"    Rate limited, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    response.raise_for_status()
                    result = response.json()
                    return result["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY * (attempt + 1)
                    print(f"    Rate limited, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise
        raise Exception("Max retries exceeded")


# Quick test
if __name__ == "__main__":
    import asyncio

    async def test():
        client = OpenRouterClient()

        # Test text generation
        print("Testing text generation...")
        response = await client.generate_text("Say hello in 5 words or less")
        print(f"Response: {response}")

    asyncio.run(test())
