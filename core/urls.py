from django.urls import path

from . import views, views_formations, views_recrutement

app_name = "core"

urlpatterns = [
    path("", views.AccueilView.as_view(), name="accueil"),
    path("media/<path:chemin>", views.MediaProtegeView.as_view(), name="media_protege"),
    path("recherche/", views.RechercheView.as_view(), name="recherche"),

    # Tableaux de bord
    path("tableau-de-bord/", views.RedirectionDashboardView.as_view(), name="redirection_dashboard"),
    path("tableau-de-bord/admin/", views.DashboardAdminView.as_view(), name="dashboard_admin"),
    path("tableau-de-bord/rh/", views.DashboardRHView.as_view(), name="dashboard_rh"),
    path("tableau-de-bord/employe/", views.DashboardEmployeView.as_view(), name="dashboard_employe"),

    # Recrutement et offres
    path("recrutements/", views_recrutement.RecrutementsView.as_view(), name="recrutements"),
    path("recrutements/historique/", views_recrutement.HistoriqueRecrutementsView.as_view(), name="historique_recrutements"),
    path("offres/", views_recrutement.OffresView.as_view(), name="offres"),
    path("offres/nouvelle/", views_recrutement.CreerOffreView.as_view(), name="creer_offre"),
    path("offres/<int:pk>/modifier/", views_recrutement.ModifierOffreView.as_view(), name="modifier_offre"),
    path("offres/<int:pk>/supprimer/", views_recrutement.SupprimerOffreView.as_view(), name="supprimer_offre"),
    path("offres/<int:pk>/candidatures/", views_recrutement.CandidaturesOffreView.as_view(), name="candidatures_offre"),
    path("offres/<int:pk>/candidatures/nouvelle/", views_recrutement.AjouterCandidatureView.as_view(), name="ajouter_candidature"),
    path("candidatures/<int:pk>/", views_recrutement.DetailCandidatureView.as_view(), name="detail_candidature"),
    path("candidatures/<int:pk>/statut/", views_recrutement.modifier_statut_candidature, name="modifier_statut_candidature"),
    path("candidatures/<int:pk>/recruter/", views_recrutement.recruter_candidat, name="recruter_candidat"),

    # Formations
    path("formations/", views_formations.FormationsView.as_view(), name="formations"),
    path("formations/historique/", views_formations.HistoriqueFormationsView.as_view(), name="historique_formations"),
    path("formations/nouvelle/", views_formations.CreerFormationView.as_view(), name="creer_formation"),
    path("formations/<int:pk>/modifier/", views_formations.ModifierFormationView.as_view(), name="modifier_formation"),
    path("formations/<int:pk>/suivi/", views_formations.SuiviFormationView.as_view(), name="suivi_formation"),
]
