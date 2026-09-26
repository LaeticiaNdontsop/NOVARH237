from django import forms

from accounts.models import Utilisateur
from demandes.validators import valider_fichier_justificatif
from employees.models import Employe, StatutEmploye, TypeContrat
from .models import Candidature, Formation, ModeTravail, Offre, ParticipationFormation, StatutCandidature, StatutOffre


class FormationForm(forms.ModelForm):
    """RG-23 : le RH cible les employes concernes ; pas d'inscription libre."""
    employes_cibles = forms.ModelMultipleChoiceField(
        label="Employés ciblés",
        queryset=Employe.objects.none(),
        widget=forms.SelectMultiple(attrs={"size": 8}),
        help_text="Employés concernés par cette formation (Ctrl/Cmd + clic pour en choisir plusieurs).",
    )

    class Meta:
        model = Formation
        fields = [
            "titre", "description", "date_formation", "date_fin", "heure_debut", "heure_fin",
            "duree_heures", "lieu", "formateur", "annulee",
        ]
        widgets = {
            "date_formation": forms.DateInput(attrs={"type": "date"}),
            "date_fin": forms.DateInput(attrs={"type": "date"}),
            "heure_debut": forms.TimeInput(attrs={"type": "time"}),
            "heure_fin": forms.TimeInput(attrs={"type": "time"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employes_cibles"].queryset = Employe.objects.filter(
            statut=StatutEmploye.ACTIF
        ).select_related("utilisateur")
        if self.instance.pk:
            self.fields["employes_cibles"].initial = list(
                self.instance.participations.values_list("employe_id", flat=True)
            )
        else:
            del self.fields["annulee"]
        self.nouveaux_cibles = []

    def clean(self):
        cleaned = super().clean()
        debut, fin = cleaned.get("date_formation"), cleaned.get("date_fin")
        if debut and fin and fin < debut:
            raise forms.ValidationError("La date de fin ne peut pas être antérieure à la date de début.")
        return cleaned

    def save(self, commit=True):
        formation = super().save(commit=commit)
        if commit:
            cibles = set(self.cleaned_data["employes_cibles"])
            existants = {p.employe_id: p for p in formation.participations.all()}
            formation.participations.exclude(employe__in=cibles).delete()
            for employe in cibles:
                if employe.pk not in existants:
                    ParticipationFormation.objects.create(formation=formation, employe=employe)
                    self.nouveaux_cibles.append(employe)
        return formation


class OffreForm(forms.ModelForm):
    type_contrat = forms.ChoiceField(label="Type de contrat", choices=TypeContrat.choices)
    statut = forms.ChoiceField(label="Statut de l'offre", choices=StatutOffre.choices, required=False)

    class Meta:
        model = Offre
        fields = [
            "poste", "departement", "type_contrat", "lieu", "mode_travail", "date_publication",
            "date_limite", "description", "missions", "competences", "responsable", "statut",
        ]
        widgets = {
            "date_publication": forms.DateInput(attrs={"type": "date"}),
            "date_limite": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "missions": forms.Textarea(attrs={"rows": 4, "placeholder": "Une mission par ligne"}),
            "competences": forms.TextInput(attrs={"placeholder": "Marketing digital, SEO, Leadership"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["responsable"].queryset = Utilisateur.objects.filter(
            role__in=["ADMIN", "RH"], is_active=True
        )
        self.fields["mode_travail"].required = False
        # A la creation, le statut est choisi via les boutons « Publier » / « Brouillon ».
        if not self.instance.pk:
            del self.fields["statut"]

    def clean_statut(self):
        return self.cleaned_data.get("statut") or self.instance.statut or StatutOffre.BROUILLON

    def clean(self):
        cleaned = super().clean()
        debut, fin = cleaned.get("date_publication"), cleaned.get("date_limite")
        if debut and fin and fin < debut:
            raise forms.ValidationError("La date d'expiration ne peut pas être antérieure à la date de publication.")
        return cleaned


class CandidatureForm(forms.ModelForm):
    """Saisie manuelle, par le Responsable RH, d'une candidature recue (RG-11 : pas de compte candidat)."""
    statut = forms.ChoiceField(
        label="Statut",
        choices=(
            (StatutCandidature.ENTRETIEN, "Entretien planifié"),
            (StatutCandidature.RETENUE, "Candidat recruté"),
        ),
    )

    class Meta:
        model = Candidature
        fields = [
            "offre", "nom_candidat", "prenom", "email", "telephone", "localisation", "linkedin", "experience_annees",
            "disponibilite", "salaire_souhaite", "competences", "cv", "lettre_motivation", "commentaire",
            "document_fourni", "statut",
        ]
        widgets = {
            "commentaire": forms.Textarea(attrs={"rows": 3}),
            "competences": forms.TextInput(attrs={"placeholder": "Stratégie digitale, SEO, Leadership"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["statut"].initial = StatutCandidature.ENTRETIEN

    def _valider(self, champ):
        fichier = self.cleaned_data.get(champ)
        if fichier and hasattr(fichier, "size"):
            valider_fichier_justificatif(fichier)
        return fichier

    def clean_cv(self):
        return self._valider("cv")

    def clean_lettre_motivation(self):
        return self._valider("lettre_motivation")

    def clean_document_fourni(self):
        return self._valider("document_fourni")
