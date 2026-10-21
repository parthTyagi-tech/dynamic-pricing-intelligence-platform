import asyncio
import json
import os
import uuid
import pytest
from datetime import datetime, timezone
from starlette.testclient import TestClient

# Configure in-memory database and mock scraping for fast, deterministic testing
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["MOCK_SCRAPING"] = "true"

from app.extensions import db
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.product import Product, ProductCategory, RecommendationStatus
from app.models.pricing_recommendation import PricingRecommendation
from app.models.recommendation import ApprovalAction, ApprovalActionType
from app.models.audit_loging import PricingRule, AuditLog
from app.models.scraper_reliability import CircuitState, ScraperReliability
from app.services.pricing.price_writer import StalePriceError, AlreadyDecidedError
from app.mcp.server import (
    mcp,
    _get_flask_app,
    scrape_marketplace,
    scrape_category_swarm,
    run_full_pricing_swarm,
    approve_or_reject_recommendation,
    rollback_price_change,
    check_or_reset_circuit_breakers,
    simulate_price_elasticity,
    MCPAgentAuthMiddleware,
)


@pytest.fixture(scope="session")
def app():
    flask_app = _get_flask_app()
    flask_app.config["TESTING"] = True
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with flask_app.app_context():
        db.create_all()
    yield flask_app


