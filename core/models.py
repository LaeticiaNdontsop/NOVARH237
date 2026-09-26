from django.conf import settings
from django.db import models
from django.utils import timezone

from employees.models import Employe


# ---------------------------------------------------------------------------
# Formations (BF-RH-11, BF-EMP10, RG-23) : ciblage par le RH, pas d'inscription libre
# ---------------------------------------------------------------------------
class Formation(models.Model):
    titre = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    date_formation = models.DateField("Date de début")
    date_fin = models.DateField("Date de fin", null=True, blank=True)
    heure_debut = models.TimeField("Heure de début", null=True, blank=True)
    heure_fin = models.TimeField("Heure de fin", null=True, blank=True)
    duree_heures = models.PositiveSmallIntegerField("Durée (heures)", default=1)
    lieu = models.CharField("Lieu / salle", max_length=150, blank=True)
    formateur = models.CharField(max_length=150, blank=True)
    annulee = models.BooleanField("Formation annulée", default=False)
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

    @property
    def date_fin_effective(self):
        return self.date_fin or self.date_formation

    @property
    def etat(self):
        """Annulée / Terminée / En cours / Planifiée (calculé à partir des dates)."""
        if self.annulee:
            return "Annulée"
        aujourdhui = timezone.localdate()
        if self.date_fin_effective < aujourdhui:
            return "Terminée"
        if self.date_formation <= aujourdhui:
            return "En cours"
        return "Planifiée"

    @property
    def nombre_cibles(self):
        return len(self.participations.all())


class StatutParticipation(models.TextChoices):
    CIBLE = "CIBLE", "Ciblé - à venir"
    PARTICIPE = "PARTICIPE", "A participé"
    ABSENT = "ABSENT", "Absent"


class ParticipationFormation(models.Model):
    """Un employé ciblé par une formation, et le suivi de sa participation effective."""
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="participations")
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name="participations_formations")
    statut = models.CharField(max_length=10, choices=StatutParticipation.choices, default=StatutParticipation.CIBLE)
    date_maj = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("formation", "employe")]
        ordering = ["employe__utilisateur__last_name", "employe__utilisateur__first_name"]

    def __str__(self):
        return f"{self.employe.nom_complet} - {self.formation.titre} ({self.get_statut_display()})"


# ---------------------------------------------------------------------------
# Offres (BF-RH-15) et Recrutement (BF-RH-16, RG-10, RG-11)
# ---------------------------------------------------------------------------
class StatutOffre(models.TextChoices):
    BROUILLON = "BROUILLON", "Brouillon"
    PUBLIEE = "PUBLIEE", "Publiée"
    POURVUE = "POURVUE", "Pourvue"
    FERMEE = "FERMEE", "Fermée"


class ModeTravail(models.TextChoices):
    SUR_SITE = "SUR_SITE", "Sur site"
    HYBRIDE = "HYBRIDE", "Hybride"
    TELETRAVAIL = "TELETRAVAIL", "Télétravail"


class StatutCandidature(models.TextChoices):
    RECUE = "RECUE", "À analyser"
    ENTRETIEN = "ENTRETIEN", "Entretien"
    RETENUE = "RETENUE", "Retenue"
    REJETEE = "REJETEE", "Refusée"


# Etapes de recrutement d'une offre (calculees a partir de ses candidatures).
ETAPE_AUCUNE = "Aucune candidature"
ETAPE_A_ANALYSER = "À analyser"
ETAPE_ENTRETIEN = "Entretien"
ETAPE_RETENUE = "Retenue"
ETAPE_RECRUTE = "Recrutement finalisé"
ETAPE_REFUSEES = "Toutes refusées"
ETAPE_CLOTUREE = "Clôturée"
ETAPES_RECRUTEMENT = [
    ETAPE_AUCUNE, ETAPE_A_ANALYSER, ETAPE_ENTRETIEN, ETAPE_RETENUE,
    ETAPE_RECRUTE, ETAPE_REFUSEES, ETAPE_CLOTUREE,
]


