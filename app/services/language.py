"""Language codes and confirmation messages in the merchant's language.

TODO (needs a native speaker): add reviewed Yoruba, Hausa and Igbo templates to TRANSLATIONS.
Until then every language falls back to the English template, so nothing breaks.
"""
from typing import Optional

from app.schemas import Entities, Intent, Language
from app.utils.naira import fmt_naira

# TRANSLATIONS[language][intent] = template using the same {placeholders} as the English ones below.
TRANSLATIONS: dict = {
    Language.yo: {},
    Language.ha: {},
    Language.ig: {},
}

_EN = {
    Intent.add_inventory: "Add {qty} {unit} of {product}{at}?",
    Intent.record_sale: "Record sale of {qty} {unit} of {product}{for_amount}?",
    Intent.record_expense: "Record expense of {amount} for {category}?",
    Intent.record_debt_payment: "Record a payment of {amount} from {customer}?",
    Intent.query: "{question}",
    Intent.unknown: "Sorry, I did not understand. Please say it again or type it.",
}


def _num(x: Optional[float]) -> str:
    if x is None:
        return "?"
    return str(int(x)) if float(x).is_integer() else str(x)


def _unit_label(unit: Optional[str], qty: Optional[float]) -> str:
    unit = unit or "unit"
    if qty is not None and qty != 1 and not unit.endswith("s"):
        return unit + "s"
    return unit


def confirmation_message(intent: Intent, e: Entities, language: Language, transcript: str = "") -> str:
    template = TRANSLATIONS.get(language, {}).get(intent) or _EN[intent]
    return template.format(
        qty=_num(e.quantity),
        unit=_unit_label(e.unit, e.quantity),
        product=e.matched_product_name or e.product or "item",
        at=f" at {fmt_naira(e.unit_cost)} each" if e.unit_cost else "",
        for_amount=f" for {fmt_naira(e.total_amount)}" if e.total_amount else "",
        amount=fmt_naira(e.total_amount),
        category=e.category or "other",
        customer=e.customer or "the customer",
        question=transcript,
    )
