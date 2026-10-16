"""Receipt extraction accuracy.  Run from ml_service/:  python scripts/eval_receipt.py

For each data/eval/receipts/<name>.jpg|png add <name>.json:
  {"supplier": "ABC Distributors", "total": 1430000, "items": [{"name": "Rice", "quantity": 10, "line_total": 850000}]}
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.receipt_reader import read_receipt  # noqa: E402

DIR = Path(__file__).resolve().parent.parent / "data" / "eval" / "receipts"


async def main():
    images = sorted(p for p in DIR.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if not images:
        print("No receipt images in data/eval/receipts/ yet.")
    for img in images:
        expected = json.loads(img.with_suffix(".json").read_text())
        got = await read_receipt(img.read_bytes(), [])
        exp_items = {i["name"].lower(): i for i in expected["items"]}
        found = {i.name.lower(): i for i in got.items}
        hits = sum(1 for k, v in exp_items.items()
                   if k in found and found[k].quantity == v.get("quantity") and found[k].line_total == v.get("line_total"))
        print(f"{img.name}: items {hits}/{len(exp_items)} correct, total {'OK' if got.total == expected.get('total') else 'WRONG'}, "
              f"warnings={got.warnings}")


if __name__ == "__main__":
    asyncio.run(main())