class Offre(models.Model):
    poste = models.CharField("Titre du poste", max_length=150)
    departement = models.CharField("Département / service", max_length=100, blank=True)
    type_contrat = models.CharField(max_length=30)
    lieu = models.CharField("Localisation", max_length=100)
    mode_travail = models.CharField("Lieu de travail", max_length=12, choices=ModeTravail.choices, blank=True)
    description = models.TextField("Description du poste")
    missions = models.TextField("Missions principales", blank=True, help_text="Une mission par ligne.")
    competences = models.TextField(
        "Compétences recherchées", blank=True, help_text="Séparées par des virgules."
    )
    statut = models.CharField(max_length=12, choices=StatutOffre.choices, default=StatutOffre.BROUILLON)
    date_publication = models.DateField(null=True, blank=True)
    date_limite = models.DateField("Date d'expiration", null=True, blank=True)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="offres_suivies",
        verbose_name="Responsable du recrutement",
    )
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

    @property
    def reference(self):
        return f"OFF-{self.date_creation.year}-{self.pk:03d}"

    @property
    def est_expiree(self):
        return (
            self.statut == StatutOffre.PUBLIEE
            and self.date_limite is not None
            and self.date_limite < timezone.localdate()
        )

    @property
    def statut_affiche(self):
        return "Expirée" if self.est_expiree else self.get_statut_display()

    @property
    def est_active(self):
        return self.statut == StatutOffre.PUBLIEE and not self.est_expiree

    @property
    def liste_competences(self):
        return [c.strip() for c in self.competences.split(",") if c.strip()]

    @property
    def liste_missions(self):
        return [m.strip(" -•\t") for m in self.missions.splitlines() if m.strip(" -•\t")]

    # Les proprietes ci-dessous travaillent sur `candidatures.all()` pour profiter d'un
    # prefetch_related("candidatures") dans les vues de liste.
    @property
    def nombre_candidatures(self):
        return len(self.candidatures.all())

    @property
    def nombre_nouvelles(self):
        return sum(1 for c in self.candidatures.all() if c.statut == StatutCandidature.RECUE)

    @property
    def derniere_candidature(self):
        dates = [c.date_candidature for c in self.candidatures.all()]
        return max(dates) if dates else None

    @property
    def nombre_recrutes(self):
        return sum(1 for c in self.candidatures.all() if c.recrute)

    @property
    def entretiens_planifies(self):
        return sum(1 for c in self.candidatures.all() if c.statut == StatutCandidature.ENTRETIEN)

    @property
    def etape(self):
        if self.statut in (StatutOffre.POURVUE, StatutOffre.FERMEE):
            return ETAPE_CLOTUREE
        candidatures = list(self.candidatures.all())
        if not candidatures:
            return ETAPE_AUCUNE
        if any(c.recrute for c in candidatures):
            return ETAPE_RECRUTE
        statuts = {c.statut for c in candidatures}
        if StatutCandidature.RETENUE in statuts:
            return ETAPE_RETENUE
        if StatutCandidature.ENTRETIEN in statuts:
            return ETAPE_ENTRETIEN
        if StatutCandidature.RECUE in statuts:
            return ETAPE_A_ANALYSER
        return ETAPE_REFUSEES


class Candidature(models.Model):
    """
    RG-11 : un candidat externe n'a pas de compte ; sa candidature (recue par les
    canaux de l'entreprise) est importee et renseignee MANUELLEMENT par le Responsable RH.
    """
    offre = models.ForeignKey(Offre, on_delete=models.CASCADE, related_name="candidatures")
    nom_candidat = models.CharField("Nom", max_length=150)
    prenom = models.CharField("Prénom", max_length=100, blank=True)
    email = models.EmailField()
    telephone = models.CharField("Téléphone", max_length=30, blank=True)
    localisation = models.CharField(max_length=100, blank=True)
    linkedin = models.URLField("Profil LinkedIn", blank=True)
    experience_annees = models.PositiveSmallIntegerField("Expérience (années)", null=True, blank=True)
    competences = models.TextField("Compétences clés", blank=True, help_text="Séparées par des virgules.")
    disponibilite = models.CharField("Disponibilité", max_length=100, blank=True)
    salaire_souhaite = models.PositiveIntegerField("Salaire souhaité (FCFA / mois)", null=True, blank=True)
    cv = models.FileField("CV", upload_to="candidatures/", blank=True)
    lettre_motivation = models.FileField("Lettre de motivation", upload_to="candidatures/", blank=True)
    document_fourni = models.FileField("Autre document fourni", upload_to="candidatures/", blank=True)
    statut = models.CharField(max_length=12, choices=StatutCandidature.choices, default=StatutCandidature.RECUE)
    commentaire = models.TextField(blank=True)
    date_entretien = models.DateTimeField("Entretien RH", null=True, blank=True)
    date_entretien_technique = models.DateTimeField("Entretien technique", null=True, blank=True)
    recrute = models.BooleanField("Candidat recruté", default=False)
    date_recrutement = models.DateTimeField(null=True, blank=True)
    saisie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="candidatures_saisies",
    )
    date_candidature = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_candidature"]

    @property
    def statut_choices(self):
        return StatutCandidature.choices

    @property
    def liste_competences(self):
        return [c.strip() for c in self.competences.split(",") if c.strip()]

    def __str__(self):
        return f"{self.nom_candidat} - {self.offre.poste}"
