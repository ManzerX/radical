from atproto import Client
from dotenv import load_dotenv
from datetime import datetime, timezone
from dateutil import parser
import os
import pandas as pd


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
    saved_posts =[]

    for post in posts:
            if datetime(2025,1,20,0,0,0,0,tzinfo=timezone.utc) <= parser.parse(post.record.created_at) <= datetime(2026,1,20,0,0,0,0,tzinfo=timezone.utc):
                saved_posts.append(
                    {
                        'uri':post.uri,
                        'text':post.record.text,
                        'likes':post.like_count,
                        'replies':post.reply_count,
                        'reposts':post.repost_count,
                        'quotes':post.quote_count,
                        'scraped_at':datetime.now(),
                        'account':post.author.handle,
                        'posted_at':post.record.created_at
                    }
                )
    print(saved_posts)

if __name__ == '__main__':
    client = Client()
    logged_in_client = login(client)
    posts = gather_posts(logged_in_client)
    sort_posts(posts)
