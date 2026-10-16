import pytest

from app.utils.naira import parse_naira, parse_quantity


@pytest.mark.parametrize("text,expected", [
    ("4 million naira", 4_000_000),
    ("120k", 120_000),
    ("₦80,000", 80_000),
    ("N1.5m", 1_500_000),
    ("120,000 naira", 120_000),
    ("I just bought 50 bags of rice for 4 million naira", 4_000_000),  # not 50
    ("I paid 15,000 for transport", 15_000),
    ("no numbers here", None),
])
def test_parse_naira(text, expected):
    assert parse_naira(text) == expected


@pytest.mark.parametrize("token,expected", [("20", 20), ("five", 5), ("dozen", 12), ("banana", None)])
def test_parse_quantity(token, expected):
    assert parse_quantity(token) == expected
