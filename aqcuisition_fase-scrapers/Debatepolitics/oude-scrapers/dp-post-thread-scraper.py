# De post scraper voor Debatepolitics forum & threads
# Library imports
import json
import gzip
import time
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

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
FORUMS_FILE = "deeper-forum-url-file.txt"
WORDS_FILE = "dp-words-list.txt" # file does not exist yet

POSTS_OUT = data_dir / "dp-posts.jsonl.gz"
MATCHES_OUT = data_dir / "dp-post-matches.jsonl.gz"
DONE_THREADS_FILE = data_dir / "done-threads.txt"

def ticktockmfter(): #
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def load_lines(path: str) -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    return [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]

def append_gz_jsonl(path: Path, obj: dict):
    # Toevoegen van een JSON-regel aan een gzip-bestand; elke schrijving voegt een nieuwe gzip-lid toe.
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    with gzip.open(path, "ab") as f:
        f.write(line.encode("utf-8"))

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

def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def extract_links_and_media(post_root: BeautifulSoup, page_url: str) -> tuple[list[dict], list[dict]]:
    """
    Returns (links, media)
    links: generic links (including youtube)
    media: typed media objects
    """
    links = []
    media = []

    # ---- Images ----
    for img in post_root.select("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original")
        if not src:
            continue
        abs_src = urljoin(page_url, src)
        # filter out smilies/icons if you want; keep it simple now
        media.append({
            "type": "image",
            "url": abs_src,
            "alt": img.get("alt"),
        })

    # ---- Iframes (youtube embeds etc.) ----
    for iframe in post_root.select("iframe"):
        src = iframe.get("src")
        if not src:
            continue
        abs_src = urljoin(page_url, src)
        lower = abs_src.lower()
        if "youtube.com" in lower or "youtu.be" in lower:
            vid = None
            m = re.search(r"(?:embed/|v=)([A-Za-z0-9_-]{6,})", abs_src)
            if m:
                vid = m.group(1)
            media.append({
                "type": "youtube",
                "url": abs_src,
                "video_id": vid
            })
        else:
            media.append({
                "type": "embed",
                "url": abs_src
            })

    # ---- Anchor links ----
    for a in post_root.select("a[href]"):
        href = a.get("href")
        if not href:
            continue
        abs_href = urljoin(page_url, href)
        text = a.get_text(" ", strip=True)
        links.append({"url": abs_href, "text": text})

        lower = abs_href.lower()
        if "youtube.com/watch" in lower or "youtu.be/" in lower:
            vid = None
            m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{6,})", abs_href)
            if m:
                vid = m.group(1)
            media.append({
                "type": "youtube",
                "url": abs_href,
                "video_id": vid
            })

    return links, media

def compile_keywords(words: list[str]) -> list[tuple[str, re.Pattern]]:
    compiled = []
    for w in words:
        w = w.strip()
        if not w:
            continue
        # Als er meerdere woorden zijn, doe een substring regex.
        if re.search(r"\W" , w):
            pat = re.compile(re.escape(w), re.IGNORECASE)
        compiled.append((w, pat))
    return compiled

def match_keywords(text: str, compiled: list[tuple[str, re.Pattern]]) -> list[str]:
    hits = []
    for word, pat in compiled:
        if pat.search(text):
            hits.append(word)
        return hits
    
def parse_posts_from_thread_page(soup: BeautifulSoup, page_url: str) -> list[dict]:
# XenForo posts are often in <article class="message">. Content typically in .message-body .bbWrapper (or .message-body).

    posts = []

    # Try common XenForo containers
    message_nodes = soup.select("article.message") or soup.select("div.message")
    for msg in message_nodes:
        # post id
        post_id = None
        # Often: <article class="message" data-content="post-12345"> or id="js-post-12345"
        dc = msg.get("data-content")
        if dc:
            m = re.search(r"post-(\d+)", dc)
            if m:
                post_id = int(m.group(1))
        if not post_id and msg.get("id"):
            m = re.search(r"(\d+)", msg["id"])
            if m:
                post_id = int(m.group(1))

        # author
        author = None
        a = msg.select_one(".message-name a, .message-userDetails .username, a.username")
        if a:
            author = a.get_text(strip=True)

        # datetime
        created_at = None
        t = msg.select_one("time[datetime]")
        if t and t.get("datetime"):
            created_at = t["datetime"]

        # content root
        content = msg.select_one(".message-body .bbWrapper") \
                  or msg.select_one(".message-body") \
                  or msg.select_one(".bbWrapper")
        if not content:
            continue

        content_html = str(content)
        content_text = clean_text(content.get_text(" ", strip=True))

        links, media = extract_links_and_media(content, page_url)

        posts.append({
            "post_id": post_id,
            "author": author,
            "created_at": created_at,
            "content": {
                "text": content_text,
                "html": content_html
            },
            "entities": {
                "links": links
            },
            "media": media
        })

    return posts

