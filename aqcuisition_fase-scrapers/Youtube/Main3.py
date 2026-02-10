from youtube_api import get_youtube_client
from video_scraper import get_video_data
from search_crawler import search_videos
from keyword_config import MUST_KEYWORDS, SHOULD_KEYWORDS

from datetime import datetime, timezone
from googleapiclient.errors import HttpError

import json
import os
import time
import sys

# =====================
# CONFIG
# =====================

TIME_SLICES = [
    (
        "2025-01-20T00:00:00Z",
        "2026-01-20T23:59:59Z"
    )
]

SEARCH_QUERIES = [
    "ICE",
    "immigration enforcement",
    "immigration raid",
    "ICE shooting",
    "border patrol operation",
    "US immigration police",
    "deportation raid",
    "shooting border patrol",
    "detention center",
    "ICE arrest",
    "ICE protest",
]

SLEEP_BETWEEN_SEARCH_PAGES = 0.5
SLEEP_BETWEEN_VIDEOS = 0.5

BASE_DIR = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DATASET_PATH = os.path.join(OUTPUT_DIR, "yt_results.jsonl")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# =====================
# HELPERS
# =====================

def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()

def keyword_relevance(text, must_keywords, should_keywords):
    text = text.lower()

    must_hits = [kw for kw in must_keywords if kw in text]
    should_hits = [kw for kw in should_keywords if kw in text]

    if not must_hits:
        return None

    return {
        "must_hits": must_hits,
        "should_hits": should_hits,
        "score": len(must_hits) * 2 + len(should_hits)
    }

def handle_http_error(e):
    if e.resp.status == 403 and "quotaExceeded" in str(e):
        print("\n[!] YouTube API quota bereikt — stoppen.")
        sys.exit(0)
    else:
        raise e

# =====================
# MAIN
# =====================

youtube = get_youtube_client()
seen_video_ids = set()
written = 0

print("[+] Start discovery & scrape")
print("RUNNING FILE:", __file__)

try:
    for query in SEARCH_QUERIES:
        for published_after, published_before in TIME_SLICES:
            year = published_after[:4]
            print(f"\n[+] Zoeken naar: '{query}' ({year})")

            for video_id in search_videos(
                youtube,
                query=query,
                relevance_language="en",
                published_after=published_after,
                published_before=published_before,
                sleep_seconds=SLEEP_BETWEEN_SEARCH_PAGES
            ):
                if video_id in seen_video_ids:
                    continue

                seen_video_ids.add(video_id)

                try:
                    print(f"    [*] Metadata scrapen {video_id}")
                    data = get_video_data(video_id)

                    combined_text = f"{data.get('title','')} {data.get('description','')}"
                    relevance = keyword_relevance(
                        combined_text,
                        MUST_KEYWORDS,
                        SHOULD_KEYWORDS
                    )

                    if not relevance:
                        print("        - Niet relevant genoeg (geen must-keyword)")
                        continue

                    light_item = {
                        "video_id": video_id,
                        "video_url": f"https://www.youtube.com/watch?v={video_id}",
                        "scraped_at": utc_now_iso(),

                        "title": data.get("title"),
                        "description": data.get("description"),
                        "channel_title": data.get("channel_title"),
                        "published_at": data.get("published_at"),

                        "views": data.get("views", 0),
                        "likes": data.get("likes", 0),
                        "comment_count": data.get("comment_count", 0),
                        "duration_seconds": data.get("duration_seconds", 0),

                        "keyword_relevance": relevance
                    }

                    if "dislikes" in data:
                        light_item["dislikes"] = data.get("dislikes", 0)

                    with open(DATASET_PATH, "a", encoding="utf-8") as f:
                        f.write(json.dumps(light_item, ensure_ascii=False) + "\n")

                    written += 1

                    print(
                        f"        ✔ Opgeslagen #{written} "
                        f"(score={relevance['score']}, views={light_item['views']})"
                    )

                    time.sleep(SLEEP_BETWEEN_VIDEOS)

                except HttpError as e:
                    handle_http_error(e)

                except Exception as e:
                    print(f"        [ERROR] {e}")

except KeyboardInterrupt:
    print("\n[!] Handmatig gestopt door gebruiker (Ctrl+C)")

print(f"[+] Crawler beëindigd — totaal opgeslagen: {written}")
