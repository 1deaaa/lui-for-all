from django.http import JsonResponse
from django.views import View
from django.views.decorators.http import require_http_methods, require_safe


ITEMS = [
    {"id": 1, "name": "paper", "status": "draft"},
    {"id": 2, "name": "pen", "status": "ready"},
]


def _snapshot_items() -> list[dict]:
    return [item.copy() for item in ITEMS]


def _next_item_id() -> int:
    return max((item["id"] for item in ITEMS), default=0) + 1


def _mutate_items(method: str) -> dict:
    if method == "GET":
        return {"route": "item_ops", "items": _snapshot_items(), "total": len(ITEMS)}
    if method == "POST":
        new_id = _next_item_id()
        new_item = {"id": new_id, "name": f"item-{new_id}", "status": "created"}
        ITEMS.append(new_item)
        return {"route": "item_ops", "created": new_item, "total": len(ITEMS)}
    if method == "PUT":
        if ITEMS:
            ITEMS[0].update({"status": "replaced", "name": f"{ITEMS[0]['name']}-v2"})
        return {"route": "item_ops", "updated": ITEMS[:1], "total": len(ITEMS)}
    if method == "PATCH":
        if ITEMS:
            ITEMS[-1]["status"] = "patched"
        return {"route": "item_ops", "patched": ITEMS[-1:]}
    if method == "DELETE":
        removed = ITEMS.pop() if ITEMS else None
        return {"route": "item_ops", "removed": removed, "total": len(ITEMS)}
    return {"route": "item_ops", "method": method}


@require_http_methods(["GET", "POST", "PUT", "PATCH", "DELETE"])
def item_ops(request):
    return JsonResponse(_mutate_items(request.method))


@require_safe
def status_view(request):
    return JsonResponse(
        {
            "route": "status_view",
            "method": request.method,
            "total": len(ITEMS),
            "has_items": bool(ITEMS),
        }
    )


def _health_payload(method: str) -> dict:
    return {
        "route": "health",
        "method": method,
        "total": len(ITEMS),
        "latest": ITEMS[-1] if ITEMS else None,
    }


class HealthView(View):
    def get(self, request):
        return JsonResponse(_health_payload("GET"))

    def post(self, request):
        return JsonResponse(_health_payload("POST"))

    def put(self, request):
        return JsonResponse(_health_payload("PUT"))

    def patch(self, request):
        return JsonResponse(_health_payload("PATCH"))

    def delete(self, request):
        return JsonResponse(_health_payload("DELETE"))

    def head(self, request):
        return JsonResponse(_health_payload("HEAD"))

    def options(self, request):
        return JsonResponse(_health_payload("OPTIONS"))
