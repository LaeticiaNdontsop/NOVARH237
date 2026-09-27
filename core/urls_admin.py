from django.urls import path

from .views import DashboardAdminView

app_name = "core_admin"

urlpatterns = [
    path("", DashboardAdminView.as_view(), name="dashboard_admin"),
]
