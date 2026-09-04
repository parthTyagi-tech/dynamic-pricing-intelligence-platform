import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional
import threading

from app.services.event_bus.base import AgentMessage, EventBus

logger = logging.getLogger(__name__)


class LocalEventBus(EventBus):
    """
    Thread-safe, in-memory event bus with async delivery and event history buffering.
    Enforces organization-level and task-level scoping (SEC-1, SEC-2).
    """

    def __init__(self):
        self._subscribers: Dict[str, List[tuple]] = defaultdict(list)
        self._history: Dict[str, List[AgentMessage]] = defaultdict(list)
        self._lock = threading.RLock()

    async def publish(self, message: AgentMessage) -> None:
        """Publish a message, record in history buffer, and notify subscribers."""
        task_id = message.task_id
        org_id = message.organization_id

        logger.info(
            f"[LocalEventBus] [{message.agent}] Task {task_id} Event: {message.event_type} (Org: {org_id})"
        )

        with self._lock:
            # Store in rolling history buffer (keep last 100 messages per task)
            self._history[task_id].append(message)
            if len(self._history[task_id]) > 100:
                self._history[task_id].pop(0)

            # Copy active callbacks under lock
            targets = list(self._subscribers.get(task_id, []))
            # Also notify wildcard/global subscribers (task_id="*")
            targets.extend(self._subscribers.get("*", []))

        # Notify callbacks
        for callback, subscribed_org in targets:
            # SEC-2 enforcement: Never dispatch message if org mismatch
            if subscribed_org and subscribed_org != org_id:
                logger.warning(
                    f"[LocalEventBus SEC-2] Prevented event dispatch: target org {subscribed_org} != event org {org_id}"
                )
                continue

            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                logger.error(f"[LocalEventBus] Callback error: {e}", exc_info=True)

    def subscribe(
        self,
        task_id: str,
        callback: Callable[[AgentMessage], Any],
        organization_id: Optional[str] = None
    ) -> None:
        """Subscribe a callback to a specific task_id (or '*' for global)."""
        with self._lock:
            self._subscribers[task_id].append((callback, organization_id))

    def unsubscribe(self, task_id: str, callback: Callable[[AgentMessage], Any]) -> None:
        """Remove a callback from subscriptions."""
        with self._lock:
            if task_id in self._subscribers:
                self._subscribers[task_id] = [
                    (cb, org) for (cb, org) in self._subscribers[task_id] if cb != callback
                ]

    def get_history(self, task_id: str, organization_id: str) -> List[AgentMessage]:
        """
        Get buffered event history for a task.
        SEC-2: Returns empty if organization_id does not match the stored events.
        """
        with self._lock:
            messages = self._history.get(task_id, [])
            if not messages:
                return []
            if messages[0].organization_id != organization_id:
                logger.warning(
                    f"[LocalEventBus SEC-2] Rejected history read for task {task_id}: "
                    f"requester org {organization_id} != task org {messages[0].organization_id}"
                )
                return []
            return list(messages)
