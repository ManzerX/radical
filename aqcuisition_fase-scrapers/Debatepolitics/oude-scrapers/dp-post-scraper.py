#!/usr/bin/env python3
import csv
import gzip
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse

import scrapy
from scrapy.crawler import CrawlerProcess

# =========================
# CONFIG (pas dit aan)
# =========================
START_URL = "https://debatepolitics.com/"
TERMS_CSV = "termen_2.csv"          # ligt in dezelfde map
TERMS_COL = ""              # kolomnaam in termen_2.csv
OUT_FILE = "ice+term-uitkeyword.jsonl.gz"

MAX_PAGES = 200000                  # hard cap
DOWNLOAD_DELAY = 0.15               # vriendelijker crawlen
CONCURRENCY = 16
# =========================


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def load_ice_prefixed_terms(path: str, prefix: str = "ice ") -> List[str]:
    """
    Leest ALLE kolomnamen uit termen_2.csv
    en maakt er keywords van als: 'ice <kolomnaam>'
    """
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)  # eerste rij = kolomnamen

    terms = []
    for col_name in header:
        col_name = col_name.strip()
        if not col_name:
            continue
        terms.append(f"{prefix}{col_name}")

    # uniek + langste eerst (betere matching)
    return sorted(set(terms), key=len, reverse=True)



@dataclass
class TermMatcher:
    terms: List[str]

    def __post_init__(self):
        self._compiled = [(t, re.compile(re.escape(t), re.IGNORECASE)) for t in self.terms]

    def find_all(self, text: str) -> List[str]:
        hits = []
        for t, rx in self._compiled:
            if rx.search(text):
                hits.append(t)
        return hits


class JsonlGzPipeline:
    def __init__(self, out_file: str):
        self.out_file = out_file
        self._fh = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings.get("OUT_FILE"))

    def open_spider(self, spider):
        self._fh = gzip.open(self.out_file, "wt", encoding="utf-8")

    def close_spider(self, spider):
        if self._fh:
            self._fh.close()

    def process_item(self, item, spider):
        self._fh.write(json.dumps(dict(item), ensure_ascii=False) + "\n")
        self._fh.flush()
        return item


