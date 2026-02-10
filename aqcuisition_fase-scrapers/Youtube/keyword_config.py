"""
Keyword configuration.

This file exposes `MUST_KEYWORDS` and `SHOULD_KEYWORDS`.
`SHOULD_KEYWORDS` is loaded from a CSV file when a file named
`should_keywords.csv` exists next to this module, or when a path is
passed to `load_should_keywords()`.

CSV format: simple single-column (or single-row) list of keywords. A
header named 'keyword' or 'keywords' is ignored. Empty cells are
skipped. Encoding `utf-8-sig` is used to tolerate BOMs.
"""

from pathlib import Path
import csv
from typing import List, Optional


# Woorden die ERIN MOETEN zitten (minstens 1)
MUST_KEYWORDS = [
    "ice",

]

def load_should_keywords(csv_path: Optional[str] = None) -> List[str]:
    """Load should-keywords from CSV.

    If `csv_path` is provided it is used first. Otherwise this function
    looks for `should_keywords.csv` in the same directory as this file.
    If no CSV is found the built-in defaults are returned.
    """
    candidates = []
    if csv_path:
        candidates.append(Path(csv_path))
    candidates.append(Path(__file__).parent / "should_keywords.csv")

    for p in candidates:
        try:
            p = Path(p)
            if not p.exists():
                continue
            keywords = []
            with p.open(newline="", encoding="utf-8-sig") as fh:
                reader = csv.reader(fh)
                for row in reader:
                    for cell in row:
                        val = cell.strip()
                        if not val:
                            continue
                        if val.lower() in ("keyword", "keywords"):
                            continue
                        keywords.append(val)

            # Remove duplicates while preserving order
            seen = set()
            out = []
            for k in keywords:
                if k not in seen:
                    seen.add(k)
                    out.append(k)
            return out
        except Exception:
            # If any error occurs reading this candidate, try the next one
            continue

    

# Module-level variable: will load CSV if present next to this file
SHOULD_KEYWORDS = load_should_keywords()

