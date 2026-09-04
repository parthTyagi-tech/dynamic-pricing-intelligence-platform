import abc
import html
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.event_bus import get_event_bus
from app.services.event_bus.base import AgentMessage
from app.services.task_state.task_manager import get_task_manager

logger = logging.getLogger(__name__)


class BaseAgent(abc.ABC):
    """
    Abstract Base Class for Autonomous Agents.
    Encapsulates:
    - Role & Goal
    - Autonomous Reasoning Loop: plan -> act -> observe -> evaluate -> adapt
    - Memory of past actions
    - Sanitization hooks (SEC-5, SEC-9)
    - Event publishing to the event bus
    """

    def __init__(self, role: str, goal: str, available_tools: Optional[List[str]] = None):
        self.role = role
        self.goal = goal
        self.available_tools = available_tools or []
        self.memory: List[Dict[str, Any]] = []

    def log_memory(self, action: str, observation: Any, details: Optional[Dict[str, Any]] = None) -> None:
        """Stores internal task memory of actions and observations."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "observation": observation,
            "details": details or {},
        }
        self.memory.append(record)
        logger.debug(f"[{self.role} Memory] Action: {action} | Observation: {observation}")

    def sanitize_output(self, text: str) -> str:
        """
        SEC-5 & SEC-9 Sanitization Hook.
        Strips dangerous script tags, HTML entities, and neutralizes prompt-injection triggers.
        """
        if not text or not isinstance(text, str):
            return ""

        # Remove script and style tags
        cleaned = re.sub(r"<(script|style).*?>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
        # Escape HTML entities to prevent XSS
        escaped = html.escape(cleaned)
        # Neutralize common prompt injection prefixes
        for pattern in [
            r"(?i)ignore\s+previous\s+instructions",
            r"(?i)system\s*:",
            r"(?i)developer\s*mode",
            r"(?i)override\s+guardrails",
        ]:
            escaped = re.sub(pattern, "[FILTERED]", escaped)

        return escaped.strip()

    async def emit_event(
        self,
        task_id: str,
        product_id: str,
        organization_id: str,
        event_type: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> None:
        """Publishes an event to the EventBus and appends to the TaskManager."""
        bus = get_event_bus()
        task_mgr = get_task_manager()

        safe_payload = payload or {}
        agent_msg = AgentMessage(
            agent=self.role,
            product_id=product_id,
            task_id=task_id,
            organization_id=organization_id,
            event_type=event_type,
            payload={"message": message, **safe_payload},
        )

        # Record in central task manager state
        task_mgr.append_event(
            task_id=task_id,
            agent=self.role,
            event_type=event_type,
            message=message,
            payload=safe_payload
        )

        # Publish to the global message bus
        await bus.publish(agent_msg)

    def record_decision(
        self,
        task_id: str,
        decision_point: str,
        rationale: str,
        action_taken: str
    ) -> None:
        """Logs an explainable reasoning trace."""
        task_mgr = get_task_manager()
        task_mgr.add_decision_trace(
            task_id=task_id,
            agent=self.role,
            decision_point=decision_point,
            rationale=rationale,
            action_taken=action_taken
        )
