import uuid
import pytest
from unittest.mock import patch, AsyncMock
from run import app
from app.config import settings
from app.services.agentic.strategy_proposer import (
    StrategyProposal,
    CitedPrice,
    verify_proposal,
    propose
)
from app.services.agentic.pricing_reasoning_agent import PricingReasoningAgent
from app.services.task_state.task_manager import get_task_manager


def test_verify_proposal_deterministic_validation():
    evidence = {"Amazon": 2400.0, "Flipkart": 2420.0}
    floor = 2000.0
    current_price = 2500.0

    # 1. Valid proposal
    valid_p = StrategyProposal(
        strategy="competitive",
        proposed_price=2410.0,
        rationale="Floor is ₹2000.00 and current is ₹2500.00. Based on Amazon at ₹2400.00, recommend ₹2410.00.",
        cited_prices=[CitedPrice(platform="Amazon", price=2400.0)]
    )
    errors = verify_proposal(valid_p, evidence, floor, current_price)
    assert errors == []

    # 2. Fake cited price
    invalid_cite_p = StrategyProposal(
        strategy="competitive",
        proposed_price=2410.0,
        rationale="Floor is ₹2000.00 and current is ₹2500.00. Based on Amazon at ₹2400.00, recommend ₹2410.00.",
        cited_prices=[CitedPrice(platform="Blinkit", price=1999.0)]
    )
    errors = verify_proposal(invalid_cite_p, evidence, floor, current_price)
    assert any("cited price for Blinkit not in evidence" in e for e in errors)

    # 3. Unverified price hallucinated in rationale
    hallucinated_p = StrategyProposal(
        strategy="competitive",
        proposed_price=2410.0,
        rationale="We observed an extreme competitor pricing at ₹9999.00 in the market.",
        cited_prices=[CitedPrice(platform="Amazon", price=2400.0)]
    )
    errors = verify_proposal(hallucinated_p, evidence, floor, current_price)
    assert any("rationale mentions unverified price 9999" in e for e in errors)


@pytest.mark.asyncio
async def test_mocked_proposal_fake_price_falls_back_and_trace_shows_error(monkeypatch):
    """(a) Mocked proposal citing a fake price -> falls back, trace shows the error."""
    monkeypatch.setattr(settings, "AGENTIC_LLM_PROPOSER", True)
    
    agent = PricingReasoningAgent()
    task_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    prod_id = str(uuid.uuid4())

    get_task_manager().create_task(task_id, prod_id, org_id)

    product = {
        "id": prod_id,
        "name": "Noise Cancelling Headphones",
        "current_price": 2500.0,
        "cost_price": 1800.0,
        "min_margin_percentage": 10.0,
        "inventory_quantity": 40
    }
    
    aggregated_data = {
        "verified_count": 2,
        "average_price": 2400.0,
        "platforms": {
            "Amazon": {"price": 2400.0, "verified": True, "match_score": 0.95},
            "Flipkart": {"price": 2450.0, "verified": True, "match_score": 0.92}
        }
    }

    # Proposal cites an invented price/platform
    bad_proposal = StrategyProposal(
        strategy="competitive",
        proposed_price=2300.0,
        rationale="Observed unverified deal at ₹1200.00 on Zepto.",
        cited_prices=[CitedPrice(platform="Zepto", price=1200.0)]
    )

    with patch("app.services.agentic.strategy_proposer.propose", new_callable=AsyncMock) as mock_prop:
        mock_prop.return_value = bad_proposal

        result = await agent.generate_recommendation(task_id, product, aggregated_data, org_id)

        # Invariant: Must fall back to deterministic target
        assert result["llm_proposer_used"] is False
        assert len(result["proposer_validation_errors"]) > 0

        # Invariant: Decision trace records validation failure
        traces = get_task_manager().get_decision_traces(task_id)
        proposer_trace = next((t for t in traces if t["agent"] == "StrategyProposer"), None)
        assert proposer_trace is not None
        assert "validation errors" in proposer_trace["rationale"]
        assert "LLM proposer used: no" in proposer_trace["rationale"]


