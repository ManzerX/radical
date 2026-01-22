from video_scraper import get_video_data
from youtube_api import get_youtube_client
import comment_scraper

ids = [
    "il5IEKQ53GI",  # current in main.py
    "dQw4w9WgXcQ"   # known other video
]

y = get_youtube_client()
for vid in ids:
    data = get_video_data(vid)
    print(vid, "->", data.get('title'))
    comments = comment_scraper.get_top_comments(y, vid, max_comments=2)
    print('  comments:', len(comments))
