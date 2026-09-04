import asyncio
import json
import logging
import time
import uuid
from flask import Blueprint, Response, jsonify, request, stream_with_context
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models.price_history import PriceHistory
from app.models.product import Product
from app.models.user import User
from app.services.agentic.approval_agent import ApprovalAgent
from app.services.agentic.supervisor_agent import SupervisorAgent
from app.services.catalog_ingestion_service import parse_and_ingest_catalog_csv
from app.services.event_bus import get_event_bus
from app.services.task_state.task_manager import (
    TaskAccessDeniedError,
    TaskNotFoundError,
    get_task_manager,
)

logger = logging.getLogger(__name__)

agentic_bp = Blueprint("agentic", __name__, url_prefix="/api/agentic")

# In-memory simple rate limiter (SEC-6: 15 req/min per user for expensive scraping)
_user_request_timestamps = {}


def check_rate_limit(user_id: str, limit: int = 15, window_sec: int = 60) -> bool:
    now = time.time()
    timestamps = _user_request_timestamps.get(user_id, [])
    # Keep only timestamps within window
    timestamps = [t for t in timestamps if now - t < window_sec]
    if len(timestamps) >= limit:
        return False
    timestamps.append(now)
    _user_request_timestamps[user_id] = timestamps
    return True


@agentic_bp.route("/recommend/<product_id>", methods=["POST"])
@jwt_required()
def start_recommendation(product_id: str):
    """
    SEC-1, SEC-6: Authenticated, org-scoped, rate-limited endpoint.
    Initiates autonomous multi-agent repricing task.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    # SEC-6: Rate limit check
    if not check_rate_limit(user.id, limit=15, window_sec=60):
        return jsonify({"success": False, "message": "Rate limit exceeded. Please wait a minute before requesting more recommendations."}), 429

    # SEC-1: Validate product ownership
    product = Product.query.filter_by(id=product_id, organization_id=user.organization_id).first()
    if not product:
        return jsonify({"success": False, "message": "Product not found or unauthorized"}), 404

    payload = request.get_json(silent=True) or {}
    force_refresh = bool(payload.get("force_refresh", False))
    simulate_failure_platform = payload.get("simulate_failure_platform")

    task_id = str(uuid.uuid4())
    task_mgr = get_task_manager()
    task = task_mgr.create_task(
        task_id=task_id,
        product_id=product.id,
        organization_id=user.organization_id,
        user_id=user.id,
        category=product.category or "general"
    )

    # Launch supervisor execution in background thread / async runner
    def run_supervisor_task():
        from flask import current_app
        with current_app.app_context():
            supervisor = SupervisorAgent()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    supervisor.execute(
                        task_id=task_id,
                        product_id=product.id,
                        organization_id=user.organization_id,
                        user_id=user.id,
                        force_refresh=force_refresh,
                        simulate_failure_platform=simulate_failure_platform
                    )
                )
            except Exception as e:
                logger.error(f"[agentic_routes] Supervisor error: {e}", exc_info=True)
                task_mgr.update_status(task_id, "failed", error_message=str(e))
            finally:
                loop.close()

    from threading import Thread
    thread = Thread(target=run_supervisor_task, daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "task_id": task_id,
        "product_id": product.id,
        "message": "Autonomous multi-agent recommendation task started."
    }), 202


@agentic_bp.route("/task/<task_id>/state", methods=["GET"])
@jwt_required()
def get_task_state(task_id: str):
    """
    SEC-1, SEC-2: Returns task snapshot.
    Enforces 403 Forbidden on cross-organization access.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    task_mgr = get_task_manager()
    try:
        task = task_mgr.get_task(task_id, requester_org_id=user.organization_id)
        return jsonify({"success": True, "task": task.to_dict()}), 200
    except TaskAccessDeniedError:
        # SEC-2: Explicit 403 Forbidden without leaking data
        return jsonify({"success": False, "message": "Access forbidden: Task belongs to another organization."}), 403
    except TaskNotFoundError:
        return jsonify({"success": False, "message": "Task not found"}), 404


