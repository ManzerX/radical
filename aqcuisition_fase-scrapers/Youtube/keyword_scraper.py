import argparse
import os
import re
import json
from typing import List

from youtube_api import get_youtube_client
from video_scraper import get_video_data
import comment_scraper


def slugify(text: str, max_len: int = 60) -> str:
    s = (text or "").strip()
    s = re.sub(r"[^A-Za-z0-9 ]+", "", s)
    s = re.sub(r"\s+", " ", s)
    s = s.replace(" ", "_").lower()
    return s[:max_len] if s else ""


def search_videos(youtube, include_all: List[str], prefer: List[str], max_results: int = 50):
    """Search YouTube and return candidate video ids.

    We perform a search call with a combined query and then locally filter results so that
    all `include_all` keywords are present in title or description. Videos are returned
    with a score based on how many `prefer` keywords match (descending).
    """
    q_parts = []
    if include_all:
        q_parts += include_all
    elif prefer:
        q_parts += prefer

    q = " ".join(q_parts) if q_parts else ""

    video_candidates = {}
    page_token = None
    fetched = 0

    while fetched < max_results:
        resp = youtube.search().list(
            part="snippet",
            q=q,
            type="video",
            maxResults=50,
            pageToken=page_token
        ).execute()

        for item in resp.get("items", []):
            vid = item["id"]["videoId"]
            title = item["snippet"].get("title", "")
            desc = item["snippet"].get("description", "")
            text = f"{title} {desc}".lower()

            # check required keywords
            ok = True
            for kw in include_all:
                if kw.lower() not in text:
                    ok = False
                    break
            if not ok:
                continue

            # score by optional matches
            score = 0
            for kw in prefer:
                if kw.lower() in text:
                    score += 1

            video_candidates[vid] = {"title": title, "score": score}
            fetched += 1
            if fetched >= max_results:
                break

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    # sort by score desc
    sorted_vids = sorted(video_candidates.items(), key=lambda kv: kv[1]["score"], reverse=True)
    return [(vid, meta["title"]) for vid, meta in sorted_vids]


def run_batch(include_all: List[str], prefer: List[str], max_videos: int, out_dir: str, fetch_comments: bool, max_comments: int, dry_run: bool = False):
    youtube = get_youtube_client()
    os.makedirs(out_dir, exist_ok=True)

    vids = search_videos(youtube, include_all, prefer, max_results=max_videos)
    print(f"Found {len(vids)} candidate videos")

    if dry_run:
        print("Dry run: listing candidate videos without fetching details")
        for vid, title in vids:
            print(f"- {vid} — {title}")
        return

    for vid, title in vids:
        print(f"Processing {vid} — {title}")
        data = get_video_data(vid)
        if fetch_comments:
            data["top_comments"] = comment_scraper.get_top_comments(youtube, vid, max_comments=max_comments)

        # build filename from title snippet (first 4 words) + id to avoid collisions
        words = (title or "").split()
        snippet = " ".join(words[:4]) if words else ""
        slug = slugify(snippet)
        if not slug:
            slug = vid
        filename = f"{slug}_{vid}.json"
        path = os.path.join(out_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Wrote {path}")


def parse_comma_list(value: str):
    if not value:
        return []
    # Accept either a single comma-separated string or a list of strings
    if isinstance(value, list):
        items = []
        for v in value:
            if not v:
                continue
            parts = [x.strip() for x in v.split(",") if x.strip()]
            items.extend(parts)
        return items
    return [v.strip() for v in value.split(",") if v.strip()]


def main():
    p = argparse.ArgumentParser(description="Batch scrape videos by required/optional keywords")
    p.add_argument("--include", nargs='*', help="Required keywords (comma-separated or space-separated)")
    p.add_argument("--prefer", nargs='*', help="Optional keywords (comma-separated or space-separated)")
    p.add_argument("--include-file", help="Path to file with required keywords (one per line or comma-separated)")
    p.add_argument("--prefer-file", help="Path to file with optional keywords (one per line or comma-separated)")
    p.add_argument("--max", type=int, default=10, help="Maximum videos to fetch")
    p.add_argument("--out", default="output/batch", help="Output directory")
    p.add_argument("--no-comments", dest="comments", action="store_false", help="Do not fetch comments")
    p.add_argument("--max-comments", type=int, default=200, help="Max comments per video")
    args = p.parse_args()

    include = parse_comma_list(args.include)
    prefer = parse_comma_list(args.prefer)

    def read_keywords_file(path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                # ignore blank lines and comments
                lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]
            return parse_comma_list(lines)
        except Exception as e:
            print(f"Warning: could not read keywords file {path}: {e}")
            return []

    if args.include_file:
        include += read_keywords_file(args.include_file)
    if args.prefer_file:
        prefer += read_keywords_file(args.prefer_file)

    # deduplicate while keeping order
    include = list(dict.fromkeys(include))
    prefer = list(dict.fromkeys(prefer))
    #--max (max videos)
    #--out (output dir)
    #--comments (fetch comments)
    #--max-comments (max comments per video)

    out_dir = os.path.join(os.path.dirname(__file__), args.out)
    run_batch(include, prefer, args.max, out_dir, args.comments, args.max_comments)


if __name__ == "__main__":
    main()
