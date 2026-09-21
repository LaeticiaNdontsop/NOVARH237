import threading

from django.conf import settings
from django.db import models

_contexte = threading.local()


def definir_requete_courante(request):
    _contexte.request = request


def requete_courante():
    return getattr(_contexte, "request", None)


def _adresse_ip(request):
    if request is None:
        return None
    transmis = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = transmis.split(",")[0].strip() if transmis else request.META.get("REMOTE_ADDR")
    return ip or None


class TypeAction(models.TextChoices):
    CONNEXION = "CONNEXION", "Connexion"
    UTILISATEUR = "UTILISATEUR", "Utilisateurs & droits"
    EMPLOYE = "EMPLOYE", "Employés"
    DEMANDE = "DEMANDE", "Demandes"
    ABSENCE = "ABSENCE", "Absences"
    DEMISSION = "DEMISSION", "Démissions"
    RECRUTEMENT = "RECRUTEMENT", "Recrutement"
    FORMATION = "FORMATION", "Formations"
    NOTIFICATION = "NOTIFICATION", "Notifications"
    AUTRE = "AUTRE", "Autre"


_MOTS_CLES_TYPE = [
    (TypeAction.CONNEXION, ("connexion",)),
    (TypeAction.UTILISATEUR, ("compte", "utilisateur", "mot de passe", "profil", "droit")),
    (TypeAction.DEMISSION, ("demission", "preavis")),
    (TypeAction.ABSENCE, ("absence",)),
    (TypeAction.DEMANDE, ("demande",)),
    (TypeAction.RECRUTEMENT, ("offre", "candidat", "recrut")),
    (TypeAction.FORMATION, ("formation",)),
    (TypeAction.NOTIFICATION, ("notification",)),
    (TypeAction.EMPLOYE, ("employe", "contrat", "remuneration", "document")),
]


def deviner_type_action(action):
    texte = action.lower()
    for type_action, mots in _MOTS_CLES_TYPE:
        if any(mot in texte for mot in mots):
            return type_action
    return TypeAction.AUTRE


def log_activity(utilisateur, action, details="", resultat="SUCCES", request=None):
    """Journalise une action ; l'adresse IP et le navigateur viennent de la requete courante."""
    request = request or requete_courante()
    return ActivityLog.objects.create(
        utilisateur=utilisateur if getattr(utilisateur, "pk", None) else None,
        action=action,
        details=details,
        type_action=deviner_type_action(action),
        resultat=resultat,
        adresse_ip=_adresse_ip(request),
        navigateur=(request.META.get("HTTP_USER_AGENT", "")[:255] if request is not None else ""),
    )


class CategorieNotification(models.TextChoices):
    DEMANDE = "DEMANDE", "Demande"
    ABSENCE = "ABSENCE", "Absence"
    RECRUTEMENT = "RECRUTEMENT", "Recrutement"
    FORMATION = "FORMATION", "Formation"
    DOCUMENT = "DOCUMENT", "Document"
    COMMUNICATION = "COMMUNICATION", "Communication"
    SECURITE = "SECURITE", "Sécurité"
    SYSTEME = "SYSTEME", "Système"
    AUTRE = "AUTRE", "Autre"


def deviner_categorie(message):
    texte = message.lower()
    for categorie, mots in (
        (CategorieNotification.ABSENCE, ("absence",)),
        (CategorieNotification.DEMANDE, ("demande",)),
        (CategorieNotification.FORMATION, ("formation",)),
        (CategorieNotification.RECRUTEMENT, ("candidat", "recrut", "offre")),
        (CategorieNotification.DOCUMENT, ("document",)),
    ):
        if any(mot in texte for mot in mots):
            return categorie
    return CategorieNotification.AUTRE


def notifier(expediteur, destinataire, message, categorie=CategorieNotification.AUTRE, titre=""):
    """Notification interne personnelle (visible uniquement par `destinataire`)."""
    if categorie == CategorieNotification.AUTRE:
        categorie = deviner_categorie(message)
    return Notification.objects.create(
        expediteur=expediteur, destinataire=destinataire, role_cible="TOUS",
        message=message, categorie=categorie, titre=titre,
    )


class Notification(models.Model):
    """Notification interne : envoyee par l'Administrateur/RH ou generee par la plateforme."""
    expediteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications_envoyees",
    )
    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications_reçues",
        null=True,
        blank=True,
    )
    role_cible = models.CharField(
        max_length=10,
        choices=[
            ("TOUS", "Tous"),
            ("EMPLOYE", "Employes"),
            ("RH", "Responsables RH"),
            ("ADMIN", "Administrateurs"),
        ],
        default="TOUS",
    )
    titre = models.CharField(max_length=150, blank=True)
    categorie = models.CharField(
        max_length=15, choices=CategorieNotification.choices, default=CategorieNotification.AUTRE
    )
    message = models.TextField()
    lu = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return self.titre or self.message[:80]

    @property
    def titre_affiche(self):
        return self.titre or self.get_categorie_display()


class ActivityLog(models.Model):
    """Journal d'activite centralise pour l'admin."""
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=120)
    details = models.TextField(blank=True)
    type_action = models.CharField(max_length=15, choices=TypeAction.choices, default=TypeAction.AUTRE)
    resultat = models.CharField(
        max_length=10, choices=[("SUCCES", "Succès"), ("ALERTE", "Alerte")], default="SUCCES"
    )
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    navigateur = models.CharField(max_length=255, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]
        verbose_name = "Journal d'activite"
        verbose_name_plural = "Journaux d'activite"

    def __str__(self):
        return f"{self.action} - {self.utilisateur or 'Systeme'}"
