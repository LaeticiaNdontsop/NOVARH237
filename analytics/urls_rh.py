from django.urls import path

from . import views

app_name = "analytics_rh"

urlpatterns = [
    path("analyse/", views.AnalyseIntelligenteView.as_view(), name="analyse"),
    path("tableaux-de-bord/", views.TableauxBordView.as_view(), name="tableaux_bord"),
    path("prediction/", views.PredictionAttritionView.as_view(), name="prediction_libre"),
    path("prediction/<int:employe_pk>/", views.PredictionAttritionView.as_view(), name="prediction_employe"),
    path("prediction/historique/", views.HistoriquePredictionsView.as_view(), name="historique"),
    path("prediction/historique/<int:employe_pk>/", views.HistoriquePredictionsView.as_view(), name="historique_employe"),
    path("assistant/", views.AssistantView.as_view(), name="assistant"),
]
