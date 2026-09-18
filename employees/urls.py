from django.urls import path
from . import views

app_name = "employees"

urlpatterns = [
    path("", views.ListeEmployesView.as_view(), name="liste_employes"),
    path("mes-documents/", views.MesDocumentsView.as_view(), name="mes_documents"),
    path("mes-remunerations/", views.MesRemunerationsView.as_view(), name="mes_remunerations"),
    path("mon-contrat/", views.MonContratView.as_view(), name="mon_contrat"),
    path("mes-evaluations-formations/", views.MesEvaluationsFormationsView.as_view(), name="mes_evaluations_formations"),
    path("nouveau/", views.CreerEmployeView.as_view(), name="creer_employe"),
    path("<int:pk>/", views.DetailEmployeView.as_view(), name="detail_employe"),
    path("<int:pk>/modifier/", views.ModifierEmployeView.as_view(), name="modifier_employe"),
    path("<int:pk>/desactiver/", views.DesactiverEmployeView.as_view(), name="desactiver_employe"),

    path("<int:employe_pk>/contrats/nouveau/", views.AjouterContratView.as_view(), name="ajouter_contrat"),
    path("<int:employe_pk>/remunerations/nouvelle/", views.AjouterRemunerationView.as_view(), name="ajouter_remuneration"),
    path("<int:employe_pk>/documents/nouveau/", views.AjouterDocumentView.as_view(), name="ajouter_document"),
]
