from __future__ import annotations

import logging
import os
import socket
import time
from datetime import datetime, timezone

# Importing the Flask app must not start the development in-memory worker.
os.environ.setdefault("VERCEL", "1")

from run import app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.recommendation import PricingRecommendation  # noqa: E402
from app.models.recommendation_job import AgentRunStatus, RecommendationJob, RecommendationJobStatus  # noqa: E402
from app.services.recommendation_job_service import emit_event, mark_job_failed, mark_job_succeeded  # noqa: E402
from app.routes.recommendation_routes import process_task  # noqa: E402

logger = logging.getLogger("klypup.durable-worker")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
WORKER_ID = os.environ.get("WORKER_ID", f"{socket.gethostname()}:{os.getpid()}")
POLL_SECONDS = float(os.environ.get("WORKER_POLL_SECONDS", "2"))
STALE_AFTER_SECONDS = int(os.environ.get("WORKER_STALE_AFTER_SECONDS", "900"))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def reclaim_stale_jobs() -> None:
    cutoff = utcnow().timestamp() - STALE_AFTER_SECONDS
    with app.app_context():
        stale = RecommendationJob.query.filter(
            RecommendationJob.status == RecommendationJobStatus.RUNNING,
            RecommendationJob.last_heartbeat_at.isnot(None),
        ).all()
        changed = 0
        for job in stale:
            if job.last_heartbeat_at and job.last_heartbeat_at.timestamp() < cutoff:
                job.status = RecommendationJobStatus.QUEUED
                job.available_at = utcnow()
                job.worker_id = None
                job.error_message = "Requeued after stale worker heartbeat."
                changed += 1
        if changed:
            db.session.commit()
            logger.warning("Requeued %s stale recommendation job(s)", changed)


def claim_job() -> str | None:
    with app.app_context():
        job = (
            RecommendationJob.query.filter(
                RecommendationJob.status == RecommendationJobStatus.QUEUED,
                RecommendationJob.available_at <= utcnow(),
            )
            .order_by(RecommendationJob.created_at.asc())
            .with_for_update(skip_locked=True)
            .first()
        )
        if not job:
            return None
        job.status = RecommendationJobStatus.RUNNING
        job.worker_id = WORKER_ID
        job.attempts = int(job.attempts or 0) + 1
        job.started_at = job.started_at or utcnow()
        job.last_heartbeat_at = utcnow()
        emit_event(job, "orchestrator", AgentRunStatus.RUNNING, 5, "Durable worker claimed the recommendation job.")
        return job.id


def process_job(job_id: str) -> None:
    with app.app_context():
        job = RecommendationJob.query.get(job_id)
        if not job:
            logger.error("Recommendation job %s disappeared before processing", job_id)
            return
        recommendation = PricingRecommendation.query.get(job.recommendation_id)
        if not recommendation:
            mark_job_failed(job, "Recommendation record not found.")
            return
        try:
            with app.test_request_context(
                "/api/recommendations/process-task",
                method="POST",
                headers={"X-Klypup-Worker-Secret": os.environ.get("WORKER_CALLBACK_SECRET", "")},
                json={"recommendation_id": recommendation.id, "product_id": job.product_id, "job_id": job.id},
            ):
                response = process_task()
            status_code = response[1] if isinstance(response, tuple) and len(response) > 1 else 200
            if status_code >= 400:
                raise RuntimeError(f"Task callback returned HTTP {status_code}")
            db.session.refresh(job)
            db.session.refresh(recommendation)
            if recommendation.status == "failed":
                mark_job_failed(job, recommendation.rationale or "Recommendation pipeline failed.")
            elif job.status != RecommendationJobStatus.SUCCEEDED:
                mark_job_succeeded(job)
                emit_event(job, "orchestrator", AgentRunStatus.SUCCEEDED, 100, "All agents completed; recommendation is ready for review.")
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            mark_job_failed(job, str(exc))
            logger.exception("Recommendation job %s failed", job_id)


def main() -> None:
    logger.info("Durable Klypup worker started as %s", WORKER_ID)
    last_reclaim = 0.0
    while True:
        now = time.monotonic()
        if now - last_reclaim > max(30.0, POLL_SECONDS * 10):
            reclaim_stale_jobs()
            last_reclaim = now
        job = claim_job()
        if job:
            process_job(job)
        else:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
