import json
import logging
import os
from typing import Any, Callable, Optional

from app.services.event_bus.base import AgentMessage, EventBus

logger = logging.getLogger(__name__)


class GCPPubSubEventBus(EventBus):
    """
    GCP Cloud Pub/Sub implementation of EventBus.
    Publishes messages to topic with `task_id` and `organization_id` attributes (SEC-15).
    """

    def __init__(self):
        self.project_id = os.environ.get("GCP_PROJECT_ID", "klypup-pricing")
        self.topic_name = os.environ.get("GCP_PUBSUB_TOPIC", "pricing-agent-events")
        self._publisher = None
        self._topic_path = None

        try:
            from google.cloud import pubsub_v1
            self._publisher = pubsub_v1.PublisherClient()
            self._topic_path = self._publisher.topic_path(self.project_id, self.topic_name)
            logger.info(f"[GCPPubSubEventBus] Initialized for topic: {self._topic_path}")
        except Exception as e:
            logger.warning(f"[GCPPubSubEventBus] Failed to initialize Pub/Sub client ({e}). Running in fallback mode.")

    async def publish(self, message: AgentMessage) -> None:
        """Publish an AgentMessage to Cloud Pub/Sub with metadata attributes."""
        if not self._publisher or not self._topic_path:
            logger.warning(f"[GCPPubSubEventBus] Pub/Sub client uninitialized. Dropping message: {message.event_type}")
            return

        try:
            data = json.dumps(message.dict()).encode("utf-8")
            # Pub/Sub attributes for message filtering (Gap #3)
            attributes = {
                "agent": message.agent,
                "task_id": message.task_id,
                "organization_id": message.organization_id,
                "event_type": message.event_type,
                "product_id": message.product_id,
            }
            future = self._publisher.publish(self._topic_path, data, **attributes)
            message_id = future.result(timeout=5.0)
            logger.info(f"[GCPPubSubEventBus] Published message {message_id} for task {message.task_id}")
        except Exception as e:
            logger.error(f"[GCPPubSubEventBus] Failed to publish message: {e}", exc_info=True)

    def subscribe(
        self,
        task_id: str,
        callback: Callable[[AgentMessage], Any],
        organization_id: Optional[str] = None
    ) -> None:
        """
        For GCP, agent-to-agent subscription runs through subscriber workers or Cloud Run push endpoints.
        This hook logs configuration for serverless deployments.
        """
        logger.info(
            f"[GCPPubSubEventBus] Subscription requested for task_id={task_id}, org={organization_id}. "
            f"Handled via Cloud Run subscriber or Firestore relay."
        )

    def unsubscribe(self, task_id: str, callback: Callable[[AgentMessage], Any]) -> None:
        pass
