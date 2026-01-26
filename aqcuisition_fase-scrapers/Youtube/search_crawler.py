def search_videos(
    youtube,
    query,
    max_videos=100,
    relevance_language="en"
):
    video_ids = []
    page_token = None

    while len(video_ids) < max_videos:
        response = youtube.search().list(
            part="id",
            q=query,
            type="video",
            maxResults=500,
            pageToken=page_token,
            relevanceLanguage=relevance_language
        ).execute()

        for item in response.get("items", []):
            video_ids.append(item["id"]["videoId"])
            if len(video_ids) >= max_videos:
                break

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return video_ids
