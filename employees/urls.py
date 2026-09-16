from django.urls import path
from . import views

app_name = "employees"

urlpatterns = [
    path("", views.ListeEmployesView.as_view(), name="liste_employes"),
    path("nouveau/", views.CreerEmployeView.as_view(), name="creer_employe"),
    path("<int:pk>/", views.DetailEmployeView.as_view(), name="detail_employe"),
    path("<int:pk>/modifier/", views.ModifierEmployeView.as_view(), name="modifier_employe"),
    path("<int:pk>/desactiver/", views.DesactiverEmployeView.as_view(), name="desactiver_employe"),

    path("<int:employe_pk>/contrats/nouveau/", views.AjouterContratView.as_view(), name="ajouter_contrat"),
    path("<int:employe_pk>/remunerations/nouvelle/", views.AjouterRemunerationView.as_view(), name="ajouter_remuneration"),
    path("<int:employe_pk>/documents/nouveau/", views.AjouterDocumentView.as_view(), name="ajouter_document"),
]
