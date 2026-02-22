import csv
import re
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlparse
import scrapy


def load_keywords(path: str) -> List[str]:
    kws: List[str] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        first_line = f.readline()
        f.seek(0)

        if "keyword" in first_line.lower():
            reader = csv.DictReader(f)
            for row in reader:
                kw = (row.get("keyword") or "").strip()
                if kw:
                    kws.append(kw)
        else:
            for line in f:
                kw = line.strip().strip('"').strip("'")
                if kw:
                    kws.append(kw)

    # langste eerst is handig (minder “partial” hits)
    return sorted(set(kws), key=len, reverse=True)


def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


@dataclass
class KwMatcher:
    keywords: List[str]

    def __post_init__(self):
        self._compiled = [(kw, re.compile(re.escape(kw), re.IGNORECASE)) for kw in self.keywords]

    def find_all(self, text: str) -> List[str]:
        hits = []
        for kw, rx in self._compiled:
            if rx.search(text):
                hits.append(kw)
        return hits


class DPPostsKeywordSpider(scrapy.Spider):
    """
    Scrape forum threads, extract individual posts, emit only posts that match keywords.
    Output via Scrapy FEEDS to jsonlines + gzip.
    """

    name = "dp_posts_keyword_spider"

    custom_settings = {
        # netjes crawlen:
        "ROBOTSTXT_OBEY": True,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "AUTOTHROTTLE_MAX_DELAY": 15.0,
        "DOWNLOAD_DELAY": 0.75,
        "CONCURRENT_REQUESTS": 4,
        "USER_AGENT": "Mozilla/5.0 (compatible; KeywordResearchCrawler/1.0)",

        # schrijf naar jsonl.gz:
        # (Scrapy regelt de gzip op basis van extensie .gz)
        "FEEDS": {
            "posts.jsonl.gz": {
                "format": "jsonlines",
                "encoding": "utf8",
                "overwrite": True,
            }
        },

        "LOG_LEVEL": "INFO",
    }

    def __init__(
        self,
        start_url: str = None,
        keywords_csv: str = "keywords.csv",
        out_file: str = "posts.jsonl.gz",
        max_pages: int = 2000,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        if not start_url:
            raise ValueError("Geef start_url mee, bv: -a start_url=https://debatepolitics.com/")

        self.start_urls = [start_url]
        netloc = urlparse(start_url).netloc.replace("www.", "")
        self.allowed_domains = [netloc]

        self.max_pages = int(max_pages)
        self.pages_seen = 0

        kws = load_keywords(keywords_csv)
        if not kws:
            raise ValueError(f"Geen keywords gevonden in {keywords_csv}")

        self.matcher = KwMatcher(kws)

        # Override FEEDS output filename indien meegegeven
        self.custom_settings["FEEDS"] = {
            out_file: {
                "format": "jsonlines",
                "encoding": "utf8",
                "overwrite": True,
            }
        }

    # --------------------------
    # Parsing helpers
    # --------------------------

    def _extract_posts(self, response):
        """
        Probeer meerdere forum-structuren.
        Yield tuples: (post_url, post_id, author, datetime, text)
        """

        # XenForo-ish: <article class="message"...>
        for msg in response.css("article.message"):
            post_id = msg.attrib.get("id") or msg.attrib.get("data-content") or None
            author = normalize_space("".join(msg.css(".message-name a::text, a.username::text").getall()))
            dt = msg.css("time::attr(datetime), time::text").get()
            content = " ".join(t.strip() for t in msg.css(".message-body *::text, .bbWrapper *::text").getall() if t.strip())
            content = normalize_space(content)

            # post link (beste effort)
            post_url = msg.css('a[href*="#post-"]::attr(href), a[href*="/post-"]::attr(href)').get()
            post_url = response.urljoin(post_url) if post_url else response.url

            if content:
                yield (post_url, post_id, author, normalize_space(dt), content)

        # vBulletin-ish: <li class="postbit..."> or <div class="postbit">
        for post in response.css("li.postbit, div.postbit, div[id^='post_']"):
            post_id = post.attrib.get("id") or None
            author = normalize_space("".join(post.css("a.username::text, a.bigusername::text").getall()))
            dt = post.css("time::attr(datetime), .date::text, .postdate::text").get()
            content = " ".join(t.strip() for t in post.css(".content *::text, .postcontent *::text, .post_message *::text").getall() if t.strip())
            content = normalize_space(content)

            post_url = post.css("a[href*='#post']::attr(href), a[href*='showpost']::attr(href)").get()
            post_url = response.urljoin(post_url) if post_url else response.url

            if content:
                yield (post_url, post_id, author, normalize_space(dt), content)

        # Fallback: pak grote content blocks (laatste redmiddel)
        # (Niet ideaal, maar voorkomt “0 posts” als markup afwijkend is)
        if not response.css("article.message, li.postbit, div.postbit, div[id^='post_']").get():
            blocks = response.css("div.message, div.post, div.postbody, div.content")
            for b in blocks:
                content = " ".join(t.strip() for t in b.css("*::text").getall() if t.strip())
                content = normalize_space(content)
                if len(content) >= 200:
                    yield (response.url, None, None, None, content)

    def _looks_like_thread_url(self, url: str) -> bool:
        u = url.lower()
        # best-effort patterns: threads, showthread, t=, etc.
        return any(p in u for p in ["/threads/", "showthread", "thread", "t="])

    def _looks_like_forum_listing_url(self, url: str) -> bool:
        u = url.lower()
        return any(p in u for p in ["/forums/", "forumdisplay", "/forum", "f="])

    # --------------------------
    # Main parse
    # --------------------------

    def parse(self, response):
        if self.pages_seen >= self.max_pages:
            return
        self.pages_seen += 1

        # 1) Extract posts on this page, emit only keyword-matches
        for (post_url, post_id, author, dt, text) in self._extract_posts(response):
            hits = self.matcher.find_all(text)
            if not hits:
                continue

            # kleine snippet voor snelle inspectie
            snippet = text[:280] + ("…" if len(text) > 280 else "")

            yield {
                "matched_keywords": hits,
                "url": response.url,
                "post_url": post_url,
                "post_id": post_id,
                "author": author,
                "datetime": dt,
                "text": text,
                "snippet": snippet,
            }

        # 2) Follow pagination within thread (next page)
        next_links = response.css('a[rel="next"]::attr(href), a.pageNav-jump--next::attr(href), a[aria-label*="Next"]::attr(href)').getall()
        for href in next_links:
            if href:
                yield response.follow(href, callback=self.parse)

        # 3) Discover thread links from forum listings (and optionally from anywhere)
        for href in response.css("a::attr(href)").getall():
            if not href:
                continue
            url = response.urljoin(href)

            # stay on domain
            netloc = urlparse(url).netloc.replace("www.", "")
            if netloc not in self.allowed_domains:
                continue

            # skip obvious junk
            if any(x in url.lower() for x in ["logout", "login", "register", "javascript:", "#"]):
                continue

            # Focus: follow thread links; also allow forum listing links so je verder kunt ontdekken
            if self._looks_like_thread_url(url) or self._looks_like_forum_listing_url(url):
                yield scrapy.Request(url, callback=self.parse)
