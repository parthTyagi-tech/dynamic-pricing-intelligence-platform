import os
from app.services.event_bus.base import AgentMessage, EventBus
from app.services.event_bus.local_bus import LocalEventBus

_global_bus: EventBus = None


def get_event_bus() -> EventBus:
    """
    Returns the configured EventBus singleton.
    Defaults to LocalEventBus for immediate zero-config testing.
    """
    global _global_bus
    if _global_bus is not None:
        return _global_bus

    provider = os.environ.get("EVENT_BUS_PROVIDER", "local").strip().lower()
    if provider == "gcp":
        try:
            from app.services.event_bus.gcp_pubsub_bus import GCPPubSubEventBus
            _global_bus = GCPPubSubEventBus()
        except Exception as e:
            print(f"[EventBus] Error initializing GCP Pub/Sub: {e}. Falling back to LocalEventBus.")
            _global_bus = LocalEventBus()
    else:
        _global_bus = LocalEventBus()

    return _global_bus
