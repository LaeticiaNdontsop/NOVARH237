from django.urls import path

from . import views

app_name = "demandes_admin"

urlpatterns = [
    path("demandes/", views.DemandesAdminView.as_view(), name="admin_a_decider"),
    path("demandes/<int:pk>/", views.DetailDemandeCongeView.as_view(), name="detail_demande"),
    path("demandes/<int:pk>/approuver/", views.approuver_par_admin, name="approuver_par_admin"),
    path("demandes/<int:pk>/rejeter/", views.rejeter_par_admin, name="rejeter_par_admin"),
    path("demissions/", views.DemissionsAdminView.as_view(), name="admin_demissions"),
    path("demissions/<int:pk>/preavis/", views.definir_preavis, name="definir_preavis"),
    path("absences-rh/", views.AbsencesRHView.as_view(), name="rh_absences"),
]
