from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .models import log_activity


@receiver(user_logged_in)
def journaliser_connexion(sender, request, user, **kwargs):
    log_activity(user, "Connexion reussie", "Connexion a la plateforme.", request=request)


@receiver(user_login_failed)
def journaliser_echec_connexion(sender, credentials, request=None, **kwargs):
    identifiant = (credentials or {}).get("username", "")
    log_activity(
        None, "Tentative de connexion refusee",
        f"Echec de connexion (identifiant ou mot de passe invalide) pour « {identifiant[:60]} ».",
        resultat="ALERTE", request=request,
    )