def scrape_thread(thread_url: str, compiled_keywords: list[tuple[str, re.Pattern]], done_threads: set[str]):
    thread_url = normalize_thread_url(thread_url)
    if thread_url in done_threads:
        print(f"SKIP (done): {thread_url}")
        return

    thread_id = extract_thread_id(thread_url)
    page_url = thread_url
    page_count = 0
    total_posts = 0

    while page_url and page_count < MAX_PAGES_PER_THREAD:
        page_count += 1
        time.sleep(DELAY_SECONDS)

        try:
            soup = fetch_soup(page_url)
        except Exception as e:
            print(f"ERROR fetching {page_url}: {e}")
            break

        # Optional thread title
        title = None
        h1 = soup.select_one("h1.p-title-value")
        if h1:
            title = h1.get_text(strip=True)

        # forum url if present (breadcrumb)
        forum_url = None
        bc = soup.select_one('nav.breadcrumbs a[href^="/forums/"]')
        if bc and bc.get("href"):
            forum_url = urljoin(page_url, bc["href"])

        posts = parse_posts_from_thread_page(soup, page_url)

        scraped_at = ticktockmfter()
        for p in posts:
            total_posts += 1

            # keyword hits: search in text + urls (optional)
            text_for_search = p["content"]["text"]
            url_blob = " ".join([x["url"] for x in p["entities"]["links"]]) if p["entities"]["links"] else ""
            hits = match_keywords(text_for_search + " " + url_blob, compiled_keywords)

            record = {
                "source": "debatepolitics",
                "scraped_at": scraped_at,
                "thread": {
                    "id": thread_id,
                    "url": thread_url,
                    "title": title,
                    "forum_url": forum_url,
                    "page_url": page_url,
                    "page_num": page_count
                },
                "post": {
                    "id": p["post_id"],
                    "author": p["author"],
                    "created_at": p["created_at"]
                },
                "content": p["content"],
                "entities": p["entities"],
                "media": p["media"],
                "keywords_hit": hits
            }

            append_gz_jsonl(POSTS_OUT, record)

            if hits:
                append_gz_jsonl(MATCHES_OUT, record)

        next_url = find_next_page_url(soup, page_url)
        if next_url and next_url != page_url:
            page_url = next_url
        else:
            page_url = None

        print(f"Thread {thread_id} page {page_count}: posts {len(posts)} (total {total_posts})")

    # Mark done if we actually scraped at least one page successfully
    done_threads.add(thread_url)
    with open(DONE_THREADS_FILE, "a", encoding="utf-8") as f:
        f.write(thread_url + "\n")
    print(f"DONE thread: {thread_url} (pages={page_count}, posts={total_posts})")

def main():
    thread_urls = load_lines(THREADS_FILE)
    words = load_lines(WORDS_FILE)

    if not thread_urls:
        print(f"No thread URLs found in {THREADS_FILE}")
        return
    if not words:
        print(f"No words found in {WORDS_FILE} - keyword matching disabled or add per row.")
        

    compiled_keywords = compile_keywords(words)
    done_threads = set(load_lines(str(DONE_THREADS_FILE)))

    print(f"Threads input: {len(thread_urls)}")
    print(f"Keywords: {len(compiled_keywords)}")
    print(f"Already done: {len(done_threads)}")

    for url in thread_urls:
        scrape_thread(url, compiled_keywords, done_threads)


if __name__ == "__main__":
    main()
