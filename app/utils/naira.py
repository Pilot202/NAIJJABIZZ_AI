"""Rule-based parsing of naira amounts and spoken numbers.

Amounts are parsed with rules, not the LLM, because LLMs misread large numbers.
Handles: "4 million naira", "120k", "₦80,000", "N1.5m", "120,000 naira".
"""
import re
from typing import Optional, Union

_MULT = {
    "k": 1_000,
    "thousand": 1_000,
    "m": 1_000_000,
    "million": 1_000_000,
    "b": 1_000_000_000,
    "billion": 1_000_000_000,
}

_RE = re.compile(
    r"(?<![A-Za-z])"
    r"(?P<cur>₦|ngn\s*|n(?=\d))?\s*"
    r"(?P<num>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<mult>billion|million|thousand|b|m|k)?"
    r"(?![A-Za-z])",
    re.IGNORECASE,
)
_NAIRA_AFTER = re.compile(r"\s*(naira|ngn)\b", re.IGNORECASE)

_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": 100, "a dozen": 12, "dozen": 12,
}


def _clean(value: float) -> Union[int, float]:
    return int(value) if float(value).is_integer() else value


def parse_naira(text: str) -> Optional[Union[int, float]]:
    """Return the money amount in the text, or None.

    Preference order: an amount marked as money (₦, N, 'naira', or k/m/million suffix);
    otherwise the largest number. Quantities like "50 bags" are therefore not mistaken for prices
    when a marked amount is present.
    """
    candidates = []  # (value, marked)
    for m in _RE.finditer(text):
        value = float(m.group("num").replace(",", ""))
        mult = m.group("mult")
        marked = bool(m.group("cur")) or bool(mult) or bool(_NAIRA_AFTER.match(text, m.end()))
        if mult:
            value *= _MULT[mult.lower()]
        candidates.append((value, marked))
    if not candidates:
        return None
    marked_values = [v for v, marked in candidates if marked]
    chosen = marked_values[0] if marked_values else max(v for v, _ in candidates)
    return _clean(chosen)


def parse_quantity(token: str) -> Optional[Union[int, float]]:
    """'20' -> 20, 'five' -> 5, 'a dozen' -> 12. TODO: compound words ('twenty five'), Pidgin/local numerals."""
    token = token.strip().lower()
    if re.fullmatch(r"\d+(?:\.\d+)?", token):
        return _clean(float(token))
    return _WORDS.get(token)


def fmt_naira(amount: Optional[float]) -> str:
    if amount is None:
        return "₦?"
    return f"₦{amount:,.0f}"
