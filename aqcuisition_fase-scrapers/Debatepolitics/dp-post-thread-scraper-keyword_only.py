import csv
import gzip
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://debatepolitics.com/"
HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 25
DELAY_SECONDS = 0.8
MAX_PAGES_PER_THREAD = 500

# ---- input files ----
THREADS_FILE = Path("thread-url-file.txt")
KEYWORDS_CSV = Path("keywords.csv")  # <- jouw csv bestand

# ---- output ----
DATA_DIR = Path("data/debatepolitics")
DATA_DIR.mkdir(parents=True, exist_ok=True)

MATCHES_OUT = DATA_DIR / "keyword_matches.jsonl.gz"
DONE_THREADS_FILE = DATA_DIR / "state_threads_done.txt"

ICE_PREFIX = "ice"  # hardcoded string prefix


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text(encoding="utf-8-sig").splitlines() if ln.strip()]


def load_keywords_from_csv(path: Path) -> list[str]:
    """
    Reads keywords from the first column of a CSV.
    Skips empty cells.
    """
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            kw = (row[0] or "").strip()
            if not kw:
                continue
            out.append(kw)
    return out


def append_gz_jsonl(path: Path, obj: dict):
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    with gzip.open(path, "ab") as f:
        f.write(line.encode("utf-8"))


def normalize_thread_url(url: str) -> str:
    if url.startswith("/"):
        url = urljoin(BASE, url)
    return url.split("#")[0]


def extract_thread_id(thread_url: str) -> int | None:
    m = re.search(r"\.(\d+)/?$", thread_url)
    return int(m.group(1)) if m else None


def fetch_soup(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def find_next_page_url(soup: BeautifulSoup, current_url: str) -> str | None:
    a = soup.select_one('a[rel="next"]')
    if a and a.get("href"):
        return urljoin(current_url, a["href"])

    a = soup.select_one("a.pageNav-jump--next")
    if a and a.get("href"):
        return urljoin(current_url, a["href"])

    return None


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_links_and_media(post_root: BeautifulSoup, page_url: str) -> tuple[list[dict], list[dict]]:
    links = []
    media = []

    for img in post_root.select("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original")
        if not src:
            continue
        media.append({"type": "image", "url": urljoin(page_url, src), "alt": img.get("alt")})

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
            media.append({"type": "youtube", "url": abs_src, "video_id": vid})
        else:
            media.append({"type": "embed", "url": abs_src})

    for a in post_root.select("a[href]"):
        href = a.get("href")
        if not href:
            continue
        abs_href = urljoin(page_url, href)
        links.append({"url": abs_href, "text": a.get_text(" ", strip=True)})

        lower = abs_href.lower()
        if "youtube.com/watch" in lower or "youtu.be/" in lower:
            vid = None
            m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{6,})", abs_href)
            if m:
                vid = m.group(1)
            media.append({"type": "youtube", "url": abs_href, "video_id": vid})

    return links, media


def parse_posts_from_thread_page(soup: BeautifulSoup, page_url: str) -> list[dict]:
    posts = []
    message_nodes = soup.select("article.message") or soup.select("div.message")

    for msg in message_nodes:
        post_id = None
        dc = msg.get("data-content", "")
        m = re.search(r"post-(\d+)", dc)
        if m:
            post_id = int(m.group(1))

        if not post_id:
            mid = msg.get("id", "")
            m = re.search(r"(\d+)", mid)
            if m:
                post_id = int(m.group(1))

        author = None
        a_user = (
            msg.select_one("a.username")
            or msg.select_one(".message-name a")
            or msg.select_one(".message-userDetails .username")
        )
        if a_user:
            author = a_user.get_text(strip=True)

        created_at = None
        t = msg.select_one("time[datetime]")
        if t and t.get("datetime"):
            created_at = t["datetime"]

        content = (
            msg.select_one(".message-body .bbWrapper")
            or msg.select_one(".message-content .bbWrapper")
            or msg.select_one(".message-body")
            or msg.select_one(".bbWrapper")
        )
        if not content:
            continue

        content_html = str(content)
        content_text = clean_text(content.get_text(" ", strip=True))
        links, media = extract_links_and_media(content, page_url)

        posts.append(
            {
                "post_id": post_id,
                "author": author,
                "created_at": created_at,
                "content": {"text": content_text, "html": content_html},
                "entities": {"links": links},
                "media": media,
            }
        )
    return posts