@pytest.mark.asyncio
async def test_mocked_proposal_below_floor_clamped_to_floor(monkeypatch):
    """(b) Mocked proposal below floor -> clamped to floor, margin_floor_applied=True."""
    monkeypatch.setattr(settings, "AGENTIC_LLM_PROPOSER", True)
    
    agent = PricingReasoningAgent()
    task_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    
    # Cost 2000, 10% margin -> Floor = 2200.0
    product = {
        "id": str(uuid.uuid4()),
        "name": "Luxury Speaker",
        "current_price": 2500.0,
        "cost_price": 2000.0,
        "min_margin_percentage": 10.0,
        "inventory_quantity": 40
    }
    
    aggregated_data = {
        "verified_count": 1,
        "average_price": 2100.0,
        "platforms": {
            "Amazon": {"price": 2100.0, "verified": True, "match_score": 0.95}
        }
    }

    # Proposal is below floor: proposed 2100.0 < 2200.0
    proposal = StrategyProposal(
        strategy="competitive",
        proposed_price=2100.0,
        rationale="Based on Amazon at ₹2100.00, matching market index to protect sales volume.",
        cited_prices=[CitedPrice(platform="Amazon", price=2100.0)]
    )

    with patch("app.services.agentic.strategy_proposer.propose", new_callable=AsyncMock) as mock_prop:
        mock_prop.return_value = proposal

        result = await agent.generate_recommendation(task_id, product, aggregated_data, org_id)

        assert result["llm_proposer_used"] is True
        assert result["recommended_price"] == 2200.0  # Hard clamped to floor
        assert result["margin_floor_applied"] is True


@pytest.mark.asyncio
async def test_mocked_proposal_plus_80_percent_flags_sanity_bound(monkeypatch):
    """(c) Mocked proposal +80% -> sanity_bound_flagged=True."""
    monkeypatch.setattr(settings, "AGENTIC_LLM_PROPOSER", True)
    
    agent = PricingReasoningAgent()
    task_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    
    # Current 1000.0, proposal 1800.0 (+80%)
    product = {
        "id": str(uuid.uuid4()),
        "name": "Trending Keyboard",
        "current_price": 1000.0,
        "cost_price": 600.0,
        "min_margin_percentage": 10.0,
        "inventory_quantity": 10
    }
    
    aggregated_data = {
        "verified_count": 1,
        "average_price": 1800.0,
        "platforms": {
            "Amazon": {"price": 1800.0, "verified": True, "match_score": 0.95}
        }
    }

    proposal = StrategyProposal(
        strategy="premium",
        proposed_price=1800.0,
        rationale="Amazon price is ₹1800.00. Harvesting scarcity premium given high demand.",
        cited_prices=[CitedPrice(platform="Amazon", price=1800.0)]
    )

    with patch("app.services.agentic.strategy_proposer.propose", new_callable=AsyncMock) as mock_prop:
        mock_prop.return_value = proposal

        result = await agent.generate_recommendation(task_id, product, aggregated_data, org_id)

        assert result["llm_proposer_used"] is True
        assert result["recommended_price"] == 1800.0
        assert result["sanity_bound_flagged"] is True
        assert result["confidence"] == "low"
        assert result["confidence_score"] <= 0.40


@pytest.mark.asyncio
async def test_flag_off_output_identical_to_default_deterministic(monkeypatch):
    """(d) Flag off -> output identical to current behavior."""
    monkeypatch.setattr(settings, "AGENTIC_LLM_PROPOSER", False)
    
    agent = PricingReasoningAgent()
    task_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    
    product = {
        "id": str(uuid.uuid4()),
        "name": "Standard Mouse",
        "current_price": 1000.0,
        "cost_price": 600.0,
        "min_margin_percentage": 10.0,
        "inventory_quantity": 40
    }
    
    aggregated_data = {
        "verified_count": 1,
        "average_price": 950.0,
        "platforms": {
            "Amazon": {"price": 950.0, "verified": True, "match_score": 0.95}
        }
    }

    with patch("app.services.agentic.strategy_proposer.propose", new_callable=AsyncMock) as mock_prop:
        result = await agent.generate_recommendation(task_id, product, aggregated_data, org_id)

        # Propose was never called when flag is off
        mock_prop.assert_not_called()
        assert result["llm_proposer_used"] is False
        assert result["proposer_validation_errors"] == []
        assert result["recommended_price"] == round(950.0 * 0.99, 2)
