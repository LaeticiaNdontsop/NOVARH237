from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.MesNotificationsView.as_view(), name="mes_notifications"),
    path("historique/", views.HistoriqueNotificationsView.as_view(), name="historique_notifications"),
    path("envoyer/", views.EnvoyerNotificationView.as_view(), name="envoyer"),
    path("marquer-lue/<int:pk>/", views.MarquerNotificationLueView.as_view(), name="marquer_lue"),
    path("tout-marquer-lu/", views.ToutMarquerLuView.as_view(), name="tout_marquer_lu"),
    path("<int:pk>/supprimer/", views.SupprimerNotificationView.as_view(), name="supprimer"),
    path("journal/", views.JournalActiviteView.as_view(), name="journal_activite"),
]
