from googleapiclient.discovery import build
from config import YOUTUBE_API_KEY

youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

request = youtube.search().list(
    part="snippet",
    q="python tutorial",
    maxResults=1
)

response = request.execute()

print(response["items"][0]["snippet"]["title"])
