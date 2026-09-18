from django.contrib import admin
from .models import EchangeAssistant, PredictionAttrition


@admin.register(PredictionAttrition)
class PredictionAttritionAdmin(admin.ModelAdmin):
    list_display = ("employe", "demande_par", "prediction_depart", "probabilite_depart", "niveau_risque", "date_prediction")
    list_filter = ("prediction_depart", "niveau_risque")
    readonly_fields = ("donnees_utilisees",)


@admin.register(EchangeAssistant)
class EchangeAssistantAdmin(admin.ModelAdmin):
    """BF-ADM06 : consultation de la traçabilite des echanges avec l'assistant IA."""
    list_display = ("utilisateur", "question_courte", "en_erreur", "date_creation")
    list_filter = ("en_erreur",)
    search_fields = ("utilisateur__username", "question")
    readonly_fields = [f.name for f in EchangeAssistant._meta.fields]

    def has_add_permission(self, request):
        return False

    def question_courte(self, obj):
        return (obj.question[:60] + "…") if len(obj.question) > 60 else obj.question
    question_courte.short_description = "Question"
