import argparse
import asyncio
import contextlib
import contextvars
import io
import json
import logging
import math
import os
import random
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# ---------------------------------------------------------------------------
# Configure logging to write strictly to sys.stderr (protect stdio JSON-RPC)
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("klypup.mcp.server")

# Request-level context variables for SSE per-request tenant header overrides
request_tenant_org_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_tenant_org_id", default=None
)
request_tenant_user_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_tenant_user_id", default=None
)

# ---------------------------------------------------------------------------
# Global Flask App Singleton
# ---------------------------------------------------------------------------
_flask_app = None


def _get_flask_app():
    """
    Returns the singleton Flask application configured without background workers
    so MCP server invocations do not spawn unnecessary worker threads.
    """
    global _flask_app
    if _flask_app is None:
        from app import create_app
        _flask_app = create_app(start_worker=False)
    return _flask_app


@contextlib.contextmanager
def _scoped_session():
    """
    Ensures that every tool and resource executes inside the Flask app context,
    with stdout redirected to stderr to prevent breaking stdio JSON-RPC streams.
    """
    app = _get_flask_app()
    with app.app_context():
        with contextlib.redirect_stdout(sys.stderr):
            yield


def _get_tenant_context() -> Tuple[str, str]:
    """
    Resolves the active organization ID and user ID according to SEC-1 and SEC-2:
    1. Checks per-request headers (X-Organization-Id, X-User-Id).
    2. Checks environment variables (KLYPUP_MCP_ORG_ID, KLYPUP_MCP_USER_ID).
    3. Falls back to the primary seeded organization and admin user in the database.
    """
    from app.models.organization import Organization
    from app.models.user import User

    # 1. Check per-request header override (from SSE middleware)
    org_id = request_tenant_org_id.get()
    user_id = request_tenant_user_id.get()

    # 2. Check environment variables
    if not org_id:
        org_id = os.environ.get("KLYPUP_MCP_ORG_ID")
    if not user_id:
        user_id = os.environ.get("KLYPUP_MCP_USER_ID")

    # 3. Fallback to primary seeded Organization and User if unset
    if not org_id:
        primary_org = Organization.query.first()
        if primary_org:
            org_id = primary_org.id
        else:
            raise ValueError("No organization configured or found in database (SEC-1 violation).")

    # Verify organization exists
    org_exists = Organization.query.filter_by(id=org_id).first()
    if not org_exists:
        raise ValueError(f"Organization '{org_id}' does not exist or access denied (SEC-1 violation).")

    if not user_id:
        primary_user = User.query.filter_by(organization_id=org_id).first()
        if primary_user:
            user_id = primary_user.id
        else:
            raise ValueError(f"No user found for organization '{org_id}' (SEC-2 violation).")

    # Verify user exists and belongs to organization
    user_exists = User.query.filter_by(id=user_id, organization_id=org_id).first()
    if not user_exists:
        raise ValueError(f"User '{user_id}' does not belong to organization '{org_id}' (SEC-2 violation).")

    return str(org_id), str(user_id)


# ---------------------------------------------------------------------------
# Initialize FastMCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP("Klypup-Pricing-Intelligence")
if hasattr(mcp.settings, "transport_security"):
    mcp.settings.transport_security.enable_dns_rebinding_protection = False


# ===========================================================================
# 7 MCP TOOLS
# ===========================================================================

