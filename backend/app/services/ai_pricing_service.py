"""
AI Pricing Service Orchestrator
Chains the 5 specialized agents concurrently in parallel using Python's asyncio.
"""
import asyncio
from app.models.audit_loging import PricingRule
from app.services.agents import (
    market_intelligence_agent,
    demand_forecast_agent,
    inventory_cost_agent,
    pricing_strategy_agent,
    compliance_agent
)
from app.services.notification_service import send_slack_alert


async def _run_pipeline_async(product):
    """Executes the Market, Demand, and Inventory agents concurrently."""
    # 1. Query relationship data inside transaction context
    competitor_prices = [cp.to_dict() for cp in product.competitor_prices.all()]
    demand_signals = [ds.to_dict() for ds in product.demand_signals.all()]
    product_dict = product.to_dict()

    # 2. Run Market, Demand, and Inventory agents in parallel using asyncio.gather
    market_task = market_intelligence_agent.run(product_dict, competitor_prices)
    demand_task = demand_forecast_agent.run(product_dict, demand_signals)
    inventory_task = inventory_cost_agent.run(product_dict)

    market_res, demand_res, inventory_res = await asyncio.gather(
        market_task,
        demand_task,
        inventory_task
    )

    # Map legacy keys for backward compatibility
    market_res["competitor_price"] = market_res.get("avg_competitor_price", product.current_price)
    market_res["market_trend"] = market_res.get("market_position", "stable")

    demand_res["demand_score"] = int(demand_res.get("avg_trend_score", 0.5) * 100)
    demand_res["trend"] = demand_res.get("trend_direction", "stable")

    inventory_res["stock_status"] = inventory_res.get("inventory_status", "healthy")
    inventory_res["inventory_level"] = product.inventory_quantity

    # =====================================
    # PHASE 4: PREDICTIVE SUPPLY CHAIN AI
    # =====================================
    velocity = demand_res.get("avg_velocity", 0.0)
    safe_velocity = velocity if velocity > 0 else 1.0
    days_to_stockout = product.inventory_quantity / safe_velocity
    inventory_res["days_to_stockout"] = round(days_to_stockout, 1)

    if days_to_stockout < 14 and product.inventory_quantity > 0 and velocity > 0:
        inventory_res["supply_chain_warning"] = f"CRITICAL: Product will stock out in {round(days_to_stockout)} days!"
        send_slack_alert(
            message=f"SUPPLY CHAIN ALERT: {product.name} will stock out in {round(days_to_stockout)} days! Re-order now.",
            recommendation={"rationale": "High velocity detected by DemandForecastAgent."},
            product=product_dict
        )

    # Fetch actual sales records
    from app.models.market_data import Sale
    sales = Sale.query.filter_by(
        product_id=product.id,
        organization_id=product.organization_id
    ).order_by(Sale.timestamp.desc()).limit(15).all()
    sales_history = [s.to_dict() for s in sales]

    # 3. Retrieve organizational rules
    rule = PricingRule.query.filter_by(organization_id=product.organization_id).first()
    rule_dict = rule.to_dict() if rule else {"auto_execute_threshold": 0.90, "minimum_margin": 0.15}

    # 4. Generate pricing strategy
    strategy_res = await pricing_strategy_agent.run(
        product_dict,
        market_res,
        demand_res,
        inventory_res,
        rule_dict,
        sales_history
    )

    # 5. Run compliance checks
    compliance_res = await compliance_agent.run(
        product_dict,
        strategy_res["recommended_price"],
        rule_dict
    )

    # Detect fallback status across all agents
    fallback_used = (
        market_res.get("llm_failed", False) or
        demand_res.get("llm_failed", False) or
        inventory_res.get("llm_failed", False) or
        strategy_res.get("llm_failed", False) or
        compliance_res.get("llm_failed", False)
    )
    strategy_res["fallback_used"] = fallback_used

    if fallback_used:
        strategy_res["recommended_price"] = product.current_price
        strategy_res["price_change_pct"] = 0.0
        strategy_res["execution_route"] = "human_review"
        strategy_res["strategy"] = "maintain"
        strategy_res["rationale"] = "LLM agent execution failed. Safe fallback applied: maintaining current catalog price."
        strategy_res["confidence_score"] = 1.0
    else:
        # Format recommendations
        final_price = compliance_res["final_recommended_price"]
        strategy_res["recommended_price"] = final_price

        if not compliance_res["compliant"]:
            strategy_res["rationale"] += " " + compliance_res["compliance_notes"]

        threshold = rule_dict.get("auto_execute_threshold", 0.90)
        confidence = strategy_res["confidence_score"]
        if confidence > 1.0:
            confidence /= 100.0

        if confidence >= threshold and compliance_res["compliant"]:
            strategy_res["execution_route"] = "auto_execute"
        else:
            strategy_res["execution_route"] = "human_review"

    strategy_res["ai_summary"] = strategy_res.get("ai_summary") or f"Recommended price update generated for {product.name}"
    strategy_res["compliance"] = compliance_res
    
    # Store sub-agent analysis details inside result
    strategy_res["agent_analysis"] = {
        "market_agent": market_res,
        "demand_agent": demand_res,
        "inventory_agent": inventory_res,
        "compliance_agent": compliance_res
    }

    # Trigger Slack alert for high-impact recommendations
    send_slack_alert(
        message=f"New AI Price Recommendation for {product.name}",
        recommendation=strategy_res,
        product=product_dict
    )

    return strategy_res


