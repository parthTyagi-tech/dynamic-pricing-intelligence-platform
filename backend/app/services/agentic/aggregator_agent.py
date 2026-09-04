from datetime import datetime, timezone
from typing import Any, Dict, List

from app.services.agentic.base_agent import BaseAgent

MATCH_THRESHOLD = 0.75


class AggregatorAgent(BaseAgent):
    """
    Normalizes and aggregates raw scraper outputs.
    Ensures that unverified matches (Gap #2) are excluded from pricing,
    and missing platforms are explicitly attributed rather than dropped silently.
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

        for item in raw_platform_results:
            platform = item.get("platform", "Unknown")
            status = item.get("status", "failed")
            match_score = float(item.get("match_score", 0.0))
            is_unverified = item.get("unverified_match", False) or match_score < MATCH_THRESHOLD

            if status == "success" and not is_unverified and float(item.get("price", 0.0)) > 0:
                clean_price = round(float(item["price"]), 2)
                prices.append(clean_price)
                verified_results[platform] = {
                    "price": clean_price,
                    "currency": item.get("currency", "INR"),
                    "stock_status": item.get("stock_status", "in_stock"),
                    "product_url": item.get("product_url", ""),
                    "product_title": self.sanitize_output(item.get("product_title", "")),
                    "scraped_at": item.get("scraped_at", datetime.now(timezone.utc).isoformat()),
                    "match_score": match_score,
                    "verified": True,
                }
            else:
                reason = item.get("reason", "low_match_score" if is_unverified else "unreachable")
                missing_platforms[platform] = {
                    "reason": reason,
                    "match_score": match_score,
                    "verified": False,
                }

        # Check for any expected platform completely absent from results
        for p in expected_platforms:
            if p not in verified_results and p not in missing_platforms:
                missing_platforms[p] = {"reason": "no_response", "verified": False}

        avg_price = round(sum(prices) / len(prices), 2) if prices else 0.0
        min_price = min(prices) if prices else 0.0
        max_price = max(prices) if prices else 0.0

        summary = {
            "verified_count": len(prices),
            "total_expected": len(expected_platforms),
            "average_price": avg_price,
            "min_price": min_price,
            "max_price": max_price,
            "platforms": verified_results,
            "missing_platforms": missing_platforms,
        }

        # Log reasoning trace
        self.record_decision(
            task_id=task_id,
            decision_point="Data Normalization",
            rationale=f"Verified {len(prices)} of {len(expected_platforms)} target platforms. Excluded unverified matches.",
            action_taken=f"Calculated market index average ₹{avg_price:,.2f}" if avg_price else "Flagged zero verified market prices"
        )

        await self.emit_event(
            task_id=task_id,
            product_id=product_id,
            organization_id=organization_id,
            event_type="aggregation_completed",
            message=f"Aggregated {len(prices)} platform(s). Market index average: ₹{avg_price:,.2f}",
            payload=summary
        )

        return summary
