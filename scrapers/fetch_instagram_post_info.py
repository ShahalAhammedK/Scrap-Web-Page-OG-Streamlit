import requests
import json
import re
from langdetect import detect, DetectorFactory

from .utils import safe_get, format_timestamp
from .api_key_manager import rapidapi_key_manager

DetectorFactory.seed = 0

RAPIDAPI_HOST = "instagram-2024-new.p.rapidapi.com"

def fetch_instagram_post_info(post_identifier):
    post_shortcode = post_identifier.strip()

    # Extract shortcode from full Instagram URL if necessary
    if post_identifier.startswith("http"):
        # Updated regex to look for /p/, /reel/, or /reels/ anywhere in the path, 
        # making it robust against URLs that include a username before the shortcode.
        match = re.search(r"/(?:p|reel|reels)\/([a-zA-Z0-9_-]+)", post_identifier)
        if match:
            post_shortcode = match.group(1)
        else:
            return {"error": f"Invalid Instagram URL or shortcode: {post_identifier}"}

    endpoint = f"https://{RAPIDAPI_HOST}/api/instagram/posts/info/{post_shortcode}/code"

    for _ in range(rapidapi_key_manager.max_key_rotations):
        try:
            headers = rapidapi_key_manager.get_headers(RAPIDAPI_HOST)
            response = requests.get(endpoint, headers=headers)
            if response.status_code == 429:
                print("Rate limit hit. Rotating key...")
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "Rate limit hit and all API keys exhausted."}
                continue
            if response.status_code in [401, 403] or "invalid api key" in response.text.lower():
                print("Authentication error. Rotating key...")
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "Unauthorized or invalid API key, all keys exhausted."}
                continue
            if response.status_code != 200:
                return {"error": f"API Error {response.status_code}: {response.text}"}

            json_data = response.json()
            break

        except Exception as e:
            print(f"Request error: {e}. Rotating key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": f"All keys failed: {str(e)}"}
            continue
    else:
        return {"error": "Failed after rotating all keys."}

    items = json_data.get("items", [])
    if not items:
        return {"error": "No items found in API response."}

    item = items[0]

    # Extract fields
    caption_text = safe_get(item, "caption.text")
    likes = safe_get(item, "like_count")
    comments = safe_get(item, "comment_count")
    shares = safe_get(item, "reshare_count", "N/A")
    views = safe_get(item, "play_count", "N/A")
    duration = safe_get(item, "video_duration", "N/A")
    created_at_unix = safe_get(item, "taken_at")
    created_at = format_timestamp(created_at_unix, include_time=True)
    username = safe_get(item, "user.username")
    full_name = safe_get(item, "user.full_name")
    shortcode = safe_get(item, "code")

    post_url = f"https://www.instagram.com/p/{shortcode}/"
    profile_url = f"https://www.instagram.com/{username}/" if username else "N/A"

    detected_caption_language = "N/A"
    if caption_text:
        try:
            detected_caption_language = detect(caption_text)
        except Exception:
            detected_caption_language = "Undetectable"

    return {
        "Caption": caption_text,
        "Likes": str(likes),
        "Comments": str(comments),
        "Shares": str(shares),
        "Video Views": str(views),
        "Video Duration (seconds)": str(duration),
        "Created At": created_at,
        "Username": username,
        "Full Name": full_name,
        "Post URL": post_url,
        "Author Profile URL": profile_url,
        "Caption Language": detected_caption_language
    }
