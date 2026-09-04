import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskAccessDeniedError(Exception):
    """Raised when an org tries to read or modify a task belonging to another org (SEC-2)."""
    pass


class TaskNotFoundError(Exception):
    """Raised when task_id does not exist."""
    pass


class TaskState:
    def __init__(
        self,
        task_id: str,
        product_id: str,
        organization_id: str,
        user_id: Optional[str] = None,
        category: str = "general",
    ):
        self.task_id = task_id
        self.product_id = product_id
        self.organization_id = organization_id
        self.user_id = user_id
        self.category = category
        self.status = "queued"  # queued, running, succeeded, failed, rejected
        self.dispatched_platforms: List[str] = []
        self.platform_results: Dict[str, Any] = {}
        self.events: List[Dict[str, Any]] = []
        self.decision_traces: List[Dict[str, Any]] = []
        self.recommendation: Optional[Dict[str, Any]] = None
        self.error_message: Optional[str] = None
        self.confidence: str = "high"
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "product_id": self.product_id,
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "category": self.category,
            "status": self.status,
            "dispatched_platforms": self.dispatched_platforms,
            "platform_results": self.platform_results,
            "events": self.events,
            "decision_traces": self.decision_traces,
            "recommendation": self.recommendation,
            "error_message": self.error_message,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class TaskManager:
    """
    Central Task State & Memory Manager.
    Maintains task progress, agent execution history, and strict multi-tenant isolation.
    """

    def __init__(self):
        self._tasks: Dict[str, TaskState] = {}
        self._lock = threading.RLock()

    def create_task(
        self,
        task_id: str,
        product_id: str,
        organization_id: str,
        user_id: Optional[str] = None,
        category: str = "general"
    ) -> TaskState:
        with self._lock:
            task = TaskState(
                task_id=task_id,
                product_id=product_id,
                organization_id=organization_id,
                user_id=user_id,
                category=category,
            )
            self._tasks[task_id] = task
            logger.info(f"[TaskManager] Created task {task_id} for product {product_id} (Org: {organization_id})")
            return task

    def get_task(self, task_id: str, requester_org_id: str) -> TaskState:
        """
        Retrieves task state.
        SEC-2: Enforces that requester_org_id matches task.organization_id.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(f"Task {task_id} not found.")

            if task.organization_id != requester_org_id:
                logger.warning(
                    f"[TaskManager SEC-2 VIOLATION] Org {requester_org_id} attempted access to task {task_id} owned by Org {task.organization_id}"
                )
                raise TaskAccessDeniedError(f"Access forbidden: Task belongs to another organization.")

            return task

    def append_event(
        self,
        task_id: str,
        agent: str,
        event_type: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return

            event = {
                "agent": agent,
                "event_type": event_type,
                "message": message,
                "payload": payload or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            task.events.append(event)
            task.updated_at = datetime.now(timezone.utc).isoformat()

    def add_decision_trace(
        self,
        task_id: str,
        agent: str,
        decision_point: str,
        rationale: str,
        action_taken: str
    ) -> None:
        """Records an explainable decision made by an autonomous agent."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return

            trace = {
                "agent": agent,
                "decision_point": decision_point,
                "rationale": rationale,
                "action_taken": action_taken,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            task.decision_traces.append(trace)
            task.updated_at = datetime.now(timezone.utc).isoformat()

    def update_status(self, task_id: str, status: str, error_message: Optional[str] = None) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task.status = status
            if error_message:
                task.error_message = error_message
            task.updated_at = datetime.now(timezone.utc).isoformat()

    def set_recommendation(self, task_id: str, recommendation: Dict[str, Any]) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task.recommendation = recommendation
            task.updated_at = datetime.now(timezone.utc).isoformat()


# Global Singleton
_task_manager = TaskManager()


def get_task_manager() -> TaskManager:
    return _task_manager
