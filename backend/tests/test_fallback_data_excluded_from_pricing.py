import os
import sys
from pathlib import Path
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.agentic.aggregator_agent import AggregatorAgent


@pytest.mark.asyncio
async def test_estimated_fallback_data_excluded_from_pricing_calculations():
    """
    Problem 3: estimated_fallback results are NEVER used to compute pricing metrics.
    They must be excluded from price aggregations and labeled distinctly.
    """
    aggregator = AggregatorAgent()

    # 1 live scrape at 1000, 1 estimated fallback at 500
    raw_results = [
        {
            "platform": "Amazon.in",
            "status": "success",
            "price": 1000.0,
            "currency": "INR",
            "stock_status": "in_stock",
            "product_url": "https://amazon.in/item",
            "product_title": "Authentic Product",
            "match_score": 0.95,
            "data_source": "live_scrape",
            "unverified_match": False,
        },
        {
            "platform": "Flipkart",
            "status": "success",
            "price": 500.0,
            "currency": "INR",
            "stock_status": "in_stock",
            "product_url": "",
            "product_title": "Estimated Fallback Item",
            "match_score": 0.50,
            "data_source": "estimated_fallback",
            "unverified_match": False,
        },
    ]

    aggregated = await aggregator.aggregate(
        task_id="test-task-1",
        product_id="prod-1",
        organization_id="org-1",
        raw_platform_results=raw_results,
        expected_platforms=["Amazon.in", "Flipkart"]
    )

    # Only 1 verified price (the live_scrape price 1000.0) should be included
    assert aggregated["verified_count"] == 1
    assert aggregated["average_price"] == 1000.0
    assert aggregated["min_price"] == 1000.0
    assert aggregated["max_price"] == 1000.0

    # Amazon is verified and live
    amazon_res = aggregated["platforms"]["Amazon.in"]
    assert amazon_res["verified"] is True
    assert amazon_res["is_estimated"] is False
    assert amazon_res["data_source"] == "live_scrape"

    # Flipkart is estimated fallback and explicitly excluded from verified calculations
    flipkart_res = aggregated["platforms"]["Flipkart"]
    assert flipkart_res["verified"] is False
    assert flipkart_res["is_estimated"] is True
    assert flipkart_res["data_source"] == "estimated_fallback"
    assert "Flipkart" in aggregated["missing_platforms"]
    assert aggregated["missing_platforms"]["Flipkart"]["reason"] == "estimated_fallback_excluded"


@pytest.mark.asyncio
async def test_all_fallback_results_flagged_as_insufficient_live_evidence():
    """
    If all scrapers produce estimated_fallback data, pricing aggregator must flag no verified evidence.
    """
    aggregator = AggregatorAgent()
    raw_results = [
        {
            "platform": "Amazon.in",
            "status": "success",
            "price": 800.0,
            "currency": "INR",
            "stock_status": "in_stock",
            "product_url": "",
            "product_title": "Fallback",
            "match_score": 0.4,
            "data_source": "estimated_fallback",
            "unverified_match": False,
        }
    ]

    aggregated = await aggregator.aggregate(
        task_id="test-task-2",
        product_id="prod-2",
        organization_id="org-2",
        raw_platform_results=raw_results,
        expected_platforms=["Amazon.in"]
    )

    # 0 verified live prices
    assert aggregated["verified_count"] == 0
    assert aggregated["average_price"] == 0.0
    assert aggregated["platforms"]["Amazon.in"]["is_estimated"] is True
    assert aggregated["platforms"]["Amazon.in"]["verified"] is False
    assert aggregated["missing_platforms"]["Amazon.in"]["reason"] == "estimated_fallback_excluded"
