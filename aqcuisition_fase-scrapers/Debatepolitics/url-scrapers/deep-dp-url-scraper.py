from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin
# This script reads URLs from "url-file.txt", scrapes each page for forum and thread links, and saves them to separate files.
with open("url-file.txt", "r", encoding="utf-8") as f:
    urls = [line.strip() for line in f if line.strip()]

headers = {"User-Agent": "Mozilla/5.0"}

all_forums = set()
all_threads = set()

with open("deeper-forum-url-file.txt", "w", encoding="utf-8") as forum_out, \
     open("thread-url-file.txt", "w", encoding="utf-8") as thread_out:

    for link in urls:
        html = requests.get(link, headers=headers, timeout=20).text
        soup = BeautifulSoup(html, "html.parser")

        # Forums
        title_form = soup.select('h3.node-title a[data-shortcut="node-description"]')
        forums = {}
        for a in title_form:
            name = a.get_text(strip=True)
            url = urljoin(link, a.get("href", ""))
            if url:
                forums[url] = name

        print(f"\n[{link}] Found {len(forums)} forums")
        for url, name in forums.items():
            if url not in all_forums:
                all_forums.add(url)
                forum_out.write(url + "\n")
            # print(name, "->", url) extra info about forum name, can be useful for debugging or future use

        # Threads - look for links in the main content area that start with "/threads/"
        thread_anchors = soup.select('div.structItem-cell--main a[href^="/threads/"]') 

        threads = set()
        for a in thread_anchors:
            href = a.get("href", "")
            if href:
                threads.add(urljoin(link, href))

        print(f"[{link}] Found {len(threads)} threads")
        for t in sorted(threads):
            if t not in all_threads:
                all_threads.add(t)
                thread_out.write(t + "\n")

print(f"\nTOTAL unique forums saved: {len(all_forums)}")
print(f"TOTAL unique threads saved: {len(all_threads)}")
