from django.conf import settings
from django.db import models

from employees.models import Employe


class PredictionAttrition(models.Model):
    """
    RG-13 : tracabilite des actions importantes. Chaque simulation de prediction
    est enregistree (qui, quand, pour quel employe, avec quel resultat) sans
    jamais etre presentee comme une decision automatique (cf. CDC §6.5.7 et
    message d'avertissement systematique retourne par predire_attrition()).
    """
    employe = models.ForeignKey(
        Employe, on_delete=models.CASCADE, null=True, blank=True, related_name="predictions_attrition",
        help_text="Vide si la simulation a ete faite sur un profil libre (non lie a une fiche employe).",
    )
    demande_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="predictions_demandees",
    )
    date_prediction = models.DateTimeField(auto_now_add=True)

    prediction_depart = models.BooleanField()
    probabilite_depart = models.FloatField()
    niveau_risque = models.CharField(max_length=10)
    donnees_utilisees = models.JSONField(
        help_text="Copie des 29 variables soumises au modele, pour tracabilite/audit.",
    )

    class Meta:
        verbose_name = "Prediction d'attrition"
        verbose_name_plural = "Predictions d'attrition"
        ordering = ["-date_prediction"]

    def __str__(self):
        cible = self.employe.nom_complet if self.employe else "profil libre"
        return f"Prediction {cible} - {self.probabilite_depart:.0%} ({self.date_prediction:%d/%m/%Y})"


class EchangeAssistant(models.Model):
    """
    RG-13 : traçabilite des echanges avec l'assistant IA (qui a demande quoi et
    quand). La reponse est conservee elle aussi : comme elle est deja construite
    a partir d'un contexte scope au role de l'utilisateur (RG-15), la stocker ne
    cree pas de fuite supplementaire et permet un controle a posteriori par
    l'Administrateur (BF-ADM06).
    """
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="echanges_assistant",
    )
    question = models.TextField()
    reponse = models.TextField(blank=True)
    en_erreur = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Echange avec l'assistant"
        verbose_name_plural = "Echanges avec l'assistant"
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.utilisateur} - {self.date_creation:%d/%m/%Y %H:%M}"