# =====================================
# Legacy Wrappers (Synchronous Delegates)
# =====================================

class MarketIntelligenceAgent:
    @staticmethod
    def analyze(product):
        # Fallback helper: runs async loop synchronously
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        competitor_prices = [cp.to_dict() for cp in product.competitor_prices.all()]
        product_dict = product.to_dict()
        
        result = loop.run_until_complete(market_intelligence_agent.run(product_dict, competitor_prices))
        result["competitor_price"] = result.get("avg_competitor_price", product.current_price)
        result["market_trend"] = result.get("market_position", "stable")
        return result


class DemandForecastAgent:
    @staticmethod
    def analyze(product):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        demand_signals = [ds.to_dict() for ds in product.demand_signals.all()]
        product_dict = product.to_dict()
        
        result = loop.run_until_complete(demand_forecast_agent.run(product_dict, demand_signals))
        result["demand_score"] = int(result.get("avg_trend_score", 0.5) * 100)
        result["trend"] = result.get("trend_direction", "stable")
        return result


class InventoryAgent:
    @staticmethod
    def analyze(product):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        product_dict = product.to_dict()
        result = loop.run_until_complete(inventory_cost_agent.run(product_dict))
        result["stock_status"] = result.get("inventory_status", "healthy")
        return result


# =====================================
# PRICING STRATEGY ORCHESTRATOR
# =====================================

class PricingStrategyAgent:

    @staticmethod
    def generate(
        product,
        market_data=None,
        demand_data=None,
        inventory_data=None
    ):
        # If any upstream data is missing, launch parallel async execution
        if market_data is None or demand_data is None or inventory_data is None:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            return loop.run_until_complete(_run_pipeline_async(product))

        # Synchronous legacy synthesis (used when precalculated metrics are supplied)
        product_dict = product.to_dict()
        
        rule = PricingRule.query.filter_by(
            organization_id=product.organization_id
        ).first()
        
        rule_dict = rule.to_dict() if rule else {
            "auto_execute_threshold": 0.90,
            "minimum_margin": 0.15
        }

        # Run legacy strategy & compliance logic synchronously
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        # Fetch actual sales records
        from app.models.market_data import Sale
        sales = Sale.query.filter_by(
            product_id=product.id,
            organization_id=product.organization_id
        ).order_by(Sale.timestamp.desc()).limit(15).all()
        sales_history = [s.to_dict() for s in sales]

        strategy_res = loop.run_until_complete(pricing_strategy_agent.run(
            product_dict,
            market_data,
            demand_data,
            inventory_data,
            rule_dict,
            sales_history
        ))

        compliance_res = loop.run_until_complete(compliance_agent.run(
            product_dict,
            strategy_res["recommended_price"],
            rule_dict
        ))

        # Detect fallback status across all agents
        fallback_used = (
            market_data.get("llm_failed", False) or
            demand_data.get("llm_failed", False) or
            inventory_data.get("llm_failed", False) or
            strategy_res.get("llm_failed", False) or
            compliance_res.get("llm_failed", False)
        )
        strategy_res["fallback_used"] = fallback_used

        if fallback_used:
            strategy_res["recommended_price"] = product.current_price
            strategy_res["price_change_pct"] = 0.0
            strategy_res["execution_route"] = "human_review"
            strategy_res["strategy"] = "maintain"
            strategy_res["rationale"] = "LLM agent execution failed. Safe fallback applied: maintaining current catalog price."
            strategy_res["confidence_score"] = 1.0
        else:
            final_price = compliance_res["final_recommended_price"]
            strategy_res["recommended_price"] = final_price

            if not compliance_res["compliant"]:
                strategy_res["rationale"] += " " + compliance_res["compliance_notes"]

            threshold = rule_dict.get("auto_execute_threshold", 0.90)
            confidence = strategy_res["confidence_score"]
            if confidence > 1.0:
                confidence /= 100.0

            if confidence >= threshold and compliance_res["compliant"]:
                strategy_res["execution_route"] = "auto_execute"
            else:
                strategy_res["execution_route"] = "human_review"

        strategy_res["ai_summary"] = strategy_res.get("ai_summary") or f"Recommended price update generated for {product.name}"
        strategy_res["compliance"] = compliance_res
        strategy_res["agent_analysis"] = {
            "market_agent": market_data,
            "demand_agent": demand_data,
            "inventory_agent": inventory_data,
            "compliance_agent": compliance_res
        }

        # Trigger Slack alert for high-impact recommendations
        send_slack_alert(
            message=f"New AI Price Recommendation for {product.name}",
            recommendation=strategy_res,
            product=product_dict
        )

        return strategy_res