import uuid
import pytest
from unittest.mock import patch, AsyncMock
from run import app
from app.extensions import db
from app.models.organization import Organization
from app.models.product import Product
from app.services.ai.schemas import (
    PricingStrategySchema,
    MarketAnalysisSchema,
    DemandAnalysisSchema,
    InventoryAnalysisSchema,
    ComplianceSchema
)
from app.services.agents.pricing_strategy_agent import _mock_strategy_generation
from app.services.agents.market_intelligence_agent import _mock_market_analysis
from app.services.agents.demand_forecast_agent import _mock_demand_analysis
from app.services.agents.inventory_cost_agent import _mock_inventory_analysis
from app.services.agents.compliance_agent import _mock_compliance_check
from app.services.ai_pricing_service import PricingStrategyAgent
from app.services.ai.client import get_last_ai_meta, set_last_ai_meta


@pytest.fixture
def product_fixture():
    with app.app_context():
        org_id = str(uuid.uuid4())
        org = Organization(id=org_id, name="AI Outage Org", invite_code=f"INV-{org_id[:6]}")
        db.session.add(org)

        prod_id = str(uuid.uuid4())
        product = Product(
            id=prod_id,
            sku=f"SKU-AI-{prod_id[:6]}",
            name="AI Test Headphones",
            brand="SoundCorp",
            category="electronics",
            current_price=2500.0,
            cost_price=1500.0,
            inventory_quantity=45,
            organization_id=org_id
        )
        db.session.add(product)
        db.session.commit()

        yield product


def test_mock_outputs_satisfy_pydantic_schemas_and_honest_degraded_flags():
    """Verify all agent _mock_* functions comply with schemas, have confidence 0.0, and set degraded/llm_failed."""
    sample_product = {
        "id": "mock-prod",
        "name": "Widget X",
        "sku": "SKU-WIDGET",
        "current_price": 1000.0,
        "cost_price": 600.0,
        "inventory_quantity": 25
    }
    rules = {"auto_execute_threshold": 0.90, "minimum_margin": 0.15}

    # 1. Market Mock
    market_mock = _mock_market_analysis(sample_product, [{"competitor_price": 950.0}])
    assert market_mock["llm_failed"] is True
    assert market_mock["degraded"] is True
    assert market_mock["market_position"] in ["leader", "competitive", "lagging"]
    MarketAnalysisSchema.model_validate(market_mock)

    # 2. Demand Mock
    demand_mock = _mock_demand_analysis(sample_product, [{"velocity": 1.5}])
    assert demand_mock["llm_failed"] is True
    assert demand_mock["degraded"] is True
    assert demand_mock["trend_direction"] in ["rising", "stable", "declining"]
    assert demand_mock["demand_level"] in ["high", "medium", "low"]
    DemandAnalysisSchema.model_validate(demand_mock)

    # 3. Inventory Mock
    inv_mock = _mock_inventory_analysis(sample_product)
    assert inv_mock["llm_failed"] is True
    assert inv_mock["degraded"] is True
    assert inv_mock["inventory_status"] in ["overstock", "healthy", "low_stock", "out_of_stock"]
    InventoryAnalysisSchema.model_validate(inv_mock)

    # 4. Strategy Mock (must return confidence_score 0.0)
    strategy_mock = _mock_strategy_generation(sample_product, market_mock, demand_mock, inv_mock, rules)
    assert strategy_mock["llm_failed"] is True
    assert strategy_mock["degraded"] is True
    assert strategy_mock["confidence_score"] == 0.0
    assert strategy_mock["strategy"] in ["penetration", "competitive", "premium", "clearance", "maintain"]
    PricingStrategySchema.model_validate(strategy_mock)

    # 5. Compliance Mock
    comp_mock = _mock_compliance_check(sample_product, 1100.0, rules)
    assert comp_mock["llm_failed"] is True
    assert comp_mock["degraded"] is True
    ComplianceSchema.model_validate(comp_mock)


def test_total_llm_outage_fails_to_human_review_and_zero_confidence(product_fixture):
    """When async_chat_completion / async_guarded_json_completion fails (None), route must be human_review."""
    with app.app_context():
        # Patch both completion methods to return None (total outage) and supervisor to return fast snapshot
        with patch("app.services.ai.client.async_chat_completion", new_callable=AsyncMock) as mock_chat, \
             patch("app.services.ai.client.async_guarded_json_completion", new_callable=AsyncMock) as mock_guarded, \
             patch("app.services.agentic.supervisor_agent.SupervisorAgent.execute", new_callable=AsyncMock) as mock_sup:
            
            mock_chat.return_value = None
            mock_guarded.return_value = None
            mock_sup.return_value = {
                "recommendation": {
                    "platform_prices_snapshot": {
                        "Amazon": {"price": 2400.0, "data_source": "live_scrape", "stock_status": "in_stock"}
                    }
                }
            }

            result = PricingStrategyAgent.generate(product_fixture)

            # Invariant: Fallback used must be True
            assert result["fallback_used"] is True

            # Invariant: Execution route must NEVER be auto_execute during an outage
            assert result["execution_route"] == "human_review"
            assert result["execution_route"] != "auto_execute"

            # Invariant: Confidence score must be 0.0, not fake 1.0 or 0.94
            assert result["confidence_score"] == 0.0

            # Invariant: Price change must be 0 (catalogue price maintained)
            assert result["recommended_price"] == product_fixture.current_price
            assert result["price_change_pct"] == 0.0

            # Invariant: Provenance metadata must report degraded: True
            agent_analysis = result.get("agent_analysis", {})
            provenance = agent_analysis.get("provenance", {})
            assert provenance.get("degraded") is True
            assert "provider" in provenance
            assert "model" in provenance
            assert "failover_attempts" in provenance


def test_subagent_degraded_flag_downgrades_to_human_review(product_fixture):
    """If a sub-agent analysis has degraded=True, the orchestrator must fallback and route to human_review."""
    with app.app_context():
        market_data = {
            "market_position": "competitive",
            "avg_competitor_price": 2400.0,
            "min_competitor_price": 2300.0,
            "max_competitor_price": 2600.0,
            "price_gap_pct": 4.0,
            "suggested_adjustment_pct": -4.0,
            "insights": "Degraded market scraper",
            "degraded": True, # Marked degraded
            "llm_failed": True
        }
        demand_data = {
            "demand_level": "medium",
            "trend_direction": "stable",
            "avg_trend_score": 0.5,
            "avg_seasonal_factor": 1.0,
            "avg_velocity": 1.0,
            "demand_based_price_adjustment_pct": 0.0,
            "insights": "Standard demand",
            "degraded": False,
            "llm_failed": False
        }
        inventory_data = {
            "inventory_status": "healthy",
            "current_margin_pct": 40.0,
            "min_viable_price": 1725.0,
            "inventory_pressure_adjustment_pct": 0.0,
            "insights": "Healthy inventory",
            "degraded": False,
            "llm_failed": False
        }

        result = PricingStrategyAgent.generate(
            product_fixture,
            market_data=market_data,
            demand_data=demand_data,
            inventory_data=inventory_data
        )

        assert result["fallback_used"] is True
        assert result["execution_route"] == "human_review"
        assert result["confidence_score"] == 0.0
        assert result["recommended_price"] == product_fixture.current_price
