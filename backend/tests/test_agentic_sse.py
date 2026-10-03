import uuid
import pytest
from flask_jwt_extended import create_access_token
from app.extensions import db
from app.models.organization import Organization
from app.models.user import User
from app.services.event_bus import get_event_bus
from app.services.event_bus.base import AgentMessage
from app.services.task_state.task_manager import get_task_manager
from run import app


@pytest.fixture
def sse_setup():
    with app.app_context():
        org_id = str(uuid.uuid4())
        org = Organization(id=org_id, name="SSE Test Org", invite_code=f"INV-{org_id[:6]}")
        db.session.add(org)

        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            name="SSE User",
            email=f"user-{user_id[:8]}@example.com",
            organization_id=org_id,
            role="admin",
            password_hash="mockhash"
        )
        db.session.add(user)
        db.session.commit()

        token = create_access_token(identity=user_id)
        task_id = str(uuid.uuid4())
        task_mgr = get_task_manager()
        task_mgr.create_task(
            task_id=task_id,
            product_id=str(uuid.uuid4()),
            organization_id=org_id,
            user_id=user_id,
            category="electronics"
        )

        yield {
            "token": token,
            "user_id": user_id,
            "org_id": org_id,
            "task_id": task_id
        }


def test_agentic_stream_task_events_sse(sse_setup):
    client = app.test_client()

    event_bus = get_event_bus()
    msg = AgentMessage(
        agent="MarketIntelligenceAgent",
        product_id="prod-123",
        task_id=sse_setup["task_id"],
        organization_id=sse_setup["org_id"],
        event_type="recommendation_ready_for_approval",
        payload={"price": 999.0}
    )
    # Store in history so generator yields it immediately
    if hasattr(event_bus, "_history"):
        event_bus._history[sse_setup["task_id"]].append(msg)

    res = client.get(
        f"/api/agentic/task/{sse_setup['task_id']}/stream",
        headers={"Authorization": f"Bearer {sse_setup['token']}"}
    )

    assert res.status_code == 200
    assert "text/event-stream" in res.content_type

    # Read the first event from stream
    stream_iter = res.response
    first_chunk = next(stream_iter)
    chunk_str = first_chunk.decode("utf-8") if isinstance(first_chunk, bytes) else first_chunk
    assert "data: " in chunk_str
    assert "recommendation_ready_for_approval" in chunk_str
    assert "prod-123" in chunk_str
