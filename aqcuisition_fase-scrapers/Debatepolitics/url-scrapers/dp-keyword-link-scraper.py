import csv
import json
import time
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlunparse, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://debatepolitics.com/"
HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 25
DELAY_SECONDS = 0.8

ICE_PREFIX = "ice"

# ---- Inputs ----
KEYWORDS_CSV = Path("termen_2.csv")  # first column = keyword

# ---- Outputs ----
OUT_THREADS = Path("threads_from_search.txt")
OUT_BY_KEYWORD = Path("threads_by_keyword.json")

# Safety limits
MAX_SEARCH_PAGES_PER_KEYWORD = 50  # raise/lower as you like


def load_keywords_from_csv(path: Path) -> list[str]:
    """
    Loads keywords from a CSV/TSV file.
    - Auto-detect delimiter (comma or tab)
    - Reads ALL cells (so A1, B1, C1... works)
    - Skips empty cells
    - Dedupes case-insensitive, preserves order
    """
    if not path.exists():
        return []

    raw = path.read_text(encoding="utf-8-sig")
    # delimiter detect: if tabs are present and commas not dominant, use tab
    delimiter = "\t" if ("\t" in raw and raw.count("\t") >= raw.count(",")) else ","

    keywords = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=delimiter)
        for row in reader:
            for cell in row:
                kw = (cell or "").strip()
                if kw:
                    keywords.append(kw)

    # Deduplicate (case-insensitive) while preserving order
    seen = set()
    out = []
    for k in keywords:
        kn = k.lower()
        if kn not in seen:
            seen.add(kn)
            out.append(k)
    return out


def fetch_soup(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def get_next_page_url(soup: BeautifulSoup, current_url: str) -> str | None:
    # XenForo usually provides rel="next"
    a = soup.select_one('a[rel="next"]')
    if a and a.get("href"):
        return urljoin(current_url, a["href"])

    # Some themes use this
    a = soup.select_one("a.pageNav-jump--next")
    if a and a.get("href"):
        return urljoin(current_url, a["href"])

    return None


def normalize_thread_url(url: str) -> str:
    # remove fragments (#post-xxx)
    url = url.split("#")[0]
    return url


def canonicalize(url: str) -> str:
    """Force https://debatepolitics.com (no www), strip fragments."""
    url = url.split("#")[0]
    p = urlparse(url)
    netloc = p.netloc.lower().replace("www.", "")
    # only keep debatepolitics.com
    if netloc and netloc != "debatepolitics.com":
        return url  # leave as-is if it's external (shouldn't happen)
    return urlunparse(("https", "debatepolitics.com", p.path, p.params, p.query, ""))

def extract_thread_urls_from_search_page(soup: BeautifulSoup, page_url: str) -> set[str]:
    found = set()

    # Check alleen op échte "no results", niet op algemene blockMessages zoals noscript
    page_text = soup.get_text(" ", strip=True).lower()
    if "no results found" in page_text:
        return set()

    # XenForo search results zitten vrijwel altijd in contentRow blokken
    for row in soup.select("div.contentRow"):
        a = row.select_one("a[href*='/threads/']")
        if not a:
            continue
        href = a.get("href")
        if not href:
            continue
        found.add(canonicalize(urljoin(page_url, href)))

    return found


def search_threads_for_phrase(phrase: str, max_pages: int) -> set[str]:
    """
    Runs a site search for `phrase`, paginates through results, and extracts thread URLs.
    """
    q = quote_plus(phrase)
    url = f"{BASE}search/?q={q}&o=relevance"
    all_found = set()

    for page_idx in range(1, max_pages + 1):
        time.sleep(DELAY_SECONDS)

        soup = fetch_soup(url)
        print("PAGE TITLE:", soup.title.get_text(strip=True) if soup.title else "NO TITLE")

        msg = soup.select_one(".blockMessage")
        if msg:
            print("BLOCK MESSAGE:", msg.get_text(strip=True))
        page_threads = extract_thread_urls_from_search_page(soup, url)
        all_found |= page_threads

        print(f"  page {page_idx}: +{len(page_threads)} threads (total {len(all_found)})")

        nxt = get_next_page_url(soup, url)
        if not nxt or nxt == url:
            break
        url = nxt

    return all_found


def main():
    keywords = load_keywords_from_csv(KEYWORDS_CSV)
    if not keywords:
        print(f"No keywords found in {KEYWORDS_CSV}")
        return

    all_threads = set()
    by_keyword: dict[str, list[str]] = {}

    print(f"Loaded {len(keywords)} keywords from {KEYWORDS_CSV}")
    print(f"Prefix: '{ICE_PREFIX} '")
    print(f"Max search pages per keyword: {MAX_SEARCH_PAGES_PER_KEYWORD}\n")

    for kw in keywords:
        phrase = f"{ICE_PREFIX} {kw}".strip()
        print(f"Searching: {phrase}")

        threads = search_threads_for_phrase(phrase, max_pages=MAX_SEARCH_PAGES_PER_KEYWORD)
        threads_sorted = sorted(threads)

        by_keyword[phrase] = threads_sorted
        all_threads |= threads

        print(f"  => {len(threads_sorted)} unique threads for '{phrase}'\n")

    OUT_THREADS.write_text("\n".join(sorted(all_threads)) + "\n", encoding="utf-8")
    OUT_BY_KEYWORD.write_text(json.dumps(by_keyword, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Loaded keywords:", keywords)
    print("Count:", len(keywords))
    print("DONE")
    print(f"Total unique threads found: {len(all_threads)}")
    print(f"Wrote: {OUT_THREADS}")
    print(f"Wrote: {OUT_BY_KEYWORD} (debug / per-keyword breakdown)")


if __name__ == "__main__":
    main()