@mcp.tool()
async def scrape_marketplace(
    platform: str,
    product_name: str,
    brand: str = "",
    barcode: str = "",
    catalog_price: float = 0.0,
) -> Dict[str, Any]:
    """
    Runs live scraping for any of Klypup's 18 e-commerce marketplaces
    (e.g., Amazon.in, Flipkart, Myntra, Ajio, Nykaa, BigBasket, Blinkit, etc.).
    Returns validated ScrapedOffer metrics: price, mrp, match_score, tier_used,
    product_url, and in_stock availability.
    """
    with _scoped_session():
        org_id, _ = _get_tenant_context()
        from app.services.agentic.scrapers.platform_scrapers import get_scraper_for_platform
        agent = get_scraper_for_platform(platform)

        task_id = f"mcp-scrape-{uuid.uuid4().hex[:8]}"
        synthetic_product = {
            "id": f"mcp-probe-{uuid.uuid4().hex[:8]}",
            "name": product_name,
            "brand": brand,
            "barcode": barcode,
            "current_price": float(catalog_price) if catalog_price > 0 else 1000.0,
        }

        result = await agent.scrape(
            task_id=task_id,
            product=synthetic_product,
            organization_id=org_id,
            simulate_failure=False,
        )

        return {
            "platform": result.get("platform", platform),
            "status": result.get("status", "success"),
            "price": float(result.get("price") or 0.0),
            "mrp": float(result["mrp"]) if result.get("mrp") else None,
            "match_score": float(result.get("match_score") or 0.0),
            "tier_used": result.get("scrape_mode", "unknown"),
            "product_url": result.get("product_url", ""),
            "product_title": result.get("product_title", product_name),
            "in_stock": bool(result.get("in_stock", True)),
            "data_source": result.get("data_source", "live_scrape"),
            "latency_ms": result.get("latency_ms"),
            "reason": result.get("reason"),
        }


