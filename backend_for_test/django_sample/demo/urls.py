from django.urls import include, path

urlpatterns = [
    path("api/", include("demo.api_urls")),
]
