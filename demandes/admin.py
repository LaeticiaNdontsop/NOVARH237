from django.contrib import admin
from .models import DemandeConge, Absence, Demission, AlerteSysteme


@admin.register(DemandeConge)
class DemandeCongeAdmin(admin.ModelAdmin):
    list_display = ("employe", "type_demande", "statut", "date_debut", "date_fin", "rh_assigne", "admin_assigne")
    list_filter = ("type_demande", "statut")


@admin.register(Absence)
class AbsenceAdmin(admin.ModelAdmin):
    list_display = ("employe", "date_debut", "date_fin", "statut")
    list_filter = ("statut",)


@admin.register(Demission)
class DemissionAdmin(admin.ModelAdmin):
    list_display = ("employe", "date_declaration", "date_effective_souhaitee", "statut", "preavis_jours")
    list_filter = ("statut",)


@admin.register(AlerteSysteme)
class AlerteSystemeAdmin(admin.ModelAdmin):
    list_display = ("message", "date_creation", "resolue")
    list_filter = ("resolue",)
