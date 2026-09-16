from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.RedirectionDashboardView.as_view(), name="redirection_dashboard"),
    path("tableau-de-bord/admin/", views.DashboardAdminView.as_view(), name="dashboard_admin"),
    path("tableau-de-bord/rh/", views.DashboardRHView.as_view(), name="dashboard_rh"),
    path("tableau-de-bord/employe/", views.DashboardEmployeView.as_view(), name="dashboard_employe"),
]
