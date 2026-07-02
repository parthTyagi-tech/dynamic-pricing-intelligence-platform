from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from app.extensions import db
from app.models.user import User
from app.models.ai_call_log import AICallLog

observability_bp = Blueprint("observability", __name__)


@observability_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_observability_stats():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    org_id = current_user.organization_id

    # 1. Aggregate core metrics
    metrics = db.session.query(
        func.sum(AICallLog.cost).label("total_cost"),
        func.sum(AICallLog.total_tokens).label("total_tokens"),
        func.avg(AICallLog.latency_ms).label("avg_latency"),
        func.count(AICallLog.id).label("total_calls")
    ).filter(AICallLog.organization_id == org_id).first()

    total_cost = round(metrics.total_cost or 0.0, 4)
    total_tokens = metrics.total_tokens or 0
    avg_latency = round(metrics.avg_latency or 0.0, 2)
    total_calls = metrics.total_calls or 0

    # 2. Success rate
    successes = AICallLog.query.filter(
        AICallLog.organization_id == org_id,
        AICallLog.status == "success"
    ).count()
    success_rate = round((successes / total_calls * 100), 2) if total_calls > 0 else 100.0

    # 3. Agent distribution metrics
    agent_metrics = db.session.query(
        AICallLog.agent_name,
        func.count(AICallLog.id).label("calls_count"),
        func.avg(AICallLog.latency_ms).label("avg_latency"),
        func.sum(AICallLog.cost).label("total_cost")
    ).filter(AICallLog.organization_id == org_id).group_by(AICallLog.agent_name).all()

    agents_data = []
    for am in agent_metrics:
        agents_data.append({
            "name": am.agent_name,
            "calls": am.calls_count,
            "avg_latency": round(am.avg_latency or 0.0, 2),
            "cost": round(am.total_cost or 0.0, 5)
        })

    # 4. Model distribution
    model_metrics = db.session.query(
        AICallLog.model_name,
        func.count(AICallLog.id).label("calls_count")
    ).filter(AICallLog.organization_id == org_id).group_by(AICallLog.model_name).all()

    models_data = []
    for mm in model_metrics:
        models_data.append({
            "name": mm.model_name,
            "calls": mm.calls_count
        })

    # 5. Recent calls history
    recent_calls = AICallLog.query.filter(
        AICallLog.organization_id == org_id
    ).order_by(AICallLog.timestamp.desc()).limit(15).all()
    recent_logs = [log.to_dict() for log in recent_calls]

    # 6. Cost chart points (Recent 15 call costs for a timeline graph)
    cost_timeline = []
    # Query logs in chronological order to build a nice timeline
    timeline_logs = AICallLog.query.filter(
        AICallLog.organization_id == org_id
    ).order_by(AICallLog.timestamp.asc()).limit(30).all()

    cumulative_cost = 0.0
    for l in timeline_logs:
        cumulative_cost += l.cost
        cost_timeline.append({
            "timestamp": l.timestamp.strftime("%H:%M:%S"),
            "call_cost": round(l.cost, 5),
            "cumulative_cost": round(cumulative_cost, 4),
            "latency": l.latency_ms
        })

    return {
        "success": True,
        "metrics": {
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "avg_latency": avg_latency,
            "total_calls": total_calls,
            "success_rate": success_rate
        },
        "agents": agents_data,
        "models": models_data,
        "recent_logs": recent_logs,
        "cost_timeline": cost_timeline
    }, 200
