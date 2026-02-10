import json
import os
import argparse

# =====================
# CONFIG
# =====================
BASE_DIR = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DATASET_PATH = os.path.join(OUTPUT_DIR, "yt_results_uniq.jsonl")

# Sorteerprioriteit: lijst met velden in aflopende belang (hoogste eerst).
# Standaard: eerst likes, dan views, dan comment_count. Alle velden aflopend.
DEFAULT_SORT_PRIORITY = ["likes", "views", "comment_count"]

def parse_args():
    p = argparse.ArgumentParser(description="Sorteer een bestaande yt_results.jsonl zonder opnieuw te scrapen.")
    p.add_argument(
        "--sort",
        "-s",
        default=",".join(DEFAULT_SORT_PRIORITY),
        help=("Comma-separated sort priority (highest first). "
              "Example: --sort likes,views,comment_count")
    )
    p.add_argument(
        "--preset",
        "-p",
        choices=["engagement"],
        help=("Use a named preset for sort priority. Available: 'engagement'"
              " (maps to likes, comment_count, views)")
    )
    p.add_argument(
        "--input",
        "-i",
        default=DATASET_PATH,
        help="Path to input file (default: output/yt_results.jsonl)"
    )
    p.add_argument(
        "--output",
        "-o",
        default=DATASET_PATH,
        help="Path to output file (default: overwrites input file)"
    )
    return p.parse_args()

def sort_items(items, priority):
    def key_fn(it):
        # We gebruiken -int() voor aflopende sortering (hoogste eerst)
        # We vangen None of lege strings op met 'or 0'
        return tuple(-int(it.get(f, 0) or 0) for f in priority)
    return sorted(items, key=key_fn)

def main():
    args = parse_args()

    # Handle preset override
    if getattr(args, "preset", None):
        if args.preset == "engagement":
            sort_priority = ["likes", "comment_count", "views"]
    else:
        sort_priority = [s.strip() for s in args.sort.split(",") if s.strip()]

    print(f"[+] Bestand lezen: {args.input}")
    print(f"[+] Sorteerprioriteit: {sort_priority}")

    if not os.path.exists(args.input):
        print(f"[!] Fout: Bestand niet gevonden: {args.input}")
        return

    items = []
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        items.append(json.loads(line))
                    except json.JSONDecodeError:
                        print("[!] Waarschuwing: Ongeldige JSON regel overgeslagen")
    except Exception as e:
        print(f"[!] Fout bij lezen bestand: {e}")
        return

    print(f"[+] {len(items)} items ingeladen. Bezig met sorteren...")

    sorted_items = sort_items(items, sort_priority)

    print(f"[+] Schrijven naar: {args.output}")
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            for item in sorted_items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"[+] Klaar! {len(sorted_items)} items gesorteerd opgeslagen.")
    except Exception as e:
        print(f"[!] Fout bij schrijven bestand: {e}")

if __name__ == "__main__":
    main()
