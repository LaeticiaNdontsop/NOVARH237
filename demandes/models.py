"""
Module "demandes" : implemente le circuit de validation decrit au CDC pour les
conges/permissions (§6.4), les absences, et les demissions.

Circuit conges/permissions (RG dediees) :
    Employe soumet -> Responsable RH (1ere validation) -> Administrateur (decision
    finale) -> Responsable RH (notification/cloture) -> Employe informe.

Chaque etape est materialisee par un statut associe a une couleur :
    - orange : demande en attente de traitement (RH ou Admin)
    - vert   : demande approuvee et cloturee
    - rouge  : demande rejetee (a n'importe quelle etape)

Reaffectation automatique : si le Responsable RH assigne a une demande ne la
traite pas dans un delai de 24h, elle est automatiquement reaffectee a un autre
Responsable RH actif (voir `reaffecter_demandes_expirees` ci-dessous, appelee
depuis les vues de liste RH).
"""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from employees.models import Employe


DELAI_REAFFECTATION = timedelta(hours=24)


# ---------------------------------------------------------------------------
# Conges & permissions
# ---------------------------------------------------------------------------
class TypeDemande(models.TextChoices):
    CONGE = "CONGE", "Conge"
    PERMISSION = "PERMISSION", "Permission"


class StatutDemande(models.TextChoices):
    EN_ATTENTE_RH = "EN_ATTENTE_RH", "En attente de traitement (RH)"
    EN_ATTENTE_ADMIN = "EN_ATTENTE_ADMIN", "Transmise a l'Administrateur"
    APPROUVEE_A_NOTIFIER = "APPROUVEE_A_NOTIFIER", "Approuvee - en attente de notification (RH)"
    APPROUVEE = "APPROUVEE", "Approuvee"
    REJETEE_RH = "REJETEE_RH", "Rejetee par le Responsable RH"
    REJETEE_ADMIN = "REJETEE_ADMIN", "Rejetee par l'Administrateur"


# Statuts pour lesquels la demande est encore "en circuit" (couleur orange)
STATUTS_EN_ATTENTE = {
    StatutDemande.EN_ATTENTE_RH,
    StatutDemande.EN_ATTENTE_ADMIN,
    StatutDemande.APPROUVEE_A_NOTIFIER,
}
STATUTS_REJETES = {StatutDemande.REJETEE_RH, StatutDemande.REJETEE_ADMIN}


