from video_scraper import get_video_data
from youtube_api import get_youtube_client
import comment_scraper
import os
import json
import re

VIDEO_ID = "DaZ2oCC6gXw"

youtube = get_youtube_client()

data = get_video_data(VIDEO_ID)
data["top_comments"] = comment_scraper.get_top_comments(youtube, VIDEO_ID, max_comments=200)

# build a safe filename from the first few words of the video title
title = (data.get("title") or "").strip()
words = title.split()
snippet = " ".join(words[:4]) if words else ""
# keep only ASCII letters/numbers and spaces, then convert spaces to underscores
slug = re.sub(r"[^A-Za-z0-9 ]+", "", snippet).strip()
slug = slug.replace(" ", "_").lower()
if not slug:
    slug = VIDEO_ID
slug = slug[:60]

output_dir = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(output_dir, exist_ok=True)
output_filename = f"{slug}.json"
output_path = os.path.join(output_dir, output_filename)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Geschreven: {output_path}")
print(f"{len(data['top_comments'])} top comments opgeslagen voor video {data.get('video_id')}")