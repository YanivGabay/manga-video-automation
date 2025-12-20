#!/usr/bin/env python3
"""
Helper script to get YouTube refresh token.
Run this once to get your refresh token, then add it to .env

Prerequisites:
1. Go to Google Cloud Console (https://console.cloud.google.com)
2. Create a project (or use existing)
3. Enable YouTube Data API v3
4. Create OAuth 2.0 credentials (Desktop app type)
5. Download or copy the Client ID and Client Secret
"""

import requests
import webbrowser
from urllib.parse import parse_qs, urlparse
import http.server
import socketserver


def get_youtube_refresh_token():
    """Get YouTube refresh token through OAuth flow"""

    print("\n" + "=" * 60)
    print("  YouTube OAuth Setup for Manga Video Automation")
    print("=" * 60)

    CLIENT_ID = input("\nEnter your YouTube Client ID: ").strip()
    CLIENT_SECRET = input("Enter your YouTube Client Secret: ").strip()

    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: Both Client ID and Client Secret are required")
        return None

    # OAuth 2.0 endpoints
    AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    # Required scopes
    SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"

    # Local server for OAuth callback
    PORT = 8080
    REDIRECT_URI = f"http://localhost:{PORT}/"

    # Build auth URL
    auth_params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'scope': SCOPES,
        'response_type': 'code',
        'access_type': 'offline',
        'prompt': 'consent'
    }

    auth_url = AUTH_URL + "?" + "&".join([f"{k}={v}" for k, v in auth_params.items()])

    print("\n" + "-" * 60)
    print("INSTRUCTIONS:")
    print("-" * 60)
    print("1. A browser window will open")
    print("2. Log in to your Google account")
    print("3. SELECT THE YOUTUBE CHANNEL for manga uploads")
    print("4. Grant the requested permissions")
    print("\nPress Enter to open browser...")
    input()

    # Start local server to capture the auth code
    auth_code = None

    class OAuthHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            query = parse_qs(urlparse(self.path).query)

            if 'code' in query:
                auth_code = query["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                    <html><body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h1>Success!</h1>
                    <p>You can close this window and return to the terminal.</p>
                    </body></html>
                """)
                print("\n✓ Authorization code received")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Error: No authorization code")

        def log_message(self, format, *args):
            pass  # Suppress server logs

    try:
        with socketserver.TCPServer(("", PORT), OAuthHandler) as httpd:
            print(f"Starting local server on port {PORT}...")
            webbrowser.open(auth_url)
            print("Waiting for authorization...")
            httpd.handle_request()
    except Exception as e:
        print(f"Error: Could not start local server: {e}")
        print("Make sure port 8080 is not in use")
        return None

    if not auth_code:
        print("Error: Failed to get authorization code")
        return None

    # Exchange code for tokens
    print("\nExchanging code for tokens...")

    response = requests.post(TOKEN_URL, data={
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': auth_code,
        'grant_type': 'authorization_code',
        'redirect_uri': REDIRECT_URI
    })

    if response.status_code != 200:
        print(f"Error: Token exchange failed: {response.text}")
        return None

    tokens = response.json()

    if 'refresh_token' not in tokens:
        print("Error: No refresh token received")
        print("Make sure you used 'prompt=consent' in the auth request")
        return None

    refresh_token = tokens['refresh_token']
    access_token = tokens['access_token']

    # Verify which channel is connected
    print("\nVerifying channel connection...")

    channel_response = requests.get(
        "https://www.googleapis.com/youtube/v3/channels",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"part": "snippet", "mine": "true"}
    )

    if channel_response.status_code == 200:
        data = channel_response.json()
        if data.get('items'):
            channel = data['items'][0]
            print(f"✓ Connected to channel: {channel['snippet']['title']}")
            print(f"  Channel ID: {channel['id']}")
    else:
        print("Warning: Could not verify channel")

    # Output the credentials
    print("\n" + "=" * 60)
    print("SUCCESS! Add these to your .env file:")
    print("=" * 60)
    print(f"\nYT_CLIENT_ID={CLIENT_ID}")
    print(f"YT_CLIENT_SECRET={CLIENT_SECRET}")
    print(f"YT_REFRESH_TOKEN={refresh_token}")
    print("\n" + "=" * 60)

    return refresh_token


if __name__ == "__main__":
    try:
        get_youtube_refresh_token()
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
    except Exception as e:
        print(f"\nError: {e}")
