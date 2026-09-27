from django.urls import path

from .views import JournalActiviteView

app_name = "notifications_admin"

urlpatterns = [
    path("journal/", JournalActiviteView.as_view(), name="journal_activite"),
]
