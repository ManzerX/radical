from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin

with open("url-file.txt", "r") as f:
    urls = [line.strip() for line in f.readlines()]

headers = {"User-Agent": "Mozilla/5.0"}
f = open("deeper-url-file.txt", "w")
for link in urls:
    # print(link)

    # copied from dp-url-scraper.py for reference.
    html = requests.get(link, headers=headers, timeout=20).text
    soup = BeautifulSoup(html, "html.parser")

    # forum titles selection based on inspection of html structure.
    title_form = soup.select('h3.node-title a[data-shortcut="node-description"]')

    forums = {}
    for a in title_form:
        name = a.get_text(strip=True)
        url = urljoin(link, a.get("href", "")) # href is used to get relative url.
        if url:
            forums[url] = name  # dict dedupes by url
    # output found forum url's.
    print(f"Found {len(forums)} forums:\n")
    for url, name in forums.items():
        print(name, "->", url)
        f.write(url + "\n")
f.close()