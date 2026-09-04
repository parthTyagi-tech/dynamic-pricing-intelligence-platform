from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AgentMessage(BaseModel):
    """
    Standardized agent message schema for the event bus.
    Mandatory task_id and organization_id guarantee SEC-1 and SEC-2 isolation.
    """
    model_config = ConfigDict(frozen=True)

    agent: str
    product_id: str
    task_id: str
    organization_id: str
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EventBus(ABC):
    """
    Abstract Event Bus interface.
    Enables pluggable implementations (Local In-Memory vs. GCP Cloud Pub/Sub).
    """

    @abstractmethod
    async def publish(self, message: AgentMessage) -> None:
        """Publish an agent message to the bus."""
        pass

    @abstractmethod
    def subscribe(self, task_id: str, callback: Callable[[AgentMessage], Any], organization_id: Optional[str] = None) -> None:
        """Subscribe a handler callback to messages matching task_id (and optional organization_id)."""
        pass

    @abstractmethod
    def unsubscribe(self, task_id: str, callback: Callable[[AgentMessage], Any]) -> None:
        """Unsubscribe a previously registered callback."""
        pass
