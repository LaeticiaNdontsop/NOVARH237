from django.conf import settings
from django.db import models


class StatutEmploye(models.TextChoices):
    ACTIF = "ACTIF", "Actif"
    INACTIF = "INACTIF", "Inactif"


class Sexe(models.TextChoices):
    HOMME = "H", "Homme"
    FEMME = "F", "Femme"


class Employe(models.Model):
    """
    Entite Employe (CDC §9.1). Un Employe est toujours rattache a un compte
    Utilisateur (role RH ou EMPLOYE) via lequel il se connecte.

    RG-16 (v6) : l'Administrateur ET le Responsable RH peuvent creer, modifier
    et desactiver une fiche employe (BF-ADM08 / BF-RH-01). Ce module ne cree pas
    de compte de connexion : la creation du compte (BF-ADM01) reste separee et
    reservee a l'Administrateur ; ici on gere les informations RH de la fiche.
    """
    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="fiche_employe"
    )
    matricule = models.CharField(max_length=20, unique=True)
    poste = models.CharField(max_length=100)
    service = models.CharField(max_length=100)
    date_embauche = models.DateField()
    date_naissance = models.DateField(null=True, blank=True)
    sexe = models.CharField(max_length=1, choices=Sexe.choices, blank=True)
    statut = models.CharField(max_length=10, choices=StatutEmploye.choices, default=StatutEmploye.ACTIF)

    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fiches_employes_creees",
        help_text="Administrateur ou Responsable RH ayant cree la fiche (tracabilite, RG-13).",
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_desactivation = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Employe"
        verbose_name_plural = "Employes"
        ordering = ["utilisateur__last_name", "utilisateur__first_name"]

    def __str__(self):
        return f"{self.matricule} - {self.utilisateur.get_full_name()}"

    @property
    def nom_complet(self):
        return self.utilisateur.get_full_name()


class TypeContrat(models.TextChoices):
    CDI = "CDI", "Contrat a duree indeterminee (CDI)"
    CDD = "CDD", "Contrat a duree determinee (CDD)"
    STAGE = "STAGE", "Stage"
    PRESTATION = "PRESTATION", "Contrat de prestation"


class Contrat(models.Model):
    """
    Dossier contractuel (CDC §6.5.5) : type, poste, service, salaire, dates,
    periode d'essai et informations de signature.
    """
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name="contrats")
    type_contrat = models.CharField(max_length=12, choices=TypeContrat.choices)
    poste = models.CharField(max_length=100)
    service = models.CharField(max_length=100)
    salaire = models.DecimalField(max_digits=12, decimal_places=2)
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True, help_text="Laisser vide pour un CDI.")
    periode_essai_mois = models.PositiveSmallIntegerField(default=0)
    signe = models.BooleanField(default=False)
    date_signature = models.DateField(null=True, blank=True)
    fichier_contrat = models.FileField(upload_to="contrats/", null=True, blank=True)

    class Meta:
        verbose_name = "Contrat"
        verbose_name_plural = "Contrats"
        ordering = ["-date_debut"]

    def __str__(self):
        return f"{self.get_type_contrat_display()} - {self.employe.nom_complet}"


class Remuneration(models.Model):
    """
    RG-12 : donnee sensible, accessible uniquement aux utilisateurs autorises
    (Administrateur, Responsable RH, et l'employe concerne pour ses propres donnees).
    L'application des controles d'acces se fait au niveau des vues (voir mixins.py).
    """
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name="remunerations")
    salaire_base = models.DecimalField(max_digits=12, decimal_places=2)
    primes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date_effective = models.DateField()
    commentaire = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Remuneration"
        verbose_name_plural = "Remunerations"
        ordering = ["-date_effective"]

    def __str__(self):
        return f"Remuneration {self.employe.nom_complet} - {self.date_effective}"

    @property
    def total(self):
        return self.salaire_base + self.primes


class TypeDocument(models.TextChoices):
    """6 types definis au CDC §9.2. RG-17 : tout document doit etre rattache a l'un d'eux."""
    CONTRAT = "CONTRAT", "Contrat de travail"
    CNI = "CNI", "Piece d'identite (CNI)"
    DIPLOME = "DIPLOME", "Diplome / certificat"
    CV = "CV", "CV"
    ATTESTATION = "ATTESTATION", "Attestation de travail"
    BULLETIN = "BULLETIN", "Bulletin de paie"


class Document(models.Model):
    """
    RG-05 / RG-06 : un employe ne consulte que ses propres documents ; le Responsable
    RH ne peut pas consulter les documents des autres employes (restriction maintenue
    meme s'il gere par ailleurs les fiches employes).
    """
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name="documents")
    type_document = models.CharField(max_length=15, choices=TypeDocument.choices)
    fichier = models.FileField(upload_to="documents/")
    date_ajout = models.DateTimeField(auto_now_add=True)
    ajoute_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="documents_ajoutes"
    )

    class Meta:
        verbose_name = "Document RH"
        verbose_name_plural = "Documents RH"
        ordering = ["-date_ajout"]

    def __str__(self):
        return f"{self.get_type_document_display()} - {self.employe.nom_complet}"
