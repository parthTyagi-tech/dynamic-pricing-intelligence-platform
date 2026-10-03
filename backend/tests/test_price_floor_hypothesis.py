from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from app.utils.security_guardrails import compute_price_floor, effective_min_margin_pct


@given(
    cost=st.floats(min_value=1.0, max_value=1_000_000.0),
    pct=st.floats(min_value=0.0, max_value=90.0),
)
def test_floor_never_below_cost_property(cost: float, pct: float):
    floor = compute_price_floor(cost, pct)
    # The floor price must strictly equal or exceed the base cost of goods
    assert floor >= round(cost, 2)


def test_canonical_margin_floor_units():
    # Unit test asserting canonical benchmark from prompt
    assert compute_price_floor(65000.0, 10.0) == 71500.0
    assert compute_price_floor(100.0, 0.0) == 100.0
    assert compute_price_floor(200.0, 15.0) == 230.0


def test_effective_min_margin_pct():
    # Stricter of product-level % and org-level fraction (0.15 -> 15.0)
    assert effective_min_margin_pct(10.0, 0.15) == 15.0
    assert effective_min_margin_pct(20.0, 0.15) == 20.0
    assert effective_min_margin_pct(None, 0.12) == 12.0
    assert effective_min_margin_pct(14.5, None) == 14.5
    assert effective_min_margin_pct(None, None) == 0.0


def test_floor_invalid_inputs_raise():
    with pytest.raises(ValueError):
        compute_price_floor(-10.0, 10.0)

    with pytest.raises(ValueError):
        compute_price_floor(100.0, None)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        compute_price_floor(None, 10.0)  # type: ignore[arg-type]
