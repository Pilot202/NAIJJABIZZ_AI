"""Fuzzy-match what the merchant said ("coke", "peak milk") to a product in their catalogue."""
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional

from app.schemas import CatalogueItem

# Spoken name -> canonical name. Extend with real market names (and Yoruba/Hausa/Igbo product names).
ALIASES = {
    "coke": "coca-cola",
    "cocacola": "coca-cola",
    "indomie": "indomie noodles",
    "noodles": "indomie noodles",
    "milk": "peak milk",
    "oil": "vegetable oil",
}


@dataclass
class Match:
    id: str
    name: str
    score: float


def _norm(s: str) -> str:
    return " ".join(s.lower().replace("-", " ").split())


def match_product(query: Optional[str], catalogue: List[CatalogueItem], cutoff: float = 0.6) -> Optional[Match]:
    if not query or not catalogue:
        return None
    q = _norm(query)
    q = _norm(ALIASES.get(q, q))
    best: Optional[Match] = None
    for item in catalogue:
        name = _norm(item.name)
        score = SequenceMatcher(None, q, name).ratio()
        if q in name or name in q:  # "rice" vs "ofada rice"
            score = max(score, 0.85)
        if best is None or score > best.score:
            best = Match(item.id, item.name, score)
    return best if best and best.score >= cutoff else None
