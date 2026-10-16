"""Runs with LLM_BACKEND=mock (the default), so these test the rule-based fallback and post-processing."""
import asyncio

from app.schemas import CatalogueItem, Intent, Language
from app.services.intent_parser import parse_command
from app.services.product_matcher import match_product

CATALOGUE = [CatalogueItem(id="p1", name="Rice"), CatalogueItem(id="p2", name="Coca-Cola"),
             CatalogueItem(id="p3", name="Indomie Noodles")]


def run(text):
    return asyncio.run(parse_command(text, Language.en, CATALOGUE))


def test_add_inventory():
    r = run("I just bought 50 bags of rice for 4 million naira")
    assert r.intent == Intent.add_inventory
    assert r.entities.quantity == 50
    assert r.entities.total_amount == 4_000_000
    assert r.entities.unit_cost == 80_000
    assert r.entities.matched_product_id == "p1"
    assert "50 bags of Rice" in r.confirmation_message
    assert not r.missing_fields


def test_sale_with_word_number():
    r = run("I just sold five bottles of Coke")
    assert r.intent == Intent.record_sale
    assert r.entities.quantity == 5
    assert r.entities.matched_product_name == "Coca-Cola"


def test_expense():
    r = run("I paid 15,000 for transport")
    assert r.intent == Intent.record_expense
    assert r.entities.total_amount == 15_000
    assert r.entities.category == "transport"


def test_query():
    assert run("How much rice do I have left?").intent == Intent.query


def test_unknown_is_low_confidence():
    r = run("hello there")
    assert r.intent == Intent.unknown and r.low_confidence


def test_missing_fields_flagged():
    r = run("I bought some rice")
    assert r.low_confidence and "quantity" in r.missing_fields


def test_matcher():
    assert match_product("peak milk", [CatalogueItem(id="x", name="Peak Milk")]).id == "x"
    assert match_product("zzzz", CATALOGUE) is None
