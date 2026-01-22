import argparse
import os
from typing import List

from keyword_scraper import run_batch, parse_comma_list


def read_keywords_file(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]
        return parse_comma_list(lines)
    except Exception as e:
        print(f"Warning: could not read keywords file {path}: {e}")
        return []


def main():
    p = argparse.ArgumentParser(description="Run batch search using keywords")
    p.add_argument("--include", nargs='*', help="Required keywords (space-separated or comma-separated)")
    p.add_argument("--prefer", nargs='*', help="Preferred keywords (space-separated or comma-separated)")
    p.add_argument("--include-file", help="Path to include keywords file")
    p.add_argument("--prefer-file", help="Path to prefer keywords file")
    p.add_argument("--keywords-dir", help="Directory containing include.txt and prefer.txt")
    p.add_argument("--max", type=int, default=10, help="Maximum videos to fetch")
    p.add_argument("--out", default="output/batch", help="Output directory")
    p.add_argument("--no-comments", dest="comments", action="store_false", help="Do not fetch comments")
    p.add_argument("--max-comments", type=int, default=200, help="Max comments per video")
    p.add_argument("--dry-run", action="store_true", help="List candidate videos without fetching details")
    args = p.parse_args()

    include = parse_comma_list(args.include)
    prefer = parse_comma_list(args.prefer)

    if args.keywords_dir:
        inc_path = os.path.join(args.keywords_dir, "include.txt")
        pref_path = os.path.join(args.keywords_dir, "prefer.txt")
        if os.path.exists(inc_path):
            include += read_keywords_file(inc_path)
        if os.path.exists(pref_path):
            prefer += read_keywords_file(pref_path)

    if args.include_file:
        include += read_keywords_file(args.include_file)
    if args.prefer_file:
        prefer += read_keywords_file(args.prefer_file)

    # deduplicate while keeping order
    include = list(dict.fromkeys(include))
    prefer = list(dict.fromkeys(prefer))

    out_dir = os.path.join(os.path.dirname(__file__), args.out)
    os.makedirs(out_dir, exist_ok=True)

    print(f"Running batch search — include={include} prefer={prefer} max={args.max} dry_run={args.dry_run}")
    run_batch(include, prefer, args.max, out_dir, args.comments, args.max_comments, dry_run=args.dry_run)


if __name__ == "__main__":
    main()