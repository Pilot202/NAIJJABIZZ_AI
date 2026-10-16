"""Ask My Business: question -> real figures -> conversational answer.

Design rule: numbers are computed here from backend data; the LLM only phrases them. It never guesses.

TODO: upgrade the keyword router to LLM tool-calling (the LLM picks which fact functions to run) once
the basics work. For historical questions ("best sales day", "top 5 products") ask the backend engineer
to add aggregates to the snapshot or separate endpoints.
"""
from pathlib import Path
from typing import Any, Dict

import json

from app.schemas import AskResponse, BusinessSnapshot, Language
from app.services.forecasting import days_of_stock_left, health_score
from app.services.llm import LLMUnavailable, chat_text
from app.utils.naira import fmt_naira

_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "ask.md").read_text(encoding="utf-8")


def gather_facts(question: str, s: BusinessSnapshot) -> Dict[str, Any]:
    q = question.lower()
    facts: Dict[str, Any] = {}

    if any(w in q for w in ("left", "stock", "remaining", "restock")) or any(p.name.lower() in q for p in s.products):
        named = [p for p in s.products if p.name.lower() in q] or s.products
        facts["stock"] = [
            {"product": p.name, "unit": p.unit, "in_stock": p.stock,
             "days_left": days_of_stock_left(p.stock, p.avg_daily_sales)}
            for p in named
        ]
    if any(w in q for w in ("owe", "debt", "credit")):
        facts["debts"] = {"total": sum(d.amount for d in s.debts),
                          "customers": [d.model_dump() for d in s.debts]}
    if any(w in q for w in ("profit", "spend", "spent", "expense", "make", "made", "revenue", "sales", "afford")):
        facts["finance"] = {
            "revenue_this_month": s.revenue_this_month, "expenses_this_month": s.expenses_this_month,
            "profit_this_month": s.revenue_this_month - s.expenses_this_month,
            "revenue_last_month": s.revenue_last_month, "expenses_last_month": s.expenses_last_month,
            "profit_last_month": s.revenue_last_month - s.expenses_last_month,
        }
    if not facts:
        facts["overview"] = {"health_score": health_score(s), "products_tracked": len(s.products)}
    return facts


def _plain_answer(facts: Dict[str, Any]) -> str:
    """Offline fallback when no LLM is available (English only)."""
    parts = []
    for item in facts.get("stock", []):
        d = f" (about {item['days_left']:g} days)" if item["days_left"] is not None else ""
        parts.append(f"You have {item['in_stock']:g} {item['unit']} of {item['product']}{d}.")
    if "debts" in facts:
        parts.append(f"Customers owe you {fmt_naira(facts['debts']['total'])} in total.")
    if "finance" in facts:
        f = facts["finance"]
        parts.append(f"This month: revenue {fmt_naira(f['revenue_this_month'])}, expenses "
                     f"{fmt_naira(f['expenses_this_month'])}, profit {fmt_naira(f['profit_this_month'])}.")
    if "overview" in facts:
        parts.append(f"Your business health score is {facts['overview']['health_score']} out of 100.")
    return " ".join(parts)


async def ask(question: str, language: Language, snapshot: BusinessSnapshot) -> AskResponse:
    facts = gather_facts(question, snapshot)
    try:
        answer = await chat_text(
            _PROMPT.replace("{language}", language.value),
            json.dumps({"question": question, "facts": facts}, ensure_ascii=False, default=str),
        )
    except LLMUnavailable:
        answer = _plain_answer(facts)
    return AskResponse(answer=answer.strip(), language=language, facts_used=facts)
