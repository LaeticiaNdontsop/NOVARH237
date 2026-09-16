from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = ("username", "get_full_name", "email", "role", "is_active", "date_creation")
    list_filter = ("role", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("Informations NOVA RH", {"fields": ("role", "telephone", "adresse", "photo", "doit_changer_mot_de_passe")}),
    )
