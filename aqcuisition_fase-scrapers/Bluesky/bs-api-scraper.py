from atproto import Client
from dotenv import load_dotenv
from datetime import datetime, timezone
from dateutil import parser
from pathlib import Path
import os
import gzip
import json


def login(client):
    load_dotenv()

    bs_user = os.getenv('USER')
    bs_pass = os.getenv('PASS')

    client.login(bs_user, bs_pass)

    return client

def gather_posts(client):
    query = """ice raids"""

    cursor = None
    bs_posts = []

    while True:
        fetched = posts = client.app.bsky.feed.search_posts(params={'q': query, 'cursor': cursor})
        bs_posts = bs_posts + fetched.posts

        if not fetched.cursor:
            break

        cursor = fetched.cursor

    # for post in bs_posts:
    #     print(post)

    return bs_posts

def sort_posts(posts):
    saved_posts = []
    for post in posts:
            if datetime(2025,1,20,0,0,0,0,tzinfo=timezone.utc) <= parser.parse(post.record.created_at) <= datetime(2026,1,20,0,0,0,0,tzinfo=timezone.utc):
                post = {
                        'uri':post.uri,
                        'text':post.record.text,
                        'likes':post.like_count,
                        'replies':post.reply_count,
                        'reposts':post.repost_count,
                        'quotes':post.quote_count,
                        'scraped_at_local_time':datetime.now().strftime(r'%Y-%m-%d %H:%M:%S.%f'),
                        'account':post.author.handle,
                        'posted_at':post.record.created_at
                    }
                saved_posts.append(post)

    return saved_posts

def export_posts(posts):
    data_dir = Path("aqcuisition_fase-scrapers\Bluesky\Data")
    data_dir.mkdir(parents=True, exist_ok=True)
    post_file = data_dir / "bs-posts.jsonl.gz"

    for post in posts:
        line = json.dumps(post, ensure_ascii=False) + "\n"

        with gzip.open(post_file, "ab") as f:
            f.write(line.encode("utf-8")) 


if __name__ == '__main__':
    client = Client()
    logged_in_client = login(client)
    posts = gather_posts(logged_in_client)
    posts = sort_posts(posts)
    export_posts(posts)