@pytest.fixture(autouse=True)
def clean_db(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        yield
        db.session.remove()


@pytest.fixture
def seeded_env(app):
    with app.app_context():
        org_id = f"org-{uuid.uuid4().hex[:8]}"
        org = Organization(id=org_id, name="Test Retail Corp", invite_code=f"INV-{org_id[:4]}")
        db.session.add(org)

        user_id = f"user-{uuid.uuid4().hex[:8]}"
        user = User(
            id=user_id,
            name="Test Pricing Admin",
            email="admin@testretail.com",
            role=UserRole.ADMIN,
            organization_id=org_id,
        )
        user.set_password("SecurePassword123!")
        db.session.add(user)

        rule = PricingRule(
            id=f"rule-{uuid.uuid4().hex[:8]}",
            organization_id=org_id,
            minimum_margin=0.15,
            auto_execute_threshold=0.90,
        )
        db.session.add(rule)

        prod_id = f"prod-{uuid.uuid4().hex[:8]}"
        product = Product(
            id=prod_id,
            sku="SKU-ELECTRONICS-01",
            name="boAt BassHeads 100 Wired Earphones",
            brand="boAt",
            category="electronics",
            current_price=399.0,
            cost_price=250.0,
            inventory_quantity=50,
            min_margin_percentage=15.0,
            organization_id=org_id,
        )
        db.session.add(product)
        db.session.commit()

        # Set environment variables for MCP tenant resolution
        os.environ["KLYPUP_MCP_ORG_ID"] = org_id
        os.environ["KLYPUP_MCP_USER_ID"] = user_id

        yield {
            "org_id": org_id,
            "user_id": user_id,
            "product_id": prod_id,
            "sku": "SKU-ELECTRONICS-01",
        }


# ===========================================================================
# 1. MCP Tool, Resource, and Prompt Registration Tests
# ===========================================================================

def test_mcp_registration():
    """Verifies that all 7 tools, 4 resources, and 2 prompts are registered on FastMCP."""
    tool_names = {t.name for t in mcp._tool_manager.list_tools()}
    expected_tools = {
        "scrape_marketplace",
        "scrape_category_swarm",
        "run_full_pricing_swarm",
        "approve_or_reject_recommendation",
        "rollback_price_change",
        "check_or_reset_circuit_breakers",
        "simulate_price_elasticity",
    }
    assert expected_tools.issubset(tool_names), f"Missing tools: {expected_tools - tool_names}"

    # Resources: static URIs + template URIs
    static_uris = {str(r.uri) for r in mcp._resource_manager.list_resources()}
    assert "klypup://catalog/products" in static_uris
    assert "klypup://scrapers/health" in static_uris
    assert "klypup://recommendations/pending" in static_uris

    template_uris = {t.uri_template for t in mcp._resource_manager.list_templates()}
    assert "klypup://catalog/product/{sku}/history" in template_uris

    # Prompts
    prompt_names = {p.name for p in mcp._prompt_manager.list_prompts()}
    assert "audit_sku_pricing" in prompt_names
    assert "diagnose_platform_sensor" in prompt_names


# ===========================================================================
# 2. Tenant Isolation Tests (SEC-1 / SEC-2)
# ===========================================================================

@pytest.mark.asyncio
async def test_tenant_isolation_sec1_sec2(app, seeded_env):
    """Verifies that accessing products outside the tenant organization raises SEC-1/SEC-2 errors."""
    with app.app_context():
        # Create a product in a completely different foreign organization
        foreign_org = Organization(id="foreign-org-99", name="Foreign Corp", invite_code="FOR99")
        db.session.add(foreign_org)
        foreign_prod = Product(
            id="foreign-prod-99",
            sku="FOREIGN-SKU-99",
            name="Foreign Laptop",
            brand="Foreign",
            category="electronics",
            current_price=50000.0,
            cost_price=40000.0,
            organization_id="foreign-org-99",
        )
        db.session.add(foreign_prod)
        db.session.commit()

    # Tenant is currently scoped to seeded_env["org_id"]
    with pytest.raises(ValueError, match="SEC-1"):
        await scrape_category_swarm(product_id="foreign-prod-99")

    with pytest.raises(ValueError, match="SEC-1"):
        await run_full_pricing_swarm(product_id="foreign-prod-99")

    with pytest.raises(ValueError, match="SEC-1"):
        await simulate_price_elasticity(product_id="foreign-prod-99")


# ===========================================================================
# 3. Tool: scrape_marketplace
# ===========================================================================

@pytest.mark.asyncio
async def test_scrape_marketplace_tool(seeded_env):
    """Tests the scrape_marketplace tool across registered scrapers."""
    result = await scrape_marketplace(
        platform="Amazon.in",
        product_name="boAt BassHeads 100 Wired Earphones",
        brand="boAt",
        catalog_price=399.0,
    )
    assert result["platform"] == "Amazon.in"
    assert result["price"] > 0
    assert result["match_score"] >= 0.70
    assert "tier_used" in result
    assert "in_stock" in result


# ===========================================================================
# 4. Tool: scrape_category_swarm
# ===========================================================================

@pytest.mark.asyncio
async def test_scrape_category_swarm_tool(seeded_env):
    """Tests category swarm scraping and MAD aggregation for electronics SKU."""
    result = await scrape_category_swarm(product_id=seeded_env["product_id"])
    assert result["sku"] == seeded_env["sku"]
    assert result["category"] == "electronics"
    assert len(result["target_platforms"]) >= 2
    assert result["market_avg"] > 0
    assert result["verified_count"] >= 1
    assert isinstance(result["valid_offers"], list)


# ===========================================================================
# 5. Tool: run_full_pricing_swarm & SEC-9 Margin Floor
# ===========================================================================

@pytest.mark.asyncio
async def test_run_full_pricing_swarm_and_margin_floor(seeded_env):
    """Tests full pricing swarm execution, Agent A vs B debate, and margin floor clamping."""
    result = await run_full_pricing_swarm(product_id=seeded_env["sku"], force_refresh=True)
    assert result["sku"] == seeded_env["sku"]
    assert result["recommended_price"] > 0
    # Cost is 250.0 and minimum margin is 15%, so floor is at least 250 / (1 - 0.15) = 294.12
    assert result["recommended_price"] >= 287.5  # cost * 1.15
    assert "confidence_score" in result
    assert "reasoning_text" in result
    assert result["status"] == "pending"


# ===========================================================================
# 6. Tool: approve_or_reject_recommendation & CAS Optimistic Concurrency
# ===========================================================================

@pytest.mark.asyncio
async def test_approve_or_reject_recommendation_and_cas(app, seeded_env):
    """Tests approving a recommendation with CAS validation and creating ApprovalAction."""
    # 1. Run pricing swarm to produce a pending recommendation
    rec_res = await run_full_pricing_swarm(product_id=seeded_env["product_id"], force_refresh=True)
    rec_id = rec_res["recommendation_id"]

    # 2. Approve recommendation
    approval_res = await approve_or_reject_recommendation(
        recommendation_id=rec_id,
        action="approve",
        reason="Approved by executive analyst via MCP",
    )
    assert approval_res["status"] == "approved"
    assert "action_id" in approval_res
    assert approval_res["new_price"] == rec_res["recommended_price"]
    assert approval_res["old_price"] == 399.0

    # Verify Product.current_price was updated in the database
    with app.app_context():
        prod = Product.query.get(seeded_env["product_id"])
        assert float(prod.current_price) == rec_res["recommended_price"]
        rec = PricingRecommendation.query.get(rec_id)
        assert rec.status == RecommendationStatus.APPROVED

        # Verify ApprovalAction record was persisted
        action = ApprovalAction.query.get(approval_res["action_id"])
        assert action is not None
        assert action.action_type == ApprovalActionType.APPROVE
        assert action.previous_price == 399.0
        assert action.executed_price == rec_res["recommended_price"]

    # 3. Attempting to approve again must fail with AlreadyDecidedError
    with pytest.raises(AlreadyDecidedError):
        await approve_or_reject_recommendation(recommendation_id=rec_id, action="approve")


@pytest.mark.asyncio
async def test_approve_stale_price_concurrency(app, seeded_env):
    """Tests that optimistic concurrency blocks approval if current_price drifted from rec.base_price."""
    # Run swarm
    rec_res = await run_full_pricing_swarm(product_id=seeded_env["product_id"], force_refresh=True)
    rec_id = rec_res["recommendation_id"]

    # Drift the product's price externally in the database
    with app.app_context():
        prod = Product.query.get(seeded_env["product_id"])
        prod.current_price = 550.0
        db.session.commit()

    # Attempt to approve must raise StalePriceError
    with pytest.raises(StalePriceError):
        await approve_or_reject_recommendation(recommendation_id=rec_id, action="approve")


# ===========================================================================
# 7. Tool: rollback_price_change & Anti-Replay Guardrail
# ===========================================================================

@pytest.mark.asyncio
async def test_rollback_price_change_anti_replay(app, seeded_env):
    """Tests rolling back an approved price change to the previous price and blocking duplicate rollbacks."""
    # Run swarm and approve
    rec_res = await run_full_pricing_swarm(product_id=seeded_env["product_id"], force_refresh=True)
    rec_id = rec_res["recommendation_id"]
    approval_res = await approve_or_reject_recommendation(recommendation_id=rec_id, action="approve")
    action_id = approval_res["action_id"]

    # Rollback price change
    rollback_res = await rollback_price_change(action_id=action_id)
    assert rollback_res["status"] == "rolled_back"
    assert rollback_res["restored_price"] == 399.0

    # Verify database current_price is restored to 399.0
    with app.app_context():
        prod = Product.query.get(seeded_env["product_id"])
        assert float(prod.current_price) == 399.0

    # Attempting duplicate rollback must fail anti-replay check
    with pytest.raises(ValueError, match="already been rolled back"):
        await rollback_price_change(action_id=action_id)


# ===========================================================================
# 8. Tool: check_or_reset_circuit_breakers
# ===========================================================================

@pytest.mark.asyncio
async def test_check_or_reset_circuit_breakers(app, seeded_env):
    """Tests inspecting and resetting circuit breakers for all 18 scraper platforms."""
    # First trip a circuit breaker manually
    with app.app_context():
        rel = ScraperReliability(platform="Amazon.in", circuit_state=CircuitState.OPEN, failure_count_last_hour=6)
        db.session.merge(rel)
        db.session.commit()

    # Call reset
    res = await check_or_reset_circuit_breakers(reset=True, run_canaries=False)
    assert res["total_platforms"] == 18
    assert res["reset_executed"] is True

    amazon_data = next(p for p in res["platforms"] if p["platform"] == "Amazon.in")
    assert amazon_data["circuit_state"] == CircuitState.CLOSED
    assert amazon_data["failure_count_last_hour"] == 0


# ===========================================================================
# 9. Tool: simulate_price_elasticity
# ===========================================================================

@pytest.mark.asyncio
async def test_simulate_price_elasticity(seeded_env):
    """Tests non-mutating log-linear elasticity modeling."""
    sim = await simulate_price_elasticity(
        product_id=seeded_env["sku"],
        elasticity=-1.5,
        days=14,
    )
    assert sim["sku"] == seeded_env["sku"]
    assert sim["simulation_days"] == 14
    assert len(sim["timeline"]) == 14
    assert sim["projected_total_revenue"] > 0
    assert sim["projected_total_profit"] > 0
    assert sim["margin_floor"] >= 250.0


# ===========================================================================
# 10. Resources and Prompts
# ===========================================================================

@pytest.mark.asyncio
async def test_mcp_resources(seeded_env):
    """Tests reading all 4 klypup:// resources."""
    # 1. klypup://catalog/products
    res1 = await mcp._resource_manager.get_resource("klypup://catalog/products")
    content1 = await res1.read()
    products_data = json.loads(content1)
    assert len(products_data) >= 1
    assert products_data[0]["sku"] == seeded_env["sku"]

    # 2. klypup://catalog/product/{sku}/history
    res2 = await mcp._resource_manager.get_resource(f"klypup://catalog/product/{seeded_env['sku']}/history")
    content2 = await res2.read()
    history_data = json.loads(content2)
    assert history_data["product"]["sku"] == seeded_env["sku"]

    # 3. klypup://scrapers/health
    res3 = await mcp._resource_manager.get_resource("klypup://scrapers/health")
    content3 = await res3.read()
    health_data = json.loads(content3)
    assert len(health_data) == 18

    # 4. klypup://recommendations/pending
    res4 = await mcp._resource_manager.get_resource("klypup://recommendations/pending")
    content4 = await res4.read()
    recs_data = json.loads(content4)
    assert isinstance(recs_data, list)


@pytest.mark.asyncio
async def test_mcp_prompts(seeded_env):
    """Tests rendering audit_sku_pricing and diagnose_platform_sensor prompts."""
    # Prompt 1
    p1 = mcp._prompt_manager.get_prompt("audit_sku_pricing")
    rendered1 = await p1.render({"sku": seeded_env["sku"]})
    assert len(rendered1) == 1
    assert seeded_env["sku"] in rendered1[0].content.text

    # Prompt 2
    p2 = mcp._prompt_manager.get_prompt("diagnose_platform_sensor")
    rendered2 = await p2.render({"platform": "Flipkart"})
    assert len(rendered2) == 1
    assert "Flipkart" in rendered2[0].content.text


# ===========================================================================
# 11. SSE Middleware & Bearer Authentication Tests
# ===========================================================================

def test_sse_bearer_auth_and_health():
    """
    Tests Render cloud deployment requirements:
    - GET /health returns 200 OK without token.
    - /sse and /messages reject missing or invalid Bearer tokens with 401 Unauthorized.
    """
    test_api_key = "render-prod-secret-999"
    app = mcp.sse_app()
    app.add_middleware(MCPAgentAuthMiddleware, api_key=test_api_key)

    client = TestClient(app, base_url="http://localhost:8001")

    # 1. Health check probe
    resp_health = client.get("/health")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] == "healthy"

    resp_healthz = client.get("/healthz")
    assert resp_healthz.status_code == 200

    # 2. Unauthorized request to SSE endpoint
    resp_unauth = client.get("/sse")
    assert resp_unauth.status_code == 401
    assert "Unauthorized" in resp_unauth.json()["error"]

    # 3. Invalid Bearer token
    resp_bad = client.get("/sse", headers={"authorization": "Bearer wrong-token"})
    assert resp_bad.status_code == 401
