# imports
from atproto import Client
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
import os
import time
import gzip
import json

# logt in met bluesky account, gegevens in .env
def login(client):
    load_dotenv()

    bs_user = os.getenv('USER')
    bs_pass = os.getenv('PASS')

    client = Client()

    with open('aqcuisition_fase-scrapers\\Bluesky\\session.txt') as f:
        session_string = f.read()

    # als er een session string doc aanwezig is, gebruik deze. anders: genereer deze
    if session_string:
        profile = client.login(session_string=session_string)
    else:
        profile = client.login(bs_user, bs_pass)
        session_string = client.export_session_string()
        with open('aqcuisition_fase-scrapers\\Bluesky\\session.txt', 'w') as f:
            f.write(session_string)

    print(f"Logged into {profile.display_name} (@{profile.handle})")


    return client

# verzamelt posts via api
def gather_posts(client):
    post_number = 0

    # inlezen zoektermen
    with open("aqcuisition_fase-scrapers\\termen_2.csv",'r') as f:
        content = f.read()

    queries = content.split(',')

    # per zoekterm een aparte query, met 25 posts opgehaald per keer
    for query in queries:
        cursor = None
        last = "0"
        params={
        'q': 'ice '+ query + ' since:2025-01-20 until:2026-01-20', 
        'lang':'en',
        'sort': 'top',
        'limit': 25
        }

        # deze posts worden 500 keer opgehaald, mbv cursor
        for loop in range(500):
            time.sleep(0.25)
            if cursor:
                params["cursor"] = cursor
            else:
                cursor = last
                params["cursor"] = cursor
            last = str(int(last) + 25)

            try:
                response = client.app.bsky.feed.search_posts(params)
                post_number = post_number + 1
                print(f"Loop {loop} started, {query}, {post_number}")
            except Exception as e:
                post_number = post_number + 1
                print(f"{post_number} not fetched, {e}")

            if not response.posts:
                print(f'No results, {query}')
                break

            cursor = response.cursor

            # posts worden weggeschreven
            export_posts(sort_posts(response.posts))

        response = None
        print(f"Loop {loop} ends with")
        print(params["cursor"],cursor,last)
        print("\n")
        time.sleep(3)

# zet posts om tot dictionary
def sort_posts(posts):
    saved_posts = []
    if posts:
        for post in posts:
            record = {
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
            saved_posts.append(record)
            print(record['posted_at'])
    return saved_posts

# schrijft posts weg naar locatie
def export_posts(posts):

    data_dir = Path("aqcuisition_fase-scrapers\Bluesky\Data")
    data_dir.mkdir(parents=True, exist_ok=True)
    post_file = data_dir / "bs-posts_2.jsonl.gz"

    # in jsonl.gz format
    for post in posts:
        line = json.dumps(post, ensure_ascii=False) + "\n"

        with gzip.open(post_file, "ab") as f:
            f.write(line.encode("utf-8")) 

# main
if __name__ == '__main__':
    client = Client()
    logged_in_client = login(client)
    posts = gather_posts(logged_in_client)
    sort_posts(posts)
