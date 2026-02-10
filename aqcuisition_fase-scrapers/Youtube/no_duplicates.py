import json
import sys
from pathlib import Path
import os

BASE_DIR = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DATASET_PATH = os.path.join(OUTPUT_DIR, "yt_results_archive.jsonl")

INPUT_FILE = os.path.join(OUTPUT_DIR, "yt_results_archive.jsonl")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "yt_results_uniq.jsonl")


def engagement_score(item):
    """
    Gebruik simpele engagement score om 'beste' duplicate te kiezen.
    """
    return (
        int(item.get("views", 0)) +
        int(item.get("likes", 0)) * 5 +
        int(item.get("comment_count", 0)) * 3
    )


def main():
    input_path = Path(INPUT_FILE)
    output_path = Path(OUTPUT_FILE)

    if not input_path.exists():
        print(f"Inputbestand bestaat niet: {input_path}")
        sys.exit(1)

    by_video_id = {}
    total_lines = 0

    print("[+] Inlezen...")

    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            total_lines += 1
            item = json.loads(line)

            vid = item.get("video_id")
            if not vid:
                continue

            if vid not in by_video_id:
                by_video_id[vid] = item
            else:
                # kies record met hoogste engagement
                old = by_video_id[vid]
                if engagement_score(item) > engagement_score(old):
                    by_video_id[vid] = item

    uniques = len(by_video_id)

    print(f"[+] Totaal regels: {total_lines}")
    print(f"[+] Unieke video_ids: {uniques}")
    print(f"[+] Duplicaten verwijderd: {total_lines - uniques}")

    print("[+] Schrijven...")

    with output_path.open("w", encoding="utf-8") as f:
        for item in by_video_id.values():
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"[✓] Klaar → {output_path}")


if __name__ == "__main__":
    main()