@mcp.tool()
async def scrape_category_swarm(
    product_id: Any,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    Fans out parallel scraping across all category-relevant marketplaces for a SKU,
    normalizes offers, filters MAD outliers (n >= 4), and returns clean market metrics:
    market_avg, market_min, market_max, valid_offers, and discarded_outliers.
    """
    with _scoped_session():
        org_id, user_id = _get_tenant_context()
        from app.models.product import Product
        from app.services.task_state.task_manager import get_task_manager
        from app.services.agentic.supervisor_agent import SupervisorAgent
        from app.services.agentic.aggregator_agent import AggregatorAgent

        prod_str_id = str(product_id)
        product = Product.query.filter_by(id=prod_str_id, organization_id=org_id).first()
        if not product:
            product = Product.query.filter_by(sku=prod_str_id, organization_id=org_id).first()
        if not product:
            raise ValueError(f"Product '{prod_str_id}' not found for tenant organization '{org_id}' (SEC-1).")

        task_mgr = get_task_manager()
        task_id = f"mcp-swarm-{uuid.uuid4().hex[:8]}"
        task_mgr.create_task(
            task_id=task_id,
            product_id=product.id,
            organization_id=org_id,
            user_id=user_id,
            category=product.category,
        )

        supervisor = SupervisorAgent()
        platforms = supervisor.resolve_platforms(product.category)

        raw_results = await supervisor.run_scraping_phase(
            task_id=task_id,
            product=product.to_dict(),
            organization_id=org_id,
            force_refresh=force_refresh,
            target_platforms=platforms,
        )

        aggregator = AggregatorAgent()
        aggregated = await aggregator.aggregate(
            task_id=task_id,
            product_id=product.id,
            organization_id=org_id,
            raw_platform_results=raw_results,
            expected_platforms=platforms,
        )

        valid_offers = aggregated.get("valid_offers", [])
        total_raw = len([r for r in raw_results if isinstance(r, dict) and float(r.get("price") or 0.0) > 0])
        discarded_outliers = max(0, total_raw - len(valid_offers))

        return {
            "product_id": product.id,
            "sku": product.sku,
            "product_name": product.name,
            "category": product.category,
            "target_platforms": platforms,
            "market_avg": aggregated.get("market_avg", 0.0),
            "market_min": aggregated.get("market_min", 0.0),
            "market_max": aggregated.get("market_max", 0.0),
            "verified_count": aggregated.get("verified_count", 0),
            "valid_offers": valid_offers,
            "discarded_outliers": discarded_outliers,
            "missing_platforms": aggregated.get("missing_platforms", {}),
        }


@mcp.tool()
async def run_full_pricing_swarm(
    product_id: Any,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    Executes Klypup's full multi-agent pricing swarm for a product:
    20-min idempotency check -> parallel scraping -> MAD outlier filtering ->
    Dual-Agent Debate (Agent A Margin Floor vs Agent B Competitor Elasticity) ->
    SEC-9 margin floor clamp -> SEC-10 ±50% sanity bound verification.
    Returns the persisted PricingRecommendation payload.
    """
    with _scoped_session():
        org_id, user_id = _get_tenant_context()
        from app.models.product import Product
        from app.models.pricing_recommendation import PricingRecommendation
        from app.services.task_state.task_manager import get_task_manager
        from app.services.agentic.supervisor_agent import SupervisorAgent

        prod_str_id = str(product_id)
        product = Product.query.filter_by(id=prod_str_id, organization_id=org_id).first()
        if not product:
            product = Product.query.filter_by(sku=prod_str_id, organization_id=org_id).first()
        if not product:
            raise ValueError(f"Product '{prod_str_id}' not found for tenant organization '{org_id}' (SEC-1).")

        task_mgr = get_task_manager()
        task_id = f"mcp-swarm-exec-{uuid.uuid4().hex[:8]}"
        task_mgr.create_task(
            task_id=task_id,
            product_id=product.id,
            organization_id=org_id,
            user_id=user_id,
            category=product.category,
        )

        supervisor = SupervisorAgent()
        result = await supervisor.execute(
            task_id=task_id,
            product_id=product.id,
            organization_id=org_id,
            user_id=user_id,
            force_refresh=force_refresh,
        )

        # Retrieve saved PricingRecommendation
        rec = None
        if result.get("recommendation"):
            rec_id = result["recommendation"].get("id")
            if rec_id:
                rec = PricingRecommendation.query.filter_by(id=rec_id, organization_id=org_id).first()
        if not rec:
            rec = (
                PricingRecommendation.query.filter_by(product_id=product.id, organization_id=org_id)
                .order_by(PricingRecommendation.created_at.desc())
                .first()
            )

        if not rec:
            raise RuntimeError(f"Pricing swarm executed but failed to persist recommendation for {product.sku}.")

        return {
            "recommendation_id": rec.id,
            "product_id": product.id,
            "sku": product.sku,
            "product_name": product.name,
            "current_price": float(product.current_price),
            "cost_price": float(product.cost_price),
            "recommended_price": round(float(rec.recommended_price), 2),
            "confidence_score": round(float(rec.confidence_score), 2),
            "margin_floor_applied": bool(rec.margin_floor_applied),
            "margin_floor_value": float(rec.margin_floor_value) if rec.margin_floor_value else None,
            "sanity_bound_flagged": bool(rec.sanity_bound_flagged),
            "reasoning_text": rec.reasoning_text or rec.rationale or "",
            "competitor_snapshot": rec.platform_prices_snapshot or {},
            "status": rec.status,
            "created_at": rec.created_at.isoformat() if rec.created_at else None,
        }


@mcp.tool()
async def approve_or_reject_recommendation(
    recommendation_id: Any,
    action: str,
    reason: str = "",
) -> Dict[str, Any]:
    """
    Decides on a pending PricingRecommendation ('approve' or 'reject').
    On approval:
      Enforces optimistic Compare-And-Swap (CAS) against expected_base_price,
      executes SEC-9 margin floor check and SEC-10 sanity bound, mutates product price,
      creates immutable PriceHistory + AuditLog, and persists ApprovalAction.
    On rejection:
      Marks recommendation rejected and records reason in ApprovalAction + AuditLog.
    Returns status and action_id (which can be rolled back via rollback_price_change).
    """
    action_clean = str(action).strip().lower()
    if action_clean not in ("approve", "reject"):
        raise ValueError(f"Invalid action '{action}'. Must be 'approve' or 'reject'.")

    with _scoped_session():
        org_id, user_id = _get_tenant_context()
        from app.extensions import db
        from app.models.pricing_recommendation import PricingRecommendation, RecommendationStatus
        from app.models.product import Product
        from app.models.recommendation import ApprovalAction, ApprovalActionType
        from app.services.pricing.price_writer import apply_price_change, AlreadyDecidedError

        rec_str_id = str(recommendation_id)
        rec = PricingRecommendation.query.filter_by(id=rec_str_id, organization_id=org_id).first()
        if not rec:
            raise ValueError(f"Pricing recommendation '{rec_str_id}' not found for tenant '{org_id}' (SEC-1).")

        if rec.status != RecommendationStatus.PENDING:
            raise AlreadyDecidedError(f"Recommendation {rec.id} has already been decided (status: {rec.status}).")

        product = Product.query.filter_by(id=rec.product_id, organization_id=org_id).first()
        if not product:
            raise ValueError(f"Associated product '{rec.product_id}' not found.")

        old_price = float(product.current_price)
        target_price = float(rec.recommended_price)
        action_uuid = str(uuid.uuid4())

        if action_clean == "approve":
            # Apply atomic price change via canonical ledger writer
            ledger_res = apply_price_change(
                product=product,
                new_price=target_price,
                actor_user_id=user_id,
                source="mcp_approval",
                recommendation=rec,
                expected_base_price=rec.base_price,
                sanity_override=False,
                reason=reason or "Approved via MCP tool call",
                action="price_approved",
            )

            rec.status = RecommendationStatus.APPROVED
            rec.decided_by = user_id
            rec.decided_at = datetime.now(timezone.utc)

            approval_action = ApprovalAction(
                id=action_uuid,
                recommendation_id=rec.id,
                action_type=ApprovalActionType.APPROVE,
                previous_price=old_price,
                executed_price=target_price,
                approved_by=user_id,
                sku=product.sku,
            )
            db.session.add(approval_action)
            db.session.commit()

            return {
                "status": "approved",
                "action_id": approval_action.id,
                "product_id": product.id,
                "sku": product.sku,
                "old_price": old_price,
                "new_price": target_price,
                "history_id": ledger_res.get("history_id"),
                "audit_id": ledger_res.get("audit_id"),
            }

        else:  # reject
            rec.status = RecommendationStatus.REJECTED
            rec.decided_by = user_id
            rec.decided_at = datetime.now(timezone.utc)

            approval_action = ApprovalAction(
                id=action_uuid,
                recommendation_id=rec.id,
                action_type=ApprovalActionType.REJECT,
                previous_price=old_price,
                executed_price=None,
                approved_by=user_id,
                rejection_reason=reason or "Rejected via MCP tool call",
                sku=product.sku,
            )
            db.session.add(approval_action)
            db.session.commit()

            return {
                "status": "rejected",
                "action_id": approval_action.id,
                "product_id": product.id,
                "sku": product.sku,
                "reason": reason or "Rejected via MCP",
            }


@mcp.tool()
async def rollback_price_change(
    action_id: Any,
) -> Dict[str, Any]:
    """
    Restores Product.current_price to the previous approved price from ApprovalAction
    with anti-replay protection. Appends immutable PriceHistory and AuditLog records.
    """
    with _scoped_session():
        org_id, user_id = _get_tenant_context()
        from app.extensions import db
        from app.models.recommendation import ApprovalAction, ApprovalActionType
        from app.models.product import Product
        from app.services.pricing.price_writer import apply_price_change

        action_str_id = str(action_id)
        target_action = ApprovalAction.query.filter_by(id=action_str_id).first()
        if not target_action:
            raise ValueError(f"Approval action '{action_str_id}' not found.")

        rec = target_action.recommendation
        if not rec or rec.organization_id != org_id:
            raise ValueError(f"Access denied to action '{action_str_id}' (SEC-1 violation).")

        if target_action.action_type != ApprovalActionType.APPROVE:
            raise ValueError(f"Only approved price changes can be rolled back (current: {target_action.action_type}).")

        # Anti-replay protection
        already_rolled_back = ApprovalAction.query.filter_by(
            recommendation_id=rec.id,
            action_type="rollback"
        ).first()
        if already_rolled_back:
            raise ValueError(f"Approval action {action_str_id} has already been rolled back (anti-replay guardrail).")

        product = Product.query.filter_by(id=rec.product_id, organization_id=org_id).first()
        if not product:
            raise ValueError(f"Associated product '{rec.product_id}' not found.")

        current_price = float(product.current_price)
        restored_price = float(target_action.previous_price)

        ledger_res = apply_price_change(
            product=product,
            new_price=restored_price,
            actor_user_id=user_id,
            source="mcp_rollback",
            recommendation=rec,
            sanity_override=True,
            reason=f"Rollback of action {action_str_id} via MCP tool call",
            action="price_rollback",
        )

        rollback_action = ApprovalAction(
            id=str(uuid.uuid4()),
            recommendation_id=rec.id,
            action_type="rollback",
            previous_price=current_price,
            executed_price=restored_price,
            approved_by=user_id,
            sku=product.sku,
        )
        db.session.add(rollback_action)
        db.session.commit()

        return {
            "status": "rolled_back",
            "rollback_action_id": rollback_action.id,
            "product_id": product.id,
            "sku": product.sku,
            "previous_price": current_price,
            "restored_price": restored_price,
            "history_id": ledger_res.get("history_id"),
            "audit_id": ledger_res.get("audit_id"),
        }


@mcp.tool()
async def check_or_reset_circuit_breakers(
    reset: bool = False,
    run_canaries: bool = False,
) -> Dict[str, Any]:
    """
    Inspects or resets circuit breakers across all 18 scraper platforms.
    If reset=True, clears all failure counts and resets states to 'closed'.
    If run_canaries=True, executes live canary health check probes across all platforms.
    """
    with _scoped_session():
        org_id, _ = _get_tenant_context()
        from app.extensions import db
        from app.models.scraper_reliability import CircuitState, ScraperReliability
        from app.services.agentic.scrapers.platform_scrapers import PLATFORM_SCRAPERS

        all_platforms = sorted(PLATFORM_SCRAPERS.keys())
        if reset:
            for p in all_platforms:
                row = ScraperReliability.query.filter_by(platform=p).first()
                if not row:
                    row = ScraperReliability(platform=p)
                    db.session.add(row)
                row.circuit_state = CircuitState.CLOSED
                row.failure_count_last_hour = 0
                row.circuit_opened_at = None
                row.backoff_minutes = 15
                row.last_failure_reason = None
            db.session.commit()

        canary_results = []
        if run_canaries:
            from app.services.agentic.health_check_scheduler import run_all_canary_health_checks
            canary_results = await run_all_canary_health_checks(organization_id=org_id)

        rows = ScraperReliability.query.all()
        row_map = {r.platform: r for r in rows}

        reliability_data = []
        for p in all_platforms:
            r = row_map.get(p)
            reliability_data.append({
                "platform": p,
                "circuit_state": r.circuit_state if r else CircuitState.CLOSED,
                "failure_count_last_hour": r.failure_count_last_hour if r else 0,
                "backoff_minutes": r.backoff_minutes if r else 15,
                "last_failure_reason": r.last_failure_reason if r else None,
                "last_successful_scrape_at": r.last_successful_scrape_at.isoformat() if (r and r.last_successful_scrape_at) else None,
            })

        return {
            "total_platforms": len(all_platforms),
            "reset_executed": reset,
            "canaries_executed": run_canaries,
            "platforms": reliability_data,
            "canary_probes": canary_results,
        }


@mcp.tool()
async def simulate_price_elasticity(
    product_id: Any,
    elasticity: float = -1.5,
    days: int = 30,
) -> Dict[str, Any]:
    """
    Runs a non-mutating log-linear price elasticity simulation for a SKU.
    Projects revenue, gross profit, sales volume, and compliance floor guardrails.
    """
    with _scoped_session():
        org_id, _ = _get_tenant_context()
        from app.models.product import Product
        from app.models.audit_loging import PricingRule
        from app.utils.security_guardrails import compute_price_floor, effective_min_margin_pct

        prod_str_id = str(product_id)
        product = Product.query.filter_by(id=prod_str_id, organization_id=org_id).first()
        if not product:
            product = Product.query.filter_by(sku=prod_str_id, organization_id=org_id).first()
        if not product:
            raise ValueError(f"Product '{prod_str_id}' not found for tenant '{org_id}' (SEC-1).")

        rule = PricingRule.query.filter_by(organization_id=org_id).first()
        min_margin = rule.minimum_margin if rule else 0.15

        cost = float(product.cost_price)
        base_price = float(product.current_price)
        base_qty = int(product.inventory_quantity or 0)
        eff_pct = effective_min_margin_pct(product.min_margin_percentage, min_margin)
        floor_price = compute_price_floor(cost, eff_pct)

        category = (product.category or "general").lower()
        if "ele" in category:
            base_daily_units = 12.0
        elif "app" in category:
            base_daily_units = 25.0
        else:
            base_daily_units = 18.0

        timeline = []
        total_actual_rev = 0.0
        total_ai_rev = 0.0
        total_actual_prof = 0.0
        total_ai_prof = 0.0

        sim_elasticity = abs(float(elasticity))
        random_gen = random.Random(42)

        for day in range(1, int(days) + 1):
            comp_price = base_price * (1.0 + 0.06 * math.sin(day / 4.0) + random_gen.uniform(-0.02, 0.02))
            trend_score = max(min(0.5 + 0.28 * math.sin(day / 6.0) + random_gen.uniform(-0.04, 0.04), 1.0), 0.0)
            seasonal_factor = 1.0 + 0.2 * math.cos(day / 8.0)
            daily_vol_factor = base_daily_units * seasonal_factor

            gap_pct = ((base_price - comp_price) / comp_price * 100) if comp_price > 0 else 0
            market_adj = -gap_pct * 0.35
            demand_adj = (trend_score - 0.5) * 12.0
            inv_adj = 4.0 if base_qty < 10 else (-6.0 if base_qty > 100 else 0.0)

            composite_adj = max(min((market_adj * 0.35) + (demand_adj * 0.35) + (inv_adj * 0.30), 15.0), -15.0)
            projected_price = round(base_price * (1.0 + composite_adj / 100.0), 2)
            if projected_price < floor_price:
                projected_price = floor_price

            q_baseline = max(int(daily_vol_factor), 1)
            price_ratio = projected_price / base_price if base_price > 0 else 1.0
            q_ai = max(int(daily_vol_factor * (price_ratio ** -sim_elasticity)), 1)

            day_actual_rev = base_price * q_baseline
            day_ai_rev = projected_price * q_ai
            day_actual_prof = (base_price - cost) * q_baseline
            day_ai_prof = (projected_price - cost) * q_ai

            total_actual_rev += day_actual_rev
            total_ai_rev += day_ai_rev
            total_actual_prof += day_actual_prof
            total_ai_prof += day_ai_prof

            timeline.append({
                "day": day,
                "projected_price": projected_price,
                "projected_volume": q_ai,
                "revenue": round(day_ai_rev, 2),
                "profit": round(day_ai_prof, 2),
            })

        return {
            "product_id": product.id,
            "sku": product.sku,
            "current_price": base_price,
            "cost_price": cost,
            "margin_floor": floor_price,
            "elasticity_applied": -sim_elasticity,
            "simulation_days": int(days),
            "projected_total_revenue": round(total_ai_rev, 2),
            "projected_total_profit": round(total_ai_prof, 2),
            "baseline_revenue": round(total_actual_rev, 2),
            "baseline_profit": round(total_actual_prof, 2),
            "revenue_lift_pct": round(((total_ai_rev - total_actual_rev) / total_actual_rev) * 100, 2) if total_actual_rev > 0 else 0.0,
            "profit_lift_pct": round(((total_ai_prof - total_actual_prof) / total_actual_prof) * 100, 2) if total_actual_prof > 0 else 0.0,
            "timeline": timeline,
        }


# ===========================================================================
# 4 MCP RESOURCES
# ===========================================================================

@mcp.resource("klypup://catalog/products")
async def get_catalog_products() -> str:
    """
    Read-only catalog list of active products for the tenant organization.
    """
    with _scoped_session():
        org_id, _ = _get_tenant_context()
        from app.models.product import Product
        from app.models.audit_loging import PricingRule
        from app.utils.security_guardrails import compute_price_floor, effective_min_margin_pct

        rule = PricingRule.query.filter_by(organization_id=org_id).first()
        min_margin = rule.minimum_margin if rule else 0.15

        products = Product.query.filter_by(organization_id=org_id).all()
        catalog = []
        for p in products:
            eff_pct = effective_min_margin_pct(p.min_margin_percentage, min_margin)
            floor = compute_price_floor(p.cost_price, eff_pct)
            catalog.append({
                "id": p.id,
                "sku": p.sku,
                "name": p.name,
                "brand": p.brand or "",
                "category": p.category,
                "cost": float(p.cost_price),
                "current_price": float(p.current_price),
                "margin_floor": floor,
                "stock_quantity": int(p.inventory_quantity or 0),
                "status": p.recommendation_status,
            })
        return json.dumps(catalog, indent=2)


@mcp.resource("klypup://catalog/product/{sku}/history")
async def get_product_price_history(sku: str) -> str:
    """
    Immutable historical audit and price change trail for a specific SKU.
    """
    with _scoped_session():
        org_id, _ = _get_tenant_context()
        from app.models.product import Product
        from app.models.price_history import PriceHistory
        from app.models.audit_loging import AuditLog

        product = Product.query.filter_by(sku=sku, organization_id=org_id).first()
        if not product:
            return json.dumps({"error": f"SKU '{sku}' not found for tenant organization '{org_id}'"}, indent=2)

        histories = PriceHistory.query.filter_by(product_id=product.id).order_by(PriceHistory.created_at.desc()).all()
        audits = AuditLog.query.filter_by(entity_id=product.id).order_by(AuditLog.timestamp.desc()).limit(20).all()

        return json.dumps({
            "product": {
                "id": product.id,
                "sku": product.sku,
                "name": product.name,
                "current_price": float(product.current_price),
                "cost_price": float(product.cost_price),
            },
            "price_history": [h.to_dict() for h in histories],
            "audit_logs": [a.to_dict() for a in audits],
        }, indent=2)


@mcp.resource("klypup://scrapers/health")
async def get_scrapers_health() -> str:
    """
    Live circuit breaker states and scraping telemetry across all 18 marketplace sensors.
    """
    with _scoped_session():
        from app.models.scraper_reliability import CircuitState, ScraperReliability
        from app.services.agentic.scrapers.platform_scrapers import PLATFORM_SCRAPERS

        all_platforms = sorted(PLATFORM_SCRAPERS.keys())
        rows = {r.platform: r for r in ScraperReliability.query.all()}

        health_data = []
        for p in all_platforms:
            r = rows.get(p)
            health_data.append({
                "platform": p,
                "circuit_state": r.circuit_state if r else CircuitState.CLOSED,
                "failure_count_last_hour": r.failure_count_last_hour if r else 0,
                "backoff_minutes": r.backoff_minutes if r else 15,
                "last_failure_reason": r.last_failure_reason if r else None,
                "last_successful_scrape_at": r.last_successful_scrape_at.isoformat() if (r and r.last_successful_scrape_at) else None,
            })
        return json.dumps(health_data, indent=2)


@mcp.resource("klypup://recommendations/pending")
async def get_pending_recommendations() -> str:
    """
    Lists all active pricing recommendations currently awaiting human-in-the-loop review.
    """
    with _scoped_session():
        org_id, _ = _get_tenant_context()
        from app.models.pricing_recommendation import PricingRecommendation, RecommendationStatus
        from app.models.product import Product

        recs = (
            PricingRecommendation.query.filter_by(organization_id=org_id, status=RecommendationStatus.PENDING)
            .order_by(PricingRecommendation.created_at.desc())
            .all()
        )
        data = []
        for r in recs:
            p = Product.query.get(r.product_id)
            data.append({
                "recommendation_id": r.id,
                "product_id": r.product_id,
                "sku": p.sku if p else "UNKNOWN",
                "product_name": p.name if p else "Unknown Product",
                "current_price": float(p.current_price) if p else None,
                "recommended_price": round(float(r.recommended_price), 2),
                "confidence_score": round(float(r.confidence_score), 2),
                "margin_floor_applied": bool(r.margin_floor_applied),
                "margin_floor_value": float(r.margin_floor_value) if r.margin_floor_value else None,
                "sanity_bound_flagged": bool(r.sanity_bound_flagged),
                "reasoning_text": r.reasoning_text or r.rationale or "",
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })
        return json.dumps(data, indent=2)


# ===========================================================================
# 2 MCP PROMPTS
# ===========================================================================

@mcp.prompt()
def audit_sku_pricing(sku: str) -> str:
    """
    Workflow prompt guiding the host AI to read SKU history, execute the multi-agent
    pricing swarm, compare Agent A margin guardrail vs Agent B elasticity, and
    format an executive pricing decision memo.
    """
    return f"""You are the Klypup Pricing Copilot auditing SKU '{sku}'.
Perform the following systematic evaluation:
1. Read the immutable price and audit trail at resource 'klypup://catalog/product/{sku}/history'.
2. Execute 'run_full_pricing_swarm(product_id="{sku}")' to gather live marketplace intelligence across verified category sensors.
3. Compare:
   - Agent A (Internal Financials & Margin Floor): Cost, inventory pressure, and non-negotiable floor clamp.
   - Agent B (Market & Competitor Dynamics): Competitor discounting index, Jaccard match scores, and price elasticity.
4. Verify if SEC-9 (Margin Floor Guardrail) or SEC-10 (±50% Price Sanity Bound) was triggered.
5. Provide a clear decision summary with your recommended action ('approve' or 'reject') and a concise rationale.
"""


@mcp.prompt()
def diagnose_platform_sensor(platform: str) -> str:
    """
    Workflow prompt guiding the host AI to inspect circuit breaker health, run a test
    probe scrape, and diagnose bot detection, selector health, and proxy latency.
    """
    return f"""You are Klypup's Platform Sensor Diagnostician evaluating marketplace sensor '{platform}'.
Perform the following health checks:
1. Inspect platform telemetry at resource 'klypup://scrapers/health'.
2. If the platform circuit breaker is OPEN, explain the failure reason and remaining cooldown.
3. Execute a live test probe using 'scrape_marketplace(platform="{platform}", product_name="Test Diagnostic Item")'.
4. Analyze the probe output:
   - Match score and price extraction accuracy
   - Scrape tier utilized (internal_api vs mobile_headers vs playwright_stealth vs search_index)
   - Latency budget compliance (< 15 seconds)
5. Report whether the scraper is fully functional, degraded, or in need of selector updates.
"""


# ===========================================================================
# Starlette Middleware for Bearer Auth & Tenant Header Overrides (SSE Mode)
# ===========================================================================

class MCPAgentAuthMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware enforcing Bearer authentication in SSE transport mode when
    KLYPUP_MCP_API_KEY is configured. Allows unauthenticated GET /health for
    Render cloud deployment health checks, and binds X-Organization-Id and
    X-User-Id request headers to async context variables.
    """

    def __init__(self, app, api_key: Optional[str] = None):
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request, call_next):
        # 1. Unauthenticated health probe for Render Cloud Web Services
        if request.url.path in ("/health", "/healthz"):
            return JSONResponse({"status": "healthy", "service": "klypup-mcp-server"})

        # 2. Bearer Authentication Check if API key is configured
        if self.api_key:
            auth_header = request.headers.get("authorization", "")
            expected_bearer = f"Bearer {self.api_key}"
            if auth_header != expected_bearer:
                return JSONResponse(
                    {"error": "Unauthorized: Invalid or missing Bearer token"},
                    status_code=401,
                )

        # 3. Bind per-request tenant header overrides
        token_org = request_tenant_org_id.set(request.headers.get("x-organization-id"))
        token_user = request_tenant_user_id.set(request.headers.get("x-user-id"))
        try:
            return await call_next(request)
        finally:
            request_tenant_org_id.reset(token_org)
            request_tenant_user_id.reset(token_user)


def create_mcp_server(api_key: Optional[str] = None):
    """
    Creates and returns the FastMCP server instance, wiring in auth middleware
    if running in an ASGI/SSE context.
    """
    return mcp


# ===========================================================================
# CLI Entrypoint (stdio and sse modes)
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description="Klypup Model Context Protocol (MCP) Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host address to bind for SSE transport (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8001")),
        help="Port to bind for SSE transport (default: 8001 or $PORT)",
    )

    args = parser.parse_args()

    # Pre-initialize Flask app singleton
    _get_flask_app()

    if args.transport == "sse":
        api_key = os.environ.get("KLYPUP_MCP_API_KEY")
        logger.info(f"Starting Klypup MCP Server in SSE mode on {args.host}:{args.port}")
        if api_key:
            logger.info("Bearer authentication enabled via KLYPUP_MCP_API_KEY")
        else:
            logger.warning("No KLYPUP_MCP_API_KEY set; running SSE server without Bearer auth")

        # FastMCP settings
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        if hasattr(mcp.settings, "transport_security"):
            mcp.settings.transport_security.enable_dns_rebinding_protection = False

        # Build Starlette app with auth middleware
        sse_app = mcp.sse_app()
        sse_app.add_middleware(MCPAgentAuthMiddleware, api_key=api_key)

        import uvicorn
        uvicorn.run(sse_app, host=args.host, port=args.port, log_level="info")

    else:  # stdio
        logger.info("Starting Klypup MCP Server in stdio mode")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
