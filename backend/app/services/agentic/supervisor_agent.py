import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.extensions import db
from app.models.pricing_recommendation import PricingRecommendation, RecommendationStatus
from app.models.product import Product
from app.models.scraper_reliability import CircuitState, ScraperReliability
from app.services.agentic.aggregator_agent import AggregatorAgent
from app.services.agentic.base_agent import BaseAgent
from app.services.agentic.pricing_reasoning_agent import PricingReasoningAgent
from app.services.agentic.scrapers.platform_scrapers import get_scraper_for_platform
from app.services.task_state.task_manager import get_task_manager

logger = logging.getLogger(__name__)

CATEGORY_PLATFORMS = {
    "fashion": ["Myntra", "Ajio"],
    "apparel": ["Myntra", "Ajio"],
    "electronics": ["Amazon.in", "Flipkart"],
    "beauty": ["Nykaa", "Purplle"],
    "personal_care": ["Nykaa", "Purplle"],
    "grocery": ["BigBasket", "JioMart"],
    "daily_essentials": ["BigBasket", "JioMart"],
    "home_goods": ["Pepperfry", "Urban Ladder"],
    "furniture": ["Pepperfry", "Urban Ladder"],
    "pharmacy": ["1mg", "PharmEasy"],
    "health": ["1mg", "PharmEasy"],
    "jewelry": ["CaratLane", "Tanishq"],
    "books": ["Amazon.in", "Flipkart"],
    "sports": ["Amazon.in", "Flipkart"],
    "general": ["Amazon.in", "Flipkart"],
}


