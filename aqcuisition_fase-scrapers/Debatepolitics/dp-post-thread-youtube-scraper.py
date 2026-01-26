# De post scraper voor Debatepolitics forum & threads - alleen YouTube links
# Library imports
import time
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Configuratie
BASE = "https://www.debatepolitics.com/"
# user agent and timeout settings
HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 25

DELAY_SECONDS = 0.8
MAX_PAGES_PER_THREAD = 500
data_dir = Path("data/threads/posts/")
data_dir.mkdir(parents=True, exist_ok=True)

THREADS_FILE = "thread-url-file.txt"

YOUTUBE_OUT = data_dir / "dp-youtube-links.txt"
DONE_THREADS_FILE = data_dir / "done-threads.txt"

def ticktockmfter():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def load_lines(path: str) -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    return [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]

def append_lines(path: Path, lines: list[str]) -> None:
    if not lines:
        return
    with open(path, "a", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

def normalize_thread_url(url: str) -> str:
    # ensure absolute URL and remove fragments
    if url.startswith("/"):
        url = urljoin(BASE, url)
    url = url.split("#")[0]
    return url

def extract_thread_id(thread_url: str) -> int | None:
    # XenForo thread URLs have the format /threads/{title}.{thread_id}/
    m = re.search(r"\.(\d+)/?$", thread_url)
    return int(m.group(1)) if m else None

def fetch_soup(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def find_next_page_url(soup: BeautifulSoup, current_url: str) -> str | None:
    # XenForo geeft meestal rel="next" link.
    a = soup.select_one('a[rel="next"]')
    if a and a.get("href"):
        return urljoin(current_url, a["href"])

    # sommige thema's gebruiken pageNav nex button
    a = soup.select_one('a.pageNav-jump--next')
    if a and a.get("href"):
        return urljoin(current_url, a["href"])

    # backup: proberen om "next" te vinden via linktekst
    for cand in soup.select("a"):
        txt = cand.get_text(strip=True).lower()
        if txt in {"next", "volgende", ">", "»"} and cand.get("href"):
            href = cand["href"]
            if not href.startswith("javascript:"):
                return urljoin(current_url, href)

    return None

def parse_post_contents(soup: BeautifulSoup) -> list[BeautifulSoup]:
    contents = []
    message_nodes = soup.select("article.message") or soup.select("div.message")
    for msg in message_nodes:
        content = msg.select_one(".message-body .bbWrapper") \
                  or msg.select_one(".message-body") \
                  or msg.select_one(".bbWrapper")
        if content:
            contents.append(content)
    return contents

def extract_youtube_links(post_root: BeautifulSoup, page_url: str) -> list[str]:
    links = []

    # Iframes (youtube embeds etc.)
    for iframe in post_root.select("iframe"):
        src = iframe.get("src")
        if not src:
            continue
        abs_src = urljoin(page_url, src)
        lower = abs_src.lower()
        if "youtube.com" in lower or "youtu.be" in lower:
            links.append(abs_src)

    # Anchor links
    for a in post_root.select("a[href]"):
        href = a.get("href")
        if not href:
            continue
        abs_href = urljoin(page_url, href)
        lower = abs_href.lower()
        if "youtube.com" in lower or "youtu.be" in lower:
            links.append(abs_href)

    return links

def scrape_thread(thread_url: str, done_threads: set[str], seen_links: set[str]):
    thread_url = normalize_thread_url(thread_url)
    if thread_url in done_threads:
        print(f"SKIP (done): {thread_url}")
        return

    thread_id = extract_thread_id(thread_url)
    page_url = thread_url
    page_count = 0
    total_links = 0

    while page_url and page_count < MAX_PAGES_PER_THREAD:
        page_count += 1
        time.sleep(DELAY_SECONDS)

        try:
            soup = fetch_soup(page_url)
        except Exception as e:
            print(f"ERROR fetching {page_url}: {e}")
            break

        contents = parse_post_contents(soup)

        new_links = []
        for content in contents:
            found = extract_youtube_links(content, page_url)
            for link in found:
                if link not in seen_links:
                    new_links.append(link)
                    seen_links.add(link)

        append_lines(YOUTUBE_OUT, new_links)
        total_links += len(new_links)

        next_url = find_next_page_url(soup, page_url)
        if next_url and next_url != page_url:
            page_url = next_url
        else:
            page_url = None

        print(f"{ticktockmfter()} Thread {thread_id} page {page_count}: new youtube links {len(new_links)} (total {total_links})")

    # Mark done if we actually scraped at least one page successfully
    done_threads.add(thread_url)
    with open(DONE_THREADS_FILE, "a", encoding="utf-8") as f:
        f.write(thread_url + "\n")
    print(f"DONE thread: {thread_url} (pages={page_count}, youtube_links={total_links})")

def main():
    thread_urls = load_lines(THREADS_FILE)
    done_threads = set(load_lines(str(DONE_THREADS_FILE)))
    seen_links = set(load_lines(str(YOUTUBE_OUT)))

    if not thread_urls:
        print(f"No thread URLs found in {THREADS_FILE}")
        return

    print(f"Threads input: {len(thread_urls)}")
    print(f"Already done: {len(done_threads)}")
    print(f"Existing YouTube links: {len(seen_links)}")

    for url in thread_urls:
        scrape_thread(url, done_threads, seen_links)

if __name__ == "__main__":
    main()
