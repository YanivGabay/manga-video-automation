"""
Tracker for managing upload state via GitHub Gist
"""
import json
import requests
from datetime import datetime
from typing import Optional
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import TRACKER_GIST_ID, GH_TOKEN


class Tracker:
    """
    Manages upload state using a GitHub Gist.

    Tracker format:
    {
        "series": [
            {
                "mangadex_id": "abc123",
                "name": "Chainsaw Man",
                "last_chapter_num": 150,
                "last_chapter_id": "xyz789",
                "last_upload": "2024-01-15T12:00:00Z"
            }
        ],
        "next_index": 0,
        "uploads": [
            {
                "manga": "Chainsaw Man",
                "chapter": 150,
                "youtube_id": "abc123",
                "uploaded_at": "2024-01-15T12:00:00Z"
            }
        ]
    }
    """

    GIST_API = "https://api.github.com/gists"

    def __init__(self, gist_id: str = None, token: str = None):
        self.gist_id = gist_id or TRACKER_GIST_ID
        self.token = token or GH_TOKEN
        self._data = None

    def _headers(self) -> dict:
        """Get headers for GitHub API"""
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def load(self) -> dict:
        """Load tracker data from gist"""
        if not self.gist_id:
            raise ValueError("No gist ID configured. Set TRACKER_GIST_ID in .env")

        response = requests.get(
            f"{self.GIST_API}/{self.gist_id}",
            headers=self._headers()
        )

        if response.status_code != 200:
            raise Exception(f"Failed to load gist: {response.status_code} - {response.text}")

        gist_data = response.json()
        files = gist_data.get("files", {})

        if "tracker.json" not in files:
            raise Exception("tracker.json not found in gist")

        content = files["tracker.json"]["content"]
        self._data = json.loads(content)
        return self._data

    def save(self) -> None:
        """Save tracker data to gist"""
        if not self._data:
            raise ValueError("No data to save. Call load() first or set data.")

        if not self.token:
            raise ValueError("No GitHub token configured. Set GH_TOKEN in .env")

        response = requests.patch(
            f"{self.GIST_API}/{self.gist_id}",
            headers=self._headers(),
            json={
                "files": {
                    "tracker.json": {
                        "content": json.dumps(self._data, indent=2)
                    }
                }
            }
        )

        if response.status_code != 200:
            raise Exception(f"Failed to save gist: {response.status_code} - {response.text}")

        print("Tracker saved to gist")

    @property
    def data(self) -> dict:
        """Get tracker data, loading if needed"""
        if self._data is None:
            self.load()
        return self._data

    def add_series(self, mangadex_id: str, name: str) -> None:
        """Add a manga series to track"""
        data = self.data

        # Check if already exists
        for series in data.get("series", []):
            if series["mangadex_id"] == mangadex_id:
                print(f"Series '{name}' already in tracker")
                return

        if "series" not in data:
            data["series"] = []

        data["series"].append({
            "mangadex_id": mangadex_id,
            "name": name,
            "last_chapter_num": 0,
            "last_chapter_id": None,
            "last_upload": None
        })

        print(f"Added series: {name}")

    def remove_series(self, mangadex_id: str) -> None:
        """Remove a manga series from tracking"""
        data = self.data
        data["series"] = [
            s for s in data.get("series", [])
            if s["mangadex_id"] != mangadex_id
        ]

    def get_next_series(self) -> Optional[dict]:
        """Get next series to process (round-robin)"""
        data = self.data
        series_list = data.get("series", [])

        if not series_list:
            return None

        next_index = data.get("next_index", 0) % len(series_list)
        return series_list[next_index]

    def advance_index(self) -> None:
        """Move to next series in round-robin"""
        data = self.data
        series_count = len(data.get("series", []))
        if series_count > 0:
            data["next_index"] = (data.get("next_index", 0) + 1) % series_count

    def record_upload(
        self,
        mangadex_id: str,
        chapter_num: int,
        chapter_id: str,
        youtube_id: str
    ) -> None:
        """Record a successful upload"""
        data = self.data
        now = datetime.utcnow().isoformat() + "Z"

        # Update series info
        for series in data.get("series", []):
            if series["mangadex_id"] == mangadex_id:
                series["last_chapter_num"] = chapter_num
                series["last_chapter_id"] = chapter_id
                series["last_upload"] = now
                manga_name = series["name"]
                break
        else:
            manga_name = "Unknown"

        # Add to uploads history
        if "uploads" not in data:
            data["uploads"] = []

        data["uploads"].append({
            "manga": manga_name,
            "chapter": chapter_num,
            "youtube_id": youtube_id,
            "uploaded_at": now
        })

        # Keep only last 100 uploads
        data["uploads"] = data["uploads"][-100:]

    def get_series_by_id(self, mangadex_id: str) -> Optional[dict]:
        """Get series info by MangaDex ID"""
        for series in self.data.get("series", []):
            if series["mangadex_id"] == mangadex_id:
                return series
        return None

    def list_series(self) -> list[dict]:
        """List all tracked series"""
        return self.data.get("series", [])


# Test
if __name__ == "__main__":
    tracker = Tracker()

    print("Loading tracker...")
    data = tracker.load()
    print(f"Current data: {json.dumps(data, indent=2)}")

    print(f"\nSeries count: {len(tracker.list_series())}")
    print(f"Next series: {tracker.get_next_series()}")
