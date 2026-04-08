from django.http import JsonResponse
from django.views import View
from django.views.decorators.http import require_http_methods, require_safe


@require_http_methods(["GET", "POST", "PUT", "PATCH", "DELETE"])
def item_ops(request):
    return JsonResponse({"route": "item_ops", "method": request.method})


@require_safe
def status_view(request):
    return JsonResponse({"route": "status_view", "method": request.method})


class HealthView(View):
    def get(self, request):
        return JsonResponse({"route": "health", "method": "GET"})

    def post(self, request):
        return JsonResponse({"route": "health", "method": "POST"})

    def put(self, request):
        return JsonResponse({"route": "health", "method": "PUT"})

    def patch(self, request):
        return JsonResponse({"route": "health", "method": "PATCH"})

    def delete(self, request):
        return JsonResponse({"route": "health", "method": "DELETE"})

    def head(self, request):
        return JsonResponse({"route": "health", "method": "HEAD"})

    def options(self, request):
        return JsonResponse({"route": "health", "method": "OPTIONS"})