class DebatePoliticsSpider(scrapy.Spider):
    name = "debatepolitics_posts_by_terms"

    def __init__(self, start_url: str, terms_csv: str, terms_col: str, max_pages: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = [start_url]
        self.max_pages = int(max_pages)
        self.pages_seen = 0

        netloc = urlparse(start_url).netloc.replace("www.", "")
        self.allowed_domains = [netloc]
        self.base_netloc = netloc

        terms = load_ice_prefixed_terms(terms_csv, prefix = "ice ")
        if not terms:
            raise ValueError(f"Geen termen gevonden in {terms_csv} (kolom '{terms_col}' of fallback eerste kolom).")
        self.matcher = TermMatcher(terms)

    # -------- URL helpers --------
    def _same_domain(self, url: str) -> bool:
        netloc = urlparse(url).netloc.replace("www.", "")
        return netloc == self.base_netloc

    def _skip_url(self, url: str) -> bool:
        u = url.lower()
        return any(x in u for x in [
            "javascript:",
            "/login",
            "/register",
            "/logout",
            "/account",
            "/members/",
            "/help",
            "/search",
            "/attachments/",
            "/goto/",
            "#",
        ])

    def _looks_like_forum_or_thread(self, url: str) -> bool:
        u = url.lower()
        return any(p in u for p in [
            "/threads/",
            "/forums/",
            "showthread",
            "forumdisplay",
            "thread",
            "t=",
            "f=",
            "page-",
            "page=",
        ])

    # -------- metadata helpers --------
    def _page_context(self, response) -> Dict[str, Optional[str]]:
        title = normalize_space(response.css("title::text").get() or "") or None
        h1 = normalize_space(" ".join(response.css("h1 *::text, h1::text").getall())) or None
        thread_title = h1 or title

        crumbs = [normalize_space(t) for t in response.css(
            ".p-breadcrumbs *::text, nav.breadcrumb *::text, .breadcrumb *::text"
        ).getall()]
        crumbs = [c for c in crumbs if c]
        forum_path = " > ".join(dict.fromkeys(crumbs)) if crumbs else None

        return {"page_title": title, "thread_title": thread_title, "forum_path": forum_path}

    def _extract_posts(self, response):
        ctx = self._page_context(response)

        found = False

        # XenForo-ish
        for msg in response.css("article.message"):
            found = True
            post_id = msg.attrib.get("id") or msg.attrib.get("data-content") or None
            author = normalize_space("".join(msg.css(".message-name a::text, a.username::text").getall())) or None
            dt = msg.css("time::attr(datetime)").get() or normalize_space(msg.css("time::text").get() or "") or None

            text = " ".join(t.strip() for t in msg.css(".message-body *::text, .bbWrapper *::text").getall() if t.strip())
            text = normalize_space(text)
            quote_count = len(msg.css("blockquote").getall())

            post_href = msg.css('a[href*="#post-"]::attr(href), a[href*="/post-"]::attr(href)').get()
            post_url = response.urljoin(post_href) if post_href else response.url

            if text:
                yield {**ctx,
                       "source_page_url": response.url,
                       "post_url": post_url,
                       "post_id": post_id,
                       "author": author,
                       "datetime": dt,
                       "quote_count": quote_count,
                       "text": text}

        # vBulletin-ish
        for post in response.css("li.postbit, div.postbit, div[id^='post_']"):
            found = True
            post_id = post.attrib.get("id") or None
            author = normalize_space("".join(post.css("a.username::text, a.bigusername::text").getall())) or None
            dt = post.css("time::attr(datetime), .date::text, .postdate::text").get()
            dt = normalize_space(dt) if dt else None

            text = " ".join(t.strip() for t in post.css(".content *::text, .postcontent *::text, .post_message *::text").getall() if t.strip())
            text = normalize_space(text)
            quote_count = len(post.css("blockquote").getall())

            post_href = post.css("a[href*='#post']::attr(href), a[href*='showpost']::attr(href)").get()
            post_url = response.urljoin(post_href) if post_href else response.url

            if text:
                yield {**ctx,
                       "source_page_url": response.url,
                       "post_url": post_url,
                       "post_id": post_id,
                       "author": author,
                       "datetime": dt,
                       "quote_count": quote_count,
                       "text": text}

        # Fallback
        if not found:
            for b in response.css("div.message, div.post, div.postbody, div.content"):
                text = " ".join(t.strip() for t in b.css("*::text").getall() if t.strip())
                text = normalize_space(text)
                if len(text) >= 250:
                    yield {**ctx,
                           "source_page_url": response.url,
                           "post_url": response.url,
                           "post_id": None,
                           "author": None,
                           "datetime": None,
                           "quote_count": len(b.css("blockquote").getall()),
                           "text": text}

    def parse(self, response):
        self.logger.info("VISITING %s", response.url)
        if self.pages_seen >= self.max_pages:
            return
        self.pages_seen += 1

        # Emit matching posts
        for post in self._extract_posts(response):
            hits = self.matcher.find_all(post["text"])
            if not hits:
                continue

            text = post["text"]
            snippet = text[:350] + ("…" if len(text) > 350 else "")
            yield {
                "matched_terms": hits,
                "scraped_at_utc": now_iso(),
                "page_title": post.get("page_title"),
                "thread_title": post.get("thread_title"),
                "forum_path": post.get("forum_path"),
                "source_page_url": post.get("source_page_url"),
                "post_url": post.get("post_url"),
                "post_id": post.get("post_id"),
                "author": post.get("author"),
                "datetime": post.get("datetime"),
                "quote_count": post.get("quote_count"),
                "snippet": snippet,
                "text": text,
            }

        # Pagination next
        for href in response.css("a::attr(href)").getall():
            if not href:
                continue

            url = response.urljoin(href)
            low = url.lower()

            if not self._same_domain(url):
                continue
            if self._skip_url(url):
                continue

            # === THREADS (hoogste prioriteit) ===
            if "/threads/" in low:
                yield scrapy.Request(url, callback=self.parse, priority=20)
                continue

            # === THREAD PAGINATION ===
            if "/page-" in low and "/threads/" in low:
                yield scrapy.Request(url, callback=self.parse, priority=15)
                continue

            # === FORUM LIJSTEN (nodig om nieuwe threads te vinden) ===
            if "/forums/" in low:
                yield scrapy.Request(url, callback=self.parse, priority=10)
                continue


def run():
    settings = {
         "ROBOTSTXT_OBEY": True,

        # agressieve maar nette crawling
        "CONCURRENT_REQUESTS": 12,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 6,

        "DOWNLOAD_DELAY": 0.35,
        "RANDOMIZE_DOWNLOAD_DELAY": True,

        # Autothrottle aan: past zich aan als site traag wordt
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 0.4,
        "AUTOTHROTTLE_MAX_DELAY": 15.0,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 3.0,

        # Timeouts/retries zodat je niet “sterft” op 1 hapering
        "DOWNLOAD_TIMEOUT": 60,
        "DNS_TIMEOUT": 30,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 6,
        "RETRY_HTTP_CODES": [408, 429, 500, 502, 503, 504, 522, 524],

        "COOKIES_ENABLED": False,
        "TELNETCONSOLE_ENABLED": False,

        "LOG_LEVEL": "INFO",
        "LOGSTATS_INTERVAL": 30,

        "ITEM_PIPELINES": {__name__ + ".JsonlGzPipeline": 300},
        "OUT_FILE": OUT_FILE,
        "OUT_FILE": OUT_FILE,
        "JOBDIR": "jobstate-debatepolitics",
    }

    process = CrawlerProcess(settings=settings)
    process.crawl(
        DebatePoliticsSpider,
        start_url=START_URL,
        terms_csv=TERMS_CSV,
        terms_col=TERMS_COL,
        max_pages=MAX_PAGES,
    )
    process.start()


if __name__ == "__main__":
    run()
