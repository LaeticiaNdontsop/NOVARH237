from django.contrib import admin
from .models import Employe, Contrat, Remuneration, Document


@admin.register(Employe)
class EmployeAdmin(admin.ModelAdmin):
    list_display = ("matricule", "nom_complet", "poste", "service", "statut", "date_embauche")
    list_filter = ("statut", "service")
    search_fields = ("matricule", "utilisateur__first_name", "utilisateur__last_name")


@admin.register(Contrat)
class ContratAdmin(admin.ModelAdmin):
    list_display = ("employe", "type_contrat", "date_debut", "date_fin", "signe")
    list_filter = ("type_contrat", "signe")


@admin.register(Remuneration)
class RemunerationAdmin(admin.ModelAdmin):
    list_display = ("employe", "salaire_base", "primes", "date_effective")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("employe", "type_document", "date_ajout", "ajoute_par")
    list_filter = ("type_document",)
