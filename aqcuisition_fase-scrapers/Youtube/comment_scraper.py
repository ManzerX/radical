def get_top_comments(youtube, video_id, max_comments=200, debug=False):
    """Fetch top-level comments for a video.

    - Handles pagination more safely.
    - Set `debug=True` to print per-page counts and nextPageToken presence.
    """
    from time import sleep
    try:
        from googleapiclient.errors import HttpError
    except Exception:
        HttpError = Exception

    comments = []
    page_token = None
    page = 1

    while len(comments) < max_comments:
        try:
            response = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=100,
                pageToken=page_token,
                order="relevance",
                textFormat="plainText"
            ).execute()
        except HttpError as e:
            if debug:
                print(f"HttpError on page {page}: {e}")
            # simple backoff and stop after a short wait
            sleep(1)
            break

        items = response.get("items", [])
        if debug:
            print(f"page {page}: items={len(items)}, nextPageToken_present={'nextPageToken' in response}")

        for item in items:
            top = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})

            comments.append({
                "author": top.get("authorDisplayName"),
                "text": top.get("textDisplay"),
                "likes": top.get("likeCount", 0),
                "published_at": top.get("publishedAt"),
                "reply_count": item.get("snippet", {}).get("totalReplyCount", 0)
            })

            if len(comments) >= max_comments:
                break

        page_token = response.get("nextPageToken")
        if not page_token:
            if debug:
                print("No nextPageToken — pagination finished")
            break

        page += 1

    return comments

def get_top_comments(youtube, video_id, max_comments=200):
    comments = []
    page_token = None

    while len(comments) < max_comments:
        response = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=100,
            pageToken=page_token,
            order="relevance",
            textFormat="plainText"
        ).execute()

        for item in response["items"]:
            top = item["snippet"]["topLevelComment"]["snippet"]

            comments.append({
                "author": top["authorDisplayName"],
                "text": top["textDisplay"],
                "likes": top["likeCount"],
                "published_at": top["publishedAt"],
                "reply_count": item["snippet"]["totalReplyCount"]
            })

            if len(comments) >= max_comments:
                break

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return comments
