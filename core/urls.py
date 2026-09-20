from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.AccueilView.as_view(), name="accueil"),
    path("tableau-de-bord/", views.RedirectionDashboardView.as_view(), name="redirection_dashboard"),
    path("tableau-de-bord/admin/", views.DashboardAdminView.as_view(), name="dashboard_admin"),
    path("tableau-de-bord/rh/", views.DashboardRHView.as_view(), name="dashboard_rh"),
    path("tableau-de-bord/employe/", views.DashboardEmployeView.as_view(), name="dashboard_employe"),
    path("recrutements/", views.RecrutementsView.as_view(), name="recrutements"),
    path("offres/", views.OffresView.as_view(), name="offres"),
    path("evaluations-formations/", views.EvaluationsFormationsView.as_view(), name="evaluations_formations"),
    path("evaluations-formations/evaluation/nouvelle/", views.CreerEvaluationView.as_view(), name="creer_evaluation"),
    path("evaluations-formations/formation/nouvelle/", views.CreerFormationView.as_view(), name="creer_formation"),
    path("offres/nouvelle/", views.CreerOffreView.as_view(), name="creer_offre"),
    path("offres/<int:pk>/postuler/", views.PostulerOffreView.as_view(), name="postuler_offre"),
    path("candidatures/<int:pk>/statut/", views.modifier_statut_candidature, name="modifier_statut_candidature"),
    path("roles-et-droits/", views.RolesDroitsView.as_view(), name="roles_droits"),
    path("journal-activite/", views.JournalActiviteView.as_view(), name="journal_activite"),
]
