from youtube_api import get_youtube_client
import isodate

def get_video_data(video_id: str) -> dict:
    youtube = get_youtube_client()

    response = youtube.videos().list(
        part="snippet,statistics,contentDetails",
        id=video_id
    ).execute()

    if not response["items"]:
        raise ValueError("Video niet gevonden")

    item = response["items"][0]

    return {
        "video_id": video_id,
        "title": item["snippet"]["title"],
        "description": item["snippet"]["description"],
        "published_at": item["snippet"]["publishedAt"],
        "channel_title": item["snippet"]["channelTitle"],
        "views": int(item["statistics"].get("viewCount", 0)),
        "likes": int(item["statistics"].get("likeCount", 0)),
        "comment_count": int(item["statistics"].get("commentCount", 0)),
        "duration_seconds": int(
            isodate.parse_duration(item["contentDetails"]["duration"]).total_seconds()
        ),
        "tags": item["snippet"].get("tags", [])
    }
