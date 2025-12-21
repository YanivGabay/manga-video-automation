"""
YouTube upload service
Handles OAuth authentication and video upload with metadata
"""
import os
import json
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional
import sys
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import (
    YT_CLIENT_ID,
    YT_CLIENT_SECRET,
    YT_REFRESH_TOKEN,
    CHANNEL_DEFAULT_TAGS
)


class YouTubeUploader:
    """YouTube video uploader using OAuth 2.0"""

    TOKEN_URL = "https://oauth2.googleapis.com/token"
    UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
    CAPTIONS_URL = "https://www.googleapis.com/upload/youtube/v3/captions"

    def __init__(self):
        self.client_id = YT_CLIENT_ID
        self.client_secret = YT_CLIENT_SECRET
        self.refresh_token = YT_REFRESH_TOKEN
        self._access_token = None

    def _get_access_token(self) -> str:
        """Exchange refresh token for access token"""
        if self._access_token:
            return self._access_token

        if not all([self.client_id, self.client_secret, self.refresh_token]):
            raise ValueError(
                "Missing YouTube OAuth credentials. "
                "Set YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN in .env"
            )

        response = requests.post(self.TOKEN_URL, data={
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token,
            'grant_type': 'refresh_token'
        })

        if response.status_code != 200:
            raise Exception(f"Failed to get access token: {response.text}")

        self._access_token = response.json()['access_token']
        return self._access_token

    def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: Optional[list[str]] = None,
        category_id: str = "24",  # Entertainment
        privacy: str = "public",
        is_short: bool = False
    ) -> dict:
        """
        Upload video to YouTube.

        Args:
            video_path: Path to the video file
            title: Video title
            description: Video description
            tags: List of tags (defaults to channel tags + manga tags)
            category_id: YouTube category (24=Entertainment, 28=Science&Tech)
            privacy: public, private, or unlisted
            is_short: If True, adds #Shorts to title

        Returns:
            dict with video_id, url, upload_date
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        access_token = self._get_access_token()

        # Prepare title
        if is_short and "#Shorts" not in title:
            title = f"{title} #Shorts"

        # Prepare tags
        default_tags = CHANNEL_DEFAULT_TAGS.split(',') if CHANNEL_DEFAULT_TAGS else []
        manga_tags = ['manga', 'anime', 'recap', 'narration']
        all_tags = list(set(default_tags + manga_tags + (tags or [])))

        # Video metadata
        metadata = {
            'snippet': {
                'title': title[:100],  # YouTube limit
                'description': description[:5000],  # YouTube limit
                'tags': all_tags[:500],  # YouTube limit
                'categoryId': category_id,
                'defaultLanguage': 'en'
            },
            'status': {
                'privacyStatus': privacy,
                'selfDeclaredMadeForKids': False
            }
        }

        print(f"Uploading: {title}")

        # Step 1: Initiate resumable upload
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        response = requests.post(
            self.UPLOAD_URL,
            headers=headers,
            params={'part': 'snippet,status', 'uploadType': 'resumable'},
            json=metadata
        )

        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to initiate upload: {response.status_code} - {response.text}")

        upload_location = response.headers.get('Location')
        if not upload_location:
            raise Exception("No upload location received")

        # Step 2: Upload video file
        print("Uploading video file...")
        file_size = video_path.stat().st_size

        with open(video_path, 'rb') as video_file:
            upload_response = requests.put(
                upload_location,
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Length': str(file_size),
                    'Content-Type': 'video/mp4'
                },
                data=video_file
            )

        if upload_response.status_code not in [200, 201]:
            raise Exception(f"Failed to upload video: {upload_response.status_code} - {upload_response.text}")

        video_info = upload_response.json()
        video_id = video_info['id']

        result = {
            'video_id': video_id,
            'url': f'https://youtube.com/watch?v={video_id}',
            'upload_date': datetime.utcnow().isoformat(),
            'title': title,
            'platform': 'youtube'
        }

        print(f"Upload successful!")
        print(f"Video URL: {result['url']}")

        return result

    def upload_captions(
        self,
        video_id: str,
        srt_path: Path,
        language: str = "en",
        name: str = "English"
    ) -> bool:
        """
        Upload SRT captions to a YouTube video.

        Args:
            video_id: YouTube video ID
            srt_path: Path to SRT file
            language: Language code
            name: Caption track name

        Returns:
            True if successful
        """
        srt_path = Path(srt_path)
        if not srt_path.exists():
            print(f"Caption file not found: {srt_path}")
            return False

        access_token = self._get_access_token()

        caption_metadata = {
            'snippet': {
                'videoId': video_id,
                'language': language,
                'name': name,
                'isDraft': False
            }
        }

        # Create multipart request
        boundary = '-------314159265358979323846'
        caption_content = srt_path.read_text(encoding='utf-8')

        multipart_data = f"""--{boundary}
Content-Type: application/json; charset=UTF-8

{json.dumps(caption_metadata)}
--{boundary}
Content-Type: text/plain

{caption_content}
--{boundary}--"""

        response = requests.post(
            self.CAPTIONS_URL,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': f'multipart/related; boundary={boundary}'
            },
            params={'part': 'snippet', 'uploadType': 'multipart'},
            data=multipart_data.encode('utf-8')
        )

        if response.status_code in [200, 201]:
            print("Captions uploaded successfully!")
            return True
        else:
            print(f"Failed to upload captions: {response.status_code} - {response.text}")
            return False


# Quick test
if __name__ == "__main__":
    uploader = YouTubeUploader()
    print("YouTube uploader initialized")
    print(f"Credentials configured: {all([uploader.client_id, uploader.client_secret, uploader.refresh_token])}")
