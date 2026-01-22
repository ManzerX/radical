from youtube_api import get_youtube_client

VIDEO_ID = "il5IEKQ53GI"

y = get_youtube_client()

page_token = None
total = 0
page = 1
while True:
    resp = y.commentThreads().list(
        part="snippet",
        videoId=VIDEO_ID,
        maxResults=100,
        pageToken=page_token,
        order="relevance",
        textFormat="plainText"
    ).execute()

    items = resp.get("items", [])
    print(f"page {page}: items={len(items)}, nextPageToken_present={'nextPageToken' in resp}")
    total += len(items)

    if 'nextPageToken' in resp and len(items) > 0:
        page_token = resp['nextPageToken']
        page += 1
    else:
        break

print('total items fetched:', total)
