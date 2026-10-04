import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.config import settings
from app.services.agentic.base_agent import BaseAgent
from app.services.agentic.scrapers.base_scraper import MATCH_THRESHOLD


class AggregatorAgent(BaseAgent):
    """
    Normalizes and aggregates raw scraper outputs.
    Ensures that unverified matches are excluded from pricing,
    uses allowlist for priceable sources, filters out-of-stock offers from price index,
    and applies MAD (Median Absolute Deviation) outlier removal for n >= 4 offers.
    """

    def __init__(self):
        super().__init__(
            role="AggregatorAgent",
            goal="Consolidate raw platform scraped data into a structured, verified dataset",
            available_tools=["price_normalizer", "match_verifier"]
        )

    async def aggregate(
        self,
        task_id: str,
        product_id: str,
        organization_id: str,
        raw_platform_results: List[Dict[str, Any]],
        expected_platforms: List[str]
    ) -> Dict[str, Any]:
        verified_results = {}
        missing_platforms = {}
        prices = []

        priceable_sources = {"live_scrape"}
        if getattr(settings, "MOCK_SCRAPING", False):
            priceable_sources.add("mock_simulation")

        for item in raw_platform_results:
            platform = item.get("platform", "Unknown")
            status = item.get("status", "failed")
            match_score = float(item.get("match_score", 0.0) or 0.0)
            data_source = item.get("data_source", "live_scrape")
            stock_status = item.get("stock_status", "in_stock")
            raw_price = float(item.get("price", 0.0) or 0.0)

            is_fallback = (data_source == "estimated_fallback")
            is_unverified = bool(item.get("unverified_match", False)) or (match_score < MATCH_THRESHOLD) or is_fallback
            is_priceable = (data_source in priceable_sources) and not is_unverified and (raw_price > 0)

            if status == "success" and is_priceable:
                clean_price = round(raw_price, 2)
                verified_results[platform] = {
                    "price": clean_price,
                    "currency": item.get("currency", "INR"),
                    "stock_status": stock_status,
                    "product_url": item.get("product_url", ""),
                    "product_title": self.sanitize_output(item.get("product_title", "")),
                    "scraped_at": item.get("scraped_at", datetime.now(timezone.utc).isoformat()),
                    "match_score": match_score,
                    "verified": True,
                    "data_source": data_source,
                    "is_estimated": False,
                    "latency_ms": item.get("latency_ms"),
                }
                # Only in-stock offers may contribute to the market price index
                if stock_status == "in_stock":
                    prices.append(clean_price)
            elif (data_source == "search_index_snippet" or is_fallback) and raw_price > 0:
                clean_price = round(raw_price, 2)
                verified_results[platform] = {
                    "price": clean_price,
                    "currency": item.get("currency", "INR"),
                    "stock_status": "unverified",
                    "product_url": item.get("product_url", ""),
                    "product_title": self.sanitize_output(item.get("product_title", "Unverified search snippet")),
                    "scraped_at": item.get("scraped_at", datetime.now(timezone.utc).isoformat()),
                    "match_score": match_score,
                    "verified": False,
                    "data_source": data_source,
                    "is_estimated": is_fallback,
                }
                missing_platforms[platform] = {
                    "reason": "estimated_fallback_excluded" if is_fallback else f"{data_source}_unverified_excluded",
                    "match_score": match_score,
                    "verified": False,
                    "data_source": data_source,
                }
            else:
                reason = item.get("reason", "low_match_score" if is_unverified else "unreachable")
                missing_platforms[platform] = {
                    "reason": reason,
                    "match_score": match_score,
                    "verified": False,
                    "data_source": data_source,
                }

        # Check for any expected platform completely absent from results
        for p in (expected_platforms or []):
            if p not in verified_results and p not in missing_platforms:
                missing_platforms[p] = {"reason": "no_response", "verified": False}

        # Apply MAD (Median Absolute Deviation) outlier removal if n >= 4 offers
        filtered_prices = list(prices)
        if len(prices) >= 4:
            med = statistics.median(prices)
            deviations = [abs(p - med) for p in prices]
            mad = statistics.median(deviations)
            if mad > 0:
                mad_threshold = 3.0 * 1.4826 * mad
                filtered_prices = [p for p in prices if abs(p - med) <= mad_threshold]

        # Use median for robust central tendency
        avg_price = round(float(statistics.median(filtered_prices)), 2) if filtered_prices else 0.0
        min_price = min(filtered_prices) if filtered_prices else 0.0
        max_price = max(filtered_prices) if filtered_prices else 0.0

        summary = {
            "verified_count": len(filtered_prices),
            "total_expected": len(expected_platforms or []),
            "average_price": avg_price,
            "min_price": min_price,
            "max_price": max_price,
            "index_method": "median",
            "min_evidence": 1,
            "platforms": verified_results,
            "missing_platforms": missing_platforms,
        }

        # Log reasoning trace
        self.record_decision(
            task_id=task_id,
            decision_point="Data Normalization",
            rationale=f"Verified {len(filtered_prices)} in-stock offers across target platforms. Outliers filtered: {len(prices) - len(filtered_prices)}.",
            action_taken=f"Calculated median market index ₹{avg_price:,.2f}" if avg_price else "Flagged zero verified market prices"
        )

        await self.emit_event(
            task_id=task_id,
            product_id=product_id,
            organization_id=organization_id,
            event_type="aggregation_completed",
            message=f"Aggregated {len(filtered_prices)} platform(s). Market index median: ₹{avg_price:,.2f}",
            payload=summary
        )

        return summary