class DemandeConge(models.Model):
    """
    Une demande de conge OU de permission (meme circuit de validation, cf. CDC).
    """
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name="demandes_conge")
    type_demande = models.CharField(max_length=12, choices=TypeDemande.choices)
    date_debut = models.DateField()
    date_fin = models.DateField()
    motif = models.CharField(max_length=255)

    statut = models.CharField(max_length=25, choices=StatutDemande.choices, default=StatutDemande.EN_ATTENTE_RH)
    date_soumission = models.DateTimeField(auto_now_add=True)

    # Etape 1 : traitement RH
    rh_assigne = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="demandes_conge_assignees",
    )
    date_limite_rh = models.DateTimeField(null=True, blank=True)
    commentaire_rh = models.CharField(max_length=255, blank=True)
    date_traitement_rh = models.DateTimeField(null=True, blank=True)

    # Etape 2 : decision Admin
    admin_assigne = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="demandes_conge_a_decider",
    )
    date_limite_admin = models.DateTimeField(null=True, blank=True)
    admin_traitant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="demandes_conge_decidees",
    )
    commentaire_admin = models.CharField(max_length=255, blank=True)
    date_decision_admin = models.DateTimeField(null=True, blank=True)

    # Etape 3 : cloture / notification par le RH
    date_limite_notification = models.DateTimeField(null=True, blank=True)
    date_cloture = models.DateTimeField(null=True, blank=True)

    # RG-20/RG-21 : tracabilite des reaffectations automatiques
    nombre_reaffectations = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Demande de conge/permission"
        verbose_name_plural = "Demandes de conges/permissions"
        ordering = ["-date_soumission"]

    def __str__(self):
        return f"{self.get_type_demande_display()} - {self.employe.nom_complet} ({self.date_debut} -> {self.date_fin})"

    @property
    def couleur(self):
        if self.statut in STATUTS_REJETES:
            return "rouge"
        if self.statut == StatutDemande.APPROUVEE:
            return "vert"
        return "orange"

    @property
    def duree_jours(self):
        return (self.date_fin - self.date_debut).days + 1

    # --- Transitions du circuit -------------------------------------------------
    def transmettre_a_admin(self, rh_utilisateur, commentaire=""):
        self.statut = StatutDemande.EN_ATTENTE_ADMIN
        self.commentaire_rh = commentaire
        self.date_traitement_rh = timezone.now()
        self.admin_assigne = choisir_utilisateur_disponible("ADMIN")
        self.date_limite_admin = timezone.now() + DELAI_REAFFECTATION
        self.save(update_fields=[
            "statut", "commentaire_rh", "date_traitement_rh", "admin_assigne", "date_limite_admin"
        ])

    def rejeter_par_rh(self, rh_utilisateur, commentaire=""):
        self.statut = StatutDemande.REJETEE_RH
        self.commentaire_rh = commentaire
        self.date_traitement_rh = timezone.now()
        self.save(update_fields=["statut", "commentaire_rh", "date_traitement_rh"])

    def approuver_par_admin(self, admin_utilisateur, commentaire=""):
        self.statut = StatutDemande.APPROUVEE_A_NOTIFIER
        self.admin_traitant = admin_utilisateur
        self.commentaire_admin = commentaire
        self.date_decision_admin = timezone.now()
        self.date_limite_notification = timezone.now() + DELAI_REAFFECTATION
        self.save(update_fields=[
            "statut", "admin_traitant", "commentaire_admin", "date_decision_admin", "date_limite_notification"
        ])

    def rejeter_par_admin(self, admin_utilisateur, commentaire=""):
        self.statut = StatutDemande.REJETEE_ADMIN
        self.admin_traitant = admin_utilisateur
        self.commentaire_admin = commentaire
        self.date_decision_admin = timezone.now()
        self.save(update_fields=["statut", "admin_traitant", "commentaire_admin", "date_decision_admin"])

    def cloturer_par_rh(self):
        """Etape finale : le RH notifie l'employe, la demande devient definitivement verte."""
        self.statut = StatutDemande.APPROUVEE
        self.date_cloture = timezone.now()
        self.save(update_fields=["statut", "date_cloture"])


def choisir_utilisateur_disponible(role, exclure=None):
    """
    RG-20 : choisit l'utilisateur (RH ou Admin) le moins charge parmi les comptes
    actifs de ce role, pour la premiere affectation ou une reaffectation.
    """
    from accounts.models import Utilisateur, Role as RoleChoices

    qs = Utilisateur.objects.filter(role=role, is_active=True)
    if exclure:
        qs = qs.exclude(pk=exclure.pk)
    candidats = list(qs)
    if not candidats:
        return None
    if role == "RH":
        candidats.sort(key=lambda u: DemandeConge.objects.filter(
            rh_assigne=u, statut=StatutDemande.EN_ATTENTE_RH
        ).count())
    else:
        candidats.sort(key=lambda u: DemandeConge.objects.filter(
            admin_assigne=u, statut=StatutDemande.EN_ATTENTE_ADMIN
        ).count())
    return candidats[0]


# Alias conserve pour compatibilite avec le code existant
def choisir_rh_disponible(exclure=None):
    return choisir_utilisateur_disponible("RH", exclure=exclure)


class AlerteSysteme(models.Model):
    """
    RG-21 : si aucune reaffectation n'est possible (un seul RH ou Admin actif dans
    le systeme), la demande reste en attente (orange) et une alerte est enregistree
    pour signalement (elle alimentera le module Notifications du Jour 3).
    """
    message = models.CharField(max_length=255)
    date_creation = models.DateTimeField(auto_now_add=True)
    resolue = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Alerte systeme"
        verbose_name_plural = "Alertes systeme"
        ordering = ["-date_creation"]

    def __str__(self):
        return self.message


