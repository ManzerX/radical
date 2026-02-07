import re
import csv
from urllib.parse import urlparse

import scrapy


def load_keywords(path: str):
    keywords = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        has_header = "keyword" in sample.lower().splitlines()[0]
        if has_header:
            reader = csv.DictReader(f)
            for row in reader:
                kw = (row.get("keyword") or "").strip()
                if kw:
                    keywords.append(kw)
        else:
            for line in f:
                kw = line.strip().strip('"').strip("'")
                if kw:
                    keywords.append(kw)
    # langste eerst (nettere snippet-matches)
    keywords = sorted(set(keywords), key=len, reverse=True)
    return keywords


class DPKeywordSpider(scrapy.Spider):
    name = "dp_keyword_spider"

    custom_settings = {
        # Wees netjes:
        "ROBOTSTXT_OBEY": True,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "AUTOTHROTTLE_MAX_DELAY": 10.0,
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS": 4,
        "USER_AGENT": "Mozilla/5.0 (compatible; ResearchCrawler/1.0; +https://example.com/bot)",
        # Output
        "LOG_LEVEL": "INFO",
    }

    def __init__(self, start_url=None, keywords_csv="keywords.csv", out_csv="ice+term-uitkeyword.csv", max_pages=2000, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not start_url:
            raise ValueError("Geef een start_url mee, bv. https://debatepolitics.com/")

        self.start_urls = [start_url]
        self.allowed_domains = [urlparse(start_url).netloc.replace("www.", "")]
        self.keywords = load_keywords(keywords_csv)
        self.out_csv = out_csv
        self.max_pages = int(max_pages)

        # precompile regexes (case-insensitive)
        self.kw_res = [(kw, re.compile(re.escape(kw), re.IGNORECASE)) for kw in self.keywords]

        # schrijf header
        with open(self.out_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["keyword", "url", "title", "snippet"])

        self.pages_seen = 0

    def parse(self, response):
        if self.pages_seen >= self.max_pages:
            return
        self.pages_seen += 1

        # Pak tekst
        title = (response.css("title::text").get() or "").strip()
        # Grofweg “zichtbare” tekst; forums hebben veel chrome, maar dit is prima start
        text = " ".join(t.strip() for t in response.css("body *::text").getall() if t.strip())
        if not text:
            text = response.text or ""

        # Keyword hits
        hits = []
        for kw, rx in self.kw_res:
            m = rx.search(text)
            if m:
                start = max(0, m.start() - 80)
                end = min(len(text), m.end() + 120)
                snippet = text[start:end].replace("\n", " ").strip()
                hits.append((kw, snippet))

        if hits:
            with open(self.out_csv, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                for kw, snippet in hits:
                    writer.writerow([kw, response.url, title, snippet])

        # Volg interne links
        for href in response.css("a::attr(href)").getall():
            if not href:
                continue
            url = response.urljoin(href)

            # Alleen hetzelfde domein + vermijd “actie” URLs
            netloc = urlparse(url).netloc.replace("www.", "")
            if netloc not in self.allowed_domains:
                continue

            # Optioneel: basic filters tegen troep
            if any(x in url for x in ["#",
                                      "logout",
                                      "/login",
                                      "/register",
                                      "javascript:"]):
                continue

            yield scrapy.Request(url, callback=self.parse, dont_filter=False)
