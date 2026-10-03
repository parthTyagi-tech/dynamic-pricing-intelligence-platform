import uuid
import pytest
from app.services.agentic.aggregator_agent import AggregatorAgent
from app.services.agentic.scrapers.base_scraper import BaseScraperAgent


@pytest.mark.asyncio
async def test_out_of_stock_cheap_listing_does_not_pollute_price_index():
    """An out-of-stock cheap offer is preserved in platforms but excluded from the price index."""
    agent = AggregatorAgent()
    task_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())

    raw_results = [
        {
            "platform": "Amazon",
            "status": "success",
            "price": 1000.0,
            "stock_status": "in_stock",
            "match_score": 0.95,
            "data_source": "live_scrape",
            "unverified_match": False
        },
        {
            "platform": "Flipkart",
            "status": "success",
            "price": 1020.0,
            "stock_status": "in_stock",
            "match_score": 0.92,
            "data_source": "live_scrape",
            "unverified_match": False
        },
        {
            "platform": "Blinkit",
            "status": "success",
            "price": 200.0,  # Extreme cheap liquidation price, but out of stock!
            "stock_status": "out_of_stock",
            "match_score": 0.90,
            "data_source": "live_scrape",
            "unverified_match": False
        }
    ]

    summary = await agent.aggregate(task_id, product_id, org_id, raw_results, ["Amazon", "Flipkart", "Blinkit"])

    # Invariant: Blinkit is listed in platforms dict
    assert "Blinkit" in summary["platforms"]
    assert summary["platforms"]["Blinkit"]["stock_status"] == "out_of_stock"
    assert summary["platforms"]["Blinkit"]["price"] == 200.0

    # Invariant: Blinkit price does NOT change the price index (median of 1000.0 and 1020.0 is 1010.0)
    assert summary["verified_count"] == 2
    assert summary["average_price"] == 1010.0
    assert summary["min_price"] == 1000.0
    assert summary["max_price"] == 1020.0
    assert summary["index_method"] == "median"


@pytest.mark.asyncio
async def test_mad_outlier_removal_drops_extreme_outlier():
    """For n >= 4 offers, [1000, 1010, 990, 1005, 1] removes the extreme outlier 1."""
    agent = AggregatorAgent()
    task_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())

    raw_results = [
        {"platform": "P1", "status": "success", "price": 1000.0, "stock_status": "in_stock", "match_score": 0.95, "data_source": "live_scrape"},
        {"platform": "P2", "status": "success", "price": 1010.0, "stock_status": "in_stock", "match_score": 0.95, "data_source": "live_scrape"},
        {"platform": "P3", "status": "success", "price": 990.0, "stock_status": "in_stock", "match_score": 0.95, "data_source": "live_scrape"},
        {"platform": "P4", "status": "success", "price": 1005.0, "stock_status": "in_stock", "match_score": 0.95, "data_source": "live_scrape"},
        {"platform": "P5", "status": "success", "price": 1.0, "stock_status": "in_stock", "match_score": 0.95, "data_source": "live_scrape"},
    ]

    summary = await agent.aggregate(task_id, product_id, org_id, raw_results, ["P1", "P2", "P3", "P4", "P5"])

    # Invariant: 1.0 is dropped via MAD outlier removal; remaining offers: [990, 1000, 1005, 1010]
    assert summary["verified_count"] == 4
    assert summary["min_price"] == 990.0
    assert summary["max_price"] == 1010.0
    # Median of [990, 1000, 1005, 1010] is (1000 + 1005) / 2 = 1002.5
    assert summary["average_price"] == 1002.5


@pytest.mark.asyncio
async def test_search_index_snippet_is_excluded_from_price_index():
    """Offers from search_index_snippet are excluded from pricing and flagged as unverified."""
    agent = AggregatorAgent()
    task_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())

    raw_results = [
        {
            "platform": "Amazon",
            "status": "success",
            "price": 1500.0,
            "stock_status": "in_stock",
            "match_score": 0.95,
            "data_source": "live_scrape",
        },
        {
            "platform": "SearchSnippet",
            "status": "success",
            "price": 1200.0,
            "stock_status": "in_stock",
            "match_score": 0.85,
            "data_source": "search_index_snippet",
        }
    ]

    summary = await agent.aggregate(task_id, product_id, org_id, raw_results, ["Amazon", "SearchSnippet"])

    # Invariant: SearchSnippet is excluded from prices list and price index
    assert summary["verified_count"] == 1
    assert summary["average_price"] == 1500.0
    assert "SearchSnippet" in summary["missing_platforms"]
    assert summary["platforms"]["SearchSnippet"]["verified"] is False
    assert summary["platforms"]["SearchSnippet"]["data_source"] == "search_index_snippet"