def reaffecter_demandes_expirees():
    """
    A appeler depuis les vues de liste RH/Admin (ou une tache planifiee/cron en
    production : `python manage.py verifier_delais_demandes`).

    RG-20 : reaffecte automatiquement, a chaque etape du circuit, toute demande
    dont le delai de 24h est depasse, vers un autre utilisateur actif du meme role.
    RG-21 : si aucune reaffectation n'est possible, la demande reste EN ATTENTE
    (orange) et une alerte est enregistree.
    """
    maintenant = timezone.now()

    # --- Etape 1 : traitement RH ---
    for demande in DemandeConge.objects.filter(statut=StatutDemande.EN_ATTENTE_RH, date_limite_rh__lt=maintenant):
        nouveau = choisir_utilisateur_disponible("RH", exclure=demande.rh_assigne)
        if nouveau and nouveau != demande.rh_assigne:
            demande.rh_assigne = nouveau
            demande.date_limite_rh = maintenant + DELAI_REAFFECTATION
            demande.nombre_reaffectations += 1
            demande.save(update_fields=["rh_assigne", "date_limite_rh", "nombre_reaffectations"])
        else:
            AlerteSysteme.objects.get_or_create(
                message=f"Demande #{demande.pk} ({demande.employe.nom_complet}) : "
                        f"aucun autre Responsable RH disponible pour reaffectation.",
                resolue=False,
            )

    # --- Etape 2 : decision Admin ---
    for demande in DemandeConge.objects.filter(statut=StatutDemande.EN_ATTENTE_ADMIN, date_limite_admin__lt=maintenant):
        nouveau = choisir_utilisateur_disponible("ADMIN", exclure=demande.admin_assigne)
        if nouveau and nouveau != demande.admin_assigne:
            demande.admin_assigne = nouveau
            demande.date_limite_admin = maintenant + DELAI_REAFFECTATION
            demande.nombre_reaffectations += 1
            demande.save(update_fields=["admin_assigne", "date_limite_admin", "nombre_reaffectations"])
        else:
            AlerteSysteme.objects.get_or_create(
                message=f"Demande #{demande.pk} ({demande.employe.nom_complet}) : "
                        f"aucun autre Administrateur disponible pour reaffectation.",
                resolue=False,
            )

    # --- Etape 3 : notification par le RH ---
    for demande in DemandeConge.objects.filter(
        statut=StatutDemande.APPROUVEE_A_NOTIFIER, date_limite_notification__lt=maintenant
    ):
        nouveau = choisir_utilisateur_disponible("RH", exclure=demande.rh_assigne)
        if nouveau and nouveau != demande.rh_assigne:
            demande.rh_assigne = nouveau
            demande.date_limite_notification = maintenant + DELAI_REAFFECTATION
            demande.nombre_reaffectations += 1
            demande.save(update_fields=["rh_assigne", "date_limite_notification", "nombre_reaffectations"])
        else:
            AlerteSysteme.objects.get_or_create(
                message=f"Demande #{demande.pk} ({demande.employe.nom_complet}) : "
                        f"approuvee mais aucun Responsable RH disponible pour notifier l'employe.",
                resolue=False,
            )


# ---------------------------------------------------------------------------
# Absences
# ---------------------------------------------------------------------------
class StatutAbsence(models.TextChoices):
    EN_ATTENTE = "EN_ATTENTE", "En attente de validation (RH)"
    APPROUVEE = "APPROUVEE", "Approuvee"
    REJETEE = "REJETEE", "Rejetee"


class Absence(models.Model):
    """
    Declaration d'absence par l'employe, validee directement par le Responsable RH
    (circuit plus court que les conges/permissions : pas d'escalade Admin requise).
    """
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name="absences")
    date_debut = models.DateField()
    date_fin = models.DateField()
    motif = models.CharField(max_length=255)
    justificatif = models.FileField(upload_to="justificatifs_absence/", null=True, blank=True)

    statut = models.CharField(max_length=10, choices=StatutAbsence.choices, default=StatutAbsence.EN_ATTENTE)
    date_declaration = models.DateTimeField(auto_now_add=True)

    traite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="absences_traitees",
    )
    commentaire_rh = models.CharField(max_length=255, blank=True)
    date_traitement = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Absence"
        verbose_name_plural = "Absences"
        ordering = ["-date_declaration"]

    def __str__(self):
        return f"Absence {self.employe.nom_complet} ({self.date_debut} -> {self.date_fin})"

    @property
    def couleur(self):
        if self.statut == StatutAbsence.APPROUVEE:
            return "vert"
        if self.statut == StatutAbsence.REJETEE:
            return "rouge"
        return "orange"

    def valider(self, utilisateur, commentaire=""):
        self.statut = StatutAbsence.APPROUVEE
        self.traite_par = utilisateur
        self.commentaire_rh = commentaire
        self.date_traitement = timezone.now()
        self.save(update_fields=["statut", "traite_par", "commentaire_rh", "date_traitement"])

    def rejeter(self, utilisateur, commentaire=""):
        self.statut = StatutAbsence.REJETEE
        self.traite_par = utilisateur
        self.commentaire_rh = commentaire
        self.date_traitement = timezone.now()
        self.save(update_fields=["statut", "traite_par", "commentaire_rh", "date_traitement"])


