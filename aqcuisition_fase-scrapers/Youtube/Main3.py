from youtube_api import get_youtube_client
from video_scraper import get_video_data
from search_crawler import search_videos
from keyword_config import MUST_KEYWORDS, SHOULD_KEYWORDS

from datetime import datetime, timezone
import argparse
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
# LIGHT SCRAPE (collect, then sort + write)
# =====================
# Sorteerprioriteit: lijst met velden in aflopende belang (hoogste eerst).
# Standaard: eerst likes, dan views, dan comment_count. Alle velden aflopend.
# DEFAULT_SORT_PRIORITY = ["likes", "views", "comment_count"]

#def parse_args():
#    p = argparse.ArgumentParser(description="Scrape YouTube metadata and write sorted dataset")
#    p.add_argument(
#        "--sort",
#        "-s",
#        default=",".join(DEFAULT_SORT_PRIORITY),
#        help=("Comma-separated sort priority (highest first). "
#              "Example: --sort likes,views,comment_count")
#    )
#    p.add_argument(
#        "--preset",
#        "-p",
#        choices=["engagement"],
#        help=("Use a named preset for sort priority. Available: 'engagement'"
#              " (maps to likes, comment_count, views)")
#    )
#    return p.parse_args()
#
#
#args = parse_args()
#
## Handle preset override
#if getattr(args, "preset", None):
#    if args.preset == "engagement":
#        # engagement: focus on likes and comments first, then views
#        SORT_PRIORITY = ["likes", "comment_count", "views"]
#else:
#    SORT_PRIORITY = [s.strip() for s in args.sort.split(",") if s.strip()]
#
#print(f"[+] Sorteerprioriteit ingesteld: {SORT_PRIORITY}")
#
#collected = []


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

            "views": data.get("views", 0),
            "likes": data.get("likes", 0),
            "comment_count": data.get("comment_count", 0),
            "duration_seconds": data.get("duration_seconds", 0),

            "keyword_relevance": relevance
        }

        # If the video scraper provides dislikes (third-party), include it
        if "dislikes" in data:
            light_item["dislikes"] = data.get("dislikes", 0)

        collected.append(light_item)

        print(f"    [OK] Verzameld (score={relevance['score']})")
        time.sleep(SLEEP_SECONDS)

    except Exception as e:
        print(f"    [ERROR] Fout bij video {video_id}: {e}")

# Sorteer de verzamelde items op de opgegeven prioriteit (aflopend per veld)
def sort_items(items, priority):
    def key_fn(it):
        return tuple(-int(it.get(f, 0) or 0) for f in priority)
    return sorted(items, key=key_fn)

sorted_items = sort_items(collected, SORT_PRIORITY)

# Schrijf resultaat naar dataset (overschrijf bestaande)
with open(DATASET_PATH, "w", encoding="utf-8") as f:
    for item in sorted_items:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

print(f"[+] Geschreven {len(sorted_items)} items naar {DATASET_PATH}")