@agentic_bp.route("/task/<task_id>/stream", methods=["GET"])
@jwt_required()
def stream_task_events(task_id: str):
    """
    SEC-2: Real-time Server-Sent Events (SSE) stream of agent messages.
    Returns 403 Forbidden if requester organization_id does not match task.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    task_mgr = get_task_manager()
    try:
        task = task_mgr.get_task(task_id, requester_org_id=user.organization_id)
    except TaskAccessDeniedError:
        return jsonify({"success": False, "message": "Access forbidden: Task belongs to another organization."}), 403
    except TaskNotFoundError:
        return jsonify({"success": False, "message": "Task not found"}), 404

    event_bus = get_event_bus()

    def event_generator():
        # First yield past history for this task
        if hasattr(event_bus, "get_history"):
            past = event_bus.get_history(task_id, organization_id=user.organization_id)
            for msg in past:
                yield f"data: {json.dumps(msg.dict())}\n\n"

        queue = asyncio.Queue()
        loop = asyncio.new_event_loop()

        def listener(msg):
            try:
                loop.call_soon_threadsafe(queue.put_nowait, msg)
            except Exception:
                pass

        event_bus.subscribe(task_id, listener, organization_id=user.organization_id)

        try:
            start_time = time.time()
            # Stream for up to 60 seconds or until completed
            while time.time() - start_time < 60:
                try:
                    # Non-blocking poll with sleep
                    msg = queue.get_nowait()
                    yield f"data: {json.dumps(msg.dict())}\n\n"
                    if msg.event_type in ("recommendation_ready_for_approval", "recommendation_served_from_cache", "task_failed"):
                        break
                except asyncio.QueueEmpty:
                    # Yield heartbeat keepalive
                    yield ": keepalive\n\n"
                    time.sleep(0.5)
        finally:
            event_bus.unsubscribe(task_id, listener)

    return Response(stream_with_context(event_generator()), mimetype="text/event-stream")


@agentic_bp.route("/task/<task_id>/approve", methods=["POST"])
@jwt_required()
def approve_recommendation(task_id: str):
    """
    SEC-1, SEC-2, SEC-8: Approves recommendation.
    Atomically commits price change and writes audit log.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    approval_agent = ApprovalAgent()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            approval_agent.approve(
                task_id=task_id,
                user_id=user.id,
                organization_id=user.organization_id
            )
        )
        return jsonify({"success": True, "data": result, "message": "Price update approved and applied."}), 200
    except TaskAccessDeniedError:
        return jsonify({"success": False, "message": "Access forbidden: Task belongs to another organization."}), 403
    except Exception as e:
        logger.error(f"[agentic_routes] Approval error: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        loop.close()


@agentic_bp.route("/task/<task_id>/reject", methods=["POST"])
@jwt_required()
def reject_recommendation(task_id: str):
    """
    SEC-1, SEC-2, SEC-8: Rejects recommendation with feedback reason.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    payload = request.get_json(silent=True) or {}
    reason = payload.get("reason", "Price rejected by user.")

    approval_agent = ApprovalAgent()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            approval_agent.reject(
                task_id=task_id,
                user_id=user.id,
                organization_id=user.organization_id,
                reason=reason
            )
        )
        return jsonify({"success": True, "data": result, "message": "Recommendation rejected."}), 200
    except TaskAccessDeniedError:
        return jsonify({"success": False, "message": "Access forbidden: Task belongs to another organization."}), 403
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        loop.close()


@agentic_bp.route("/product/<product_id>/price-history", methods=["GET"])
@jwt_required()
def get_price_history(product_id: str):
    """
    SEC-1: Fetches append-only price history for product.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    product = Product.query.filter_by(id=product_id, organization_id=user.organization_id).first()
    if not product:
        return jsonify({"success": False, "message": "Product not found or unauthorized"}), 404

    history = PriceHistory.query.filter_by(
        product_id=product.id,
        organization_id=user.organization_id
    ).order_by(PriceHistory.created_at.desc()).all()

    return jsonify({
        "success": True,
        "product_id": product.id,
        "history": [h.to_dict() for h in history]
    }), 200


@agentic_bp.route("/catalog/upload", methods=["POST"])
@jwt_required()
def upload_catalog_csv():
    """
    SEC-4: Validated and sanitized CSV upload with formula injection neutralization.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file uploaded."}), 400

    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"success": False, "message": "Empty filename."}), 400

    try:
        file_bytes = file.read()
        imported, updated, errors = parse_and_ingest_catalog_csv(
            file_bytes=file_bytes,
            filename=file.filename,
            organization_id=user.organization_id,
            user_id=user.id
        )
        return jsonify({
            "success": True,
            "imported_count": imported,
            "updated_count": updated,
            "errors": errors,
            "message": f"Successfully processed {imported} new and {updated} updated items."
        }), 200
    except ValueError as val_err:
        return jsonify({"success": False, "message": str(val_err)}), 400
    except Exception as e:
        logger.error(f"[agentic_routes] Catalog upload error: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Upload processing failed: {str(e)}"}), 500
