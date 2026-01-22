from googleapiclient.discovery import build
from config import YOUTUBE_API_KEY

def get_youtube_client():
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
