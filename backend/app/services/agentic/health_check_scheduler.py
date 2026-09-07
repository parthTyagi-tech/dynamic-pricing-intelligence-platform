import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.extensions import db
from app.models.scraper_reliability import CircuitState, ScraperHealthCheckLog, ScraperReliability
from app.services.agentic.scrapers.platform_scrapers import PLATFORM_SCRAPERS, get_scraper_for_platform

logger = logging.getLogger(__name__)

CANARY_PRODUCTS: Dict[str, Dict[str, Any]] = {
    "Amazon.in": {"id": "canary-amazon", "name": "boAt BassHeads 100 Wired Earphones", "brand": "boAt", "category": "electronics", "current_price": 399.0},
    "Flipkart": {"id": "canary-flipkart", "name": "boAt BassHeads 100 Wired Earphones", "brand": "boAt", "category": "electronics", "current_price": 399.0},
    "Myntra": {"id": "canary-myntra", "name": "Roadster Men Solid Pure Cotton T-shirt", "brand": "Roadster", "category": "fashion", "current_price": 499.0},
    "Ajio": {"id": "canary-ajio", "name": "Teamspirit Men Graphic Print T-shirt", "brand": "Teamspirit", "category": "fashion", "current_price": 449.0},
    "Nykaa": {"id": "canary-nykaa", "name": "Maybelline New York Colossal Kajal", "brand": "Maybelline", "category": "beauty", "current_price": 199.0},
    "Purplle": {"id": "canary-purplle", "name": "Good Vibes Rosehip Serum", "brand": "Good Vibes", "category": "beauty", "current_price": 249.0},
    "BigBasket": {"id": "canary-bigbasket", "name": "Fortune Sunlite Refined Sunflower Oil", "brand": "Fortune", "category": "grocery", "current_price": 140.0},
    "JioMart": {"id": "canary-jiomart", "name": "Tata Salt Iodized Salt 1 kg", "brand": "Tata", "category": "grocery", "current_price": 28.0},
    "Pepperfry": {"id": "canary-pepperfry", "name": "Solid Wood Study Desk Chair", "brand": "Woodsworth", "category": "furniture", "current_price": 3499.0},
    "Urban Ladder": {"id": "canary-urbanladder", "name": "Solid Wood Bookshelf Rack", "brand": "Urban Ladder", "category": "furniture", "current_price": 4999.0},
    "1mg": {"id": "canary-1mg", "name": "Dettol Antiseptic Liquid 550ml", "brand": "Dettol", "category": "pharmacy", "current_price": 215.0},
    "PharmEasy": {"id": "canary-pharmeasy", "name": "Volini Pain Relief Gel 75g", "brand": "Volini", "category": "pharmacy", "current_price": 175.0},
    "CaratLane": {"id": "canary-caratlane", "name": "14KT Yellow Gold Diamond Stud", "brand": "CaratLane", "category": "jewelry", "current_price": 8999.0},
    "Tanishq": {"id": "canary-tanishq", "name": "18KT Gold Pendant with Chain", "brand": "Tanishq", "category": "jewelry", "current_price": 12999.0},
}


async def run_single_canary_check(platform_name: str, organization_id: str = "system") -> Dict[str, Any]:
    """
    Executes a single canary probe against a known product for the platform.
    Updates ScraperReliability and logs to ScraperHealthCheckLog.
    """
    agent = get_scraper_for_platform(platform_name)
    canary_item = CANARY_PRODUCTS.get(platform_name, {
        "id": f"canary-{platform_name.lower().replace(' ', '-')}",
        "name": "Standard Benchmark Item",
        "brand": "",
        "category": "general",
        "current_price": 1000.0
    })

    task_id = f"canary-{uuid.uuid4().hex[:8]}"
    start_time = time.perf_counter()

    try:
        result = await agent.scrape(
            task_id=task_id,
            product=canary_item,
            organization_id=organization_id,
            simulate_failure=False
        )
        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 1)

        is_success = (
            result.get("status") == "success"
            and not result.get("unverified_match", False)
            and float(result.get("price", 0.0)) > 0
        )

        now = datetime.now(timezone.utc)
        rel = ScraperReliability.query.filter_by(platform=platform_name).first()
        if not rel:
            rel = ScraperReliability(platform=platform_name)
            db.session.add(rel)

        if is_success:
            status_str = "success"
            rel.circuit_state = CircuitState.CLOSED
            rel.failure_count_last_hour = 0
            rel.backoff_minutes = 15
            rel.last_successful_scrape_at = now
        else:
            status_str = "failed"
            rel.failure_count_last_hour = (rel.failure_count_last_hour or 0) + 1
            rel.last_failure_at = now
            if rel.circuit_state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
                rel.circuit_state = CircuitState.OPEN
                rel.circuit_opened_at = now
                rel.backoff_minutes = min(240, (rel.backoff_minutes or 15) * 2)
            elif rel.failure_count_last_hour >= 3:
                rel.circuit_state = CircuitState.OPEN
                rel.circuit_opened_at = now
                rel.backoff_minutes = max(15, rel.backoff_minutes or 15)

        # Record health check log
        log_entry = ScraperHealthCheckLog(
            id=str(uuid.uuid4()),
            platform=platform_name,
            status=status_str,
            latency_ms=latency_ms,
            source="health_check",
            details={
                "price": result.get("price"),
                "match_score": result.get("match_score"),
                "reason": result.get("reason"),
                "data_source": result.get("data_source", "canary"),
            },
            checked_at=now
        )
        db.session.add(log_entry)
        db.session.commit()

        return {
            "platform": platform_name,
            "status": status_str,
            "latency_ms": latency_ms,
            "circuit_state": rel.circuit_state,
            "checked_at": now.isoformat(),
        }

    except Exception as e:
        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 1)
        now = datetime.now(timezone.utc)
        logger.error(f"[CanaryHealthCheck] Error checking {platform_name}: {e}")

        rel = ScraperReliability.query.filter_by(platform=platform_name).first()
        if not rel:
            rel = ScraperReliability(platform=platform_name)
            db.session.add(rel)

        rel.failure_count_last_hour = (rel.failure_count_last_hour or 0) + 1
        rel.last_failure_at = now
        rel.last_failure_reason = str(e)[:255]
        if rel.circuit_state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
            rel.circuit_state = CircuitState.OPEN
            rel.circuit_opened_at = now
            rel.backoff_minutes = min(240, (rel.backoff_minutes or 15) * 2)
        elif rel.failure_count_last_hour >= 3:
            rel.circuit_state = CircuitState.OPEN
            rel.circuit_opened_at = now
            rel.backoff_minutes = max(15, rel.backoff_minutes or 15)

        log_entry = ScraperHealthCheckLog(
            id=str(uuid.uuid4()),
            platform=platform_name,
            status="failed",
            latency_ms=latency_ms,
            source="health_check",
            details={"error": str(e)},
            checked_at=now
        )
        db.session.add(log_entry)
        db.session.commit()

        return {
            "platform": platform_name,
            "status": "failed",
            "latency_ms": latency_ms,
            "error": str(e),
            "circuit_state": rel.circuit_state,
            "checked_at": now.isoformat(),
        }


async def run_all_canary_health_checks(organization_id: str = "system") -> List[Dict[str, Any]]:
    """Runs canary health checks across all registered platform scrapers."""
    results = []
    for platform in sorted(PLATFORM_SCRAPERS.keys()):
        res = await run_single_canary_check(platform, organization_id)
        results.append(res)
    return results
