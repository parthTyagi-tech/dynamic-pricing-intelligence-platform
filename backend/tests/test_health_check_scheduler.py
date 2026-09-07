import os
import sys
from pathlib import Path
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("FLASK_ENV", "testing")

from run import app
from app.extensions import db
from app.models.recommendation import PricingRecommendation
from app.models.scraper_reliability import ScraperReliability, ScraperHealthCheckLog
from app.services.agentic.health_check_scheduler import run_single_canary_check, CANARY_PRODUCTS
from app.services.agentic.scrapers.platform_scrapers import AmazonScraperAgent


@pytest.mark.asyncio
async def test_canary_run_updates_reliability_without_pricing_recommendation(monkeypatch):
    """
    Problem 5: Scheduled canary reachability probes must:
    1. Update ScraperReliability (circuit breaker state, last_successful_scrape_at).
    2. Log to ScraperHealthCheckLog with source="health_check".
    3. NEVER create a user-visible PricingRecommendation row.
    """
    with app.app_context():
        # Count existing recommendations
        initial_recs_count = PricingRecommendation.query.count()

        platform = "Amazon.in"

        # Mock the scraper scrape method to return reachability success without external network hit
        async def fake_scrape(*args, **kwargs):
            return {
                "platform": platform,
                "status": "success",
                "price": 999.0,
                "currency": "INR",
                "stock_status": "in_stock",
                "product_url": "https://amazon.in/canary",
                "product_title": "Canary Probe Item",
                "match_score": 0.99,
                "data_source": "live_scrape",
                "unverified_match": False,
            }

        monkeypatch.setattr(AmazonScraperAgent, "scrape", fake_scrape)

        result = await run_single_canary_check(platform, organization_id="test-org")

        assert result["platform"] == platform
        assert result["status"] == "success"

        # 1. ScraperReliability was updated
        rel = ScraperReliability.query.filter_by(platform=platform).first()
        assert rel is not None
        assert rel.circuit_state == "closed"
        assert rel.failure_count_last_hour == 0
        assert rel.last_successful_scrape_at is not None

        # 2. Health check log created
        log = ScraperHealthCheckLog.query.filter_by(platform=platform).order_by(ScraperHealthCheckLog.checked_at.desc()).first()
        assert log is not None
        assert log.status == "success"
        assert log.source == "health_check"

        # 3. No PricingRecommendation was created
        assert PricingRecommendation.query.count() == initial_recs_count
