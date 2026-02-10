import argparse
import json
import os
import time

from googleapiclient.errors import HttpError

from youtube_api import get_youtube_client


BASE_DIR = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DEFAULT_INPUT_PATH = os.path.join(OUTPUT_DIR, "yt_results_uniq.jsonl")
DEFAULT_OUTPUT_PATH = os.path.join(OUTPUT_DIR, "yt_results_uniq_with_comments.jsonl")


def _http_reason(exc):
    try:
        payload = json.loads(exc.content.decode("utf-8"))
        return (
            payload.get("error", {})
            .get("errors", [{}])[0]
            .get("reason", "")
        )
    except Exception:
        return ""


def get_top_comments(youtube, video_id, max_comments=200, debug=False, max_retries=3):
    comments = []
    page_token = None
    page = 1

    # Eerst relevance; bij structureel 0 items valt dit terug naar time.
    for order in ("relevance", "time"):
        comments = []
        page_token = None
        page = 1

        while len(comments) < max_comments:
            retries = 0
            response = None

            while retries <= max_retries:
                try:
                    response = youtube.commentThreads().list(
                        part="snippet",
                        videoId=video_id,
                        maxResults=100,
                        pageToken=page_token,
                        order=order,
                        textFormat="plainText",
                    ).execute()
                    break
                except HttpError as e:
                    reason = _http_reason(e)

                    if reason in ("commentsDisabled", "videoNotFound"):
                        if debug:
                            print(f"[SKIP] {video_id}: {reason}")
                        return []

                    if reason in ("quotaExceeded", "dailyLimitExceeded"):
                        raise RuntimeError(f"quota_exceeded:{video_id}") from e

                    retries += 1
                    if retries > max_retries:
                        raise RuntimeError(f"http_error:{video_id}:{reason or 'unknown'}") from e

                    backoff = 1.5 ** retries
                    if debug:
                        print(
                            f"[WARN] {video_id} page {page} order={order} retry {retries}/{max_retries} "
                            f"reason={reason or 'unknown'} wacht={backoff:.1f}s"
                        )
                    time.sleep(backoff)

            if response is None:
                break

            items = response.get("items", [])
            if debug:
                print(
                    f"[DEBUG] {video_id} page={page} order={order} items={len(items)} "
                    f"next={'yes' if response.get('nextPageToken') else 'no'}"
                )

            for item in items:
                top = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                comments.append(
                    {
                        "author": top.get("authorDisplayName"),
                        "text": top.get("textDisplay"),
                        "likes": top.get("likeCount", 0),
                        "published_at": top.get("publishedAt"),
                        "reply_count": item.get("snippet", {}).get("totalReplyCount", 0),
                    }
                )
                if len(comments) >= max_comments:
                    break

            page_token = response.get("nextPageToken")
            if not page_token:
                break
            page += 1

        if comments:
            return comments

    return comments


def iter_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield line_no, json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[WARN] Ongeldige JSON op regel {line_no}: {e}")


def run(input_path, output_path, max_comments, sleep_seconds, debug=False):
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Inputbestand niet gevonden: {input_path}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    youtube = get_youtube_client()
    processed = 0
    skipped = 0

    with open(output_path, "w", encoding="utf-8") as out_f:
        for line_no, item in iter_jsonl(input_path):
            video_id = item.get("video_id")
            if not video_id:
                skipped += 1
                print(f"[SKIP] Regel {line_no} heeft geen video_id")
                continue

            try:
                comment_list = get_top_comments(
                    youtube=youtube,
                    video_id=video_id,
                    max_comments=max_comments,
                    debug=debug,
                )
            except RuntimeError as e:
                skipped += 1
                msg = str(e)
                if msg.startswith("quota_exceeded:"):
                    print("[STOP] YouTube API quota bereikt. Stoppen om foutieve lege comment-lijsten te voorkomen.")
                    break
                print(f"[ERROR] {video_id}: {msg}")
                continue
            except Exception as e:
                skipped += 1
                print(f"[ERROR] {video_id}: {e}")
                continue

            result = {
                "video_id": video_id,
                "title": item.get("title"),
                "likes": int(item.get("likes", 0) or 0),
                "comments": int(item.get("comment_count", 0) or 0),
                "views": int(item.get("views", 0) or 0),
                "comment_list": comment_list,
            }

            out_f.write(json.dumps(result, ensure_ascii=False) + "\n")
            processed += 1

            print(
                f"[OK] {video_id}: meta_comments={result['comments']} "
                f"gescraped={len(comment_list)}"
            )

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    print(
        f"\nKlaar. Verwerkt: {processed}, overgeslagen/fout: {skipped}. "
        f"Output: {output_path}"
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Lees yt_results_uniq.jsonl en haal comments op voor elke video."
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT_PATH,
        help=f"Input JSONL pad (default: {DEFAULT_INPUT_PATH})",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output JSONL pad (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--max-comments",
        type=int,
        default=200,
        help="Max aantal comments per video (default: 200)",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.25,
        help="Wachttijd tussen video's in seconden (default: 0.25)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Toon extra debug output",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(
        input_path=args.input,
        output_path=args.output,
        max_comments=args.max_comments,
        sleep_seconds=args.sleep,
        debug=args.debug,
    )
