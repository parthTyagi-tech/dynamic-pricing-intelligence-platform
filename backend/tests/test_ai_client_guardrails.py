import pytest
from pydantic import BaseModel, Field
from app.services.ai.client import async_guarded_json_completion


class SamplePricingSchema(BaseModel):
    recommended_price: float = Field(gt=0)
    confidence: float = Field(ge=0.0, le=1.0)


@pytest.mark.asyncio
async def test_async_guarded_json_completion_retry_and_newlines(monkeypatch):
    attempts = []

    async def fake_async_structured_json(system_prompt, user_prompt, **kwargs):
        attempts.append(user_prompt)
        if len(attempts) == 1:
            # First attempt returns invalid schema (missing recommended_price)
            return {"confidence": 0.9}
        else:
            # Second attempt returns valid schema
            return {"recommended_price": 499.0, "confidence": 0.95}

    monkeypatch.setattr("app.services.ai.client.async_structured_json_completion", fake_async_structured_json)

    res = await async_guarded_json_completion(
        system_prompt="You are a pricing engine.",
        user_prompt="Evaluate SKU-100",
        response_model=SamplePricingSchema,
        agent_name="TestPricingAgent",
        max_retries=2
    )

    assert res is not None
    assert res["recommended_price"] == 499.0
    assert res["confidence"] == 0.95
    assert len(attempts) == 2

    retry_prompt = attempts[1]
    # Check that real newlines are present, NOT literal escaped '\\n'
    assert "\\n\\nERROR" not in retry_prompt
    assert "\n\nERROR ON PREVIOUS ATTEMPT:\n" in retry_prompt
    assert "Invalid JSON provided:" in retry_prompt
    assert '{"confidence": 0.9}' in retry_prompt
