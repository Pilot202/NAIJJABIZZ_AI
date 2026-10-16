"""Transcript/text -> ActionProposal (intent + entities + confidence + confirmation message).

Pipeline: LLM extracts intent/entities -> rules fix the numbers (naira.py) -> product matcher -> confidence.
If the LLM is unavailable (LLM_BACKEND=mock) a small English rule-based parser keeps the service usable.

TODO (experiment): for Yoruba/Hausa/Igbo compare (a) parsing the local text directly with N-ATLaS-LLM vs
(b) translating to English first, then parsing. Pick whichever scores better in scripts/eval_intent.py.
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.config import settings
from app.schemas import ActionProposal, CatalogueItem, Entities, Intent, Language
from app.services import language as lang
from app.services.llm import LLMUnavailable, chat_json
from app.services.product_matcher import match_product
from app.utils.naira import parse_naira, parse_quantity

_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "intent_parser.md").read_text(encoding="utf-8")

REQUIRED: Dict[Intent, List[str]] = {
    Intent.add_inventory: ["product", "quantity"],
    Intent.record_sale: ["product", "quantity"],
    Intent.record_expense: ["total_amount"],
    Intent.record_debt_payment: ["customer", "total_amount"],
    Intent.query: [],
    Intent.unknown: [],
}

_ITEM_RE = re.compile(
    r"(?P<qty>\d+(?:\.\d+)?|[a-z]+)\s+"
    r"(?P<unit>bags?|cartons?|bottles?|packs?|packets?|pieces?|units?|crates?|tins?|kegs?)\s+"
    r"(?:of\s+)?(?P<product>[a-z][a-z\- ]*?)(?=\s+(?:for|to|at|on)\b|[.,?!]|$)",
    re.IGNORECASE,
)
_QUESTION_START = re.compile(r"^\s*(how|what|which|who|when|why|can i|should i|do i|show|tell)\b", re.IGNORECASE)


def _rule_parse(text: str) -> Tuple[Intent, Entities, float]:
    t = text.strip()
    low = t.lower()
    e = Entities()

    if t.endswith("?") or _QUESTION_START.match(t):
        return Intent.query, e, 0.5

    if re.search(r"\b(sold|selling)\b", low):
        intent = Intent.record_sale
    elif re.search(r"\b(bought|purchased|restocked|add(ed)?\b.*\binventory)", low):
        intent = Intent.add_inventory
    elif re.search(r"\b(paid|spent|expense)\b", low):
        intent = Intent.record_expense
    else:
        return Intent.unknown, e, 0.2

    m = _ITEM_RE.search(t)
    if m:
        qty = parse_quantity(m.group("qty"))
        if qty is not None:
            e.quantity = qty
            e.unit = m.group("unit").lower().rstrip("s")
            e.product = m.group("product").strip().lower()
    if intent == Intent.record_expense:
        cat = re.search(r"\bfor\s+([a-z][a-z ]*)$", low)
        e.category = cat.group(1).strip() if cat else None
    return intent, e, 0.55


async def _llm_parse(text: str, language: Language, catalogue: List[CatalogueItem]) -> Tuple[Intent, Entities, float]:
    user = json.dumps(
        {"language": language.value, "command": text, "known_products": [c.name for c in catalogue]},
        ensure_ascii=False,
    )
    data = await chat_json(_PROMPT, user)
    try:
        intent = Intent(data.get("intent", "unknown"))
    except ValueError:
        intent = Intent.unknown
    raw = data.get("entities") or {}
    allowed = {k: v for k, v in raw.items() if k in Entities.model_fields}
    return intent, Entities(**allowed), float(data.get("confidence", 0.5))


async def parse_command(text: str, language: Language, catalogue: List[CatalogueItem]) -> ActionProposal:
    try:
        intent, entities, confidence = await _llm_parse(text, language, catalogue)
    except LLMUnavailable:
        intent, entities, confidence = _rule_parse(text)

    # Numbers come from rules, not the LLM.
    rule_amount = parse_naira(text) if intent != Intent.query else None
    if rule_amount is not None and intent in (Intent.add_inventory, Intent.record_sale, Intent.record_expense,
                                              Intent.record_debt_payment):
        entities.total_amount = float(rule_amount)
    if intent == Intent.add_inventory and entities.total_amount and entities.quantity:
        entities.unit_cost = round(entities.total_amount / entities.quantity, 2)

    # Product matching against the merchant's catalogue.
    match = match_product(entities.product, catalogue)
    if match:
        entities.matched_product_id, entities.matched_product_name = match.id, match.name

    # Confidence: cap it when required fields are missing.
    missing = [f for f in REQUIRED[intent] if getattr(entities, f) in (None, "")]
    if missing:
        confidence = min(confidence, 0.5)
    if intent == Intent.unknown:
        confidence = min(confidence, 0.3)

    return ActionProposal(
        intent=intent,
        language=language,
        transcript=text,
        entities=entities,
        confidence=round(confidence, 2),
        low_confidence=confidence < settings.min_confidence or bool(missing),
        missing_fields=missing,
        confirmation_message=lang.confirmation_message(intent, entities, language, transcript=text),
    )