# ---------------------------------------------------------------------------
# Demission
# ---------------------------------------------------------------------------
class StatutDemission(models.TextChoices):
    DECLAREE = "DECLAREE", "Declaree - en attente de transmission (RH)"
    TRANSMISE_ADMIN = "TRANSMISE_ADMIN", "Transmise a l'Administrateur"
    PREAVIS_DEFINI = "PREAVIS_DEFINI", "Preavis defini - a communiquer (RH)"
    COMMUNIQUEE = "COMMUNIQUEE", "Decision communiquee a l'employe"


class Demission(models.Model):
    """
    RG-09 : une demission est une declaration de l'employe, jamais une demande a
    approuver ou refuser.
    RG-22 : la declaration suit neanmoins le meme circuit de transmission que les
    conges/permissions -- Employe -> Responsable RH -> Administrateur -> Responsable
    RH -> Employe -- mais uniquement pour DETERMINER LES MODALITES (le preavis) ;
    la demission elle-meme n'est jamais rejetee. Le Responsable RH transmet puis
    restitue la decision de l'Administrateur SANS la modifier.
    """
    employe = models.OneToOneField(Employe, on_delete=models.CASCADE, related_name="demission")
    date_declaration = models.DateTimeField(auto_now_add=True)
    date_effective_souhaitee = models.DateField()
    motif = models.CharField(max_length=255, blank=True)

    statut = models.CharField(max_length=20, choices=StatutDemission.choices, default=StatutDemission.DECLAREE)

    # Etape 1 : transmission par le Responsable RH
    rh_transmetteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="demissions_transmises",
    )
    date_transmission = models.DateTimeField(null=True, blank=True)

    # Etape 2 : decision de l'Administrateur (modalites / preavis uniquement)
    preavis_jours = models.PositiveSmallIntegerField(null=True, blank=True)
    traite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="demissions_traitees",
    )
    commentaire_admin = models.CharField(max_length=255, blank=True)
    date_decision_admin = models.DateTimeField(null=True, blank=True)

    # Etape 3 : communication finale a l'employe par le Responsable RH (sans modification)
    date_communication = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Demission"
        verbose_name_plural = "Demissions"

    def __str__(self):
        return f"Demission {self.employe.nom_complet}"

    @property
    def couleur(self):
        # Toujours "orange" tant que la communication finale n'a pas eu lieu :
        # ce n'est pas une decision d'acceptation/refus (RG-09), juste un suivi de traitement.
        return "vert" if self.statut == StatutDemission.COMMUNIQUEE else "orange"

    def transmettre_a_admin(self, rh_utilisateur):
        self.statut = StatutDemission.TRANSMISE_ADMIN
        self.rh_transmetteur = rh_utilisateur
        self.date_transmission = timezone.now()
        self.save(update_fields=["statut", "rh_transmetteur", "date_transmission"])

    def definir_preavis(self, admin_utilisateur, jours, commentaire=""):
        self.preavis_jours = jours
        self.statut = StatutDemission.PREAVIS_DEFINI
        self.traite_par = admin_utilisateur
        self.commentaire_admin = commentaire
        self.date_decision_admin = timezone.now()
        self.save(update_fields=[
            "preavis_jours", "statut", "traite_par", "commentaire_admin", "date_decision_admin"
        ])

    def communiquer_a_employe(self):
        """Le Responsable RH transmet la decision a l'employe SANS la modifier (RG-22)."""
        self.statut = StatutDemission.COMMUNIQUEE
        self.date_communication = timezone.now()
        self.save(update_fields=["statut", "date_communication"])