class SupervisorAgent(BaseAgent):
    """
    Supervisor / Orchestrator Agent.
    - Idempotency Caching (Gap #6)
    - Circuit Breaker Enforcement (Gap #7)
    - Autonomous Multi-Platform Coordination
    - Dynamic Failure Adaptation (Partial data reasoning)
    """

    def __init__(self):
        super().__init__(
            role="SupervisorAgent",
            goal="Coordinate autonomous sub-agents to deliver a reliable, verified pricing recommendation",
            available_tools=["idempotency_checker", "circuit_breaker", "platform_router", "failure_evaluator"]
        )
        self.aggregator = AggregatorAgent()
        self.pricing_reasoner = PricingReasoningAgent()

    def resolve_platforms(self, category: str) -> List[str]:
        """Resolves target e-commerce platforms based on product category."""
        clean_cat = (category or "general").strip().lower().replace(" ", "_")
        for key, platforms in CATEGORY_PLATFORMS.items():
            if key in clean_cat:
                return platforms
        return CATEGORY_PLATFORMS["general"]

    def check_circuit_breaker(self, platform: str) -> bool:
        """
        Gap #7: Checks if platform's circuit is OPEN.
        Returns True if healthy (closed or half-open), False if open (tripped).
        """
        try:
            rel = ScraperReliability.query.filter_by(platform=platform).first()
            if rel and rel.circuit_state == CircuitState.OPEN:
                return False
        except Exception:
            pass
        return True

    def check_idempotency_cache(self, product_id: str, organization_id: str) -> Optional[PricingRecommendation]:
        """
        Gap #6: Returns cached recommendation if created within 20 minutes.
        """
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=20)
            existing = PricingRecommendation.query.filter(
                PricingRecommendation.product_id == product_id,
                PricingRecommendation.organization_id == organization_id,
                PricingRecommendation.status == RecommendationStatus.PENDING,
                PricingRecommendation.created_at >= cutoff
            ).order_by(PricingRecommendation.created_at.desc()).first()
            return existing
        except Exception as e:
            logger.debug(f"[SupervisorAgent] Idempotency check failed: {e}")
            return None

    async def execute(
        self,
        task_id: str,
        product_id: str,
        organization_id: str,
        user_id: Optional[str] = None,
        force_refresh: bool = False,
        simulate_failure_platform: Optional[str] = None
    ) -> Dict[str, Any]:
        task_mgr = get_task_manager()

        # 1. Fetch Product
        product = Product.query.filter_by(id=product_id, organization_id=organization_id).first()
        if not product:
            task_mgr.update_status(task_id, "failed", error_message="Product not found or access denied.")
            return {"status": "failed", "message": "Product not found"}

        product_dict = product.to_dict()
        category = product.category or "general"

        # 2. Idempotency Check (Gap #6)
        if not force_refresh:
            cached_rec = self.check_idempotency_cache(product_id, organization_id)
            if cached_rec:
                self.record_decision(
                    task_id=task_id,
                    decision_point="Idempotency Cache Check (Gap #6)",
                    rationale=f"Active recommendation found within 20-min TTL (ID: {cached_rec.id}).",
                    action_taken="Served cached recommendation without triggering redundant scraping runs"
                )
                await self.emit_event(
                    task_id=task_id,
                    product_id=product_id,
                    organization_id=organization_id,
                    event_type="recommendation_served_from_cache",
                    message="Recommendation served from active 20-minute cache.",
                    payload=cached_rec.to_dict()
                )
                task_mgr.set_recommendation(task_id, cached_rec.to_dict())
                task_mgr.update_status(task_id, "succeeded")
                return {"status": "succeeded", "recommendation": cached_rec.to_dict(), "cached": True}

        # 3. Plan: Resolve Category to Platforms
        target_platforms = self.resolve_platforms(category)
        task = task_mgr.get_task(task_id, organization_id)
        task.dispatched_platforms = list(target_platforms)

        self.record_decision(
            task_id=task_id,
            decision_point="Platform Routing",
            rationale=f"Product category '{category}' mapped to target marketplaces.",
            action_taken=f"Dispatched tasks for platforms: {', '.join(target_platforms)}"
        )

        await self.emit_event(
            task_id=task_id,
            product_id=product_id,
            organization_id=organization_id,
            event_type="supervisor_planning_complete",
            message=f"Category '{category}' routed to {', '.join(target_platforms)}.",
            payload={"platforms": target_platforms, "category": category}
        )

        # 4. Filter platforms by Circuit Breaker (Gap #7)
        active_platforms = []
        raw_results = []

        for p_name in target_platforms:
            if not self.check_circuit_breaker(p_name):
                self.record_decision(
                    task_id=task_id,
                    decision_point="Circuit Breaker Check (Gap #7)",
                    rationale=f"Platform {p_name} has exceeded error threshold in the past hour (Circuit State: OPEN).",
                    action_taken="Skipped platform immediately to avoid latency and proxy burn"
                )
                await self.emit_event(
                    task_id=task_id,
                    product_id=product_id,
                    organization_id=organization_id,
                    event_type="scraper_skipped_circuit_open",
                    message=f"{p_name} skipped: Circuit breaker is OPEN due to recent consecutive blocks.",
                    payload={"platform": p_name, "circuit_state": "open"}
                )
                raw_results.append({
                    "platform": p_name,
                    "status": "unreachable",
                    "reason": "circuit_open",
                    "match_score": 0.0,
                    "unverified_match": True,
                })
            else:
                active_platforms.append(p_name)

        # 5. Dispatch Scraper Agents in Parallel
        scraper_tasks = []
        for p_name in active_platforms:
            try:
                agent = get_scraper_for_platform(p_name)
            except ValueError as val_err:
                logger.warning(f"[SupervisorAgent] Unknown or unsupported platform: {p_name} - {val_err}")
                self.record_decision(
                    task_id=task_id,
                    decision_point="Platform Resolution",
                    rationale=f"Platform '{p_name}' has no registered scraper: {val_err}",
                    action_taken="Marked as unsupported platform without silent fallback"
                )
                await self.emit_event(
                    task_id=task_id,
                    product_id=product_id,
                    organization_id=organization_id,
                    event_type="platform_not_found",
                    message=f"Platform '{p_name}' is unsupported by scraper registry.",
                    payload={"platform": p_name, "error": str(val_err)}
                )
                raw_results.append({
                    "platform": p_name,
                    "status": "unreachable",
                    "reason": f"unsupported_platform: {p_name}",
                    "match_score": 0.0,
                    "unverified_match": True,
                })
                continue

            sim_fail = (p_name == simulate_failure_platform)
            scraper_tasks.append(
                agent.scrape(
                    task_id=task_id,
                    product=product_dict,
                    organization_id=organization_id,
                    simulate_failure=sim_fail
                )
            )

        if scraper_tasks:
            scraped_outputs = await asyncio.gather(*scraper_tasks, return_exceptions=True)
            for out in scraped_outputs:
                if isinstance(out, dict):
                    raw_results.append(out)
                else:
                    logger.error(f"[SupervisorAgent] Scraper task exception: {out}")

        # 6. Aggregation Step
        aggregated_data = await self.aggregator.aggregate(
            task_id=task_id,
            product_id=product_id,
            organization_id=organization_id,
            raw_platform_results=raw_results,
            expected_platforms=target_platforms
        )

        verified_count = aggregated_data.get("verified_count", 0)

        # 7. Supervisor Decision Reasoning
        if verified_count == 0:
            self.record_decision(
                task_id=task_id,
                decision_point="Market Data Evaluation",
                rationale="Zero platforms returned verified listings. Refusing to fabricate market prices.",
                action_taken="Proceeding with conservative cost-plus margin guardrail calculation"
            )
        elif verified_count == 1:
            healthy_platform = list(aggregated_data["platforms"].keys())[0]
            self.record_decision(
                task_id=task_id,
                decision_point="Partial Market Data Reasoning",
                rationale=f"Single platform ({healthy_platform}) succeeded; secondary platform was unavailable.",
                action_taken="Proceeding with partial evidence, downgraded confidence to MEDIUM, and attached explanation"
            )
        else:
            self.record_decision(
                task_id=task_id,
                decision_point="Full Market Evidence Evaluation",
                rationale=f"Successfully verified listings across both target platforms ({', '.join(aggregated_data['platforms'].keys())}).",
                action_taken="Proceeded to pricing formulation with HIGH confidence"
            )

        # 8. Financial Reasoning & Guardrail Enforcement
        rec_data = await self.pricing_reasoner.generate_recommendation(
            task_id=task_id,
            product=product_dict,
            aggregated_data=aggregated_data,
            organization_id=organization_id
        )

        # 9. Persist Recommendation to Postgres
        rec_model = PricingRecommendation(
            id=str(uuid.uuid4()),
            product_id=product_id,
            organization_id=organization_id,
            task_id=task_id,
            recommended_price=rec_data["recommended_price"],
            confidence=rec_data["confidence"],
            reasoning_text=rec_data["reasoning_text"],
            platform_prices_snapshot=rec_data["platform_prices_snapshot"],
            margin_floor_applied=rec_data["margin_floor_applied"],
            margin_floor_value=rec_data["margin_floor_value"],
            sanity_bound_flagged=rec_data["sanity_bound_flagged"],
            status=RecommendationStatus.PENDING,
            decided_by=None
        )
        db.session.add(rec_model)
        db.session.commit()

        final_rec_dict = rec_model.to_dict()
        task_mgr.set_recommendation(task_id, final_rec_dict)
        task_mgr.update_status(task_id, "succeeded")

        await self.emit_event(
            task_id=task_id,
            product_id=product_id,
            organization_id=organization_id,
            event_type="recommendation_ready_for_approval",
            message=f"Recommendation ready for human review: ₹{rec_model.recommended_price:,.2f}",
            payload=final_rec_dict
        )

        return {"status": "succeeded", "recommendation": final_rec_dict, "cached": False}
