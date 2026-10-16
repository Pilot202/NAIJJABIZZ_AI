"""Intent/entity accuracy per language.  Run from ml_service/:  python scripts/eval_intent.py"""
import asyncio
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas import Language  # noqa: E402
from app.services.intent_parser import parse_command  # noqa: E402

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "eval" / "phrases.csv"


def rows():
    with CSV_PATH.open(encoding="utf-8") as f:
        yield from csv.DictReader(line for line in f if not line.startswith("#"))


async def main():
    stats = defaultdict(lambda: {"n": 0, "intent": 0, "product": 0, "qty": 0, "total": 0, "n_prod": 0, "n_qty": 0, "n_tot": 0})
    for r in rows():
        p = await parse_command(r["text"], Language(r["language"]), [])
        s = stats[r["language"]]
        s["n"] += 1
        s["intent"] += p.intent.value == r["expected_intent"]
        if r["expected_product"]:
            s["n_prod"] += 1
            s["product"] += (p.entities.product or "").lower() == r["expected_product"].lower()
        if r["expected_quantity"]:
            s["n_qty"] += 1
            s["qty"] += p.entities.quantity == float(r["expected_quantity"])
        if r["expected_total"]:
            s["n_tot"] += 1
            s["total"] += p.entities.total_amount == float(r["expected_total"])

    def pct(a, b):
        return f"{a / b:.0%}" if b else "n/a"

    print(f"{'lang':<6}{'n':>4}{'intent':>9}{'product':>9}{'qty':>7}{'amount':>8}")
    for lang_code, s in stats.items():
        print(f"{lang_code:<6}{s['n']:>4}{pct(s['intent'], s['n']):>9}{pct(s['product'], s['n_prod']):>9}"
              f"{pct(s['qty'], s['n_qty']):>7}{pct(s['total'], s['n_tot']):>8}")


if __name__ == "__main__":
    asyncio.run(main())
