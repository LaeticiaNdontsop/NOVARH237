from django.urls import path
from . import views

app_name = "demandes_employe"

urlpatterns = [
    # Espace Employé - congés / permissions
    path(
        "mes-demandes/",
        views.MesDemandesCongeListView.as_view(),
        name="mes_demandes",
    ),
    path(
        "mes-demandes/historique/",
        views.HistoriqueCongesView.as_view(),
        name="historique_conges",
    ),
    path(
        "mes-demandes/nouvelle/",
        views.CreerDemandeCongeView.as_view(),
        name="creer_demande",
    ),
    path(
        "mes-demandes/<int:pk>/",
        views.DetailDemandeCongeView.as_view(),
        name="detail_demande",
    ),

    # Espace Employé - absences
    path(
        "mes-absences/",
        views.MesAbsencesListView.as_view(),
        name="mes_absences",
    ),
    path(
        "mes-absences/historique/",
        views.HistoriqueAbsencesView.as_view(),
        name="historique_absences",
    ),
    path(
        "mes-absences/nouvelle/",
        views.CreerAbsenceView.as_view(),
        name="creer_absence",
    ),

    # Espace Employé - démission
    path(
        "ma-demission/",
        views.MaDemissionView.as_view(),
        name="ma_demission",
    ),
    path(
        "ma-demission/historique/",
        views.HistoriqueDemissionsView.as_view(),
        name="historique_demissions",
    ),
]