def compile_phrases_with_ice(keywords: list[str]) -> list[tuple[str, re.Pattern]]:
    """
    For each keyword -> phrase = "ice <keyword>"
    Match case-insensitive substring (escaped).
    """
    compiled = []
    for kw in keywords:
        phrase = f"{ICE_PREFIX} {kw}".strip()
        pat = re.compile(re.escape(phrase), re.IGNORECASE)
        compiled.append((phrase, pat))
    return compiled


def match_phrases(text: str, compiled: list[tuple[str, re.Pattern]]) -> list[str]:
    hits = []
    for phrase, pat in compiled:
        if pat.search(text):
            hits.append(phrase)
    return hits


def scrape_thread(thread_url: str, compiled_phrases: list[tuple[str, re.Pattern]], done_threads: set[str]):
    thread_url = normalize_thread_url(thread_url)
    if thread_url in done_threads:
        print(f"SKIP (done): {thread_url}")
        return

    thread_id = extract_thread_id(thread_url)
    page_url = thread_url
    page_num = 0
    matches_in_thread = 0

    while page_url and page_num < MAX_PAGES_PER_THREAD:
        page_num += 1
        time.sleep(DELAY_SECONDS)

        try:
            soup = fetch_soup(page_url)
        except Exception as e:
            print(f"ERROR fetching {page_url}: {e}")
            break

        title = None
        h1 = soup.select_one("h1.p-title-value")
        if h1:
            title = h1.get_text(strip=True)

        forum_url = None
        bc = soup.select_one('nav.breadcrumbs a[href^="/forums/"]')
        if bc and bc.get("href"):
            forum_url = urljoin(page_url, bc["href"])

        posts = parse_posts_from_thread_page(soup, page_url)
        scraped_at = now_iso()

        for p in posts:
            # zoek in tekst + urls (handig voor matches op links)
            url_blob = " ".join([x["url"] for x in p["entities"]["links"]]) if p["entities"]["links"] else ""
            haystack = f'{p["content"]["text"]} {url_blob}'

            hits = match_phrases(haystack, compiled_phrases)
            if not hits:
                continue  # <-- KEYWORD-ONLY: skip posts without hits

            matches_in_thread += 1
            record = {
                "source": "debatepolitics",
                "scraped_at": scraped_at,
                "thread": {
                    "id": thread_id,
                    "url": thread_url,
                    "title": title,
                    "forum_url": forum_url,
                    "page_url": page_url,
                    "page_num": page_num,
                },
                "post": {
                    "id": p["post_id"],
                    "author": p["author"],
                    "created_at": p["created_at"],
                },
                "content": p["content"],
                "entities": p["entities"],
                "media": p["media"],
                "keywords_hit": hits,
            }
            append_gz_jsonl(MATCHES_OUT, record)

        next_url = find_next_page_url(soup, page_url)
        page_url = next_url if next_url and next_url != page_url else None

        print(f"Thread {thread_id} page {page_num}: posts={len(posts)} matches_so_far={matches_in_thread}")

    done_threads.add(thread_url)
    with DONE_THREADS_FILE.open("a", encoding="utf-8") as f:
        f.write(thread_url + "\n")

    print(f"DONE thread: {thread_url} | total_matches={matches_in_thread}")


def main():
    thread_urls = load_lines(THREADS_FILE)
    if not thread_urls:
        print(f"No thread URLs found in {THREADS_FILE}")
        return

    keywords = load_keywords_from_csv(KEYWORDS_CSV)
    if not keywords:
        print(f"No keywords found in {KEYWORDS_CSV}")
        return

    compiled_phrases = compile_phrases_with_ice(keywords)
    done_threads = set(load_lines(DONE_THREADS_FILE))

    print(f"Threads input: {len(thread_urls)}")
    print(f"Keywords from CSV: {len(keywords)}")
    print(f"Search phrases (with prefix '{ICE_PREFIX}'): {len(compiled_phrases)}")
    print(f"Already done: {len(done_threads)}")
    print(f"Output (matches only): {MATCHES_OUT}")

    for url in thread_urls:
        scrape_thread(url, compiled_phrases, done_threads)


if __name__ == "__main__":
    main()
