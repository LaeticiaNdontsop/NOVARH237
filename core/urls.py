from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.AccueilView.as_view(), name="accueil"),
    path("media/<path:chemin>", views.MediaProtegeView.as_view(), name="media_protege"),
    path("recherche/", views.RechercheView.as_view(), name="recherche"),

    path("tableau-de-bord/", views.RedirectionDashboardView.as_view(), name="redirection_dashboard"),
]
