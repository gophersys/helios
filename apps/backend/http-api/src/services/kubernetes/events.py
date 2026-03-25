from .client import get_core_v1_api
from .serializers import serialize_event


def list_events(
    namespace: str | None = None,
    limit: int = 100,
    field_selector: str | None = None,
) -> list[dict]:
    core = get_core_v1_api()
    kwargs = {"limit": limit}
    if field_selector:
        kwargs["field_selector"] = field_selector

    if namespace:
        event_list = core.list_namespaced_event(namespace, **kwargs)
    else:
        event_list = core.list_event_for_all_namespaces(**kwargs)

    events = [serialize_event(e) for e in event_list.items]

    # Sort by lastSeen descending (most recent first)
    events.sort(key=lambda e: e.get("lastSeen") or "", reverse=True)

    return events
