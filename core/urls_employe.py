from django.urls import path

from .views import DashboardEmployeView

app_name = "core_employe"

urlpatterns = [
    path("", DashboardEmployeView.as_view(), name="dashboard_employe"),
]
