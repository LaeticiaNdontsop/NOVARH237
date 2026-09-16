from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    """
    Trois roles fonctionnels (cf. CDC §5).
    Le Responsable RH est modelise comme un cas particulier d'Employe : il herite
    de toutes les fonctionnalites Employe et beneficie de droits supplementaires.
    On ne cree pas de 4e role : la distinction se fait uniquement via ce champ.
    """
    ADMIN = "ADMIN", "Administrateur"
    RH = "RH", "Responsable RH"
    EMPLOYE = "EMPLOYE", "Employe"


class Utilisateur(AbstractUser):
    """
    Utilisateur d'authentification NOVA RH.
    - RG-01 : tout acces necessite une authentification (gere par Django auth).
    - RG-02 : les droits dependent du role (champ `role` ci-dessous).
    - RG-03 : seul l'Administrateur cree des comptes utilisateurs (voir vues accounts).
    - BF-EMP02 : l'utilisateur peut modifier ses coordonnees (telephone, adresse, photo)
      et son mot de passe ; les informations professionnelles restent en lecture seule
      pour l'Employe (elles vivent sur le modele Employe, cf. app "employees").
    """
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.EMPLOYE)
    telephone = models.CharField(max_length=20, blank=True)
    adresse = models.CharField(max_length=255, blank=True)
    photo = models.ImageField(upload_to="photos_profil/", blank=True, null=True)

    # BF-ADM02 : mot de passe temporaire attribue par l'Administrateur.
    # A la premiere connexion, l'utilisateur est invite a le changer.
    doit_changer_mot_de_passe = models.BooleanField(default=True)

    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    # --- Raccourcis de role, utilises partout dans le code (vues, templates, permissions) ---
    @property
    def est_admin(self):
        return self.role == Role.ADMIN

    @property
    def est_rh(self):
        return self.role == Role.RH

    @property
    def est_employe(self):
        # Au sens large : un Responsable RH EST AUSSI un employe (RG-04).
        return self.role in (Role.RH, Role.EMPLOYE)

    @property
    def peut_gerer_employes(self):
        # RG-16 (v6) : Administrateur ET Responsable RH peuvent gerer les fiches employes.
        return self.role in (Role.ADMIN, Role.RH)
