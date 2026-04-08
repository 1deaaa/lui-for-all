# Route Extraction Result: django_sample

- Adapter: django_urlconf
- Source Path: C:\Users\SERVER\Desktop\lui-for-all\backend_for_test\django_sample
- Route Count: 14

## Route List

1. GET:/api/items | GET /api/items | demo\views.py:43-44
2. POST:/api/items | POST /api/items | demo\views.py:43-44
3. PUT:/api/items | PUT /api/items | demo\views.py:43-44
4. PATCH:/api/items | PATCH /api/items | demo\views.py:43-44
5. DELETE:/api/items | DELETE /api/items | demo\views.py:43-44
6. GET:/api/status | GET /api/status | demo\views.py:48-56
7. HEAD:/api/status | HEAD /api/status | demo\views.py:48-56
8. GET:/api/health | GET /api/health | demo\views.py:68-88
9. POST:/api/health | POST /api/health | demo\views.py:68-88
10. PUT:/api/health | PUT /api/health | demo\views.py:68-88
11. PATCH:/api/health | PATCH /api/health | demo\views.py:68-88
12. DELETE:/api/health | DELETE /api/health | demo\views.py:68-88
13. HEAD:/api/health | HEAD /api/health | demo\views.py:68-88
14. OPTIONS:/api/health | OPTIONS /api/health | demo\views.py:68-88

## Function Implementation Blocks

### GET:/api/items

```text
def item_ops(request):
    return JsonResponse(_mutate_items(request.method))
```

### POST:/api/items

```text
def item_ops(request):
    return JsonResponse(_mutate_items(request.method))
```

### PUT:/api/items

```text
def item_ops(request):
    return JsonResponse(_mutate_items(request.method))
```

### PATCH:/api/items

```text
def item_ops(request):
    return JsonResponse(_mutate_items(request.method))
```

### DELETE:/api/items

```text
def item_ops(request):
    return JsonResponse(_mutate_items(request.method))
```

### GET:/api/status

```text
def status_view(request):
    return JsonResponse(
        {
            "route": "status_view",
            "method": request.method,
            "total": len(ITEMS),
            "has_items": bool(ITEMS),
        }
    )
```

### HEAD:/api/status

```text
def status_view(request):
    return JsonResponse(
        {
            "route": "status_view",
            "method": request.method,
            "total": len(ITEMS),
            "has_items": bool(ITEMS),
        }
    )
```

### GET:/api/health

```text
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
```

### POST:/api/health

```text
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
```

### PUT:/api/health

```text
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
```

### PATCH:/api/health

```text
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
```

### DELETE:/api/health

```text
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
```

### HEAD:/api/health

```text
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
```

### OPTIONS:/api/health

```text
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
```
