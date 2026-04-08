from django.urls import path
from . import views

urlpatterns = [
    path("items", views.item_ops, name="items"),
    path("status", views.status_view, name="status"),
    path("health", views.HealthView.as_view(), name="health"),
]
