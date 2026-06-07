# scrapers/fetch_youtube_post_info.py

import requests
import re
from datetime import datetime
from langdetect import detect, DetectorFactory
import isodate  # New import to convert ISO 8601 durations

from .utils import safe_get
from .api_key_manager import rapidapi_key_manager

# Ensure consistent langdetect behavior
DetectorFactory.seed = 0

# Updated API configuration
RAPIDAPI_HOST_YOUTUBE = "youtube342.p.rapidapi.com"
RAPIDAPI_ENDPOINT = f"https://{RAPIDAPI_HOST_YOUTUBE}/videos"

def fetch_youtube_post_info(video_url):
    """
    Fetches video details from YouTube using RapidAPI (new endpoint with requests),
    with API key rotation, language detection, and robust error handling.
    """

    # --- Extract YouTube Video ID ---
    match = re.search(r'(?:v=|youtu\.be/|embed/|shorts/)([a-zA-Z0-9_-]{11})', video_url)
    if not match:
        return {"error": f"Could not extract video ID from URL: {video_url}"}
    video_id = match.group(1)

    # --- Prepare API Query ---
    params = {
        "part": "snippet,contentDetails,statistics",
        "id": video_id,
        "maxResults": "1"
    }

    for _ in range(rapidapi_key_manager.max_key_rotations):
        try:
            headers = rapidapi_key_manager.get_headers(RAPIDAPI_HOST_YOUTUBE)
            response = requests.get(RAPIDAPI_ENDPOINT, headers=headers, params=params)

            if response.status_code == 429:
                print("Rate limit hit. Rotating key...")
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "All API keys exhausted due to rate limits."}
                continue

            if response.status_code in [401, 403]:
                print("Authentication issue. Rotating key...")
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "All API keys exhausted or invalid for YouTube."}
                continue

            if response.status_code != 200:
                return {"error": f"YouTube API Error {response.status_code}: {response.text}"}

            data = response.json()
            items = data.get("items", [])
            if not items:
                return {"error": f"No video data found for ID: {video_id}"}

            video_data = items[0]
            snippet = video_data.get("snippet", {})
            statistics = video_data.get("statistics", {})
            content_details = video_data.get("contentDetails", {})

            # --- Extract and Format Data ---
            views = statistics.get("viewCount", "N/A")
            likes = statistics.get("likeCount", "N/A")
            comments = statistics.get("commentCount", "N/A")
            description = snippet.get("description", "")
            channel_name = snippet.get("channelTitle", "N/A")
            channel_id = snippet.get("channelId", "N/A")
            channel_url = f"https://www.youtube.com/channel/{channel_id}" if channel_id != "N/A" else "N/A"
            published_at = snippet.get("publishedAt", "N/A")

            # Convert ISO 8601 duration to seconds
            raw_duration = content_details.get("duration", "N/A")
            try:
                duration_seconds = int(isodate.parse_duration(raw_duration).total_seconds())
            except Exception:
                duration_seconds = "N/A"

            try:
                dt_object = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
                published_date = dt_object.strftime("%Y-%m-%d %H:%M:%S")
            except:
                published_date = "N/A"

            detected_lang = "N/A"
            if description.strip():
                try:
                    detected_lang = detect(description)
                except Exception:
                    detected_lang = "Undetectable"

            return {
                "Views": views,
                "Likes": likes,
                "Comments": comments,
                "Video URL": video_url,
                "Channel Name": channel_name,
                "Channel URL": channel_url,
                "Video Duration (seconds)": str(duration_seconds),
                "Published Date (UTC)": published_date,
                "Description Language": detected_lang
            }

        except requests.RequestException as e:
            print(f"HTTP error: {e}. Rotating key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": "All API keys exhausted due to HTTP errors."}
        except Exception as e:
            print(f"Unexpected error: {e}")
            if not rapidapi_key_manager.rotate_key():
                return {"error": f"All keys failed due to: {e}"}

    return {"error": "Failed after trying all API keys."}


# --- CLI / Script Mode ---
if __name__ == "__main__":
    from tabulate import tabulate

    youtube_video_urls_to_process = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",     # Regular
        "https://www.youtube.com/shorts/QXzE-0ba5vY",       # Shorts
        "https://youtu.be/oyOxX7e67qY",                     # Shortened
        "https://www.youtube.com/embed/oyOxX7e67qY",        # Embed
        "https://www.youtube.com/watch?v=invalid_id_xyz"    # Invalid
    ]

    output_headers = [
        "Views",
        "Likes",
        "Comments",
        "Video URL",
        "Channel Name",
        "Channel URL",
        "Video Duration (seconds)",   # Updated
        "Published Date (UTC)",
        "Description Language"
    ]

    results = []

    print("--- Processing YouTube Videos ---\n")
    for url in youtube_video_urls_to_process:
        print(f"Fetching info for: {url}")
        info = fetch_youtube_post_info(url)
        if "error" not in info:
            row = [info.get(h, "N/A") for h in output_headers]
            results.append(row)
            print("Success.")
        else:
            print(f"Failed: {info['error']}")
        print("-" * 40)

    if results:
        print("\n--- Results Table ---")
        print(tabulate(results, headers=output_headers, tablefmt="fancy_grid"))
    else:
        print("No data collected.")
