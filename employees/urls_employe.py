from django.urls import path

from . import views

app_name = "employees_employe"

urlpatterns = [
    path("mes-documents/", views.MesDocumentsView.as_view(), name="mes_documents"),
    path("documents/<int:pk>/", views.DocumentDetailView.as_view(), name="document_detail"),
    path("mes-formations/", views.MesFormationsView.as_view(), name="mes_formations"),
]
