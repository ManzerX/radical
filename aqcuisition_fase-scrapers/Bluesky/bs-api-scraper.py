from atproto import Client
from dotenv import load_dotenv
import os
import pandas as pd

def main(client):
    load_dotenv()

    bs_user = os.getenv('USER')
    bs_pass = os.getenv('PASS')

    cursor = None
    databs_posts = []

    client.login(bs_user, bs_pass)

    while True:
        fetched = posts = client.app.bsky.feed.search_posts(params={'q': """query""", 'cursor': cursor})
        databs_posts = databs_posts + fetched.posts

        if not fetched.cursor:
            break

        cursor = fetched.cursor


if __name__ == '__main__':
    client = Client()
    main(client)
