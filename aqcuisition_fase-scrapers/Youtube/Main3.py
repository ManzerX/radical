from youtube_api import get_youtube_client
from video_scraper import get_video_data
from search_crawler import search_videos
from keyword_config import MUST_KEYWORDS, SHOULD_KEYWORDS

from datetime import datetime, timezone
import json
import os
import time

# =====================
# CONFIG
# =====================
SEARCH_QUERIES = [
    "ICE",
    "immigration enforcement",
    "immigration raid",
    "border patrol operation",
    "US immigration police",
    "deportation raid",
    "shooting border patrol",
    "detention center",
]

MAX_VIDEOS_PER_QUERY = 100
SLEEP_SECONDS = 1

BASE_DIR = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DATASET_PATH = os.path.join(OUTPUT_DIR, "dataset_light.jsonl")

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

# =====================
# DISCOVERY
# =====================
youtube = get_youtube_client()
all_video_ids = set()

print("[+] Start discovery")

for query in SEARCH_QUERIES:
    print(f"    Zoeken naar: {query}")
    ids = search_videos(
        youtube,
        query=query,
        max_videos=MAX_VIDEOS_PER_QUERY
    )
    all_video_ids.update(ids)

print(f"[+] {len(all_video_ids)} unieke video’s gevonden")

# =====================
# LIGHT SCRAPE
# =====================
for idx, video_id in enumerate(all_video_ids, start=1):
    try:
        print(f"[{idx}/{len(all_video_ids)}] Metadata scrapen {video_id}")

        data = get_video_data(video_id)

        combined_text = f"{data.get('title','')} {data.get('description','')}"
        relevance = keyword_relevance(
            combined_text,
            MUST_KEYWORDS,
            SHOULD_KEYWORDS
        )

        if not relevance:
            print("    - Niet relevant genoeg (geen must-keyword)")
            continue

        light_item = {
            "video_id": video_id,
            "video_url": f"https://www.youtube.com/watch?v={video_id}",
            "scraped_at": utc_now_iso(),

            "title": data["title"],
            "description": data["description"],
            "channel_title": data["channel_title"],
            "published_at": data["published_at"],

            "views": data["views"],
            "likes": data["likes"],
            "comment_count": data["comment_count"],
            "duration_seconds": data["duration_seconds"],

            "keyword_relevance": relevance
        }

        with open(DATASET_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(light_item, ensure_ascii=False) + "\n")

        print(f"    [OK] Opgeslagen (score={relevance['score']})")
        time.sleep(SLEEP_SECONDS)

    except Exception as e:
        print(f"    [ERROR] Fout bij video {video_id}: {e}")
