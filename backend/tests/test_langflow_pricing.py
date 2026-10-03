import asyncio
import json
import uuid
import pytest
from app.extensions import db
from app.models.organization import Organization
from app.models.product import Product
from app.services.orchestration.langflow_client import trigger_pricing_flow
from app.services.ai_pricing_service import _run_pipeline_async
from run import app


@pytest.mark.asyncio
async def test_trigger_pricing_flow_fallback(monkeypatch):
    # Simulate a network/http failure to verify fallback price uses current_price
    product_data = {"id": "p1", "current_price": 799.0, "cost_price": 400.0}
    market_data = {"competitor_prices": []}

    # Verify fallback uses current_price when Langflow call fails
    res = await trigger_pricing_flow(product_data, market_data)
    assert res["recommended_price"] == 799.0
    assert "strategy_explanation" in res


def test_ai_pricing_service_langflow_flag_no_unbound_local(monkeypatch):
    with app.app_context():
        org_id = str(uuid.uuid4())
        org = Organization(id=org_id, name="Langflow Org", invite_code=f"INV-{org_id[:6]}")
        db.session.add(org)

        prod_id = str(uuid.uuid4())
        product = Product(
            id=prod_id,
            sku=f"SKU-{prod_id[:6]}",
            name="Langflow Widget",
            brand="Acme",
            category="electronics",
            current_price=500.0,
            cost_price=300.0,
            inventory_quantity=10,
            organization_id=org_id
        )
        db.session.add(product)
        db.session.commit()

        monkeypatch.setenv("USE_LANGFLOW", "true")

        async def fake_trigger(prod_dict, market_dict):
            return {
                "recommended_price": 520.0,
                "strategy": "moderate_increase",
                "strategy_explanation": "Healthy demand permits small margin lift",
                "confidence": 0.85
            }

        async def fake_supervisor_exec(*args, **kwargs):
            return {"recommendation": {"platform_prices_snapshot": {}}}

        monkeypatch.setattr("app.services.agentic.supervisor_agent.SupervisorAgent.execute", fake_supervisor_exec)
        monkeypatch.setattr("app.services.ai_pricing_service.trigger_pricing_flow", fake_trigger)
        monkeypatch.setattr("app.services.ai_pricing_service.send_slack_alert", lambda *args, **kwargs: None)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_run_pipeline_async(product))
            assert result is not None
            assert result["recommended_price"] == 520.0
            assert "agent_analysis" in result
            assert "market_agent" in result["agent_analysis"]
            assert "compliance" in result
        finally:
            loop.close()
