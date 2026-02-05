from .client import get_core_v1_api
from .serializers import serialize_event


def list_events(namespace: str | None = None, limit: int = 100) -> list[dict]:
    core = get_core_v1_api()

    if namespace:
        event_list = core.list_namespaced_event(namespace, limit=limit)
    else:
        event_list = core.list_event_for_all_namespaces(limit=limit)

    events = [serialize_event(e) for e in event_list.items]

    # Sort by lastSeen descending (most recent first)
    events.sort(key=lambda e: e.get("lastSeen") or "", reverse=True)

    return events[:limit]
