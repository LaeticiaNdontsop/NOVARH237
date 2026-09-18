from django.urls import path
from . import views

app_name = "demandes"

urlpatterns = [
    # Espace employe - conges/permissions
    path("mes-demandes/", views.MesDemandesCongeListView.as_view(), name="mes_demandes"),
    path("mes-demandes/nouvelle/", views.CreerDemandeCongeView.as_view(), name="creer_demande"),
    path("mes-demandes/<int:pk>/", views.DetailDemandeCongeView.as_view(), name="detail_demande"),

    # Espace RH - conges/permissions
    path("rh/a-traiter/", views.DemandesATraiterRHView.as_view(), name="rh_a_traiter"),
    path("rh/a-notifier/", views.DemandesANotifierRHView.as_view(), name="rh_a_notifier"),
    path("rh/<int:pk>/transmettre/", views.transmettre_a_admin, name="transmettre_a_admin"),
    path("rh/<int:pk>/rejeter/", views.rejeter_par_rh, name="rejeter_par_rh"),
    path("rh/<int:pk>/cloturer/", views.cloturer_demande, name="cloturer_demande"),

    # Espace Admin - conges/permissions
    path("admin/a-decider/", views.DemandesAdminView.as_view(), name="admin_a_decider"),
    path("admin/<int:pk>/approuver/", views.approuver_par_admin, name="approuver_par_admin"),
    path("admin/<int:pk>/rejeter/", views.rejeter_par_admin, name="rejeter_par_admin"),

    # Absences
    path("mes-absences/", views.MesAbsencesListView.as_view(), name="mes_absences"),
    path("mes-absences/nouvelle/", views.CreerAbsenceView.as_view(), name="creer_absence"),
    path("rh/absences/", views.AbsencesRHView.as_view(), name="rh_absences"),
    path("rh/absences/<int:pk>/valider/", views.valider_absence, name="valider_absence"),
    path("rh/absences/<int:pk>/rejeter/", views.rejeter_absence, name="rejeter_absence"),

    # Demission (RG-22 : Employe -> RH -> Admin -> RH -> Employe)
    path("ma-demission/", views.MaDemissionView.as_view(), name="ma_demission"),
    path("rh/demissions/a-transmettre/", views.DemissionsATransmettreRHView.as_view(), name="rh_demissions_a_transmettre"),
    path("rh/demissions/<int:pk>/transmettre/", views.transmettre_demission, name="transmettre_demission"),
    path("admin/demissions/", views.DemissionsAdminView.as_view(), name="admin_demissions"),
    path("admin/demissions/<int:pk>/preavis/", views.definir_preavis, name="definir_preavis"),
    path("rh/demissions/a-communiquer/", views.DemissionsACommuniquerRHView.as_view(), name="rh_demissions_a_communiquer"),
    path("rh/demissions/<int:pk>/communiquer/", views.communiquer_demission, name="communiquer_demission"),
]
