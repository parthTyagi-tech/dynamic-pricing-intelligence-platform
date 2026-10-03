import re
from typing import Literal, List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.services.ai.client import async_guarded_json_completion

PRICE_RE = re.compile(r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d+)?)")


class CitedPrice(BaseModel):
    platform: str
    price: float


class StrategyProposal(BaseModel):
    strategy: Literal["penetration", "competitive", "premium", "clearance", "maintain"]
    proposed_price: float = Field(gt=0)
    rationale: str = Field(min_length=20, max_length=600)
    cited_prices: List[CitedPrice]


def verify_proposal(
    p: StrategyProposal,
    evidence: Dict[str, float],
    floor: float,
    current_price: float,
    tol: float = 0.01
) -> List[str]:
    """
    Deterministic validator:
    - Every cited price must exist in verified marketplace evidence within tolerance.
    - Every price mentioned in the rationale must match an allowed value (evidence, floor, current, proposed).
    """
    errors = []
    for c in p.cited_prices:  # cited prices must exist in evidence
        if c.platform not in evidence or abs(evidence[c.platform] - c.price) > tol * evidence[c.platform]:
            errors.append(f"cited price for {c.platform} not in evidence")

    allowed = set(evidence.values()) | {floor, current_price, p.proposed_price}
    for m in PRICE_RE.findall(p.rationale):  # every number in the rationale must be known
        val = float(m.replace(",", ""))
        if not any(abs(val - a) <= tol * max(a, 1) for a in allowed):
            errors.append(f"rationale mentions unverified price {val}")

    return errors


async def propose(
    cost: float,
    floor: float,
    current_price: float,
    inventory_quantity: int,
    evidence_platforms: List[Dict[str, Any]]
) -> Optional[StrategyProposal]:
    """
    Query LLM for a structured StrategyProposal using numbers only.
    Scraped titles and free text are NEVER included in the prompt.
    """
    system_prompt = (
        "You are an expert pricing strategist. Propose a pricing strategy based ONLY on the provided verified financial and marketplace metrics.\n"
        "Rules:\n"
        "1. Never mention any unverified prices in your rationale; only mention prices that match verified evidence, the floor, current price, or your proposed price.\n"
        "2. If you cite competitor prices in cited_prices, they must exactly match the platform price from evidence.\n"
        "3. Provide structured JSON matching StrategyProposal."
    )
    cleaned_evidence = [
        f"- Platform: {e.get('platform', 'unknown')}, Price: ₹{float(e.get('price', 0.0)):.2f}, Match Score: {float(e.get('match_score', 1.0)):.2f}, In Stock: {bool(e.get('in_stock', True))}"
        for e in evidence_platforms
    ]
    user_prompt = (
        f"FINANCIAL METRICS:\n"
        f"- Cost Price: ₹{cost:.2f}\n"
        f"- Floor Price: ₹{floor:.2f}\n"
        f"- Current Catalog Price: ₹{current_price:.2f}\n"
        f"- Inventory Quantity: {inventory_quantity}\n\n"
        f"VERIFIED EVIDENCE:\n"
        + ("\n".join(cleaned_evidence) if cleaned_evidence else "None")
        + "\n\nReturn your proposal as valid JSON matching StrategyProposal."
    )
    result = await async_guarded_json_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=StrategyProposal,
        agent_name="StrategyProposer",
        max_retries=2
    )
    if not result:
        return None
    try:
        return StrategyProposal.model_validate(result)
    except Exception:
        return None
