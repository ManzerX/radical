import time

def search_videos(
    youtube,
    query,
    relevance_language="en",
    published_after=None,
    published_before=None,
    sleep_seconds=0.5
):
    """
    Generator die video_ids oplevert zolang YouTube resultaten teruggeeft,
    optioneel beperkt tot een tijdsvenster.
    """

    page_token = None

    while True:
        request = youtube.search().list(
            part="id",
            q=query,
            type="video",
            maxResults=50,               # API max
            pageToken=page_token,
            relevanceLanguage=relevance_language,
            publishedAfter=published_after,
            publishedBefore=published_before
        )

        response = request.execute()
        items = response.get("items", [])

        if not items:
            break

        for item in items:
            yield item["id"]["videoId"]

        page_token = response.get("nextPageToken")
        if not page_token:
            break

        time.sleep(sleep_seconds)
