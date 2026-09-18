from django.conf import settings
from django.db import models

from employees.models import Employe


class Evaluation(models.Model):
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name="evaluations")
    titre = models.CharField(max_length=150)
    date_evaluation = models.DateField()
    note = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    commentaire = models.TextField(blank=True)
    creee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="evaluations_creees",
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_evaluation", "-date_creation"]

    def __str__(self):
        return f"{self.titre} - {self.employe.nom_complet}"


class Formation(models.Model):
    titre = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    date_formation = models.DateField()
    duree_heures = models.PositiveSmallIntegerField(default=1)
    participants = models.ManyToManyField(Employe, blank=True, related_name="formations")
    creee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="formations_creees",
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date_formation", "titre"]

    def __str__(self):
        return self.titre


class StatutOffre(models.TextChoices):
    BROUILLON = "BROUILLON", "Brouillon"
    PUBLIEE = "PUBLIEE", "Publiee"
    POURVUE = "POURVUE", "Pourvue"
    FERMEE = "FERMEE", "Fermee"


class Offre(models.Model):
    poste = models.CharField(max_length=150)
    type_contrat = models.CharField(max_length=30)
    lieu = models.CharField(max_length=100)
    description = models.TextField()
    statut = models.CharField(max_length=12, choices=StatutOffre.choices, default=StatutOffre.BROUILLON)
    date_publication = models.DateField(null=True, blank=True)
    date_limite = models.DateField(null=True, blank=True)
    creee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="offres_creees",
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.poste} - {self.lieu}"


class StatutCandidature(models.TextChoices):
    RECUE = "RECUE", "Recue"
    EN_REVUE = "EN_REVUE", "En revue"
    ENTRETIEN = "ENTRETIEN", "Entretien"
    RETENUE = "RETENUE", "Retenue"
    REJETEE = "REJETEE", "Rejetee"


class Candidature(models.Model):
    offre = models.ForeignKey(Offre, on_delete=models.CASCADE, related_name="candidatures")
    nom_candidat = models.CharField(max_length=150)
    email = models.EmailField()
    telephone = models.CharField(max_length=30, blank=True)
    cv = models.FileField(upload_to="candidatures/", blank=True)
    statut = models.CharField(max_length=12, choices=StatutCandidature.choices, default=StatutCandidature.RECUE)
    commentaire = models.TextField(blank=True)
    date_candidature = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_candidature"]

    @property
    def statut_choices(self):
        return StatutCandidature.choices

    def __str__(self):
        return f"{self.nom_candidat} - {self.offre.poste}"