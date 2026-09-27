from django.urls import path

from . import views

app_name = "employees_rh"

urlpatterns = [
    path("employes/", views.ListeEmployesView.as_view(), name="liste_employes"),
    path("employes/nouveau/", views.CreerEmployeView.as_view(), name="creer_employe"),
    path("employes/<int:pk>/", views.DetailEmployeView.as_view(), name="detail_employe"),
    path("employes/<int:pk>/modifier/", views.ModifierEmployeView.as_view(), name="modifier_employe"),
    path("employes/<int:pk>/desactiver/", views.DesactiverEmployeView.as_view(), name="desactiver_employe"),
    path("employes/<int:employe_pk>/contrats/nouveau/", views.AjouterContratView.as_view(), name="ajouter_contrat"),
    path("employes/<int:employe_pk>/remunerations/nouvelle/", views.AjouterRemunerationView.as_view(), name="ajouter_remuneration"),
    path("employes/<int:employe_pk>/documents/nouveau/", views.AjouterDocumentView.as_view(), name="ajouter_document"),
    path("remunerations/", views.ListeRemunerationsView.as_view(), name="liste_remunerations"),
]
