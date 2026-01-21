# De post scraper voor Debatepolitics forum & threads
# Library imports
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin

# user agent and timeout settings
headers = {"User-Agent": "Mozilla/5.0"}
timeout = 20

# Reading 2 input files, generated in deep-dp-url-scraper.py to scrape posts from threads and forums.
with open("thread-url-file.txt", "r", encoding="utf-8") as threads_file:
    thread_urls = [line.strip() for line in threads_file if line.strip()]

with open("deeper-forum-url-file.txt", "r", encoding="utf-8") as forums_file:
    forum_urls = [line.strip() for line in forums_file if line.strip()]

# Function to scrape posts from a given URL
def scrape_posts(url): # schetch function
    print(f"Scraping posts from: {url}")
    html = requests.get(url, headers=headers, timeout=timeout).text
    soup = BeautifulSoup(html, "html.parser")

    posts = []
    post_divs = soup.select('div.message-body')
    for div in post_divs:
        post_text = div.get_text(strip=True)
        posts.append(post_text)

    print(f"Found {len(posts)} posts.")
    return posts

