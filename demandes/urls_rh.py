from django.urls import path

from . import views

app_name = "demandes_rh"

urlpatterns = [
    path("demandes/", views.DemandesRHView.as_view(), name="rh_demandes"),
    path("demandes/historique/", views.HistoriqueCongesView.as_view(), name="historique_conges"),
    path("demandes/a-traiter/", views.DemandesATraiterRHView.as_view(), name="rh_a_traiter"),
    path("demandes/a-communiquer/", views.DemandesANotifierRHView.as_view(), name="rh_a_notifier"),
    path("demandes/<int:pk>/", views.DetailDemandeCongeView.as_view(), name="detail_demande"),
    path("demandes/<int:pk>/transmettre/", views.transmettre_a_admin, name="transmettre_a_admin"),
    path("demandes/<int:pk>/rejeter/", views.rejeter_par_rh, name="rejeter_par_rh"),
    path("demandes/<int:pk>/cloturer/", views.cloturer_demande, name="cloturer_demande"),
    path("absences/", views.AbsencesRHView.as_view(), name="rh_absences"),
    path("absences/historique/", views.HistoriqueAbsencesView.as_view(), name="historique_absences"),
    path("demissions/", views.DemissionsATransmettreRHView.as_view(), name="rh_demissions_a_transmettre"),
    path("demissions/a-communiquer/", views.DemissionsACommuniquerRHView.as_view(), name="rh_demissions_a_communiquer"),
    path("demissions/historique/", views.HistoriqueDemissionsView.as_view(), name="historique_demissions"),
    path("demissions/<int:pk>/transmettre/", views.transmettre_demission, name="transmettre_demission"),
    path("demissions/<int:pk>/communiquer/", views.communiquer_demission, name="communiquer_demission"),
]
