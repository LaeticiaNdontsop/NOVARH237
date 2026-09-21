from django import forms
from accounts.models import Utilisateur, Role
from .models import Employe, Contrat, Remuneration, Document


class EmployeForm(forms.ModelForm):
    """
    BF-RH-01 / BF-ADM08 : creation/modification d'une fiche employe.
    Le compte de connexion (Utilisateur) doit deja exister (cree par l'Administrateur,
    BF-ADM01) ; ce formulaire cree la fiche RH associee (poste, service, etc.).
    """

    class Meta:
        model = Employe
        fields = [
            "utilisateur", "matricule", "poste", "service", "date_embauche", "date_naissance", "sexe", "statut",
            "manager", "lieu_travail", "nationalite", "situation_familiale",
            "contact_urgence_nom", "contact_urgence_telephone",
            "niveau_etudes", "etablissement", "specialite", "langues",
        ]
        widgets = {
            "date_embauche": forms.DateInput(attrs={"type": "date"}),
            "date_naissance": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "utilisateur": "Compte utilisateur associé",
            "matricule": "Identifiant (matricule)",
            "poste": "Poste",
            "service": "Département",
            "date_embauche": "Date d'embauche",
            "date_naissance": "Date de naissance",
            "sexe": "Genre",
            "statut": "Statut",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # On ne propose que les comptes RH/Employe qui n'ont pas encore de fiche
        # (sauf celui de l'instance en cours d'edition, s'il y en a une).
        queryset = Utilisateur.objects.filter(role__in=[Role.RH, Role.EMPLOYE])
        if self.instance.pk:
            # En edition : garder le compte deja lie + les comptes encore sans fiche.
            queryset = queryset.filter(pk=self.instance.utilisateur_id) | queryset.filter(fiche_employe__isnull=True)
        else:
            queryset = queryset.filter(fiche_employe__isnull=True)
        self.fields["utilisateur"].queryset = queryset.distinct()
        self.fields["matricule"].required = False
        managers = Employe.objects.filter(statut="ACTIF").select_related("utilisateur")
        if self.instance.pk:
            managers = managers.exclude(pk=self.instance.pk)
        self.fields["manager"].queryset = managers


class ContratForm(forms.ModelForm):
    """BF-RH-04 / BF-RH-05 : gestion des informations contractuelles."""

    class Meta:
        model = Contrat
        fields = [
            "type_contrat", "poste", "service", "salaire", "date_debut", "date_fin",
            "periode_essai_mois", "signe", "date_signature", "fichier_contrat",
        ]
        widgets = {
            "date_debut": forms.DateInput(attrs={"type": "date"}),
            "date_fin": forms.DateInput(attrs={"type": "date"}),
            "date_signature": forms.DateInput(attrs={"type": "date"}),
        }


class RemunerationForm(forms.ModelForm):
    """BF-RH-06 : gestion des remunerations (donnee confidentielle, RG-12)."""

    class Meta:
        model = Remuneration
        fields = ["salaire_base", "primes", "date_effective", "commentaire"]
        widgets = {"date_effective": forms.DateInput(attrs={"type": "date"})}


class DocumentForm(forms.ModelForm):
    """BF-RH-12 : ajout d'un document RH, obligatoirement rattache a un type (RG-17)."""

    class Meta:
        model = Document
        fields = ["type_document", "fichier"]
