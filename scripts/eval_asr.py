"""Word error rate (WER) per language.  Run from ml_service/:  python scripts/eval_asr.py"""
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas import Language  # noqa: E402
from app.services.asr import transcribe  # noqa: E402

BASE = Path(__file__).resolve().parent.parent / "data" / "eval"


def words(s: str):
    return re.sub(r"[^\w\s']", "", s.lower()).split()


def edit_distance(a, b) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def main():
    errors, totals = defaultdict(int), defaultdict(int)
    with (BASE / "asr.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(line for line in f if not line.startswith("#")):
            hyp, _ = transcribe((BASE / "audio" / r["audio_file"]).read_bytes(), Language(r["language"]), r["audio_file"])
            ref = words(r["reference_transcript"])
            errors[r["language"]] += edit_distance(ref, words(hyp))
            totals[r["language"]] += len(ref)
    if not totals:
        print("No rows in data/eval/asr.csv yet. Record phrases and add them first.")
    for lang_code in totals:
        print(f"{lang_code}: WER {errors[lang_code] / totals[lang_code]:.1%} over {totals[lang_code]} words")


if __name__ == "__main__":
    main()
